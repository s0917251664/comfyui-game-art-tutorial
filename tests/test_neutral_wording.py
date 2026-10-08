"""程式、測試與文件不寫特定人名(審核者一律寫 human review / reviewer / 美術審核者)。

PR 2.5 起 custom node 改用 GameArt 名稱(D9)。舊名稱只允許出現在:
- 各 node 套件 contracts.py 的 LEGACY_* 常數(隱藏別名的唯一定義處);
- 遷移說明 docs/knowledge/maintenance/custom-node-renames.md;
- 本檔。
第 8 階段移除別名時,一併刪掉這裡的例外。
"""
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"steve", re.I)
TEXT_SUFFIXES = (".py", ".md", ".json", ".html", ".js", ".ps1", ".txt", ".yaml", ".yml", ".toml", ".cfg", ".ini")
SKIP_PREFIXES = ("third_party/", "output/")
MIGRATION_NOTE = "docs/knowledge/maintenance/custom-node-renames.md"
THIS_FILE = "tests/test_neutral_wording.py"
# 舊名稱別名的定義:只能是 contracts.py 裡 LEGACY_ 開頭的常數行
ALIAS_FILES = ("tools_src/comfyui_video_layers/contracts.py", "tools_src/comfyui_face_swap_video/contracts.py")
ALIAS_LINE_RE = re.compile(r"^LEGACY_[A-Z_]+ = ")


def tracked_text_files():
    try:
        out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-z"],
                             cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
        files = [f for f in out.split("\0") if f]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for base, dirs, names in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "output", "__pycache__")]
            files += [os.path.relpath(os.path.join(base, n), ROOT).replace(os.sep, "/") for n in names]
    return sorted(f for f in files if f.endswith(TEXT_SUFFIXES) and not f.startswith(SKIP_PREFIXES)
                  and (ROOT / f).is_file())


class NeutralWordingTests(unittest.TestCase):
    def test_no_personal_name_outside_legacy_alias_definitions(self):
        hits = []
        for rel in tracked_text_files():
            if rel in (MIGRATION_NOTE, THIS_FILE):
                continue
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
            for no, line in enumerate(text.splitlines(), 1):
                if not NAME_RE.search(line):
                    continue
                if rel in ALIAS_FILES and ALIAS_LINE_RE.match(line):
                    continue
                hits.append(f"{rel}:{no}: {line.strip()[:120]}")
        self.assertEqual(hits, [], "\n" + "\n".join(hits))

    def test_scan_covers_code_tests_and_docs(self):
        files = tracked_text_files()
        for expected in ("tools_src/face_swap.py", "tests/test_face_swap.py", "AGENTS.md",
                         "skills/comfyui-video-layers/SKILL.md", "docs/knowledge/video/layers.md"):
            self.assertIn(expected, files)

    def test_legacy_names_live_only_in_alias_constants(self):
        for rel in ALIAS_FILES:
            lines = [l for l in (ROOT / rel).read_text(encoding="utf-8").splitlines() if NAME_RE.search(l)]
            self.assertTrue(lines, rel)  # 別名還在(第 8 階段才移除)
            self.assertTrue(all(ALIAS_LINE_RE.match(l) for l in lines), lines)
        self.assertTrue((ROOT / MIGRATION_NOTE).is_file())


if __name__ == "__main__":
    unittest.main()
