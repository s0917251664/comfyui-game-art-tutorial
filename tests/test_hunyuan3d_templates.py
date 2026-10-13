"""3d/hunyuan3d-2mv/*：graph 與官方 workflow 逐欄相同、cutout 只多去背分支、GLB 輸出的下載與技術檢查。"""
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golden_template_graphs as golden  # noqa: E402

from comfyui_pipeline.runner import run as R  # noqa: E402
from comfyui_pipeline.runner import steps as S  # noqa: E402
from comfyui_pipeline.runner import template as T  # noqa: E402

ROOT = Path(golden.ROOT)
TEMPLATES = Path(golden.TEMPLATES)
BASE = "3d/hunyuan3d-2mv/multiview"
CUTOUT = "3d/hunyuan3d-2mv/multiview-cutout"
OFFICIAL = TEMPLATES / BASE / "source" / "3d_hunyuan3d_multiview_to_model.json"
# 官方 UI workflow 的 widgets_values 對應到 API 輸入名稱（seed 與 control_after_generate 由 runner 處理）
WIDGETS = {
    "ImageOnlyCheckpointLoader": ["ckpt_name"],
    "ModelSamplingAuraFlow": ["shift"],
    "EmptyLatentHunyuan3Dv2": ["resolution", "batch_size"],
    "KSampler": ["seed", None, "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "VAEDecodeHunyuan3D": ["num_chunks", "octree_resolution"],
    "VoxelToMesh": ["algorithm", "threshold"],
    "CLIPVisionEncode": ["crop"],
}


def official_api():
    ui = json.loads(OFFICIAL.read_text(encoding="utf-8"))
    links = {link[0]: link for link in ui["links"]}
    nodes = {}
    for node in ui["nodes"]:
        if node["type"] == "MarkdownNote":
            continue
        inputs = {}
        for slot in node.get("inputs") or []:
            if slot.get("link") is not None:
                link = links[slot["link"]]
                inputs[slot["name"]] = [str(link[1]), link[2]]
        for name, value in zip(WIDGETS.get(node["type"], []), node.get("widgets_values") or []):
            if name:
                inputs[name] = value
        nodes[str(node["id"])] = {"class_type": node["type"], "inputs": inputs}
    return nodes


def tiny_glb(path, vertices=3):
    doc = {"asset": {"version": "2.0"}, "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"count": vertices, "componentType": 5126, "type": "VEC3"}]}
    js = json.dumps(doc).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    with open(path, "wb") as handle:
        handle.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js)))
        handle.write(struct.pack("<II", len(js), 0x4E4F534A) + js)


class Hunyuan3DTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = T.load_template(TEMPLATES, BASE, repo_root=ROOT)
        cls.cutout = T.load_template(TEMPLATES, CUTOUT, repo_root=ROOT)

    def test_base_graph_matches_official_field_by_field(self):
        official = official_api()
        graph = self.base.graph
        self.assertEqual(set(official), set(graph))
        for node_id, node in official.items():
            with self.subTest(node_id):
                self.assertEqual(node["class_type"], graph[node_id]["class_type"])
                for name, value in node["inputs"].items():
                    if node["class_type"] == "LoadImage" or name == "seed":
                        continue
                    self.assertEqual(value, graph[node_id]["inputs"][name], name)
        # 只有存檔前綴和官方不同（官方 mesh/ComfyUI）
        self.assertEqual("3d/hunyuan3d_multiview", graph["83"]["inputs"]["filename_prefix"])

    def test_both_sources_are_the_unmodified_official_file(self):
        self.assertEqual(OFFICIAL.read_bytes(), (TEMPLATES / CUTOUT / "source" / OFFICIAL.name).read_bytes())
        for template in (self.base, self.cutout):
            self.assertEqual("3d_hunyuan3d_multiview_to_model", template.data["provenance"]["upstream"]["name"])

    def test_cutout_only_adds_background_removal_before_clip_vision(self):
        base, cut = self.base.graph, self.cutout.graph
        extra = set(cut) - set(base)
        self.assertEqual({"200", "201"} | {str(i) for i in range(210, 222)}, extra)
        self.assertEqual(set(base), set(cut) & set(base))
        for load, enc in (("56", "51"), ("78", "79"), ("80", "81"), ("87", "86")):
            comp = cut[enc]["inputs"]["image"][0]
            self.assertEqual("ImageCompositeMasked", cut[comp]["class_type"])
            self.assertEqual([load, 0], cut[comp]["inputs"]["destination"])
            self.assertTrue(cut[comp]["inputs"]["resize_source"])
            mask = cut[cut[comp]["inputs"]["mask"][0]]
            self.assertEqual("InvertMask", mask["class_type"])
            self.assertEqual("RemoveBackground", cut[mask["inputs"]["mask"][0]]["class_type"])
        self.assertEqual(16777215, cut["201"]["inputs"]["color"])
        for node_id in base:
            if node_id in ("51", "79", "81", "86", "83"):
                continue
            self.assertEqual(base[node_id], cut[node_id], node_id)

    def test_slots_defaults_and_outputs(self):
        for template in (self.base, self.cutout):
            slots = template.slots
            self.assertEqual({"front_image", "left_image", "back_image", "right_image", "seed", "steps", "cfg",
                              "filename_prefix"}, set(slots))
            self.assertEqual(20, slots["steps"]["default"])
            self.assertEqual(7.5, slots["cfg"]["default"])
            self.assertEqual([{"id": "mesh", "node": "83", "kind": "model_3d", "role": "candidate"}],
                             template.data["outputs"])
            self.assertEqual("check_model_3d", template.data["post"][0]["step"])
            self.assertEqual("hunyuan3d-dit-v2-mv_fp16.safetensors", template.data["models"][0]["filename"])
            self.assertEqual(40, len(template.data["models"][0]["source"]["revision"]))

    def test_history_3d_key_is_downloaded(self):
        items = R._history_items({"3d": [{"filename": "m.glb", "subfolder": "3d", "type": "output"}]})
        self.assertEqual([("3d", {"filename": "m.glb", "subfolder": "3d", "type": "output"})], items)

    def test_glb_stats_and_post_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = os.path.join(tmp, "good.glb"), os.path.join(tmp, "bad.glb")
            tiny_glb(good, vertices=150)
            self.assertEqual({"meshes": 1, "primitives": 1, "vertices": 150, "bytes": os.path.getsize(good)},
                             S.glb_stats(good))
            with open(bad, "wb") as handle:
                handle.write(b"not a glb file at all")
            with self.assertRaises(ValueError):
                S.glb_stats(bad)
            resolution = {"slot_values": {}, "options": {}, "inputs": {}}
            checks, problems, _w, artifacts = S.run_post_checks(self.base, resolution, {}, {"mesh": [good]}, tmp, None)
            self.assertEqual([], problems)
            self.assertEqual(150, artifacts["media"][good]["vertices"])
            tiny_glb(good, vertices=10)
            _c, problems, _w, _a = S.run_post_checks(self.base, resolution, {}, {"mesh": [good]}, tmp, None)
            self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()
