import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOLS_SRC = Path(__file__).resolve().parents[1] / "tools_src"
sys.path.insert(0, str(TOOLS_SRC))
import gameart  # noqa: E402


class GameartDispatcherTests(unittest.TestCase):
    def test_every_tool_script_exists(self):
        for name, (script, desc) in gameart.TOOLS.items():
            self.assertTrue((TOOLS_SRC / script).is_file(), name)
            self.assertTrue(desc, name)

    def test_list_prints_all_tools(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(gameart.main(["list"]), 0)
        for name in gameart.TOOLS:
            self.assertIn(name, buf.getvalue())

    def test_unknown_tool_returns_2(self):
        self.assertEqual(gameart.main(["no-such-tool"]), 2)

    def test_forwards_argv_and_help_unchanged(self):
        direct = subprocess.run([sys.executable, str(TOOLS_SRC / "detect_device.py"), "--help"],
                                capture_output=True, text=True)
        via = subprocess.run([sys.executable, str(TOOLS_SRC / "gameart.py"), "detect-device", "--help"],
                             capture_output=True, text=True)
        self.assertEqual(via.returncode, direct.returncode)
        self.assertIn("--out", via.stdout)
        self.assertEqual(via.stdout, direct.stdout)


if __name__ == "__main__":
    unittest.main()
