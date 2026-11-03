"""pose-edit 動作選單：提示句型、seed 規則、dry-run 走真的 runner、對照圖與 result 說明。不連 ComfyUI、不需要 GPU。"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools_src"))

import gameart  # noqa: E402
import pose_edit as P  # noqa: E402


def make_png(path, color=(200, 100, 100), size=(120, 160)):
    from PIL import Image
    Image.new("RGB", size, color).save(path)
    return path


class PromptTests(unittest.TestCase):
    def test_every_action_has_fixed_prefix_suffix_and_checks(self):
        self.assertGreaterEqual(len(P.ACTIONS), 8)
        for action, (label, sentence, checks) in P.ACTIONS.items():
            prompt = P.build_prompt(action)
            self.assertTrue(prompt.startswith("Change only the pose: "), action)
            self.assertTrue(prompt.endswith("Keep the face, hairstyle, accessories, clothes, art style and "
                                            "the plain background unchanged."), action)
            self.assertIn(sentence, prompt)
            self.assertTrue(label and checks, action)

    def test_menu_covers_the_tested_actions(self):
        self.assertEqual({"raise_hand", "walk", "cross_arms", "look_back_wave", "hold_staff", "point",
                          "look_down", "palm_to_camera"}, set(P.ACTIONS))

    def test_palm_to_camera_keeps_stop_gesture_wording(self):
        self.assertIn("like a stop gesture", P.build_prompt("palm_to_camera"))
        self.assertIn("not spread to the sides", P.build_prompt("palm_to_camera"))

    def test_note_goes_before_fixed_suffix(self):
        prompt = P.build_prompt("walk", "She wears a red scarf.")
        self.assertLess(prompt.index("She wears a red scarf."), prompt.index("Keep the face"))

    def test_unknown_action_rejected(self):
        with self.assertRaises(P.PoseEditError):
            P.build_prompt("backflip")


class SeedTests(unittest.TestCase):
    def test_default_three_seeds(self):
        self.assertEqual([7, 21, 99], P.parse_seeds(",".join(str(s) for s in P.DEFAULT_SEEDS)))

    def test_bad_seeds(self):
        for bad in ("", "a,b", "1,1", "-3", "1,2,3,4,5,6,7"):
            with self.assertRaises(P.PoseEditError, msg=bad):
                P.parse_seeds(bad)


class DryRunContractTests(unittest.TestCase):
    """dry-run 走真的 runner（image/flux2/edit），graph 不被包裝層改掉。"""

    def test_dry_run_patches_only_prompt_seed_and_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = make_png(Path(tmp) / "src.png")
            out_dir = Path(tmp) / "out"
            out, err = io.StringIO(), io.StringIO()
            code = P.main(["run", "--action", "raise_hand", "--image", str(image), "--dry-run",
                           "--output-dir", str(out_dir)], out=out, err=err)
            self.assertEqual(0, code, err.getvalue())
            result = json.loads((out_dir / P.RESULT_FILE).read_text(encoding="utf-8"))
            self.assertEqual("dry-run", result["mode"])
            self.assertEqual(P.TEMPLATE_ID, result["template"])
            self.assertEqual([7, 21, 99], result["seeds"])
            for seed in result["seeds"]:
                graph = json.loads((out_dir / f"seed_{seed}" / "workflow_api.dryrun.json").read_text(encoding="utf-8"))
                base = json.loads((ROOT / "templates/image/flux2/edit/graph.api.json").read_text(encoding="utf-8"))
                self.assertEqual(set(base), set(graph))
                changed = {nid for nid in base if base[nid] != graph[nid]}
                self.assertTrue(changed <= {"4", "7", "13", "19"}, changed)
                self.assertEqual(result["prompt"], graph["7"]["inputs"]["text"])
                self.assertEqual(seed, graph["13"]["inputs"]["noise_seed"])

    def test_missing_image_is_error(self):
        err = io.StringIO()
        code = P.main(["run", "--action", "walk", "--image", "does-not-exist.png", "--dry-run"],
                      out=io.StringIO(), err=err)
        self.assertEqual(2, code)

    def test_output_dir_must_be_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = make_png(Path(tmp) / "src.png")
            (Path(tmp) / "out").mkdir()
            (Path(tmp) / "out" / "x").write_text("x")
            err = io.StringIO()
            code = P.main(["run", "--action", "walk", "--image", str(image), "--dry-run",
                           "--output-dir", str(Path(tmp) / "out")], out=io.StringIO(), err=err)
            self.assertEqual(2, code)


class FakeRunnerTests(unittest.TestCase):
    """假 runner 寫 run.result.json 與輸出圖，檢查對照圖與 result 說明。"""

    @staticmethod
    def fake_runner(tmp, fail_seeds=()):
        def runner(argv, out=None, err=None):
            seed = int(next(a for a in argv if a.startswith("seed=")).split("=", 1)[1])
            seed_dir = Path(argv[argv.index("--output-dir") + 1])
            (seed_dir / "outputs" / "image").mkdir(parents=True)
            if seed in fail_seeds:
                (seed_dir / "run.result.json").write_text(json.dumps({"status": "failed"}), encoding="utf-8")
                return 1
            png = make_png(seed_dir / "outputs" / "image" / "a.png", color=(seed % 255, 80, 160))
            (seed_dir / "run.result.json").write_text(json.dumps({
                "status": "completed", "outputs": [{"kind": "image", "role": "candidate", "path": str(png)}]}),
                encoding="utf-8")
            return 0
        return runner

    def run_cli(self, tmp, fail_seeds=()):
        image = make_png(Path(tmp) / "src.png")
        out_dir = Path(tmp) / "out"
        err = io.StringIO()
        code = P.main(["run", "--action", "palm_to_camera", "--image", str(image), "--output-dir", str(out_dir)],
                      out=io.StringIO(), err=err, runner_main=self.fake_runner(tmp, fail_seeds))
        return code, out_dir, json.loads((out_dir / P.RESULT_FILE).read_text(encoding="utf-8"))

    def test_three_seeds_make_contact_sheet_and_pending_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out_dir, result = self.run_cli(tmp)
            self.assertEqual(0, code)
            self.assertEqual("completed", result["status"])
            self.assertEqual(3, len(result["runs"]))
            self.assertTrue((out_dir / P.SHEET_FILE).is_file())
            from PIL import Image
            with Image.open(out_dir / P.SHEET_FILE) as sheet:
                self.assertEqual(4 * 360, sheet.width)  # 原圖 + 3 seed
            self.assertEqual("pending", result["content_review"])
            self.assertEqual("none", result["acceptance"])
            joined = "\n".join(result["review_checks"])
            for word in ("手", "持物", "髮型", "服裝"):
                self.assertIn(word, joined)
            self.assertIn("不等於美術接受", result["notice"])

    def test_partial_failure_is_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out_dir, result = self.run_cli(tmp, fail_seeds=(21,))
            self.assertEqual(1, code)
            self.assertEqual("partial", result["status"])
            self.assertEqual(["completed", "failed", "completed"], [r["status"] for r in result["runs"]])
            self.assertTrue((out_dir / P.SHEET_FILE).is_file())


class RegistrationTests(unittest.TestCase):
    def test_registered_and_repo_only(self):
        self.assertIn("pose-edit", gameart.TOOLS)
        self.assertIn("pose-edit", gameart.REPO_ONLY)
        self.assertTrue((ROOT / "tools_src" / gameart.TOOLS["pose-edit"][0]).is_file())

    def test_template_slots_still_match_what_the_tool_sets(self):
        data = json.loads((ROOT / "templates/image/flux2/edit/template.json").read_text(encoding="utf-8"))
        self.assertTrue({"prompt", "image", "seed"} <= set(data["slots"]))


if __name__ == "__main__":
    unittest.main()
