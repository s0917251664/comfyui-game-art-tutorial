"""工具輸出與 CLI 文字不寫特定人名(審核者一律寫 human review / reviewer)。

例外只有 custom node 的舊名稱(class、socket 型別、分類、顯示名稱):改名要部署與重啟 ComfyUI,
排在 PR 2.5,並保留舊名稱作相容別名。2.5 完成後應縮小這裡的允許清單。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"steve", re.I)
# 2.5 之前允許的 custom node 舊名稱
ALLOWED_RE = re.compile(
    r"Steve(VideoLayers|LoadFaceSwapVideo|ReActorVideo)\b|STEVE_FACE_SWAP_SOURCE|Steve/Video|Steve ·")


class NeutralWordingTests(unittest.TestCase):
    def test_tools_src_has_no_personal_name_outside_node_ids(self):
        hits = []
        for path in sorted((ROOT / "tools_src").rglob("*")):
            if path.suffix not in (".py", ".json", ".html", ".js", ".ps1") or "__pycache__" in path.parts:
                continue
            for no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if NAME_RE.search(ALLOWED_RE.sub("", line)):
                    hits.append(f"{path.relative_to(ROOT).as_posix()}:{no}: {line.strip()[:120]}")
        self.assertEqual(hits, [], "\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
