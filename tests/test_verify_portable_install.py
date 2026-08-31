import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "tools_src" / "verify_portable_install.py"
GENERATE_PATH = ROOT / "tools_src" / "generate.py"
DETECT_DEVICE_PATH = ROOT / "tools_src" / "detect_device.py"
DETECT_VIDEO_PATH = ROOT / "tools_src" / "detect_video_capabilities.py"
PIPELINE_PKG = ROOT / "tools_src" / "comfyui_pipeline"


def load_module(path, name):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class VerifyPortableInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verify = load_module(VERIFY_PATH, "verify_portable_install_under_test")
        cls.generate = load_module(GENERATE_PATH, "generate_under_test")
        cls.detect_video = load_module(DETECT_VIDEO_PATH, "detect_video_capabilities_under_test")
        cls.generate_bytes = GENERATE_PATH.read_bytes()
        cls.detect_device_bytes = DETECT_DEVICE_PATH.read_bytes()
        cls.detect_video_bytes = DETECT_VIDEO_PATH.read_bytes()
        cls.pipeline_init_bytes = (PIPELINE_PKG / "__init__.py").read_bytes()
        cls.pipeline_image_bytes = (PIPELINE_PKG / "image_graphs.py").read_bytes()
        cls.pipeline_video_bytes = (PIPELINE_PKG / "video_catalog.py").read_bytes()

    def _write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _copy_source(self, path, source_bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source_bytes)

    def _base_install(self, temp_root, live_snapshot, deployed_snapshot=None, include_video=False):
        comfyui_path = temp_root / "ComfyUI"
        tools_dir = comfyui_path / "tools"
        models_dir = comfyui_path / "models"
        output_dir = temp_root / "output"
        tools_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)
        for subdir in ("diffusion_models", "text_encoders", "vae"):
            (models_dir / subdir).mkdir(parents=True)

        self._copy_source(tools_dir / "generate.py", self.generate_bytes)
        self._copy_source(tools_dir / "detect_device.py", self.detect_device_bytes)
        self._copy_source(tools_dir / "comfyui_pipeline" / "__init__.py", self.pipeline_init_bytes)
        self._copy_source(tools_dir / "comfyui_pipeline" / "image_graphs.py", self.pipeline_image_bytes)
        self._copy_source(tools_dir / "comfyui_pipeline" / "video_catalog.py", self.pipeline_video_bytes)
        if include_video:
            self._copy_source(tools_dir / "detect_video_capabilities.py", self.detect_video_bytes)

        self._write_json(tools_dir / "device_config.json", deployed_snapshot or live_snapshot)

        local_config = {
            "comfyui_path": str(comfyui_path),
            "python_exe": sys.executable,
            "generate_script": str(tools_dir / "generate.py"),
            "comfyui_url": "http://127.0.0.1:8188",
            "output_dir": str(output_dir),
        }
        config_path = temp_root / "local_config.json"
        self._write_json(config_path, local_config)
        return comfyui_path, tools_dir, models_dir, output_dir, config_path

    def _write_wan_video_config(
            self, tools_dir, comfyui_path, models_dir, live_snapshot,
            missing_keys=(), absent_keys=()):
        wan_spec = self.generate.VIDEO_BACKEND_SPECS["wan"]
        models = {}
        for key, filename in wan_spec["models"].items():
            directory = self.detect_video.MODEL_DIRECTORIES["wan"][key]
            model_path = models_dir / directory / filename
            present = key not in absent_keys
            models[key] = {
                "file": filename,
                "directory": directory,
                "path": str(model_path),
                "present": present,
                "size_bytes": 5 if present else None,
            }
            if key not in missing_keys and present:
                self._copy_source(model_path, b"model")
        capabilities = ["i2v"] if absent_keys else sorted(wan_spec["capabilities"])
        video_config = {
            "schema_version": 1,
            "comfyui_path": str(comfyui_path),
            "python_exe": sys.executable,
            "device_config": dict(live_snapshot),
            "backends": {
                "wan": {
                    "available": True,
                    "capabilities": capabilities,
                    "models": models,
                }
            },
        }
        self._write_json(tools_dir / "video_capabilities.json", video_config)

    def test_tier_mismatch_is_stale_against_live_detector(self):
        live = {
            "os": "Windows",
            "machine": "amd64",
            "backend": "cuda",
            "tier": "sdxl",
            "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024,
            "default_height": 1024,
            "gpu_name": "Test GPU",
            "vram_mb": 24576,
        }
        stale = dict(live, tier="sd15", checkpoint="dreamshaper_8.safetensors")

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            _, _, _, _, config_path = self._base_install(temp_root, live, deployed_snapshot=stale)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(["--config", str(config_path), "--repo-root", str(ROOT)], detector=lambda: live)

        self.assertEqual(1, code)
        text = out.getvalue()
        self.assertIn("tier", text)
        self.assertIn("請在目標機重跑 detect_device.py", text)

    def test_matching_live_detector_passes(self):
        live = {
            "os": "Windows",
            "machine": "amd64",
            "backend": "cuda",
            "tier": "sdxl",
            "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024,
            "default_height": 1024,
            "gpu_name": "Test GPU",
            "vram_mb": 24576,
        }

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            _, _, _, _, config_path = self._base_install(temp_root, live)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(["--config", str(config_path), "--repo-root", str(ROOT)], detector=lambda: live)

        self.assertEqual(0, code)
        self.assertIn("[PASS] device_config 對照 live detect()", out.getvalue())

    def test_detect_device_source_drift_fails_source_sync(self):
        live = {
            "os": "Windows",
            "machine": "amd64",
            "backend": "cuda",
            "tier": "sdxl",
            "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024,
            "default_height": 1024,
            "gpu_name": "Test GPU",
            "vram_mb": 24576,
        }

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            comfyui_path, tools_dir, _, _, config_path = self._base_install(temp_root, live)
            self._copy_source(tools_dir / "detect_device.py", self.detect_device_bytes + b"\n# drift\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(["--config", str(config_path), "--repo-root", str(ROOT)], detector=lambda: live)

        self.assertEqual(1, code)
        text = out.getvalue()
        self.assertIn("[FAIL] detect_device.py source sync", text)

    def test_source_sync_accepts_only_newline_differences(self):
        live = {
            "os": "Windows", "machine": "amd64", "backend": "cuda",
            "tier": "sdxl", "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024, "default_height": 1024,
            "gpu_name": "Test GPU", "vram_mb": 24576,
        }

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            _, tools_dir, _, _, config_path = self._base_install(temp_root, live)
            for name, source in (
                    ("generate.py", self.generate_bytes),
                    ("detect_device.py", self.detect_device_bytes),
                    ("comfyui_pipeline/__init__.py", self.pipeline_init_bytes),
                    ("comfyui_pipeline/image_graphs.py", self.pipeline_image_bytes),
                    ("comfyui_pipeline/video_catalog.py", self.pipeline_video_bytes)):
                text = source.decode("utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
                target = tools_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8", newline="")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(
                    ["--config", str(config_path), "--repo-root", str(ROOT)],
                    detector=lambda: live,
                )

        self.assertEqual(0, code)
        self.assertNotIn("[FAIL]", out.getvalue())

    def test_video_success_uses_default_path_and_matching_models(self):
        live = {
            "os": "Windows",
            "machine": "amd64",
            "backend": "cuda",
            "tier": "sdxl",
            "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024,
            "default_height": 1024,
            "gpu_name": "Test GPU",
            "vram_mb": 24576,
        }

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            comfyui_path, tools_dir, models_dir, _, config_path = self._base_install(
                temp_root, live, include_video=True,
            )
            self._write_wan_video_config(tools_dir, comfyui_path, models_dir, live)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(
                    ["--config", str(config_path), "--repo-root", str(ROOT), "--require-video"],
                    detector=lambda: live,
                )

        self.assertEqual(0, code)
        text = out.getvalue()
        self.assertIn("[PASS] detect_video_capabilities.py source sync", text)
        self.assertIn("[PASS] video_config", text)

    def test_video_model_missing_fails(self):
        live = {
            "os": "Windows",
            "machine": "amd64",
            "backend": "cuda",
            "tier": "sdxl",
            "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024,
            "default_height": 1024,
            "gpu_name": "Test GPU",
            "vram_mb": 24576,
        }

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            comfyui_path, tools_dir, models_dir, _, config_path = self._base_install(
                temp_root, live, include_video=True,
            )
            self._write_wan_video_config(tools_dir, comfyui_path, models_dir, live, missing_keys={"vae"})
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(
                    ["--config", str(config_path), "--repo-root", str(ROOT), "--require-video"],
                    detector=lambda: live,
                )

        self.assertEqual(1, code)
        self.assertIn("video_config 列出的可用 backend 模型路徑不存在", out.getvalue())

    def test_video_partial_backend_skips_models_marked_absent(self):
        live = {
            "os": "Linux",
            "machine": "x86_64",
            "backend": "cuda",
            "tier": "sdxl_light",
            "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 768,
            "default_height": 768,
            "gpu_name": "Small GPU",
            "vram_mb": 8192,
        }

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            comfyui_path, tools_dir, models_dir, _, config_path = self._base_install(
                temp_root, live, include_video=True,
            )
            self._write_wan_video_config(
                tools_dir, comfyui_path, models_dir, live,
                absent_keys={"control_unet"},
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(
                    ["--config", str(config_path), "--repo-root", str(ROOT), "--require-video"],
                    detector=lambda: live,
                )

        self.assertEqual(0, code)
        self.assertIn("[PASS] video_config", out.getvalue())


if __name__ == "__main__":
    unittest.main()
