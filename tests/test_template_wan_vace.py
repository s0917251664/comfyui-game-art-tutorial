"""PR 3.4:``video/wan-vace/inpaint`` template 和 ``build_video_inpaint_wan``(generate.py video_inpaint 原本的 builder)等價。

多組參數下,runner 的 resolve → fill_from_pre → patch 產生的 graph,和 builder 用同樣的值產生的 graph 逐欄位相同。
PR 8.3 刪掉了 builder;它對這 7 組參數的輸出在刪除前凍結在 ``tests/fixtures/vace_builder_frozen.json``。
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golden_template_graphs as golden  # noqa: E402

from comfyui_pipeline.runner import template as T  # noqa: E402
FROZEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "vace_builder_frozen.json")
from comfyui_pipeline.video_catalog import VACE_NEGATIVE_DEFAULT  # noqa: E402

TEMPLATE_ID = "video/wan-vace/inpaint"
RUN_ID = "vaceeq01"
UPLOADS = {"control_video": f"{RUN_ID}/control.mkv", "mask_video": f"{RUN_ID}/mask.mkv"}
LOCAL = {"source_video": "local/source.mp4", "masks": "local/masks"}

# (名稱, slot 值, pre 結果 width／height／length)
CASES = [
    ("defaults_1024", {"prompt": "a glowing blue crystal hammer", "seed": 202}, (544, 560, 57)),
    ("small_9_frames", {"prompt": "red metal", "seed": 0}, (192, 128, 9)),
    ("max_area_81", {"prompt": "x", "seed": 2 ** 32 - 1}, (832, 480, 81)),
    ("portrait", {"prompt": "fire sword, game art", "seed": 7}, (464, 816, 33)),
    ("strength_and_negative", {"prompt": "ice", "seed": 99, "strength": 0.35, "negative": "blurry"}, (320, 320, 21)),
    ("strength_max", {"prompt": "ice", "seed": 5, "strength": 10.0}, (128, 128, 5)),
    ("local_params_do_not_touch_graph",
     {"prompt": "ice", "seed": 5, "mode": "replace", "grow": 0, "feather": 0, "pad": 0, "crop": "0,0,128,128",
      "mask_object": 3}, (128, 128, 5)),
]


class WanVaceEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = T.load_template(golden.TEMPLATES, TEMPLATE_ID, repo_root=golden.ROOT)

    def runner_graph(self, values, size):
        resolution = T.resolve(self.template, dict(LOCAL, **values), run_id=RUN_ID)
        T.fill_from_pre(self.template, resolution,
                        {"vace_work_area": {"width": size[0], "height": size[1], "length": size[2], "frames": size[2]}})
        graph, _ = T.patch(self.template, resolution, UPLOADS)
        return graph

    def builder_graph(self, name, values, size):
        """刪除前凍結的 builder 輸出(參數必須和這裡的案例完全相同)。"""
        with open(FROZEN, encoding="utf-8") as handle:
            frozen = json.load(handle)
        self.assertEqual((RUN_ID, UPLOADS), (frozen["run_id"], frozen["uploads"]))
        case = frozen["cases"][name]
        self.assertEqual((values, list(size)), (case["values"], case["size"]), name)
        self.assertEqual("58", case["output_node"])
        self.assertEqual(case["graph_canonical_sha256"], T.canonical_sha256(case["graph"]))
        return case["graph"]

    def test_runner_graph_equals_builder_field_by_field(self):
        with open(FROZEN, encoding="utf-8") as handle:
            self.assertEqual(sorted(name for name, _v, _s in CASES), sorted(json.load(handle)["cases"]))
        for name, values, size in CASES:
            with self.subTest(name):
                runner, builder = self.runner_graph(values, size), self.builder_graph(name, values, size)
                self.assertEqual(sorted(builder), sorted(runner))
                for node_id in builder:
                    self.assertEqual(builder[node_id]["class_type"], runner[node_id]["class_type"], node_id)
                    for field, value in builder[node_id]["inputs"].items():
                        got = runner[node_id]["inputs"].get(field)
                        self.assertEqual((value, type(value)), (got, type(got)), f"{node_id}.{field}")
                    self.assertEqual(set(builder[node_id]["inputs"]), set(runner[node_id]["inputs"]), node_id)
                self.assertEqual(T.canonical_sha256(builder), T.canonical_sha256(runner))

    def test_defaults_match_generate_cli_defaults(self):
        slots = self.template.slots
        self.assertEqual(VACE_NEGATIVE_DEFAULT, slots["negative"]["default"])
        # generate.py video_inpaint 的預設值:--mode keep、--grow 8、--feather 4、--pad 48、--strength 1.0、--mask-object 1
        self.assertEqual({"mode": "keep", "grow": 8, "feather": 4, "pad": 48, "strength": 1.0, "mask_object": 1},
                         {k: slots[k]["default"] for k in ("mode", "grow", "feather", "pad", "strength", "mask_object")})

    def test_template_shape(self):
        data = self.template.data
        self.assertEqual("technical_pass", data["status"])
        self.assertEqual({"windows-cuda": "technical_pass", "macos-mps": "untested"}, T.platform_summary(self.template))
        self.assertEqual(["control_video", "mask_video"], self.template.upload_slots())
        self.assertEqual(["vace_work_area", "upload"], [s["step"] for s in data["pre"]][1:])
        self.assertEqual(["check_video_output", "extract_keyframes", "paste_back", "qa_outside_mask_unchanged"],
                         [s["step"] for s in data["post"]])
        upstream = data["provenance"]["upstream"]
        self.assertEqual(("workflow_templates", "video_wan_vace_inpainting", "4af6c58919482553498d0e9f5bc7b5985030b914"),
                         (upstream["kind"], upstream["name"], upstream["blob"]))
        self.assertEqual({"wan2.1_vace_1.3B_fp16.safetensors", "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                          "wan_2.1_vae.safetensors"}, {m["filename"] for m in data["models"]})

    def test_invalid_values_rejected(self):
        bad = [({"strength": 0.0}, "strength"), ({"strength": 10.5}, "strength"), ({"mode": "erase"}, "mode"),
               ({"crop": "1,2,3"}, "crop"), ({"grow": 65}, "grow"), ({"prompt": ""}, "prompt")]
        for change, fragment in bad:
            with self.subTest(change), self.assertRaises(T.TemplateError) as ctx:
                T.resolve(self.template, {**LOCAL, "prompt": "x", "seed": 1, **change}, run_id=RUN_ID)
            self.assertIn(fragment, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
