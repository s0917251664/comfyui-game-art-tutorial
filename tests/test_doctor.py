import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_SRC = Path(__file__).resolve().parents[1] / "tools_src"
sys.path.insert(0, str(TOOLS_SRC))
from comfyui_pipeline import fingerprint as fp  # noqa: E402
import doctor  # noqa: E402


def make_env(root):
    comfy = os.path.join(root, "ComfyUI")
    models = os.path.join(comfy, "models")
    os.makedirs(os.path.join(comfy, "custom_nodes", "node_a"))
    os.makedirs(os.path.join(comfy, ".git"))
    os.makedirs(os.path.join(models, "checkpoints"))
    Path(comfy, ".git", "HEAD").write_text("abc123\n")
    Path(comfy, "comfyui_version.py").write_text('__version__ = "0.3.1"\n')
    Path(models, "checkpoints", "a.safetensors").write_bytes(b"12345")
    tools = os.path.join(comfy, "tools")
    os.makedirs(tools)
    return comfy, models, tools


class FingerprintTests(unittest.TestCase):
    def test_components_and_compare(self):
        with tempfile.TemporaryDirectory() as root:
            comfy, models, tools = make_env(root)
            base = fp.compute_components(comfy, [models])
            self.assertEqual(base["comfyui"], {"commit": "abc123", "version": "0.3.1"})
            self.assertEqual(base["custom_nodes"]["count"], 1)
            self.assertEqual(fp.compare_components(base, fp.compute_components(comfy, [models])), [])
            os.makedirs(os.path.join(comfy, "custom_nodes", "node_b"))
            Path(models, "checkpoints", "b.safetensors").write_bytes(b"1")
            Path(comfy, ".git", "HEAD").write_text("def456\n")
            diffs = fp.compare_components(base, fp.compute_components(comfy, [models]))
            self.assertEqual({d["component"] for d in diffs}, {"comfyui", "custom_nodes", "models"})

    def test_missing_component_is_not_a_diff(self):
        recorded = {"models": {"count": 1, "hash": "x"}, "hardware": None}
        self.assertEqual(fp.compare_components(recorded, {"models": None}), [])

    def test_read_fingerprint_tolerates_garbage(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, fp.FINGERPRINT_FILENAME)
            self.assertIsNone(fp.read_fingerprint(path))
            Path(path).write_text("{not json")
            self.assertIsNone(fp.read_fingerprint(path))


class ReminderTests(unittest.TestCase):
    def setUp(self):
        fp._reminded = False

    def test_silent_without_sidecar(self):
        with tempfile.TemporaryDirectory() as root:
            buf = io.StringIO()
            self.assertFalse(fp.reminder_if_stale(root, stream=buf))
            self.assertEqual(buf.getvalue(), "")

    def test_reminds_once_when_stale_and_silent_when_fresh(self):
        with tempfile.TemporaryDirectory() as root:
            comfy, models, tools = make_env(root)
            fp.write_fingerprint(os.path.join(tools, fp.FINGERPRINT_FILENAME),
                                 fp.build_fingerprint(comfy, [models], tools, include_hardware=False))
            buf = io.StringIO()
            self.assertFalse(fp.reminder_if_stale(tools, stream=buf))
            os.makedirs(os.path.join(comfy, "custom_nodes", "node_b"))
            self.assertTrue(fp.reminder_if_stale(tools, stream=buf))
            self.assertIn("[提醒]", buf.getvalue())
            self.assertIn("doctor --refresh", buf.getvalue())
            self.assertEqual(buf.getvalue().count("\n"), 1)
            self.assertFalse(fp.reminder_if_stale(tools, stream=buf))  # 每行程一次


class DoctorStatusTests(unittest.TestCase):
    def run_doctor(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = doctor.main(list(argv))
        return code, buf.getvalue()

    def test_status_json_with_and_without_snapshots(self):
        with tempfile.TemporaryDirectory() as root:
            comfy, models, tools = make_env(root)
            config = os.path.join(root, "local_config.json")
            Path(config).write_text(json.dumps({"comfyui_path": comfy}))
            code, out = self.run_doctor("--config", config, "--json")
            data = json.loads(out)
            self.assertEqual(code, 0)
            self.assertFalse(any(s["exists"] for s in data["snapshots"].values()))
            self.assertFalse(data["fingerprint"]["exists"])

            Path(tools, "image_capabilities.json").write_text(json.dumps({
                "captured_at": "2020-01-01T00:00:00+00:00", "default_profile": "p",
                "profiles": {"p": {"eligible": True, "installed": True, "tasks": {
                    "concept": {"available": True, "validation": "unverified"},
                    "inpaint": {"available": False, "validation": "verified", "missing_files": ["m.safetensors"]},
                }}}}))
            fp.write_fingerprint(os.path.join(tools, fp.FINGERPRINT_FILENAME),
                                 fp.build_fingerprint(comfy, [models], tools, include_hardware=False))
            os.makedirs(os.path.join(comfy, "custom_nodes", "node_b"))
            code, out = self.run_doctor("--config", config, "--json")
            data = json.loads(out)
            self.assertTrue(data["snapshots"]["image"]["exists"])
            self.assertGreater(data["snapshots"]["image"]["age_seconds"], 0)
            self.assertTrue(data["fingerprint"]["stale"])
            self.assertEqual(data["image"]["profiles"]["p"]["unverified"], ["concept"])
            code, text = self.run_doctor("--config", config)
            self.assertIn("custom_nodes", text)
            self.assertIn("unverified", text)


if __name__ == "__main__":
    unittest.main()
