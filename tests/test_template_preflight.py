"""PR 2.2:template preflight(平台閘門、/object_info、模型檔、sha256 快取、cuda 節點);PR 2.3 的修正也在這裡。

用假的 ComfyUI(本機 HTTP server 只回 /object_info)和暫存的小模型檔;Windows 路徑用 ntpath 模擬。
"""
import hashlib
import io
import json
import ntpath
import os
import random
import shutil
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golden_template_graphs as golden  # noqa: E402

from comfyui_pipeline.runner import cli  # noqa: E402
from comfyui_pipeline.runner import preflight as P  # noqa: E402
from comfyui_pipeline.runner import template as T  # noqa: E402

ROOT = Path(golden.ROOT)
TEMPLATES = Path(golden.TEMPLATES)
URL_ENV = ("COMFY_URL", "COMFYUI_URL", "COMFY_CONFIG", "COMFYUI_CONFIG", "COMFY_CONFIG_PATH", "COMFYUI_CONFIG_PATH")


def object_info_for(template, combo_style="list", drop_classes=(), drop_options=()):
    """依 template 的 graph 產生假的 /object_info:每個 class 都有,模型 input 是含檔名的選項清單。"""
    model_inputs = {(m["node"], m["input"]): m["filename"] for m in template.data["models"]}
    payload = {}
    for node_id, node in template.graph.items():
        cls = node["class_type"]
        if cls in drop_classes:
            continue
        required = payload.setdefault(cls, {"input": {"required": {}, "optional": {}}})["input"]["required"]
        for field in node["inputs"]:
            filename = model_inputs.get((node_id, field))
            if filename is None:
                required.setdefault(field, ["STRING", {}])
                continue
            spec = required.get(field)
            known = (spec[0] if combo_style == "list" else spec[1]["options"]) if spec and spec[0] != "STRING" \
                else ["other.safetensors"]
            options = [name for name in dict.fromkeys(known + [filename]) if name not in drop_options]
            required[field] = [options, {}] if combo_style == "list" else ["COMBO", {"options": options}]
    return payload


class FakeComfy:
    """只回 GET /object_info 的本機 server;記錄所有請求,確認 preflight 沒有上傳或 queue。"""

    def __init__(self, payload):
        self.payload = payload
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self):
                outer.requests.append((self.command, self.path))
                if self.command == "GET" and self.path == "/object_info":
                    body = json.dumps(outer.payload).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            do_GET = do_POST = _reply

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class PreflightFixture:
    """暫存 templates 根目錄(模型 pin 改成小檔)、ComfyUI 資料夾、設定檔與假 server。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "templates"
        self.comfy = Path(self.tmp) / "ComfyUI"
        (self.comfy / "tools").mkdir(parents=True)
        self.servers = []
        self.env = mock.patch.dict(os.environ, {k: "" for k in URL_ENV})
        self.env.start()
        for key in URL_ENV:
            os.environ.pop(key, None)

    def tearDown(self):
        self.env.stop()
        for server in self.servers:
            server.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def install(self, template_id, create_files=True, edit=None):
        """複製 template,把每個模型改成 3～10 KB 的小檔(寫進暫存 ComfyUI),回傳載入後的 Template。"""
        folder = self.root / template_id
        shutil.copytree(TEMPLATES / template_id, folder)
        data = json.loads((folder / "template.json").read_text(encoding="utf-8"))
        for index, model in enumerate(data["models"]):
            content = (f"{template_id}:{model['role']}:{index}".encode("utf-8") * 400)[: 3000 + index * 700]
            model["size_bytes"] = len(content)
            model["sha256"] = hashlib.sha256(content).hexdigest()
            target = self.comfy.joinpath(*model["path"].split("/"))
            if create_files and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        if edit:
            edit(data)
        (folder / "template.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return T.load_template(self.root, template_id, repo_root=ROOT)

    def server(self, template, **kwargs):
        server = FakeComfy(object_info_for(template, **kwargs))
        self.servers.append(server)
        return server

    def write_config(self, url="http://127.0.0.1:1", platform_key="windows-cuda", comfyui_path=None):
        config = Path(self.tmp) / "local_config.json"
        config.write_text(json.dumps({"comfyui_url": url, "comfyui_path": str(comfyui_path or self.comfy)}),
                          encoding="utf-8")
        if platform_key:
            (self.comfy / "tools" / "device_config.json").write_text(
                json.dumps({"platform_key": platform_key, "usable_memory_mb": 15000}), encoding="utf-8")
        return config

    def settings(self, url, platform_key="windows-cuda"):
        return {"comfy_url": url, "comfy_url_source": "--comfy-url", "comfyui_path": str(self.comfy),
                "platform_key": platform_key, "platform_source": "test", "device": {}, "platform_problem": None,
                "config_path": None, "config_source": None, "snapshot_dir": None, "repo_root": None}

    def preflight(self, template, url, platform_key="windows-cuda", **kwargs):
        return P.run_preflight(template, self.settings(url, platform_key), **kwargs)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(list(argv), root=self.root, out=out, err=err, rng=random.Random(5))
        return code, out.getvalue(), err.getvalue()


class PreflightChecksTests(PreflightFixture, unittest.TestCase):
    def test_all_checks_pass_and_only_object_info_is_requested(self):
        template = self.install("video/sam3/track-mask")
        server = self.server(template)
        report = self.preflight(template, server.url)
        self.assertEqual(P.PASS, report["status"], report["problems"])
        self.assertEqual([("GET", "/object_info")], server.requests)
        self.assertEqual("ok", report["checks"]["object_info"]["selectors"][0]["result"])
        self.assertEqual("skipped", report["checks"]["models"][0]["sha256"])

    def test_new_combo_format_is_understood(self):
        template = self.install("video/sam3/track-text")
        report = self.preflight(template, self.server(template, combo_style="combo").url)
        self.assertEqual(P.PASS, report["status"], report["problems"])

    def test_missing_node_class_blocks(self):
        template = self.install("video/sam3/track-text")
        report = self.preflight(template, self.server(template, drop_classes=("SAM3_VideoTrack",)).url)
        self.assertEqual(P.BLOCKED, report["status"])
        self.assertTrue(any("SAM3_VideoTrack" in p for p in report["problems"]), report["problems"])

    def test_selector_without_filename_blocks(self):
        template = self.install("video/sam3/track-text")
        report = self.preflight(template, self.server(template, drop_options=("sam3.1_multiplex_fp16.safetensors",)).url)
        self.assertEqual(P.BLOCKED, report["status"])
        self.assertTrue(any("sam3.1_multiplex_fp16.safetensors" in p and "選項" in p for p in report["problems"]))

    def test_missing_model_file_lists_path_and_auto_download(self):
        template = self.install("video/wan-animate/mix")
        sam2 = self.comfy / "models" / "sam2" / "sam2_hiera_base_plus.safetensors"
        sam2.unlink()
        report = self.preflight(template, self.server(template).url)
        self.assertEqual(P.BLOCKED, report["status"])
        problem = next(p for p in report["problems"] if "sam2_hiera_base_plus" in p)
        self.assertIn(str(sam2), problem)
        self.assertIn("自動下載", problem)

    def test_dwpose_files_are_guarded_against_auto_download(self):
        template = self.install("video/wan-animate/move")
        dw = self.comfy.joinpath(*"custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/dw-ll_ucoco_384.onnx".split("/"))
        dw.unlink()
        report = self.preflight(template, self.server(template).url)
        problem = next(p for p in report["problems"] if "dw-ll_ucoco_384.onnx" in p)
        self.assertIn(str(dw), problem)
        self.assertIn("自動下載", problem)

    def test_size_mismatch_blocks(self):
        template = self.install("video/sam3/track-mask")
        target = self.comfy / "models" / "checkpoints" / "sam3.1_multiplex_fp16.safetensors"
        target.write_bytes(target.read_bytes() + b"x")
        report = self.preflight(template, self.server(template).url)
        self.assertTrue(any("大小不符" in p and str(target) in p for p in report["problems"]), report["problems"])
        # 摘要要分開「存在」與「大小相符」,不能只寫 1/1 存在
        line = next(l for l in P.summary_lines(report) if "模型檔" in l)
        self.assertIn("存在 1/1,大小相符 0/1", line)
        self.assertIn("1 個檔案存在但大小不符", line)

    def test_unreachable_url_still_checks_files(self):
        template = self.install("video/sam3/track-mask")
        (self.comfy / "models" / "checkpoints" / "sam3.1_multiplex_fp16.safetensors").unlink()
        report = self.preflight(template, "http://127.0.0.1:1")
        self.assertFalse(report["checks"]["comfyui"]["reachable"])
        self.assertTrue(any("object_info" in p and "127.0.0.1:1" in p for p in report["problems"]))
        self.assertTrue(any("找不到模型檔" in p for p in report["problems"]))

    def test_no_comfyui_path_blocks(self):
        template = self.install("video/sam3/track-mask")
        settings = dict(self.settings(self.server(template).url), comfyui_path=None)
        report = P.run_preflight(template, settings)
        self.assertTrue(any("comfyui_path" in p for p in report["problems"]))


class HashTests(PreflightFixture, unittest.TestCase):
    def test_verify_hashes_match_and_cache_reuse(self):
        template = self.install("video/sam3/track-mask")
        url = self.server(template).url
        cache = Path(self.tmp) / "runs" / P.HASH_CACHE_NAME
        first = self.preflight(template, url, verify_hashes=True, hash_cache_path=str(cache))
        self.assertEqual(P.PASS, first["status"], first["problems"])
        self.assertEqual(("match", "computed"), (first["checks"]["models"][0]["sha256"],
                                                 first["checks"]["models"][0]["sha256_source"]))
        self.assertTrue(cache.is_file())
        second = self.preflight(template, url, verify_hashes=True, hash_cache_path=str(cache))
        self.assertEqual("cache", second["checks"]["models"][0]["sha256_source"])

    def test_same_size_different_content_is_caught(self):
        template = self.install("video/sam3/track-mask")
        url = self.server(template).url
        cache = Path(self.tmp) / P.HASH_CACHE_NAME
        self.preflight(template, url, verify_hashes=True, hash_cache_path=str(cache))
        target = self.comfy / "models" / "checkpoints" / "sam3.1_multiplex_fp16.safetensors"
        data = bytearray(target.read_bytes())
        data[0] ^= 0xFF
        target.write_bytes(bytes(data))
        stamp = time.time() + 10
        os.utime(target, (stamp, stamp))  # 確保 mtime 不同,快取失效
        report = self.preflight(template, url, verify_hashes=True, hash_cache_path=str(cache))
        self.assertEqual(P.BLOCKED, report["status"])
        self.assertTrue(any("sha256 不符" in p for p in report["problems"]))

    def test_cache_key_normalises_windows_paths(self):
        a = P.HashCache.key(r"C:\Users\XU\ComfyUI\models\X.safetensors", ntpath)
        b = P.HashCache.key(r"c:/users/xu/comfyui/models/x.safetensors", ntpath)
        self.assertEqual(a, b)


class PlatformGateTests(PreflightFixture, unittest.TestCase):
    def test_untested_platform_refused_unless_flag(self):
        template = self.install("video/sam3/track-text")
        url = self.server(template).url
        refused = self.preflight(template, url, platform_key="macos-mps")
        self.assertEqual(P.BLOCKED, refused["status"])
        self.assertTrue(any("untested" in p and P.ALLOW_FLAG in p for p in refused["problems"]))
        allowed = self.preflight(template, url, platform_key="macos-mps", allow_unverified=True)
        self.assertEqual(P.PASS, allowed["status"], allowed["problems"])
        self.assertTrue(allowed["checks"]["platform"]["allowed_by_flag"])
        self.assertTrue(any(P.ALLOW_FLAG in w for w in allowed["warnings"]))

    def test_unlisted_platform_counts_as_untested(self):
        template = self.install("video/sam3/track-text")
        report = self.preflight(template, self.server(template).url, platform_key="linux-cuda")
        self.assertTrue(any("沒有列出平台 linux-cuda" in p for p in report["problems"]))

    def test_unsupported_platform_refused_even_with_flag(self):
        def mark(data):
            data["capability_gate"]["platforms"]["macos-mps"]["status"] = "unsupported"
        template = self.install("video/sam3/track-text", edit=mark)
        report = self.preflight(template, self.server(template).url, platform_key="macos-mps", allow_unverified=True)
        self.assertEqual(P.BLOCKED, report["status"])

    def test_cuda_device_node_refused_on_mps(self):
        template = self.install("video/wan-animate/mix")
        url = self.server(template).url
        refused = self.preflight(template, url, platform_key="macos-mps")
        self.assertTrue(any("node 108" in p and "device=cuda" in p for p in refused["problems"]), refused["problems"])
        allowed = self.preflight(template, url, platform_key="macos-mps", allow_unverified=True)
        self.assertEqual(P.PASS, allowed["status"], allowed["problems"])
        self.assertTrue(any("node 108" in w for w in allowed["warnings"]))
        on_cuda = self.preflight(template, url, platform_key="windows-cuda")
        self.assertEqual(P.PASS, on_cuda["status"], on_cuda["problems"])

    def test_cuda_scan_only_hits_mix_graphs(self):
        hits = {tid: P.cuda_device_nodes(T.load_template(TEMPLATES, tid, repo_root=ROOT).graph)
                for tid in T.discover(TEMPLATES)}
        self.assertEqual({"video/wan-animate/mix": [("108", "DownloadAndLoadSAM2Model")],
                          "video/wan-animate/mix-extend": [("108", "DownloadAndLoadSAM2Model")]},
                         {k: v for k, v in hits.items() if v})

    def test_status_draft_warns_and_retired_blocks(self):
        def draft(data):
            data["status"] = "draft"
        template = self.install("video/sam3/track-text", edit=draft)
        report = self.preflight(template, self.server(template).url)
        self.assertEqual(P.PASS, report["status"])
        self.assertTrue(any("draft" in w for w in report["warnings"]))
        shutil.rmtree(self.root / "video/sam3/track-mask", ignore_errors=True)

        def retired(data):
            data["status"] = "retired"
        template = self.install("video/sam3/track-mask", edit=retired)
        self.assertEqual(P.BLOCKED, self.preflight(template, self.server(template).url)["status"])

    def test_min_memory(self):
        def need(data):
            data["capability_gate"]["min_memory_mb"] = 20000
        template = self.install("video/sam3/track-text", edit=need)
        settings = dict(self.settings(self.server(template).url), device={"usable_memory_mb": 15000})
        report = P.run_preflight(template, settings)
        self.assertTrue(any("20000" in p for p in report["problems"]))


class SettingsTests(unittest.TestCase):
    """設定解析;Windows 路徑以 ntpath 模擬。"""

    def fake_isfile(self, existing):
        keys = {ntpath.normcase(ntpath.normpath(p)) for p in existing}
        return lambda path: ntpath.normcase(ntpath.normpath(path)) in keys

    def test_windows_paths(self):
        files = [r"C:\repo\AGENTS.md", r"C:\repo\tools_src\gameart.py", r"C:\repo\local_config.json",
                 r"C:\Users\XU\ComfyUI\tools\device_config.json"]
        data = {r"C:\repo\local_config.json": {"comfyui_path": r"C:\Users\XU\ComfyUI"},
                r"C:\Users\XU\ComfyUI\tools\device_config.json": {"platform_key": "windows-cuda"}}
        settings = P.resolve_settings("local_config.json", "http://127.0.0.1:8188", script_dir=r"C:\repo\tools_src",
                                      cwd=r"D:\elsewhere", isfile=self.fake_isfile(files), pathmod=ntpath,
                                      read_json=lambda p: data.get(ntpath.normpath(p)))
        self.assertEqual(r"C:\repo\local_config.json", settings["config_path"])
        self.assertEqual(r"C:\Users\XU\ComfyUI", settings["comfyui_path"])
        self.assertEqual(r"C:\Users\XU\ComfyUI\tools", settings["snapshot_dir"])
        self.assertEqual("windows-cuda", settings["platform_key"])
        self.assertEqual(r"C:\Users\XU\ComfyUI\custom_nodes\comfyui_controlnet_aux\ckpts\yzd-v\DWPose\dw-ll_ucoco_384.onnx",
                         P.model_file_path(settings["comfyui_path"],
                                           "custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/dw-ll_ucoco_384.onnx",
                                           ntpath))

    def test_missing_config_reports_resolved_path(self):
        files = [r"C:\repo\AGENTS.md", r"C:\repo\tools_src\gameart.py"]
        with self.assertRaises(P.PreflightConfigError) as ctx:
            P.resolve_settings(r"cfg\nope.json", "http://x:1", script_dir=r"C:\repo\tools_src", cwd=r"D:\x",
                               isfile=self.fake_isfile(files), pathmod=ntpath, read_json=lambda p: None)
        self.assertIn(r"C:\repo\cfg\nope.json", str(ctx.exception))

    def test_no_snapshot_needs_platform_key(self):
        files = [r"C:\repo\AGENTS.md", r"C:\repo\tools_src\gameart.py", r"C:\repo\local_config.json"]
        data = {r"C:\repo\local_config.json": {"comfyui_path": r"C:\ComfyUI"}}
        kwargs = dict(script_dir=r"C:\repo\tools_src", cwd=r"C:\repo", isfile=self.fake_isfile(files), pathmod=ntpath,
                      read_json=lambda p: data.get(ntpath.normpath(p)))
        settings = P.resolve_settings(None, "http://x:1", **kwargs)
        self.assertIsNone(settings["platform_key"])
        self.assertIn(r"C:\ComfyUI\tools", settings["platform_problem"])
        self.assertIn("--platform-key", settings["platform_problem"])
        forced = P.resolve_settings(None, "http://x:1", platform_key="macos-mps", **kwargs)
        self.assertEqual(("macos-mps", "--platform-key"), (forced["platform_key"], forced["platform_source"]))
        self.assertIsNone(forced["platform_mismatch"])

    def test_platform_key_differs_from_snapshot_warns_and_records_both(self):
        files = [r"C:\repo\AGENTS.md", r"C:\repo\tools_src\gameart.py", r"C:\repo\local_config.json",
                 r"C:\ComfyUI\tools\device_config.json"]
        data = {r"C:\repo\local_config.json": {"comfyui_path": r"C:\ComfyUI"},
                r"C:\ComfyUI\tools\device_config.json": {"platform_key": "windows-cuda"}}
        kwargs = dict(script_dir=r"C:\repo\tools_src", cwd=r"C:\repo", isfile=self.fake_isfile(files), pathmod=ntpath,
                      read_json=lambda p: data.get(ntpath.normpath(p)))
        same = P.resolve_settings(None, "http://x:1", platform_key="windows-cuda", **kwargs)
        self.assertIsNone(same["platform_mismatch"])
        forced = P.resolve_settings(None, "http://x:1", platform_key="macos-mps", **kwargs)
        self.assertEqual(("macos-mps", "windows-cuda"), (forced["platform_key"], forced["device_platform_key"]))
        self.assertIn(r"C:\ComfyUI\tools\device_config.json", forced["platform_mismatch"])
        template = T.load_template(TEMPLATES, "video/sam3/track-text", repo_root=ROOT)
        problems, warnings, info = P.check_platform(template, forced, allow_unverified=True)
        self.assertTrue(any("--platform-key macos-mps" in w and "windows-cuda" in w for w in warnings), warnings)
        self.assertEqual("windows-cuda", info["device_platform_key"])

    def test_url_from_config_when_no_flag(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=False):
            for key in URL_ENV:
                os.environ.pop(key, None)
            config = Path(tmp) / "c.json"
            config.write_text(json.dumps({"comfyui_url": "http://127.0.0.1:8188/", "comfyui_path": tmp}), encoding="utf-8")
            settings = P.resolve_settings(str(config), None, platform_key="windows-cuda", script_dir=tmp)
            self.assertEqual(("http://127.0.0.1:8188", "config"), (settings["comfy_url"], settings["comfy_url_source"]))


class PreflightCliTests(PreflightFixture, unittest.TestCase):
    def test_preflight_cli_pass_without_slots_and_writes_report(self):
        template = self.install("video/wan-animate/move")
        server = self.server(template)
        config = self.write_config()
        target = Path(self.tmp) / "pf"
        code, out, err = self.run_cli("video/wan-animate/move", "--preflight", "--config", str(config),
                                      "--comfy-url", server.url, "--output-dir", str(target))
        self.assertEqual(0, code, out + err)
        self.assertIn("結果: 通過", out)
        self.assertIn("沒有提供必填 slot: prompt", out)
        report = json.loads((target / cli.PREFLIGHT_FILE).read_text(encoding="utf-8"))
        self.assertEqual(("pass", "windows-cuda"), (report["status"], report["settings"]["platform_key"]))
        self.assertFalse((target / cli.DRYRUN_GRAPH).exists())  # slot 沒給齊就不產生 graph
        self.assertEqual([("GET", "/object_info")], server.requests)

    def test_preflight_cli_with_slots_writes_graph_and_json(self):
        template = self.install("video/sam3/track-text")
        server = self.server(template)
        config = self.write_config()
        target = Path(self.tmp) / "pf"
        code, out, err = self.run_cli("video/sam3/track-text", "--preflight", "--config", str(config),
                                      "--comfy-url", server.url, "--set", "track_text=mallet", "--verify-hashes",
                                      "--output-dir", str(target), "--json")
        self.assertEqual(0, code, out + err)
        report = json.loads(out)
        self.assertEqual("match", report["checks"]["models"][0]["sha256"])
        self.assertTrue((target / cli.DRYRUN_GRAPH).is_file())
        self.assertTrue((Path(self.tmp) / P.HASH_CACHE_NAME).is_file())  # <output-dir>/../.hash-cache.json

    def test_preflight_cli_blocked_exit_1(self):
        template = self.install("video/wan-animate/mix")
        server = self.server(template)
        config = self.write_config(platform_key="macos-mps")
        code, out, _ = self.run_cli("video/wan-animate/mix", "--preflight", "--config", str(config),
                                    "--comfy-url", server.url)
        self.assertEqual(1, code)
        self.assertIn("macos-mps", out)
        self.assertIn("node 108", out)

    def test_unreachable_url_exit_1(self):
        self.install("video/sam3/track-mask")
        config = self.write_config()
        code, out, _ = self.run_cli("video/sam3/track-mask", "--preflight", "--config", str(config),
                                    "--comfy-url", "http://127.0.0.1:1")
        self.assertEqual(1, code)
        self.assertIn("http://127.0.0.1:1/object_info", out)

    def test_config_errors_exit_2(self):
        self.install("video/sam3/track-mask")
        code, _, err = self.run_cli("video/sam3/track-mask", "--preflight", "--config",
                                    str(Path(self.tmp) / "missing.json"), "--comfy-url", "http://127.0.0.1:1")
        self.assertEqual(2, code)
        self.assertIn("missing.json", err)
        self.assertEqual(2, self.run_cli("video/sam3/track-mask", "--dry-run", "--verify-hashes")[0])
        with self.assertRaises(SystemExit):
            self.run_cli("video/sam3/track-mask", "--dry-run", "--preflight")

    def test_real_run_runs_preflight_then_checks_inputs(self):
        template = self.install("video/sam3/track-text")
        server = self.server(template)
        config = self.write_config()
        clip = Path(self.tmp) / "clip.mp4"
        clip.write_bytes(b"not really a video")
        out_dir = Path(self.tmp) / "run"
        code, out, err = self.run_cli("video/sam3/track-text", "--config", str(config), "--comfy-url", server.url,
                                      "--set", "track_text=mallet", "--set", f"source_video={clip}",
                                      "--output-dir", str(out_dir))
        # preflight 通過 → pre 檢查讀不了假影片(或缺 PyAV)→ 結束碼 1,沒有上傳或 queue
        self.assertEqual(1, code, out + err)
        self.assertIn("結果: 通過", out)
        self.assertEqual("pre", json.loads((out_dir / "run.result.json").read_text(encoding="utf-8"))["failure"]["step"])
        self.assertEqual([], [r for r in server.requests if r[0] == "POST"])
        # 實際執行時缺上傳檔案 → 參數錯誤(2),不會連線
        code, _, err = self.run_cli("video/sam3/track-text", "--config", str(config), "--comfy-url", server.url,
                                    "--set", "track_text=mallet")
        self.assertEqual(2, code)
        self.assertIn("source_video", err)

    def test_preflight_platform_mismatch_recorded_in_report(self):
        template = self.install("video/sam3/track-text")
        server = self.server(template)
        config = self.write_config(server.url)
        out_dir = Path(self.tmp) / "pf"
        code, out, err = self.run_cli("video/sam3/track-text", "--preflight", "--config", str(config),
                                      "--platform-key", "macos-mps", "--allow-unverified-platform",
                                      "--output-dir", str(out_dir))
        self.assertEqual(0, code, out + err)
        report = json.loads((out_dir / "preflight.json").read_text(encoding="utf-8"))
        self.assertEqual(("macos-mps", "windows-cuda"),
                         (report["settings"]["platform_key"], report["settings"]["device_platform_key"]))
        self.assertIn("機器快照記錄的是 windows-cuda", out)
        self.assertTrue(any("--platform-key macos-mps" in w for w in report["warnings"]))

    def test_stdout_is_flushed_before_stderr(self):
        """stdout 有緩衝時,stderr 的訊息不能跑到 stdout 已印的內容前面。"""
        events = []

        class Buffered(io.StringIO):
            def __init__(self, name):
                super().__init__()
                self.name, self.pending = name, ""

            def write(self, text):
                self.pending += text
                return len(text)

            def flush(self):
                if self.pending:
                    events.append((self.name, self.pending))
                    self.pending = ""

        class Unbuffered(io.StringIO):
            def write(self, text):
                events.append(("err", text))
                return len(text)

        template = self.install("video/sam3/track-text")
        config = self.write_config()
        out = Buffered("out")
        # dry-run:graph 印到 stdout,摘要到 stderr
        cli.main(["video/sam3/track-text", "--dry-run", "--set", "track_text=x"], root=self.root, out=out,
                 err=Unbuffered(), rng=random.Random(5))
        self.assertEqual("out", events[0][0], events[:2])
        # preflight 後的錯誤訊息(結束碼 2)也要在 stdout 之後
        events.clear()
        out = Buffered("out")
        out.write("[preflight] 前面的輸出\n")
        cli.main(["video/sam3/track-text", "--preflight", "--config", str(config), "--timeout", "5"], root=self.root,
                 out=out, err=Unbuffered(), rng=random.Random(5))
        self.assertEqual(["out", "err"], [e[0] for e in events[:2]], events)


class RealTemplatePinsTests(unittest.TestCase):
    def test_every_model_is_pinned_and_wan_templates_promoted(self):
        for template_id in T.discover(TEMPLATES):
            template = T.load_template(TEMPLATES, template_id, repo_root=ROOT)
            with self.subTest(template_id):
                for model in template.data["models"]:
                    self.assertRegex(model["sha256"] or "", r"^[0-9a-f]{64}$", model["filename"])
                    self.assertIsInstance(model["size_bytes"], int)
                self.assertEqual("technical_pass", template.data["status"])
                self.assertNotIn("status_note", template.data)

    def test_dwpose_pin_and_auto_download_flags(self):
        for name in ("mix", "move", "mix-extend", "move-extend"):
            template = T.load_template(TEMPLATES, f"video/wan-animate/{name}", repo_root=ROOT)
            by_name = {m["filename"]: m for m in template.data["models"]}
            dw = by_name["dw-ll_ucoco_384.onnx"]
            self.assertEqual("custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/dw-ll_ucoco_384.onnx", dw["path"])
            self.assertEqual(134399116, dw["size_bytes"])
            self.assertEqual("724f4ff2439ed61afb86fb8a1951ec39c6220682803b4a8bd4f598cd913b1843", dw["sha256"])
            expected_auto = {"dw-ll_ucoco_384.onnx", "yolox_l.onnx"} | ({"sam2_hiera_base_plus.safetensors"} if "mix" in name else set())
            self.assertEqual(expected_auto, {f for f, m in by_name.items() if m.get("auto_download")})

    def test_old_manifest_has_dwpose_pin(self):
        manifest = json.loads((ROOT / "skills/comfyui-wan-animate/assets/template-manifest.json").read_text(encoding="utf-8"))
        pins = {m["source"]: m for m in manifest["models"]}
        self.assertEqual("724f4ff2439ed61afb86fb8a1951ec39c6220682803b4a8bd4f598cd913b1843", pins["dw-ll_ucoco_384.onnx"]["sha256"])


if __name__ == "__main__":
    unittest.main()
