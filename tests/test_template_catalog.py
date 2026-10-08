"""The generated template catalog matches template.json and skips underscore folders."""
import json
import tempfile
import unittest
from pathlib import Path

from maintenance.build_catalog import catalog_document, markdown_page, render

ROOT = Path(__file__).resolve().parents[1]


class TemplateCatalogTests(unittest.TestCase):
    def test_committed_catalog_matches_templates(self):
        catalog_bytes, page_bytes = render(ROOT)
        catalog = (ROOT / "templates" / "catalog.json").read_bytes()
        page = (ROOT / "docs" / "knowledge" / "maintenance" / "template-catalog.md").read_bytes()
        self.assertEqual(catalog_bytes, catalog.replace(b"\r\n", b"\n"))
        self.assertEqual(page_bytes, page.replace(b"\r\n", b"\n"))
        document = json.loads(catalog_bytes.decode("utf-8"))
        self.assertIn("自動產生，勿手改", document["note"])
        self.assertTrue(document["templates"])
        self.assertEqual(
            [item["id"] for item in document["templates"]],
            sorted(item["id"] for item in document["templates"]),
        )

    def test_skips_underscore_directories_and_checks_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kept = root / "video" / "example"
            kept.mkdir(parents=True)
            (kept / "template.json").write_text(json.dumps({
                "id": "video/example",
                "version": "0.1.0",
                "title": "範例",
                "summary": "一句",
                "status": "draft",
                "capability": "object_track",
                "min_comfyui_version": "0.34.0",
                "requires_custom_nodes": [],
                "platforms": {"windows-cuda": {"status": "untested"}},
                "frame_anchoring": {"first": "none", "time_alignment": None},
                "models": [{"role": "unet", "filename": "a.safetensors", "directory": "diffusion_models"}],
            }), encoding="utf-8")
            gated = root / "video" / "gated"
            gated.mkdir(parents=True)
            (gated / "template.json").write_text(json.dumps({
                "id": "video/gated",
                "capability": "wrong",
                "platforms": {"macos-mps": {"status": "technical_pass"}},
                "capability_gate": {
                    "capability": "object_track",
                    "platforms": {"windows-cuda": {"status": "technical_pass"}},
                },
            }), encoding="utf-8")
            hidden = root / "_schema" / "not-a-template"
            hidden.mkdir(parents=True)
            (hidden / "template.json").write_text("{}", encoding="utf-8")
            entries = catalog_document(root)["templates"]
            by_id = {item["id"]: item for item in entries}
            self.assertEqual(["video/example", "video/gated"], sorted(by_id))
            self.assertEqual("video", by_id["video/example"]["media"])
            self.assertEqual("object_track", by_id["video/example"]["capability"])
            self.assertEqual({"windows-cuda": "untested"}, by_id["video/example"]["platforms"])
            self.assertEqual("object_track", by_id["video/gated"]["capability"])
            self.assertEqual({"windows-cuda": "technical_pass"}, by_id["video/gated"]["platforms"])
            page = markdown_page(catalog_document(root))
            self.assertIn("自動產生，勿手改", page)
            self.assertIn("`video/example`", page)
            self.assertIn("time_alignment=null", page)
            self.assertNotIn("_schema", page)

    def test_rejects_id_that_does_not_match_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "video" / "example"
            folder.mkdir(parents=True)
            (folder / "template.json").write_text(json.dumps({"id": "video/other"}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                catalog_document(tmp)


if __name__ == "__main__":
    unittest.main()
