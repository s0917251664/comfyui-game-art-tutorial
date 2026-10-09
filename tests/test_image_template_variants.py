"""圖片 template 的完整性:selector 列出的每個 variant 都有 template.json,且保留固定的前綴與時間對齊設定。

templates/ 是圖片 graph 的唯一來源(Python builder 已移除),這裡只檢查目錄完整與欄位不變式;
graph 內容由 test_image_task_template 對照凍結 golden。
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golden_image_graphs as image_golden  # noqa: E402

from comfyui_pipeline.image_template_select import iter_variant_ids  # noqa: E402
from comfyui_pipeline.runner import template as T  # noqa: E402

ROOT = Path(image_golden.ROOT)
TEMPLATES = ROOT / "templates"


def _template_path(template_id):
    return TEMPLATES.joinpath(*template_id.split("/")) / "template.json"


class ImageTemplateVariantTests(unittest.TestCase):
    def test_selector_counts_and_required_directories(self):
        self.assertEqual(72, len(iter_variant_ids("sdxl")))
        self.assertEqual(1, len(iter_variant_ids("layer_split")))
        self.assertEqual(2, len(iter_variant_ids("flux2")))
        for template_id in iter_variant_ids("sdxl", "layer_split", "flux2"):
            self.assertTrue(_template_path(template_id).is_file(), template_id)
        self.assertFalse(_template_path("image/sd15/concept").is_file())

    def test_image_templates_keep_prefix_and_null_alignment(self):
        for template_id in iter_variant_ids("sdxl", "layer_split", "flux2"):
            template = T.load_template(TEMPLATES, template_id, repo_root=ROOT)
            self.assertIsNone(template.data["frame_anchoring"]["time_alignment"], template_id)
            self.assertEqual("draft", template.data["status"], template_id)
            for name, slot in template.slots.items():
                self.assertNotEqual("output_prefix", slot["type"], f"{template_id}.{name}")
            prefix = template.slots["filename_prefix"]
            self.assertEqual("string", prefix["type"], template_id)
            self.assertFalse(str(prefix["default"]).startswith("gameart/"), template_id)


if __name__ == "__main__":
    unittest.main()
