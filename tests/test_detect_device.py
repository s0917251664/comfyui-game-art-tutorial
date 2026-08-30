import contextlib
import io
import pathlib
import subprocess
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools_src"))

import detect_device


class DetectDeviceTests(unittest.TestCase):
    def completed(self, stdout=""):
        return subprocess.CompletedProcess(["nvidia-smi"], 0, stdout=stdout, stderr="")

    @mock.patch.object(detect_device.shutil, "which", return_value="/usr/bin/nvidia-smi")
    @mock.patch.object(detect_device.subprocess, "run")
    def test_cuda13_requires_driver_580(self, run, _which):
        for driver, expected in (
            ("549.99.99\r\n", "cu126"),
            ("550.54.14\r\n", "cu126"),
            ("579.99.01\r\n", "cu126"),
            ("580.00.00\r\n", "cu130"),
            ("580.65.06\r\n", "cu130"),
        ):
            with self.subTest(driver=driver):
                run.return_value = self.completed(driver)
                self.assertEqual(detect_device.get_nvidia_driver_cuda_hint(), expected)

    @mock.patch.object(detect_device.shutil, "which", return_value="/usr/bin/nvidia-smi")
    @mock.patch.object(detect_device.subprocess, "run")
    def test_driver_query_uses_oldest_version_when_output_differs(self, run, _which):
        run.return_value = self.completed("580.65.06\n579.99.01\n")

        self.assertEqual(detect_device.get_nvidia_driver_cuda_hint(), "cu126")

    @mock.patch.object(detect_device.shutil, "which", return_value=None)
    def test_missing_nvidia_smi_keeps_normal_fallback_without_warning(self, _which):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertIsNone(detect_device.get_nvidia_gpu())
            self.assertEqual(detect_device.get_nvidia_driver_cuda_hint(), "cu126")

        self.assertEqual(stderr.getvalue(), "")

    @mock.patch.object(detect_device.shutil, "which", return_value="/usr/bin/nvidia-smi")
    @mock.patch.object(detect_device.subprocess, "run")
    def test_selects_gpu_with_most_vram_and_preserves_name(self, run, _which):
        run.return_value = self.completed(
            '"NVIDIA GeForce RTX 4080, Laptop GPU", 12288\n'
            'NVIDIA RTX 4090, 24576\n'
        )

        self.assertEqual(detect_device.get_nvidia_gpu(), ("NVIDIA RTX 4090", 24576))

    @mock.patch.object(detect_device.shutil, "which", return_value="/usr/bin/nvidia-smi")
    @mock.patch.object(detect_device.subprocess, "run")
    def test_malformed_gpu_row_is_diagnostic_but_good_rows_still_work(self, run, _which):
        run.return_value = self.completed("not-a-row\nNVIDIA RTX 4090, 24576\n")
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            gpu = detect_device.get_nvidia_gpu()

        self.assertEqual(gpu, ("NVIDIA RTX 4090", 24576))
        self.assertIn("nvidia-smi", stderr.getvalue())

    @mock.patch.object(detect_device.shutil, "which", return_value="/usr/bin/nvidia-smi")
    @mock.patch.object(detect_device.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "nvidia-smi"))
    def test_nvidia_smi_failure_emits_diagnostic_warning(self, _run, _which):
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            gpu = detect_device.get_nvidia_gpu()

        self.assertIsNone(gpu)
        self.assertIn("nvidia-smi", stderr.getvalue())

    @mock.patch.object(detect_device.platform, "system", return_value="Darwin")
    @mock.patch.object(detect_device.platform, "machine", return_value="arm64")
    @mock.patch.object(detect_device, "get_nvidia_gpu", return_value=None)
    @mock.patch.object(detect_device.subprocess, "run")
    def test_apple_unified_memory_is_exposed_and_tiered_conservatively(
        self, run, _get_gpu, _machine, _system
    ):
        total_memory_mb = 36 * 1024
        run.return_value = self.completed(str(total_memory_mb * 1024 * 1024))

        config = detect_device.detect()

        self.assertEqual(config["backend"], "mps")
        self.assertEqual(config["gpu_name"], "Apple Silicon (MPS)")
        self.assertIsNone(config["vram_mb"])
        self.assertEqual(config["unified_memory_mb"], total_memory_mb)
        self.assertEqual(config["tier"], "sdxl")
        self.assertEqual((config["default_width"], config["default_height"]), (1024, 1024))

    @mock.patch.object(detect_device.platform, "system", return_value="Darwin")
    @mock.patch.object(detect_device.platform, "machine", return_value="arm64")
    @mock.patch.object(detect_device, "get_nvidia_gpu", return_value=None)
    @mock.patch.object(detect_device.subprocess, "run", side_effect=FileNotFoundError("sysctl"))
    def test_unreadable_apple_memory_uses_safe_lowest_tier_with_warning(
        self, _run, _get_gpu, _machine, _system
    ):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            config = detect_device.detect()

        self.assertEqual(config["backend"], "mps")
        self.assertIsNone(config["vram_mb"])
        self.assertEqual(config["tier"], "sd15")
        self.assertIn("unified memory", stderr.getvalue())

    def test_default_config_path_is_next_to_detector(self):
        expected = ROOT / "tools_src" / "device_config.json"
        self.assertEqual(expected, pathlib.Path(detect_device.DEFAULT_DEVICE_CONFIG_PATH))


if __name__ == "__main__":
    unittest.main()
