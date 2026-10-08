import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools_src"))

import detect_video_capabilities as detector  # noqa: E402
import doctor  # noqa: E402


RUNTIME = {
    "python": "3.12.0", "pillow": "1", "torch": "1", "pyav": "1", "torch_cuda": False,
}


class _Body:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class TemplateCapabilityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.comfy = os.path.join(self.root, "ComfyUI")
        self.models = os.path.join(self.comfy, "models")
        self.templates = os.path.join(self.root, "templates")
        os.makedirs(os.path.join(self.comfy, "tools"))
        os.makedirs(self.templates)

    def tearDown(self):
        self._tmp.cleanup()

    def write_file(self, *parts, payload=b"abc"):
        path = os.path.join(*parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(payload)
        return path

    def write_template(self, template_id, data):
        folder = os.path.join(self.templates, *template_id.split("/"))
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "template.json"), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle)

    def detect(self, **overrides):
        args = SimpleNamespace(
            comfyui_path=self.comfy,
            python_exe=sys.executable,
            model_root=[self.models],
            device_config=os.path.join(self.comfy, "tools", "missing-device.json"),
            comfy_url=None,
            http_timeout=1.0,
            default_backend=None,
            control_type="pose",
            hash_models=False,
            templates_root=self.templates,
        )
        for key, value in overrides.items():
            setattr(args, key, value)
        with mock.patch.object(detector, "_runtime_probe", return_value=dict(RUNTIME)):
            return detector.detect(args)

    def entry(self, config, capability):
        found = [item for item in config["template_capabilities"] if item["capability"] == capability]
        self.assertEqual(len(found), 1, config["template_capabilities"])
        return found[0]

    def test_groups_declared_video_capabilities(self):
        payload = b"sam"
        self.write_file(self.models, "checkpoints", "sam.safetensors", payload=payload)
        self.write_template("video/sam3/track-mask", {
            "capability": "image_generation",
            "capability_gate": {"capability": "object_track"},
            "models": [{
                "filename": "sam.safetensors", "directory": "checkpoints", "size_bytes": len(payload),
            }],
        })
        self.write_template("video/sam3/track-text", {
            "capability_gate": {"capability": "object_track"},
            "models": [{"filename": "missing.safetensors", "directory": "checkpoints", "size_bytes": 3}],
        })
        self.write_template("video/wan-animate/move", {
            "capability": "image_generation",
            "capability_gate": {"capability": "wan_animate_move"},
            "models": [],
        })
        self.write_template("video/no-gate/scail", {"capability": "scail2", "models": []})
        self.write_template("video/wan-vace/inpaint", {
            "capability_gate": {"capability": "masked_edit"},
            "models": [{"filename": "nope.safetensors", "directory": "diffusion_models"}],
        })
        self.write_template("image/flux2/concept", {
            "capability_gate": {"capability": "image_generation"},
            "models": [{"filename": "missing.safetensors", "directory": "checkpoints"}],
        })
        self.write_template("video/looks-like-image", {
            "capability": "object_track",
            "capability_gate": {"capability": "image_generation"},
        })
        self.write_template("video/_hidden/ghost", {"capability_gate": {"capability": "object_track"}})
        self.write_template("video/sam3/_extra/x", {"capability_gate": {"capability": "object_track"}})
        self.write_template("_schema/ignored", {"capability_gate": {"capability": "object_track"}})
        self.write_template("video/bad-type/x", {
            "capability": "masked_edit",
            "capability_gate": {"capability": 3},
        })
        self.write_template("video/empty-gate", {
            "capability": "masked_edit",
            "capability_gate": {},
        })
        self.write_template("video/list-cap/x", {"capability": ["masked_edit"]})

        config = self.detect()
        self.assertEqual(config["schema_version"], 1)
        self.assertEqual(
            set(config["backends"]["h3"]),
            {"available", "capabilities", "models", "required_nodes", "reasons"},
        )
        self.assertEqual(set(config["backends"]["wan"]), set(config["backends"]["h3"]))
        self.assertIn("img2video", config["tasks"])
        self.assertEqual(
            [item["capability"] for item in config["template_capabilities"]],
            ["masked_edit", "object_track", "scail2", "wan_animate_move"],
        )
        for item in config["template_capabilities"]:
            self.assertEqual(set(item), {"capability", "template_ids", "available", "reasons"})

        tracked = self.entry(config, "object_track")
        self.assertEqual(tracked["template_ids"], ["video/sam3/track-mask", "video/sam3/track-text"])
        self.assertTrue(tracked["available"])
        self.assertEqual(tracked["reasons"]["note"], "節點未檢查")
        self.assertEqual(
            tracked["reasons"]["by_template"]["video/sam3/track-text"]["missing_models"],
            ["checkpoints/missing.safetensors"],
        )
        self.assertNotIn("video/sam3/track-mask", tracked["reasons"]["by_template"])

        masked = self.entry(config, "masked_edit")
        self.assertEqual(masked["template_ids"], ["video/wan-vace/inpaint"])
        self.assertFalse(masked["available"])
        self.assertEqual(
            masked["reasons"]["by_template"]["video/wan-vace/inpaint"]["missing_models"],
            ["diffusion_models/nope.safetensors"],
        )
        self.assertTrue(self.entry(config, "scail2")["available"])
        self.assertEqual(self.entry(config, "scail2")["template_ids"], ["video/no-gate/scail"])
        self.assertEqual(self.entry(config, "wan_animate_move")["template_ids"], ["video/wan-animate/move"])
        ids = [template_id for item in config["template_capabilities"] for template_id in item["template_ids"]]
        for skipped in (
            "image/flux2/concept", "video/looks-like-image", "video/_hidden/ghost",
            "video/sam3/_extra/x", "_schema/ignored", "video/bad-type/x",
            "video/empty-gate", "video/list-cap/x",
        ):
            self.assertNotIn(skipped, ids)

    def test_size_mismatch_is_unavailable_and_does_not_hash(self):
        payload = b"abcd"
        self.write_file(self.models, "diffusion_models", "a.safetensors", payload=payload)
        self.write_template("video/pin", {
            "capability_gate": {"capability": "scail2"},
            "models": [{
                "filename": "a.safetensors",
                "directory": "diffusion_models",
                "size_bytes": len(payload) + 5,
                "sha256": "ab" * 32,
            }],
        })
        real = detector._sha256_file
        with mock.patch.object(detector, "_sha256_file", wraps=real) as hashed:
            config = self.detect(hash_models=True)
        hashed.assert_not_called()
        entry = self.entry(config, "scail2")
        self.assertFalse(entry["available"])
        self.assertEqual(entry["reasons"]["by_template"]["video/pin"]["size_mismatch"], [{
            "file": "diffusion_models/a.safetensors",
            "expected": len(payload) + 5,
            "actual": len(payload),
        }])
        self.assertNotIn("sha256_mismatch", entry["reasons"]["by_template"]["video/pin"])

    def test_sha256_runs_only_with_hash_models(self):
        payload = b"hello-model"
        self.write_file(self.models, "diffusion_models", "a.safetensors", payload=payload)
        digest = hashlib.sha256(payload).hexdigest()

        def write(pin):
            self.write_template("video/pin", {
                "capability_gate": {"capability": "scail2"},
                "models": [{
                    "filename": "a.safetensors",
                    "directory": "diffusion_models",
                    "size_bytes": len(payload),
                    "sha256": pin,
                }],
            })

        write("0" * 64)
        real = detector._sha256_file
        with mock.patch.object(detector, "_sha256_file", wraps=real) as hashed:
            config = self.detect()
        hashed.assert_not_called()
        self.assertTrue(self.entry(config, "scail2")["available"])

        with mock.patch.object(detector, "_sha256_file", wraps=real) as hashed:
            config = self.detect(hash_models=True)
        self.assertGreaterEqual(hashed.call_count, 1)
        problem = self.entry(config, "scail2")["reasons"]["by_template"]["video/pin"]
        self.assertEqual(problem["sha256_mismatch"], ["diffusion_models/a.safetensors"])
        self.assertFalse(self.entry(config, "scail2")["available"])

        write(digest)
        config = self.detect(hash_models=True)
        entry = self.entry(config, "scail2")
        self.assertTrue(entry["available"])
        self.assertNotIn("by_template", entry["reasons"])

    def test_nodes_unchecked_without_object_info_and_missing_when_class_absent(self):
        self.write_template("video/needs-node", {
            "capability_gate": {"capability": "object_track"},
            "models": [],
            "requires_custom_nodes": [{"id": "NeededNode", "source": "registry"}],
        })
        unchecked = self.entry(self.detect(), "object_track")
        self.assertTrue(unchecked["available"])
        self.assertEqual(unchecked["reasons"], {"note": "節點未檢查"})

        missing = {"status": "available", "classes": ["OtherNode"], "error": None, "class_modules": ["nodes"]}
        with mock.patch.object(detector, "_query_object_info", return_value=missing):
            config = self.detect(comfy_url="http://127.0.0.1:9")
        entry = self.entry(config, "object_track")
        self.assertFalse(entry["available"])
        self.assertEqual(entry["reasons"]["by_template"]["video/needs-node"]["missing_nodes"], ["NeededNode"])
        self.assertNotIn("note", entry["reasons"])
        self.assertNotIn("class_modules", config["node_check"])

        present = {"status": "available", "classes": ["NeededNode"], "error": None}
        with mock.patch.object(detector, "_query_object_info", return_value=present):
            config = self.detect(comfy_url="http://127.0.0.1:9")
        entry = self.entry(config, "object_track")
        self.assertTrue(entry["available"])
        self.assertEqual(entry["reasons"], {})

    def test_registry_id_matches_python_module_segment(self):
        self.write_template("video/wan-animate/move", {
            "capability_gate": {"capability": "wan_animate_move"},
            "requires_custom_nodes": [
                {"id": "comfyui_controlnet_aux", "source": "registry"},
                {"id": "comfyui-kjnodes", "source": "registry"},
            ],
        })
        found = {
            "status": "available",
            "classes": ["KSampler"],
            "error": None,
            "class_modules": [
                "custom_nodes.comfyui_controlnet_aux.nodes",
                "custom_nodes.ComfyUI-KJNodes",
            ],
        }
        with mock.patch.object(detector, "_query_object_info", return_value=found):
            config = self.detect(comfy_url="http://127.0.0.1:9")
        self.assertTrue(self.entry(config, "wan_animate_move")["available"])
        self.assertEqual(self.entry(config, "wan_animate_move")["reasons"], {})

        missing = {
            "status": "available",
            "classes": ["KSampler"],
            "error": None,
            "class_modules": ["nodes"],
        }
        with mock.patch.object(detector, "_query_object_info", return_value=missing):
            config = self.detect(comfy_url="http://127.0.0.1:9")
        problem = self.entry(config, "wan_animate_move")["reasons"]["by_template"]["video/wan-animate/move"]
        self.assertEqual(problem["missing_nodes"], ["comfyui-kjnodes", "comfyui_controlnet_aux"])

    def test_null_directory_uses_comfyui_path_and_directory_ignores_path(self):
        payload = b"onnx"
        self.write_file(self.comfy, "custom_nodes", "pkg", "ckpts", "a.onnx", payload=payload)
        self.write_template("video/wan-animate/move", {
            "capability_gate": {"capability": "wan_animate_move"},
            "models": [{
                "filename": "a.onnx",
                "directory": None,
                "path": "custom_nodes/pkg/ckpts/a.onnx",
                "size_bytes": len(payload),
            }],
        })
        self.write_file(self.comfy, "somewhere", "a.safetensors", payload=b"zz")
        self.write_template("video/only-path", {
            "capability_gate": {"capability": "masked_edit"},
            "models": [{
                "filename": "a.safetensors",
                "directory": "checkpoints",
                "path": "somewhere/a.safetensors",
                "size_bytes": 2,
            }],
        })
        config = self.detect()
        self.assertTrue(self.entry(config, "wan_animate_move")["available"])
        masked = self.entry(config, "masked_edit")
        self.assertFalse(masked["available"])
        self.assertEqual(
            masked["reasons"]["by_template"]["video/only-path"]["missing_models"],
            ["checkpoints/a.safetensors"],
        )

    def test_second_model_root_and_rejected_parent_traversal(self):
        payload = b"hi"
        extra = os.path.join(self.root, "extra-models")
        self.write_file(extra, "vae", "v.safetensors", payload=payload)
        self.write_template("video/root2", {
            "capability_gate": {"capability": "i2v"},
            "models": [{"filename": "v.safetensors", "directory": "vae", "size_bytes": len(payload)}],
        })
        self.write_file(self.root, "outside.bin", payload=b"abc")
        self.write_template("video/escape", {
            "capability_gate": {"capability": "scail2"},
            "models": [{"filename": "outside.bin", "directory": "..", "size_bytes": 3}],
        })
        config = self.detect(model_root=[os.path.join(self.root, "missing-root"), extra])
        self.assertTrue(self.entry(config, "i2v")["available"])
        escaped = self.entry(config, "scail2")
        self.assertFalse(escaped["available"])
        self.assertEqual(
            escaped["reasons"]["by_template"]["video/escape"]["missing_models"],
            ["../outside.bin"],
        )
        self.assertNotIn("size_mismatch", escaped["reasons"]["by_template"]["video/escape"])

    def test_invalid_model_entry_and_invalid_template_json(self):
        self.write_template("video/bad-model", {
            "capability_gate": {"capability": "object_track"},
            "models": ["nope"],
        })
        entry = self.entry(self.detect(), "object_track")
        self.assertFalse(entry["available"])
        self.assertEqual(entry["reasons"]["by_template"]["video/bad-model"]["invalid_models"], 1)

        folder = os.path.join(self.templates, "video", "broken")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "template.json"), "w", encoding="utf-8") as handle:
            handle.write("{")
        with self.assertRaisesRegex(RuntimeError, "video/broken"):
            self.detect()

    def test_missing_templates_root_is_empty(self):
        config = self.detect(templates_root=os.path.join(self.root, "no-such-templates"))
        self.assertEqual(config["template_capabilities"], [])

    def test_object_info_collects_class_modules_without_network(self):
        payload = {
            "DWPreprocessor": {"python_module": "custom_nodes.comfyui_controlnet_aux", "input": {}},
            "KSampler": {"python_module": "nodes"},
            "Broken": "nope",
        }
        with mock.patch.object(detector.urllib.request, "urlopen", return_value=_Body(payload)):
            info = detector._query_object_info("http://127.0.0.1:9", 1)
        self.assertEqual(info["status"], "available")
        self.assertEqual(info["classes"], ["Broken", "DWPreprocessor", "KSampler"])
        self.assertEqual(info["class_modules"], ["custom_nodes.comfyui_controlnet_aux", "nodes"])
        self.assertEqual(len(info["schema_fingerprint"]), 64)


class DoctorTemplateCapabilityTests(unittest.TestCase):
    def status_for(self, video):
        return {
            "comfyui_path": None,
            "snapshot_dir": "/s",
            "snapshots": {},
            "fingerprint": {"exists": False},
            "notes": [],
            "video": video,
        }

    def test_summary_line_and_old_snapshot_shape(self):
        old = doctor.summarize_video({
            "default_backend": "wan",
            "backends": {"wan": {"available": True, "capabilities": ["i2v"], "reasons": {}}},
        })
        self.assertNotIn("template_capabilities", old)
        text = doctor.format_status(self.status_for(old))
        self.assertIn("可用 i2v", text)
        self.assertNotIn("template:", text)

        weird = doctor.summarize_video({
            "default_backend": None,
            "backends": {},
            "template_capabilities": "nope",
        })
        self.assertNotIn("template_capabilities", weird)
        self.assertNotIn("template:", doctor.format_status(self.status_for(weird)))

        fresh = doctor.summarize_video({
            "default_backend": None,
            "backends": {"wan": {"available": False, "capabilities": [], "reasons": {}}},
            "template_capabilities": [
                "skip-me",
                {
                    "capability": "object_track",
                    "template_ids": ["video/sam3/track-mask"],
                    "available": True,
                    "reasons": {"note": "節點未檢查"},
                },
                {
                    "capability": "scail2",
                    "template_ids": ["video/wan-animate/scail2"],
                    "available": False,
                    "reasons": {"by_template": {"video/wan-animate/scail2": {"missing_models": ["a"]}}},
                },
            ],
        })
        self.assertEqual([item["capability"] for item in fresh["template_capabilities"]], ["object_track", "scail2"])
        text = doctor.format_status(self.status_for(fresh))
        self.assertIn("未安裝(未選用)", text)
        self.assertIn("  template: 可用 object_track; 未安裝 scail2 (節點未檢查)", text)
        self.assertEqual(text.count("template:"), 1)

        empty = doctor.summarize_video({
            "default_backend": None,
            "backends": {},
            "template_capabilities": [],
        })
        self.assertIn("  template: 沒有宣告的影片能力", doctor.format_status(self.status_for(empty)))

    def test_doctor_main_accepts_snapshot_without_the_field(self):
        with tempfile.TemporaryDirectory() as root:
            comfy = os.path.join(root, "ComfyUI")
            tools = os.path.join(comfy, "tools")
            os.makedirs(tools)
            path = os.path.join(tools, "video_capabilities.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({
                    "captured_at": "2020-01-01T00:00:00+00:00",
                    "default_backend": "wan",
                    "backends": {"wan": {"available": True, "capabilities": ["i2v"], "reasons": {}}},
                }, handle)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = doctor.main(["--comfyui-path", comfy, "--snapshot-dir", tools, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(buf.getvalue())
            self.assertNotIn("template_capabilities", data["video"])
            self.assertTrue(data["video"]["backends"]["wan"]["available"])
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = doctor.main(["--comfyui-path", comfy, "--snapshot-dir", tools])
            self.assertEqual(code, 0)
            text = buf.getvalue()
            self.assertIn("可用 i2v", text)
            self.assertNotIn("template:", text)

            with open(path, "w", encoding="utf-8") as handle:
                json.dump({
                    "captured_at": "2020-01-01T00:00:00+00:00",
                    "default_backend": None,
                    "backends": {},
                    "template_capabilities": [{
                        "capability": "object_track",
                        "template_ids": ["video/sam3/track-mask"],
                        "available": True,
                        "reasons": {"note": "節點未檢查"},
                    }],
                }, handle)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = doctor.main(["--comfyui-path", comfy, "--snapshot-dir", tools])
            self.assertEqual(code, 0)
            self.assertIn("  template: 可用 object_track (節點未檢查)", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
