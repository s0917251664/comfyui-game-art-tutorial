"""extract_last_frame 與 camera_end_still：只做既有的抽尾幀與運鏡終點靜幀，清單外的名稱仍拒絕。"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comfyui_pipeline.runner import media as media_mod  # noqa: E402
from comfyui_pipeline.runner import steps as S  # noqa: E402
from comfyui_pipeline.runner import template as T  # noqa: E402

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

TEMPLATE_ID = "video/test/frame-steps"
REPO = Path(__file__).resolve().parents[1]
GRAPH = {
    "56": {"class_type": "LoadImage", "inputs": {"image": "__LAST__"}},
    "56b": {"class_type": "LoadImage", "inputs": {"image": "__STILL__"}},
    "58": {"class_type": "SaveVideo", "inputs": {"video": ["56", 0], "filename_prefix": "frame"}},
}


def _template_data(graph_sha, canonical):
    target = lambda node, field, placeholder: [{"node": node, "input": field, "placeholder": placeholder}]
    return {
        "schema_version": 1, "id": TEMPLATE_ID, "version": "0.1.0", "title": "尾幀與運鏡步驟",
        "summary": "測試用", "status": "draft", "status_note": "測試用",
        "min_comfyui_version": "0.34.0", "requires_custom_nodes": [],
        "graph": {"file": "graph.api.json", "format": "comfyui-api", "sha256": graph_sha,
                  "canonical_sha256": canonical},
        "provenance": {"derived_from": "測試", "tested_source_sha256": None,
                       "upstream": {"kind": "none", "name": None, "blob": None, "comfyui_version": None,
                                    "note": "測試用，沒有官方對應"},
                       "evidence": [{"path": "templates/README.md", "note": "步驟說明"}]},
        "slots": {
            "clip": {"type": "video", "targets": [], "required": True, "help": "上一鏡"},
            "source_image": {"type": "image", "targets": [], "required": True, "help": "運鏡起點"},
            "camera": {"type": "string", "targets": [], "default": "static",
                       "validate": {"enum": ["static", "zoom_in", "pan_left", "orbit_cw"]}},
            "width": {"type": "int", "targets": [], "default": 64, "validate": {"min": 8, "multiple_of": 8}},
            "height": {"type": "int", "targets": [], "default": 64, "validate": {"min": 8, "multiple_of": 8}},
            "last_frame": {"type": "image", "upload": True, "generated": True,
                           "targets": target("56", "image", "__LAST__")},
            "end_still": {"type": "image", "upload": True, "generated": True,
                          "targets": target("56b", "image", "__STILL__")},
        },
        "pre": [
            {"step": "extract_last_frame", "video": "clip", "image": "last_frame"},
            {"step": "camera_end_still", "image": "source_image", "camera": "{camera}",
             "width": "{width}", "height": "{height}", "still": "end_still"},
            {"step": "upload", "slots": ["last_frame", "end_still"]},
        ],
        "post": [],
        "frame_anchoring": {"first": "image", "last": "image", "reference_role": "none",
                            "time_alignment": "source_from_frame_0", "continuity": None},
        "models": [],
        "capability_gate": {"nodes": "from_graph", "selectors": "from_models", "files": "from_models",
                            "platforms": {"windows-cuda": {"status": "untested"}},
                            "min_memory_mb": None, "capability": "i2v"},
        "outputs": [{"id": "video", "node": "58", "kind": "video", "role": "candidate"}],
    }


def write_step_template(root, change=None):
    folder = Path(root) / TEMPLATE_ID
    folder.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(GRAPH, indent=2) + "\n").encode("utf-8")
    (folder / "graph.api.json").write_bytes(raw)
    data = _template_data(T.file_sha256(folder / "graph.api.json"), T.canonical_sha256(GRAPH))
    if change:
        change(data)
    (folder / "template.json").write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return folder


class StepListTests(unittest.TestCase):
    def test_unknown_name_and_bad_params_rejected(self):
        slots = {"clip": {"type": "video"}, "last_frame": {"type": "image"}}
        unknown = S.validate_steps([{"step": "run_python", "code": "x"}], "pre", slots, {}, set())
        self.assertTrue(any("不在步驟清單內" in item for item in unknown))
        extra = S.validate_steps(
            [{"step": "extract_last_frame", "video": "clip", "image": "last_frame", "code": "print(1)"}],
            "pre", slots, {}, set())
        self.assertTrue(any("不接受參數" in item for item in extra))
        missing = S.validate_steps(
            [{"step": "extract_last_frame", "video": "missing", "image": "{nope}"}],
            "pre", slots, {}, set())
        self.assertTrue(any("missing" in item for item in missing))
        self.assertTrue(any("nope" in item for item in missing))

    def test_named_steps_load_on_a_template(self):
        root = Path(tempfile.mkdtemp()) / "templates"
        self.addCleanup(shutil.rmtree, root.parent, True)
        write_step_template(root)
        template = T.load_template(root, TEMPLATE_ID, repo_root=REPO)
        self.assertEqual(["extract_last_frame", "camera_end_still", "upload"],
                         [step["step"] for step in template.data["pre"]])

    def test_bad_generated_flag_rejected(self):
        root = Path(tempfile.mkdtemp()) / "templates"
        self.addCleanup(shutil.rmtree, root.parent, True)
        write_step_template(root, lambda data: data["slots"]["last_frame"].pop("generated"))
        with self.assertRaises(T.TemplateError) as ctx:
            T.load_template(root, TEMPLATE_ID, repo_root=REPO)
        self.assertIn("generated", str(ctx.exception))


class RunStepTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.image = os.path.join(self.tmp, "start.png")
        if PILImage is not None:
            PILImage.new("RGB", (80, 60), (12, 34, 56)).save(self.image)

    def test_media_wrappers_call_the_existing_functions(self):
        with mock.patch("comfyui_pipeline.video_media.extract_last_frame", return_value="out.png") as impl:
            self.assertEqual("out.png", media_mod.extract_last_frame("a.mp4", "out.png"))
        impl.assert_called_once_with("a.mp4", "out.png")
        with mock.patch("comfyui_pipeline.video_graphs.build_camera_end_still", return_value=None) as still:
            self.assertIsNone(media_mod.camera_end_still("a.png", "orbit_cw", 64, 48, "b.png"))
        still.assert_called_once_with("a.png", "orbit_cw", 64, 48, "b.png")

    def test_extract_last_frame_publishes_the_png(self):
        seen = {}

        class Media:
            def extract_last_frame(self, video_path, dest_path):
                seen["video"] = video_path
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as handle:
                    handle.write(b"png")
                return dest_path

        context = {"generated": {}}
        template = SimpleNamespace(data={"pre": [
            {"step": "extract_last_frame", "video": "clip", "image": "last_frame"}]})
        resolution = {"slot_values": {}, "options": {}, "inputs": {"clip": os.path.join(self.tmp, "clip.mp4")}}
        _results, _checks, problems, _warnings = S.run_pre_checks(
            template, resolution, Media(), work_dir=self.tmp, context=context)
        self.assertEqual([], problems)
        self.assertTrue(context["generated"]["last_frame"].endswith(os.path.join("work", "last_frame.png")))
        self.assertTrue(os.path.isfile(context["generated"]["last_frame"]))
        self.assertTrue(seen["video"].endswith("clip.mp4"))

    def test_extract_requires_work_dir(self):
        template = SimpleNamespace(data={"pre": [
            {"step": "extract_last_frame", "video": "clip", "image": "last_frame"}]})
        resolution = {"slot_values": {}, "options": {}, "inputs": {"clip": "clip.mp4"}}
        _results, _checks, problems, _warnings = S.run_pre_checks(template, resolution, SimpleNamespace(), work_dir=None)
        self.assertTrue(any("work_dir" in item for item in problems))

    def test_camera_end_still_writes_static_zoom_and_pan_and_skips_orbit(self):
        if PILImage is None:
            self.skipTest("需要 Pillow")
        pre = [{"step": "camera_end_still", "image": "source_image", "camera": "{camera}",
                "width": "{width}", "height": "{height}", "still": "end_still"}]
        for camera in ("static", "zoom_in", "pan_left"):
            work = os.path.join(self.tmp, camera)
            context = {"generated": {}}
            template = SimpleNamespace(data={"pre": pre})
            resolution = {"slot_values": {"camera": camera, "width": 64, "height": 48}, "options": {},
                          "inputs": {"source_image": self.image}}
            _results, _checks, problems, _warnings = S.run_pre_checks(
                template, resolution, media_mod, work_dir=work, context=context)
            self.assertEqual([], problems, camera)
            written = context["generated"]["end_still"]
            self.assertTrue(written.endswith(os.path.join("work", "camera_end.png")))
            with PILImage.open(written) as image:
                self.assertEqual((64, 48), image.size)
        work = os.path.join(self.tmp, "orbit")
        context = {"generated": {}}
        template = SimpleNamespace(data={"pre": pre})
        resolution = {"slot_values": {"camera": "orbit_cw", "width": 64, "height": 48}, "options": {},
                      "inputs": {"source_image": self.image}}
        _results, _checks, problems, _warnings = S.run_pre_checks(
            template, resolution, media_mod, work_dir=work, context=context)
        self.assertNotIn("end_still", context["generated"])
        self.assertTrue(any("沒有終點靜幀" in item for item in problems))
        self.assertFalse(os.path.isfile(os.path.join(work, "work", "camera_end.png")))


if __name__ == "__main__":
    unittest.main()
