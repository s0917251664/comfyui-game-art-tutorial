"""recipe 載入、dry-run、確認點續跑。不連 ComfyUI、不 queue prompt。"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools_src"))
sys.path.insert(0, str(ROOT / "tests"))

import gameart  # noqa: E402
import test_templates  # noqa: E402
from comfyui_pipeline.runner import recipe as R  # noqa: E402
from comfyui_pipeline.runner import recipe_cli as cli  # noqa: E402
from comfyui_pipeline.runner import template as T  # noqa: E402

RECIPES = ROOT / "templates" / "recipes"
TEMPLATES = ROOT / "templates"
DRAFTS = ("prop-swap", "idle-anchored-action", "fx-alpha-export")
PROMOTION = "轉正要另開變更且要使用者核准"


class Clock:
    def __init__(self):
        self.values = []

    def __call__(self):
        value = f"2026-10-08T00:00:{len(self.values):02d}+00:00"
        self.values.append(value)
        return value


class FakeExecutor:
    """收 template id 與 slots,回傳假的輸出路徑。不 queue。"""

    def __init__(self):
        self.calls = []

    def run_template(self, template_id, slots, step_dir):
        if template_id == "video/sam3/track-mask":
            outputs = {"masks": str(Path(step_dir) / "outputs" / "masks")}
        else:
            outputs = {"raw": str(Path(step_dir) / "outputs" / "raw")}
        self.calls.append({"kind": "template", "template": template_id, "slots": dict(slots), "outputs": outputs})
        return {"command": f"gameart.py run {template_id}", "outputs": outputs}

    def run_local(self, command, args, step_dir):
        outputs = {name: str(Path(step_dir) / name) for name in ("frames", "sheet", "composited")}
        self.calls.append({"kind": "local", "command": command, "args": dict(args), "outputs": outputs})
        return {"command": command, "outputs": outputs}


def run_cli(argv, *, executor=None, clock=None, recipes_root=None, templates_root=None):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(argv), recipes_root=recipes_root, templates_root=templates_root,
                    out=out, err=err, executor=executor, clock=clock)
    return code, out.getvalue(), err.getvalue()


class RecipeSchemaTests(unittest.TestCase):
    def test_schema_fields_match_loader(self):
        schema = json.loads((TEMPLATES / "_schema" / "recipe.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(R.REQUIRED_FIELDS), sorted(schema["required"]))
        self.assertEqual(sorted(R.REQUIRED_FIELDS + R.OPTIONAL_FIELDS), sorted(schema["properties"]))
        self.assertEqual(sorted(R.STATUSES), sorted(schema["properties"]["status"]["enum"]))
        self.assertEqual(sorted(R.INPUT_KEYS), sorted(schema["$defs"]["input"]["properties"]))
        self.assertEqual(sorted(R.INPUT_TYPES), sorted(schema["$defs"]["input"]["properties"]["type"]["enum"]))
        self.assertEqual(sorted(R.SUPPORTS), sorted(schema["$defs"]["support"]["enum"]))
        kinds = [schema["$defs"][name]["properties"]["kind"]["const"]
                 for name in ("templateStep", "confirmStep", "localStep", "noteStep")]
        self.assertEqual(sorted(R.STEP_KINDS), sorted(kinds))
        for key, name in (
            (R.TEMPLATE_STEP_KEYS, "templateStep"),
            (R.CONFIRM_STEP_KEYS, "confirmStep"),
            (R.LOCAL_STEP_KEYS, "localStep"),
            (R.NOTE_STEP_KEYS, "noteStep"),
        ):
            self.assertEqual(sorted(key), sorted(schema["$defs"][name]["properties"]), name)

    def test_recipe_files_stay_lf_and_are_not_templates(self):
        paths = list(RECIPES.rglob("recipe.json"))
        paths.append(TEMPLATES / "_schema" / "recipe.schema.json")
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), path)
            self.assertNotIn(b"\r\n", raw, path)
            self.assertTrue(raw.endswith(b"\n"), path)
            self.assertNotEqual(path.name, "template.json")
        self.assertEqual(test_templates.ALL_IDS, T.discover(TEMPLATES))
        self.assertNotIn("object-mark-inpaint", T.discover(TEMPLATES))


class RecipeCatalogTests(unittest.TestCase):
    def test_list_hides_drafts_until_flag(self):
        code, out, err = run_cli(["list"])
        self.assertEqual(0, code, err)
        self.assertIn("object-mark-inpaint", out)
        for recipe_id in DRAFTS:
            self.assertNotIn(recipe_id, out)
        code, out, err = run_cli(["list", "--draft"])
        self.assertEqual(0, code, err)
        self.assertIn("object-mark-inpaint", out)
        for recipe_id in DRAFTS:
            self.assertIn(recipe_id, out)

    def test_draft_show_and_run_require_flag_and_promotion_is_documented(self):
        readme = (TEMPLATES / "README.md").read_text(encoding="utf-8")
        self.assertIn("python tools_src/gameart.py run list", readme)
        for name in ("recipe list", "recipe show", "recipe run", "recipe resume"):
            self.assertIn(name, readme)
        self.assertIn(PROMOTION, readme)
        self.assertIn("recipe.json", readme)
        for recipe_id in DRAFTS:
            code, out, err = run_cli(["show", recipe_id])
            self.assertEqual(2, code, out)
            self.assertIn("--draft", err)
            code, out, err = run_cli(["run", recipe_id, "--dry-run"])
            self.assertEqual(2, code, out)
            code, out, err = run_cli(["show", recipe_id, "--draft"])
            self.assertEqual(0, code, err)
            self.assertIn(PROMOTION, out)
            self.assertEqual(recipe_id, json.loads((RECIPES / "_drafts" / recipe_id / "recipe.json").read_text(encoding="utf-8"))["id"])
            self.assertEqual("draft", json.loads((RECIPES / "_drafts" / recipe_id / "recipe.json").read_text(encoding="utf-8"))["status"])

    def test_object_mark_dry_run_expands_three_steps(self):
        code, out, err = run_cli(["run", "object-mark-inpaint", "--dry-run"])
        self.assertEqual(0, code, err)
        track = out.index("[0] track")
        review = out.index("[1] review_masks")
        inpaint = out.index("[2] inpaint")
        self.assertLess(track, review)
        self.assertLess(review, inpaint)
        self.assertIn("video/sam3/track-mask", out[track:review])
        self.assertIn("kind=confirm", out[review:inpaint])
        self.assertIn("keyframes/mask_preview.png", out[review:inpaint])
        self.assertIn("video/wan-vace/inpaint", out[inpaint:])
        self.assertIn("{steps.track.outputs.masks}", out[inpaint:])
        self.assertNotIn("等待確認", out)
        self.assertNotIn("queue", out)
        self.assertNotIn(PROMOTION, out)

    def test_prop_swap_show_and_dry_run_stays_described(self):
        code, out, err = run_cli(["show", "prop-swap", "--draft", "--json"])
        self.assertEqual(0, code, err)
        shown = json.loads(out)
        self.assertEqual("prop-swap", shown["recipe"]["id"])
        code, out, err = run_cli(["run", "prop-swap", "--draft", "--dry-run", "--json"])
        self.assertEqual(0, code, err)
        payload = json.loads(out)
        self.assertEqual(["master_still", "prop_paste", "review_master", "pose_drive"],
                         [step["id"] for step in payload["steps"]])
        self.assertEqual(["note", "local", "confirm", "template"], [step["kind"] for step in payload["steps"]])
        pose = payload["steps"][3]
        self.assertEqual("video/h3/pose-drive-canny", pose["template"])
        self.assertEqual("described", pose["resolution"])
        self.assertEqual("{steps.prop_paste.outputs.composited}", pose["slots"]["start_image"])
        self.assertEqual("{inputs.motion_ref}", pose["slots"]["motion_video"])
        self.assertNotIn("image", pose["slots"])
        self.assertNotIn("motion_ref", pose["slots"])
        self.assertFalse(pose["executable"])
        self.assertFalse(pose["calls_comfyui"])
        self.assertTrue(payload["steps"][2]["confirmation_point"])
        self.assertLess(payload["steps"][2]["index"], pose["index"])

    def test_idle_dry_run_confirms_before_h3_and_marks_wan_unsupported(self):
        code, out, err = run_cli(["run", "idle-anchored-action", "--draft", "--dry-run", "--json"])
        self.assertEqual(0, code, err)
        steps = json.loads(out)["steps"]
        self.assertEqual("confirm", steps[0]["kind"])
        self.assertEqual("video/h3/img2video-last", steps[1]["template"])
        self.assertEqual("described", steps[1]["resolution"])
        self.assertEqual("{inputs.idle}", steps[1]["slots"]["start_image"])
        self.assertEqual("{inputs.idle}", steps[1]["slots"]["last_image"])
        self.assertEqual("start_image", steps[1]["frame_anchoring"]["first"])
        self.assertEqual("last_image", steps[1]["frame_anchoring"]["last"])
        self.assertIn("last", steps[1]["text"])
        self.assertLess(steps[0]["index"], steps[1]["index"])
        self.assertEqual("unsupported", steps[2]["resolution"])
        self.assertEqual("video/wan/img2video", steps[2]["template"])
        self.assertFalse(any(step["calls_comfyui"] for step in steps))

    def test_fx_alpha_dry_run_is_local_and_confirms_before_pack(self):
        code, out, err = run_cli(["run", "fx-alpha-export", "--draft", "--dry-run", "--json"])
        self.assertEqual(0, code, err)
        payload = json.loads(out)
        steps = payload["steps"]
        self.assertEqual(["local", "confirm", "local"], [step["kind"] for step in steps])
        self.assertIn("luma-alpha", payload["inputs"]["method"]["enum"])
        self.assertIn("chroma-alpha", payload["inputs"]["method"]["enum"])
        self.assertIn("{inputs.method}", steps[0]["command"])
        self.assertLess(steps[1]["index"], steps[2]["index"])
        self.assertIn("pack", steps[2]["command"])
        self.assertTrue(steps[1]["confirmation_point"])
        self.assertFalse(any(step["calls_comfyui"] for step in steps))
        self.assertNotIn("template", [step["kind"] for step in steps])

    def test_missing_template_stays_unresolved_and_unknown_slot_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            recipes = Path(tmp) / "recipes"
            missing = {
                "schema_version": 1, "id": "missing-template", "version": "0.1.0",
                "title": "尚未登記", "summary": "測試用", "status": "draft",
                "inputs": {"idle": {"type": "path", "required": True}},
                "steps": [{
                    "id": "gen", "kind": "template", "template": "video/missing/not-registered",
                    "executable": False, "support": "planned",
                    "slots": {"image": "{inputs.idle}"},
                }],
            }
            bad = {
                "schema_version": 1, "id": "bad-slot", "version": "0.1.0",
                "title": "slot 對不上", "summary": "測試用", "status": "draft",
                "inputs": {"idle": {"type": "path", "required": True}},
                "steps": [{
                    "id": "gen", "kind": "template", "template": "video/h3/img2video",
                    "executable": False, "support": "planned",
                    "slots": {"image": "{inputs.idle}"},
                }],
            }
            for recipe_id, data in (("missing-template", missing), ("bad-slot", bad)):
                folder = recipes / recipe_id
                folder.mkdir(parents=True)
                (folder / "recipe.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
            code, out, err = run_cli(
                ["run", "missing-template", "--dry-run", "--json"],
                recipes_root=recipes, templates_root=TEMPLATES)
            self.assertEqual(0, code, err)
            step = json.loads(out)["steps"][0]
            self.assertEqual("unresolved", step["resolution"])
            self.assertFalse(step["calls_comfyui"])
            code, out, err = run_cli(
                ["show", "bad-slot"], recipes_root=recipes, templates_root=TEMPLATES)
            self.assertEqual(2, code, out)
            self.assertIn("沒有 slot image", err)


class ConfirmationTests(unittest.TestCase):
    def test_object_mark_stops_until_confirm_then_runs_next_template(self):
        executor, clock = FakeExecutor(), Clock()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "run"
            argv = ["run", "object-mark-inpaint", "--output-dir", str(folder),
                    "--set", "source_video=clip.mp4", "--set", "seed_mask=mask.png",
                    "--set", "prompt=glow", "--set", "mode=replace", "--set", "seed=7"]
            code, out, err = run_cli(argv, executor=executor, clock=clock)
            self.assertEqual(0, code, err)
            self.assertIn("等待確認", out)
            self.assertIn("keyframes/mask_preview.png", out)
            self.assertEqual(1, len(executor.calls))
            first = executor.calls[0]
            self.assertEqual("video/sam3/track-mask", first["template"])
            self.assertEqual("clip.mp4", first["slots"]["source_video"])
            self.assertEqual("mask.png", first["slots"]["seed_mask"])
            state = json.loads((folder / "recipe.state.json").read_text(encoding="utf-8"))
            self.assertEqual(1, state["schema_version"])
            self.assertEqual({"id": "object-mark-inpaint", "version": "0.1.0"}, state["recipe"])
            self.assertEqual(1, state["next_index"])
            self.assertEqual("waiting_confirm", state["status"])
            self.assertEqual("pending", state["content_review"])
            done = state["steps"][0]
            self.assertEqual("video/sam3/track-mask", done["template"])
            self.assertIn("video/sam3/track-mask", done["command"])
            self.assertEqual(clock.values[0], done["started_at"])
            self.assertEqual(clock.values[1], done["finished_at"])
            self.assertEqual("pending", done["content_review"])
            self.assertEqual(first["outputs"]["masks"], done["outputs"]["masks"])
            self.assertFalse(state["confirmations"][0]["confirmed"])
            self.assertEqual("pending", state["confirmations"][0]["content_review"])
            self.assertNotIn("accept", (folder / "recipe.state.json").read_text(encoding="utf-8"))

            code, out, err = run_cli(["resume", str(folder)], executor=executor, clock=clock)
            self.assertEqual(0, code, err)
            self.assertIn("等待確認", out)
            self.assertEqual(1, len(executor.calls))
            state = json.loads((folder / "recipe.state.json").read_text(encoding="utf-8"))
            self.assertEqual(1, state["next_index"])
            self.assertFalse(state["confirmations"][0]["confirmed"])

            code, out, err = run_cli(["resume", str(folder), "--confirm"], executor=executor, clock=clock)
            self.assertEqual(0, code, err)
            self.assertEqual(2, len(executor.calls))
            second = executor.calls[1]
            self.assertEqual("video/wan-vace/inpaint", second["template"])
            self.assertEqual(first["outputs"]["masks"], second["slots"]["masks"])
            self.assertEqual("glow", second["slots"]["prompt"])
            self.assertEqual("replace", second["slots"]["mode"])
            self.assertEqual(7, second["slots"]["seed"])
            self.assertNotIn("control_video", second["slots"])
            self.assertNotIn("output_prefix", second["slots"])
            state = json.loads((folder / "recipe.state.json").read_text(encoding="utf-8"))
            self.assertEqual(3, state["next_index"])
            self.assertEqual("completed", state["status"])
            self.assertTrue(state["confirmations"][0]["confirmed"])
            self.assertEqual(clock.values[2], state["confirmations"][0]["at"])
            self.assertEqual("pending", state["confirmations"][0]["content_review"])
            self.assertEqual("pending", state["content_review"])
            self.assertEqual("video/wan-vace/inpaint", state["steps"][1]["template"])
            self.assertEqual(clock.values[3], state["steps"][1]["started_at"])
            self.assertEqual(clock.values[4], state["steps"][1]["finished_at"])
            self.assertNotIn("accept", (folder / "recipe.state.json").read_text(encoding="utf-8"))

    def test_tampered_index_still_cannot_pass_confirm_without_flag(self):
        executor, clock = FakeExecutor(), Clock()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "run"
            code, out, err = run_cli(
                ["run", "object-mark-inpaint", "--output-dir", str(folder),
                 "--set", "source_video=clip.mp4", "--set", "seed_mask=mask.png", "--set", "prompt=glow"],
                executor=executor, clock=clock)
            self.assertEqual(0, code, err)
            path = folder / "recipe.state.json"
            state = json.loads(path.read_text(encoding="utf-8"))
            state["next_index"] = 2
            state["content_review"] = "accept"
            path.write_text(json.dumps(state), encoding="utf-8")
            code, out, err = run_cli(["resume", str(folder)], executor=executor, clock=clock)
            self.assertEqual(0, code, err)
            self.assertIn("等待確認", out)
            self.assertEqual(1, len(executor.calls))
            saved = path.read_text(encoding="utf-8")
            self.assertNotIn("accept", saved)
            self.assertEqual(1, json.loads(saved)["next_index"])

    def test_offline_template_stops_before_confirm_without_queueing(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "run"
            code, out, err = run_cli(
                ["run", "object-mark-inpaint", "--output-dir", str(folder),
                 "--set", "source_video=clip.mp4", "--set", "seed_mask=mask.png", "--set", "prompt=glow"])
            self.assertEqual(0, code, err)
            self.assertNotIn("等待確認", out)
            self.assertIn("沒有送出", out)
            self.assertIn("沒有 queue", out)
            state = json.loads((folder / "recipe.state.json").read_text(encoding="utf-8"))
            self.assertEqual(0, state["next_index"])
            self.assertEqual("blocked", state["status"])
            self.assertEqual([], state["steps"])
            self.assertEqual([], state["confirmations"])
            self.assertEqual("pending", state["content_review"])

    def test_first_step_confirm_writes_state_and_resume_waits(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "run"
            code, out, err = run_cli(
                ["run", "idle-anchored-action", "--draft", "--output-dir", str(folder),
                 "--set", "idle=idle.png", "--set", "prompt=return to the same idle"])
            self.assertEqual(0, code, err)
            self.assertIn("等待確認", out)
            state = json.loads((folder / "recipe.state.json").read_text(encoding="utf-8"))
            self.assertEqual(0, state["next_index"])
            self.assertEqual("waiting_confirm", state["status"])
            self.assertEqual([], state["steps"])
            self.assertFalse(state["confirmations"][0]["confirmed"])
            self.assertEqual("pending", state["content_review"])
            code, out, err = run_cli(["resume", str(folder)])
            self.assertEqual(0, code, err)
            self.assertIn("等待確認", out)
            state = json.loads((folder / "recipe.state.json").read_text(encoding="utf-8"))
            self.assertEqual([], state["steps"])
            self.assertFalse(state["confirmations"][0]["confirmed"])
            code, out, err = run_cli(["resume", str(folder), "--confirm"])
            self.assertEqual(0, code, err)
            self.assertNotIn("沒有送出", out)
            state = json.loads((folder / "recipe.state.json").read_text(encoding="utf-8"))
            self.assertEqual("completed", state["status"])
            self.assertTrue(state["confirmations"][0]["confirmed"])
            self.assertEqual("pending", state["confirmations"][0]["content_review"])
            described = {step["id"]: step for step in state["steps"]}
            self.assertEqual("described", described["h3_img2video"]["resolution"])
            self.assertEqual("unsupported", described["wan_img2video"]["resolution"])
            self.assertIsNone(described["h3_img2video"]["command"])
            self.assertEqual("pending", state["content_review"])
            self.assertNotIn("accept", (folder / "recipe.state.json").read_text(encoding="utf-8"))

    def test_second_confirm_is_also_a_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            recipes = Path(tmp) / "recipes"
            data = {
                "schema_version": 1, "id": "two-gates", "version": "0.1.0",
                "title": "兩個確認點", "summary": "測試用", "status": "draft",
                "inputs": {
                    "source_video": {"type": "path", "required": True},
                    "seed_mask": {"type": "path", "required": True},
                },
                "steps": [
                    {"id": "track_a", "kind": "template", "template": "video/sam3/track-mask",
                     "slots": {"source_video": "{inputs.source_video}", "seed_mask": "{inputs.seed_mask}"}},
                    {"id": "check_a", "kind": "confirm", "message": "請看第一段遮罩"},
                    {"id": "track_b", "kind": "template", "template": "video/sam3/track-mask",
                     "slots": {"source_video": "{inputs.source_video}", "seed_mask": "{inputs.seed_mask}"}},
                    {"id": "check_b", "kind": "confirm", "message": "請看第二段遮罩"},
                ],
            }
            folder = recipes / "two-gates"
            folder.mkdir(parents=True)
            (folder / "recipe.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8", newline="\n")
            executor, clock = FakeExecutor(), Clock()
            run = Path(tmp) / "run"
            common = {"recipes_root": recipes, "templates_root": TEMPLATES, "executor": executor, "clock": clock}
            code, out, err = run_cli(
                ["run", "two-gates", "--output-dir", str(run), "--set", "source_video=a.mp4", "--set", "seed_mask=a.png"],
                **common)
            self.assertEqual(0, code, err)
            self.assertEqual(["video/sam3/track-mask"], [call["template"] for call in executor.calls])
            self.assertIn("等待確認", out)
            code, out, err = run_cli(["resume", str(run)], **common)
            self.assertEqual(0, code, err)
            self.assertEqual(1, len(executor.calls))
            code, out, err = run_cli(["resume", str(run), "--confirm"], **common)
            self.assertEqual(0, code, err)
            self.assertIn("等待確認", out)
            self.assertEqual(2, len(executor.calls))
            self.assertEqual("video/sam3/track-mask", executor.calls[1]["template"])
            state = json.loads((run / "recipe.state.json").read_text(encoding="utf-8"))
            self.assertEqual(3, state["next_index"])
            self.assertTrue(state["confirmations"][0]["confirmed"])
            self.assertFalse(state["confirmations"][1]["confirmed"])
            code, out, err = run_cli(["resume", str(run)], **common)
            self.assertEqual(2, len(executor.calls))
            code, out, err = run_cli(["resume", str(run), "--confirm"], **common)
            self.assertEqual(0, code, err)
            self.assertEqual(2, len(executor.calls))
            state = json.loads((run / "recipe.state.json").read_text(encoding="utf-8"))
            self.assertEqual("completed", state["status"])
            self.assertTrue(all(item["confirmed"] for item in state["confirmations"]))
            self.assertTrue(all(item["content_review"] == "pending" for item in state["confirmations"]))

    def test_run_requires_output_dir_and_inputs(self):
        code, out, err = run_cli(["run", "object-mark-inpaint", "--set", "source_video=clip.mp4"])
        self.assertEqual(2, code, out)
        self.assertIn("--output-dir", err)
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_cli(["run", "object-mark-inpaint", "--output-dir", str(Path(tmp) / "run")])
            self.assertEqual(2, code, out)
            self.assertIn("缺少輸入", err)
            self.assertFalse((Path(tmp) / "run").exists())


class DispatcherSurfaceTests(unittest.TestCase):
    def test_old_tools_remain_and_recipe_is_repo_only(self):
        self.assertIn("run", gameart.TOOLS)
        self.assertIn("gen", gameart.TOOLS)
        self.assertIn("vfx", gameart.TOOLS)
        self.assertEqual("run_recipe.py", gameart.TOOLS["recipe"][0])
        self.assertIn("recipe", gameart.REPO_ONLY)
        self.assertTrue((ROOT / "tools_src" / "run_recipe.py").is_file())
        buf = io.StringIO()
        from contextlib import redirect_stdout
        with redirect_stdout(buf):
            self.assertEqual(0, gameart.main(["list"]))
        listed = buf.getvalue()
        for name in ("gen", "run", "recipe", "vfx", "review"):
            self.assertIn(name, listed)

    def test_gameart_recipe_list_subprocess(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools_src" / "gameart.py"), "recipe", "list"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(ROOT))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("object-mark-inpaint", proc.stdout)
        self.assertNotIn("prop-swap", proc.stdout)


if __name__ == "__main__":
    unittest.main()
