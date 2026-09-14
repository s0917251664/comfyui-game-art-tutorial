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
SAM_SEGMENT_PATH = ROOT / "tools_src" / "sam_segment.py"
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
        cls.sam_segment_bytes = SAM_SEGMENT_PATH.read_bytes()
        cls.pipeline_init_bytes = (PIPELINE_PKG / "__init__.py").read_bytes()
        cls.pipeline_image_bytes = (PIPELINE_PKG / "image_graphs.py").read_bytes()
        cls.pipeline_video_bytes = (PIPELINE_PKG / "video_catalog.py").read_bytes()
        cls.pipeline_video_graphs_bytes = (PIPELINE_PKG / "video_graphs.py").read_bytes()
        cls.pipeline_profiles_bytes = (PIPELINE_PKG / "profiles.py").read_bytes()
        cls.detect_image_bytes = (ROOT / "tools_src" / "detect_image_capabilities.py").read_bytes()
        cls.profile_json_bytes = {
            path.name: path.read_bytes() for path in sorted((PIPELINE_PKG / "profiles").glob("*.json"))
        }

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
        self._copy_source(tools_dir / "sam_segment.py", self.sam_segment_bytes)
        self._copy_source(tools_dir / "comfyui_pipeline" / "__init__.py", self.pipeline_init_bytes)
        self._copy_source(tools_dir / "comfyui_pipeline" / "image_graphs.py", self.pipeline_image_bytes)
        self._copy_source(tools_dir / "comfyui_pipeline" / "video_catalog.py", self.pipeline_video_bytes)
        self._copy_source(tools_dir / "comfyui_pipeline" / "video_graphs.py", self.pipeline_video_graphs_bytes)
        self._copy_source(tools_dir / "comfyui_pipeline" / "profiles.py", self.pipeline_profiles_bytes)
        self._copy_source(tools_dir / "detect_image_capabilities.py", self.detect_image_bytes)
        for name, source in self.profile_json_bytes.items():
            self._copy_source(tools_dir / "comfyui_pipeline" / "profiles" / name, source)
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

    def test_missing_sam_segment_fails_source_sync(self):
        live = {
            "os": "Windows", "machine": "amd64", "backend": "cuda",
            "tier": "sdxl", "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024, "default_height": 1024,
            "gpu_name": "Test GPU", "vram_mb": 24576,
        }
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            _, tools_dir, _, _, config_path = self._base_install(temp_root, live)
            (tools_dir / "sam_segment.py").unlink()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(
                    ["--config", str(config_path), "--repo-root", str(ROOT)], detector=lambda: live
                )
        self.assertEqual(1, code)
        self.assertIn("[FAIL] sam_segment.py source sync", out.getvalue())

    def test_platform_field_drift_fails_against_live_detector(self):
        live = {
            "os": "Darwin", "machine": "arm64", "backend": "mps",
            "tier": "sdxl", "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024, "default_height": 1024,
            "gpu_name": "Apple Silicon (MPS)", "vram_mb": None, "unified_memory_mb": 36864,
            "platform_key": "macos-mps", "usable_memory_mb": 18432, "memory_kind": "unified",
            "compute_capability": None, "precision_support": ["fp32", "fp16"],
        }
        legacy = {key: value for key, value in live.items()
                  if key not in ("platform_key", "usable_memory_mb", "memory_kind",
                                 "compute_capability", "precision_support")}
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, config_path = self._base_install(pathlib.Path(tmp), live, deployed_snapshot=legacy)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(["--config", str(config_path), "--repo-root", str(ROOT)], detector=lambda: live)
        self.assertEqual(1, code)
        self.assertIn("platform_key", out.getvalue())

    def test_precision_support_order_does_not_matter(self):
        live = {
            "os": "Windows", "machine": "amd64", "backend": "cuda",
            "tier": "sdxl", "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024, "default_height": 1024,
            "gpu_name": "Test GPU", "vram_mb": 16376, "precision_support": ["fp32", "fp16", "fp8"],
        }
        deployed = dict(live, precision_support=["FP8", "fp16", "fp32"])
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, config_path = self._base_install(pathlib.Path(tmp), live, deployed_snapshot=deployed)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(["--config", str(config_path), "--repo-root", str(ROOT)], detector=lambda: live)
        self.assertEqual(0, code, out.getvalue())

    IMAGE_LIVE = {
        "os": "Windows", "machine": "amd64", "backend": "cuda",
        "tier": "sdxl", "checkpoint": "sd_xl_base_1.0.safetensors",
        "default_width": 1024, "default_height": 1024,
        "gpu_name": "Test GPU", "vram_mb": 16376, "platform_key": "windows-cuda",
        "usable_memory_mb": 16376, "memory_kind": "dedicated", "compute_capability": "8.9",
        "precision_support": ["fp32", "fp16", "bf16", "fp8"],
    }

    def _run_image_verify(self, image_config_factory=None, extra_args=()):
        profiles_mod = self.verify._load_profiles_module(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            _, tools_dir, models_dir, _, config_path = self._base_install(pathlib.Path(tmp), self.IMAGE_LIVE)
            if image_config_factory is not None:
                self._write_json(tools_dir / "image_capabilities.json",
                                 image_config_factory(profiles_mod, models_dir))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(["--config", str(config_path), "--repo-root", str(ROOT), *extra_args],
                                        detector=lambda: self.IMAGE_LIVE)
        return code, out.getvalue()

    def _image_config(self, profiles_mod, models_dir, default_profile="sdxl_standard", create_checkpoint=True,
                      device=None):
        checkpoint = models_dir / "checkpoints" / "sd_xl_base_1.0.safetensors"
        if create_checkpoint:
            self._copy_source(checkpoint, b"model")
        return {
            "device_fingerprint": profiles_mod.device_fingerprint(device or self.IMAGE_LIVE),
            "default_profile": default_profile,
            "profiles": {"sdxl_standard": {"models": {"checkpoint": {"path": str(checkpoint)}}}},
        }

    def test_missing_image_config_is_info_unless_required(self):
        code, text = self._run_image_verify()
        self.assertEqual(0, code, text)
        self.assertIn("[INFO] 尚未產生 image_capabilities.json", text)
        code, text = self._run_image_verify(extra_args=["--require-image"])
        self.assertEqual(1, code)
        self.assertIn("[FAIL] image_config", text)

    def test_valid_image_config_passes_with_default_profile(self):
        code, text = self._run_image_verify(lambda p, m: self._image_config(p, m))
        self.assertEqual(0, code, text)
        self.assertIn("[PASS] image_config: default_profile: sdxl_standard", text)

    def test_stale_image_config_fingerprint_fails(self):
        code, text = self._run_image_verify(
            lambda p, m: self._image_config(p, m, device=dict(self.IMAGE_LIVE, usable_memory_mb=8192)))
        self.assertEqual(1, code)
        self.assertIn("detect_image_capabilities.py", text)

    def test_image_config_default_profile_checkpoint_must_exist(self):
        code, text = self._run_image_verify(lambda p, m: self._image_config(p, m, create_checkpoint=False))
        self.assertEqual(1, code)
        self.assertIn("底模檔案不存在", text)

    def _profile_sync_output(self, mutate_tools_dir):
        live = {
            "os": "Windows", "machine": "amd64", "backend": "cuda",
            "tier": "sdxl", "checkpoint": "sd_xl_base_1.0.safetensors",
            "default_width": 1024, "default_height": 1024,
            "gpu_name": "Test GPU", "vram_mb": 24576,
        }
        with tempfile.TemporaryDirectory() as tmp:
            _, tools_dir, _, _, config_path = self._base_install(pathlib.Path(tmp), live)
            mutate_tools_dir(tools_dir / "comfyui_pipeline" / "profiles")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.verify.main(["--config", str(config_path), "--repo-root", str(ROOT)], detector=lambda: live)
        return code, out.getvalue()

    def test_missing_deployed_profile_fails_source_sync(self):
        code, text = self._profile_sync_output(lambda d: (d / "sd15_light.json").unlink())
        self.assertEqual(1, code)
        self.assertIn("[FAIL] comfyui_pipeline/profiles/sd15_light.json source sync", text)
        self.assertIn("[PASS] comfyui_pipeline/profiles/sdxl_standard.json source sync", text)

    def test_stale_deployed_profile_fails_source_sync(self):
        code, text = self._profile_sync_output(lambda d: (d / "retired.json").write_text("{}", encoding="utf-8"))
        self.assertEqual(1, code)
        self.assertIn("[FAIL] comfyui_pipeline/profiles/retired.json source sync", text)
        self.assertIn("repo 已不存在", text)

    def test_drifted_deployed_profile_fails_source_sync(self):
        def drift(profiles_dir):
            path = profiles_dir / "sdxl_standard.json"
            path.write_text(path.read_text(encoding="utf-8").replace('"steps": 25', '"steps": 8'), encoding="utf-8")
        code, text = self._profile_sync_output(drift)
        self.assertEqual(1, code)
        self.assertIn("[FAIL] comfyui_pipeline/profiles/sdxl_standard.json source sync", text)

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
                    ("sam_segment.py", self.sam_segment_bytes),
                    ("comfyui_pipeline/__init__.py", self.pipeline_init_bytes),
                    ("comfyui_pipeline/image_graphs.py", self.pipeline_image_bytes),
                    ("comfyui_pipeline/video_catalog.py", self.pipeline_video_bytes),
                    ("comfyui_pipeline/video_graphs.py", self.pipeline_video_graphs_bytes),
                    ("comfyui_pipeline/profiles.py", self.pipeline_profiles_bytes),
                    ("detect_image_capabilities.py", self.detect_image_bytes),
                    *((f"comfyui_pipeline/profiles/{name}", source)
                      for name, source in self.profile_json_bytes.items())):
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
