import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from fractions import Fraction
from types import SimpleNamespace
from unittest import mock


MODULE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools_src", "generate.py")
DETECTOR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tools_src", "detect_video_capabilities.py"
)


def load_generate_module():
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        spec = importlib.util.spec_from_file_location("generate_under_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def load_detector_module():
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        spec = importlib.util.spec_from_file_location("detect_video_capabilities_under_test", DETECTOR_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, payload):
        self.payload = payload if isinstance(payload, bytes) else payload.encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class GenerateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generate = load_generate_module()
        cls.detector = load_detector_module()

    def setUp(self):
        self.generate.COMFY_URL = None
        self.generate.ACTIVE_VIDEO_CONFIG = None
        self.generate.DEVICE = {
            "tier": "sdxl",
            "checkpoint": "test.safetensors",
            "default_width": 1024,
            "default_height": 1024,
        }

    def test_url_resolution_prioritises_cli_then_environment_then_explicit_config(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as config_file:
            json.dump({"comfyui_url": "http://config:8188/"}, config_file)
            config_path = config_file.name
        try:
            with mock.patch.dict(os.environ, {"COMFY_URL": "http://env:8188/"}, clear=True):
                self.assertEqual("http://cli:8188", self.generate.resolve_comfy_url("http://cli:8188/", config_path))
                self.assertEqual("http://env:8188", self.generate.resolve_comfy_url(config_path=config_path))
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual("http://config:8188", self.generate.resolve_comfy_url(config_path=config_path))
                with self.assertRaises(RuntimeError):
                    self.generate.resolve_comfy_url()
        finally:
            os.unlink(config_path)

    def test_parser_accepts_runtime_options_before_or_after_task(self):
        with mock.patch.object(self.generate, "build_concept", return_value=({}, "1")), \
                mock.patch.object(self.generate, "submit_and_wait", return_value={"outputs": {}}), \
                mock.patch.object(self.generate, "download_outputs", return_value=[]) as download:
            self.generate.main(["--comfy-url", "http://before:8188", "--timeout", "12", "concept", "--prompt", "x"])
            self.generate.main(["concept", "--comfy-url", "http://after:8188", "--timeout", "13", "--prompt", "x"])
        self.assertEqual("http://before:8188", download.call_args_list[0].kwargs["comfy_url"])
        self.assertEqual(12.0, download.call_args_list[0].kwargs["request_timeout"])
        self.assertEqual("http://after:8188", download.call_args_list[1].kwargs["comfy_url"])
        self.assertEqual(13.0, download.call_args_list[1].kwargs["request_timeout"])

    def test_boundary_validators_reject_invalid_values(self):
        with self.assertRaises(ValueError):
            self.generate.validate_batch(0)
        with self.assertRaises(ValueError):
            self.generate.validate_dimensions(1024, 1025)
        for value in (-0.01, 1.01, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.generate.validate_unit_interval(value, "weight")
        for value in (0, -1, 4.01, float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.generate.validate_scale(value)
        with self.assertRaises(ValueError):
            self.generate.build_upscale("x", "image.png", scale=4.1)
        with self.assertRaises(ValueError):
            self.generate.build_inpaint("x", "image.png", "mask.png", denoise=-0.1)

    def test_sd15_controlnet_and_ipadapter_features_fail_fast(self):
        self.generate.DEVICE["tier"] = "sd15"
        with self.assertRaisesRegex(RuntimeError, "sd15"):
            self.generate.build_pose_only("x", "pose.png")
        with self.assertRaisesRegex(RuntimeError, "sd15"):
            self.generate.build_style_lock("x", "character.png")
        with self.assertRaisesRegex(RuntimeError, "sd15"):
            self.generate.build_icon_asset("x", structure_ref_filename="ref.png")
        # A plain icon does not use either SDXL-only add-on and remains available.
        graph, _ = self.generate.build_icon_asset("x")
        self.assertEqual("CheckpointLoaderSimple", graph["1"]["class_type"])

    def test_submit_and_wait_uses_same_injected_url_and_keeps_prompt_id_on_retry(self):
        opener = mock.Mock(side_effect=[
            Response('{"prompt_id":"prompt-1"}'),
            urllib.error.URLError("temporary"),
            Response('{"prompt-1":{"status":{"completed":true}}}'),
        ])
        with mock.patch.object(self.generate.urllib.request, "urlopen", opener), \
                mock.patch.object(self.generate.time, "sleep"):
            result = self.generate.submit_and_wait(
                {"1": {}}, timeout=10, comfy_url="http://server:8188/", poll_interval=0,
            )
        self.assertTrue(result["status"]["completed"])
        first_request = opener.call_args_list[0].args[0]
        self.assertEqual("http://server:8188/prompt", first_request.full_url)
        self.assertEqual("http://server:8188/history/prompt-1", opener.call_args_list[2].args[0])

    def test_submit_and_wait_bounded_poll_retry_reports_prompt_id(self):
        opener = mock.Mock(side_effect=[
            Response('{"prompt_id":"prompt-retry"}'),
            urllib.error.URLError("temporary"),
            urllib.error.URLError("temporary"),
            urllib.error.URLError("temporary"),
        ])
        with mock.patch.object(self.generate.urllib.request, "urlopen", opener), \
                mock.patch.object(self.generate.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "prompt-retry"):
                self.generate.submit_and_wait(
                    {"1": {}}, timeout=10, comfy_url="http://server:8188", poll_interval=0,
                    max_poll_retries=2,
                )

    def test_submit_timeout_reports_prompt_id(self):
        opener = mock.Mock(side_effect=[
            Response('{"prompt_id":"prompt-timeout"}'),
            Response("{}"),
        ])
        # start, loop check, remaining, post-poll remaining, next loop check
        clock = mock.Mock(side_effect=[0.0, 0.0, 0.0, 1.0, 1.0])
        with mock.patch.object(self.generate.urllib.request, "urlopen", opener), \
                mock.patch.object(self.generate.time, "monotonic", clock), \
                mock.patch.object(self.generate.time, "sleep"):
            with self.assertRaisesRegex(TimeoutError, "prompt-timeout"):
                self.generate.submit_and_wait(
                    {"1": {}}, timeout=0.5, comfy_url="http://server:8188", poll_interval=0,
                )

    def test_timeout_only_attempts_exact_pending_queue_deletion(self):
        opener = mock.Mock(return_value=Response("{}"))
        with mock.patch.object(self.generate.urllib.request, "urlopen", opener):
            status = self.generate._cancel_exact_pending_prompt(
                "prompt-exact", "http://server:8188", 3,
                {"status": "pending"},
            )
        self.assertTrue(status["cancel_attempted"])
        request = opener.call_args.args[0]
        self.assertEqual("http://server:8188/queue", request.full_url)
        self.assertNotIn("interrupt", request.full_url)
        self.assertEqual({"delete": ["prompt-exact"]}, json.loads(request.data.decode()))

    def test_submit_rejects_malformed_queue_and_history_shapes(self):
        with mock.patch.object(self.generate.urllib.request, "urlopen", return_value=Response("[]")):
            with self.assertRaisesRegex(RuntimeError, "JSON object"):
                self.generate.submit_and_wait({}, comfy_url="http://server:8188")

        for history in ('{"p":null}', '{"p":{"status":null}}'):
            with self.subTest(history=history), \
                    mock.patch.object(self.generate.urllib.request, "urlopen", side_effect=[
                        Response('{"prompt_id":"p"}'), Response(history),
                    ]):
                with self.assertRaisesRegex(RuntimeError, "prompt_id=p"):
                    self.generate.submit_and_wait({}, comfy_url="http://server:8188")

    def test_download_outputs_encodes_all_query_values_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as output_dir:
            history = {"outputs": {"7": {"images": [{
                "filename": "safe.png", "subfolder": "nested/ref", "type": "temp&preview",
            }]}}}
            response = mock.Mock()
            response.__enter__ = mock.Mock(return_value=response)
            response.__exit__ = mock.Mock(return_value=False)
            response.read.side_effect = [b"image-bytes", b""]
            with mock.patch.object(self.generate.urllib.request, "urlopen", return_value=response) as opener:
                paths = self.generate.download_outputs(
                    history, output_dir, comfy_url="http://server:8188", request_timeout=7,
                )
            self.assertEqual([os.path.join(output_dir, "safe.png")], paths)
            url = opener.call_args.args[0]
            self.assertIn("filename=safe.png", url)
            self.assertIn("subfolder=nested%2Fref", url)
            self.assertIn("type=temp%26preview", url)
            self.assertEqual(7, opener.call_args.kwargs["timeout"])
            with open(paths[0], "rb") as downloaded:
                self.assertEqual(b"image-bytes", downloaded.read())

            partial_response = mock.Mock()
            partial_response.__enter__ = mock.Mock(return_value=partial_response)
            partial_response.__exit__ = mock.Mock(return_value=False)
            partial_response.read.side_effect = [b"partial", TimeoutError("download stalled")]
            incomplete = {"outputs": {"7": {"images": [{"filename": "incomplete.png"}]}}}
            with mock.patch.object(self.generate.urllib.request, "urlopen", return_value=partial_response):
                with self.assertRaises(TimeoutError):
                    self.generate.download_outputs(incomplete, output_dir, comfy_url="http://server:8188")
            self.assertFalse(os.path.exists(os.path.join(output_dir, "incomplete.png")))
            self.assertFalse(any(name.endswith(".part") for name in os.listdir(output_dir)))

            unsafe = {"outputs": {"7": {"images": [{"filename": "../escape.png"}]}}}
            with self.assertRaises(ValueError):
                self.generate.download_outputs(unsafe, output_dir, comfy_url="http://server:8188")
            with self.assertRaises(RuntimeError):
                self.generate.download_outputs({"outputs": {}}, output_dir, comfy_url="http://server:8188")

    def test_main_downloads_only_transparent_saveimage_after_background_removal(self):
        graph = {"1": {"class_type": "SaveImage", "inputs": {}}}
        with mock.patch.object(self.generate, "build_concept", return_value=(graph, "1")), \
                mock.patch.object(self.generate, "attach_bg_removal", return_value="9") as attach, \
                mock.patch.object(self.generate, "submit_and_wait", return_value={"outputs": {}}), \
                mock.patch.object(self.generate, "download_outputs", return_value=["out.png"]) as download:
            self.generate.main(["--comfy-url", "http://server:8188", "concept", "--prompt", "x", "--remove-bg"])
        attach.assert_called_once_with(graph, "1")
        self.assertEqual(["9"], download.call_args.kwargs["node_ids"])

    def test_video_backend_unsupported_combination_fails_fast_without_argv_fallback(self):
        with mock.patch.object(self.generate.sys, "argv", ["test_generate.py"]):
            with self.assertRaisesRegex(SystemExit, "character_video"):
                self.generate.require_video_backend("character_video", "wan")

    def test_video_timeout_defaults_and_cli_override(self):
        common_patches = {
            "configure_video_capability": mock.patch.object(
                self.generate, "configure_video_capability", return_value="h3"
            ),
            "video_canvas": mock.patch.object(self.generate, "video_canvas", return_value=(64, 64)),
            "upload_image": mock.patch.object(self.generate, "upload_image", return_value="still.png"),
            "run_i2v": mock.patch.object(self.generate, "run_i2v", return_value=({}, "1")),
            "download_outputs": mock.patch.object(self.generate, "download_outputs", return_value=["out.mp4"]),
            "submit_and_wait": mock.patch.object(self.generate, "submit_and_wait", return_value={"outputs": {}}),
            "report_video_output": mock.patch.object(
                self.generate, "report_video_output", return_value={"frames": 49}
            ),
        }
        with common_patches["configure_video_capability"], common_patches["video_canvas"], common_patches["upload_image"], \
                common_patches["run_i2v"], common_patches["download_outputs"], \
                common_patches["submit_and_wait"] as submit, common_patches["report_video_output"]:
            self.generate.main([
                "img2video", "--comfy-url", "http://server:8188",
                "--image", "still.png", "--prompt", "idle",
            ])
            self.generate.main([
                "img2video", "--comfy-url", "http://server:8188", "--timeout", "17",
                "--image", "still.png", "--prompt", "idle",
            ])
        self.assertEqual(
            [self.generate.DEFAULT_VIDEO_TIMEOUT, 17.0],
            [call.kwargs["timeout"] for call in submit.call_args_list],
        )

    def test_video_concat_is_local_and_does_not_resolve_comfy_url(self):
        with tempfile.TemporaryDirectory() as output_dir:
            with mock.patch.object(self.generate, "resolve_comfy_url", side_effect=AssertionError("must stay local")), \
                    mock.patch.object(self.generate, "concat_videos") as concat, \
                    mock.patch.object(self.generate, "report_video_output") as report:
                self.generate.main([
                    "video_concat", "--video", "a.mp4", "--video", "b.mp4",
                    "--output-dir", output_dir,
                ])
        concat.assert_called_once_with(
            ["a.mp4", "b.mp4"], os.path.join(output_dir, "video_concat.mp4"),
            allow_overwrite=False,
        )
        report.assert_called_once_with(
            os.path.join(output_dir, "video_concat.mp4"),
            task="video_concat", backend="local", elapsed_seconds=mock.ANY,
        )

    def test_video_concat_name_rejects_absolute_and_traversal_paths(self):
        with tempfile.TemporaryDirectory() as output_dir:
            for name in ("../escape", "/tmp/escape", r"C:\\escape"):
                with self.subTest(name=name), \
                        mock.patch.object(self.generate, "concat_videos") as concat:
                    with self.assertRaises(SystemExit):
                        self.generate.main([
                            "video_concat", "--video", "a.mp4", "--video", "b.mp4",
                            "--name", name, "--output-dir", output_dir,
                        ])
                    concat.assert_not_called()

    def test_h3_video_graph_has_basic_i2v_structure(self):
        graph, output_id = self.generate.build_img2video_h3(
            "slow idle motion", "still.png", width=512, height=512, seed=42, duration=2.0,
        )
        self.assertEqual("92", output_id)
        self.assertEqual("MiniMaxH3ImageToVideo", graph["104"]["class_type"])
        self.assertEqual(["56", 0], graph["104"]["inputs"]["first_frame"])
        self.assertEqual("SamplerCustomAdvanced", graph["14"]["class_type"])
        self.assertEqual(["10", 0], graph["91"]["inputs"]["images"])
        self.assertEqual(["91", 0], graph["92"]["inputs"]["video"])

    def test_download_outputs_downloads_videos_with_safe_paths(self):
        with tempfile.TemporaryDirectory() as output_dir:
            history = {"outputs": {"58": {"videos": [{
                "filename": "safe clip.mp4", "subfolder": "nested/renders", "type": "output",
            }]}}}
            response = mock.Mock()
            response.__enter__ = mock.Mock(return_value=response)
            response.__exit__ = mock.Mock(return_value=False)
            response.read.side_effect = [b"video-bytes", b""]
            with mock.patch.object(self.generate.urllib.request, "urlopen", return_value=response) as opener:
                paths = self.generate.download_outputs(
                    history, output_dir, comfy_url="http://server:8188", request_timeout=7,
                )
            self.assertEqual([os.path.join(output_dir, "safe clip.mp4")], paths)
            url = opener.call_args.args[0]
            self.assertIn("filename=safe+clip.mp4", url)
            self.assertIn("subfolder=nested%2Frenders", url)
            with open(paths[0], "rb") as downloaded:
                self.assertEqual(b"video-bytes", downloaded.read())

            unsafe = {"outputs": {"58": {"videos": [{"filename": "../escape.mp4"}]}}}
            with self.assertRaises(ValueError):
                self.generate.download_outputs(
                    unsafe, output_dir, comfy_url="http://server:8188",
                )

    def test_clip_extend_generated_still_is_unique_and_cleaned(self):
        with tempfile.TemporaryDirectory() as output_dir:
            with mock.patch.object(self.generate, "extract_last_frame") as extract, \
                    mock.patch.object(self.generate, "configure_video_capability", return_value="h3"), \
                    mock.patch.object(self.generate, "video_canvas", return_value=(64, 64)), \
                    mock.patch.object(self.generate, "upload_image", return_value="last.png") as upload, \
                    mock.patch.object(self.generate, "run_i2v", return_value=({}, "1")), \
                    mock.patch.object(self.generate, "submit_and_wait", return_value={"outputs": {}}), \
                    mock.patch.object(self.generate, "download_outputs", return_value=["out.mp4"]), \
                    mock.patch.object(self.generate, "report_video_output", return_value={"frames": 49}):
                self.generate.main([
                    "clip_extend", "--comfy-url", "http://server:8188", "--video", "previous.mp4",
                    "--prompt", "continue", "--output-dir", output_dir,
                ])
            generated_path = upload.call_args.args[0]
            self.assertNotEqual("_clip_extend_last.png", os.path.basename(generated_path))
            self.assertFalse(os.path.exists(generated_path))
            self.assertEqual([], os.listdir(output_dir))

    def test_pose_drive_rejects_non_24_fps_before_upload(self):
        container = SimpleNamespace(
            streams=SimpleNamespace(video=[SimpleNamespace(average_rate=Fraction(30, 1))]),
            close=mock.Mock(),
        )
        fake_av = SimpleNamespace(open=mock.Mock(return_value=container))
        with mock.patch.dict(sys.modules, {"av": fake_av}), \
                mock.patch.object(self.generate, "configure_video_capability", return_value="h3"), \
                mock.patch.object(self.generate, "upload_image") as upload:
            with self.assertRaisesRegex(SystemExit, "24 FPS"):
                self.generate.main([
                    "pose_drive", "--comfy-url", "http://server:8188", "--image", "char.png",
                    "--motion-ref", "motion.mp4", "--prompt", "perform motion",
                ])
        upload.assert_not_called()
        container.close.assert_called_once_with()

    def test_extract_video_frames_clears_only_old_numeric_png_frames(self):
        class FakeImage:
            def save(self, path):
                with open(path, "wb") as output:
                    output.write(b"new")

        class FakeFrame:
            def to_image(self):
                return FakeImage()

        container = SimpleNamespace(
            decode=lambda **kwargs: [FakeFrame(), FakeFrame()],
            close=mock.Mock(),
        )
        fake_av = SimpleNamespace(open=mock.Mock(return_value=container))
        with tempfile.TemporaryDirectory() as output_dir:
            frame_dir = os.path.join(output_dir, "clip_frames")
            os.makedirs(frame_dir)
            for filename in ("000.png", "001.png", "999.png", "keep.txt"):
                with open(os.path.join(frame_dir, filename), "wb") as output:
                    output.write(b"old")
            with mock.patch.dict(sys.modules, {"av": fake_av}):
                paths, returned_dir = self.generate.extract_video_frames(
                    os.path.join(output_dir, "clip.mp4"), output_dir,
                )
            self.assertEqual(frame_dir, returned_dir)
            self.assertEqual(2, len(paths))
            self.assertFalse(os.path.exists(os.path.join(frame_dir, "999.png")))
            self.assertTrue(os.path.exists(os.path.join(frame_dir, "keep.txt")))
            container.close.assert_called_once_with()

    def test_video_capability_requires_explicit_default_or_backend(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as config_file:
            json.dump({
                "schema_version": 1,
                "default_backend": None,
                "backends": {
                    "wan": {
                        "capabilities": ["i2v"],
                        "models": {},
                    },
                },
            }, config_file)
            config_path = config_file.name
        try:
            with mock.patch.object(self.generate, "validate_video_runtime"), \
                    mock.patch.object(self.generate, "validate_comfy_video_nodes"):
                with self.assertRaisesRegex(RuntimeError, "請明確給 --backend"):
                    self.generate.configure_video_capability(
                        "img2video", runtime_config_path=None,
                        video_config_path=config_path, comfy_url="http://server:8188",
                    )
        finally:
            os.unlink(config_path)

    def test_video_capability_selects_configured_backend_and_task_nodes(self):
        with tempfile.TemporaryDirectory() as model_dir:
            model_paths = {}
            for key, filename in self.generate.VIDEO_BACKEND_SPECS["wan"]["models"].items():
                path = os.path.join(model_dir, f"{key}.safetensors")
                with open(path, "wb") as model:
                    model.write(b"model")
                model_paths[key] = {"file": filename, "path": path}
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as config_file:
                json.dump({
                    "schema_version": 1,
                    "default_backend": "wan",
                    "runtime": {},
                    "backends": {
                        "wan": {
                            "available": True,
                            "capabilities": ["i2v", "control_video"],
                            "models": model_paths,
                        },
                    },
                }, config_file)
                config_path = config_file.name
            try:
                with mock.patch.object(self.generate, "validate_video_runtime"), \
                        mock.patch.object(self.generate, "validate_comfy_video_nodes") as nodes:
                    selected = self.generate.configure_video_capability(
                        "img2video", video_config_path=config_path,
                        comfy_url="http://server:8188",
                    )
                self.assertEqual("wan", selected)
                nodes.assert_called_once()
                required_nodes = nodes.call_args.args[1]
                self.assertIn("Wan22ImageToVideoLatent", required_nodes)
                self.assertNotIn("Wan22FunControlToVideo", required_nodes)
            finally:
                os.unlink(config_path)

    def test_video_capability_missing_model_stops_before_node_check(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as config_file:
            json.dump({
                "schema_version": 1,
                "default_backend": "wan",
                "backends": {
                    "wan": {
                        "capabilities": ["i2v"],
                        "models": {
                            "i2v_unet": {"file": "missing.safetensors", "path": "missing.safetensors"},
                        },
                    },
                },
            }, config_file)
            config_path = config_file.name
        try:
            with mock.patch.object(self.generate, "validate_video_runtime"), \
                    mock.patch.object(self.generate, "validate_comfy_video_nodes") as nodes:
                with self.assertRaisesRegex(RuntimeError, "upload/queue 前停止"):
                    self.generate.configure_video_capability(
                        "img2video", video_config_path=config_path,
                        comfy_url="http://server:8188",
                    )
            nodes.assert_not_called()
        finally:
            os.unlink(config_path)

    def test_main_video_capability_failure_happens_before_upload(self):
        with mock.patch.object(
                self.generate, "configure_video_capability",
                side_effect=RuntimeError("missing video runtime"),
        ), mock.patch.object(self.generate, "upload_image") as upload:
            with self.assertRaisesRegex(SystemExit, "missing video runtime"):
                self.generate.main([
                    "img2video", "--comfy-url", "http://server:8188",
                    "--image", "still.png", "--prompt", "idle",
                ])
        upload.assert_not_called()

    def test_video_outputs_refuse_existing_path_without_overwrite(self):
        with tempfile.TemporaryDirectory() as output_dir:
            existing = os.path.join(output_dir, "clip.mp4")
            with open(existing, "wb") as output:
                output.write(b"keep")
            history = {"outputs": {"1": {"videos": [{"filename": "clip.mp4"}]}}}
            with mock.patch.object(self.generate.urllib.request, "urlopen") as opener:
                with self.assertRaisesRegex(RuntimeError, "拒絕覆寫"):
                    self.generate.download_outputs(
                        history, output_dir, comfy_url="http://server:8188",
                        allow_overwrite=False,
                    )
            opener.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "拒絕覆寫"):
                self.generate.concat_videos(["a.mp4", "b.mp4"], existing)

    def test_transition_rejects_mismatched_aspect_before_upload(self):
        with mock.patch.object(self.generate, "_image_size", side_effect=[(512, 512), (768, 512)]):
            with self.assertRaisesRegex(ValueError, "比例"):
                self.generate.validate_transition_images("a.png", "b.png")

    def test_detector_reports_present_backends_without_choosing_h3(self):
        catalog = self.detector._load_generate_catalog()
        with tempfile.TemporaryDirectory() as comfyui_path:
            model_root = os.path.join(comfyui_path, "models")
            for backend, implementation in catalog.VIDEO_BACKEND_SPECS.items():
                for key, filename in implementation["models"].items():
                    directory = self.detector.MODEL_DIRECTORIES[backend][key]
                    path = os.path.join(model_root, directory, filename)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as model:
                        model.write(b"model")
            device_path = os.path.join(comfyui_path, "tools", "device_config.json")
            os.makedirs(os.path.dirname(device_path), exist_ok=True)
            with open(device_path, "w", encoding="utf-8") as device:
                json.dump({"backend": "cuda", "gpu_name": "Test GPU"}, device)
            classes = set()
            for implementation in catalog.VIDEO_BACKEND_SPECS.values():
                for nodes in implementation["required_nodes"].values():
                    classes.update(nodes)
            classes.add("OpenposePreprocessor")
            args = SimpleNamespace(
                comfyui_path=comfyui_path,
                python_exe=sys.executable,
                model_root=None,
                device_config=device_path,
                comfy_url="http://server:8188",
                http_timeout=1.0,
                default_backend=None,
                control_type="pose",
            )
            with mock.patch.object(self.detector, "_runtime_probe", return_value={
                "python": "3.13.9", "pillow": "12.2.0", "torch": "2.13.0+cu130",
                "pyav": "18.1.0", "torch_cuda": True, "gpu_name": "Test GPU",
            }), mock.patch.object(self.detector, "_query_object_info", return_value={
                "status": "available", "classes": sorted(classes), "error": None,
            }):
                config = self.detector.detect(args)
            self.assertIsNone(config["default_backend"])
            self.assertTrue(config["backends"]["h3"]["available"])
            self.assertTrue(config["backends"]["wan"]["available"])
            self.assertIn("i2v", config["backends"]["h3"]["capabilities"])

    def test_concat_rejects_mismatched_fps_before_creating_output(self):
        def fake_open(path, mode="r"):
            rate = Fraction(24, 1) if path == "a.mp4" else Fraction(30, 1)
            return SimpleNamespace(
                streams=SimpleNamespace(video=[SimpleNamespace(width=64, height=64, average_rate=rate)], audio=[]),
                close=mock.Mock(),
            )

        fake_av = SimpleNamespace(open=fake_open)
        with tempfile.TemporaryDirectory() as output_dir:
            dest = os.path.join(output_dir, "joined.mp4")
            with mock.patch.object(self.generate, "_require_pillow"), \
                    mock.patch.dict(sys.modules, {"av": fake_av}):
                with self.assertRaisesRegex(ValueError, "相同 FPS"):
                    self.generate.concat_videos(["a.mp4", "b.mp4"], dest)
            self.assertFalse(os.path.exists(dest))

    def test_concat_uses_atomic_destination_and_rejects_source_destination_alias(self):
        class FakeOutputStream:
            width = None
            height = None
            pix_fmt = None

            def encode(self, frame=None):
                return []

        class FakeOutput:
            def __init__(self, path):
                self.path = path
                self.closed = False

            def add_stream(self, *args, **kwargs):
                return FakeOutputStream()

            def mux(self, packet):
                pass

            def close(self):
                if not self.closed:
                    with open(self.path, "wb") as output:
                        output.write(b"joined")
                    self.closed = True

        class FakeInput:
            def __init__(self):
                self.streams = SimpleNamespace(
                    video=[SimpleNamespace(width=64, height=64, average_rate=Fraction(24, 1))],
                    audio=[],
                )

            def decode(self, **kwargs):
                return []

            def close(self):
                pass

        def fake_open(path, mode="r"):
            return FakeOutput(path) if mode == "w" else FakeInput()

        fake_av = SimpleNamespace(open=fake_open)
        fake_av.VideoFrame = SimpleNamespace(from_image=lambda image: image)
        with tempfile.TemporaryDirectory() as output_dir:
            source_a = os.path.join(output_dir, "a.mp4")
            source_b = os.path.join(output_dir, "b.mp4")
            dest = os.path.join(output_dir, "joined.mp4")
            for path in (source_a, source_b):
                with open(path, "wb") as source:
                    source.write(b"source")
            with mock.patch.object(self.generate, "_require_pillow"), \
                    mock.patch.dict(sys.modules, {"av": fake_av}):
                result = self.generate.concat_videos([source_a, source_b], dest)
            self.assertEqual(dest, result)
            with open(dest, "rb") as joined:
                self.assertEqual(b"joined", joined.read())
            self.assertEqual(
                [], [name for name in os.listdir(output_dir) if name.startswith(".joined.mp4.")]
            )

            with mock.patch.object(self.generate, "_require_pillow"), \
                    mock.patch.dict(sys.modules, {"av": fake_av}), \
                    mock.patch.object(fake_av, "open", side_effect=AssertionError("must reject first")):
                with self.assertRaisesRegex(ValueError, "輸入影片不可與輸出路徑相同"):
                    self.generate.concat_videos([source_a, source_b], source_a)

    def test_video_contract_fails_on_geometry_and_audio_mismatch(self):
        metadata = {
            "width": 128, "height": 64, "fps": 24.0, "frames": 49,
            "duration_seconds": 2.041667, "audio": False,
        }
        contract = self.generate.make_video_contract(
            "img2video", "h3", 64, 64, duration=2.0, audio_expected=True,
        )
        errors = self.generate._validate_video_contract(metadata, contract)
        self.assertTrue(any("width mismatch" in item for item in errors))
        self.assertTrue(any("audio mismatch" in item for item in errors))

    def test_sidecar_is_atomic_traceable_and_does_not_copy_runtime_secret(self):
        with tempfile.TemporaryDirectory() as work:
            source = os.path.join(work, "still.png")
            output = os.path.join(work, "shot_A01.mp4")
            with open(source, "wb") as handle:
                handle.write(b"source")
            with open(output, "wb") as handle:
                handle.write(b"video")
            config = {
                "schema_version": 1,
                "_source": os.path.join(work, "video_capabilities.json"),
                "comfyui_url": "http://user:super-secret-token@server:8188",
                "backends": {"h3": {"models": {
                    "i2v_unet": {"file": "h3.safetensors", "size_bytes": 123, "sha256": "abc"},
                }}},
            }
            contract = self.generate.make_video_contract("img2video", "h3", 64, 64, 2.0, True)
            actual = {"width": 64, "height": 64, "fps": 24.0, "frames": 56,
                      "duration_seconds": 2.333333, "audio": True,
                      "validation": {"status": "warning", "warnings": [{"kind": "continuity"}]}}
            path = self.generate.write_video_sidecar(
                output, "img2video", "h3", 42, "idle", "bad", [source], config,
                contract, actual, prompt_id="prompt-42", elapsed_seconds=1.25,
            )
            self.assertEqual(output + ".json", path)
            with open(path, encoding="utf-8") as handle:
                sidecar = json.load(handle)
            encoded = json.dumps(sidecar, ensure_ascii=False)
            self.assertNotIn("super-secret-token", encoded)
            self.assertEqual(42, sidecar["resolved_seed"])
            self.assertEqual("prompt-42", sidecar["prompt_id"])
            self.assertEqual(os.path.abspath(source), sidecar["inputs"][0]["path"])
            self.assertEqual(64, sidecar["requested_contract"]["width"])
            self.assertEqual("warning", sidecar["actual_pyav_metadata"]["validation"]["status"])

    def test_extract_video_frames_failure_keeps_previous_successful_set(self):
        class FakeImage:
            def save(self, path):
                with open(path, "wb") as output:
                    output.write(b"new")

        class FakeFrame:
            def to_image(self):
                return FakeImage()

        def decode(**kwargs):
            yield FakeFrame()
            raise RuntimeError("decode broke")

        old_container = SimpleNamespace(decode=decode, close=mock.Mock())
        fake_av = SimpleNamespace(open=mock.Mock(return_value=old_container))
        with tempfile.TemporaryDirectory() as output_dir:
            frame_dir = os.path.join(output_dir, "clip_frames")
            os.makedirs(frame_dir)
            old = os.path.join(frame_dir, "000.png")
            with open(old, "wb") as output:
                output.write(b"old-success")
            with mock.patch.dict(sys.modules, {"av": fake_av}):
                with self.assertRaisesRegex(RuntimeError, "decode broke"):
                    self.generate.extract_video_frames(os.path.join(output_dir, "clip.mp4"), output_dir)
            with open(old, "rb") as output:
                self.assertEqual(b"old-success", output.read())
            self.assertFalse(any(name.startswith(".clip_frames.") for name in os.listdir(output_dir)))

    def test_video_concat_default_rejects_mixed_audio_policy(self):
        class FakeInput:
            def __init__(self, has_audio):
                self.streams = SimpleNamespace(
                    video=[SimpleNamespace(width=64, height=64, average_rate=Fraction(24, 1))],
                    audio=[SimpleNamespace()] if has_audio else [],
                )
            def decode(self, **kwargs):
                return iter([object()])
            def close(self):
                pass

        fake_av = SimpleNamespace(open=lambda path, mode="r": FakeInput(path == "a.mp4"))
        with tempfile.TemporaryDirectory() as output_dir:
            dest = os.path.join(output_dir, "joined.mp4")
            with mock.patch.object(self.generate, "_require_pillow"), \
                    mock.patch.dict(sys.modules, {"av": fake_av}):
                with self.assertRaisesRegex(ValueError, "音訊不一致"):
                    self.generate.concat_videos(["a.mp4", "b.mp4"], dest)
            self.assertFalse(os.path.exists(dest))

    def test_input_preflight_rejects_empty_video_before_upload(self):
        container = SimpleNamespace(
            streams=SimpleNamespace(video=[SimpleNamespace(width=64, height=64, average_rate=Fraction(24, 1))], audio=[]),
            decode=lambda **kwargs: iter(()), close=mock.Mock(),
        )
        fake_av = SimpleNamespace(open=mock.Mock(return_value=container))
        with tempfile.NamedTemporaryFile(suffix=".mp4") as source, \
                mock.patch.dict(sys.modules, {"av": fake_av}):
            with self.assertRaisesRegex(ValueError, "沒有影格"):
                self.generate.validate_video_input(source.name, label="motion-ref")

    def test_model_size_preflight_rejects_stale_capability_config(self):
        with tempfile.TemporaryDirectory() as model_dir:
            path = os.path.join(model_dir, "model.safetensors")
            with open(path, "wb") as model:
                model.write(b"actual")
            config = {"backends": {"wan": {"available": True, "models": {
                "i2v_unet": {"file": "model.safetensors", "path": path, "size_bytes": 999},
            }}}}
            with self.assertRaisesRegex(RuntimeError, "size_bytes"):
                self.generate._validate_video_models(config, "wan", ["i2v"])

    def test_resume_requires_exact_sidecar_signature_and_revalidates_output(self):
        with tempfile.TemporaryDirectory() as work:
            source = os.path.join(work, "still.png")
            output = os.path.join(work, "shot_A01.mp4")
            for path, data in ((source, b"source"), (output, b"video")):
                with open(path, "wb") as handle:
                    handle.write(data)
            contract = self.generate.make_video_contract("img2video", "wan", 64, 64, 2.0, False)
            config = {"backends": {"wan": {"models": {}}}}
            actual = {"width": 64, "height": 64, "fps": 24.0, "frames": 49,
                      "duration_seconds": 2.041667, "audio": False,
                      "validation": {"status": "pass", "warnings": []}}
            self.generate.write_video_sidecar(output, "img2video", "wan", 7, "idle", "", [source],
                                              config, contract, actual)
            with mock.patch.object(self.generate, "report_video_output", return_value=actual) as report:
                result = self.generate.resume_video_output(
                    output, "img2video", "wan", 7, [source], config, contract,
                )
            self.assertIs(actual, result)
            report.assert_called_once()
            with self.assertRaisesRegex(RuntimeError, "不完全相符"):
                self.generate.resume_video_output(output, "img2video", "wan", 8, [source], config, contract)

    def test_continuity_metric_is_warning_only(self):
        with tempfile.TemporaryDirectory() as work:
            source = os.path.join(work, "source.png")
            self.generate.PILImage.new("RGB", (64, 64), (0, 0, 0)).save(source)
            black = self.generate.PILImage.new("RGB", (64, 64), (0, 0, 0))
            white = self.generate.PILImage.new("RGB", (64, 64), (255, 255, 255))
            with mock.patch.object(self.generate, "_first_last_video_images", return_value=(black, white)):
                warnings = self.generate._continuity_warnings("unused.mp4", "fx_loop")
            self.assertEqual("continuity", warnings[0]["kind"])
            self.assertEqual("seam", warnings[0]["label"])
            self.assertIn("warning", warnings[0]["message"])


if __name__ == "__main__":
    unittest.main()
