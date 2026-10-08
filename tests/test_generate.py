import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from fractions import Fraction
from types import SimpleNamespace
from unittest import mock


TOOLS_SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools_src")
if TOOLS_SRC not in sys.path:
    sys.path.insert(0, TOOLS_SRC)

from comfyui_pipeline import (  # noqa: E402
    cli, client, image_capabilities, image_graphs, image_runtime, profiles, tasks,
    video_catalog, video_config, video_contract, video_graphs, video_media,
)
from comfyui_pipeline.context import RunContext  # noqa: E402
from comfyui_pipeline.tasks import video as task_video, video_local as task_video_local  # noqa: E402
from comfyui_pipeline.video_config import configure_video_capability  # noqa: E402

MODULE_PATH = os.path.join(TOOLS_SRC, "generate.py")
DETECTOR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tools_src", "detect_video_capabilities.py"
)
PYAV_AVAILABLE = importlib.util.find_spec("av") is not None


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


@contextlib.contextmanager
def patch_all(name, modules, **kwargs):
    """同一個 mock 同時替換多個模組裡的同名參照(各模組各自 import 了這個名稱,呼叫端不只一處)。"""
    shared = mock.MagicMock(**kwargs)
    with contextlib.ExitStack() as stack:
        for module in modules:
            stack.enter_context(mock.patch.object(module, name, shared))
        yield shared


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
        self.ctx = RunContext(device={
            "tier": "sdxl",
            "checkpoint": "test.safetensors",
            "default_width": 1024,
            "default_height": 1024,
        })

    def main(self, argv):
        """以這個測試的 RunContext 跑 CLI(取代原本對 generate 全域的改值)。"""
        return cli.run(argv, context=self.ctx)

    def test_url_resolution_prioritises_cli_then_environment_then_explicit_config(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as config_file:
            json.dump({"comfyui_url": "http://config:8188/"}, config_file)
            config_path = config_file.name
        try:
            with mock.patch.dict(os.environ, {"COMFY_URL": "http://env:8188/"}, clear=True):
                self.assertEqual("http://cli:8188", cli.resolve_comfy_url("http://cli:8188/", config_path))
                self.assertEqual("http://env:8188", cli.resolve_comfy_url(config_path=config_path))
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual("http://config:8188", cli.resolve_comfy_url(config_path=config_path))
                with self.assertRaises(RuntimeError):
                    cli.resolve_comfy_url()
        finally:
            os.unlink(config_path)

    def test_parser_accepts_runtime_options_before_or_after_task(self):
        with mock.patch.object(image_runtime, "build_concept", return_value=({}, "1")), \
                mock.patch.object(tasks, "preflight_image_task", return_value=True), \
                mock.patch.object(cli, "submit_and_wait", return_value={"outputs": {}}), \
                mock.patch.object(cli, "download_outputs", return_value=[]) as download:
            self.main(["--comfy-url", "http://before:8188", "--timeout", "12", "concept", "--prompt", "x"])
            self.main(["concept", "--comfy-url", "http://after:8188", "--timeout", "13", "--prompt", "x"])
        self.assertEqual("http://before:8188", download.call_args_list[0].kwargs["comfy_url"])
        self.assertEqual(12.0, download.call_args_list[0].kwargs["request_timeout"])
        self.assertEqual("http://after:8188", download.call_args_list[1].kwargs["comfy_url"])
        self.assertEqual(13.0, download.call_args_list[1].kwargs["request_timeout"])

    def test_result_json_rejects_video_before_runtime_or_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = os.path.join(directory, "result.json")
            with mock.patch.object(cli, "upload_image") as upload, \
                    mock.patch.object(cli, "submit_and_wait") as submit:
                with self.assertRaisesRegex(SystemExit, "只支援圖片 task"):
                    self.main([
                        "--result-json", destination, "img2video",
                        "--image", "still.png", "--prompt", "motion",
                    ])
            upload.assert_not_called()
            submit.assert_not_called()

    def test_result_json_writes_manifest_from_the_submitted_graph(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            image_path = os.path.join(directory, "generated.png")
            manifest_path = os.path.join(directory, "result.json")
            Image.new("RGB", (64, 64), (20, 30, 40)).save(image_path)
            graph = {
                "4": {"class_type": "KSampler", "inputs": {"seed": 123456}},
                "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
                "2": {"class_type": "EmptyLatentImage", "inputs": {"width": 64, "height": 64}},
            }
            with mock.patch.object(cli, "resolve_image_profile", return_value="sdxl_standard"), \
                    mock.patch.object(tasks, "preflight_image_task", return_value=True), \
                    mock.patch.object(tasks, "build_image_task_graph", return_value=(graph, "9")), \
                    mock.patch.object(cli, "submit_and_wait", return_value={"_prompt_id": "prompt-1", "outputs": {}}), \
                    mock.patch.object(cli, "download_outputs", return_value=[image_path]):
                self.main([
                    "--comfy-url", "http://localhost:8188", "--result-json", manifest_path,
                    "concept", "--prompt", "test request", "--seed", "5",
                ])
            with open(manifest_path, encoding="utf-8") as stream:
                manifest = json.load(stream)
            self.assertEqual("prompt-1", manifest["prompt_id"])
            self.assertEqual({"4": {"seed": 123456}}, manifest["resolved_seeds"])
            self.assertEqual("pass", manifest["technical_validation"]["status"])
            self.assertEqual("pending", manifest["content_review"])
            self.assertEqual((64, 64), (manifest["outputs"][0]["width"], manifest["outputs"][0]["height"]))

    def test_boundary_validators_reject_invalid_values(self):
        with self.assertRaises(ValueError):
            image_graphs.validate_batch(0)
        with self.assertRaises(ValueError):
            image_graphs.validate_dimensions(1024, 1025)
        for value in (-0.01, 1.01, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    image_graphs.validate_unit_interval(value, "weight")
        for value in (0, -1, 4.01, float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    image_graphs.validate_scale(value)
        with self.assertRaises(ValueError):
            image_runtime.build_upscale(self.ctx, "x", "image.png", scale=4.1)
        with self.assertRaises(ValueError):
            image_runtime.build_inpaint(self.ctx, "x", "image.png", "mask.png", denoise=-0.1)

    def test_generate_entry_reexports_names_used_by_other_tools(self):
        # face_swap / video_layers 以 generate.<名稱> 讀取這些(唯讀)。
        for name in ("main", "resolve_comfy_url", "validate_timeout", "submit_and_wait", "download_outputs",
                     "upload_image", "_fetch_comfy_object_info", "check_image_graph_against_object_info"):
            self.assertTrue(callable(getattr(self.generate, name)), name)
        self.assertIs(client.submit_and_wait, self.generate.submit_and_wait)

    def test_pipeline_modules_expose_moved_symbols(self):
        self.assertTrue(callable(image_runtime.build_concept))
        self.assertTrue(callable(image_runtime.build_flux2_concept))
        self.assertTrue(callable(image_runtime.build_flux2_edit))
        self.assertTrue(callable(image_graphs.build_control_preprocessor))
        self.assertTrue(callable(image_runtime.build_layer_split))
        self.assertEqual("blurry, low quality, extra fingers, deformed, watermark", image_graphs.DEFAULT_NEGATIVE)
        self.assertIn("wan", video_catalog.VIDEO_BACKEND_SPECS)
        self.assertIn("static", video_catalog.CAMERA_MOVES)

    def test_flux2_concept_is_locked_to_official_distilled_contract(self):
        graph, output_id = image_runtime.build_flux2_concept(self.ctx,
            "a game prop with a readable sign", width=1024, height=1024, seed=42,
        )
        self.assertEqual("12", output_id)
        self.assertEqual("flux-2-klein-4b-fp8.safetensors", graph["1"]["inputs"]["unet_name"])
        self.assertEqual("flux2", graph["2"]["inputs"]["type"])
        self.assertEqual(4, graph["10"]["inputs"]["steps"])
        self.assertEqual(1.0, graph["8"]["inputs"]["cfg"])
        self.assertEqual("euler", graph["9"]["inputs"]["sampler_name"])
        self.assertEqual(42, graph["7"]["inputs"]["noise_seed"])

    def test_flux2_concept_rejects_non_aligned_dimensions_before_submit(self):
        with self.assertRaisesRegex(ValueError, "16"):
            image_runtime.build_flux2_concept(self.ctx, "x", width=1000, height=1024)

    def test_flux2_edit_matches_official_one_reference_contract(self):
        graph, output_id = image_runtime.build_flux2_edit(self.ctx, "make it silver", "uploaded.png", seed=7)
        self.assertEqual("18", output_id)
        self.assertEqual("flux-2-klein-base-4b-fp8.safetensors", graph["1"]["inputs"]["unet_name"])
        self.assertEqual(["9", 0], graph["10"]["inputs"]["latent"])
        self.assertEqual(["9", 0], graph["11"]["inputs"]["latent"])
        self.assertEqual(["6", 0], graph["12"]["inputs"]["width"])
        self.assertEqual(["6", 1], graph["12"]["inputs"]["height"])
        self.assertEqual(20, graph["16"]["inputs"]["steps"])
        self.assertEqual(5.0, graph["14"]["inputs"]["cfg"])

    def test_flux2_cli_does_not_expose_sdxl_style_or_lora(self):
        with self.assertRaises(SystemExit):
            self.main([
                "flux2_concept", "--comfy-url", "http://server:8188",
                "--prompt", "x", "--style", "realistic",
            ])

    def test_flux2_preflight_rejects_missing_model_before_upload(self):
        node_names = set(image_capabilities.FLUX2_REQUIRED_NODES) | set(
            image_capabilities.FLUX2_EDIT_REQUIRED_NODES
        )
        payload = {name: {"input": {"required": {}}} for name in node_names}
        payload["UNETLoader"]["input"]["required"]["unet_name"] = [[
            "flux-2-klein-base-4b-fp8.safetensors"
        ]]
        payload["CLIPLoader"]["input"]["required"]["clip_name"] = [[
            "qwen_3_4b.safetensors"
        ]]
        payload["VAELoader"]["input"]["required"]["vae_name"] = [[
            "some-other-vae.safetensors"
        ]]
        with patch_all("_fetch_comfy_object_info", (tasks, image_capabilities, video_config,), return_value=payload), \
                mock.patch.object(cli, "upload_image") as upload:
            with self.assertRaisesRegex(SystemExit, "flux2-vae"):
                self.main([
                    "flux2_edit", "--comfy-url", "http://server:8188",
                    "--prompt", "make it silver", "--image", "source.png",
                ])
        upload.assert_not_called()

    def test_sd15_controlnet_and_ipadapter_features_fail_fast(self):
        self.ctx.device["tier"] = "sd15"
        with self.assertRaisesRegex(RuntimeError, "sd15"):
            image_runtime.build_pose_only(self.ctx, "x", "pose.png")
        with self.assertRaisesRegex(RuntimeError, "sd15"):
            image_runtime.build_style_lock(self.ctx, "x", "character.png")
        with self.assertRaisesRegex(RuntimeError, "sd15"):
            image_runtime.build_icon_asset(self.ctx, "x", structure_ref_filename="ref.png")
        # A plain icon does not use either SDXL-only add-on and remains available.
        graph, _ = image_runtime.build_icon_asset(self.ctx, "x")
        self.assertEqual("CheckpointLoaderSimple", graph["1"]["class_type"])

    def test_pose_only_verified_controlnet_remains_default(self):
        graph, _ = image_runtime.build_pose_only(self.ctx,
            "x", "pose.png", control_type="depth", seed=7,
        )
        self.assertEqual("ControlNetLoader", graph["6"]["class_type"])
        self.assertEqual(
            image_graphs.CONTROLNET_MODELS["depth"],
            graph["6"]["inputs"]["control_net_name"],
        )
        self.assertNotIn("6u", graph)
        self.assertEqual(["6", 0], graph["7"]["inputs"]["control_net"])

    def test_pose_only_union_inserts_explicit_control_type_node(self):
        expected = {
            "canny": "canny/lineart/anime_lineart/mlsd",
            "pose": "openpose",
            "depth": "depth",
        }
        for control_type, union_type in expected.items():
            with self.subTest(control_type=control_type):
                graph, _ = image_runtime.build_pose_only(self.ctx,
                    "x", "pose.png", control_type=control_type,
                    control_backend="union", seed=7,
                )
                self.assertEqual(
                    "xinsir-controlnet-union-sdxl-1.0-promax.safetensors",
                    graph["6"]["inputs"]["control_net_name"],
                )
                self.assertEqual("SetUnionControlNetType", graph["6u"]["class_type"])
                self.assertEqual(union_type, graph["6u"]["inputs"]["type"])
                self.assertEqual(["6u", 0], graph["7"]["inputs"]["control_net"])

    def test_union_preflight_rejects_missing_model_before_upload(self):
        payload = {
            "ControlNetLoader": {"input": {"required": {
                "control_net_name": [["controlnet-canny-sdxl-1.0.safetensors"]],
            }}},
            "SetUnionControlNetType": {"input": {"required": {}}},
        }
        with patch_all("_fetch_comfy_object_info", (tasks, image_capabilities, video_config,), return_value=payload), \
                mock.patch.object(cli, "upload_image") as upload:
            with self.assertRaisesRegex(SystemExit, "xinsir-controlnet-union"):
                self.main([
                    "pose_only", "--comfy-url", "http://server:8188",
                    "--prompt", "x", "--pose-ref", "pose.png",
                    "--control-backend", "union",
                ])
        upload.assert_not_called()

    def test_submit_and_wait_uses_same_injected_url_and_keeps_prompt_id_on_retry(self):
        opener = mock.Mock(side_effect=[
            Response('{"prompt_id":"prompt-1"}'),
            urllib.error.URLError("temporary"),
            Response('{"prompt-1":{"status":{"completed":true}}}'),
        ])
        with mock.patch.object(urllib.request, "urlopen", opener), \
                mock.patch.object(time, "sleep"):
            result = cli.submit_and_wait(
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
        with mock.patch.object(urllib.request, "urlopen", opener), \
                mock.patch.object(time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "prompt-retry"):
                cli.submit_and_wait(
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
        with mock.patch.object(urllib.request, "urlopen", opener), \
                mock.patch.object(time, "monotonic", clock), \
                mock.patch.object(time, "sleep"):
            with self.assertRaisesRegex(TimeoutError, "prompt-timeout"):
                cli.submit_and_wait(
                    {"1": {}}, timeout=0.5, comfy_url="http://server:8188", poll_interval=0,
                )

    def test_timeout_only_attempts_exact_pending_queue_deletion(self):
        opener = mock.Mock(return_value=Response("{}"))
        with mock.patch.object(urllib.request, "urlopen", opener):
            status = client._cancel_exact_pending_prompt(
                "prompt-exact", "http://server:8188", 3,
                {"status": "pending"},
            )
        self.assertTrue(status["cancel_attempted"])
        request = opener.call_args.args[0]
        self.assertEqual("http://server:8188/queue", request.full_url)
        self.assertNotIn("interrupt", request.full_url)
        self.assertEqual({"delete": ["prompt-exact"]}, json.loads(request.data.decode()))

    def test_submit_rejects_malformed_queue_and_history_shapes(self):
        with mock.patch.object(urllib.request, "urlopen", return_value=Response("[]")):
            with self.assertRaisesRegex(RuntimeError, "JSON object"):
                cli.submit_and_wait({}, comfy_url="http://server:8188")

        for history in ('{"p":null}', '{"p":{"status":null}}'):
            with self.subTest(history=history), \
                    mock.patch.object(urllib.request, "urlopen", side_effect=[
                        Response('{"prompt_id":"p"}'), Response(history),
                    ]):
                with self.assertRaisesRegex(RuntimeError, "prompt_id=p"):
                    cli.submit_and_wait({}, comfy_url="http://server:8188")

    def test_download_outputs_encodes_all_query_values_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as output_dir:
            history = {"outputs": {"7": {"images": [{
                "filename": "safe.png", "subfolder": "nested/ref", "type": "temp&preview",
            }]}}}
            response = mock.Mock()
            response.__enter__ = mock.Mock(return_value=response)
            response.__exit__ = mock.Mock(return_value=False)
            response.read.side_effect = [b"image-bytes", b""]
            with mock.patch.object(urllib.request, "urlopen", return_value=response) as opener:
                paths = cli.download_outputs(
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
            with mock.patch.object(urllib.request, "urlopen", return_value=partial_response):
                with self.assertRaises(TimeoutError):
                    cli.download_outputs(incomplete, output_dir, comfy_url="http://server:8188")
            self.assertFalse(os.path.exists(os.path.join(output_dir, "incomplete.png")))
            self.assertFalse(any(name.endswith(".part") for name in os.listdir(output_dir)))

            unsafe = {"outputs": {"7": {"images": [{"filename": "../escape.png"}]}}}
            with self.assertRaises(ValueError):
                cli.download_outputs(unsafe, output_dir, comfy_url="http://server:8188")
            with self.assertRaises(RuntimeError):
                cli.download_outputs({"outputs": {}}, output_dir, comfy_url="http://server:8188")

    def test_main_downloads_only_transparent_saveimage_after_background_removal(self):
        # concept --remove-bg 選 -transparent template，graph 裡已經有一顆去背 SaveImage。
        # 下載節點就是那一顆；不能再接一次 attach，否則會多一顆 RemoveBackground。
        captured = {}

        def fake_submit(prompt, **_kwargs):
            captured["graph"] = prompt
            return {"outputs": {}}

        with mock.patch.object(tasks, "preflight_image_task", return_value=True), \
                mock.patch.object(cli, "submit_and_wait", side_effect=fake_submit), \
                mock.patch.object(cli, "download_outputs", return_value=["out.png"]) as download:
            self.main(["--comfy-url", "http://server:8188", "concept", "--prompt", "x",
                       "--remove-bg", "--seed", "1"])
        graph = captured["graph"]
        transparent = [
            node_id for node_id, node in graph.items()
            if node.get("class_type") == "SaveImage"
            and (node.get("inputs") or {}).get("filename_prefix") == "transparent"
        ]
        removals = [node for node in graph.values() if node.get("class_type") == "RemoveBackground"]
        self.assertEqual(1, len(transparent))
        self.assertEqual(1, len(removals))
        self.assertEqual(transparent, download.call_args.kwargs["node_ids"])

    def _object_info_for(self, graph, drop_nodes=(), drop_models=()):
        """依 graph 產生剛好足夠的 /object_info;可指定要拿掉的 node 或模型檔。"""
        payload = {}
        for node in graph.values():
            class_type = node["class_type"]
            if class_type in drop_nodes:
                continue
            entry = payload.setdefault(class_type, {"input": {"required": {}}})
            field = image_capabilities.IMAGE_MODEL_INPUTS.get(class_type)
            if field:
                options = entry["input"]["required"].setdefault(field, [[]])[0]
                value = node["inputs"][field]
                if value not in drop_models and value not in options:
                    options.append(value)
        return payload

    def _full_graph(self, task_args, remove_bg=False):
        graph, out_id = tasks.build_image_task_graph(
            self.ctx, task_args, None, lambda _p: image_capabilities.PREFLIGHT_IMAGE_PLACEHOLDER,
        )
        if remove_bg:
            image_graphs.attach_bg_removal(graph, out_id)
        return graph

    def test_image_preflight_rejects_missing_custom_node_before_upload(self):
        argv = ["pose_only", "--prompt", "x", "--pose-ref", "pose.png", "--control-type", "pose"]
        args = SimpleNamespace(task="pose_only", prompt="x", negative=None, width=None, height=None, seed=1,
                               pose_ref="pose.png", pose_strength=1.0, batch=1, control_type="pose",
                               lora=None, lora_strength=0.8, control_backend="verified")
        payload = self._object_info_for(self._full_graph(args), drop_nodes=("OpenposePreprocessor",))
        with patch_all("_fetch_comfy_object_info", (tasks, image_capabilities, video_config,), return_value=payload), \
                mock.patch.object(cli, "upload_image") as upload, \
                mock.patch.object(cli, "submit_and_wait") as submit:
            with self.assertRaisesRegex(SystemExit, "OpenposePreprocessor"):
                self.main(["--comfy-url", "http://server:8188"] + argv)
        upload.assert_not_called()
        submit.assert_not_called()

    def test_image_preflight_rejects_missing_model_file_before_upload(self):
        argv = ["style_lock", "--prompt", "x", "--character-ref", "char.png"]
        args = SimpleNamespace(task="style_lock", prompt="x", negative=None, width=None, height=None, seed=1,
                               character_ref="char.png", ip_weight=0.8, batch=1, lora=None, lora_strength=0.8)
        payload = self._object_info_for(
            self._full_graph(args), drop_models=(image_graphs.IPADAPTER_MODEL,),
        )
        with patch_all("_fetch_comfy_object_info", (tasks, image_capabilities, video_config,), return_value=payload), \
                mock.patch.object(cli, "upload_image") as upload:
            with self.assertRaisesRegex(SystemExit, "ip-adapter-plus_sdxl_vit-h"):
                self.main(["--comfy-url", "http://server:8188"] + argv)
        upload.assert_not_called()

    def test_image_preflight_checks_background_removal_model(self):
        argv = ["concept", "--prompt", "x", "--remove-bg"]
        args = SimpleNamespace(task="concept", prompt="x", negative=None, width=None, height=None, seed=1,
                               batch=1, lora=None, lora_strength=0.8, remove_bg=True)
        payload = self._object_info_for(
            self._full_graph(args, remove_bg=True), drop_models=(image_graphs.BG_REMOVAL_MODEL,),
        )
        with patch_all("_fetch_comfy_object_info", (tasks, image_capabilities, video_config,), return_value=payload), \
                mock.patch.object(cli, "submit_and_wait") as submit:
            with self.assertRaisesRegex(SystemExit, "birefnet"):
                self.main(["--comfy-url", "http://server:8188"] + argv)
        submit.assert_not_called()

    def test_image_preflight_passes_then_uploads_and_submits(self):
        argv = ["style_lock", "--prompt", "x", "--character-ref", "char.png"]
        args = SimpleNamespace(task="style_lock", prompt="x", negative=None, width=None, height=None, seed=1,
                               character_ref="char.png", ip_weight=0.8, batch=1, lora=None, lora_strength=0.8)
        payload = self._object_info_for(self._full_graph(args))
        with patch_all("_fetch_comfy_object_info", (tasks, image_capabilities, video_config,), return_value=payload), \
                mock.patch.object(cli, "upload_image", return_value="char.png") as upload, \
                mock.patch.object(cli, "submit_and_wait", return_value={"outputs": {}}) as submit, \
                mock.patch.object(cli, "download_outputs", return_value=["out.png"]):
            self.main(["--comfy-url", "http://server:8188"] + argv)
        upload.assert_called_once()
        submit.assert_called_once()

    def test_object_info_options_accepts_legacy_and_combo_schema(self):
        legacy = {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["a.safetensors"], {}]}}}}
        combo = {"CheckpointLoaderSimple": {"input": {"required": {
            "ckpt_name": ["COMBO", {"options": ["b.safetensors"]}]}}}}
        self.assertEqual(["a.safetensors"], image_capabilities._object_info_options(legacy, "CheckpointLoaderSimple", "ckpt_name"))
        self.assertEqual(["b.safetensors"], image_capabilities._object_info_options(combo, "CheckpointLoaderSimple", "ckpt_name"))
        self.assertIsNone(image_capabilities._object_info_options({}, "CheckpointLoaderSimple", "ckpt_name"))

    PLATFORM_FIELDS = {
        "backend": "cuda", "platform_key": "windows-cuda", "gpu_name": "RTX 4080",
        "usable_memory_mb": 16376, "precision_support": ["fp32", "fp16", "bf16", "fp8"],
    }

    def _run_concept_capturing_graph(self, argv):
        captured = {}

        def fake_submit(prompt, **_kwargs):
            captured["graph"] = json.loads(json.dumps(prompt))
            return {"outputs": {}}
        with mock.patch.object(tasks, "preflight_image_task", return_value=True), \
                mock.patch.object(cli, "submit_and_wait", side_effect=fake_submit), \
                mock.patch.object(cli, "download_outputs", return_value=[]):
            self.main(["--comfy-url", "http://server:8188"] + argv)
        return captured["graph"]

    def test_profile_flag_selects_smaller_profile_checkpoint_and_resolution(self):
        self.ctx.device.update(self.PLATFORM_FIELDS)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            graph = self._run_concept_capturing_graph(["concept", "--prompt", "x", "--profile", "sd15_light"])
        self.assertEqual("dreamshaper_8.safetensors", graph["1"]["inputs"]["ckpt_name"])
        self.assertEqual((512, 512), (graph["4"]["inputs"]["width"], graph["4"]["inputs"]["height"]))
        self.assertIn("unverified", stderr.getvalue())

    def test_without_profile_keeps_tier_behaviour(self):
        graph = self._run_concept_capturing_graph(["concept", "--prompt", "x"])
        self.assertEqual("test.safetensors", graph["1"]["inputs"]["ckpt_name"])
        self.assertEqual((1024, 1024), (graph["4"]["inputs"]["width"], graph["4"]["inputs"]["height"]))

    def test_explicit_dimensions_still_override_profile_default(self):
        self.ctx.device.update(self.PLATFORM_FIELDS)
        with contextlib.redirect_stderr(io.StringIO()):
            graph = self._run_concept_capturing_graph(
                ["concept", "--prompt", "x", "--profile", "sd15_light", "--width", "640", "--height", "768"])
        self.assertEqual((640, 768), (graph["4"]["inputs"]["width"], graph["4"]["inputs"]["height"]))

    def test_invalid_explicit_dimension_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.main(["--comfy-url", "http://server:8188", "concept", "--prompt", "x", "--height", "1001"])

    def test_profile_rejections_happen_before_upload(self):
        cases = [
            (dict(self.PLATFORM_FIELDS, usable_memory_mb=4096),
             ["style_lock", "--prompt", "x", "--character-ref", "c.png", "--profile", "sdxl_standard"], "不適用這台機器"),
            (self.PLATFORM_FIELDS,
             ["style_lock", "--prompt", "x", "--character-ref", "c.png", "--profile", "sd15_light"], "不提供 style_lock"),
            (self.PLATFORM_FIELDS,
             ["concept", "--prompt", "x", "--profile", "sd15_light", "--style", "anime"], "風格清單"),
            ({}, ["concept", "--prompt", "x", "--profile", "sd15_light"], "detect_device.py"),
            (self.PLATFORM_FIELDS, ["concept", "--prompt", "x", "--profile", "nope"], "找不到模型設定檔"),
        ]
        for device_fields, argv, message in cases:
            with self.subTest(argv=argv):
                self.setUp()
                self.ctx.device.update(device_fields)
                with mock.patch.object(cli, "upload_image") as upload, \
                        patch_all("_fetch_comfy_object_info", (tasks, image_capabilities, video_config,)) as fetch:
                    with self.assertRaisesRegex(SystemExit, message):
                        self.main(["--comfy-url", "http://server:8188"] + argv)
                upload.assert_not_called()
                fetch.assert_not_called()

    def test_image_capabilities_default_profile_is_used_and_fingerprint_checked(self):
        self.ctx.device.update(self.PLATFORM_FIELDS)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "image_capabilities.json")
            config = {"default_profile": "sd15_light",
                      "device_fingerprint": profiles.device_fingerprint(self.ctx.device)}
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(config, handle)
            with contextlib.redirect_stderr(io.StringIO()):
                graph = self._run_concept_capturing_graph(["concept", "--prompt", "x", "--image-config", path])
            self.assertEqual("dreamshaper_8.safetensors", graph["1"]["inputs"]["ckpt_name"])

            self.ctx.device["usable_memory_mb"] = 8192
            with mock.patch.object(cli, "upload_image") as upload:
                with self.assertRaisesRegex(SystemExit, "detect_image_capabilities.py"):
                    self.main(["--comfy-url", "http://server:8188", "concept", "--prompt", "x",
                                        "--image-config", path])
            upload.assert_not_called()

    def test_runtime_image_config_not_yet_generated_falls_back_to_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = os.path.join(tmp, "local_config.json")
            with open(runtime, "w", encoding="utf-8") as handle:
                json.dump({"image_config": "image_capabilities.json"}, handle)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual((None, None), image_capabilities.load_image_capabilities(runtime))
            self.assertIn("detect_image_capabilities.py", stderr.getvalue())
            # An explicit --image-config is a user request, so a missing file still fails.
            with self.assertRaisesRegex(RuntimeError, "找不到"):
                image_capabilities.load_image_capabilities(runtime, os.path.join(tmp, "missing.json"))

    def test_profile_flag_is_rejected_for_non_profile_tasks(self):
        with self.assertRaisesRegex(SystemExit, "--profile"):
            self.main(["--comfy-url", "http://server:8188", "flux2_concept", "--prompt", "x",
                                "--profile", "sdxl_standard"])

    def test_flux2_tasks_do_not_use_profile_preflight(self):
        self.assertNotIn("flux2_concept", image_capabilities.IMAGE_PROFILE_TASKS)
        self.assertNotIn("flux2_edit", image_capabilities.IMAGE_PROFILE_TASKS)
        self.assertIn("layer_split", image_capabilities.IMAGE_PROFILE_TASKS)

    def test_video_backend_unsupported_combination_fails_fast_without_argv_fallback(self):
        with mock.patch.object(sys, "argv", ["test_generate.py"]):
            with self.assertRaisesRegex(SystemExit, "character_video"):
                video_config.require_video_backend("character_video", "wan")

    def test_video_timeout_defaults_and_cli_override(self):
        common_patches = {
            "configure_video_capability": mock.patch.object(
                cli, "configure_video_capability", return_value="h3"
            ),
            "video_canvas": mock.patch.object(task_video, "video_canvas", return_value=(64, 64)),
            "upload_image": mock.patch.object(cli, "upload_image", return_value="still.png"),
            "download_outputs": mock.patch.object(cli, "download_outputs", return_value=["out.mp4"]),
            "submit_and_wait": mock.patch.object(cli, "submit_and_wait", return_value={"outputs": {}}),
            "report_video_output": patch_all(
                "report_video_output", (cli, task_video_local, video_contract), return_value={"frames": 49}
            ),
            "write_video_sidecar": patch_all("write_video_sidecar", (cli, task_video_local,)),
        }
        with common_patches["configure_video_capability"], common_patches["video_canvas"], common_patches["upload_image"], \
                common_patches["download_outputs"], \
                common_patches["submit_and_wait"] as submit, common_patches["report_video_output"], \
                common_patches["write_video_sidecar"]:
            self.main([
                "img2video", "--comfy-url", "http://server:8188",
                "--image", "still.png", "--prompt", "idle",
            ])
            self.main([
                "img2video", "--comfy-url", "http://server:8188", "--timeout", "17",
                "--image", "still.png", "--prompt", "idle",
            ])
        self.assertEqual(
            [video_catalog.DEFAULT_VIDEO_TIMEOUT, 17.0],
            [call.kwargs["timeout"] for call in submit.call_args_list],
        )

    def test_video_concat_is_local_and_does_not_resolve_comfy_url(self):
        with tempfile.TemporaryDirectory() as output_dir:
            with mock.patch.object(cli, "resolve_comfy_url", side_effect=AssertionError("must stay local")), \
                    mock.patch.object(task_video_local, "concat_videos") as concat, \
                    patch_all("report_video_output", (cli, task_video_local, video_contract,)) as report:
                self.main([
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
                        mock.patch.object(task_video_local, "concat_videos") as concat:
                    with self.assertRaises(SystemExit):
                        self.main([
                            "video_concat", "--video", "a.mp4", "--video", "b.mp4",
                            "--name", name, "--output-dir", output_dir,
                        ])
                    concat.assert_not_called()

    def test_h3_video_graph_has_basic_i2v_structure(self):
        # PR 8.3 刪掉 builder 後,改看 video/h3/img2video template(golden 見 test_video_graph_golden)
        from comfyui_pipeline.runner import template as runner_template
        repo = os.path.dirname(TOOLS_SRC)
        template = runner_template.load_template(os.path.join(repo, "templates"), "video/h3/img2video",
                                                 repo_root=repo)
        graph, output_id = template.graph, template.data["outputs"][0]["node"]
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
            with mock.patch.object(urllib.request, "urlopen", return_value=response) as opener:
                paths = cli.download_outputs(
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
                cli.download_outputs(
                    unsafe, output_dir, comfy_url="http://server:8188",
                )

    def test_clip_extend_generated_still_is_unique_and_cleaned(self):
        with tempfile.TemporaryDirectory() as output_dir:
            with mock.patch.object(task_video, "extract_last_frame") as extract, \
                    mock.patch.object(cli, "configure_video_capability", return_value="h3"), \
                    mock.patch.object(task_video, "video_canvas", return_value=(64, 64)), \
                    mock.patch.object(cli, "upload_image", return_value="last.png") as upload, \
                    mock.patch.object(cli, "submit_and_wait", return_value={"outputs": {}}), \
                    mock.patch.object(cli, "download_outputs", return_value=["out.mp4"]), \
                    patch_all("report_video_output", (cli, task_video_local, video_contract,), return_value={"frames": 49}), \
                    patch_all("write_video_sidecar", (cli, task_video_local,)):
                self.main([
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
                mock.patch.object(cli, "configure_video_capability", return_value="h3"), \
                mock.patch.object(cli, "upload_image") as upload:
            with self.assertRaisesRegex(SystemExit, "24 FPS"):
                self.main([
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
                paths, returned_dir = cli.extract_video_frames(
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
            with mock.patch.object(video_config, "validate_video_runtime"), \
                    mock.patch.object(video_config, "validate_comfy_video_nodes"):
                with self.assertRaisesRegex(RuntimeError, "請明確給 --backend"):
                    configure_video_capability(self.ctx,
                        "img2video", runtime_config_path=None,
                        video_config_path=config_path, comfy_url="http://server:8188",
                    )
        finally:
            os.unlink(config_path)

    def test_video_capability_selects_configured_backend_and_task_nodes(self):
        with tempfile.TemporaryDirectory() as model_dir:
            model_paths = {}
            for key, filename in video_catalog.VIDEO_BACKEND_SPECS["wan"]["models"].items():
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
                with mock.patch.object(video_config, "validate_video_runtime"), \
                        mock.patch.object(video_config, "validate_comfy_video_nodes") as nodes:
                    selected = configure_video_capability(self.ctx,
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
            with mock.patch.object(video_config, "validate_video_runtime"), \
                    mock.patch.object(video_config, "validate_comfy_video_nodes") as nodes:
                with self.assertRaisesRegex(RuntimeError, "upload/queue 前停止"):
                    configure_video_capability(self.ctx,
                        "img2video", video_config_path=config_path,
                        comfy_url="http://server:8188",
                    )
            nodes.assert_not_called()
        finally:
            os.unlink(config_path)

    def test_main_video_capability_failure_happens_before_upload(self):
        with mock.patch.object(
                cli, "configure_video_capability",
                side_effect=RuntimeError("missing video runtime"),
        ), mock.patch.object(cli, "upload_image") as upload:
            with self.assertRaisesRegex(SystemExit, "missing video runtime"):
                self.main([
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
            with mock.patch.object(urllib.request, "urlopen") as opener:
                with self.assertRaisesRegex(RuntimeError, "拒絕覆寫"):
                    cli.download_outputs(
                        history, output_dir, comfy_url="http://server:8188",
                        allow_overwrite=False,
                    )
            opener.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "拒絕覆寫"):
                task_video_local.concat_videos(["a.mp4", "b.mp4"], existing)

    def test_transition_rejects_mismatched_aspect_before_upload(self):
        with mock.patch.object(video_media, "_image_size", side_effect=[(512, 512), (768, 512)]):
            with self.assertRaisesRegex(ValueError, "比例"):
                video_media.validate_transition_images("a.png", "b.png")

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

    def test_video_fingerprint_ignores_uploaded_inventory_but_retains_interface(self):
        payload = {
            "LoadImage": {"input": {"required": {"image": [["old.png"], {"image_upload": True}]}}, "output": ["IMAGE"]},
            "LoadVideo": {"input": {"required": {"file": ["COMBO", {"options": ["old.mp4"], "video_upload": True}]}}, "output": ["VIDEO"]},
            "Sampler": {"input": {"required": {"mode": [["fast", "slow"], {}]}}, "output": ["LATENT"]},
        }
        before = json.loads(json.dumps(payload))
        fingerprint = video_config._node_schema_fingerprint(payload)
        self.assertEqual(before, payload)
        self.assertEqual(fingerprint, self.detector._schema_fingerprint(payload, list(payload)))
        payload["LoadImage"]["input"]["required"]["image"][0].append("new.png")
        payload["LoadVideo"]["input"]["required"]["file"][1]["options"].append("new.mp4")
        self.assertEqual(fingerprint, video_config._node_schema_fingerprint(payload))
        payload["LoadVideo"]["input"]["required"]["file"][1]["video_upload"] = False
        self.assertNotEqual(fingerprint, video_config._node_schema_fingerprint(payload))
        payload["LoadVideo"] = before["LoadVideo"]
        payload["Sampler"]["input"]["required"]["mode"][0].append("new-mode")
        self.assertNotEqual(fingerprint, video_config._node_schema_fingerprint(payload))
        payload["Sampler"] = before["Sampler"]
        payload["LoadImage"]["output"] = ["MASK"]
        self.assertNotEqual(fingerprint, video_config._node_schema_fingerprint(payload))

    def test_detector_catalog_loads_without_generate_py(self):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        with tempfile.TemporaryDirectory() as tmp:
            package_dir = os.path.join(tmp, "comfyui_pipeline")
            os.makedirs(package_dir, exist_ok=True)
            with open(os.path.join(repo_root, "tools_src", "comfyui_pipeline", "__init__.py"), encoding="utf-8") as source, \
                    open(os.path.join(package_dir, "__init__.py"), "w", encoding="utf-8") as target:
                target.write(source.read())
            with open(os.path.join(repo_root, "tools_src", "comfyui_pipeline", "video_catalog.py"), encoding="utf-8") as source, \
                    open(os.path.join(package_dir, "video_catalog.py"), "w", encoding="utf-8") as target:
                target.write(source.read())
            saved_modules = {
                name: sys.modules.pop(name)
                for name in list(sys.modules)
                if name == "comfyui_pipeline" or name.startswith("comfyui_pipeline.")
            }
            try:
                with mock.patch.object(sys, "path", [tmp] + list(sys.path)):
                    catalog = self.detector._load_generate_catalog()
            finally:
                sys.modules.update(saved_modules)
        self.assertIn("wan", catalog.VIDEO_BACKEND_SPECS)
        self.assertFalse(os.path.exists(os.path.join(tmp, "generate.py")))

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
            with patch_all("_require_pillow", (video_media, video_contract,)), \
                    mock.patch.dict(sys.modules, {"av": fake_av}):
                with self.assertRaisesRegex(ValueError, "相同 FPS"):
                    task_video_local.concat_videos(["a.mp4", "b.mp4"], dest)
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
            with patch_all("_require_pillow", (video_media, video_contract,)), \
                    mock.patch.dict(sys.modules, {"av": fake_av}):
                result = task_video_local.concat_videos([source_a, source_b], dest)
            self.assertEqual(dest, result)
            with open(dest, "rb") as joined:
                self.assertEqual(b"joined", joined.read())
            self.assertEqual(
                [], [name for name in os.listdir(output_dir) if name.startswith(".joined.mp4.")]
            )

            with patch_all("_require_pillow", (video_media, video_contract,)), \
                    mock.patch.dict(sys.modules, {"av": fake_av}), \
                    mock.patch.object(fake_av, "open", side_effect=AssertionError("must reject first")):
                with self.assertRaisesRegex(ValueError, "輸入影片不可與輸出路徑相同"):
                    task_video_local.concat_videos([source_a, source_b], source_a)

    @unittest.skipUnless(PYAV_AVAILABLE, "video_composite integration test requires PyAV")
    def test_video_composite_replaces_green_and_preserves_foreground(self):
        import av
        import numpy as np

        def write_video(path, arrays):
            output = av.open(path, "w")
            try:
                stream = output.add_stream("libx264", rate=24)
                stream.width = arrays[0].shape[1]
                stream.height = arrays[0].shape[0]
                stream.pix_fmt = "yuv420p"
                for array in arrays:
                    frame = av.VideoFrame.from_ndarray(array, format="rgb24")
                    for packet in stream.encode(frame):
                        output.mux(packet)
                for packet in stream.encode():
                    output.mux(packet)
            finally:
                output.close()

        with tempfile.TemporaryDirectory() as work:
            foreground = os.path.join(work, "foreground.mp4")
            background = os.path.join(work, "background.mp4")
            result = os.path.join(work, "result.mp4")
            green = np.zeros((16, 16, 3), dtype=np.uint8)
            green[:, :] = (0, 255, 0)
            green[4:12, 4:12] = (255, 0, 0)
            blue = np.zeros((16, 16, 3), dtype=np.uint8)
            blue[:, :] = (0, 0, 255)
            # A one-frame background exercises deterministic reopen/loop behavior.
            write_video(foreground, [green, green, green])
            write_video(background, [blue])

            task_video_local.composite_videos(foreground, background, result)

            container = av.open(result)
            try:
                frames = [frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)]
            finally:
                container.close()
            self.assertEqual(3, len(frames))
            for frame in frames:
                corner = frame[1, 1]
                center = frame[8, 8]
                self.assertGreater(int(corner[2]), int(corner[0]) + 100)
                self.assertGreater(int(center[0]), int(center[2]) + 100)

    @unittest.skipUnless(PYAV_AVAILABLE, "video_composite integration test requires PyAV")
    def test_video_composite_rejects_strict_size_mismatch_without_output(self):
        import av
        import numpy as np
        from PIL import Image

        with tempfile.TemporaryDirectory() as work:
            foreground = os.path.join(work, "foreground.mp4")
            background = os.path.join(work, "background.png")
            result = os.path.join(work, "result.mp4")
            output = av.open(foreground, "w")
            try:
                stream = output.add_stream("libx264", rate=24)
                stream.width = 16
                stream.height = 16
                stream.pix_fmt = "yuv420p"
                frame = av.VideoFrame.from_ndarray(
                    np.full((16, 16, 3), (0, 255, 0), dtype=np.uint8), format="rgb24",
                )
                for packet in stream.encode(frame):
                    output.mux(packet)
                for packet in stream.encode():
                    output.mux(packet)
            finally:
                output.close()
            Image.new("RGB", (32, 16), (0, 0, 255)).save(background)

            with self.assertRaisesRegex(ValueError, "--resize-mode strict"):
                task_video_local.composite_videos(
                    foreground, background, result, resize_mode="strict",
                )
            self.assertFalse(os.path.exists(result))

    def test_video_contract_fails_on_geometry_and_audio_mismatch(self):
        metadata = {
            "width": 128, "height": 64, "fps": 24.0, "frames": 49,
            "duration_seconds": 2.041667, "audio": False,
        }
        contract = video_contract.make_video_contract(
            "img2video", "h3", 64, 64, duration=2.0, audio_expected=True,
        )
        errors = video_contract._validate_video_contract(metadata, contract)
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
            contract = video_contract.make_video_contract("img2video", "h3", 64, 64, 2.0, True)
            actual = {"width": 64, "height": 64, "fps": 24.0, "frames": 56,
                      "duration_seconds": 2.333333, "audio": True,
                      "validation": {"status": "warning", "warnings": [{"kind": "continuity"}]}}
            path = video_contract.write_video_sidecar(
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
                    cli.extract_video_frames(os.path.join(output_dir, "clip.mp4"), output_dir)
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
            with patch_all("_require_pillow", (video_media, video_contract,)), \
                    mock.patch.dict(sys.modules, {"av": fake_av}):
                with self.assertRaisesRegex(ValueError, "音訊不一致"):
                    task_video_local.concat_videos(["a.mp4", "b.mp4"], dest)
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
                video_media.validate_video_input(source.name, label="motion-ref")

    def test_model_size_preflight_rejects_stale_capability_config(self):
        with tempfile.TemporaryDirectory() as model_dir:
            path = os.path.join(model_dir, "model.safetensors")
            with open(path, "wb") as model:
                model.write(b"actual")
            config = {"backends": {"wan": {"available": True, "models": {
                "i2v_unet": {"file": "model.safetensors", "path": path, "size_bytes": 999},
            }}}}
            with self.assertRaisesRegex(RuntimeError, "size_bytes"):
                video_config._validate_video_models(config, "wan", ["i2v"])

    def test_resume_requires_exact_sidecar_signature_and_revalidates_output(self):
        with tempfile.TemporaryDirectory() as work:
            source = os.path.join(work, "still.png")
            output = os.path.join(work, "shot_A01.mp4")
            for path, data in ((source, b"source"), (output, b"video")):
                with open(path, "wb") as handle:
                    handle.write(data)
            contract = video_contract.make_video_contract("img2video", "wan", 64, 64, 2.0, False)
            config = {"backends": {"wan": {"models": {}}}}
            actual = {"width": 64, "height": 64, "fps": 24.0, "frames": 49,
                      "duration_seconds": 2.041667, "audio": False,
                      "validation": {"status": "pass", "warnings": []}}
            video_contract.write_video_sidecar(output, "img2video", "wan", 7, "idle", "", [source],
                                              config, contract, actual)
            with patch_all("report_video_output", (cli, task_video_local, video_contract,), return_value=actual) as report:
                result = video_contract.resume_video_output(
                    output, "img2video", "wan", 7, [source], config, contract,
                )
            self.assertIs(actual, result)
            report.assert_called_once()
            with self.assertRaisesRegex(RuntimeError, "不完全相符"):
                video_contract.resume_video_output(output, "img2video", "wan", 8, [source], config, contract)

    def test_continuity_metric_is_warning_only(self):
        with tempfile.TemporaryDirectory() as work:
            source = os.path.join(work, "source.png")
            image_graphs.PILImage.new("RGB", (64, 64), (0, 0, 0)).save(source)
            black = image_graphs.PILImage.new("RGB", (64, 64), (0, 0, 0))
            white = image_graphs.PILImage.new("RGB", (64, 64), (255, 255, 255))
            with mock.patch.object(video_contract, "_first_last_video_images", return_value=(black, white)):
                warnings = video_contract._continuity_warnings("unused.mp4", "fx_loop")
            self.assertEqual("continuity", warnings[0]["kind"])
            self.assertEqual("seam", warnings[0]["label"])
            self.assertIn("warning", warnings[0]["message"])


if __name__ == "__main__":
    unittest.main()
