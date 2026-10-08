"""PR 2.3:`gameart.py run <template>` 實際執行(上傳 → queue → 輪詢 → 下載 → result manifest)。

用本機假 ComfyUI(/object_info、/system_stats、/upload/image、/prompt、/history、/view、/queue)跑完整流程。
大部分測試用假的 media 物件,不需要 PyAV／Pillow;RealMediaTests 用真的小影片,缺套件時 skip。
"""
import email.parser
import email.policy
import hashlib
import io
import json
import os
import random
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import optional_deps  # noqa: E402
from test_template_preflight import PreflightFixture, object_info_for  # noqa: E402

import asset_review  # noqa: E402
from comfyui_pipeline import client  # noqa: E402
from comfyui_pipeline import image_results as IR  # noqa: E402
from comfyui_pipeline.runner import cli  # noqa: E402
from comfyui_pipeline.runner import run as R  # noqa: E402
from comfyui_pipeline.runner import steps as S  # noqa: E402

PROMPT_ID = "11111111-2222-3333-4444-555555555555"


def history_success(outputs, start=1_000_000, end=1_012_345):
    return {"prompt": [], "outputs": outputs,
            "status": {"status_str": "success", "completed": True,
                       "messages": [["execution_start", {"prompt_id": PROMPT_ID, "timestamp": start}],
                                    ["execution_success", {"prompt_id": PROMPT_ID, "timestamp": end}]]}}


class FakeComfyRun:
    """記錄所有請求;``history`` 是每次輪詢依序回傳的 entry(None=還沒完成),用完後重複最後一個。"""

    def __init__(self, object_info):
        self.object_info = object_info
        self.requests, self.uploads, self.prompts, self.queue_posts = [], [], [], []
        self.history = [None]
        self.files = {}           # filename -> bytes(/view)
        self.missing_view = set()
        self.queue_state = {"queue_running": [], "queue_pending": []}
        self.upload_status = 200
        self.prompt_response = None
        self.polls = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _json(self, data, status=200):
                body = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                outer.requests.append(("GET", parsed.path))
                if parsed.path == "/object_info":
                    return self._json(outer.object_info)
                if parsed.path == "/system_stats":
                    return self._json({"system": {"comfyui_version": "0.34.0", "python_version": "3.12.9",
                                                  "pytorch_version": "2.7.0+cu128"},
                                       "devices": [{"name": "cuda:0 Fake GPU"}]})
                if parsed.path.startswith("/history/"):
                    index = min(outer.polls, len(outer.history) - 1)
                    outer.polls += 1
                    entry = outer.history[index]
                    return self._json({PROMPT_ID: entry} if entry is not None else {})
                if parsed.path == "/view":
                    query = urllib.parse.parse_qs(parsed.query)
                    name = query["filename"][0]
                    if name in outer.missing_view or name not in outer.files:
                        self.send_response(404)
                        self.end_headers()
                        return None
                    body = outer.files[name]
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return None
                if parsed.path == "/queue":
                    return self._json(outer.queue_state)
                self.send_response(404)
                self.end_headers()
                return None

            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                outer.requests.append(("POST", parsed.path))
                body = self._body()
                if parsed.path == "/upload/image":
                    message = email.parser.BytesParser(policy=email.policy.default).parsebytes(
                        b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + body)
                    fields, record = {}, {}
                    for part in message.iter_parts():
                        name = part.get_param("name", header="content-disposition")
                        if part.get_filename():
                            record["filename"] = part.get_filename()
                            record["bytes"] = part.get_payload(decode=True)
                        else:
                            fields[name] = part.get_content().strip()
                    record["fields"] = fields
                    outer.uploads.append(record)
                    if outer.upload_status != 200:
                        return self._json({"error": "boom"}, outer.upload_status)
                    return self._json({"name": record["filename"], "subfolder": fields.get("subfolder", ""),
                                       "type": "input"})
                if parsed.path == "/prompt":
                    outer.prompts.append(json.loads(body))
                    return self._json(outer.prompt_response or {"prompt_id": PROMPT_ID, "number": 7, "node_errors": {}})
                if parsed.path == "/queue":
                    outer.queue_posts.append(json.loads(body))
                    return self._json({})
                self.send_response(404)
                self.end_headers()
                return None

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class FakeMedia:
    """和 media.py 同名的函式,回傳設定好的量測值;不讀真正的媒體。"""

    MediaDependencyError = RuntimeError

    def __init__(self, video=None, image=None, mask=None, png=None, output_video=None):
        self.video = dict({"width": 64, "height": 48, "frames": 8, "fps": "16/1", "fps_value": 16.0,
                           "pts_uniform": True, "has_audio": False, "duration_seconds": 0.5}, **(video or {}))
        self.image = image or {"width": 512, "height": 512, "mode": "RGB", "has_alpha": False}
        self.mask = dict({"width": 64, "height": 48, "nonzero": 120, "has_transparency": False}, **(mask or {}))
        self.png = dict({"width": 64, "height": 48, "mode": "L", "grayscale": True}, **(png or {}))
        self.output_video = output_video
        self.calls = []

    def probe_image(self, path):
        self.calls.append(("probe_image", path))
        return dict(self.image)

    def probe_video(self, path):
        self.calls.append(("probe_video", path))
        if self.output_video and os.sep + "outputs" + os.sep in str(path):
            return dict(self.output_video)
        return dict(self.video)

    def mask_stats(self, path, channel="red"):
        return dict(self.mask)

    def png_frame_stats(self, path):
        return dict(self.png)

    def extract_keyframes(self, video_path, which, dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
        result = {}
        for index, name in enumerate(which):
            path = os.path.join(dest_dir, f"{name}.png")
            Path(path).write_bytes(b"png")
            result[name] = {"path": path, "frame_index": index}
        return result

    def mask_preview(self, video_path, mask_paths, dest_path):
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        Path(dest_path).write_bytes(b"preview")
        return dest_path


def png_outputs(count, prefix="run_", node="36", subfolder="gameart/video-sam3-track-mask"):
    files = {f"{prefix}{i:05d}_.png": f"mask {i}".encode() for i in range(1, count + 1)}
    outputs = {node: {"images": [{"filename": n, "subfolder": subfolder, "type": "output"} for n in files]}}
    return files, outputs


class RunFixture(PreflightFixture):
    def setUp(self):
        super().setUp()
        self.media = FakeMedia()
        patches = [mock.patch.object(R, "_media", self.media), mock.patch.object(R, "POLL_INTERVAL", 0.01)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.clip = Path(self.tmp) / "clip.mp4"
        self.clip.write_bytes(b"fake video bytes")
        self.mask = Path(self.tmp) / "mask.png"
        self.mask.write_bytes(b"fake mask bytes")
        self.ref = Path(self.tmp) / "ref.png"
        self.ref.write_bytes(b"fake ref bytes")

    def fake(self, template, **kwargs):
        server = FakeComfyRun(object_info_for(template, **kwargs))
        self.servers.append(server)
        return server

    def track_mask(self, count=8, history=None, **kwargs):
        template = self.install("video/sam3/track-mask")
        server = self.fake(template, **kwargs)
        server.files, outputs = png_outputs(count)
        server.history = history or [None, history_success(outputs)]
        return template, server

    def run_template(self, template_id, server, *extra, out_name="run"):
        config = self.write_config(server.url)
        self.out_dir = Path(self.tmp) / out_name
        args = [template_id, "--config", str(config), "--output-dir", str(self.out_dir), "--run-id", "abc123def"]
        if template_id == "video/sam3/track-mask":
            args += ["--set", f"source_video={self.clip}", "--set", f"seed_mask={self.mask}"]
        code, out, err = self.run_cli(*(args + list(extra)))
        manifest_path = self.out_dir / R.RESULT_FILE
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
        return code, out, err, manifest

    def posted(self, server):
        return [r for r in server.requests if r[0] == "POST"]


class SuccessTests(RunFixture, unittest.TestCase):
    def test_track_mask_end_to_end(self):
        template, server = self.track_mask()
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(0, code, out + err)
        self.assertEqual("completed", manifest["status"])
        self.assertEqual("template_run_result", manifest["kind"])
        self.assertEqual("pass", manifest["technical_validation"]["status"])
        self.assertEqual("pending", manifest["content_review"])
        self.assertIsNone(manifest["failure"])
        # 上傳:兩個檔案都到 run_id 子資料夾,overwrite=false
        self.assertEqual(2, len(server.uploads))
        for upload in server.uploads:
            self.assertEqual({"subfolder": "abc123def", "overwrite": "false"}, upload["fields"])
        self.assertEqual(b"fake video bytes", server.uploads[0]["bytes"])
        # 送出的 graph 用 subfolder/name,帶 client_id;只送一次
        self.assertEqual(1, len(server.prompts))
        body = server.prompts[0]
        self.assertEqual(manifest["client_id"], body["client_id"])
        self.assertEqual("abc123def/clip.mp4", body["prompt"]["1"]["inputs"]["file"])
        self.assertEqual("abc123def/mask.png", body["prompt"]["10"]["inputs"]["image"])
        self.assertEqual("gameart/video-sam3-track-mask/abc123def", body["prompt"]["36"]["inputs"]["filename_prefix"])
        self.assertEqual(IR.graph_sha256(body["prompt"]), manifest["graph_sha256"])
        saved = json.loads((self.out_dir / R.GRAPH_FILE).read_text(encoding="utf-8"))
        self.assertEqual(body["prompt"], saved)
        # 紀錄檔
        self.assertEqual(PROMPT_ID, manifest["prompt_id"])
        queue = json.loads((self.out_dir / R.QUEUE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(PROMPT_ID, queue["prompt_id"])
        history = json.loads((self.out_dir / R.HISTORY_FILE).read_text(encoding="utf-8"))
        self.assertIn(PROMPT_ID, history)
        uploads = json.loads((self.out_dir / R.UPLOADS_FILE).read_text(encoding="utf-8"))
        self.assertEqual("abc123def/clip.mp4", uploads["source_video"]["graph_value"])
        self.assertTrue((self.out_dir / "preflight.json").exists())
        self.assertTrue((self.out_dir / R.LOG_FILE).exists())
        # 輸出、sha256、量測值、時間
        self.assertEqual(8, len(manifest["outputs"]))
        first = manifest["outputs"][0]
        self.assertEqual(str(self.out_dir / "outputs" / "masks" / "run_00001_.png"), first["path"])
        self.assertEqual(hashlib.sha256(b"mask 1").hexdigest(), first["sha256"])
        self.assertEqual(("mask", "masks", "36"), (first["role"], first["output_id"], first["node"]))
        self.assertEqual(64, first["width"])
        self.assertEqual(12.345, manifest["timing"]["execution_seconds"])
        self.assertEqual("0.34.0", manifest["environment"]["comfyui_version"])
        self.assertEqual(hashlib.sha256(b"fake video bytes").hexdigest(), manifest["inputs"][0]["sha256"])
        self.assertEqual("abc123def", manifest["inputs"][0]["upload"]["subfolder"])
        self.assertEqual(str(self.out_dir / "keyframes" / "mask_preview.png"), manifest["mask_preview"])
        self.assertEqual("windows-cuda", manifest["platform_key"])
        self.assertEqual("technical_pass", manifest["platform_status"])
        steps = [c["step"] for c in manifest["technical_validation"]["checks"]]
        self.assertEqual(["check_video", "check_mask_matches_video", "check_png_sequence", "mask_preview"], steps)
        self.assertNotIn("/interrupt", [r[1] for r in server.requests])
        self.assertIn("已送出 prompt_id=" + PROMPT_ID, out)
        self.assertIn("美術是否接受仍待人工審查", out)

    def test_json_mode_prints_only_status(self):
        template, server = self.track_mask()
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server, "--json")
        self.assertEqual(0, code, err)
        data = json.loads(out)
        self.assertEqual("completed", data["status"])
        self.assertEqual(str(self.out_dir / R.RESULT_FILE), data["result"])
        self.assertIn("[run]", err)

    def test_wan_extend_records_seam_reminder_and_keyframes(self):
        template = self.install("video/wan-animate/move-extend")
        server = self.fake(template)
        server.files = {"clip_00001_.mp4": b"video"}
        server.history = [history_success({"19": {"images": [{"filename": "clip_00001_.mp4", "subfolder": "",
                                                              "type": "output"}], "animated": [True]}})]
        self.media.video.update(frames=61, width=384, height=384)
        self.media.output_video = dict(self.media.video)
        code, out, err, manifest = self.run_template("video/wan-animate/move-extend", server,
                                            "--set", f"reference_image={self.ref}", "--set", f"source_video={self.clip}",
                                            "--set", "prompt=hero", "--set", "seed=5", "--set", "seed_segment2=6")
        self.assertEqual(0, code, out + err)
        self.assertTrue(any("延伸段接縫(第 32/33 幀前後)需要人工檢查" in w
                            for w in manifest["technical_validation"]["warnings"]))
        self.assertIn("延伸段接縫", out)
        self.assertEqual({"first", "middle", "last"}, set(manifest["keyframes"]))
        self.assertEqual(61, manifest["outputs"][0]["frames"])
        seeds = [v for node in manifest["resolved_seeds"].values() for v in node.values()]
        self.assertIn(5, seeds)
        self.assertIn(6, seeds)


class FailureTests(RunFixture, unittest.TestCase):
    def assertFailed(self, manifest, step):
        self.assertIsNotNone(manifest)
        self.assertEqual("failed", manifest["status"])
        self.assertEqual("fail", manifest["technical_validation"]["status"])
        self.assertEqual(step, manifest["failure"]["step"], manifest["failure"])

    def test_preflight_blocked_writes_failed_manifest_and_uploads_nothing(self):
        template, server = self.track_mask(drop_classes=("SAM3_VideoTrack",))
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "preflight")
        self.assertIn("SAM3_VideoTrack", manifest["failure"]["error"])
        self.assertEqual([], self.posted(server))

    def test_unreachable_comfyui_blocks_before_upload(self):
        template = self.install("video/sam3/track-mask")
        config = self.write_config("http://127.0.0.1:1")
        out_dir = Path(self.tmp) / "unreachable"
        code, out, err = self.run_cli("video/sam3/track-mask", "--config", str(config), "--output-dir", str(out_dir),
                                      "--set", f"source_video={self.clip}", "--set", f"seed_mask={self.mask}")
        self.assertEqual(1, code)
        manifest = json.loads((out_dir / R.RESULT_FILE).read_text(encoding="utf-8"))
        self.assertEqual("preflight", manifest["failure"]["step"])
        self.assertIn("無法取得", manifest["failure"]["error"])

    def test_missing_input_file_is_preflight_problem(self):
        template, server = self.track_mask()
        self.mask.unlink()
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "preflight")
        self.assertIn("mask.png", manifest["failure"]["error"])
        self.assertEqual([], self.posted(server))

    def test_pre_check_failure_uploads_nothing(self):
        template, server = self.track_mask()
        self.media.mask.update(width=32)
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "pre")
        self.assertIn("尺寸不同", manifest["failure"]["error"])
        self.assertEqual([], self.posted(server))

    def test_missing_media_dependency_is_reported(self):
        template, server = self.track_mask()
        self.media.probe_video = mock.Mock(side_effect=RuntimeError("檢查媒體需要 PyAV,…python_exe"))
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "pre")
        self.assertIn("python_exe", manifest["failure"]["error"])

    def test_upload_error(self):
        template, server = self.track_mask()
        server.upload_status = 500
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "upload")
        self.assertEqual([], server.prompts)

    def test_node_errors_on_queue(self):
        template, server = self.track_mask()
        server.prompt_response = {"error": "invalid", "node_errors": {"1": {"errors": ["bad"]}}}
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "queue")
        self.assertIsNone(manifest["prompt_id"])
        self.assertIn("節點參數錯誤", manifest["failure"]["error"])

    def test_execution_error_keeps_history(self):
        entry = {"outputs": {}, "status": {"status_str": "error", "completed": False, "messages": [
            ["execution_start", {"timestamp": 10}],
            ["execution_error", {"node_id": "20", "node_type": "SAM3_VideoTrack", "exception_type": "OutOfMemoryError",
                                 "exception_message": "CUDA out of memory", "timestamp": 2010}]]}}
        template, server = self.track_mask(history=[None, entry])
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "execution")
        self.assertIn("CUDA out of memory", manifest["failure"]["error"])
        self.assertEqual(PROMPT_ID, manifest["failure"]["prompt_id"])
        self.assertEqual(2.0, manifest["timing"]["execution_seconds"])
        self.assertTrue((self.out_dir / R.HISTORY_FILE).exists())
        self.assertEqual([], manifest["outputs"])
        self.assertEqual(1, len(server.prompts))

    def test_comfyui_side_interrupt(self):
        entry = {"outputs": {}, "status": {"status_str": "error", "completed": False, "messages": [
            ["execution_interrupted", {"node_id": "20", "node_type": "SAM3_VideoTrack", "timestamp": 5}]]}}
        template, server = self.track_mask(history=[entry])
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "interrupted")
        self.assertIn("中斷", manifest["failure"]["error"])

    def test_completed_without_success_is_not_a_pass(self):
        _files, outputs = png_outputs(8)
        entry = {"outputs": outputs, "status": {"completed": True, "messages": []}}
        template, server = self.track_mask(history=[entry])
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "execution")

    def test_timeout_does_not_resend_and_cancels_only_own_pending_prompt(self):
        template, server = self.track_mask(history=[None])
        server.queue_state = {"queue_running": [], "queue_pending": [[7, PROMPT_ID, {}, {}, []]]}
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server, "--timeout", "0.3")
        self.assertEqual(1, code)
        self.assertFailed(manifest, "timeout")
        self.assertEqual(PROMPT_ID, manifest["prompt_id"])
        self.assertEqual("pending", manifest["failure"]["queue_status"]["status"])
        self.assertEqual([{"delete": [PROMPT_ID]}], server.queue_posts)
        self.assertEqual(1, len(server.prompts))
        self.assertNotIn(("POST", "/interrupt"), server.requests)
        self.assertTrue((self.out_dir / R.QUEUE_FILE).exists())

    def test_timeout_while_running_leaves_job_alone(self):
        template, server = self.track_mask(history=[None])
        server.queue_state = {"queue_running": [[7, PROMPT_ID, {}, {}, []]], "queue_pending": []}
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server, "--timeout", "0.3")
        self.assertEqual(1, code)
        self.assertEqual("running", manifest["failure"]["queue_status"]["status"])
        self.assertEqual([], server.queue_posts)
        self.assertIn("不會全域 interrupt", manifest["failure"]["note"])

    def test_ctrl_c_while_waiting(self):
        template, server = self.track_mask(history=[None])
        server.queue_state = {"queue_running": [[7, PROMPT_ID, {}, {}, []]], "queue_pending": []}
        with mock.patch.object(client.time, "sleep", side_effect=KeyboardInterrupt):
            code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "queue")
        self.assertIn("Ctrl+C", manifest["failure"]["error"])
        self.assertEqual(PROMPT_ID, manifest["failure"]["prompt_id"])
        self.assertEqual("running", manifest["failure"]["queue_status"]["status"])
        self.assertEqual([], server.queue_posts)
        self.assertEqual(1, len(server.prompts))

    def test_poll_connection_lost_mid_run(self):
        template, server = self.track_mask(history=[None])
        original = client.urllib.request.urlopen

        def flaky(request, *args, **kwargs):
            url = request if isinstance(request, str) else request.full_url
            if "/history/" in url:
                raise client.urllib.error.URLError("connection refused")
            return original(request, *args, **kwargs)

        with mock.patch.object(client.urllib.request, "urlopen", side_effect=flaky):
            code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "poll")
        self.assertEqual(PROMPT_ID, manifest["failure"]["prompt_id"])
        self.assertEqual(1, len(server.prompts))

    def test_partial_outputs_are_kept(self):
        template, server = self.track_mask()
        server.missing_view = {"run_00003_.png"}
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "download")
        self.assertIn("run_00003_.png", manifest["failure"]["error"])
        self.assertEqual(7, len(manifest["outputs"]))
        self.assertFalse(list((self.out_dir / "outputs" / "masks").glob("*.part")))

    def test_path_traversal_output_is_refused(self):
        template = self.install("video/sam3/track-mask")
        server = self.fake(template)
        server.files = {"../evil.png": b"evil"}
        server.history = [history_success({"36": {"images": [{"filename": "../evil.png", "subfolder": "",
                                                              "type": "output"}]}})]
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "download")
        self.assertIn("path traversal", manifest["failure"]["error"])
        self.assertFalse((self.out_dir / "outputs" / "evil.png").exists())
        self.assertFalse((self.out_dir / "evil.png").exists())

    def test_frame_count_mismatch_fails_post_check(self):
        template, server = self.track_mask(count=7)
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "post")
        self.assertIn("張數是 7,需要 8", manifest["failure"]["error"])
        self.assertEqual(7, len(manifest["outputs"]))

    def test_missing_output_node(self):
        template, server = self.track_mask(history=[history_success({})])
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        self.assertFailed(manifest, "download")

    def test_optional_mask_preview_failure_is_only_a_warning(self):
        template, server = self.track_mask()
        self.media.mask_preview = mock.Mock(side_effect=ImportError("no numpy"))
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(0, code, out + err)
        self.assertTrue(any("mask_preview(選用)" in w for w in manifest["technical_validation"]["warnings"]))

    def test_output_dir_must_be_new_and_usage_errors_exit_2(self):
        template, server = self.track_mask()
        busy = Path(self.tmp) / "busy"
        busy.mkdir()
        (busy / "x").write_text("x")
        config = self.write_config(server.url)
        base = ["video/sam3/track-mask", "--config", str(config), "--set", f"source_video={self.clip}",
                "--set", f"seed_mask={self.mask}"]
        self.assertEqual(2, self.run_cli(*base, "--output-dir", str(busy))[0])
        self.assertEqual(2, self.run_cli(*base, "--output-dir", str(busy / "n"), "--timeout", "0")[0])
        self.assertEqual(2, self.run_cli(*base, "--preflight", "--timeout", "5")[0])
        self.assertEqual(2, self.run_cli(*base, "--output-dir", str(busy / "m"), "--run-id", "../x")[0])
        self.assertEqual([], self.posted(server))


class AssetReviewTests(RunFixture, unittest.TestCase):
    def test_list_and_decide_on_template_run(self):
        template, server = self.track_mask()
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(0, code)
        rows = asset_review.collect(str(self.out_dir))
        self.assertEqual(8, len(rows))
        self.assertTrue(all(r["technical"] == "pass" and r["decision"] == "pending" for r in rows))
        # 輸出檔在 outputs/masks/ 底下,manifest 在上兩層也找得到
        output = manifest["outputs"][0]["path"]
        self.assertEqual([str(self.out_dir / R.RESULT_FILE)], asset_review._find_manifests(output))
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(0, asset_review.main(["accept", output, "--by", "yuxiu"]))
        rows = {r["output_path"]: r for r in asset_review.collect(str(self.out_dir))}
        self.assertEqual("accepted", rows[output]["decision"])

    def test_failed_run_cannot_be_accepted(self):
        template, server = self.track_mask(count=7)
        code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(1, code)
        output = manifest["outputs"][0]["path"]
        with self.assertRaises(SystemExit) as ctx:
            asset_review.main(["accept", output, "--by", "yuxiu"])
        self.assertIn("status=failed", str(ctx.exception))
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(0, asset_review.main(["reject", output, "--by", "yuxiu"]))


class StepLogicTests(unittest.TestCase):
    def test_resolve_param(self):
        pre = {"source_video": {"frames": 56, "width": 1024}}
        self.assertEqual(56, S.resolve_param("{pre.source_video.frames}", {}, {}, pre))
        self.assertEqual(17, S.resolve_param("{frames}", {"frames": 17}, {}, pre))
        self.assertTrue(S.resolve_param("{keep_audio}", {}, {"keep_audio": True}, pre))
        self.assertEqual(["first"], S.resolve_param(["first"], {}, {}, pre))
        with self.assertRaises(KeyError):
            S.resolve_param("{pre.source_video.fps}", {}, {}, pre)

    def test_video_input_checks(self):
        media = FakeMedia(video={"fps": "30/1", "fps_value": 30.0, "pts_uniform": False, "frames": 10})
        _, problems, _ = S._check_video_input("check_video", "a.mp4",
                                              {"fps": 16, "cfr": True, "frames_min": 17, "frames_max": 33}, media)
        self.assertEqual(3, len(problems), problems)

    def test_keep_audio_without_source_audio_is_warning(self):
        class Tpl:
            data = {"post": [{"step": "check_video_output", "output": "video", "audio": "{keep_audio}"}]}
        media = FakeMedia(video={"has_audio": False})
        checks, problems, warnings, _ = S.run_post_checks(
            Tpl, {"slot_values": {}, "options": {"keep_audio": True}, "inputs": {}},
            {"source_video": {"has_audio": False}}, {"video": ["out.mp4"]}, "/tmp/x", media)
        self.assertEqual([], problems)
        self.assertTrue(any("沒有音軌" in w for w in warnings))

    def test_execution_seconds_and_default_dir(self):
        self.assertIsNone(R.execution_seconds({"status": {"messages": []}}))
        import datetime
        path = R.default_output_dir("/repo", "video/sam3/track-mask", "0123456789abcdef", datetime.date(2026, 10, 8))
        self.assertEqual(os.path.join("/repo", "output", "runs", "20261008-video-sam3-track-mask-01234567"), path)


def _has_media_deps():
    try:
        optional_deps.require("av", "PIL", "numpy")
    except unittest.SkipTest:
        return False
    return True


@unittest.skipUnless(_has_media_deps(), "需要 PyAV、Pillow 與 numpy")
class RealMediaTests(RunFixture, unittest.TestCase):
    """用真的小影片與 PNG 走一次 media.py(ComfyUI 的 Python 環境都有 PyAV／Pillow)。"""

    def make_video(self, path, frames, size=(64, 48), fps=16):
        import av
        from PIL import Image
        container = av.open(str(path), "w")
        stream = container.add_stream("mpeg4", rate=fps)
        stream.width, stream.height, stream.pix_fmt = size[0], size[1], "yuv420p"
        for i in range(frames):
            image = Image.new("RGB", size, (i * 20 % 255, 80, 160))
            for packet in stream.encode(av.VideoFrame.from_image(image)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
        container.close()

    def png_bytes(self, size, color, mode="L"):
        from PIL import Image
        buffer = io.BytesIO()
        Image.new(mode, size, color).save(buffer, format="PNG")
        return buffer.getvalue()

    def test_media_probe(self):
        from comfyui_pipeline.runner import media
        self.make_video(self.clip, 8)
        info = media.probe_video(self.clip)
        self.assertEqual((64, 48, 8, "16/1", True, False),
                         (info["width"], info["height"], info["frames"], info["fps"], info["pts_uniform"],
                          info["has_audio"]))
        frames = media.extract_keyframes(self.clip, ["first", "middle", "last"], os.path.join(self.tmp, "kf"))
        self.assertEqual(7, frames["last"]["frame_index"])
        self.assertTrue(os.path.isfile(frames["middle"]["path"]))
        Path(self.mask).write_bytes(self.png_bytes((64, 48), (255, 0, 0, 255), "RGBA"))
        stats = media.mask_stats(self.mask)
        self.assertEqual((64, 48, 64 * 48, True), (stats["width"], stats["height"], stats["nonzero"],
                                                  stats["has_transparency"]))
        rgb = Path(self.tmp) / "rgb.png"
        rgb.write_bytes(self.png_bytes((4, 4), (10, 20, 30), "RGB"))
        self.assertFalse(media.png_frame_stats(rgb)["grayscale"])
        with self.assertRaises(ValueError):
            media.probe_video(Path(self.tmp) / "ref.png")

    def test_track_mask_with_real_media(self):
        from comfyui_pipeline.runner import media
        self.make_video(self.clip, 8)
        Path(self.mask).write_bytes(self.png_bytes((64, 48), (255, 0, 0), "RGB"))
        template = self.install("video/sam3/track-mask")
        server = self.fake(template)
        files = {f"run_{i:05d}_.png": self.png_bytes((64, 48), 255 if i % 2 else 0) for i in range(1, 9)}
        server.files = files
        server.history = [history_success({"36": {"images": [{"filename": n, "subfolder": "", "type": "output"}
                                                             for n in files]}})]
        with mock.patch.object(R, "_media", media):
            code, out, err, manifest = self.run_template("video/sam3/track-mask", server)
        self.assertEqual(0, code, out + err)
        self.assertEqual(8, len(manifest["outputs"]))
        self.assertTrue(all(o["grayscale"] for o in manifest["outputs"]))
        self.assertTrue(os.path.isfile(manifest["mask_preview"] or ""), manifest["technical_validation"]["warnings"])

    def test_wan_move_with_real_video_output(self):
        from comfyui_pipeline.runner import media
        self.make_video(self.clip, 20, size=(64, 64))
        Path(self.ref).write_bytes(self.png_bytes((32, 32), (1, 2, 3), "RGB"))
        produced = Path(self.tmp) / "produced.mp4"
        self.make_video(produced, 17, size=(384, 384))
        template = self.install("video/wan-animate/move")
        server = self.fake(template)
        server.files = {"move_00001_.mp4": produced.read_bytes()}
        server.history = [history_success({"19": {"images": [{"filename": "move_00001_.mp4", "subfolder": "",
                                                              "type": "output"}], "animated": [True]}})]
        with mock.patch.object(R, "_media", media):
            code, out, err, manifest = self.run_template("video/wan-animate/move", server,
                                                "--set", f"reference_image={self.ref}",
                                                "--set", f"source_video={self.clip}", "--set", "prompt=hero",
                                                "--set", "seed=1")
        self.assertEqual(0, code, out + err)
        video = manifest["outputs"][0]
        self.assertEqual((384, 384, 17, "16/1", True), (video["width"], video["height"], video["frames"],
                                                       video["fps"], video["pts_uniform"]))
        self.assertTrue(os.path.isfile(manifest["keyframes"]["last"]))


class ClientOptionalParamsTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeComfyRun({})
        self.addCleanup(self.server.close)
        self.tmp = Path(os.environ.get("TMPDIR", "/tmp")) / ("gameart-" + os.urandom(4).hex())
        self.tmp.mkdir()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.file = self.tmp / "a.png"
        self.file.write_bytes(b"img")

    def test_upload_defaults_unchanged(self):
        name = client.upload_image(str(self.file), self.server.url)
        self.assertEqual("a.png", name)
        self.assertEqual({}, self.server.uploads[0]["fields"])

    def test_upload_with_subfolder_returns_response(self):
        response = client.upload_image(str(self.file), self.server.url, subfolder="run1", overwrite=False,
                                       return_response=True)
        self.assertEqual({"name": "a.png", "subfolder": "run1", "type": "input"}, response)
        self.assertEqual({"subfolder": "run1", "overwrite": "false"}, self.server.uploads[0]["fields"])

    def test_submit_defaults_unchanged(self):
        self.server.history = [history_success({})]
        entry = client.submit_and_wait({"1": {}}, timeout=5, comfy_url=self.server.url, poll_interval=0.01)
        self.assertEqual(PROMPT_ID, entry["_prompt_id"])
        self.assertNotIn("client_id", self.server.prompts[0])

    def test_submit_client_id_and_on_queued(self):
        self.server.history = [history_success({})]
        seen = []
        client.submit_and_wait({"1": {}}, timeout=5, comfy_url=self.server.url, poll_interval=0.01,
                               client_id="cid", require_success=True, on_queued=lambda pid, resp: seen.append(pid))
        self.assertEqual("cid", self.server.prompts[0]["client_id"])
        self.assertEqual([PROMPT_ID], seen)

    def test_require_success(self):
        self.server.history = [{"outputs": {}, "status": {"completed": True}}]
        entry = client.submit_and_wait({"1": {}}, timeout=5, comfy_url=self.server.url, poll_interval=0.01)
        self.assertEqual("completed", entry["_queue_status"])
        with self.assertRaises(client.PromptExecutionError):
            client.submit_and_wait({"1": {}}, timeout=5, comfy_url=self.server.url, poll_interval=0.01,
                                   require_success=True)

    def test_execution_error_is_still_runtime_error(self):
        entry = {"outputs": {}, "status": {"status_str": "error", "completed": False}}
        self.server.history = [entry]
        with self.assertRaises(RuntimeError) as ctx:
            client.submit_and_wait({"1": {}}, timeout=5, comfy_url=self.server.url, poll_interval=0.01)
        self.assertIsInstance(ctx.exception, client.PromptExecutionError)
        self.assertEqual(PROMPT_ID, ctx.exception.prompt_id)
        self.assertEqual(entry, ctx.exception.history_entry)
        self.assertIn("生成失敗", str(ctx.exception))


class ManifestWriteTests(unittest.TestCase):
    def test_falls_back_when_hard_links_are_unsupported(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.result.json")
            with mock.patch.object(IR.os, "link", side_effect=PermissionError("exFAT")):
                IR.write_manifest_atomic(path, {"a": 1})
                self.assertEqual({"a": 1}, json.loads(Path(path).read_text(encoding="utf-8")))
                with self.assertRaises(FileExistsError):
                    IR.write_manifest_atomic(path, {"a": 2})
                with mock.patch.object(IR, "validate_manifest_path", side_effect=lambda p: p):
                    with self.assertRaises(FileExistsError):
                        IR.write_manifest_atomic(path, {"a": 3})
            self.assertEqual({"a": 1}, json.loads(Path(path).read_text(encoding="utf-8")))
            self.assertEqual(["x.result.json"], os.listdir(tmp))


if __name__ == "__main__":
    unittest.main()
