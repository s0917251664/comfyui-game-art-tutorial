import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools_src"))
import deploy  # noqa: E402
import deploy_manifest  # noqa: E402
import verify_portable_install as verify  # noqa: E402


class DeployTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        # 迷你 repo:只放 tools_src 的副本,避免動到真的 repo。
        self.repo = self.tmp / "repo"
        shutil.copytree(ROOT / "tools_src", self.repo / "tools_src",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.comfy = self.tmp / "ComfyUI"
        (self.comfy / "tools").mkdir(parents=True)
        (self.comfy / "tools" / "device_config.json").write_text("{}", encoding="utf-8")
        self.config = self.tmp / "local_config.json"
        self.config.write_text(json.dumps({
            "comfyui_path": str(self.comfy), "python_exe": sys.executable,
            "generate_script": str(self.comfy / "tools" / "generate.py"),
            "comfyui_url": "http://127.0.0.1:8188", "output_dir": str(self.tmp)}), encoding="utf-8")

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = deploy.main(["--repo-root", str(self.repo), "--config", str(self.config), *args])
        return code, out.getvalue() + err.getvalue()

    def apply_with(self, verify_results, *args):
        """以假的 verify 結果執行 --yes。"""
        original = deploy.verify.verify_install
        deploy.verify.verify_install = lambda *a, **k: (verify_results, 0, 0)
        try:
            return self.run_main("--yes", *args)
        finally:
            deploy.verify.verify_install = original

    def passing(self):
        return [("info", "x")]

    def test_manifest_shared_with_verify_and_covers_docs(self):
        manifest = deploy_manifest.deploy_manifest(ROOT)
        dsts = {e.dst.as_posix() for e in manifest}
        for required in ("tools/mask_session.py", "tools/mask_refine.py", "tools/simple_mask_tool/core.py",
                         "custom_nodes/comfyui-simple-mask-tool/comfyui_plugin/web/index.html",
                         "tools/comfyui_pipeline/profiles/sdxl_standard.json", "tools/gameart.py",
                         "tools/vfx_alpha_tools.py", "tools/vfx_alpha/__init__.py", "tools/vfx_alpha/pixel.py",
                         "tools/vfx_alpha/mask.py", "tools/vfx_alpha/media.py", "tools/vfx_alpha/qa.py"):
            self.assertIn(required, dsts)
        self.assertFalse(any("vfx_alpha" in e.dst.as_posix() and e.dst.parts[0] == "custom_nodes" for e in manifest))
        # verify 與 deploy 用同一個函式,不另存清單
        self.assertIs(verify.deploy_manifest, deploy_manifest.deploy_manifest)
        self.assertFalse(hasattr(verify, "SYNC_SOURCE_FILES"))
        # 永遠不碰機器快照/generated
        for e in manifest:
            self.assertNotIn(e.dst.name, deploy_manifest.PROTECTED_NAMES)
            self.assertNotEqual("generated", e.dst.parts[0])
        # 清單內每個 repo 來源都存在
        for e in manifest:
            self.assertTrue((ROOT / e.src).is_file(), e.src)

    def test_deployed_by_deploy_passes_verify_sync_checks(self):
        (self.comfy / "custom_nodes" / "comfyui-simple-mask-tool").mkdir(parents=True)
        code, _ = self.run_main("--yes")  # 真的 verify:snapshot 檢查可能 FAIL(與部署無關),但 sync 必須全過
        results, _, _ = verify.verify_install(self.repo, self.config)
        sync_fails = [r for r in results if r[0] == "fail" and r[1].endswith("source sync")
                      and "face-swap-video/custom_nodes" not in r[1] and "video-layers/custom_nodes" not in r[1]]
        self.assertEqual([], sync_fails)

    def test_dry_run_writes_nothing(self):
        code, out = self.run_main()
        self.assertEqual(0, code)
        self.assertIn("dry run", out)
        self.assertFalse((self.comfy / "tools" / "generate.py").exists())
        self.assertFalse((self.comfy / "tools" / ".deploy-backups").exists())

    def test_plan_counts_new_changed_unchanged_stale_and_skip(self):
        self.assertEqual(0, self.apply_with(self.passing())[0])
        (self.comfy / "tools" / "generate.py").write_text("# drift", encoding="utf-8")
        (self.comfy / "tools" / "comfyui_pipeline" / "old_mod.py").write_text("x", encoding="utf-8")
        (self.comfy / "tools" / "comfyui_pipeline" / "__pycache__").mkdir()
        (self.comfy / "tools" / "comfyui_pipeline" / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"1")
        (self.comfy / "tools" / "mask_refine.py").unlink()
        plan = deploy.build_plan(self.repo, self.comfy)
        by = {}
        for i in plan["items"]:
            by.setdefault(i["action"], []).append(i["dst"].as_posix())
        self.assertEqual(["tools/generate.py"], by["changed"])
        self.assertEqual(["tools/mask_refine.py"], by["new"])
        self.assertEqual(["tools/comfyui_pipeline/old_mod.py"], by["remove"])
        self.assertTrue(plan["skipped"])

    def test_absent_custom_nodes_skipped_present_deployed(self):
        plan = deploy.build_plan(self.repo, self.comfy)
        self.assertFalse(any(i["dst"].parts[0] == "custom_nodes" for i in plan["items"]))
        self.assertTrue(plan["skipped"])
        (self.comfy / "custom_nodes" / "comfyui-simple-mask-tool").mkdir(parents=True)
        code, out = self.apply_with(self.passing())
        self.assertEqual(0, code)
        self.assertIn("重啟 ComfyUI", out)
        self.assertTrue((self.comfy / "custom_nodes/comfyui-simple-mask-tool/core.py").is_file())
        self.assertFalse((self.comfy / "custom_nodes/comfyui-face-swap-video").exists())

    def test_apply_stale_removal_backup_and_rollback(self):
        self.apply_with(self.passing())
        gen = self.comfy / "tools" / "generate.py"
        stale = self.comfy / "tools" / "comfyui_pipeline" / "profiles" / "retired.json"
        stale.write_text("{}", encoding="utf-8")
        gen.write_text("# local edit", encoding="utf-8")
        snapshot = self.comfy / "tools" / "device_config.json"
        code, _ = self.apply_with(self.passing())
        self.assertEqual(0, code)
        self.assertFalse(stale.exists())
        self.assertEqual((self.repo / "tools_src/generate.py").read_bytes(), gen.read_bytes())
        self.assertEqual("{}", snapshot.read_text(encoding="utf-8"))
        backups = deploy.list_backups(self.comfy)
        self.assertEqual(2, len(backups))
        latest = self.comfy / deploy.BACKUP_DIRNAME / backups[-1]
        manifest = json.loads((latest / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual({"changed", "remove"}, {a["action"] for a in manifest["actions"]})
        self.assertEqual("# local edit", (latest / "tools/generate.py").read_text(encoding="utf-8"))
        # 沒有 --yes 的 rollback 是 dry run
        code, out = self.run_main("--rollback")
        self.assertIn("dry run", out)
        self.assertFalse(stale.exists())
        code, _ = self.run_main("--rollback", "latest", "--yes")
        self.assertEqual(0, code)
        self.assertTrue(stale.exists())
        self.assertEqual("# local edit", gen.read_text(encoding="utf-8"))

    def test_rollback_deletes_files_the_deploy_created(self):
        self.apply_with(self.passing())
        self.assertTrue((self.comfy / "tools/generate.py").exists())
        code, _ = self.run_main("--rollback", deploy.list_backups(self.comfy)[0], "--yes")
        self.assertEqual(0, code)
        self.assertFalse((self.comfy / "tools/generate.py").exists())
        self.assertTrue((self.comfy / "tools/device_config.json").exists())

    def test_auto_rollback_on_deploy_related_verify_failure(self):
        self.apply_with(self.passing())
        gen = self.comfy / "tools" / "generate.py"
        gen.write_text("# before", encoding="utf-8")
        code, out = self.apply_with([("fail", "generate.py source sync", "boom")])
        self.assertEqual(1, code)
        self.assertIn("自動從備份還原", out)
        self.assertEqual("# before", gen.read_text(encoding="utf-8"))

    def test_unrelated_verify_failure_does_not_roll_back(self):
        code, out = self.apply_with([
            ("fail", "device_config 對照 live detect()", "tier mismatch"),
            ("fail", "face-swap-video/custom_nodes/comfyui-face-swap-video/nodes.py source sync", "部署副本不存在"),
        ])
        self.assertEqual(0, code)
        self.assertIn("與部署無關", out)
        self.assertTrue((self.comfy / "tools/generate.py").exists())

    def test_prune_keeps_last_n(self):
        for i in range(4):
            (self.comfy / "tools" / "generate.py").write_text(f"# {i}", encoding="utf-8")
            self.apply_with(self.passing(), "--keep", "2")
        self.assertEqual(2, len(deploy.list_backups(self.comfy)))
        code, out = self.run_main("--list-backups")
        self.assertEqual(0, code)

    def test_protected_names_refused(self):
        with self.assertRaises(deploy.DeployError):
            deploy._guard(Path("tools/device_config.json"))
        with self.assertRaises(deploy.DeployError):
            deploy._guard(Path("generated/x.png"))


if __name__ == "__main__":
    unittest.main()
