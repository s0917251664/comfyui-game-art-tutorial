"""PR 3.5：generate.py video_inpaint 的 graph 改由 runner 填 VACE template。

CLI 旗標與 prepare()/finalize 的契約不變。指定 seed、固定上傳檔名時，送出的 graph
和 build_video_inpaint_wan 逐欄位相同。PR 8.3 刪掉 builder 後，改和刪除前凍結的 builder 輸出比對
（tests/fixtures/vace_builder_frozen.json），只替換 slot 會寫入的欄位。
"""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import optional_deps

optional_deps.require("PIL", "numpy", "av")

import numpy as np
from PIL import Image

from comfyui_pipeline.context import RunContext
from comfyui_pipeline.runner import template as T
from comfyui_pipeline.tasks import video_edit
from comfyui_pipeline.video_catalog import VACE_NEGATIVE_DEFAULT
from comfyui_pipeline.video_contract import video_filename_prefix
from test_video_inpaint import synthetic, write_clip

FROZEN = Path(__file__).resolve().parent / "fixtures" / "vace_builder_frozen.json"


def build_video_inpaint_wan(prompt, control, mask, width, height, length, seed, strength, filename_prefix,
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
    return graph, frozen["output_node"]


class VideoInpaintRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        frames, masks = synthetic()
        self.video = self.root / "src.mp4"
        write_clip(self.video, frames)
        self.masks = self.root / "masks"
        self.masks.mkdir()
        for i, mask in enumerate(masks):
            Image.fromarray(mask).save(self.masks / f"{i:05d}.png")

    def args(self, **kw):
        base = dict(task="video_inpaint", backend="wan", video=str(self.video), masks=str(self.masks),
                    mask_object=1, prompt="glowing hammer", mode="keep", grow=2, feather=2, pad=4, crop=None,
                    strength=1.0, negative=None, seed=11, shot_id=None, name="t", resume=False,
                    output_dir=str(self.root / "out"))
        base.update(kw)
        return SimpleNamespace(**base)

    def test_prepare_graph_matches_builder_for_the_same_seed(self):
        names = []

        def upload(path):
            names.append(os.path.basename(path))
            return f"fixed/{os.path.basename(path)}"

        plan = video_edit.prepare(RunContext(device={"tier": "sdxl"}), self.args(), upload)
        self.assertEqual("58", plan.out_id)
        self.assertEqual(2, len(names))
        prefix = video_filename_prefix("video_inpaint", None, "t")
        built, out_id = build_video_inpaint_wan(
            "glowing hammer", names and f"fixed/{names[0]}", f"fixed/{names[1]}",
            plan.graph["55"]["inputs"]["width"], plan.graph["55"]["inputs"]["height"],
            plan.graph["55"]["inputs"]["length"], seed=11, strength=1.0, filename_prefix=prefix)
        self.assertEqual("58", out_id)
        self.assertEqual(T.canonical_sha256(built), T.canonical_sha256(plan.graph))
        for node_id, node in built.items():
            self.assertEqual(node, plan.graph[node_id], node_id)

    def test_negative_and_replace_mode_stay_in_the_graph(self):
        def upload(path):
            return f"up/{os.path.basename(path)}"

        args = self.args(mode="replace", negative="blurry", strength=0.4, seed=3, name=None, shot_id="A01")
        plan = video_edit.prepare(RunContext(device={}), args, upload)
        prefix = video_filename_prefix("video_inpaint", "A01", None)
        self.assertEqual(prefix, plan.graph["58"]["inputs"]["filename_prefix"])
        self.assertEqual("blurry", plan.graph["7"]["inputs"]["text"])
        self.assertEqual(0.4, plan.graph["55"]["inputs"]["strength"])
        self.assertEqual(3, plan.graph["3"]["inputs"]["seed"])


if __name__ == "__main__":
    unittest.main()
