import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools_src"))
import asset_review  # noqa: E402


def _make(directory, name="a", content=b"png-bytes"):
    out = os.path.join(directory, name + ".png")
    Path(out).write_bytes(content)
    manifest = os.path.join(directory, name + ".result.json")
    Path(manifest).write_text(json.dumps({
        "kind": "image_generation_result", "task": "concept",
        "technical_validation": {"status": "pass"},
        "outputs": [{"path": out, "sha256": hashlib.sha256(content).hexdigest()}],
    }), encoding="utf-8")
    return out, manifest


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = asset_review.main(list(argv))
    return code, buf.getvalue()


class AssetReviewTests(unittest.TestCase):
    def test_default_pending_then_accept_then_regenerate_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            out, manifest = _make(d)
            self.assertIn("pending", run("list", d)[1])
            before = Path(manifest).read_bytes()
            run("accept", manifest, "--by", "reviewer", "--note", "ok")
            self.assertEqual(Path(manifest).read_bytes(), before)
            self.assertIn("accepted", run("list", d)[1])
            Path(out).write_bytes(b"regenerated")
            listing = run("list", d)[1]
            self.assertIn("mismatch", listing)
            self.assertIn("modified", listing)
            with self.assertRaises(SystemExit):
                run("reject", out, "--by", "reviewer")

    def test_by_required_and_reject_by_output_path(self):
        with tempfile.TemporaryDirectory() as d:
            out, manifest = _make(d)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                run("accept", manifest)
            with self.assertRaises(SystemExit):
                run("accept", manifest, "--by", "  ")
            run("reject", out, "--by", "reviewer")
            self.assertIn("rejected", run("list", manifest)[1])
            self.assertFalse(Path(d, "a.decisions.json").read_text().count("accepted"))

    def test_show_by_hash_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            _, manifest = _make(d)
            run("accept", manifest, "--by", "reviewer")
            sha = hashlib.sha256(b"png-bytes").hexdigest()[:8]
            code, text = run("show", sha, "--in", d)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(text)["decision_history"][0]["by"], "reviewer")


if __name__ == "__main__":
    unittest.main()


class DefaultManifestPathTests(unittest.TestCase):
    def test_default_path_next_to_first_png(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools_src"))
        from comfyui_pipeline import cli
        self.assertEqual(cli.default_manifest_path(["/o/x_00001_.png", "/o/x_00002_.png"]),
                         os.path.abspath("/o/x_00001_.result.json"))
        self.assertIsNone(cli.default_manifest_path(["/o/v.mp4"]))


class ExplicitManifestTests(unittest.TestCase):
    def test_list_accepts_custom_named_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            _out, manifest = _make(d)
            custom = os.path.join(d, "explicit.json")
            os.replace(manifest, custom)
            code, listing = run("list", custom)
            self.assertEqual(0, code)
            self.assertIn("pending", listing)
            run("accept", custom, "--by", "reviewer")
            self.assertTrue(os.path.isfile(os.path.join(d, "explicit.decisions.json")))
            self.assertIn("accepted", run("list", custom)[1])

    def test_unrelated_json_is_not_a_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            other = os.path.join(d, "other.json")
            Path(other).write_text('{"kind": "something_else"}', encoding="utf-8")
            self.assertNotIn("pending", run("list", other)[1])
