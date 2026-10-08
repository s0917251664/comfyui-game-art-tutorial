"""PR 3.3:runner 的 pre 產生上傳檔(generated)、pre 結果填進 graph(from_pre),以及 VACE 前後處理步驟
(vace_work_area、paste_back、qa_outside_mask_unchanged)。

用一份精簡的 VACE 測試 template(暫存資料夾,不是正式 template):
- 驗證規則的正反案例;
- 用假 ComfyUI＋假 media 跑完整流程(上傳的是 pre 產生的檔案,graph 的寬高與長度來自 pre 結果);
- RealVaceMediaTests 用真的小影片確認新步驟和 ``generate.py video_inpaint`` 的舊路徑逐 byte 相同。
"""

import hashlib
import json
import os

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_template_preflight import object_info_for  # noqa: E402
from test_template_run import FakeComfyRun, FakeMedia, RunFixture, history_success  # noqa: E402

from comfyui_pipeline.runner import run as R  # noqa: E402
from comfyui_pipeline.runner import steps as S  # noqa: E402
from comfyui_pipeline.runner import template as T  # noqa: E402

TEMPLATE_ID = "video/test/vace-steps"
RUN_ID = "abc123def"

GRAPH = {
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "__PROMPT__", "clip": ["38", 0]}},
    "38": {"class_type": "CLIPLoader", "inputs": {"clip_name": "clip.safetensors", "type": "wan", "device": "default"}},
    "80": {"class_type": "LoadVideo", "inputs": {"file": "__CONTROL_VIDEO__"}},
    "82": {"class_type": "LoadVideo", "inputs": {"file": "__MASK_VIDEO__"}},
    "55": {"class_type": "WanVaceToVideo", "inputs": {
        "positive": ["6", 0], "width": "__WORK_WIDTH__", "height": "__WORK_HEIGHT__", "length": "__VACE_LENGTH__",
        "control_video": ["80", 0], "control_masks": ["82", 0]}},
    "58": {"class_type": "SaveVideo", "inputs": {"video": ["55", 0], "filename_prefix": "__OUTPUT_PREFIX__"}},
}


def _have(*names):
    try:
        for name in names:
            __import__(name)
    except Exception:  # noqa: BLE001 - 缺套件或載入失敗都 skip
        return False
    return True


def target(node, field, placeholder):
    return [{"node": node, "input": field, "placeholder": placeholder}]


def template_data(graph_sha, canonical):
    return {
        "schema_version": 1, "id": TEMPLATE_ID, "version": "0.1.0", "title": "VACE 步驟測試",
        "summary": "PR 3.3 測試用", "status": "draft", "status_note": "測試用",
        "min_comfyui_version": "0.34.0", "requires_custom_nodes": [],
        "graph": {"file": "graph.api.json", "format": "comfyui-api", "sha256": graph_sha, "canonical_sha256": canonical},
        "provenance": {"derived_from": "測試", "upstream": {"kind": "none", "name": None, "blob": None,
                                                           "comfyui_version": None, "note": "測試用"},
                       "tested_source_sha256": None, "evidence": [{"path": "templates/README.md", "note": "x"}]},
        "slots": {
            "source_video": {"type": "video", "targets": [], "required": True, "help": "來源影片(24 FPS)"},
            "masks": {"type": "path", "targets": [], "required": True, "help": "遮罩 PNG 資料夾或 layers.zip"},
            "grow": {"type": "int", "targets": [], "default": 8, "validate": {"min": 0, "max": 64}},
            "feather": {"type": "int", "targets": [], "default": 4, "validate": {"min": 0, "max": 32}},
            "mode": {"type": "string", "targets": [], "default": "keep", "validate": {"enum": ["keep", "replace"]}},
            "crop": {"type": "string", "targets": [], "default": ""},
            "control_video": {"type": "video", "upload": True, "generated": True,
                              "targets": target("80", "file", "__CONTROL_VIDEO__")},
            "mask_video": {"type": "video", "upload": True, "generated": True,
                           "targets": target("82", "file", "__MASK_VIDEO__")},
            "work_width": {"type": "int", "from_pre": "{pre.vace_work_area.width}",
                           "targets": target("55", "width", "__WORK_WIDTH__")},
            "work_height": {"type": "int", "from_pre": "{pre.vace_work_area.height}",
                            "targets": target("55", "height", "__WORK_HEIGHT__")},
            "vace_length": {"type": "int", "from_pre": "{pre.vace_work_area.length}",
                            "targets": target("55", "length", "__VACE_LENGTH__")},
            "prompt": {"type": "text", "required": True, "targets": target("6", "text", "__PROMPT__")},
            "output_prefix": {"type": "output_prefix", "targets": target("58", "filename_prefix", "__OUTPUT_PREFIX__")},
        },
        "pre": [
            {"step": "vace_work_area", "video": "source_video", "masks": "masks", "grow": "{grow}", "mode": "{mode}",
             "crop": "{crop}", "control": "control_video", "mask": "mask_video"},
            {"step": "upload", "slots": ["control_video", "mask_video"]},
        ],
        "post": [
            {"step": "check_video_output", "output": "raw", "width": "{pre.vace_work_area.width}",
             "height": "{pre.vace_work_area.height}", "frames": "{pre.vace_work_area.length}"},
            {"step": "paste_back", "output": "raw", "feather": "{feather}"},
            {"step": "qa_outside_mask_unchanged"},
        ],
        "frame_anchoring": {"first": "none", "last": "none", "reference_role": "none",
                            "time_alignment": "per_source_frame", "continuity": None},
        "models": [],
        "capability_gate": {"nodes": "from_graph", "selectors": "from_models", "files": "from_models",
                            "platforms": {"windows-cuda": {"status": "technical_pass", "evidence": "測試"}},
                            "min_memory_mb": None, "capability": "masked_edit"},
        "outputs": [{"id": "raw", "node": "58", "kind": "video", "role": "candidate"}],
    }


def write_template(root, change=None):
    folder = Path(root) / TEMPLATE_ID
    folder.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(GRAPH, indent=2).encode("utf-8")
    (folder / "graph.api.json").write_bytes(raw)
    data = template_data(hashlib.sha256(raw).hexdigest(), T.canonical_sha256(GRAPH))
    if change:
        change(data)
    (folder / "template.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return folder


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = Path(self.tmp) / "templates"

    def load(self, change=None):
        shutil.rmtree(self.root, ignore_errors=True)
        write_template(self.root, change)
        return T.load_template(self.root, TEMPLATE_ID, repo_root=Path(__file__).resolve().parents[1])

    def rejected(self, change, fragment):
        with self.assertRaises(T.TemplateError) as ctx:
            self.load(change)
        self.assertIn(fragment, str(ctx.exception))

    def test_valid_template_loads(self):
        template = self.load()
        self.assertEqual(["control_video", "mask_video"], template.upload_slots())
        self.assertEqual(["control_video", "mask_video", "work_width", "work_height", "vace_length"],
                         template.deferred_slots())

    def test_rejections(self):
        def pre(index, **kw):
            return lambda d: d["pre"][index].update(kw)
        cases = [
            (lambda d: d["pre"].insert(0, {"step": "run_python", "code": "x"}), "不在步驟清單內的 'run_python'"),
            (lambda d: d["slots"]["control_video"].pop("generated"), "要寫 \"generated\": true"),
            (lambda d: d["pre"].reverse(), "upload 步驟排在產生它的 pre 步驟之前"),
            (lambda d: d["slots"].update(extra_clip={"type": "video", "upload": True, "generated": True,
                                                     "targets": []}), "targets 必須是非空陣列"),
            (lambda d: d["slots"]["prompt"].update(generated=True), "generated 只能用在 upload 的 slot"),
            (lambda d: d["slots"]["work_width"].update(from_pre="{pre.vace_work_area.crop}"), "from_pre 要寫成"),
            (lambda d: d["slots"]["work_width"].update(from_pre="{pre.source_video.width}"), "from_pre 要寫成"),
            (lambda d: d["slots"]["work_width"].update(default=16), "不能有 default 或 required"),
            (lambda d: d["slots"]["source_video"].update(targets=target("80", "file", "__CONTROL_VIDEO__")),
             "targets 要是 []"),
            (lambda d: d["slots"].update(unused={"type": "int", "targets": [], "default": 1}), "slot unused: 沒有寫進 graph"),
            (pre(0, masks="source_video"), "vace_work_area.masks: slot source_video 必須是 path"),
            (lambda d: d["post"].pop(1), "qa_outside_mask_unchanged 需要在它之前有 post 步驟 paste_back"),
            (lambda d: d["pre"].pop(0) and d["slots"].pop("control_video"), "slot "),
            (lambda d: d["slots"]["masks"].update(upload=True), "upload 只能用在 image／video／mask_image"),
            (lambda d: d["post"][0].update(width="{pre.vace_work_area.size}"), "vace_work_area 的結果只能取"),
        ]
        for change, fragment in cases:
            with self.subTest(fragment):
                self.rejected(change, fragment)

    def test_paste_back_needs_work_area(self):
        def drop(d):
            d["pre"] = [{"step": "upload", "slots": ["control_video", "mask_video"]}]
            for name in ("control_video", "mask_video"):
                d["slots"][name].pop("generated")
            for name in ("work_width", "work_height", "vace_length"):
                d["slots"][name].pop("from_pre")
                d["slots"][name]["required"] = True
        with self.assertRaises(T.TemplateError) as ctx:
            self.load(drop)
        self.assertIn("paste_back 需要在它之前有 pre 步驟 vace_work_area", str(ctx.exception))

    def test_generated_and_from_pre_cannot_be_set(self):
        template = self.load()
        for name in ("control_video", "work_width"):
            with self.subTest(name), self.assertRaises(T.TemplateError) as ctx:
                T.resolve(template, {name: "1", "source_video": "a.mp4", "masks": "m", "prompt": "p"}, run_id=RUN_ID)
            self.assertIn("值由 pre 步驟產生,不能指定", str(ctx.exception))

    def test_dry_run_marks_pending_values(self):
        template = self.load()
        resolution = T.resolve(template, {"source_video": "a.mp4", "masks": "m", "prompt": "p"}, run_id=RUN_ID,
                               dry_run=True)
        self.assertEqual({"source_video": "a.mp4", "masks": "m"}, resolution["inputs"])
        self.assertEqual([], resolution["warnings"])
        graph, changes = T.patch(template, resolution, require_uploads=False)
        self.assertEqual("<upload:control_video>", graph["80"]["inputs"]["file"])
        self.assertEqual("<pre:vace_work_area.width>", graph["55"]["inputs"]["width"])
        self.assertIn("55.length", changes)
        with self.assertRaises(T.TemplateError):  # 實際送出時一定要有值
            T.patch(template, resolution, {"control_video": "x/c.mkv", "mask_video": "x/m.mkv"})

    def test_fill_from_pre(self):
        template = self.load()
        resolution = T.resolve(template, {"source_video": "a.mp4", "masks": "m", "prompt": "p"}, run_id=RUN_ID)
        T.fill_from_pre(template, resolution, {"vace_work_area": {"width": 544, "height": 560, "length": 57}})
        graph, _ = T.patch(template, resolution, {"control_video": "r/control.mkv", "mask_video": "r/mask.mkv"})
        self.assertEqual((544, 560, 57), tuple(graph["55"]["inputs"][k] for k in ("width", "height", "length")))
        with self.assertRaises(T.TemplateError):
            T.fill_from_pre(template, resolution, {})

    def test_parse_crop(self):
        self.assertIsNone(S.parse_crop(""))
        self.assertEqual([1, 2, 3, 4], S.parse_crop("1, 2,3,4"))
        self.assertEqual([1, 2, 3, 4], S.parse_crop([1, 2, 3, 4]))
        with self.assertRaises(ValueError):
            S.parse_crop("1,2,3")


class FakeVaceMedia(FakeMedia):
    """假的 vace_* 函式:寫小檔案,記錄呼叫參數。"""

    def __init__(self, outside_counts=(0, 0), **kwargs):
        super().__init__(output_video={"width": 96, "height": 64, "frames": 9, "fps": 24, "fps_rational": "24/1",
                                       "fps_value": 24.0, "pts_uniform": True, "has_audio": False}, **kwargs)
        self.outside_counts = list(outside_counts)
        self.vace_calls = []

    def vace_work_area(self, video, masks, out_dir, **kwargs):
        self.vace_calls.append(("work_area", video, masks, out_dir, kwargs))
        os.makedirs(out_dir)
        control, mask = os.path.join(out_dir, "control.mkv"), os.path.join(out_dir, "mask.mkv")
        Path(control).write_bytes(b"control clip")
        Path(mask).write_bytes(b"mask clip")
        info = {"frames": 9, "fps": 24.0, "source_width": 200, "source_height": 120, "crop": [0, 0, 192, 128],
                "width": 96, "height": 64, "length": 9, "mode": kwargs["mode"], "grow": kwargs["grow"],
                "pad": kwargs["pad"], "mask_object": kwargs["mask_object"], "control": control, "mask": mask}
        return info, {"state": "work"}

    def vace_composite(self, state, raw_video, out_dir, feather=4):
        self.vace_calls.append(("composite", state, raw_video, out_dir, feather))
        frames = os.path.join(out_dir, "frames")
        os.makedirs(frames)
        paths = []
        for i in range(2):
            paths.append(os.path.join(frames, f"{i:05d}.png"))
            Path(paths[-1]).write_bytes(f"frame {i}".encode())
        mp4 = os.path.join(out_dir, "composited.mp4")
        Path(mp4).write_bytes(b"composited")
        return {"raw_frames": 9, "used_frames": 9, "feather": feather, "frames": paths, "mp4": mp4,
                "outside_changed_pixels_total": 0, "per_frame": []}

    def vace_outside_changes(self, state, frame_paths, feather=4):
        self.vace_calls.append(("qa", state, len(frame_paths), feather))
        return list(self.outside_counts)


class RunTests(RunFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.media = FakeVaceMedia()
        patch = mock.patch.object(R, "_media", self.media)
        patch.start()
        self.addCleanup(patch.stop)
        self.masks = Path(self.tmp) / "masks"
        self.masks.mkdir()
        for i in range(3):
            (self.masks / f"{i:05d}.png").write_bytes(f"mask {i}".encode())
        write_template(self.root)
        self.template = T.load_template(self.root, TEMPLATE_ID, repo_root=Path(__file__).resolve().parents[1])

    def server(self):
        server = FakeComfyRun(object_info_for(self.template))
        self.servers.append(server)
        server.files = {"raw_00001_.mp4": b"raw vace output"}
        server.history = [None, history_success({"58": {"images": [
            {"filename": "raw_00001_.mp4", "subfolder": "gameart/video-test-vace-steps", "type": "output"}]}})]
        return server

    def run_vace(self, server, *extra):
        config = self.write_config(server.url)
        self.out_dir = Path(self.tmp) / "run"
        code, out, err = self.run_cli(TEMPLATE_ID, "--config", str(config), "--output-dir", str(self.out_dir),
                                      "--run-id", RUN_ID, "--set", f"source_video={self.clip}",
                                      "--set", f"masks={self.masks}", "--set", "prompt=a red hammer", *extra)
        path = self.out_dir / R.RESULT_FILE
        return code, out, err, json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def test_end_to_end_uploads_generated_files_and_fills_graph(self):
        server = self.server()
        code, out, err, manifest = self.run_vace(server, "--set", "grow=6", "--set", "crop=0,0,192,128")
        self.assertEqual(0, code, out + err)
        self.assertEqual("completed", manifest["status"])
        # pre 步驟的參數(slot 值與預設值)
        _, video, masks, work_dir, kwargs = self.media.vace_calls[0]
        self.assertEqual((str(self.clip), str(self.masks)), (video, masks))
        self.assertEqual(str(self.out_dir / "work"), work_dir)
        self.assertEqual({"mask_object": 1, "grow": 6, "pad": 48, "crop": [0, 0, 192, 128], "mode": "keep"}, kwargs)
        # 上傳的是 pre 產生的兩個檔案,不是來源影片與遮罩
        self.assertEqual([b"control clip", b"mask clip"], [u["bytes"] for u in server.uploads])
        self.assertEqual(["control.mkv", "mask.mkv"], [u["filename"] for u in server.uploads])
        prompt = server.prompts[0]["prompt"]
        self.assertEqual(f"{RUN_ID}/control.mkv", prompt["80"]["inputs"]["file"])
        self.assertEqual(f"{RUN_ID}/mask.mkv", prompt["82"]["inputs"]["file"])
        self.assertEqual((96, 64, 9), tuple(prompt["55"]["inputs"][k] for k in ("width", "height", "length")))
        self.assertEqual({"work_width": 96, "work_height": 64, "vace_length": 9},
                         {k: manifest["slot_values"][k] for k in ("work_width", "work_height", "vace_length")})
        # 輸入紀錄:來源檔、遮罩資料夾(檔案數與 sha256)、產生的工作片段
        inputs = {row["role"]: row for row in manifest["inputs"]}
        self.assertEqual(("directory", 3), (inputs["masks"]["kind"], inputs["masks"]["files"]))
        self.assertTrue(inputs["control_video"]["generated"])
        self.assertEqual(hashlib.sha256(b"control clip").hexdigest(), inputs["control_video"]["sha256"])
        self.assertEqual(f"{RUN_ID}/control.mkv", inputs["control_video"]["upload"]["graph_value"])
        # post:貼回用 pre 的中間資料;QA 讀貼回的 PNG
        composite = next(c for c in self.media.vace_calls if c[0] == "composite")
        self.assertEqual(({"state": "work"}, str(self.out_dir / "outputs" / "raw" / "raw_00001_.mp4"),
                          str(self.out_dir / "composited"), 4), composite[1:])
        self.assertEqual(("qa", {"state": "work"}, 2, 4), self.media.vace_calls[-1])
        steps = [c["step"] for c in manifest["technical_validation"]["checks"]]
        self.assertEqual(["vace_work_area", "check_video_output", "paste_back", "qa_outside_mask_unchanged"], steps)
        derived = {row["role"]: row for row in manifest["derived_outputs"]}
        self.assertEqual(hashlib.sha256(b"composited").hexdigest(), derived["composited_mp4"]["sha256"])
        self.assertEqual(2, derived["composited_frames"]["files"])
        self.assertEqual("pending", manifest["content_review"])

    def test_outside_mask_change_fails_post(self):
        self.media.outside_counts = [0, 5]
        code, out, err, manifest = self.run_vace(self.server())
        self.assertEqual(1, code)
        self.assertEqual("post", manifest["failure"]["step"])
        self.assertIn("遮罩外有 5 個像素", manifest["failure"]["error"])
        qa = manifest["technical_validation"]["checks"][-1]
        self.assertEqual(([1], "fail"), (qa["detail"]["frames_with_changes"], qa["status"]))

    def test_work_area_failure_uploads_nothing(self):
        def boom(*args, **kwargs):
            raise ValueError("video_inpaint --video 必須接近 24 FPS")
        self.media.vace_work_area = boom
        server = self.server()
        code, out, err, manifest = self.run_vace(server)
        self.assertEqual(1, code)
        self.assertEqual("pre", manifest["failure"]["step"])
        self.assertIn("24 FPS", manifest["failure"]["error"])
        self.assertEqual([], server.uploads)
        self.assertEqual([], server.prompts)

    def test_missing_mask_folder_is_preflight_problem(self):
        shutil.rmtree(self.masks)
        code, out, err, manifest = self.run_vace(self.server())
        self.assertEqual(1, code)
        self.assertIn("slot masks 的檔案不存在", manifest["failure"]["error"])

    def test_dry_run_cli(self):
        code, out, err = self.run_cli(TEMPLATE_ID, "--dry-run", "--set", f"source_video={self.clip}",
                                      "--set", f"masks={self.masks}", "--set", "prompt=p", "--run-id", RUN_ID)
        self.assertEqual(0, code, err)
        graph = json.loads(out)
        self.assertEqual("<pre:vace_work_area.length>", graph["55"]["inputs"]["length"])


@unittest.skipUnless(_have("numpy", "av", "PIL"), "需要 numpy、PyAV、Pillow")
class RealVaceMediaTests(unittest.TestCase):
    """新步驟(runner/vace_media 的 prepare_work_area／composite)和舊路徑(tasks/video_edit)產生相同的結果。"""

    def setUp(self):
        import numpy as np
        from PIL import Image
        from comfyui_pipeline import video_edit_media as old
        self.np, self.old = np, old
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        rng = np.random.default_rng(7)
        self.frames = [rng.integers(0, 255, (120, 200, 3), dtype=np.uint8) for _ in range(9)]
        self.video = old.write_lossless_video(self.frames, self.tmp / "source.mkv", fps=24)
        self.masks = self.tmp / "masks"
        self.masks.mkdir()
        for i in range(9):
            m = np.zeros((120, 200), np.uint8)
            m[40 + i:70 + i, 60:110] = 255
            Image.fromarray(m).save(self.masks / f"{i:05d}.png")

    def decoded(self, path):
        frames, _ = self.old.read_video_frames(path)
        return hashlib.sha256(b"".join(f.tobytes() for f in frames)).hexdigest()

    def test_work_area_and_paste_back_match_old_path(self):
        from comfyui_pipeline.runner import media
        np, old = self.np, self.old
        for mode, crop in (("keep", None), ("replace", [0, 0, 192, 112])):
            with self.subTest(mode=mode):
                work = self.tmp / f"work-{mode}"
                info, state = media.vace_work_area(str(self.video), str(self.masks), work, grow=4, pad=16,
                                                   crop=crop, mode=mode)
                # 舊路徑:tasks/video_edit.prepare 的同一串呼叫
                frames, fps = old.read_video_frames(self.video)
                masks = old.read_masks(str(self.masks), len(frames), (200, 120))
                grown = old.grow_masks(masks, 4)
                old_crop = old.compute_crop(grown, (200, 120), 16, tuple(crop) if crop else None)
                size = old.processing_size(old_crop[2] - old_crop[0], old_crop[3] - old_crop[1])
                controls, mask_clip = old.build_work_clips(frames, grown, old_crop, size, mode)
                self.assertEqual((list(old_crop), size[0], size[1], old.vace_length(9)),
                                 (info["crop"], info["width"], info["height"], info["length"]))
                old_control = old.write_lossless_video(controls, self.tmp / f"old-control-{mode}.mkv")
                old_mask = old.write_lossless_video(mask_clip, self.tmp / f"old-mask-{mode}.mkv")
                self.assertEqual(self.decoded(old_control), self.decoded(info["control"]))
                self.assertEqual(self.decoded(old_mask), self.decoded(info["mask"]))
                # 假的 VACE 輸出:工作區尺寸、length 幀
                raw = [np.full((size[1], size[0], 3), 40 * i % 255, np.uint8) for i in range(info["length"])]
                raw_path = old.write_lossless_video(raw, self.tmp / f"raw-{mode}.mkv")
                result = media.vace_composite(state, raw_path, self.tmp / f"composited-{mode}", feather=2)
                old_frames, _ = old.paste_back(frames, old.read_video_frames(raw_path)[0][:9], old_crop, grown, 2)
                for path, expected in zip(result["frames"], old_frames):
                    from PIL import Image
                    with Image.open(path) as im:
                        np.testing.assert_array_equal(expected, np.asarray(im.convert("RGB")))
                self.assertEqual([0] * 9, media.vace_outside_changes(state, result["frames"], 2))
                # 改掉遮罩外的一個像素,QA 要抓到
                from PIL import Image
                with Image.open(result["frames"][3]) as im:
                    tampered = np.asarray(im.convert("RGB")).copy()
                tampered[0, 0] = 255 - tampered[0, 0]
                Image.fromarray(tampered).save(result["frames"][3])
                self.assertEqual(1, media.vace_outside_changes(state, result["frames"], 2)[3])

    def test_work_area_refuses_non_empty_folder(self):
        from comfyui_pipeline.runner import media
        work = self.tmp / "busy"
        work.mkdir()
        (work / "x").write_bytes(b"x")
        with self.assertRaises(FileExistsError):
            media.vace_work_area(str(self.video), str(self.masks), work)


if __name__ == "__main__":
    unittest.main()
