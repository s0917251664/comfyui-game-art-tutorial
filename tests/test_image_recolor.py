import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from tools_src import image_edit_tools as tool


class RecolorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.mask = self.root / 'source.png', self.root / 'mask.png'
        self.pixels = np.array([[(0, 128, 128, 120), (0, 128, 128, 255), (128, 128, 128, 200),
                                 (160, 100, 0, 255), (0, 128, 128, 0)]], dtype=np.uint8)
        Image.fromarray(self.pixels).save(self.source)
        im = Image.new('RGBA', (5, 1), 'white')
        im.putalpha(Image.fromarray(np.array([[0, 255, 0, 0, 0]], dtype=np.uint8)))
        im.save(self.mask)

    def test_recolor_changes_matching_visible_hue_only_and_preserves_alpha(self):
        report = tool.recolor(self.source, self.mask, self.root / 'out', 180, 0)
        after = np.asarray(Image.open(report['output']['path']))
        self.assertEqual(1, report['matched_pixels'])
        self.assertGreater(after[0, 0, 0], 120)
        self.assertLess(after[0, 0, 1], 5)
        self.assertEqual(128, after[0, 0, :3].max())
        np.testing.assert_array_equal(after[:, :, 3], self.pixels[:, :, 3])
        np.testing.assert_array_equal(after[:, 1:], self.pixels[:, 1:])

    def test_soft_mask_wraparound_and_cli(self):
        Image.new('RGBA', (5, 1), (128, 0, 8, 180)).save(self.source)
        mask = Image.new('RGBA', (5, 1), (0, 0, 0, 128)); mask.save(self.mask)
        code = tool.main(['recolor', '--source', str(self.source), '--mask', str(self.mask),
                          '--from-hue', '0', '--to-hue', '180', '--hue-range', '10',
                          '--output-dir', str(self.root / 'out')])
        self.assertEqual(0, code)
        pixel = Image.open(self.root / 'out/recolored.png').getpixel((0, 0))
        self.assertEqual(180, pixel[3])
        self.assertTrue(50 < pixel[0] < 80 and 50 < pixel[1] < 80)

    def test_invalid_inputs_and_empty_matches_leave_no_output(self):
        for kw in ({'from_hue': float('nan')}, {'hue_range': 181}, {'min_saturation': -1}):
            args = dict(from_hue=180, to_hue=0); args.update(kw)
            with self.assertRaises(ValueError):
                tool.recolor(self.source, self.mask, self.root / 'out', **args)
        with self.assertRaisesRegex(ValueError, 'No visible'):
            tool.recolor(self.source, self.mask, self.root / 'out', 90, 0, hue_range=1)
        self.assertFalse((self.root / 'out').exists())
        Image.new('RGB', (5, 1)).save(self.mask)
        with self.assertRaisesRegex(ValueError, 'Alpha'):
            tool.recolor(self.source, self.mask, self.root / 'out', 180, 0)

    def test_composite_keep_alpha_preserves_soft_alpha_and_rgba_outside(self):
        edited = self.root / 'edited.png'
        Image.new('RGBA', (5, 1), (200, 0, 0, 255)).save(edited)
        report = tool.composite(self.source, edited, self.mask, self.root / 'out', keep_source_alpha=True)
        result = np.asarray(Image.open(report['output']['path']))
        np.testing.assert_array_equal(result[:, :, 3], self.pixels[:, :, 3])
        np.testing.assert_array_equal(result[0, 1], self.pixels[0, 1])
        self.assertEqual((200, 0, 0, 120), tuple(result[0, 0]))


if __name__ == '__main__':
    unittest.main()
