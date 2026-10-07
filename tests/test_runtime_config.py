"""設定檔與快照路徑解析(runtime_config)和 smoke 的接線。

對應 Windows 實測:從 repo 根目錄給相對 --config,smoke 子程序 cwd 是 tools/ 而找不到設定檔;
從 repo 的 tools_src 執行時讀不到 <ComfyUI>/tools 的快照(0 pass/2 fail/8 skip)。
Windows 路徑用 ntpath 模擬,任何平台都能跑。
"""
import io
import json
import ntpath
import os
import posixpath
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools_src"))
from comfyui_pipeline import client  # noqa: E402
from comfyui_pipeline import runtime_config as rc  # noqa: E402
import doctor  # noqa: E402
import smoke  # noqa: E402

URL_ENV = {name: "" for name in (*client.COMFY_URL_ENV_VARS, *client.COMFY_CONFIG_ENV_VARS)}


def fake_isfile(existing, pathmod):
    keys = {pathmod.normcase(pathmod.normpath(p)) for p in existing}
    return lambda path: pathmod.normcase(pathmod.normpath(path)) in keys


class ConfigPathTests(unittest.TestCase):
    def test_posix_repo_mode_relative_uses_repo_root_not_cwd(self):
        got = rc.resolve_config_path("local_config.json", repo_root="/r", cwd="/somewhere/else", pathmod=posixpath)
        self.assertEqual(got, "/r/local_config.json")
        got = rc.resolve_config_path("cfg/../local_config.json", repo_root="/r", cwd="/x", pathmod=posixpath)
        self.assertEqual(got, "/r/local_config.json")

    def test_posix_deployed_mode_relative_uses_cwd(self):
        got = rc.resolve_config_path("../local_config.json", repo_root=None, cwd="/c/ComfyUI/tools",
                                     pathmod=posixpath)
        self.assertEqual(got, "/c/ComfyUI/local_config.json")

    def test_absolute_is_kept(self):
        self.assertEqual(rc.resolve_config_path("/abs/c.json", repo_root="/r", cwd="/x", pathmod=posixpath),
                         "/abs/c.json")
        self.assertIsNone(rc.resolve_config_path(None, repo_root="/r"))

    def test_windows_paths(self):
        repo = "C:\\Users\\yuxiu\\comfyui-game-art-tutorial"
        self.assertEqual(rc.resolve_config_path("local_config.json", repo_root=repo, cwd="D:\\work", pathmod=ntpath),
                         repo + "\\local_config.json")
        self.assertEqual(rc.resolve_config_path("D:\\cfg\\local_config.json", repo_root=repo, pathmod=ntpath),
                         "D:\\cfg\\local_config.json")
        self.assertEqual(rc.resolve_config_path("D:/cfg/local_config.json", repo_root=repo, pathmod=ntpath),
                         "D:\\cfg\\local_config.json")
        self.assertEqual(rc.resolve_config_path("..\\local_config.json", cwd="E:\\ComfyUI\\tools", pathmod=ntpath),
                         "E:\\ComfyUI\\local_config.json")

    def test_find_repo_root_and_mode(self):
        repo = "C:\\r"
        isfile = fake_isfile([repo + "\\AGENTS.md", repo + "\\tools_src\\gameart.py"], ntpath)
        self.assertEqual(rc.find_repo_root(repo + "\\tools_src", isfile=isfile, pathmod=ntpath), repo)
        self.assertIsNone(rc.find_repo_root("E:\\ComfyUI\\tools", isfile=isfile, pathmod=ntpath))
        # 資料夾名稱對但不是 repo(缺 AGENTS.md)
        self.assertIsNone(rc.find_repo_root("D:\\x\\tools_src", isfile=isfile, pathmod=ntpath))
        self.assertEqual(rc.run_mode(repo), rc.REPO_MODE)
        self.assertEqual(rc.run_mode(None), rc.DEPLOYED_MODE)
        self.assertEqual(rc.find_repo_root(ROOT / "tools_src"), str(ROOT))

    def test_default_config_only_in_repo_mode(self):
        isfile = fake_isfile(["/r/local_config.json", "/c/ComfyUI/local_config.json"], posixpath)
        self.assertEqual(rc.choose_config_path(None, "/r", isfile=isfile, pathmod=posixpath),
                         ("/r/local_config.json", "repo-default"))
        self.assertEqual(rc.choose_config_path(None, None, isfile=isfile, pathmod=posixpath), (None, None))
        self.assertEqual(rc.choose_config_path(None, "/empty", isfile=isfile, pathmod=posixpath), (None, None))
        self.assertEqual(rc.choose_config_path("x.json", "/r", isfile=isfile, pathmod=posixpath),
                         ("/r/x.json", "cli"))

    def test_comfyui_path_relative_to_config_dir(self):
        self.assertEqual(rc.comfyui_path_from_config({"comfyui_path": "../ComfyUI"}, "/w/repo/local_config.json",
                                                     pathmod=posixpath), "/w/ComfyUI")
        self.assertEqual(rc.comfyui_path_from_config({"comfyui_path": "E:\\ComfyUI"}, "C:\\r\\local_config.json",
                                                     pathmod=ntpath), "E:\\ComfyUI")
        self.assertIsNone(rc.comfyui_path_from_config({}, "/r/local_config.json"))


class SnapshotDirTests(unittest.TestCase):
    def test_order_repo_mode(self):
        got = rc.snapshot_candidates("/r/tools_src", repo_root="/r", comfyui_path="/c/ComfyUI", pathmod=posixpath)
        self.assertEqual(got, [("/c/ComfyUI/tools", "comfyui_path/tools"), ("/r/tools_src", "script_dir")])

    def test_deployed_mode_ignores_comfyui_path_and_dedupes(self):
        self.assertEqual(rc.snapshot_candidates("/c/ComfyUI/tools", comfyui_path="/c/ComfyUI", pathmod=posixpath),
                         [("/c/ComfyUI/tools", "script_dir")])
        got = rc.snapshot_candidates("E:\\comfyui\\TOOLS", repo_root="C:\\r", comfyui_path="E:\\ComfyUI",
                                     pathmod=ntpath)
        self.assertEqual(len(got), 1)  # Windows 不分大小寫

    def test_explicit_wins_and_does_not_fall_back(self):
        isfile = fake_isfile(["/c/ComfyUI/tools/device_config.json"], posixpath)
        got = rc.snapshot_candidates("/r/tools_src", explicit="snap", repo_root="/r", comfyui_path="/c/ComfyUI",
                                     cwd="/work", pathmod=posixpath)
        self.assertEqual(got, [("/work/snap", "--snapshot-dir")])
        with self.assertRaises(rc.SnapshotNotFound) as ctx:
            rc.find_snapshot_dir("/r/tools_src", explicit="snap", repo_root="/r", comfyui_path="/c/ComfyUI",
                                 cwd="/work", isfile=isfile, pathmod=posixpath)
        self.assertEqual(ctx.exception.searched, ["/work/snap"])

    def test_found_and_not_found_messages(self):
        isfile = fake_isfile(["E:\\ComfyUI\\tools\\device_config.json"], ntpath)
        self.assertEqual(rc.find_snapshot_dir("C:\\r\\tools_src", repo_root="C:\\r", comfyui_path="E:\\ComfyUI",
                                              isfile=isfile, pathmod=ntpath),
                         ("E:\\ComfyUI\\tools", "comfyui_path/tools"))
        with self.assertRaises(rc.SnapshotNotFound) as ctx:
            rc.find_snapshot_dir("C:\\r\\tools_src", repo_root="C:\\r", isfile=isfile, pathmod=ntpath)
        self.assertEqual(ctx.exception.searched, ["C:\\r\\tools_src"])
        self.assertIn("C:\\r\\tools_src", str(ctx.exception))
        self.assertIn("comfyui_path", str(ctx.exception))


class Layout:
    """暫存的 repo 與 ComfyUI 資料夾,模擬兩台機器上的實際配置。"""

    def __init__(self, root, comfyui_path_value=None):
        self.root = Path(root)
        self.repo = self.root / "repo"
        self.comfy = self.root / "ComfyUI"
        self.tools = self.comfy / "tools"
        (self.repo / "tools_src").mkdir(parents=True)
        self.tools.mkdir(parents=True)
        (self.repo / "AGENTS.md").write_text("x", encoding="utf-8")
        (self.repo / "tools_src" / "gameart.py").write_text("", encoding="utf-8")
        (self.tools / "device_config.json").write_text(json.dumps({"tier": "sdxl_high"}), encoding="utf-8")
        self.config = self.repo / "local_config.json"
        self.config.write_text(json.dumps({
            "comfyui_path": comfyui_path_value or str(self.comfy), "comfyui_url": "http://127.0.0.1:8188"}),
            encoding="utf-8")


class SmokeSettingsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.lay = Layout(tmp.name)
        patcher = mock.patch.dict(os.environ, URL_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)

    def settings(self, **kw):
        kw.setdefault("cwd", str(self.lay.root / "elsewhere"))
        return smoke.resolve_run_settings(**kw)

    def test_repo_run_without_config_uses_repo_default_and_comfyui_tools(self):
        got = self.settings(script_dir=self.lay.repo / "tools_src")
        self.assertEqual(got["mode"], rc.REPO_MODE)
        self.assertEqual(got["config_source"], "repo-default")
        self.assertEqual(Path(got["config_path"]), self.lay.config)
        self.assertEqual(Path(got["snapshot_dir"]), self.lay.tools)

    def test_repo_run_relative_config_with_other_cwd(self):
        got = self.settings(config="local_config.json", script_dir=self.lay.repo / "tools_src")
        self.assertTrue(os.path.isabs(got["config_path"]))
        self.assertEqual(Path(got["config_path"]), self.lay.config)
        self.assertEqual(Path(got["snapshot_dir"]), self.lay.tools)

    def test_repo_run_absolute_config_and_relative_comfyui_path(self):
        self.lay.config.write_text(json.dumps({"comfyui_path": "../ComfyUI", "comfyui_url": "http://h:1"}),
                                   encoding="utf-8")
        got = self.settings(config=str(self.lay.config), script_dir=self.lay.repo / "tools_src")
        self.assertEqual(Path(got["snapshot_dir"]).resolve(), self.lay.tools.resolve())
        self.assertEqual(Path(got["comfyui_path"]).resolve(), self.lay.comfy.resolve())

    def test_repo_run_without_snapshot_lists_paths(self):
        (self.lay.tools / "device_config.json").unlink()
        with self.assertRaises(smoke.SmokeError) as ctx:
            self.settings(script_dir=self.lay.repo / "tools_src")
        self.assertIn(str(self.lay.tools), str(ctx.exception))
        self.assertIn(str(self.lay.repo / "tools_src"), str(ctx.exception))

    def test_snapshot_dir_override(self):
        other = self.lay.root / "snap"
        other.mkdir()
        (other / "device_config.json").write_text("{}", encoding="utf-8")
        got = self.settings(script_dir=self.lay.repo / "tools_src", snapshot_dir=str(other))
        self.assertEqual(Path(got["snapshot_dir"]), other)

    def test_missing_config_file_is_an_error(self):
        with self.assertRaises(smoke.SmokeError) as ctx:
            self.settings(config="nope.json", script_dir=self.lay.repo / "tools_src")
        self.assertIn(str(self.lay.repo / "nope.json"), str(ctx.exception))

    def test_deployed_run_requires_config_or_url(self):
        with self.assertRaises(smoke.SmokeError) as ctx:
            self.settings(script_dir=self.lay.tools)
        self.assertIn("未設定 ComfyUI URL", str(ctx.exception))
        got = self.settings(script_dir=self.lay.tools, comfy_url="http://127.0.0.1:8188")
        self.assertEqual(got["mode"], rc.DEPLOYED_MODE)
        self.assertIsNone(got["config_path"])
        self.assertEqual(Path(got["snapshot_dir"]), self.lay.tools)

    def test_deployed_run_relative_config_uses_cwd(self):
        got = self.settings(config="local_config.json", script_dir=self.lay.tools, cwd=str(self.lay.repo))
        self.assertEqual(Path(got["config_path"]), self.lay.config)
        self.assertEqual(Path(got["snapshot_dir"]), self.lay.tools)  # 部署端仍讀 tools/ 本身

    def test_child_gets_absolute_config_and_snapshot_env(self):
        got = self.settings(config="local_config.json", script_dir=self.lay.repo / "tools_src")
        seen = {}

        def runner(cmd, timeout, cwd, env=None):
            seen.update(cmd=cmd, cwd=cwd, env=env)
            return 1, "", "stop", False

        caps = {"default_profile": "sdxl_standard", "profiles": {"sdxl_standard": {"tasks": {}}}}
        environment = {"device": {"platform_key": "macos-mps", "backend": "mps", "usable_memory_mb": 48000,
                                  "precision_support": ["fp16"], "tier": "sdxl_high"},
                       "capabilities": caps, "profile_id": "sdxl_standard", "comfyui_path": None, "model_roots": []}
        entry = {"id": "concept", "task": "concept", "args": ["--prompt", "x"], "seed": 1}
        with tempfile.TemporaryDirectory() as out:
            smoke.run_task(entry, environment, out, {}, None, {}, runner=runner,
                           config_path=got["config_path"], snapshot_dir=got["snapshot_dir"])
        cfg = seen["cmd"][seen["cmd"].index("--config") + 1]
        self.assertTrue(os.path.isabs(cfg))
        self.assertTrue(os.path.isfile(cfg))
        self.assertNotEqual(Path(seen["cwd"]), self.lay.repo)  # 子程序 cwd 不是 repo root,仍找得到設定檔
        self.assertEqual(seen["env"][rc.SNAPSHOT_DIR_ENV], got["snapshot_dir"])

    def test_main_reports_missing_config_with_exit_2(self):
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as out, redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = smoke.main(["run", "--output-dir", out, "--config", "definitely-missing-config.json"])
        self.assertEqual(code, 2)
        self.assertIn(str(ROOT / "definitely-missing-config.json"), err.getvalue())


class GenerateSnapshotEnvTests(unittest.TestCase):
    def test_image_graphs_reads_device_config_from_env(self):
        with tempfile.TemporaryDirectory() as snap:
            Path(snap, "device_config.json").write_text(
                json.dumps({"tier": "sdxl_high", "checkpoint": "from-env.safetensors"}), encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(ROOT / "tools_src"), **{rc.SNAPSHOT_DIR_ENV: snap})
            out = subprocess.run(
                [sys.executable, "-c",
                 "from comfyui_pipeline import image_graphs as g; print(g.DEVICE_CONFIG_PATH); print(g.CKPT)"],
                env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
            self.assertEqual(out.returncode, 0, out.stderr)
            lines = out.stdout.strip().splitlines()
            self.assertEqual(Path(lines[0]), Path(snap) / "device_config.json")
            self.assertEqual(lines[1], "from-env.safetensors")


class DoctorConfigTests(unittest.TestCase):
    def test_relative_config_resolves_against_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            lay = Layout(tmp, comfyui_path_value="../ComfyUI")
            args = SimpleNamespace(config="local_config.json", comfyui_path=None, snapshot_dir=None)
            cwd = os.getcwd()
            os.chdir(lay.tools)
            try:
                with mock.patch.object(doctor.rc, "find_repo_root", return_value=str(lay.repo)):
                    config, comfyui_path, snapshot_dir = doctor.resolve_context(args)
            finally:
                os.chdir(cwd)
            self.assertEqual(config["comfyui_url"], "http://127.0.0.1:8188")
            self.assertEqual(Path(comfyui_path).resolve(), lay.comfy.resolve())
            self.assertEqual(Path(snapshot_dir).resolve(), lay.tools.resolve())


if __name__ == "__main__":
    unittest.main()
