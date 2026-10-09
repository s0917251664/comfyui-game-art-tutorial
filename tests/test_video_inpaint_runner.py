"""PR 3.5／8.3b:``generate.py video_inpaint`` 整個交給 template runner(``video/wan-vace/inpaint``)。

- CLI 參數對到 template slot 的方式和 3.5 相同;送出的 graph 和刪除前凍結的 builder 輸出逐欄位相同
  (只替換 slot 會寫的欄位;tests/fixtures/vace_builder_frozen.json)。
- ``run_with_runner`` 把值交給 ``gameart.py run``,輸出在 ``<output-dir>/<名稱>_run/``,另寫一份和舊版欄位相同的
  ``composited/result.json``。
- 完整流程:真的 runner＋真的小影片＋假 ComfyUI,從 pre(工作區、上傳)跑到 post(貼回、遮罩外檢查)。
"""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import optional_deps

optional_deps.require("PIL", "numpy", "av")

import numpy as np
from PIL import Image

from comfyui_pipeline.context import RunContext
from comfyui_pipeline.runner import cli as runner_cli
from comfyui_pipeline.runner import run as R
from comfyui_pipeline.runner import template as T
from comfyui_pipeline.runner import vace_media
from comfyui_pipeline.tasks import video_edit
from comfyui_pipeline.video_catalog import VACE_NEGATIVE_DEFAULT
from test_template_preflight import PreflightFixture, object_info_for
from test_template_run import FakeComfyRun, history_success
from test_video_inpaint import synthetic, write_clip

FROZEN = Path(__file__).resolve().parent / "fixtures" / "vace_builder_frozen.json"
REPO = Path(__file__).resolve().parents[1]


def frozen_builder_graph(prompt, control, mask, width, height, length, seed, strength, filename_prefix,
                         negative=None):
    """刪除前凍結的 builder 輸出,換上這次的值。只換 template slot 會寫的欄位,其他欄位必須和 builder 一樣。"""
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))["cases"]["defaults_1024"]
    graph = copy.deepcopy(frozen["graph"])
    graph["6"]["inputs"]["text"] = prompt
    graph["7"]["inputs"]["text"] = negative or VACE_NEGATIVE_DEFAULT
    graph["80"]["inputs"]["file"], graph["82"]["inputs"]["file"] = control, mask
    graph["55"]["inputs"].update(width=width, height=height, length=length, strength=float(strength))
    graph["3"]["inputs"]["seed"] = seed
    graph["58"]["inputs"]["filename_prefix"] = filename_prefix
    return graph


class Media:
    """真的小影片與遮罩(24 FPS、9 幀)。"""

    def make(self, root):
        frames, masks = synthetic()
        video = Path(root) / "src.mp4"
        write_clip(video, frames)
        mask_dir = Path(root) / "masks"
        mask_dir.mkdir()
        for i, mask in enumerate(masks):
            Image.fromarray(mask).save(mask_dir / f"{i:05d}.png")
        return video, mask_dir


def cli_args(video, masks, out_dir, **kw):
    base = dict(task="video_inpaint", backend="wan", video=str(video), masks=str(masks), mask_object=1,
                prompt="glowing hammer", mode="keep", grow=2, feather=2, pad=4, crop=None, strength=1.0,
                negative=None, seed=11, shot_id=None, name="t", resume=False, output_dir=str(out_dir),
                timeout=60.0, config_path=None)
    base.update(kw)
    return SimpleNamespace(**base)


class ArgumentMappingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ctx = RunContext(device={})

    def args(self, **kw):
        return cli_args(self.root / "v.mp4", self.root / "m", self.root / "out", **kw)

    def test_values_and_argv_go_to_the_runner(self):
        seen = {}

        def fake_main(argv, root=None):
            seen["argv"], seen["root"] = argv, root
            seen["values"] = json.loads(Path(argv[argv.index("--values") + 1]).read_text(encoding="utf-8"))
            return 1
        args = self.args(mode="replace", negative="blurry", strength=0.4, crop="0,0,64,64", config_path="cfg.json")
        code = video_edit.run_with_runner(self.ctx, args, "http://127.0.0.1:8188", runner_main=fake_main)
        self.assertEqual(1, code)
        argv = seen["argv"]
        self.assertEqual("video/wan-vace/inpaint", argv[0])
        self.assertEqual(str(self.root / "out" / "t_run"), argv[argv.index("--output-dir") + 1])
        self.assertEqual(self.root / "out" / "t_run", video_edit.run_folder(args))
        self.assertEqual("http://127.0.0.1:8188", argv[argv.index("--comfy-url") + 1])
        self.assertEqual("60.0", argv[argv.index("--timeout") + 1])
        self.assertEqual(os.path.abspath("cfg.json"), argv[argv.index("--config") + 1])
        self.assertEqual({"source_video": os.path.abspath(args.video), "masks": os.path.abspath(args.masks),
                          "prompt": "glowing hammer", "mode": "replace", "grow": 2, "pad": 4, "feather": 2,
                          "mask_object": 1, "strength": 0.4, "crop": "0,0,64,64", "negative": "blurry",
                          "seed": 11}, seen["values"])
        self.assertEqual(REPO / "templates", Path(seen["root"]))
        self.assertFalse(os.path.exists(argv[argv.index("--values") + 1]))  # 暫存的 values 檔會刪掉

    def test_refusals(self):
        with self.assertRaises(SystemExit):
            video_edit.run_with_runner(self.ctx, self.args(resume=True), "u", runner_main=lambda *a, **k: 0)
        folder = video_edit.run_folder(self.args())
        folder.mkdir(parents=True)
        (folder / "x").write_text("x", encoding="utf-8")
        with self.assertRaises(SystemExit):
            video_edit.run_with_runner(self.ctx, self.args(), "u", runner_main=lambda *a, **k: 0)
        with self.assertRaises(SystemExit):
            video_edit.run_with_runner(self.ctx, self.args(backend="h3", name="h"), "u",
                                       runner_main=lambda *a, **k: 0)

    def test_graph_matches_frozen_builder(self):
        """3.5 的等價:同樣的 slot 值、固定上傳檔名,graph 和刪除前的 builder 逐欄位相同。"""
        args = self.args(mode="replace", negative="blurry", strength=0.4, seed=3)
        template = T.load_template(REPO / "templates", "video/wan-vace/inpaint", repo_root=REPO)
        resolution = T.resolve(template, video_edit._slot_values(args), run_id="eq")
        T.fill_from_pre(template, resolution, {"vace_work_area": {"width": 96, "height": 64, "length": 9, "frames": 9}})
        graph, _ = T.patch(template, resolution, {"control_video": "up/c.mkv", "mask_video": "up/m.mkv"})
        expected = frozen_builder_graph("glowing hammer", "up/c.mkv", "up/m.mkv", 96, 64, 9, 3, 0.4,
                                        T.output_prefix("video/wan-vace/inpaint", "eq"), negative="blurry")
        self.assertEqual(T.canonical_sha256(expected), T.canonical_sha256(graph))


class EndToEndTests(PreflightFixture, unittest.TestCase):
    """真的 runner(pre 工作區、上傳、送出、下載、貼回、遮罩外檢查)+ 假 ComfyUI + 真的小影片。"""

    def test_video_inpaint_runs_through_the_runner(self):
        template = self.install("video/wan-vace/inpaint")
        video, masks = Media().make(self.tmp)
        out_dir = Path(self.tmp) / "out"
        args = cli_args(video, masks, out_dir, config_path=str(self.write_config()))
        # 先用同樣的參數算出工作區,才知道假 VACE 輸出要多大
        info, _state = vace_media.prepare_work_area(str(video), str(masks), Path(self.tmp) / "probe",
                                                    grow=2, pad=4, mode="keep")
        raw = Path(self.tmp) / "raw.mp4"
        write_clip(raw, [np.full((info["height"], info["width"], 3), 200, np.uint8)] * info["length"])
        server = FakeComfyRun(object_info_for(template))
        self.servers.append(server)
        args.config_path = str(self.write_config(server.url))
        server.files = {"raw_00001_.mp4": raw.read_bytes()}
        server.history = [None, history_success({"58": {"images": [
            {"filename": "raw_00001_.mp4", "subfolder": "gameart/video-wan-vace-inpaint", "type": "output"}]}})]

        log = io.StringIO()

        def runner_main(argv, root=None):
            return runner_cli.main(argv, root=self.root, out=log, err=log)

        with mock.patch.object(R, "POLL_INTERVAL", 0.01):
            code = video_edit.run_with_runner(RunContext(device={}), args, server.url, runner_main=runner_main)
        folder = video_edit.run_folder(args)
        self.assertTrue((folder / "run.result.json").is_file(), log.getvalue())
        manifest = json.loads((folder / "run.result.json").read_text(encoding="utf-8"))
        self.assertEqual(0, code, manifest.get("failure"))
        # 上傳的是 pre 產生的兩支 FFV1 片段,graph 的寬高與長度來自 pre
        self.assertEqual(["control.mkv", "mask.mkv"], [u["filename"] for u in server.uploads])
        prompt = server.prompts[0]["prompt"]
        self.assertEqual((info["width"], info["height"], info["length"]),
                         tuple(prompt["55"]["inputs"][k] for k in ("width", "height", "length")))
        self.assertEqual(11, prompt["3"]["inputs"]["seed"])
        steps = [c["step"] for c in manifest["technical_validation"]["checks"]]
        self.assertEqual(["check_video", "vace_work_area", "check_video_output", "extract_keyframes",
                          "paste_back", "qa_outside_mask_unchanged"], steps)
        # 和舊版欄位相同的 composited/result.json
        result = json.loads((folder / "composited" / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(("video_inpaint_paste_back", "candidate", 0),
                         (result["kind"], result["status"], result["outside_changed_pixels_total"]))
        self.assertEqual(info["crop"], result["crop"])
        self.assertEqual([info["width"], info["height"]], result["processing_size"])
        self.assertEqual((9, 9, 11), (result["source"]["frames"], len(result["per_frame"]), result["seed"]))
        self.assertEqual(9, len(list((folder / "composited" / "frames").glob("*.png"))))
        self.assertTrue((folder / "composited" / "composited.mp4").is_file())
        self.assertEqual("pending", manifest["content_review"])


if __name__ == "__main__":
    unittest.main()
