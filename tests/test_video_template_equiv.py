"""第 6.2 階段：每一個第 6.1 階段的影片 graph golden，選對 template、填入該案例的 slot 後，
patch 結果與 golden graph 逐欄位相同。golden 本身已由 test_video_graph_golden 鎖成 builder 的輸出。
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import golden_template_graphs as template_golden  # noqa: E402
import golden_video_graphs as G  # noqa: E402

from comfyui_pipeline.runner import template as T  # noqa: E402
from comfyui_pipeline.video_catalog import CHARACTER_REF_MAX, VIDEO_CONTROL_NODES  # noqa: E402

ROOT = template_golden.ROOT
TEMPLATES = template_golden.TEMPLATES


def select_template(data):
    """依 builder 名稱與結構參數選 template。尾幀、前處理、參考圖張數會改變節點。"""
    name = data["builder"]["name"]
    kwargs = data["builder"]["kwargs"]
    args = data["builder"]["args"]
    if name == "build_img2video_wan":
        return "video/wan/img2video"
    if name == "build_img2video_h3":
        return "video/h3/img2video-last" if kwargs.get("last_image_filename") else "video/h3/img2video"
    if name == "build_pose_drive_wan":
        return f"video/wan/pose-drive-{kwargs['control_type']}"
    if name == "build_pose_drive_h3":
        return f"video/h3/pose-drive-{kwargs['control_type']}"
    if name == "build_character_video_h3":
        return f"video/h3/character-video-{len(args[1])}"
    raise AssertionError(name)


def _jsonable(value):
    return json.loads(json.dumps(value))


class VideoTemplateEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = {G.fixture_name(task, backend, case): G.load_fixture(G.fixture_name(task, backend, case))
                        for task, backend, case, _overrides in G.CASES}

    def test_every_golden_case_patches_to_the_same_graph(self):
        covered = set()
        for name, data in self.fixtures.items():
            with self.subTest(case=name):
                template_id = select_template(data)
                covered.add(template_id)
                template = T.load_template(TEMPLATES, template_id, repo_root=ROOT)
                values, uploads, local = {}, {}, {}
                for slot_name, slot in template.slots.items():
                    targets = slot.get("targets") or []
                    if not targets:
                        continue
                    node, field = targets[0]["node"], targets[0]["input"]
                    value = data["graph"][node]["inputs"][field]
                    for target in targets[1:]:
                        self.assertEqual(value, data["graph"][target["node"]]["inputs"][target["input"]], slot_name)
                    if slot.get("upload"):
                        uploads[slot_name] = value
                        local[slot_name] = f"local/{os.path.basename(value)}"
                    else:
                        values[slot_name] = value
                resolution = T.resolve(template, dict(local, **values), {}, run_id="equiv")
                graph, _changes = T.patch(template, resolution, uploads)
                actual = _jsonable(graph)
                self.assertEqual(sorted(data["graph"]), sorted(actual), name)
                for node_id, node in data["graph"].items():
                    other = actual[node_id]
                    self.assertEqual(node["class_type"], other["class_type"], f"{name} {node_id}")
                    self.assertEqual(sorted(node["inputs"]), sorted(other["inputs"]), f"{name} {node_id}")
                    for key, value in node["inputs"].items():
                        self.assertEqual(value, other["inputs"][key], f"{name} {node_id}.{key}")
                self.assertEqual(data["output_node"], template.data["outputs"][0]["node"])
        expected = {
            "video/wan/img2video", "video/h3/img2video", "video/h3/img2video-last",
            "video/h3/character-video-1", "video/h3/character-video-2",
            "video/h3/character-video-3", "video/h3/character-video-9",
            *(f"video/{backend}/pose-drive-{control}"
              for backend in ("wan", "h3") for control in ("canny", "pose", "depth")),
        }
        self.assertTrue(expected <= covered, sorted(expected - covered))
        self.assertTrue(covered <= set(template_golden.VIDEO_TEMPLATE_IDS))

    def test_structural_variants_match_builder_shape(self):
        plain = T.load_template(TEMPLATES, "video/h3/img2video", repo_root=ROOT)
        last = T.load_template(TEMPLATES, "video/h3/img2video-last", repo_root=ROOT)
        wan = T.load_template(TEMPLATES, "video/wan/img2video", repo_root=ROOT)
        self.assertNotIn("56b", plain.graph)
        self.assertNotIn("last_frame", plain.graph["104"]["inputs"])
        self.assertEqual(["56b", 0], last.graph["104"]["inputs"]["last_frame"])
        self.assertNotIn("56b", wan.graph)
        for backend in ("wan", "h3"):
            for control, class_name in VIDEO_CONTROL_NODES.items():
                template = T.load_template(TEMPLATES, f"video/{backend}/pose-drive-{control}", repo_root=ROOT)
                self.assertEqual(class_name, template.graph["82"]["class_type"], f"{backend}/{control}")
        for count in range(1, CHARACTER_REF_MAX + 1):
            template = T.load_template(TEMPLATES, f"video/h3/character-video-{count}", repo_root=ROOT)
            images = [node for node in template.graph.values() if node["class_type"] == "LoadImage"]
            self.assertEqual(count, len(images), count)
            for index in range(count):
                self.assertEqual(f"__REF_IMAGE_{index + 1}__", template.graph[f"56r{index}"]["inputs"]["image"])


if __name__ == "__main__":
    unittest.main()
