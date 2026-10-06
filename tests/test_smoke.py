import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools_src"))
import smoke  # noqa: E402
import deploy_manifest  # noqa: E402

try:
    import PIL  # noqa: F401
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

DEVICE = {"platform_key": "macos-mps", "backend": "mps", "usable_memory_mb": 48000,
          "precision_support": ["fp16"], "tier": "sdxl_high"}
ALL_TASKS = ("concept", "icon_asset", "refine", "upscale", "pose_only", "style_lock", "character_action",
             "inpaint", "guided_inpaint", "layer_split")


def caps(missing=None):
    tasks = {t: {"available": True, "missing_files": [], "missing_nodes": []} for t in ALL_TASKS}
    for t, files in (missing or {}).items():
        tasks[t] = {"available": False, "missing_files": files, "missing_nodes": []}
    return {"default_profile": "sdxl_standard", "profiles": {"sdxl_standard": {"tasks": tasks}}}


def env(**kw):
    base = {"device": DEVICE, "capabilities": caps(), "profile_id": "sdxl_standard",
            "comfyui_path": None, "model_roots": []}
    base.update(kw)
    return base


def fake_runner_factory(fail=(), calls=None, stderr_for=None):
    def runner(cmd, timeout, cwd):
        result = Path(cmd[cmd.index("--result-json") + 1])
        task_id = result.name[:-len(".result.json")]
        if calls is not None:
            calls.append((task_id, cmd))
        if task_id in fail:
            return 1, "", (stderr_for or "boom\nRuntimeError: oops"), False
        out_dir = Path(cmd[cmd.index("--output-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        png = out_dir / f"{task_id}.png"
        if HAVE_PIL:
            from PIL import Image
            Image.new("RGB", (16, 16), (200, 10, 10)).save(png)
        else:
            png.write_bytes(b"png")
        seed = cmd[cmd.index("--seed") + 1] if "--seed" in cmd else None
        manifest = {"kind": "image_generation_result", "profile_id": "sdxl_standard", "profile_sha256": "x",
                    "resolved_seeds": {"3": {"seed": int(seed)}} if seed else {},
                    "technical_validation": {"status": "pass"},
                    "outputs": [{"path": str(png), "sha256": "ab" * 32, "mode": "RGB", "width": 16, "height": 16}]}
        result.write_text(json.dumps(manifest), encoding="utf-8")
        return 0, "[完成] x", "", False
    return runner


class SuiteTests(unittest.TestCase):
    def test_suite_parses_and_is_fixed(self):
        suite = smoke.load_suite("image-core")
        self.assertEqual(len(suite["_sha256"]), 64)
        ids = [t["id"] for t in suite["tasks"]]
        self.assertEqual(ids[0], "concept")
        self.assertEqual(len(ids), len(set(ids)))
        seeds = []
        for t in suite["tasks"]:
            self.assertIn("seed", t)
            if t["task"] != "layer_split":
                self.assertIsInstance(t["seed"], int)
            if t["seed"] is not None:
                seeds.append(t["seed"])
        self.assertEqual(len(seeds), len(set(seeds)))

    def test_suite_args_are_valid_generate_cli(self):
        from comfyui_pipeline import cli
        suite = smoke.load_suite("image-core")
        outputs = {t["id"]: "/x/in.png" for t in suite["tasks"]}
        for entry in suite["tasks"]:
            cmd = smoke.build_command(entry, "/x/out", outputs, "/x/mask.png", python="py")
            args = cli.build_parser().parse_args(cmd[2:])
            try:
                cli.validate_cli_args(args)
            except SystemExit as exc:
                self.fail(f"{entry['id']}: {exc}")
            if entry["seed"] is not None:
                self.assertEqual(args.seed, entry["seed"])
            self.assertTrue(args.result_json.endswith(f"{entry['id']}.result.json"))

    def test_select_tasks_adds_dependencies(self):
        suite = smoke.load_suite("image-core")
        entries, auto = smoke.select_tasks(suite, ["inpaint"])
        self.assertEqual([e["id"] for e in entries], ["concept", "inpaint"])
        self.assertEqual(auto, {"concept"})
        with self.assertRaises(smoke.SmokeError):
            smoke.select_tasks(suite, ["nope"])

    def test_deploy_manifest_includes_smoke(self):
        labels = {e.label for e in deploy_manifest.deploy_manifest(ROOT)}
        self.assertIn("smoke.py", labels)
        self.assertIn("comfyui_pipeline/smoke_suites/image-core.json", labels)


class PlanTests(unittest.TestCase):
    def test_not_installed_from_capabilities(self):
        status, reason, _ = smoke.plan_task(
            {"task": "upscale"}, env(capabilities=caps(missing={"upscale": ["RealESRGAN.pth"]})))
        self.assertEqual(status, smoke.NOT_INSTALLED)
        self.assertIn("未安裝(使用者未選用)", reason)
        self.assertIn("RealESRGAN.pth", reason)

    def test_profile_without_task_is_skipped(self):
        self.assertEqual(smoke.plan_task({"task": "flux2_concept"}, env())[0], smoke.SKIPPED)

    def test_ineligible_platform_is_skipped(self):
        status, _, _ = smoke.plan_task(
            {"task": "concept"}, env(device=dict(DEVICE, backend="cpu", usable_memory_mb=0)))
        self.assertEqual(status, smoke.SKIPPED)

    def test_no_profile_is_skipped(self):
        self.assertEqual(smoke.plan_task({"task": "concept"}, env(profile_id=None))[0], smoke.SKIPPED)

    def test_runnable(self):
        self.assertIsNone(smoke.plan_task({"task": "concept"}, env())[0])


class RunTests(unittest.TestCase):
    def run_suite(self, environment, wanted=None, **kw):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        suite = smoke.load_suite("image-core")
        report = smoke.run_suite(suite, environment, tmp.name, wanted, log=lambda m: None, **kw)
        return report, Path(tmp.name)

    @staticmethod
    def by_id(report):
        return {t["id"]: t for t in report["tasks"]}

    def test_all_pass_report_schema(self):
        calls = []
        report, out = self.run_suite(env(), runner=fake_runner_factory(calls=calls))
        self.assertEqual(report["kind"], "smoke_report")
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(report["technical_only"])
        self.assertEqual(report["content_review"], "not_performed")
        self.assertEqual(report["summary"]["overall"], "pass")
        self.assertEqual(report["platform_key"], "macos-mps")
        self.assertEqual(report["profile_id"], "sdxl_standard")
        self.assertEqual(len(report["profile_sha256"]), 64)
        self.assertEqual(len(report["suite"]["sha256"]), 64)
        for key in ("started", "finished", "device", "fingerprint"):
            self.assertIn(key, report)
        tasks = self.by_id(report)
        self.assertTrue(all(t["status"] == "pass" for t in tasks.values()))
        called = dict(calls)
        for entry in smoke.load_suite("image-core")["tasks"]:
            cmd = called[entry["id"]]
            if entry["seed"] is None:
                self.assertNotIn("--seed", cmd)
            else:
                self.assertEqual(cmd[cmd.index("--seed") + 1], str(entry["seed"]))
        self.assertIn(tasks["concept"]["outputs"][0]["abs_path"], called["refine"])
        self.assertEqual(tasks["concept"]["seeds_resolved"], {"3": {"seed": 1001}})
        data = json.loads(smoke.write_report(out, report).read_text(encoding="utf-8"))
        self.assertNotIn("abs_path", data["tasks"][0]["outputs"][0])
        self.assertEqual(data["tasks"][0]["outputs"][0]["sha256"], "ab" * 32)
        self.assertTrue((out / "logs" / "concept.log").is_file())

    def test_not_installed_does_not_fail_suite(self):
        environment = env(capabilities=caps(missing={"upscale": ["x.pth"], "style_lock": ["ip.bin"]}))
        report, _ = self.run_suite(environment, runner=fake_runner_factory())
        tasks = self.by_id(report)
        self.assertEqual(tasks["upscale"]["status"], "not_installed")
        self.assertEqual(tasks["style_lock"]["status"], "not_installed")
        self.assertEqual(report["summary"]["overall"], "pass")
        self.assertEqual(report["summary"]["counts"]["fail"], 0)
        self.assertEqual(report["summary"]["counts"]["not_installed"], 2)

    def test_available_task_error_is_fail(self):
        report, _ = self.run_suite(env(), runner=fake_runner_factory(fail={"refine"}))
        self.assertEqual(self.by_id(report)["refine"]["status"], "fail")
        self.assertEqual(report["summary"]["overall"], "fail")

    def test_upstream_not_installed_skips_dependents(self):
        environment = env(capabilities=caps(missing={"concept": ["ckpt"]}))
        report, _ = self.run_suite(environment, ["inpaint"], runner=fake_runner_factory())
        tasks = self.by_id(report)
        self.assertEqual(tasks["concept"]["status"], "not_installed")
        self.assertEqual(tasks["inpaint"]["status"], "skipped")
        self.assertTrue(tasks["concept"]["dependency_only"])
        self.assertEqual(report["summary"]["overall"], "no_runnable_tasks")

    def test_preflight_missing_without_snapshot_is_not_installed(self):
        msg = "ComfyUI 缺少 concept 需要的內容，已在上傳/排隊前停止；缺少模型檔: a.pth"
        report, _ = self.run_suite(env(capabilities=None), ["concept"],
                                   runner=fake_runner_factory(fail={"concept"}, stderr_for=msg))
        self.assertEqual(self.by_id(report)["concept"]["status"], "not_installed")
        self.assertEqual(report["summary"]["overall"], "no_runnable_tasks")

    @unittest.skipUnless(HAVE_PIL, "needs Pillow")
    def test_mask_and_contact_sheet(self):
        report, out = self.run_suite(env(capabilities=caps(missing={"upscale": ["x"]})),
                                     runner=fake_runner_factory())
        from PIL import Image
        with Image.open(out / "smoke-mask.png") as mask:
            self.assertEqual(mask.mode, "RGBA")
            self.assertEqual(mask.getpixel((384, 384))[3], 0)
            self.assertEqual(mask.getpixel((5, 5))[3], 255)
        sheet = smoke.make_contact_sheet(report, out)
        with Image.open(sheet) as img:
            self.assertEqual(img.format, "JPEG")


class RecordTests(unittest.TestCase):
    def test_record_naming_and_no_overwrite(self):
        report = {"started": "2026-10-06T10:00:00+00:00", "platform_key": "macos-mps",
                  "profile_id": "sdxl_standard", "suite": {"id": "image-core"}}
        with tempfile.TemporaryDirectory() as tmp:
            repo, src = Path(tmp) / "repo", Path(tmp) / "run"
            src.mkdir()
            (src / "smoke-report.json").write_text("{}")
            (src / "smoke-contact-sheet.jpg").write_bytes(b"jpg")
            first = smoke.record_report(repo, src / "smoke-report.json", src / "smoke-contact-sheet.jpg", report)
            self.assertEqual(first, [repo / "docs/knowledge/validation/macos-mps/2026-10-06-image-core-sdxl_standard.json"])
            second = smoke.record_report(repo, src / "smoke-report.json", src / "smoke-contact-sheet.jpg",
                                         report, with_images=True)
            self.assertEqual(second[0].name, "2026-10-06-image-core-sdxl_standard-2.json")
            self.assertEqual(second[1].suffix, ".jpg")
            self.assertTrue(second[1].is_file())


if __name__ == "__main__":
    unittest.main()
