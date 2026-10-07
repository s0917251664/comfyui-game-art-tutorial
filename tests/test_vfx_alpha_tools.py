import optional_deps

optional_deps.require("PIL", "numpy")

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tools_src import vfx_alpha_tools as tool


def glow(size=32, peak=(60, 200, 255), radius=10.0):
    """Synthetic radial glow with known straight colour and alpha."""
    y, x = np.mgrid[:size, :size]
    alpha = np.clip(1 - np.hypot(x - size / 2, y - size / 2) / radius, 0, 1).astype(np.float32)
    colour = np.empty((size, size, 3), np.float32)
    colour[...] = np.array(peak, np.float32) / 255
    return colour, alpha


def over_bg(colour, alpha, bg):
    return np.round((colour * alpha[..., None] + np.array(bg, np.float32) / 255 * (1 - alpha[..., None])) * 255).astype(np.uint8)


def has_libvpx():
    if importlib.util.find_spec("av") is None:
        return False
    import av
    try:
        av.codec.Codec("libvpx-vp9", "w")
        av.codec.Codec("libvpx-vp9", "r")
        return True
    except Exception:
        return False


class AlphaExtractionTests(unittest.TestCase):
    def test_luma_alpha_round_trips_saturated_glow_over_black(self):
        colour, alpha = glow()
        source = over_bg(colour, alpha, (0, 0, 0))
        rgba = tool.luma_alpha(source)
        # Max-channel alpha equals true alpha when the peak channel is 255.
        np.testing.assert_allclose(rgba[..., 3] / 255, alpha, atol=2 / 255)
        np.testing.assert_array_less(np.abs(tool.over(rgba, (0, 0, 0)).astype(int) - source), 2)

    def test_luma_alpha_black_point_clears_noisy_background(self):
        frame = np.full((4, 4, 3), 10, np.uint8)
        frame[0, 0] = (255, 255, 255)
        rgba = tool.luma_alpha(frame, black_point=12 / 255)
        self.assertEqual(0, int(rgba[1:, 1:, 3].max()))
        self.assertEqual(255, int(rgba[0, 0, 3]))
        with self.assertRaises(ValueError):
            tool.luma_alpha(frame, black_point=0.5, white_point=0.4)

    def test_chroma_baseline_matches_video_composite_ramp_and_unmix_restores_colour(self):
        colour, alpha = glow(peak=(255, 120, 40))
        source = over_bg(colour, alpha, (0, 255, 0))
        base = tool.chroma_alpha(source)
        dist = np.abs(source.astype(np.int16) - np.array([0, 255, 0])).max(axis=2)
        expected = np.round(np.clip((dist - 60) / 40, 0, 1) * 255)
        np.testing.assert_array_equal(base[..., 3], expected.astype(np.uint8))
        unmixed = tool.chroma_alpha(source, unmix=True, despill=True)
        semi = (unmixed[..., 3] > 64) & (unmixed[..., 3] < 255)
        self.assertTrue(semi.any())
        # Baseline keeps green spill in soft pixels; unmix+despill removes it.
        self.assertGreater(base[semi][:, 1].mean(), unmixed[semi][:, 1].mean() + 20)
        self.assertTrue(np.all(unmixed[..., 1] <= np.maximum(unmixed[..., 0], unmixed[..., 2])))

    def test_parse_hex_rejects_bad_colour(self):
        with self.assertRaises(ValueError):
            tool.parse_hex("GG0000")


class MetricsTests(unittest.TestCase):
    def test_flicker_metric_flags_alternating_alpha(self):
        steady = [np.dstack([np.full((8, 8, 3), 200, np.uint8), np.full((8, 8), 128, np.uint8)]) for _ in range(5)]
        flicker = [np.dstack([np.full((8, 8, 3), 200, np.uint8), np.full((8, 8), 60 if i % 2 else 200, np.uint8)])
                   for i in range(5)]
        a = tool.alpha_metrics(steady)
        b = tool.alpha_metrics(flicker)
        self.assertEqual(0.0, a["temporal"]["mean_second_difference_flicker"])
        self.assertGreater(b["temporal"]["mean_second_difference_flicker"], 0.5)
        self.assertAlmostEqual(1.0, a["semi_transparent_fraction_of_visible"])

    def test_fringe_and_reference(self):
        frame = np.zeros((2, 2, 4), np.uint8)
        frame[0, 0] = (10, 200, 10, 128)
        frame[1, 1] = (200, 200, 200, 255)
        report = tool.alpha_metrics([frame], key="00FF00", reference_alpha=[np.array([[128, 0], [0, 255]], np.uint8)])
        self.assertEqual(1, report["fringe"]["edge_pixels"])
        self.assertEqual(190.0, report["fringe"]["mean_key_excess"])
        self.assertEqual(0.0, report["against_reference"]["alpha_mae"])


class PackingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        colour, alpha = glow(16)
        self.frames = []
        for i in range(5):
            rgba = np.dstack([np.round(colour * 255).astype(np.uint8), np.round(alpha * 255 * (i + 1) / 5).astype(np.uint8)])
            self.frames.append(rgba)

    def test_sprite_sheet_layout_and_pixels(self):
        meta = tool.sprite_sheet(self.frames, self.root / "sheet.png", columns=2)
        self.assertEqual((2, 3), (meta["columns"], meta["rows"]))
        sheet = np.asarray(Image.open(self.root / "sheet.png"))
        r = meta["frames"][3]
        np.testing.assert_array_equal(sheet[r["y"]:r["y"] + 16, r["x"]:r["x"] + 16], self.frames[3])
        self.assertEqual(0, int(sheet[32:, 16:, 3].max()))  # unused cell stays transparent
        self.assertTrue((self.root / "sheet.json").is_file())

    def test_apng_keeps_frames_and_alpha(self):
        tool.write_apng(self.frames, self.root / "anim.png")
        with Image.open(self.root / "anim.png") as im:
            self.assertEqual(5, im.n_frames)
            im.seek(4)
            np.testing.assert_array_equal(np.asarray(im.convert("RGBA")), self.frames[4])

    @unittest.skipUnless(has_libvpx(), "PyAV with libvpx-vp9 not available")
    def test_webm_vp9_alpha_round_trip(self):
        tool.write_webm_alpha(self.frames, self.root / "anim.webm", crf=10)
        decoded = tool.read_webm_alpha(self.root / "anim.webm")
        self.assertEqual(5, len(decoded))
        err = np.abs(decoded[4][..., 3].astype(int) - self.frames[4][..., 3].astype(int)).mean()
        self.assertLess(err, 8)

    def test_cli_pack_refuses_existing_output(self):
        src = tool.write_sequence(self.frames, self.root / "seq")
        (self.root / "taken").mkdir()
        self.assertEqual(1, tool.main(["pack", "--input", str(src), "--output-dir", str(self.root / "taken")]))
        self.assertEqual(0, tool.main(["pack", "--input", str(src), "--output-dir", str(self.root / "out"), "--apng"]))
        result = json.loads((self.root / "out" / "result.json").read_text(encoding="utf-8"))
        self.assertIn("apng", result["outputs"])


class MaskTests(unittest.TestCase):
    def test_sam_mask_direction_conversion(self):
        edit = tool.sam_to_edit_mask(np.array([[255, 0, 128]], np.uint8))
        np.testing.assert_array_equal(edit[0, :, 3], [0, 255, 127])

    def test_mask_composite_preserves_outside_exactly_with_feather(self):
        rng = np.random.default_rng(1)
        original = [rng.integers(0, 256, (20, 20, 3), dtype=np.uint8) for _ in range(3)]
        edited = [np.zeros((20, 20, 3), np.uint8) for _ in range(3)]
        masks = [np.zeros((20, 20), np.uint8) for _ in range(3)]
        for m in masks:
            m[8:12, 8:12] = 255
        out, rows = tool.mask_composite(original, edited, masks, feather=2)
        for o, c, m in zip(original, out, masks):
            grown_far = np.ones((20, 20), bool)
            grown_far[6:14, 6:14] = False
            np.testing.assert_array_equal(c[grown_far], o[grown_far])
            np.testing.assert_array_equal(c[9:11, 9:11], 0)
        self.assertEqual(0, sum(r["outside_changed_pixels"] for r in rows))
        with self.assertRaises(ValueError):
            tool.mask_composite(original, edited[:2], masks)

    def test_masked_hue_rotate_only_changes_selected_matching_hue(self):
        frame = np.array([[(0, 200, 255), (0, 200, 255), (128, 128, 128)]], np.uint8)
        selected = np.array([[True, False, True]])
        out, hits = tool.masked_hue_rotate(frame, selected, from_hue=195, to_hue=15)
        self.assertEqual(1, hits)
        self.assertGreater(out[0, 0, 0], out[0, 0, 2])
        np.testing.assert_array_equal(out[0, 1:], frame[0, 1:])

    def test_outside_drift_reports_changes(self):
        o = [np.zeros((4, 4, 3), np.uint8)]
        c = [np.full((4, 4, 3), 20, np.uint8)]
        m = [np.zeros((4, 4), np.uint8)]
        self.assertEqual(1.0, tool.outside_mask_drift(o, c, m)[0]["fraction_gt_8"])


class LoopTests(unittest.TestCase):
    def test_loop_metrics_identical_ends_and_reference(self):
        base = np.zeros((80, 80, 3), np.uint8)
        base[...] = (0, 255, 0)
        base[30:50, 35:45] = (200, 50, 50)
        frames = [base.copy() for _ in range(6)]
        for i in range(1, 5):
            frames[i][30:50, 35 + i:45 + i] = (200, 50, 50)
        report, ref = tool.loop_metrics(frames, reference=base, key="00FF00")
        self.assertEqual(0.0, report["last_vs_first"]["mae"])
        self.assertIsNone(report["last_vs_first"]["psnr_db"])
        self.assertEqual(0.0, report["first_vs_reference"]["mae"])
        self.assertEqual([19, 14, 61, 66], report["roi"])
        self.assertEqual(0.0, report["seam_to_median_adjacent_ratio"])

    def test_subject_roi_none_on_pure_key(self):
        self.assertIsNone(tool.subject_roi(np.tile(np.array([0, 255, 0], np.uint8), (4, 4, 1)), "00FF00"))


if __name__ == "__main__":
    unittest.main()
