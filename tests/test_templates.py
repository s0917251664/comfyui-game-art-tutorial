import copy
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golden_template_graphs as golden  # noqa: E402

from comfyui_pipeline.runner import cli  # noqa: E402
from comfyui_pipeline.runner import template as T  # noqa: E402

ROOT = Path(golden.ROOT)
TEMPLATES = Path(golden.TEMPLATES)
# PR 2.1 從舊位置搬過來的 8 份(graph 位元組不能變)
MOVED_IDS = [
    "video/sam3/track-mask", "video/sam3/track-text",
    "video/wan-animate/mix", "video/wan-animate/mix-extend", "video/wan-animate/move",
    "video/wan-animate/move-extend", "video/wan-animate/scail2", "video/wan-animate/scail2-extend",
]
# discover 用路徑各段排序（video/wan 排在 video/wan-animate 前面），不是整段字串的 '/' 與 '-'。
def _id_key(template_id):
    return tuple(template_id.split("/"))


VIDEO_IDS = sorted(MOVED_IDS + ["video/wan-vace/inpaint", *golden.VIDEO_TEMPLATE_IDS], key=_id_key)


def image_template_ids():
    return [template_id for template_id in T.discover(TEMPLATES) if template_id.startswith("image/")]


ALL_IDS = sorted(VIDEO_IDS + image_template_ids(), key=_id_key)
# 舊位置 → 新位置與位元組 sha256(PR 2.1 搬移前後必須一致)
MOVED_GRAPH_SHA256 = {
    "video/wan-animate/mix": "5ba22f287ef8f9cb9cb926c249724ae050a0b3bd3076863cdd25f4b6b64c6d6c",
    "video/wan-animate/move": "e1f9f6c2097987170e591612d4f7d0b98547a3eddf1f5945153c6223e7cb3240",
    "video/wan-animate/mix-extend": "c239bc60f3e6995e798eb3e6cf7d2cecd6b58c7c0867ad21e1a61c1d4bbc1773",
    "video/wan-animate/move-extend": "07e7b2a589c6518e0a0627a1879594fe27a4ec9dde435520f9c8f94f93611150",
    "video/wan-animate/scail2": "a083556edc9ffd5f06e7afe2492449363bd7291d75a687d276741734ab339432",
    "video/wan-animate/scail2-extend": "35a3f3e50206d705e3faebc64e9da33a7345ebc8db6d5623422205a5dcf89780",
    "video/sam3/track-mask": "39cf43cd89593679f6db30dc38adc13d175bc152fcfd2fe139a8b38c2ff191cf",
    "video/sam3/track-text": "836c6ce1744a19b65cbfda6d627cd6c3891779838d801f342686cd6e665af642",
}


def tracked_files(*patterns):
    """git 追蹤中、符合 patterns 的檔案(repo 相對路徑);沒有 git 時改走目錄。"""
    skip = ("third_party/", "output/")
    try:
        out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-z", "--", *patterns],
                             cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
        files = [f for f in out.split("\0") if f]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for pattern in patterns:
            files += [p.relative_to(ROOT).as_posix() for p in ROOT.rglob(pattern) if ".git" not in p.parts]
    return sorted({f for f in files if not f.startswith(skip) and (ROOT / f).is_file()})

class TemplateFixture:
    """把一份 template 複製到暫存資料夾,方便改壞來測試驗證。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "templates"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def copy(self, template_id):
        shutil.copytree(TEMPLATES / template_id, self.root / template_id)
        return self.root / template_id

    def edit(self, template_id, change_data=None, change_graph=None):
        folder = self.copy(template_id)
        data = json.loads((folder / "template.json").read_text(encoding="utf-8"))
        if change_graph:
            graph = json.loads((folder / "graph.api.json").read_text(encoding="utf-8"))
            change_graph(graph)
            raw = json.dumps(graph, indent=2).encode("utf-8")
            (folder / "graph.api.json").write_bytes(raw)
            data["graph"]["sha256"] = T.file_sha256(folder / "graph.api.json")
            data["graph"]["canonical_sha256"] = T.canonical_sha256(graph)
        if change_data:
            change_data(data)
        (folder / "template.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return folder

    def load(self, template_id):
        return T.load_template(self.root, template_id, repo_root=ROOT)

    def assertRejected(self, template_id, fragment):
        with self.assertRaises(T.TemplateError) as ctx:
            self.load(template_id)
        self.assertIn(fragment, str(ctx.exception))


class LoadTemplatesTests(unittest.TestCase):
    def test_discovers_exactly_listed_templates(self):
        self.assertEqual(ALL_IDS, T.discover(TEMPLATES))
        self.assertEqual(VIDEO_IDS, [template_id for template_id in ALL_IDS if template_id.startswith("video/")])

    def test_all_templates_load_and_hashes_match_moved_bytes(self):
        for template_id in MOVED_IDS:
            with self.subTest(template_id):
                template = T.load_template(TEMPLATES, template_id, repo_root=ROOT)
                self.assertEqual(MOVED_GRAPH_SHA256[template_id], template.graph_sha256)
                self.assertEqual(template.data["graph"]["canonical_sha256"], template.graph_canonical_sha256)
                self.assertEqual(template_id, template.data["id"])

    def test_old_asset_locations_are_gone(self):
        for old in ("skills/comfyui-wan-animate/assets/mix-api.json",
                    "skills/comfyui-video-layers/assets/sam3-track-mask-api.json",
                    # D12:舊 Wan manifest 在 PR 2.4 刪除,template.json 是唯一來源
                    "skills/comfyui-wan-animate/assets/template-manifest.json"):
            self.assertFalse((ROOT / old).exists(), old)

    def test_deleted_wan_manifest_is_indexed_not_linked(self):
        old = "skills/comfyui-wan-animate/assets/template-manifest.json"
        index = (ROOT / "docs/knowledge/archive/redirect-stubs.md").read_text(encoding="utf-8")
        self.assertIn(f"`{old}`", index)
        # 只有轉址索引、決策紀錄和 templates/README 可以提到舊路徑(說明它已刪除)
        allowed = {"docs/knowledge/archive/redirect-stubs.md", "templates/README.md"}
        for path in tracked_files("*.md", "*.py", "*.json"):
            if path in allowed or path.startswith("docs/knowledge/decisions/") or path.startswith("tests/"):
                continue
            text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("assets/template-manifest.json", text, path)

    def test_fixed_graph_docs_route_through_runner(self):
        """D8:技能與規則不再要求手動送 JSON,也不再禁止 runner。"""
        stale = ("沒有 Python 入口", "無 Python 入口", "runner 合併前", "不要建立 `.ps1`",
                 "增加 Python client", "直接 HTTP 送出", "直接 HTTP 送 templates")
        for path in tracked_files("*.md"):
            if not (path.startswith("skills/") or path.startswith("docs/knowledge/rules/")
                    or path.startswith("docs/knowledge/maintenance/") or path == "AGENTS.md"
                    or path in ("docs/knowledge/TOOLS.md", "docs/knowledge/video/vfx-tools.md")):
                continue
            text = (ROOT / path).read_text(encoding="utf-8")
            for phrase in stale:
                self.assertNotIn(phrase, text, f"{path}: {phrase}")
        for path in ("docs/knowledge/rules/fixed-graphs.md",
                     "skills/comfyui-run/references/comfyui-wan-animate/README.md",
                     "skills/comfyui-run/references/comfyui-wan-animate/references/comfyui-api.md",
                     "skills/comfyui-run/references/comfyui-wan-animate/references/scail2.md",
                     "skills/comfyui-run/references/comfyui-video-layers/references/sam3-track.md"):
            text = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("gameart.py run", text, path)
        for path in ("skills/comfyui-run/references/comfyui-wan-animate/README.md",
                     "skills/comfyui-run/references/comfyui-wan-animate/references/comfyui-api.md",
                     "skills/comfyui-run/references/comfyui-video-layers/references/sam3-track.md"):
            self.assertIn("--preflight", (ROOT / path).read_text(encoding="utf-8"), path)

    def test_schema_required_matches_loader(self):
        schema = json.loads((TEMPLATES / "_schema" / "template.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(T.REQUIRED_FIELDS), sorted(schema["required"]))
        self.assertEqual(sorted(T.REQUIRED_FIELDS + T.OPTIONAL_FIELDS), sorted(schema["properties"]))
        self.assertEqual(sorted(T.SLOT_TYPES), sorted(schema["$defs"]["slot"]["properties"]["type"]["enum"]))

    def test_gitattributes_keeps_template_bytes(self):
        text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("templates/** -text", text)


class RejectBrokenTemplatesTests(TemplateFixture, unittest.TestCase):
    def test_tampered_graph_bytes_rejected(self):
        folder = self.copy("video/sam3/track-text")
        raw = (folder / "graph.api.json").read_bytes()
        (folder / "graph.api.json").write_bytes(raw.replace(b"0.5", b"0.6", 1))
        self.assertRejected("video/sam3/track-text", "sha256")

    def test_crlf_conversion_rejected_with_hint(self):
        folder = self.copy("video/sam3/track-text")
        raw = (folder / "graph.api.json").read_bytes()
        (folder / "graph.api.json").write_bytes(raw.replace(b"\n", b"\r\n"))
        self.assertRejected("video/sam3/track-text", "CRLF")

    def test_unclaimed_placeholder_rejected(self):
        def add(graph):
            graph["31"]["inputs"]["text"] = "__SOMETHING_NEW__"
        self.edit("video/sam3/track-text", lambda d: d["slots"].pop("track_text"), add)
        self.assertRejected("video/sam3/track-text", "__SOMETHING_NEW__")

    def test_wrong_node_rejected(self):
        self.edit("video/sam3/track-text", lambda d: d["slots"]["track_text"]["targets"][0].update(node="999"))
        self.assertRejected("video/sam3/track-text", "999")

    def test_duplicate_target_rejected(self):
        def dup(d):
            d["slots"]["prompt2"] = copy.deepcopy(d["slots"]["prompt"])
        self.edit("video/wan-animate/move", dup)
        self.assertRejected("video/wan-animate/move", "21.text")

    def test_unclaimed_seed_rejected(self):
        self.edit("video/wan-animate/move-extend", lambda d: d["slots"].pop("seed_segment2"))
        self.assertRejected("video/wan-animate/move-extend", "401.seed")

    def test_set_link_on_existing_input_rejected(self):
        def bad(d):
            d["options"]["keep_audio"]["when_true"][0]["input"] = "fps"
        self.edit("video/wan-animate/move", bad)
        self.assertRejected("video/wan-animate/move", "keep_audio")

    def test_option_overlapping_slot_target_rejected(self):
        def bad(d):
            d["options"]["force_text"] = {"default": False, "when_true": [
                {"op": "set_value", "node": "21", "input": "text", "value": "x"}]}
        self.edit("video/wan-animate/move", bad)
        self.assertRejected("video/wan-animate/move", "21.text")

    def test_missing_pin_forbids_technical_pass(self):
        def unpin(d):
            d["models"][-1].update(sha256=None, pin_status="測試:拿掉 pin")
        self.edit("video/wan-animate/move", unpin)
        self.assertRejected("video/wan-animate/move", "technical_pass")

    def test_model_filename_must_match_graph(self):
        self.edit("video/sam3/track-mask", lambda d: d["models"][0].update(filename="other.safetensors"))
        self.assertRejected("video/sam3/track-mask", "other.safetensors")

    def test_missing_evidence_file_rejected(self):
        self.edit("video/sam3/track-mask", lambda d: d["provenance"]["evidence"].append({"path": "docs/nope.md", "note": "x"}))
        self.assertRejected("video/sam3/track-mask", "docs/nope.md")

    def test_upload_slot_must_be_uploaded_once(self):
        self.edit("video/sam3/track-mask", lambda d: d["pre"][-1].update(slots=["source_video"]))
        self.assertRejected("video/sam3/track-mask", "seed_mask")

    def test_unknown_top_level_field_rejected(self):
        self.edit("video/sam3/track-mask", lambda d: d.update(surprise=1))
        self.assertRejected("video/sam3/track-mask", "surprise")

    def test_id_must_match_folder(self):
        self.edit("video/sam3/track-mask", lambda d: d.update(id="video/sam3/other"))
        self.assertRejected("video/sam3/track-mask", "video/sam3/other")


class OfficialFieldsTests(TemplateFixture, unittest.TestCase):
    """PR 3.2:min_comfyui_version、requires_custom_nodes、models[].directory／url、provenance.upstream。"""

    MIX = "video/wan-animate/mix"

    def model(self, data, role):
        return next(m for m in data["models"] if m["role"] == role)

    def rejected(self, change, fragment, template_id=MIX):
        self.edit(template_id, change)
        self.assertRejected(template_id, fragment)

    def accepted(self, change, template_id=MIX):
        self.edit(template_id, change)
        return self.load(template_id)

    def test_min_comfyui_version_required_and_semver(self):
        self.rejected(lambda d: d.pop("min_comfyui_version"), "缺少必填欄位 min_comfyui_version")
        shutil.rmtree(self.root)
        self.rejected(lambda d: d.update(min_comfyui_version="0.34"), "min_comfyui_version 必須是 X.Y.Z")

    def test_requires_custom_nodes(self):
        cases = [
            (lambda d: d.update(requires_custom_nodes={"id": "x"}), "requires_custom_nodes 必須是陣列"),
            (lambda d: d["requires_custom_nodes"].append({"id": "comfyui-kjnodes", "source": "registry"}), "重複"),
            (lambda d: d["requires_custom_nodes"].append({"id": "x", "source": "github"}), "source 必須是"),
            (lambda d: d["requires_custom_nodes"].append({"id": "x"}), "必須剛好有 id、source"),
            (lambda d: d["requires_custom_nodes"].append({"id": "bad id", "source": "registry"}), "id 格式不對"),
        ]
        for change, fragment in cases:
            with self.subTest(fragment):
                shutil.rmtree(self.root, ignore_errors=True)
                self.rejected(change, fragment)
        shutil.rmtree(self.root)
        loaded = self.accepted(lambda d: d["requires_custom_nodes"].append({"id": "comfyui-video-layers", "source": "repo"}))
        self.assertEqual(4, len(loaded.data["requires_custom_nodes"]))

    def test_directory_must_match_path(self):
        cases = [
            (lambda d: self.model(d, "vae").update(directory="loras"), "directory 'loras' 和 path"),
            (lambda d: self.model(d, "vae").update(directory=None), "directory None 和 path"),
            (lambda d: self.model(d, "pose_bbox").update(directory="ckpts"), "directory 要寫 null"),
            (lambda d: self.model(d, "vae").update(directory="../vae"), "directory 必須是 models/ 底下"),
            (lambda d: self.model(d, "vae").pop("directory"), "缺少 directory"),
        ]
        for change, fragment in cases:
            with self.subTest(fragment):
                shutil.rmtree(self.root, ignore_errors=True)
                self.rejected(change, fragment)

    def test_url_must_match_source(self):
        def other_revision(d):
            self.model(d, "vae")["url"] = self.model(d, "vae")["url"].replace("123acf1", "0000000")
        def unpinned_revision(d):
            self.model(d, "vae")["source"]["revision"] = "main"
            self.model(d, "vae")["url"] = T.MODEL_URL.format(**self.model(d, "vae")["source"])
        def url_without_source(d):
            self.model(d, "vae")["source"] = None
        cases = [
            (other_revision, "url 和 source 不一致"),
            (unpinned_revision, "source.revision 必須是 40 位 commit sha"),
            (url_without_source, "沒有 source 時 url 必須是 null"),
            (lambda d: self.model(d, "vae")["source"].pop("file"), "source 必須是 null 或剛好有 repo、revision、file"),
            (lambda d: self.model(d, "vae").pop("url"), "缺少 url"),
        ]
        for change, fragment in cases:
            with self.subTest(fragment):
                shutil.rmtree(self.root, ignore_errors=True)
                self.rejected(change, fragment)
        shutil.rmtree(self.root)
        loaded = self.accepted(lambda d: self.model(d, "vae").update(source=None, url=None))
        self.assertIsNone(self.model(loaded.data, "vae")["url"])

    def test_upstream(self):
        up = lambda d: d["provenance"]["upstream"]  # noqa: E731
        cases = [
            (lambda d: d["provenance"].pop("upstream"), "provenance 必須剛好有"),
            (lambda d: up(d).update(kind="github"), "provenance.upstream.kind 必須是"),
            (lambda d: up(d).update(blob="ee96a29c"), "40 位 git blob sha"),
            (lambda d: up(d).update(name="video_wan2_2_14B_animate.json"), "不含 .json"),
            (lambda d: up(d).update(kind="core_blueprint", name="Video Inpainting"), "要含 .json"),
            (lambda d: up(d).update(comfyui_version="latest"), "comfyui_version 必須是 X.Y.Z"),
            (lambda d: up(d).update(kind="none", name=None, blob=None, comfyui_version=None, note=None) or up(d).pop("note"),
             "要在 note 說明"),
            (lambda d: up(d).update(kind="none"), "name、blob、comfyui_version 都要是 null"),
            (lambda d: up(d).update(extra=1), "provenance.upstream 必須有"),
        ]
        for change, fragment in cases:
            with self.subTest(fragment):
                shutil.rmtree(self.root, ignore_errors=True)
                self.rejected(change, fragment)
        for kind, name in (("core_blueprint", "Video Inpainting (Wan2.1 VACE).json"), ("none", None)):
            with self.subTest(kind):
                shutil.rmtree(self.root, ignore_errors=True)
                blob = None if kind == "none" else "3eb700cb9478e00a3b8d8a7c415a36609193ac5e"
                version = None if kind == "none" else "0.34.0"
                loaded = self.accepted(lambda d: up(d).update(kind=kind, name=name, blob=blob, comfyui_version=version,
                                                              note="測試"))
                self.assertEqual(kind, loaded.data["provenance"]["upstream"]["kind"])

    def test_model_platforms(self):
        def pin(data, **override):
            model = data["models"][0]
            entry = {"filename": model["filename"], "sha256": model["sha256"], "size_bytes": model["size_bytes"]}
            entry.update(override)
            model["platforms"] = {"windows-cuda": entry}

        def extra_key(data):
            pin(data)
            data["models"][0]["platforms"]["windows-cuda"]["extra"] = 1

        def other_platform(data):
            pin(data)
            model = data["models"][0]
            model["platforms"]["linux-cpu"] = {
                "filename": "other.safetensors", "sha256": model["sha256"], "size_bytes": model["size_bytes"]}

        shutil.rmtree(self.root, ignore_errors=True)
        loaded = self.accepted(pin)
        self.assertEqual(loaded.data["models"][0]["filename"],
                         loaded.data["models"][0]["platforms"]["windows-cuda"]["filename"])
        shutil.rmtree(self.root, ignore_errors=True)
        self.accepted(other_platform)
        cases = [
            (lambda d: pin(d, filename="other.safetensors"), "必須等於頂層 filename"),
            (lambda d: pin(d, sha256="0" * 64), "必須等於頂層 sha256"),
            (lambda d: pin(d, size_bytes=1), "必須等於頂層 size_bytes"),
            (lambda d: d["models"][0].__setitem__("platforms", {}), "非空"),
            (lambda d: d["models"][0].__setitem__("platforms", {
                "macos-mps": {"filename": "a.safetensors", "sha256": "ab", "size_bytes": 1}}), "必須有 windows-cuda"),
            (extra_key, "必須剛好有"),
        ]
        for change, fragment in cases:
            with self.subTest(fragment):
                shutil.rmtree(self.root, ignore_errors=True)
                self.rejected(change, fragment)

    def test_parse_version(self):
        self.assertEqual((0, 34, 0), T.parse_version("0.34.0"))
        self.assertEqual((0, 34, 1), T.parse_version("v0.34.1-dev"))
        self.assertIsNone(T.parse_version("nightly"))
        self.assertIsNone(T.parse_version(None))


class VideoTemplatePlatformTests(unittest.TestCase):
    def test_windows_cuda_duplicates_the_top_level_pin(self):
        self.assertEqual(18, len(golden.VIDEO_TEMPLATE_IDS))
        for template_id in golden.VIDEO_TEMPLATE_IDS:
            data = T.load_template(TEMPLATES, template_id, repo_root=ROOT).data
            with self.subTest(template_id):
                self.assertEqual("draft", data["status"])
                self.assertEqual("0.34.0", data["min_comfyui_version"])
                self.assertEqual("untested", data["capability_gate"]["platforms"]["macos-mps"]["status"])
                for model in data["models"]:
                    self.assertEqual(["windows-cuda"], list(model["platforms"]))
                    pin = model["platforms"]["windows-cuda"]
                    self.assertEqual(model["filename"], pin["filename"])
                    self.assertEqual(model["sha256"], pin["sha256"])
                    self.assertEqual(model["size_bytes"], pin["size_bytes"])

    def test_preflight_model_check_ignores_platforms(self):
        import inspect
        from comfyui_pipeline.runner import preflight as preflight_mod
        text = inspect.getsource(preflight_mod.check_models)
        self.assertNotIn("platforms", text)
        self.assertIn("filename", text)
        self.assertIn("sha256", text)


class RealTemplateOfficialFieldsTests(unittest.TestCase):
    """8 份 template 的 3.2 欄位值(graph hash 不變由 LoadTemplatesTests 確認)。"""

    EXPECTED_VERSION = {"video/sam3/track-mask": "1.0.1", "video/sam3/track-text": "1.0.1",
                        "video/wan-animate/mix": "1.1.1", "video/wan-animate/mix-extend": "1.1.1",
                        "video/wan-animate/move": "1.1.1", "video/wan-animate/move-extend": "1.1.1",
                        "video/wan-animate/scail2": "1.0.1", "video/wan-animate/scail2-extend": "1.0.1"}
    CUSTOM = {"mix": {"comfyui_controlnet_aux", "comfyui-kjnodes", "comfyui-segment-anything-2"},
              "move": {"comfyui_controlnet_aux"}}

    def test_fields(self):
        for template_id in MOVED_IDS:
            data = T.load_template(TEMPLATES, template_id, repo_root=ROOT).data
            with self.subTest(template_id):
                self.assertEqual(self.EXPECTED_VERSION[template_id], data["version"])
                self.assertEqual("0.34.0", data["min_comfyui_version"])
                family = template_id.rsplit("/", 1)[-1].replace("-extend", "")
                self.assertEqual(self.CUSTOM.get(family, set()), {n["id"] for n in data["requires_custom_nodes"]})
                upstream = data["provenance"]["upstream"]
                self.assertEqual("workflow_templates", upstream["kind"])
                expected_blob = ("ee96a29cbac97c89d961ba7a95f219b2326c2063" if family in ("mix", "move")
                                 else "1fc5602b9c54b3517ed6af320ff281d5615e9306")
                self.assertEqual(expected_blob, upstream["blob"])
                for model in data["models"]:
                    self.assertIsNotNone(model["url"], model["filename"])


class ValueValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mix = T.load_template(TEMPLATES, "video/wan-animate/mix", repo_root=ROOT)
        cls.scail = T.load_template(TEMPLATES, "video/wan-animate/scail2", repo_root=ROOT)
        cls.text = T.load_template(TEMPLATES, "video/sam3/track-text", repo_root=ROOT)

    def resolve(self, template, values, options=None):
        return T.resolve(template, values, options, run_id="t", dry_run=True, rng=random.Random(1))

    def assertBad(self, template, values, fragment, options=None):
        with self.assertRaises(T.TemplateError) as ctx:
            self.resolve(template, values, options)
        self.assertIn(fragment, str(ctx.exception))

    def mix_values(self, **extra):
        return dict({"prompt": "p", "positive_points": '[{"x":192,"y":192}]'}, **extra)

    def test_multiple_of_16_and_32(self):
        self.assertBad(self.mix, self.mix_values(width="392"), "16")
        self.resolve(self.mix, self.mix_values(width="400"))
        self.assertBad(self.scail, {"prompt": "p", "sam3_video_object": "person", "sam3_image_object": "robot",
                                    "width": "400"}, "32")

    def test_frames_enum(self):
        self.assertBad(self.mix, self.mix_values(frames="25"), "frames")
        self.assertEqual(33, self.resolve(self.mix, self.mix_values(frames="33"))["slot_values"]["frames"])

    def test_points_must_be_inside_output(self):
        self.assertBad(self.mix, self.mix_values(positive_points='[{"x":384,"y":0}]'), "超出")
        ok = self.resolve(self.mix, self.mix_values(height="640", positive_points='[{"x":10,"y":600}]'))
        self.assertEqual([{"x": 10, "y": 600}], ok["slot_values"]["positive_points"])

    def test_points_need_one_positive_and_valid_json(self):
        self.assertBad(self.mix, self.mix_values(positive_points="[]"), "positive_points")
        self.assertBad(self.mix, self.mix_values(positive_points="not json"), "positive_points")

    def test_seed_rules(self):
        self.assertBad(self.mix, self.mix_values(seed="-1"), "seed")
        res = self.resolve(self.mix, self.mix_values(seed="auto"))
        self.assertEqual("auto", res["seed_sources"]["seed"])
        self.assertTrue(0 <= res["slot_values"]["seed"] <= T.AUTO_SEED_MAX)
        self.assertEqual("explicit", self.resolve(self.mix, self.mix_values(seed="5"))["seed_sources"]["seed"])

    def test_object_indices_pattern(self):
        base = {"prompt": "p", "sam3_video_object": "person", "sam3_image_object": "robot"}
        self.resolve(self.scail, dict(base, object_indices="0,2"))
        self.assertBad(self.scail, dict(base, object_indices="0, 2"), "object_indices")

    def test_track_text_must_be_english_noun(self):
        self.assertBad(self.text, {"track_text": "槌子"}, "track_text")

    def test_output_prefix_cannot_be_set(self):
        self.assertBad(self.text, {"track_text": "mallet", "output_prefix": "x"}, "output_prefix")

    def test_unknown_slot_and_option(self):
        self.assertBad(self.text, {"track_text": "mallet", "nope": "1"}, "nope")
        self.assertBad(self.text, {"track_text": "mallet"}, "keep_audio", options={"keep_audio": True})

    def test_untested_size_warns(self):
        res = self.resolve(self.mix, self.mix_values(width="512"))
        self.assertTrue(any("width" in w for w in res["warnings"]))


class DiffWhitelistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.move = T.load_template(TEMPLATES, "video/wan-animate/move", repo_root=ROOT)

    def patched(self, options=None):
        res = T.resolve(self.move, {"prompt": "p", "seed": "1", "reference_image": "a.png", "source_video": "b.mp4"},
                        options, run_id="t")
        return T.patch(self.move, res, {"reference_image": "r/a.png", "source_video": "r/b.mp4"})[0]

    def test_change_outside_declared_targets_rejected(self):
        graph = self.patched()
        graph["63"]["inputs"]["steps"] = 20
        with self.assertRaises(T.TemplateError) as ctx:
            T.check_patched(self.move, graph)
        self.assertIn("63.steps", str(ctx.exception))

    def test_disabled_option_target_rejected(self):
        graph = self.patched()
        graph["15"]["inputs"]["audio"] = ["23", 1]
        with self.assertRaises(T.TemplateError):
            T.check_patched(self.move, graph)
        self.assertIn("15.audio", T.check_patched(self.move, graph, ["keep_audio"]))

    def test_structural_change_rejected(self):
        graph = self.patched()
        graph["999"] = {"class_type": "Note", "inputs": {}}
        with self.assertRaises(T.TemplateError):
            T.check_patched(self.move, graph)
        graph = self.patched()
        graph["21"]["class_type"] = "Other"
        with self.assertRaises(T.TemplateError):
            T.check_patched(self.move, graph)

    def test_type_change_counts_as_change(self):
        graph = self.patched()
        graph["63"]["inputs"]["cfg"] = int(graph["63"]["inputs"]["cfg"]) if isinstance(graph["63"]["inputs"]["cfg"], float) else float(graph["63"]["inputs"]["cfg"])
        with self.assertRaises(T.TemplateError):
            T.check_patched(self.move, graph)

    def test_real_patch_requires_uploads(self):
        res = T.resolve(self.move, {"prompt": "p", "reference_image": "a.png", "source_video": "b.mp4"}, run_id="t")
        with self.assertRaises(T.TemplateError):
            T.patch(self.move, res, {"reference_image": "r/a.png"})


class GoldenGraphTests(unittest.TestCase):
    def test_golden_cases_cover_all_templates(self):
        video_cases = [case for case in golden.CASES if case[0].startswith("video/")]
        image_cases = [case for case in golden.CASES if case[0].startswith("image/")]
        self.assertEqual(18, len(golden.VIDEO_TEMPLATE_IDS))
        self.assertEqual(24 + len(golden.VIDEO_TEMPLATE_IDS), len(video_cases))
        self.assertEqual(len(image_cases), len({case[0] for case in image_cases}))
        self.assertEqual(len(video_cases) + len(image_cases), len(golden.CASES))
        self.assertEqual(set(ALL_IDS), {case[0] for case in golden.CASES})
        names = sorted(os.listdir(golden.FIXTURE_DIR))
        self.assertEqual(sorted(golden.fixture_name(c[0], c[1]) for c in golden.CASES), names)

    def test_patched_graphs_match_golden(self):
        for template_id, case, values, options in golden.CASES:
            name = golden.fixture_name(template_id, case)
            with self.subTest(name):
                expected = golden.load_fixture(name)
                actual = json.loads(json.dumps(golden.build_case(template_id, case, values, options)))
                self.assertEqual(expected["changed"], actual["changed"])  # diff 白名單
                self.assertEqual(expected["graph"], actual["graph"])
                self.assertEqual(expected["patched_graph_sha256"], actual["patched_graph_sha256"])

    def test_golden_graphs_have_no_placeholders_or_unset_seeds(self):
        for template_id, case, _values, _options in golden.CASES:
            graph = golden.load_fixture(golden.fixture_name(template_id, case))["graph"]
            for node_id, node in graph.items():
                for field, value in node["inputs"].items():
                    self.assertFalse(isinstance(value, str) and value.startswith("__"), f"{case} {node_id}.{field}")
                    self.assertFalse(isinstance(value, str) and value.startswith("<upload:"), f"{case} {node_id}.{field}")
                    if field in T.SEED_INPUTS:
                        self.assertNotEqual(-1, value, f"{case} {node_id}.{field}")

    def test_golden_diff_only_touches_declared_targets(self):
        for template_id, case, _values, options in golden.CASES:
            template = T.load_template(TEMPLATES, template_id, repo_root=ROOT)
            fixture = golden.load_fixture(golden.fixture_name(template_id, case))
            enabled = [name for name, on in fixture["options"].items() if on]
            allowed = {f"{node}.{field}" for node, field in template.declared_targets(enabled)}
            self.assertLessEqual(set(fixture["changed"]), allowed, case)


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(list(argv), root=TEMPLATES, out=out, err=err, rng=random.Random(3))
        return code, out.getvalue(), err.getvalue()

    def test_list(self):
        code, out, _ = self.run_cli("list")
        self.assertEqual(0, code)
        for template_id in ALL_IDS:
            self.assertIn(template_id, out)
        code, out, _ = self.run_cli("list", "--json")
        self.assertEqual(ALL_IDS, [row["id"] for row in json.loads(out)])

    def test_show(self):
        code, out, _ = self.run_cli("show", "video/wan-animate/mix")
        self.assertEqual(0, code)
        for fragment in ("positive_points", "keep_audio", "dw-ll_ucoco_384.onnx", "724f4ff2439e", "缺檔會自動下載",
                         "windows-cuda", "ComfyUI: 0.34.0 以上", "comfyui-kjnodes(registry)",
                         "官方來源: workflow_templates video_wan2_2_14B_animate  blob ee96a29cbac9"):
            self.assertIn(fragment, out)
        code, out, _ = self.run_cli("show", "video/sam3/track-text", "--json")
        self.assertEqual("video/sam3/track-text", json.loads(out)["id"])
        self.assertEqual(2, self.run_cli("show", "video/nope/nope")[0])

    def test_dry_run_prints_graph_and_summary(self):
        code, out, err = self.run_cli("video/sam3/track-text", "--dry-run", "--set", "track_text=mallet", "--run-id", "x")
        self.assertEqual(0, code, err)
        graph = json.loads(out)
        self.assertEqual("mallet", graph["31"]["inputs"]["text"])
        self.assertEqual("<upload:source_video>", graph["1"]["inputs"]["file"])
        self.assertEqual("gameart/video-sam3-track-text/x", graph["36"]["inputs"]["filename_prefix"])
        self.assertIn("沒有連線", err)

    def test_dry_run_json_and_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "dry")
            code, out, err = self.run_cli("video/wan-animate/scail2", "--dry-run", "--set", "prompt=p",
                                          "--set", "sam3_video_object=person", "--set", "sam3_image_object=robot",
                                          "--set", "seed=9", "--option", "keep_audio", "--output-dir", target, "--json")
            self.assertEqual(0, code, err)
            payload = json.loads(out)
            self.assertEqual({"keep_audio": True}, payload["options"])
            self.assertIn("60.audio", payload["changed_inputs"])
            self.assertEqual(9, payload["graph"]["43"]["inputs"]["noise_seed"])
            written = json.loads(Path(target, cli.DRYRUN_GRAPH).read_text(encoding="utf-8"))
            self.assertEqual(payload["graph"], written)
            summary = json.loads(Path(target, cli.DRYRUN_SUMMARY).read_text(encoding="utf-8"))
            self.assertEqual("template_dry_run", summary["kind"])
            # 非空資料夾拒絕
            self.assertEqual(2, self.run_cli("video/sam3/track-text", "--dry-run", "--set", "track_text=mallet",
                                             "--output-dir", target)[0])

    def test_set_from_file_strips_bom_and_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "prompt.txt")
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                handle.write("機器人跳舞,動作同來源\r\n")
            code, out, err = self.run_cli("video/wan-animate/move", "--dry-run", "--set", f"prompt=@{path}")
            self.assertEqual(0, code, err)
            self.assertEqual("機器人跳舞,動作同來源", json.loads(out)["21"]["inputs"]["text"])

    def test_values_file_and_set_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "v.json")
            Path(path).write_text(json.dumps({"prompt": "from file", "positive_points": [{"x": 1, "y": 2}], "seed": 4}),
                                  encoding="utf-8")
            code, out, err = self.run_cli("video/wan-animate/mix", "--dry-run", "--values", path, "--set", "seed=5")
            self.assertEqual(0, code, err)
            graph = json.loads(out)
            self.assertEqual("from file", graph["21"]["inputs"]["text"])
            self.assertEqual('[{"x":1,"y":2}]', graph["107"]["inputs"]["coordinates_positive"])
            self.assertEqual(5, graph["63"]["inputs"]["seed"])

    def test_errors_exit_2(self):
        self.assertEqual(2, self.run_cli("video/sam3/track-text", "--set", "track_text=mallet")[0])  # 沒有 --dry-run
        code, _, err = self.run_cli("video/sam3/track-text", "--dry-run", "--set", "nope=1")
        self.assertEqual(2, code)
        self.assertIn("nope", err)
        self.assertEqual(2, self.run_cli("video/sam3/track-text", "--dry-run", "--set", "track_text")[0])
        self.assertEqual(2, self.run_cli("video/wan-animate/move", "--dry-run", "--set", "prompt=p",
                                         "--option", "keep_audio", "--no-option", "keep_audio")[0])

    def test_gameart_dispatcher_registers_run_as_repo_only(self):
        import gameart
        self.assertEqual("run_template.py", gameart.TOOLS["run"][0])
        self.assertIn("run", gameart.REPO_ONLY)


if __name__ == "__main__":
    unittest.main()
