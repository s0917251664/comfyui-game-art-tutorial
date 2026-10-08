"""程式、測試與文件不寫特定人名(審核者一律寫 human review / reviewer / 美術審核者)。

PR 2.5 起 custom node 改用 GameArt 名稱(D9)。PR 8.2 移除隱藏別名後,
舊 class 名稱只允許出現在:
- 遷移說明 docs/knowledge/maintenance/custom-node-renames.md;
- 本檔(掃描用的正則)。
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
CONTRACT_FILES = ("tools_src/comfyui_video_layers/contracts.py", "tools_src/comfyui_face_swap_video/contracts.py")


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
    def test_no_personal_name_outside_migration_note(self):
        hits = []
        for rel in tracked_text_files():
            if rel in (MIGRATION_NOTE, THIS_FILE):
                continue
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
            for no, line in enumerate(text.splitlines(), 1):
                if NAME_RE.search(line):
                    hits.append(f"{rel}:{no}: {line.strip()[:120]}")
        self.assertEqual(hits, [], "\n" + "\n".join(hits))

    def test_scan_covers_code_tests_and_docs(self):
        files = tracked_text_files()
        for expected in ("tools_src/face_swap.py", "tests/test_face_swap.py", "AGENTS.md",
                         "skills/comfyui-video-layers/SKILL.md", "docs/knowledge/video/layers.md"):
            self.assertIn(expected, files)

    def test_legacy_names_absent_from_contracts(self):
        for rel in CONTRACT_FILES:
            lines = [l for l in (ROOT / rel).read_text(encoding="utf-8").splitlines() if NAME_RE.search(l)]
            self.assertEqual(lines, [], rel)
        note = (ROOT / MIGRATION_NOTE).read_text(encoding="utf-8")
        self.assertTrue(NAME_RE.search(note), "遷移說明仍是舊名稱的唯一紀錄")


if __name__ == "__main__":
    unittest.main()
