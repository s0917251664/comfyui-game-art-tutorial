"""版控內的文字檔一律 UTF-8、不加 BOM、repo 內存 LF、工作副本不混用換行。

Windows 上容易出錯的地方：Python open() 沒寫 encoding 會用 cp950；PowerShell 5.1 的
Set-Content 預設 ANSI、Out-File 會加 BOM；編輯 CRLF 檔再存回容易變成混用換行。

例外：
- .ps1：Windows PowerShell 5.1 要有 BOM 才會把非 ASCII 當 UTF-8 讀，所以含非 ASCII 時必須有 BOM。
- .gitattributes 標 -text 的路徑（有 hash 紀錄）保留原始位元組，不檢查 repo 內是不是 LF；
  third_party/ 是上游原檔，連混用換行也不檢查。
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOM = b"\xef\xbb\xbf"
UPSTREAM_PREFIXES = ("third_party/",)


def tracked_files():
    """回傳 [(path, index_eol, worktree_eol, attr)]；git 不可用時回傳 None。"""
    try:
        out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-z", "--eol"],
                             cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        return None
    rows = []
    for row in out.split("\0"):
        if not row:
            continue
        meta, path = row.split("\t", 1)
        index_eol, worktree_eol, attr = meta.split()[:3]
        rows.append((path, index_eol[2:], worktree_eol[2:], attr[5:]))
    return rows


def encoding_problems(path, data, index_eol, worktree_eol, attr):
    """單一檔案的問題清單；index_eol 為 -text（git 判定為二進位）或 none（空檔）時不檢查。"""
    if index_eol in ("-text", "none"):
        return []
    problems = []
    body = data[len(BOM):] if data.startswith(BOM) else data
    try:
        body.decode("utf-8")
    except UnicodeDecodeError as exc:
        problems.append(f"不是 UTF-8（位元組 {exc.start}）")
    if path.endswith(".ps1"):
        if not data.startswith(BOM) and any(b > 127 for b in body):
            problems.append(".ps1 含非 ASCII 但沒有 BOM（PowerShell 5.1 會用 ANSI 讀）")
    elif data.startswith(BOM):
        problems.append("有 UTF-8 BOM")
    if attr != "-text" and index_eol != "lf":
        problems.append(f"repo 內換行是 {index_eol}，應為 lf")
    if worktree_eol == "mixed" and not path.startswith(UPSTREAM_PREFIXES):
        problems.append("工作副本混用 LF 與 CRLF")
    return problems


class EncodingRuleTests(unittest.TestCase):
    def check(self, data, path="docs/a.md", index_eol="lf", worktree_eol="crlf", attr="text=auto"):
        return encoding_problems(path, data, index_eol, worktree_eol, attr)

    def test_accepts_plain_utf8(self):
        self.assertEqual([], self.check("中文\r\n".encode("utf-8")))

    def test_rejects_bom_cp950_and_crlf_in_index(self):
        self.assertTrue(self.check(BOM + b"a\n"))
        self.assertTrue(self.check("中文".encode("cp950")))
        self.assertTrue(self.check(b"a\r\n", index_eol="crlf"))
        self.assertTrue(self.check(b"a\r\nb\n", index_eol="mixed", worktree_eol="mixed"))

    def test_hash_pinned_and_upstream_exceptions(self):
        self.assertEqual([], self.check(b"a\r\n", path="templates/x/graph.api.json", index_eol="crlf", attr="-text"))
        self.assertTrue(self.check(b"a\r\nb\n", path="templates/x/README.md", index_eol="mixed",
                                   worktree_eol="mixed", attr="-text"))
        self.assertEqual([], self.check(b"a\r\nb\n", path="third_party/x/SKILL.md", index_eol="mixed",
                                        worktree_eol="mixed", attr="-text"))

    def test_ps1_bom_rules(self):
        self.assertEqual([], self.check(BOM + "說明".encode("utf-8"), path="tools_src/x.ps1"))
        self.assertEqual([], self.check(BOM + b"ascii", path="tools_src/x.ps1"))
        self.assertTrue(self.check("說明".encode("utf-8"), path="tools_src/x.ps1"))

    def test_binary_and_empty_files_are_skipped(self):
        self.assertEqual([], self.check(b"\x89PNG\xff", path="a.png", index_eol="-text", attr=""))


class TrackedFilesEncodingTests(unittest.TestCase):
    def test_tracked_text_files_follow_encoding_rules(self):
        rows = tracked_files()
        if rows is None:
            self.skipTest("需要 git")
        self.assertGreater(len(rows), 100)
        hits = []
        for path, index_eol, worktree_eol, attr in rows:
            full = ROOT / path
            if not full.is_file():
                continue
            for problem in encoding_problems(path, full.read_bytes(), index_eol, worktree_eol, attr):
                hits.append(f"{path}: {problem}")
        self.assertEqual([], hits, "\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
