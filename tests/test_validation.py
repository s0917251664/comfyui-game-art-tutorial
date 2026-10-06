import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools_src"))
import smoke  # noqa: E402
import validation  # noqa: E402
import doctor  # noqa: E402
from comfyui_pipeline import image_capabilities, profiles  # noqa: E402

PROFILE_SRC = ROOT / "tools_src" / "comfyui_pipeline" / "profiles"
ENV = {"comfyui": {"commit": "c" * 40, "version": "0.34.0"}, "custom_nodes": {"count": 1, "hash": "n1"},
       "models": {"count": 2, "hash": "m1"}}


def make_report(profile, statuses=None, **overrides):
    statuses = statuses or {}
    tasks = [{"id": t, "task": t, "status": statuses.get(t, "pass"), "outputs": []} for t in profile["tasks"]]
    report = {
        "schema_version": 1, "kind": "smoke_report", "started": "2026-10-06T07:55:05+00:00",
        "platform_key": "macos-mps", "device": {"platform_key": "macos-mps", "usable_memory_mb": 18432},
        "fingerprint": ENV, "profile_id": profile["id"], "profile_sha256": profiles.profile_content_sha256(profile),
        "profile_hash_scheme": "content-v1", "suite": {"id": "image-core", "sha256": "s" * 64},
        "summary": {"overall": "pass"}, "tasks": tasks,
    }
    report.update(overrides)
    return report


class RepoCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        dest = self.repo / validation.PROFILES_SUBDIR
        dest.mkdir(parents=True)
        shutil.copy(PROFILE_SRC / "sdxl_standard.json", dest)
        self.profile = json.loads((dest / "sdxl_standard.json").read_text(encoding="utf-8"))

    def write_report(self, report, name="2026-10-06-image-core-sdxl_standard.json", inside=True):
        base = self.repo / (validation.VALIDATION_SUBDIR / "macos-mps" if inside else Path("elsewhere"))
        base.mkdir(parents=True, exist_ok=True)
        path = base / name
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        return path

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = validation.main(["--repo-root", str(self.repo), *argv])
        return code, out.getvalue(), err.getvalue()

    def profile_text(self):
        return (self.repo / validation.PROFILES_SUBDIR / "sdxl_standard.json").read_text(encoding="utf-8")


class ProposeTests(RepoCase):
    def test_propose_lists_tasks_and_writes_nothing(self):
        path = self.write_report(make_report(self.profile))
        before = self.profile_text()
        code, out, _ = self.run_cli("propose", str(path))
        self.assertEqual(0, code)
        self.assertIn("可升格為 verified 的 task(10)", out)
        self.assertEqual(before, self.profile_text())

    def test_not_installed_and_skipped_are_neutral(self):
        report = make_report(self.profile, {"upscale": "not_installed", "refine": "skipped"})
        path = self.write_report(report)
        code, out, _ = self.run_cli("propose", str(path))
        self.assertEqual(0, code)
        self.assertIn("未列入(沒有此次證據): refine, upscale", out)
        self.assertNotIn("missing", out.lower())
        for bad in ("失敗", "錯誤", "FAIL", "缺少"):
            self.assertNotIn(bad, out)
        plan = validation.build_plan(self.repo, str(path))
        self.assertNotIn("upscale", plan["promote"])
        self.assertNotIn("refine", plan["promote"])

    def test_failed_task_is_not_promoted(self):
        plan = validation.build_plan(self.repo, str(self.write_report(make_report(self.profile, {"concept": "fail"}))))
        self.assertNotIn("concept", plan["promote"])
        self.assertTrue(any("concept" in n for n in plan["notes"]))

    def test_report_outside_validation_dir_is_refused(self):
        path = self.write_report(make_report(self.profile), inside=False)
        code, _, err = self.run_cli("propose", str(path))
        self.assertEqual(2, code)
        self.assertIn("smoke record", err)

    def test_profile_sha_mismatch_blocks(self):
        path = self.write_report(make_report(self.profile, profile_sha256="0" * 64))
        code, out, _ = self.run_cli("propose", str(path))
        self.assertEqual(1, code)
        self.assertIn("不一致", out)

    def test_old_format_report_without_scheme_is_refused(self):
        report = make_report(self.profile)
        report.pop("profile_hash_scheme")
        path = self.write_report(report)
        code, out, _ = self.run_cli("propose", str(path))
        self.assertEqual(1, code)
        self.assertIn("舊格式報告(無 profile_hash_scheme),請用目前版本重跑 smoke 產生新報告", out)
        before = self.profile_text()
        code, _, err = self.run_cli("approve", str(path), "--by", "steve")
        self.assertEqual(2, code)
        self.assertIn("舊格式報告", err)
        self.assertEqual(before, self.profile_text())

    def test_zero_passing_tasks_is_not_approvable(self):
        report = make_report(self.profile, {t: "not_installed" for t in self.profile["tasks"]})
        plan = validation.build_plan(self.repo, str(self.write_report(report)))
        self.assertTrue(any("沒有可升格" in r for r in validation.refusal_reasons(plan)))


class ApproveTests(RepoCase):
    def test_approve_appends_evidence_and_keeps_rest_of_profile(self):
        path = self.write_report(make_report(self.profile))
        before_no_validation = {k: v for k, v in self.profile.items() if k != "validation"}
        code, out, err = self.run_cli("approve", str(path), "--by", "steve")
        self.assertEqual(0, code, err)
        updated = json.loads(self.profile_text())
        self.assertEqual(before_no_validation, {k: v for k, v in updated.items() if k != "validation"})
        entries = updated["validation"]["macos-mps"]
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual("steve", entry["approved_by"])
        self.assertEqual(validation.sha256_file(path), entry["report_sha256"])
        self.assertEqual(profiles.profile_content_sha256(self.profile), entry["profile_sha256"])
        self.assertEqual({"comfyui_version": "0.34.0", "comfyui_commit": "c" * 40,
                          "models_hash": "m1", "custom_nodes_hash": "n1"}, entry["env"])
        self.assertEqual(18432, entry["min_memory_mb"])
        self.assertEqual(self.profile["validation"]["windows-cuda"], updated["validation"]["windows-cuda"])
        # 核准後,新證據綁定的設定檔雜湊仍然有效(證據不會讓自己失效)
        self.assertEqual(entry["profile_sha256"], profiles.profile_content_sha256(updated))
        status, _ = profiles.effective_validation(updated, "macos-mps", 18432, "concept", profiles.env_from_components(ENV))
        self.assertEqual("verified", status)

    def test_approve_requires_by(self):
        path = self.write_report(make_report(self.profile))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            validation.main(["--repo-root", str(self.repo), "approve", str(path)])
        code, _, err = self.run_cli("approve", str(path), "--by", "  ")
        self.assertEqual(2, code)
        self.assertIn("--by", err)
        self.assertNotIn("macos-mps", json.loads(self.profile_text())["validation"])

    def test_refusals_leave_profile_unchanged(self):
        before = self.profile_text()
        cases = {
            "outside": self.write_report(make_report(self.profile), inside=False),
            "sha": self.write_report(make_report(self.profile, profile_sha256="0" * 64), name="b.json"),
            "zero": self.write_report(
                make_report(self.profile, {t: "skipped" for t in self.profile["tasks"]}), name="c.json"),
        }
        for label, path in cases.items():
            with self.subTest(label):
                code, _, err = self.run_cli("approve", str(path), "--by", "steve")
                self.assertEqual(2, code)
                self.assertTrue(err)
                self.assertEqual(before, self.profile_text())

    def test_same_report_cannot_be_approved_twice(self):
        path = self.write_report(make_report(self.profile))
        self.assertEqual(0, self.run_cli("approve", str(path), "--by", "steve")[0])
        code, _, err = self.run_cli("approve", str(path), "--by", "steve")
        self.assertEqual(2, code)
        self.assertIn("已核准", err)

    def test_status_shows_legacy_and_evidence(self):
        path = self.write_report(make_report(self.profile))
        self.run_cli("approve", str(path), "--by", "steve")
        code, out, _ = self.run_cli("status", "--profile", "sdxl_standard")
        self.assertEqual(0, code)
        self.assertIn("legacy", out)
        self.assertIn("verified", out)
        self.assertIn(str(path.relative_to(self.repo).as_posix()), out)
        code, out, _ = self.run_cli("status", "--profile", "sdxl_standard", "--platform", "linux-cuda")
        self.assertIn("unverified", out)


class OtherEnvReminderTests(unittest.TestCase):
    def _profile(self):
        profile = copy.deepcopy(profiles.load_profile("sdxl_standard"))
        profile["validation"]["macos-mps"] = [{
            "report": "docs/knowledge/validation/macos-mps/r.json", "report_sha256": "a" * 64, "tasks": ["concept"],
            "profile_sha256": profiles.profile_content_sha256(profile),
            "env": {"comfyui_version": "0.34.0", "comfyui_commit": "c" * 40, "models_hash": "m1", "custom_nodes_hash": "n1"},
            "min_memory_mb": 18000, "approved_by": "u", "approved_at": "2026-10-06T10:00:00+00:00"}]
        return profile

    def _resolve(self, profile, env_components):
        device = {"platform_key": "macos-mps", "backend": "mps", "usable_memory_mb": 18432,
                  "precision_support": ["fp16"]}
        stderr = io.StringIO()
        with mock.patch.dict(profiles._cache, {"sdxl_standard": profile}), \
                mock.patch("comfyui_pipeline.fingerprint.compute_components", return_value=env_components), \
                contextlib.redirect_stderr(stderr):
            image_capabilities.resolve_image_profile(
                "concept", device, cli_profile="sdxl_standard",
                capabilities={"comfyui_path": "/x", "model_roots": ["/x/models"]})
        return stderr.getvalue()

    def test_other_env_reminder_names_the_difference_not_plain_unverified(self):
        text = self._resolve(self._profile(), dict(ENV, comfyui={"commit": "c" * 40, "version": "0.35.0"}))
        self.assertIn("已在 2026-10-06 的環境驗證", text)
        self.assertIn("目前環境不同", text)
        self.assertIn("0.34.0→0.35.0", text)
        self.assertNotIn("驗證狀態是 unverified", text)

    def test_matching_environment_is_silent(self):
        self.assertEqual("", self._resolve(self._profile(), ENV))

    def test_uncovered_task_keeps_plain_unverified_reminder(self):
        profile = self._profile()
        profile["validation"]["macos-mps"][0]["tasks"] = ["refine"]
        self.assertIn("驗證狀態是 unverified", self._resolve(profile, ENV))


class DoctorSummaryTests(unittest.TestCase):
    def test_doctor_shows_other_env_and_legacy_note(self):
        snap = {"default_profile": "p", "profiles": {"p": {"eligible": True, "installed": True, "tasks": {
            "concept": {"available": True, "validation": "verified_other_env",
                        "validation_reason": "已在 2026-10-06 的環境驗證;目前環境不同(comfyui 版本 0.34.0→0.35.0)"},
            "refine": {"available": True, "validation": "verified", "validation_basis": "legacy"},
            "upscale": {"available": True, "validation": "verified", "validation_basis": "evidence"},
        }}}}
        summary = doctor.summarize_image(snap)["profiles"]["p"]
        self.assertEqual(["refine"], summary["verified_legacy"])
        self.assertEqual(["concept"], list(summary["verified_other_env"]))
        status = {"comfyui_path": None, "snapshot_dir": "/s", "snapshots": {}, "image": {
            "default_profile": "p", "profiles": {"p": summary}},
            "fingerprint": {"exists": False}, "notes": []}
        text = doctor.format_status(status)
        self.assertIn("目前環境不同", text)
        self.assertIn("無環境紀錄", text)


class SmokeRecordCommandTests(unittest.TestCase):
    def test_record_existing_report_and_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, run = Path(tmp) / "repo", Path(tmp) / "run"
            run.mkdir()
            report = {"kind": "smoke_report", "started": "2026-10-06T10:00:00+00:00", "platform_key": "macos-mps",
                      "profile_id": "sdxl_standard", "suite": {"id": "image-core"}, "contact_sheet": "smoke-contact-sheet.jpg"}
            (run / "smoke-report.json").write_text(json.dumps(report))
            (run / "smoke-contact-sheet.jpg").write_bytes(b"jpg")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(0, smoke.main(["record", str(run / "smoke-report.json"), "--repo-root", str(repo),
                                                "--with-images"]))
            base = repo / "docs/knowledge/validation/macos-mps"
            self.assertTrue((base / "2026-10-06-image-core-sdxl_standard.json").is_file())
            self.assertTrue((base / "2026-10-06-image-core-sdxl_standard.jpg").is_file())
            with contextlib.redirect_stdout(buf):
                self.assertEqual(0, smoke.main(["record", str(run / "smoke-report.json"), "--repo-root", str(repo)]))
            self.assertIn("已記錄", buf.getvalue())
            self.assertEqual(1, len(list(base.glob("*.json"))), "相同報告不重複記錄")

    def test_record_rejects_non_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "x.json"
            bad.write_text("{}")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(2, smoke.main(["record", str(bad), "--repo-root", tmp]))

    def test_explicit_run_form_parses_like_bare_form(self):
        parser = smoke.build_parser()
        with mock.patch.object(smoke, "run_suite", side_effect=RuntimeError("stop")), \
                mock.patch.object(smoke, "resolve_environment", return_value={}), \
                tempfile.TemporaryDirectory() as tmp:
            for argv in (["run", "--output-dir", tmp], ["--output-dir", tmp]):
                with self.assertRaises(RuntimeError):
                    smoke.main(argv)
        self.assertEqual("image-core", parser.parse_args(["--output-dir", "x"]).suite)

    def test_new_report_carries_content_hash_scheme(self):
        suite = smoke.load_suite("image-core")
        report = smoke.build_report(suite, {"profile_id": "sdxl_standard", "device": {}, "comfyui_path": None,
                                            "model_roots": []}, [], "a", "b")
        self.assertEqual("content-v1", report["profile_hash_scheme"])
        self.assertEqual(profiles.profile_content_sha256(profiles.load_profile("sdxl_standard")),
                         report["profile_sha256"])


if __name__ == "__main__":
    unittest.main()
