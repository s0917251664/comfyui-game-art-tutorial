"""Markdown 相對連結回歸測試(只用標準庫,不連網)。

檢查 repo 內追蹤的 Markdown:
- 相對連結的目標檔案或資料夾存在;
- 指向 .md 的 ``#錨點`` 對得到 GitHub 風格的標題錨點;
- 不連到不進版控的 ``output/``(本機證據改寫成純文字標註,規則見
  docs/knowledge/maintenance/doc-links.md)。

``third_party/claude-obsidian/``(上游 vendor 原檔)不檢查。刻意保留的例外列在 ALLOWED_MISSING,
例外已不存在時測試也會失敗,避免清單過期。
"""
import os
import re
import subprocess
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_PREFIXES = ("third_party/claude-obsidian/", "output/")

# (來源檔, 連結原文) -> 保留原因
ALLOWED_MISSING = {
    ("AGENTS.md", "local_config.json"): "本機設定檔,刻意不進版控",
    ("third_party/claude-obsidian-skills/wiki/references/frontmatter.md", "../../../WIKI.md"):
        "上游原文,原本指向上游 repo 根目錄;改了會破壞 hash",
}

FENCE_RE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
INLINE_CODE_RE = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)", re.S)
LINK_RE = re.compile(r"\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
HTML_ANCHOR_RE = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"", re.I)
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def tracked_markdown():
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z", "--", "*.md"],
            cwd=ROOT, capture_output=True, check=True,
        ).stdout.decode("utf-8")
        files = [f for f in out.split("\0") if f]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for base, dirs, names in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "output", "__pycache__")]
            for name in names:
                if name.endswith(".md"):
                    files.append(os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/"))
    return sorted(f for f in files if not f.startswith(SKIP_PREFIXES))


def strip_code(text):
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


def slugify(heading):
    heading = re.sub(r"`([^`]*)`", r"\1", heading)
    heading = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    heading = heading.strip().lower()
    heading = re.sub(r"[^\w\- ]", "", heading)
    return heading.replace(" ", "-")


_ANCHORS = {}


def anchors(path):
    if path not in _ANCHORS:
        found, counts = set(), {}
        with open(path, encoding="utf-8") as handle:
            text = FENCE_RE.sub("", handle.read())
        for line in text.splitlines():
            match = HEADING_RE.match(line)
            if match:
                slug = slugify(match.group(1))
                n = counts.get(slug, 0)
                counts[slug] = n + 1
                found.add(slug if n == 0 else f"{slug}-{n}")
            found.update(a.lower() for a in HTML_ANCHOR_RE.findall(line))
        _ANCHORS[path] = found
    return _ANCHORS[path]


def check_repo():
    problems, allowed_seen = [], set()
    for rel in tracked_markdown():
        source = os.path.join(ROOT, rel)
        if not os.path.isfile(source):
            continue
        with open(source, encoding="utf-8") as handle:
            text = strip_code(handle.read())
        for raw in LINK_RE.findall(text):
            if SCHEME_RE.match(raw) or raw.startswith(("<", "//")):
                continue
            path_part, _, fragment = raw.partition("#")
            path_part = urllib.parse.unquote(path_part)
            target = os.path.normpath(os.path.join(os.path.dirname(source), path_part)) if path_part else source
            target_rel = os.path.relpath(target, ROOT).replace(os.sep, "/")
            if target_rel == "output" or target_rel.startswith("output/"):
                problems.append(f"{rel}: 連到不進版控的 output/: {raw}(改寫成「標籤（本機證據：`output/...`）」)")
                continue
            if not os.path.exists(target):
                if (rel, raw) in ALLOWED_MISSING:
                    allowed_seen.add((rel, raw))
                    continue
                problems.append(f"{rel}: 目標不存在: {raw}")
                continue
            if fragment and target.endswith(".md"):
                if urllib.parse.unquote(fragment).lower() not in anchors(target):
                    problems.append(f"{rel}: 錨點不存在: {raw}")
    stale = sorted(set(ALLOWED_MISSING) - allowed_seen)
    return problems, stale


class DocLinkTests(unittest.TestCase):
    def test_relative_links_and_anchors_resolve(self):
        problems, stale = check_repo()
        self.assertEqual(problems, [], "\n" + "\n".join(problems))
        self.assertEqual(stale, [], "ALLOWED_MISSING 裡有已經不存在的例外,請移除: %r" % stale)

    def test_slugify_matches_github_style(self):
        self.assertEqual(slugify("2. 影片物件標記與局部重繪"), "2-影片物件標記與局部重繪")
        self.assertEqual(slugify("Queue、輪詢與下載"), "queue輪詢與下載")
        self.assertEqual(slugify("`gameart.py` 工具 (CLI)"), "gameartpy-工具-cli")

    def test_output_links_are_rejected(self):
        self.assertTrue(LINK_RE.search("[x](../../output/a.json)"))
        self.assertEqual(strip_code("`[x](output/a.json)`"), "")


if __name__ == "__main__":
    unittest.main()
