import optional_deps

optional_deps.require("PIL", "numpy")

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from tools_src import image_edit_tools as tool


class EditToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.png"
        self.edited = self.root / "edited.png"
        self.mask = self.root / "mask.png"
        Image.new("RGBA", (3, 1), (10, 20, 30, 255)).save(self.source)
        Image.new("RGBA", (3, 1), (110, 120, 130, 0)).save(self.edited)
        mask = Image.new("RGBA", (3, 1))
        mask.putalpha(Image.fromarray(np.array([[0, 128, 255]], dtype=np.uint8)))
        mask.save(self.mask)

    def plan(self, **overrides):
        plan = {"task": "inpaint", "base": {"image": "source.png", "mask": "mask.png",
                "prompt": "change material", "seed": 42}, "sweep": {"denoise": [0.4, 0.6]},
                "preserve_outside": True}
        plan.update(overrides)
        return plan

    def config_file(self):
        config = self.root / "config.json"
        config.write_text(json.dumps({"python_exe": sys.executable,
                           "generate_script": str(self.root / "generate.py"),
                           "comfyui_path": str(self.root), "comfyui_url": "http://127.0.0.1:8188"}))
        return config

    def write_plan(self, plan=None):
        path = self.root / "plan.json"
        path.write_text(json.dumps(plan or self.plan()))
        return path

    def test_composite_preserves_exact_rgba_and_soft_mask_direction(self):
        report = tool.composite(self.source, self.edited, self.mask, self.root / "out")
        result = tool.load_image(report["output"]["path"])
        self.assertEqual((110, 120, 130, 0), result.getpixel((0, 0)))
        self.assertEqual((60, 70, 80, 128), result.getpixel((1, 0)))
        self.assertEqual((10, 20, 30, 255), result.getpixel((2, 0)))
        self.assertEqual(0, report["outside_changed_pixels"])
        self.assertEqual("candidate", report["status"])

    def test_rejects_resize_missing_alpha_and_existing_destination(self):
        Image.new("RGB", (3, 1)).save(self.mask)
        with self.assertRaisesRegex(ValueError, "Alpha"):
            tool.composite(self.source, self.edited, self.mask, self.root / "invalid")
        self.assertFalse((self.root / "invalid").exists())
        Image.new("RGBA", (2, 1)).save(self.edited)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            tool.compare(self.source, self.edited, self.root / "invalid")
        with self.assertRaises(FileExistsError):
            tool.compare(self.source, self.source, self.root)

    def test_comparison_regions_count_hidden_rgb_and_alpha(self):
        result = tool.compare(self.source, self.edited, self.root / "compare", self.mask)
        self.assertEqual(3, result["regions"]["whole"]["changed_pixels"])
        for region in ("edited", "transition", "preserved"):
            self.assertEqual(1, result["regions"][region]["pixels"])
            self.assertEqual(255, result["regions"][region]["max_byte_difference"])
        self.assertEqual("not assessed", result["art_acceptance"])
        Image.new("RGBA", (3, 1), (0, 0, 0, 0)).save(self.source)
        Image.new("RGBA", (3, 1), (1, 0, 0, 0)).save(self.edited)
        result = tool.compare(self.source, self.edited, self.root / "hidden")
        self.assertEqual(3, result["regions"]["whole"]["changed_pixels"])

    def test_empty_region_has_null_measurement_and_identity_has_zero_changes(self):
        Image.new("RGBA", (3, 1), (0, 0, 0, 255)).save(self.mask)
        report = tool.compare(self.source, self.source, self.root / "same", self.mask)
        self.assertEqual(0, report["regions"]["whole"]["changed_pixels"])
        self.assertIsNone(report["regions"]["edited"]["changed_fraction"])
        self.assertFalse((self.root / "same/detail.png").exists())

    def test_plan_keeps_seed_prompt_inputs_fixed_and_resolves_relative_paths(self):
        task, runs, preserve = tool.expand_plan(self.plan(), self.root)
        self.assertEqual("inpaint", task)
        self.assertTrue(preserve)
        self.assertEqual([0.4, 0.6], [run["denoise"] for run in runs])
        self.assertEqual({42}, {run["seed"] for run in runs})
        self.assertEqual({str(self.source.resolve())}, {run["image"] for run in runs})

    def test_plan_rejects_unsupported_axes_over_budget_duplicates_and_bad_values(self):
        for axes in ({"seed": [1, 2]}, {"image": ["source.png"]}, {"prompt": ["x"]},
                     {"denoise": [float("nan")]}, {"denoise": [True]}, {"denoise": [1.1]},
                     {"denoise": [0.4, 0.4]}, {"denoise": [n / 20 for n in range(17)]}):
            with self.subTest(axes=axes), self.assertRaises(ValueError):
                tool.expand_plan(self.plan(sweep=axes), self.root)

    def test_guided_refs_have_explicit_roles_and_no_noop_controls(self):
        plan = self.plan(task="guided_inpaint")
        plan["base"].update(control_ref="source.png", control_type="canny",
                            appearance_ref="edited.png")
        plan["sweep"] = {"control_strength": [0.5, 1], "appearance_weight": [0.3, 0.8]}
        _, runs, _ = tool.expand_plan(plan, self.root)
        self.assertEqual(4, len(runs))
        del plan["base"]["control_type"]
        with self.assertRaisesRegex(ValueError, "control_type"):
            tool.expand_plan(plan, self.root)

    def test_character_action_plan_and_cli_support_match(self):
        plan = {"task": "character_action", "base": {"prompt": "wave", "seed": 42,
                "character_ref": "source.png", "pose_ref": "edited.png", "control_type": "pose"},
                "sweep": {"ip_weight": [0.6, 0.8]}}
        task, runs, preserve = tool.expand_plan(plan, self.root)
        self.assertFalse(preserve)
        command = tool.generation_command(json.loads(self.config_file().read_text()), self.root / "config.json",
                                           task, runs[0], self.root / "out", 240)
        self.assertIn("--character-ref", command)
        self.assertIn("--pose-ref", command)
        self.assertNotIn("--appearance-ref", command)

    def test_dry_run_does_not_contact_server_or_launch_process(self):
        with patch.object(tool, "check_runtime") as runtime, patch.object(tool.subprocess, "run") as process:
            report = tool.sweep(self.write_plan(), self.config_file(), self.root / "dry", dry_run=True)
        runtime.assert_not_called()
        process.assert_not_called()
        self.assertEqual("planned", report["status"])
        self.assertEqual(2, len(report["runs"]))

    def test_runtime_gate_rejects_unavailable_and_unsupported_even_with_override(self):
        config = json.loads(self.config_file().read_text())
        (self.root / "generate.py").write_text("# fixture")
        (self.root / "tools").mkdir()
        caps = self.root / "tools/image_capabilities.json"
        for state in ({"available": False, "validation": "verified"},
                      {"available": True, "validation": "unsupported"}):
            caps.write_text(json.dumps({"default_profile": "test", "profiles": {
                "test": {"tasks": {"inpaint": state}}}}))
            with patch.object(tool.urllib.request, "urlopen") as request:
                with self.assertRaises(ValueError):
                    tool.check_runtime(config, "inpaint", allow_unverified=True)
            request.assert_not_called()

    def fake_generate(self, command, **kwargs):
        folder = Path(command[command.index("--output-dir") + 1])
        output = folder / "generated.png"
        Image.new("RGBA", (3, 1), (100, 110, 120, 255)).save(output)
        (folder / "generation.json").write_text(json.dumps({"outputs": [tool.file_record(output)]}))
        return subprocess.CompletedProcess(command, 0, "success", "")

    def test_successful_sweep_keeps_raw_and_preserved_outputs_and_trace(self):
        with patch.object(tool, "check_runtime", return_value={"profile": "test"}), \
             patch.object(tool.subprocess, "run", side_effect=self.fake_generate) as process:
            report = tool.sweep(self.write_plan(), self.config_file(), self.root / "sweep")
        self.assertEqual(2, process.call_count)
        self.assertEqual("complete", report["status"])
        for run in report["runs"]:
            self.assertEqual("candidate", run["status"])
            self.assertEqual(1, run["raw_regions"]["preserved"]["changed_pixels"])
            self.assertEqual(0, run["final_regions"]["preserved"]["changed_pixels"])
            self.assertIn("--profile", run["argv"])
        self.assertTrue((self.root / "sweep/candidates.png").exists())

    def test_generation_failure_stops_and_preserves_logs_and_failed_manifest(self):
        failure = subprocess.CompletedProcess([], 1, "partial output", "missing model")
        with patch.object(tool, "check_runtime", return_value={"profile": "test"}), \
             patch.object(tool.subprocess, "run", return_value=failure) as process:
            with self.assertRaisesRegex(RuntimeError, "inspect logs/queue"):
                tool.sweep(self.write_plan(), self.config_file(), self.root / "failed")
        self.assertEqual(1, process.call_count)
        report = json.loads((self.root / "failed/sweep.json").read_text())
        self.assertEqual("failed", report["status"])
        self.assertEqual("failed", report["runs"][0]["status"])
        self.assertEqual("missing model", (self.root / "failed/run_01/stderr.log").read_text())

    def test_changed_input_stops_before_next_generation(self):
        def mutate(command, **kwargs):
            result = self.fake_generate(command, **kwargs)
            Image.new("RGBA", (3, 1), "red").save(self.source)
            return result
        with patch.object(tool, "check_runtime", return_value={"profile": "test"}), \
             patch.object(tool.subprocess, "run", side_effect=mutate) as process:
            with self.assertRaisesRegex(ValueError, "Input changed"):
                tool.sweep(self.write_plan(), self.config_file(), self.root / "mutated")
        self.assertEqual(1, process.call_count)


if __name__ == "__main__":
    unittest.main()
