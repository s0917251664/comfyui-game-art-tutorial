import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools_src.simple_mask_tool.core import (
    build_outputs,
    load_source_image,
    normalize_editor_mask,
    selected_ratio,
    validate_token,
)


def png_bytes(image):
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class SimpleMaskCoreTests(unittest.TestCase):
    def test_token_validation_rejects_paths_and_short_values(self):
        for value in ("short", "../unsafe-token-1234567890", "bad/token_123456789012345"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_token(value)
        self.assertEqual("Abc_def-12345678901234567890", validate_token("Abc_def-12345678901234567890"))

    def test_source_normalizes_to_rgba(self):
        source = Image.new("RGB", (9, 7), (10, 20, 30))
        loaded = load_source_image(png_bytes(source))
        self.assertEqual((9, 7), loaded.size)
        self.assertEqual("RGBA", loaded.mode)

    def test_mask_must_match_source_dimensions(self):
        mask = Image.new("L", (4, 4), 255)
        with self.assertRaisesRegex(ValueError, "does not match"):
            normalize_editor_mask(png_bytes(mask), (5, 4))

    def test_selected_ratio_uses_soft_mask_coverage(self):
        mask = Image.new("L", (2, 1))
        mask.putdata([0, 255])
        self.assertAlmostEqual(0.5, selected_ratio(mask))

    def test_outputs_follow_existing_comfy_alpha_contract(self):
        source = Image.new("RGBA", (2, 1), (20, 40, 60, 255))
        mask = Image.new("L", (2, 1))
        mask.putdata([255, 0])
        editor, comfy, preview = build_outputs(source, mask)
        self.assertEqual("L", editor.mode)
        self.assertEqual("RGBA", comfy.mode)
        self.assertEqual([0, 255], list(comfy.getchannel("A").getdata()))
        self.assertEqual(source.size, preview.size)
        self.assertGreater(preview.getpixel((0, 0))[0], source.getpixel((0, 0))[0])
        self.assertEqual(source.getpixel((1, 0)), preview.getpixel((1, 0)))

    def test_rgba_mask_alpha_is_not_used_as_selection_semantics(self):
        mask = Image.new("RGBA", (1, 1), (255, 255, 255, 0))
        normalized = normalize_editor_mask(png_bytes(mask), (1, 1))
        self.assertEqual(255, normalized.getpixel((0, 0)))


if __name__ == "__main__":
    unittest.main()
