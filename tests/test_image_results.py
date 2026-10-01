import importlib.util
import json
import os
import tempfile
import unittest
from types import SimpleNamespace


MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tools_src", "comfyui_pipeline", "image_results.py"
)
SPEC = importlib.util.spec_from_file_location("image_results_under_test", MODULE_PATH)
image_results = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(image_results)


class ImageResultsTests(unittest.TestCase):
    def test_extracts_seeds_and_selected_models_from_graph(self):
        graph = {
            "4": {"class_type": "KSampler", "inputs": {"seed": 71}},
            "5": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
            "6": {"class_type": "RandomNoise", "inputs": {"noise_seed": 88}},
        }
        self.assertEqual({"4": {"seed": 71}, "6": {"noise_seed": 88}},
                         image_results.resolved_seeds(graph))
        self.assertEqual("base.safetensors", image_results.selected_models(graph)[0]["filename"])
        self.assertEqual(64, len(image_results.graph_sha256(graph)))

    def test_validates_png_alpha_dimensions_and_hashes(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            png_path = os.path.join(directory, "out.png")
            Image.new("RGBA", (12, 9), (20, 30, 40, 128)).save(png_path)
            rows = image_results.validate_png_outputs(
                [png_path], expected_dimensions={"width": 12, "height": 9},
                require_alpha=True, require_transparency=True,
            )
            self.assertEqual((12, 9), (rows[0]["width"], rows[0]["height"]))
            self.assertTrue(rows[0]["has_alpha_channel"])
            self.assertTrue(rows[0]["has_transparency"])
            self.assertEqual(64, len(rows[0]["sha256"]))
            with self.assertRaisesRegex(ValueError, "graph latent"):
                image_results.validate_png_outputs(
                    [png_path], expected_dimensions={"width": 10, "height": 9}
                )

    def test_rejects_non_png_content_with_png_extension(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            mislabeled = os.path.join(directory, "jpeg-renamed.png")
            Image.new("RGB", (12, 9), (20, 30, 40)).save(mislabeled, format="JPEG")
            with self.assertRaisesRegex(ValueError, "不是 PNG"):
                image_results.validate_png_outputs([mislabeled])

    def test_manifest_has_separate_technical_and_content_status_and_no_clobber(self):
        graph = {"4": {"class_type": "KSampler", "inputs": {"seed": 71}}}
        manifest = image_results.make_manifest(
            task="concept", profile_id=None, backend="comfyui", prompt_id="p1",
            graph=graph, inputs=[], outputs=[{
                "path": "C:/out.png", "sha256": "x", "width": 8, "height": 8,
                "mode": "RGBA", "has_alpha_channel": True, "has_transparency": False,
            }],
        )
        self.assertEqual("completed", manifest["status"])
        self.assertEqual("pass", manifest["technical_validation"]["status"])
        self.assertEqual("pending", manifest["content_review"])
        self.assertEqual({"4": {"seed": 71}}, manifest["resolved_seeds"])
        with tempfile.TemporaryDirectory() as directory:
            destination = os.path.join(directory, "result.json")
            image_results.write_manifest_atomic(destination, manifest)
            with open(destination, encoding="utf-8") as stream:
                self.assertEqual("image_generation_result", json.load(stream)["kind"])
            with self.assertRaises(FileExistsError):
                image_results.write_manifest_atomic(destination, manifest)

    def test_path_validation_rejects_bad_or_existing_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, ".json"):
                image_results.validate_manifest_path(os.path.join(directory, "result.txt"))
            destination = os.path.join(directory, "result.json")
            with open(destination, "w", encoding="utf-8") as stream:
                stream.write("{}");
            with self.assertRaises(FileExistsError):
                image_results.validate_manifest_path(destination)

    def test_manifest_preserves_input_roles_and_requested_vs_effective_prompt(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "source.png")
            Image.new("RGBA", (8, 8), (0, 0, 0, 255)).save(source)
            records = image_results.input_records([{"role": "image", "path": source}])
            graph = {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "safe, raw prompt"}}}
            manifest = image_results.make_manifest(
                task="concept", profile_id=None, backend="comfyui", prompt_id="p1",
                graph=graph, inputs=records, outputs=[{
                    "path": "C:/out.png", "sha256": "x", "width": 8, "height": 8,
                    "mode": "RGB", "has_alpha_channel": False, "has_transparency": False,
                }],
                args=SimpleNamespace(prompt="safe, raw prompt", requested_prompt="raw prompt", rating="safe"),
            )
            self.assertEqual("image", manifest["inputs"][0]["role"])
            self.assertEqual("raw prompt", manifest["task_parameters"]["prompt"])
            self.assertEqual([source], manifest["task_parameters"]["input_paths"]["image"])
            self.assertEqual("safe, raw prompt", manifest["effective_conditioning"][0]["text"])


if __name__ == "__main__":
    unittest.main()
