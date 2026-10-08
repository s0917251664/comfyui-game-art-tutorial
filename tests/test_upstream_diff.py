"""The upstream blob helper hashes like git hash-object and does not need the network."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from maintenance.diff_upstream_template import git_blob_sha1, main


class UpstreamDiffTests(unittest.TestCase):
    def test_git_blob_sha1_matches_the_git_header(self):
        data = b"abc\n"
        header = f"blob {len(data)}\0".encode("ascii")
        self.assertEqual(git_blob_sha1(data), hashlib.sha1(header + data).hexdigest())

    def test_local_file_compares_without_network(self):
        body = b'{"nodes":[]}\n'
        blob = git_blob_sha1(body)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "templates" / "video" / "example"
            folder.mkdir(parents=True)
            template = {
                "provenance": {
                    "upstream": {
                        "kind": "workflow_templates",
                        "name": "video_example",
                        "blob": blob,
                    }
                }
            }
            (folder / "template.json").write_text(json.dumps(template), encoding="utf-8")
            official = root / "official.json"
            official.write_bytes(body)
            code = main(["--template", "video/example", "--repo", str(root), "--file", str(official)])
            self.assertEqual(0, code)

    def test_rejects_template_without_a_workflow_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "templates" / "video" / "example"
            folder.mkdir(parents=True)
            (folder / "template.json").write_text(
                json.dumps({"provenance": {"upstream": {"kind": "none", "name": "", "blob": ""}}}),
                encoding="utf-8")
            with self.assertRaises(SystemExit):
                main(["--template", "video/example", "--repo", str(root), "--file", str(root / "missing")])


if __name__ == "__main__":
    unittest.main()
