import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from tools_src.image_edit_tools import asset_audit, reference_board


class AssetToolsTests(unittest.TestCase):
    def test_audit_distinguishes_rgb_empty_and_partial_alpha(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rgb = root / 'rgb.png'
            Image.new('RGB', (8, 8), 'white').save(rgb)
            report = asset_audit(rgb, root / 'rgb-audit')
            self.assertFalse(report['has_alpha'])
            self.assertIn('no_alpha_channel', report['findings'])
            empty = root / 'empty.png'
            Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(empty)
            self.assertIsNone(asset_audit(empty, root / 'empty-audit')['visible_bbox'])
            partial = Image.new('RGBA', (8, 8), (0, 0, 0, 0))
            partial.putpixel((3, 3), (255, 0, 0, 128))
            path = root / 'partial.png'
            partial.save(path)
            before = path.read_bytes()
            report = asset_audit(path, root / 'partial-audit')
            self.assertEqual([3, 3, 4, 4], report['visible_bbox'])
            self.assertEqual(1, report['partial_alpha_pixels'])
            self.assertNotIn('visible_pixels_touch_canvas_edge', report['findings'])
            self.assertEqual(before, path.read_bytes())
            with Image.open(root / 'partial-audit/preview_black.png') as preview:
                self.assertEqual((8, 8), preview.size)
            with self.assertRaises(FileExistsError):
                asset_audit(path, root / 'partial-audit')

    def test_palette_transparency_is_recognized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = Image.new('P', (4, 4), 0)
            image.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
            image.putpixel((1, 1), 1)
            path = root / 'palette.png'
            image.save(path, transparency=0)
            report = asset_audit(path, root / 'audit')
            self.assertTrue(report['has_alpha'])
            self.assertEqual(15, report['transparent_pixels'])
            self.assertEqual(1, report['opaque_pixels'])

    def test_board_relative_paths_roles_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / 'ref.png'
            Image.new('RGBA', (8, 12), (0, 0, 255, 128)).save(image)
            before = image.read_bytes()
            plan = root / 'plan.json'
            plan.write_text(json.dumps({'items': [{'path': 'ref.png', 'role': 'character', 'label': '角色參考'}]}), encoding='utf-8')
            report = reference_board(plan, root / 'board')
            self.assertEqual('character', report['items'][0]['role'])
            self.assertEqual(str(image.resolve()), report['items'][0]['input']['path'])
            self.assertEqual(before, image.read_bytes())
            with Image.open(root / 'board/reference_board.png') as board:
                self.assertEqual((360, 420), board.size)
            plan.write_text(json.dumps({'items': [{'path': 'ref.png', 'role': 'unknown', 'label': 'x'}]}))
            with self.assertRaises(ValueError):
                reference_board(plan, root / 'invalid')
            self.assertFalse((root / 'invalid').exists())
            plan.write_text(json.dumps({'items': []}))
            with self.assertRaises(ValueError):
                reference_board(plan, root / 'empty-board')


if __name__ == '__main__':
    unittest.main()
