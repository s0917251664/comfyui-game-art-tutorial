"""video/wan-vace/inpaint-reference：inpaint 加參考圖分支，其餘節點不變。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools_src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comfyui_pipeline.runner import template as T  # noqa: E402
import golden_template_graphs as golden  # noqa: E402

ID = "video/wan-vace/inpaint-reference"
BASE = "video/wan-vace/inpaint"
REF_NODES = {"90", "91", "92", "93", "94", "95"}
PRE = {"vace_work_area": {"frames": 56, "width": 544, "height": 560, "length": 57}}


class InpaintReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = T.load_template(golden.TEMPLATES, ID, repo_root=golden.ROOT)
        cls.base = T.load_template(golden.TEMPLATES, BASE, repo_root=golden.ROOT)

    def _patched(self, **values):
        values = dict({"source_video": "local/source.mp4", "masks": "local/masks",
                       "reference_image": "local/ref.png", "prompt": "a hammer", "seed": 7}, **values)
        resolution = T.resolve(self.template, values, {}, run_id="test")
        T.fill_from_pre(self.template, resolution, PRE)
        uploads = {name: f"run/{name}" for name in self.template.upload_slots()}
        graph, _ = T.patch(self.template, resolution, uploads)
        return graph, resolution

    def test_base_nodes_unchanged_except_reference_link(self):
        for node, data in self.base.graph.items():
            mine = self.template.graph[node]
            if node == "55":
                inputs = dict(mine["inputs"])
                self.assertEqual(["95", 0], inputs.pop("reference_image"))
                self.assertEqual(data["inputs"], inputs)
            else:
                self.assertEqual(data, mine, node)
        self.assertEqual(REF_NODES, set(self.template.graph) - set(self.base.graph))
        self.assertEqual(self.base.data["models"], self.template.data["models"])

    def test_reference_chain_white_canvas_then_fit_to_work_area(self):
        graph, _ = self._patched()
        self.assertEqual("run/reference_image", graph["90"]["inputs"]["image"])
        self.assertEqual(16777215, graph["92"]["inputs"]["color"])
        self.assertEqual(["90", 1], graph["93"]["inputs"]["mask"])
        self.assertEqual({"destination": ["92", 0], "source": ["90", 0], "mask": ["93", 0]},
                         {k: graph["94"]["inputs"][k] for k in ("destination", "source", "mask")})
        pad = graph["95"]["inputs"]
        self.assertEqual((544, 560, "white"), (pad["target_width"], pad["target_height"], pad["padding_color"]))
        self.assertEqual((544, 560), (graph["55"]["inputs"]["width"], graph["55"]["inputs"]["height"]))
        self.assertEqual(["55", 3], graph["56"]["inputs"]["trim_amount"])

    def test_defaults_and_gates(self):
        _, resolution = self._patched()
        self.assertEqual("replace", resolution["slot_values"]["mode"])
        self.assertEqual("draft", self.template.data["status"])
        for platform in self.template.data["capability_gate"]["platforms"].values():
            self.assertEqual("untested", platform["status"])
        upload = [s for s in self.template.data["pre"] if s["step"] == "upload"][0]
        self.assertIn("reference_image", upload["slots"])

    def test_reference_required(self):
        with self.assertRaises(T.TemplateError):
            T.resolve(self.template, {"source_video": "a.mp4", "masks": "m", "prompt": "p"}, {}, run_id="t")

    def test_base_template_untouched(self):
        self.assertEqual("fd9a75dac3b3742316d06be169d7925707dca84256882b561c0fe646df773f75",
                         self.base.graph_sha256)


if __name__ == "__main__":
    unittest.main()
