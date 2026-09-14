import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools_src"))

import detect_image_capabilities as detector  # noqa: E402


MPS_DEVICE = {
    "os": "Darwin", "backend": "mps", "platform_key": "macos-mps", "tier": "sdxl",
    "gpu_name": "Apple Silicon (MPS)", "usable_memory_mb": 18432,
    "precision_support": ["fp32", "fp16"],
}
CUDA_DEVICE = {
    "os": "Windows", "backend": "cuda", "platform_key": "windows-cuda", "tier": "sdxl",
    "gpu_name": "RTX 4080", "usable_memory_mb": 16376,
    "precision_support": ["fp32", "fp16", "bf16", "fp8"],
}


class DetectImageCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.comfyui = os.path.join(self._tmp.name, "ComfyUI")
        os.makedirs(os.path.join(self.comfyui, "tools"))

    def tearDown(self):
        self._tmp.cleanup()

    def _model(self, directory, filename):
        path = os.path.join(self.comfyui, "models", directory, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"x")

    def _device(self, device):
        path = os.path.join(self.comfyui, "tools", "device_config.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(device, handle)

    def _args(self, **overrides):
        values = dict(comfyui_path=self.comfyui, model_root=None, device_config=None,
                      comfy_url=None, http_timeout=5.0, out=None, overwrite=False)
        values.update(overrides)
        return SimpleNamespace(**values)

    def _install_sdxl_base(self):
        self._model("checkpoints", "sd_xl_base_1.0.safetensors")

    def test_checkpoint_only_enables_base_tasks_and_reports_missing_addons(self):
        self._device(CUDA_DEVICE)
        self._install_sdxl_base()
        config = detector.detect(self._args())
        sdxl = config["profiles"]["sdxl_standard"]
        self.assertEqual("sdxl_standard", config["default_profile"])
        self.assertTrue(sdxl["eligible"])
        self.assertTrue(sdxl["tasks"]["concept"]["available"])
        self.assertFalse(sdxl["tasks"]["style_lock"]["available"])
        self.assertEqual(["ipadapter", "clip_vision"], sdxl["tasks"]["style_lock"]["missing_models"])
        self.assertIn("ip-adapter-plus_sdxl_vit-h.safetensors", sdxl["tasks"]["style_lock"]["missing_files"])
        self.assertFalse(sdxl["tasks"]["pose_only"]["available"])
        self.assertEqual(["controlnet.canny | controlnet.depth | controlnet.pose"],
                         sdxl["tasks"]["pose_only"]["missing_models"])
        self.assertEqual("not_checked", config["node_check"]["status"])

    def test_controlnet_group_is_satisfied_by_any_verified_member_but_not_union(self):
        self._device(CUDA_DEVICE)
        self._install_sdxl_base()
        self._model("controlnet", "xinsir-controlnet-union-sdxl-1.0-promax.safetensors")
        pose_only = detector.detect(self._args())["profiles"]["sdxl_standard"]["tasks"]["pose_only"]
        self.assertFalse(pose_only["available"], "實驗性 union 不能滿足必要的 controlnet 群組")

        self._model("controlnet", "controlnet-openpose-sdxl-1.0.safetensors")
        pose_only = detector.detect(self._args())["profiles"]["sdxl_standard"]["tasks"]["pose_only"]
        self.assertTrue(pose_only["available"])
        self.assertTrue(pose_only["features"]["controlnet.pose"]["available"])
        self.assertFalse(pose_only["features"]["controlnet.canny"]["available"])
        self.assertTrue(pose_only["features"]["controlnet.union"]["experimental"])

    def test_missing_custom_nodes_make_task_unavailable_when_object_info_is_checked(self):
        self._device(CUDA_DEVICE)
        self._install_sdxl_base()
        self._model("controlnet", "controlnet-openpose-sdxl-1.0.safetensors")
        node_check = {"status": "available", "url": "http://x/object_info", "error": None,
                      "classes": ["CheckpointLoaderSimple", "ControlNetLoader", "ControlNetApplyAdvanced"]}
        with mock.patch.object(detector, "query_object_info", return_value=node_check):
            pose_only = detector.detect(self._args(comfy_url="http://x"))["profiles"]["sdxl_standard"]["tasks"]["pose_only"]
        self.assertFalse(pose_only["available"])
        self.assertEqual(["OpenposePreprocessor"], pose_only["missing_nodes"])

    def test_validation_downgrades_by_platform_and_memory(self):
        self._install_sdxl_base()
        self._device(CUDA_DEVICE)
        concept = detector.detect(self._args())["profiles"]["sdxl_standard"]["tasks"]["concept"]
        self.assertEqual(("verified", None), (concept["validation"], concept["validation_reason"]))

        self._device(dict(CUDA_DEVICE, usable_memory_mb=10240))
        concept = detector.detect(self._args())["profiles"]["sdxl_standard"]["tasks"]["concept"]
        self.assertEqual("unverified", concept["validation"])
        self.assertIn("16000", concept["validation_reason"])

        self._device(MPS_DEVICE)
        concept = detector.detect(self._args())["profiles"]["sdxl_standard"]["tasks"]["concept"]
        self.assertEqual("unverified", concept["validation"])
        self.assertIn("macos-mps", concept["validation_reason"])

    def test_ineligible_platform_blocks_tasks_even_when_models_exist(self):
        self._install_sdxl_base()
        self._device(dict(CUDA_DEVICE, backend="cpu", platform_key="linux-cpu", usable_memory_mb=0,
                          precision_support=["fp32"], tier="sd15"))
        config = detector.detect(self._args())
        sdxl = config["profiles"]["sdxl_standard"]
        self.assertFalse(sdxl["eligible"])
        self.assertFalse(sdxl["tasks"]["concept"]["available"])
        self.assertIsNone(config["default_profile"], "sd15 tier 的底模沒裝時不該有預設設定檔")
        self.assertTrue(config["profiles"]["sd15_light"]["eligible"])

    def test_legacy_device_config_requires_rerunning_detect_device(self):
        self._device({"backend": "cuda", "tier": "sdxl"})
        with self.assertRaisesRegex(RuntimeError, "detect_device.py"):
            detector.detect(self._args())

    def test_model_root_supports_shared_model_library(self):
        shared = os.path.join(self._tmp.name, "shared")
        path = os.path.join(shared, "checkpoints", "sd_xl_base_1.0.safetensors")
        os.makedirs(os.path.dirname(path))
        open(path, "wb").close()
        self._device(CUDA_DEVICE)
        config = detector.detect(self._args(model_root=[shared]))
        self.assertTrue(config["profiles"]["sdxl_standard"]["installed"])

    def test_fingerprint_changes_with_platform_fields(self):
        self.assertNotEqual(detector.device_fingerprint(CUDA_DEVICE),
                            detector.device_fingerprint(dict(CUDA_DEVICE, usable_memory_mb=8192)))

    def test_main_refuses_to_overwrite_without_flag(self):
        self._device(CUDA_DEVICE)
        out = os.path.join(self.comfyui, "tools", "image_capabilities.json")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, detector.main(["--comfyui-path", self.comfyui]))
        self.assertTrue(os.path.isfile(out))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            detector.main(["--comfyui-path", self.comfyui])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, detector.main(["--comfyui-path", self.comfyui, "--overwrite"]))


if __name__ == "__main__":
    unittest.main()
