import optional_deps

optional_deps.require("PIL", "numpy")

import argparse
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools_src"))
import comfyui_design as d  # noqa: E402


class DesignTests(unittest.TestCase):
    def icon(self):
        im = Image.new("RGBA", (100, 100))
        ImageDraw.Draw(im).rectangle((30, 10, 69, 89), fill=(200, 50, 20, 40))
        return im

    def bands(self):
        im = Image.new("RGBA", (400, 400), (0, 255, 0, 255))
        draw = ImageDraw.Draw(im)
        draw.rectangle((0, 0, 399, 49), fill=(255, 0, 0, 255))
        draw.rectangle((0, 350, 399, 399), fill=(0, 0, 255, 255))
        return im

    def test_scene_preserves_aspect_uses_source_alpha_and_exact_canvas(self):
        background = Image.new("RGBA", (400, 400), (10, 20, 30, 255))
        image, size, placements = d.compose(
            "scene", [self.icon()], background=background, x=100, y=50, width=100, height=200)
        self.assertEqual(size, (400, 400))
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(placements, [{"input": 0, "box": [100, 50, 100, 200]}])
        self.assertEqual(image.getpixel((99, 149)), (10, 20, 30))
        # alpha 40 是來源權重。若用 255-alpha，這個像素會靠近物件色而不是背景。
        weight = 40 / 255
        expected = tuple(int(round(s * weight + b * (1 - weight)))
                         for s, b in zip((200, 50, 20), (10, 20, 30)))
        self.assertEqual(image.getpixel((150, 150)), expected)
        self.assertLess(expected[0], 80)

    def test_pattern_uses_one_scaled_motif_and_spacing_proves_no_edge_crossing(self):
        image, size, placements = d.compose(
            "pattern", [self.icon()], cell=128, columns=3, rows=2, padding=24)
        self.assertEqual(size, (384, 256))
        self.assertEqual(image.size, size)
        self.assertEqual(len(placements), 6)
        self.assertEqual({p["input"] for p in placements}, {0})
        for placement in placements:
            x, y, w, h = placement["box"]
            self.assertGreaterEqual(x, 24)
            self.assertGreaterEqual(y, 24)
            self.assertLessEqual(x + w, size[0] - 24)
            self.assertLessEqual(y + h, size[1] - 24)
        self.assertEqual(image.getpixel((0, 0)), (0xF5, 0xF0, 0xE5))

    def test_sheet_places_each_input_once(self):
        image, size, placements = d.compose(
            "sheet", [self.icon(), self.icon()], cell=128, columns=2)
        self.assertEqual(size, (256, 128))
        self.assertEqual(image.size, size)
        self.assertEqual([item["input"] for item in placements], [0, 1])

    def test_chinese_title_bad_color_and_overflow_rejected(self):
        with self.assertRaises(ValueError):
            d.compose("sheet", [self.icon()], title="藥水")
        with self.assertRaises(ValueError):
            d.rgb_color("#zzz000")
        with self.assertRaises(ValueError):
            d.compose("scene", [self.icon()], background=Image.new("RGBA", (200, 200), (1, 2, 3, 255)),
                      x=100, y=100, width=101, height=100)
        with self.assertRaises(ValueError):
            d.compose("pattern", [self.icon(), self.icon()])

    def test_canvas_resize_crops_background_only_and_centers_object_box(self):
        image, size, placements = d.compose(
            "scene", [self.icon()], background=self.bands(), x=500, y=50, width=200, height=400,
            canvas_width=800, canvas_height=600)
        self.assertEqual(size, (800, 600))
        self.assertEqual(placements[0]["box"], [500, 50, 200, 400])
        # 400×400 上下各 50px 色帶被中心裁掉，輸出背景是中間的綠。
        self.assertEqual(image.getpixel((0, 0)), (0, 255, 0))
        self.assertEqual(image.getpixel((499, 250)), (0, 255, 0))
        self.assertNotEqual(image.getpixel((600, 250)), (0, 255, 0))

    def test_opaque_object_rejected_without_touching_comfy_or_output(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            image = root / "i.png"
            out = root / "out"
            Image.new("RGB", (64, 64), "red").save(image)
            args = argparse.Namespace(
                command="sheet", images=[str(image)], comfy_url="http://127.0.0.1:8188", config=None,
                timeout=30, background=None, x=0, y=0, width=128, height=128, cell=128, columns=2, padding=24,
                rows=2, color="#ffffff", title="", caption="", canvas_width=None, canvas_height=None,
                output_dir=str(out))
            with patch("comfyui_pipeline.client.upload_image") as upload, \
                    patch("comfyui_pipeline.client.submit_and_wait") as queue, \
                    patch("comfyui_pipeline.client._fetch_comfy_object_info") as fetch, \
                    patch("comfyui_pipeline.client.resolve_comfy_url") as resolve:
                with self.assertRaises(ValueError):
                    d.run(args)
                upload.assert_not_called()
                queue.assert_not_called()
                fetch.assert_not_called()
                resolve.assert_not_called()
                self.assertFalse(out.exists())
                self.icon().save(image)
                report = d.run(args)
                upload.assert_not_called()
                queue.assert_not_called()
                fetch.assert_not_called()
                resolve.assert_not_called()
            self.assertFalse(report["model_generation"])
            self.assertEqual(report["dimensions"], [256, 128])
            self.assertTrue((out / "design_sheet.png").is_file())
            self.assertFalse((out / "failure.json").exists())
            with Image.open(out / "design_sheet.png") as output:
                self.assertEqual(output.size, (256, 128))
                self.assertEqual(output.mode, "RGB")


if __name__ == "__main__":
    unittest.main()
