"""文件收斂的防回歸測試(純 unittest,不 import tools_src)。

規則(每種資訊只放一個地方):
- skills/ 只放 SKILL.md(思路與路由),不再有 references/ 資料夾;每個 SKILL.md 不超過 60 行。
- 現行文件(skills/、docs/knowledge 排除 archive/ 與 decisions/、AGENTS.md、README.md、templates/README.md)
  不得出現已移除功能的舊名詞;要增減禁用詞只改下面的 FORBIDDEN_TERMS。
- 這些現行文件裡的 Markdown 相對連結都要指向存在的檔案或資料夾。

歷史資料(archive/、decisions/)可以保留舊名詞,agent 平常不讀。

單獨執行(repo 根目錄):
  $env:PYTHONPATH='tools_src;tests;.'; python -m unittest tests.test_docs_converged
"""
import os
import re
import unittest
import urllib.parse

# ---- 禁用詞:(說明, 正規表示式,不分大小寫) ----
FORBIDDEN_TERMS = [
    ("舊低記憶體底模 sd15 設定檔", r"sd15"),
    ("SD1.5", r"sd ?1\.5"),
    ("dreamshaper", r"dreamshaper"),
    ("換臉(face-swap / face_swap / 換臉)", r"face[-_ ]?swap|換臉"),
    ("ReActor", r"reactor"),
    ("image_graphs(舊 Python graph builder 模組)", r"image_graphs"),
    ("Python 圖形 builder 名稱(build_wheel_* 與 build_catalog 不在此列)",
     r"\bbuild_(concept|icon_asset|pose_only|style_lock|character_action|refine|inpaint|guided_inpaint|upscale"
     r"|layer_split|flux2_\w+|img2video\w*|pose_drive\w*|character_video\w*|camera_end_still|video_inpaint\w*"
     r"|image_templates|extend_templates|scail2_templates)\b"),
    ("教學.md", r"教學\.md"),
    ("workflows/Ch*", r"workflows/ch"),
]

# 由 template.json 自動產生的頁面,內容跟著 template 走,不手改也不在這裡掃詞
GENERATED_FILES = {"docs/knowledge/maintenance/template-catalog.md"}

# 不屬於「現行文件」的資料夾(歷史資料)
HISTORY_PREFIXES = ("docs/knowledge/archive/", "docs/knowledge/decisions/")

MAX_SKILL_LINES = 60
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FENCE_RE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
INLINE_CODE_RE = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)", re.S)
LINK_RE = re.compile(r"\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _walk(base):
    for folder, dirs, names in os.walk(os.path.join(ROOT, base)):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".obsidian")]
        for name in names:
            yield os.path.relpath(os.path.join(folder, name), ROOT).replace(os.sep, "/")


def current_docs():
    """現行 Markdown:skills/、docs/knowledge(排除歷史資料夾)、AGENTS.md、README.md、templates/README.md。"""
    found = [p for p in _walk("skills") if p.endswith(".md")]
    found += [p for p in _walk("docs/knowledge") if p.endswith(".md") and not p.startswith(HISTORY_PREFIXES)]
    found += [p for p in ("AGENTS.md", "README.md", "templates/README.md") if os.path.isfile(os.path.join(ROOT, p))]
    return sorted(set(found))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as handle:
        return handle.read()


class SkillsAreLeanTests(unittest.TestCase):
    def test_no_references_folder_under_skills(self):
        bad = []
        for folder, dirs, _ in os.walk(os.path.join(ROOT, "skills")):
            for d in dirs:
                if d in ("references", "reference"):
                    bad.append(os.path.relpath(os.path.join(folder, d), ROOT).replace(os.sep, "/"))
        self.assertEqual(bad, [], "skills/ 底下不得有 references/ 資料夾(判斷依據放 docs/knowledge,用法以 template.json 為準)")

    def test_skill_files_are_short(self):
        skills = [p for p in _walk("skills") if p.endswith("/SKILL.md")]
        self.assertTrue(skills, "找不到任何 SKILL.md")
        too_long = []
        for rel in skills:
            lines = len(read(rel).splitlines())
            if lines > MAX_SKILL_LINES:
                too_long.append(f"{rel}: {lines} 行(上限 {MAX_SKILL_LINES})")
        self.assertEqual(too_long, [], "SKILL.md 只寫思路,細節放知識庫:\n" + "\n".join(too_long))


class NoOldTracesTests(unittest.TestCase):
    def test_no_forbidden_terms_in_current_docs(self):
        patterns = [(label, re.compile(rx, re.I)) for label, rx in FORBIDDEN_TERMS]
        hits = []
        for rel in current_docs():
            if rel in GENERATED_FILES:
                continue
            for no, line in enumerate(read(rel).splitlines(), 1):
                for label, pattern in patterns:
                    if pattern.search(line):
                        hits.append(f"{rel}:{no}: [{label}] {line.strip()[:100]}")
        self.assertEqual(hits, [], "現行文件出現已移除功能的舊名詞(歷史資料請放 docs/knowledge/archive/):\n" + "\n".join(hits))

    def test_forbidden_patterns_actually_match(self):
        # 防止正規表示式寫壞而永遠不命中
        samples = ["sd15_light", "SD1.5", "SD 1.5", "DreamShaper 8", "face_swap.py", "face-swap", "換臉", "ReActor",
                   "image_graphs.py", "build_concept", "build_icon_asset", "教學.md", "workflows/Ch8_x.json"]
        for sample in samples:
            self.assertTrue(any(re.search(rx, sample, re.I) for _, rx in FORBIDDEN_TERMS), sample)
        for allowed in ("build_catalog.py", "build_wheel_segment_template", "build_wheel_layer_masks"):
            self.assertFalse(any(re.search(rx, allowed, re.I) for _, rx in FORBIDDEN_TERMS), allowed)


class RelativeLinksTests(unittest.TestCase):
    def test_relative_links_point_to_existing_files(self):
        problems = []
        for rel in current_docs():
            text = INLINE_CODE_RE.sub("", FENCE_RE.sub("", read(rel)))
            base = os.path.dirname(os.path.join(ROOT, rel))
            for raw in LINK_RE.findall(text):
                if SCHEME_RE.match(raw) or raw.startswith(("<", "//", "#")):
                    continue
                path_part = urllib.parse.unquote(raw.partition("#")[0])
                if not path_part:
                    continue
                target = os.path.normpath(os.path.join(base, path_part))
                if os.path.exists(target):
                    continue
                # local_config.json 是不進版控的本機設定檔,clean checkout 沒有
                if os.path.relpath(target, ROOT).replace(os.sep, "/") == "local_config.json":
                    continue
                problems.append(f"{rel}: 目標不存在: {raw}")
        self.assertEqual(problems, [], "\n" + "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
