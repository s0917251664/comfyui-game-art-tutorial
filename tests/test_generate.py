import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock


MODULE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools_src", "generate.py")


def load_generate_module():
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        spec = importlib.util.spec_from_file_location("generate_under_test", MODULE_PATH)
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

    def setUp(self):
        self.generate.COMFY_URL = None
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


if __name__ == "__main__":
    unittest.main()
