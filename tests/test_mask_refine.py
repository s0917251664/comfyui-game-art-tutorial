import unittest
import numpy as np
from PIL import Image, ImageDraw
from tools_src.mask_refine import refine_mask
from tools_src.simple_mask_tool.core import build_outputs


class MaskRefineTests(unittest.TestCase):
    def fixture(self):
        source = Image.new('RGB', (160, 160), 'white')
        ImageDraw.Draw(source).ellipse((40, 40, 120, 120), fill=(25, 70, 160))
        rough = Image.new('L', source.size, 0)
        ImageDraw.Draw(rough).rectangle((32, 32, 128, 128), fill=255)
        return source, rough

    def test_removes_overshoot_using_image_and_never_expands(self):
        source, rough = self.fixture()
        candidate, info = refine_mask(source, rough, radius=32, feather=0)
        self.assertEqual(255, candidate.getpixel((80, 80)))
        self.assertEqual(0, candidate.getpixel((35, 35)))
        self.assertTrue(np.all(np.asarray(candidate) <= np.asarray(rough)))
        self.assertLess(info['candidate_selected_pixels'], info['original_selected_pixels'])
        self.assertEqual('candidate', info['status'])

    def test_soft_edges_survive_comfy_alpha_export(self):
        source, rough = self.fixture()
        candidate, _ = refine_mask(source, rough, radius=32, feather=2)
        values = np.asarray(candidate)
        self.assertTrue(((values > 0) & (values < 255)).any())
        _, comfy, _ = build_outputs(source.convert('RGBA'), candidate)
        np.testing.assert_array_equal(255 - values, np.asarray(comfy.getchannel('A')))

    def test_shrink_reduces_area(self):
        source, rough = self.fixture()
        baseline, _ = refine_mask(source, rough, radius=32, feather=0)
        smaller, _ = refine_mask(source, rough, radius=32, shrink=3, feather=0)
        self.assertLess(np.asarray(smaller).sum(), np.asarray(baseline).sum())

    def test_invalid_input_and_empty_selection(self):
        source, rough = self.fixture()
        for args in ({'radius': 0}, {'radius': True}, {'feather': -1}, {'shrink': 17}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                refine_mask(source, rough, **args)
        with self.assertRaises(ValueError):
            refine_mask(source, Image.new('L', source.size, 0))
        with self.assertRaises(ValueError):
            refine_mask(source, Image.new('L', (10, 10), 255))

    def test_transparent_source_is_preserved(self):
        source, rough = self.fixture()
        source = source.convert('RGBA')
        ImageDraw.Draw(source).rectangle((40, 40, 50, 70), fill=(25, 70, 160, 0))
        candidate, _ = refine_mask(source, rough, radius=32)
        self.assertEqual(0, candidate.getpixel((45, 60)))


if __name__ == '__main__':
    unittest.main()
