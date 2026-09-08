import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tools_src.sam_segment import (
    build_contact_sheet,
    build_cutout,
    normalize_candidates,
    save_candidates,
    tensor_mask_to_l,
)


class FakeScore:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class SamSegmentTests(unittest.TestCase):
    def test_tensor_mask_normalizes_shape_and_size(self):
        mask = np.zeros((1, 2, 3), dtype=np.float32)
        mask[0, 0, 1] = 1
        result = tensor_mask_to_l(mask, (6, 4))
        self.assertEqual("L", result.mode)
        self.assertEqual((6, 4), result.size)
        self.assertEqual({0, 255}, set(result.getdata()))

    def test_candidates_are_filtered_sorted_and_limited(self):
        empty = np.zeros((4, 4), dtype=np.uint8)
        small = empty.copy()
        small[:2, :2] = 1
        large = empty.copy()
        large[:3, :] = 1
        result = normalize_candidates(
            [empty, small, large], [FakeScore(0.99), FakeScore(0.7), FakeScore(0.9)], (4, 4), 1
        )
        self.assertEqual(1, len(result))
        self.assertEqual(3, result[0]["source_index"])

    def test_cutout_uses_selected_white_as_visible_alpha(self):
        source = Image.new("RGBA", (2, 1), (10, 20, 30, 255))
        mask = Image.new("L", (2, 1))
        mask.putdata([255, 0])
        cutout = build_cutout(source, mask)
        self.assertEqual([255, 0], list(cutout.getchannel("A").getdata()))

    def test_save_candidates_emits_contract_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_path = root / "source_input.png"
            Image.new("RGBA", (8, 6), (10, 20, 30, 255)).save(source_path)
            mask = Image.new("L", (8, 6), 0)
            for y in range(2, 5):
                for x in range(2, 6):
                    mask.putpixel((x, y), 255)
            manifest = save_candidates(
                source_path,
                root / "out",
                [{"source_index": 1, "score": 0.95, "selected_ratio": 0.25, "editor_mask": mask}],
            )
            self.assertEqual(1, manifest["candidate_count"])
            for name in (
                "candidate_01_mask_editor.png",
                "candidate_01_mask_comfy.png",
                "candidate_01_preview.png",
                "candidate_01_cutout.png",
                "contact_sheet.png",
                "manifest.json",
                "source.png",
            ):
                self.assertTrue((root / "out" / name).is_file(), name)
            comfy = Image.open(root / "out" / "candidate_01_mask_comfy.png")
            self.assertEqual((0, 255), comfy.getchannel("A").getextrema())

    def test_contact_sheet_has_expected_grid(self):
        previews = [Image.new("RGBA", (100, 200), "white") for _ in range(4)]
        sheet = build_contact_sheet(previews, ["a", "b", "c", "d"], thumb_width=60)
        self.assertEqual((180, 324), sheet.size)


if __name__ == "__main__":
    unittest.main()
