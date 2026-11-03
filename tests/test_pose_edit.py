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
        self.assertEqual([7, 21, 99], P.parse_seeds("7,21,99"))
        self.assertEqual((7, 21, 99), P.SEED_POOL[:3])

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


def ns(**kw):
    import argparse
    base = dict(step_tokens=[], keep_extra=None, avoid=None, note=None, seeds=None, count=None, pick=None)
    base.update(kw)
    return argparse.Namespace(**base)


class FreeformTests(unittest.TestCase):
    def test_custom_gets_fixed_prefix_and_suffix(self):
        steps = P.resolve_steps(ns(step_tokens=[("custom", "the character waves with the left hand")]), P.ACTIONS)
        self.assertEqual(1, len(steps))
        prompt = steps[0]["prompt"]
        self.assertTrue(prompt.startswith("Change only the pose: the character waves with the left hand."))
        self.assertTrue(prompt.endswith("unchanged."))

    def test_keep_extra_and_avoid_are_appended_after_fixed_suffix(self):
        steps = P.resolve_steps(ns(step_tokens=[("action", "hold_staff")], keep_extra="the wooden staff",
                                   avoid="a second staff"), P.ACTIONS)
        prompt = steps[0]["prompt"]
        self.assertIn("Also keep the wooden staff exactly as it is.", prompt)
        self.assertIn("Do not add a second staff.", prompt)
        self.assertLess(prompt.index("Keep the face"), prompt.index("Also keep"))

    def test_parts_compose_one_sentence_with_chinese_aliases(self):
        steps = P.resolve_steps(ns(step_tokens=[("part", "右手=舉高"), ("part", "頭=朝左"), ("part", "視線=往下看"),
                                                ("part", "feet=向前跨步")]), P.ACTIONS)
        self.assertEqual(1, len(steps))
        sentence = steps[0]["sentence"]
        for piece in ("the character's right hand raised straight up with an open palm",
                      "the head turned to the left", "the character looks down at the ground",
                      "the feet stepping forward, mid-stride"):
            self.assertIn(piece, sentence)
        self.assertTrue(sentence.endswith("."))

    def test_part_errors(self):
        for tokens in ([("part", "沒有等號")], [("part", "翅膀=展開")], [("part", "頭=")]):
            with self.assertRaises(P.PoseEditError, msg=tokens):
                P.resolve_steps(ns(step_tokens=tokens), P.ACTIONS)

    def test_then_splits_parts_into_steps_and_chain_order_is_kept(self):
        tokens = [("action", "raise_hand,look_down"), ("part", "左手=叉腰"), ("then", True),
                  ("custom", "the character turns around")]
        steps = P.resolve_steps(ns(step_tokens=tokens), P.ACTIONS)
        self.assertEqual(["raise_hand", "look_down", "parts1", "custom1"], [s["id"] for s in steps])

    def test_too_many_steps_and_empty(self):
        with self.assertRaises(P.PoseEditError):
            P.resolve_steps(ns(step_tokens=[("action", "walk,walk,walk,walk,walk")]), P.ACTIONS)
        with self.assertRaises(P.PoseEditError):
            P.resolve_steps(ns(), P.ACTIONS)

    def test_count_seed_pool_and_exclusive_with_seeds(self):
        self.assertEqual([7, 21], P.resolve_seeds(ns(count=2)))
        self.assertEqual([7, 21, 99], P.resolve_seeds(ns()))
        self.assertEqual([5], P.resolve_seeds(ns(seeds="5")))
        with self.assertRaises(P.PoseEditError):
            P.resolve_seeds(ns(count=2, seeds="5"))
        with self.assertRaises(P.PoseEditError):
            P.resolve_seeds(ns(count=9))

    def test_pick_parsing(self):
        self.assertEqual([21], P.parse_picks("21", 2))
        with self.assertRaises(P.PoseEditError):
            P.parse_picks("21,7", 2)


class UserActionsTests(unittest.TestCase):
    def test_save_load_and_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "mine.json"
            out = io.StringIO()
            code = P.main(["save", "--id", "wave_left", "--label", "左手揮手", "--custom",
                           "the character waves with the left hand", "--actions-file", str(file)], out=out)
            self.assertEqual(0, code)
            actions = P.load_user_actions(file)
            self.assertIn("wave_left", actions)
            self.assertEqual("左手揮手", actions["wave_left"][0])
            listing = io.StringIO()
            P.main(["list", "--actions-file", str(file)], out=listing)
            self.assertIn("wave_left", listing.getvalue())
            self.assertIn("自訂", listing.getvalue())
            steps = P.resolve_steps(ns(step_tokens=[("action", "wave_left")]), P.all_actions(file))
            self.assertEqual("user", steps[0]["kind"])
            self.assertIn("waves with the left hand", steps[0]["prompt"])

    def test_cannot_shadow_builtin_or_save_menu_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "mine.json"
            for argv in (["save", "--id", "walk", "--custom", "x"], ["save", "--id", "a b", "--custom", "x"],
                         ["save", "--id", "x", "--action", "walk"]):
                code = P.main(argv + ["--actions-file", str(file)], out=io.StringIO(), err=io.StringIO())
                self.assertEqual(2, code, argv)

    def test_bad_user_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "bad.json"
            file.write_text('{"actions": {"walk": {"sentence": "x"}}}', encoding="utf-8")
            with self.assertRaises(P.PoseEditError):
                P.load_user_actions(file)
            file.write_text("not json", encoding="utf-8")
            with self.assertRaises(P.PoseEditError):
                P.load_user_actions(file)

    def test_local_actions_file_is_gitignored(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(P.USER_ACTIONS_FILE, text)


class ChainTests(FakeRunnerTests):
    """連續編修：上一步輸出當下一步來源；--pick 指定；沒給就用第一張並說明。"""

    def test_two_step_chain_uses_previous_output_as_source(self):
        seen = []
        base = self.fake_runner(None)

        def runner(argv, out=None, err=None):
            seen.append(next(a for a in argv if a.startswith("image=")))
            return base(argv, out=out, err=err)

        with tempfile.TemporaryDirectory() as tmp:
            image = make_png(Path(tmp) / "src.png")
            out_dir = Path(tmp) / "out"
            code = P.main(["run", "--image", str(image), "--action", "raise_hand,look_down", "--seeds", "7,21",
                           "--pick", "21", "--output-dir", str(out_dir)],
                          out=io.StringIO(), err=io.StringIO(), runner_main=runner)
            self.assertEqual(0, code)
            result = json.loads((out_dir / P.RESULT_FILE).read_text(encoding="utf-8"))
            self.assertEqual(2, len(result["steps"]))
            self.assertEqual(21, result["steps"][0]["picked_seed"])
            self.assertEqual("user", result["steps"][0]["pick_reason"])
            first_out = result["steps"][0]["runs"][1]["output"]
            self.assertEqual(f"image={first_out}", seen[2])
            self.assertTrue((out_dir / "step_1_raise_hand" / P.SHEET_FILE).is_file())
            self.assertTrue((out_dir / "step_2_look_down" / P.SHEET_FILE).is_file())
            self.assertIn("連續編修", "\n".join(result["review_checks"]))

    def test_chain_without_pick_auto_uses_first_and_says_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = make_png(Path(tmp) / "src.png")
            out_dir = Path(tmp) / "out"
            P.main(["run", "--image", str(image), "--action", "walk", "--action", "point",
                    "--output-dir", str(out_dir)], out=io.StringIO(), err=io.StringIO(),
                   runner_main=self.fake_runner(tmp))
            result = json.loads((out_dir / P.RESULT_FILE).read_text(encoding="utf-8"))
            self.assertEqual(7, result["steps"][0]["picked_seed"])
            self.assertIn("不是接受", result["steps"][0]["pick_reason"])
            self.assertTrue(result["chain_notes"])
            self.assertEqual("pending", result["content_review"])

    def test_pick_of_failed_seed_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = make_png(Path(tmp) / "src.png")
            code = P.main(["run", "--image", str(image), "--action", "walk,point", "--pick", "21",
                           "--output-dir", str(Path(tmp) / "out")], out=io.StringIO(), err=io.StringIO(),
                          runner_main=self.fake_runner(tmp, fail_seeds=(21,)))
            self.assertEqual(2, code)

    def test_dry_run_prints_full_prompt_for_every_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = make_png(Path(tmp) / "src.png")
            out = io.StringIO()
            code = P.main(["run", "--image", str(image), "--action", "raise_hand", "--custom",
                           "the character looks to the right", "--dry-run", "--count", "1",
                           "--output-dir", str(Path(tmp) / "out")], out=out, err=io.StringIO())
            self.assertEqual(0, code)
            text = out.getvalue()
            self.assertIn("步驟 1 提示：Change only the pose: the character raises the right arm", text)
            self.assertIn("步驟 2 提示：Change only the pose: the character looks to the right.", text)
            self.assertEqual(2, text.count("Keep the face, hairstyle"))


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
