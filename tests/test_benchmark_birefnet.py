import argparse
import importlib.util
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


MODULE_PATH = Path(__file__).parents[1] / "tools_src" / "benchmark_birefnet.py"
SPEC = importlib.util.spec_from_file_location("benchmark_birefnet", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BiRefNetBenchmarkTests(unittest.TestCase):
    def test_case_size_is_bounded_and_aligned(self):
        self.assertEqual(MODULE.validate_case_size("2048"), 2048)
        for value in (255, 2305, 1000, "nope"):
            with self.assertRaises(argparse.ArgumentTypeError):
                MODULE.validate_case_size(value)

    def test_square_fit_preserves_alpha_and_aspect(self):
        source = Image.new("RGBA", (100, 50), (20, 30, 40, 255))
        result = MODULE.fit_rgba_to_square(source, 256)
        self.assertEqual(result.size, (256, 256))
        self.assertEqual(result.getchannel("A").getbbox(), (0, 64, 256, 192))

    def test_metrics_are_exact_for_identical_alpha(self):
        alpha = np.array([[0, 64], [192, 255]], dtype=np.uint8)
        metrics = MODULE.alpha_metrics(alpha, alpha)
        self.assertEqual(metrics["alpha_mae"], 0.0)
        self.assertEqual(metrics["iou_0_5"], 1.0)
        self.assertEqual(metrics["boundary_mae"], 0.0)

    def test_composite_is_rgb_and_preserves_geometry(self):
        rgba = Image.new("RGBA", (32, 48), (255, 0, 0, 128))
        result = MODULE.composite_case(rgba, (0, 0, 0))
        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, rgba.size)

    def test_legacy_alpha_can_be_explicitly_inverted(self):
        rgba = Image.new("RGBA", (2, 1), (10, 20, 30, 0))
        rgba.putalpha(Image.fromarray(np.array([[0, 255]], dtype=np.uint8)))
        corrected = MODULE.invert_alpha(rgba)
        self.assertEqual(np.asarray(corrected.getchannel("A")).tolist(), [[255, 0]])


if __name__ == "__main__":
    unittest.main()
