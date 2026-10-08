"""face_swap.py／video_layers.py 不載入 image_graphs,所以缺 device_config.json 時不印誤導的提醒(PR 3.1)。

圖片 task 在真的缺快照時仍要提醒:image_graphs 本身的行為不變。
每個案例都在全新的 Python process 執行,並把 GAMEART_SNAPSHOT_DIR 指到空資料夾,模擬沒有快照的機器。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest

TOOLS_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools_src")
WARNING = re.compile(r"找不到.*device_config")
TOOLS = ("face_swap", "video_layers")


class DeviceConfigWarningTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = temp.name
        self.snapshot_dir = os.path.join(self.root, "empty-snapshot")
        os.mkdir(self.snapshot_dir)
        self.env = dict(os.environ, GAMEART_SNAPSHOT_DIR=self.snapshot_dir, PYTHONIOENCODING="utf-8")

    def run_process(self, args):
        return subprocess.run([sys.executable, *args], cwd=TOOLS_SRC, env=self.env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", check=False)

    def run_code(self, code):
        return self.run_process(["-c", textwrap.dedent(code)])

    def assert_no_warning(self, result):
        self.assertIsNone(WARNING.search(result.stdout + result.stderr), result.stdout + result.stderr)

    def test_help_does_not_warn(self):
        for tool in TOOLS:
            with self.subTest(tool=tool):
                result = self.run_process([os.path.join(TOOLS_SRC, f"{tool}.py"), "--help"])
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("preflight", result.stdout)
                self.assert_no_warning(result)

    def test_preflight_does_not_load_image_graphs(self):
        # 非 loopback URL 讓 preflight 在連線前就停下;重點是過程中沒有載入 image_graphs、沒有提醒。
        config = os.path.join(self.root, "config.json")
        with open(config, "w", encoding="utf-8") as f:
            json.dump({"comfyui_path": self.root, "comfyui_url": "https://example.com"}, f)
        calls = {"face_swap": f"face_swap.preflight({config!r})",
                 "video_layers": f"video_layers.preflight({config!r}, 'compose')"}
        for tool in TOOLS:
            with self.subTest(tool=tool):
                result = self.run_code(f"""
                    import sys
                    sys.path.insert(0, {TOOLS_SRC!r})
                    import {tool}
                    try:
                        {calls[tool]}
                    except ValueError as exc:
                        assert "loopback" in str(exc), exc
                    else:
                        raise AssertionError("preflight 應該擋下非 loopback URL")
                    loaded = sorted(m for m in sys.modules if m in ("generate", "comfyui_pipeline.image_graphs"))
                    assert not loaded, loaded
                    print("ok")
                """)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("ok", result.stdout)
                self.assert_no_warning(result)

    def test_image_graphs_still_warns_without_snapshot(self):
        result = self.run_code(f"""
            import sys
            sys.path.insert(0, {TOOLS_SRC!r})
            import comfyui_pipeline.image_graphs
        """)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIsNotNone(WARNING.search(result.stderr), result.stderr)


if __name__ == "__main__":
    unittest.main()
