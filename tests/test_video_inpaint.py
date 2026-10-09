import optional_deps

optional_deps.require("PIL", "numpy", "av")

import io
import json
import os
import tempfile
import unittest
import zipfile
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import av
import numpy as np
from PIL import Image

from comfyui_pipeline import tasks, video_edit_media as media
from comfyui_pipeline.context import RunContext
from comfyui_pipeline.tasks import video_edit
from comfyui_pipeline.runner import template as runner_template

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_video_inpaint_wan(prompt, control, mask, width, height, length, seed):
    """PR 8.3 刪掉 builder 後,改用 video/wan-vace/inpaint template 組同一份 graph(等價見 test_template_wan_vace)。"""
    template = runner_template.load_template(REPO_ROOT / "templates", "video/wan-vace/inpaint", repo_root=REPO_ROOT)
    resolution = runner_template.resolve(
        template, {"source_video": "s.mp4", "masks": "m", "prompt": prompt, "seed": seed}, run_id="test")
    runner_template.fill_from_pre(template, resolution, {"vace_work_area": {
        "width": width, "height": height, "length": length, "frames": length}})
    graph, _ = runner_template.patch(template, resolution, {"control_video": control, "mask_video": mask})
    return graph, template.data["outputs"][0]["node"]
from comfyui_pipeline.video_catalog import VACE_MAX_PIXELS, VIDEO_BACKEND_SPECS, VIDEO_TASK_CAPS


def write_clip(path, frames, fps=24):
    h, w = frames[0].shape[:2]
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264rgb", rate=Fraction(fps))
        s.width, s.height, s.pix_fmt = w, h, "rgb24"
        s.options = {"crf": "0"}
        for f in frames:
            for p in s.encode(av.VideoFrame.from_ndarray(f, format="rgb24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)


def synthetic(n=9, w=96, h=64):
    rng = np.random.default_rng(3)
    frames = [rng.integers(0, 256, (h, w, 3), dtype=np.uint8) for _ in range(n)]
    masks = []
    for i in range(n):
        m = np.zeros((h, w), np.uint8)
        m[20:36, 30 + i:46 + i] = 255
        masks.append(m)
    return frames, masks


class CatalogAndGraphTests(unittest.TestCase):
    def test_capability_wiring(self):
        self.assertEqual("masked_edit", VIDEO_TASK_CAPS["video_inpaint"])
        wan = VIDEO_BACKEND_SPECS["wan"]
        self.assertIn("masked_edit", wan["capabilities"])
        self.assertEqual(("vace_unet", "clip", "vace_vae"), wan["required_models"]["masked_edit"])
        self.assertNotIn("masked_edit", VIDEO_BACKEND_SPECS["h3"]["capabilities"])
        self.assertIn("video_inpaint", tasks.VIDEO_TASKS)

    def test_graph_matches_official_template_settings(self):
        g, out = build_video_inpaint_wan("p", "c.mkv", "m.mkv", 320, 240, 13, seed=7)
        self.assertEqual("58", out)
        self.assertEqual("wan2.1_vace_1.3B_fp16.safetensors", g["37"]["inputs"]["unet_name"])
        self.assertEqual("wan_2.1_vae.safetensors", g["39"]["inputs"]["vae_name"])
        self.assertEqual(5.0, g["48"]["inputs"]["shift"])
        k = g["3"]["inputs"]
        self.assertEqual((20, 6.0, "uni_pc", "simple", 7), (k["steps"], k["cfg"], k["sampler_name"], k["scheduler"], k["seed"]))
        vace = g["55"]["inputs"]
        self.assertEqual((320, 240, 13), (vace["width"], vace["height"], vace["length"]))
        self.assertEqual(["84", 0], vace["control_masks"])
        self.assertEqual(["55", 3], g["56"]["inputs"]["trim_amount"])
        self.assertEqual("red", g["84"]["inputs"]["channel"])
        self.assertTrue(g["7"]["inputs"]["text"].startswith("过曝"))


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_lengths_sizes_and_crop(self):
        self.assertEqual([5, 9, 57, 81], [media.vace_length(n) for n in (5, 9, 56, 81)])
        w, h = media.processing_size(1024, 1024)
        self.assertLessEqual(w * h, VACE_MAX_PIXELS)
        self.assertEqual((0, 0), (w % 16, h % 16))
        self.assertEqual((576, 576), media.processing_size(576, 576))
        frames, masks = synthetic(w=400, h=300)
        grown = media.grow_masks(masks, 4)
        crop = media.compute_crop(grown, (400, 300), pad=8)
        x0, y0, x1, y1 = crop
        self.assertEqual((0, 0), ((x1 - x0) % 16, (y1 - y0) % 16))
        self.assertGreaterEqual(x1 - x0, media.MIN_SIDE)
        with self.assertRaises(ValueError):
            media.compute_crop(grown, (400, 300), explicit=(300, 150, 400, 300))

    def test_read_masks_contract(self):
        frames, masks = synthetic()
        d = self.root / "masks"
        d.mkdir()
        for i, m in enumerate(masks):
            Image.fromarray(m).save(d / f"{i:05d}.png")
        got = media.read_masks(d, len(frames), (96, 64))
        np.testing.assert_array_equal(got[3], masks[3])
        with self.assertRaises(ValueError):
            media.read_masks(d, len(frames) + 1, (96, 64))
        rgba = self.root / "rgba"
        rgba.mkdir()
        for i in range(len(masks)):
            Image.new("RGBA", (96, 64)).save(rgba / f"{i:05d}.png")
        with self.assertRaisesRegex(ValueError, "L"):
            media.read_masks(rgba, len(frames), (96, 64))
        gray = self.root / "gray_rgb"
        gray.mkdir()
        for i, m in enumerate(masks):
            Image.fromarray(np.dstack([m, m, m])).save(gray / f"{i:05d}.png")
        np.testing.assert_array_equal(media.read_masks(gray, len(frames), (96, 64))[3], masks[3])
        colour = self.root / "colour"
        colour.mkdir()
        for i, m in enumerate(masks):
            Image.fromarray(np.dstack([m, np.zeros_like(m), m])).save(colour / f"{i:05d}.png")
        with self.assertRaises(ValueError):
            media.read_masks(colour, len(frames), (96, 64))
        z = self.root / "layers.zip"
        with zipfile.ZipFile(z, "w") as archive:
            for i, m in enumerate(masks):
                buf = io.BytesIO()
                Image.fromarray(m).save(buf, format="PNG")
                archive.writestr(f"masks/object-002/{i:06d}.png", buf.getvalue())
        self.assertEqual(len(masks), len(media.read_masks(z, len(frames), (96, 64), object_id=2)))
        with self.assertRaises(ValueError):
            media.read_masks(z, len(frames), (96, 64), object_id=1)

    def test_lossless_clip_round_trip(self):
        frames, _ = synthetic()
        path = media.write_lossless_video(frames, self.root / "c.mkv")
        back, fps = media.read_video_frames(path)
        self.assertEqual(24.0, fps)
        for a, b in zip(frames, back):
            np.testing.assert_array_equal(a, b)

    def test_replace_mode_blacks_masked_area_and_paste_back_is_exact_outside(self):
        frames, masks = synthetic()
        grown = media.grow_masks(masks, 2)
        crop = (0, 0, 96, 64)
        keep, _ = media.build_work_clips(frames, grown, crop, (96, 64), "keep")
        rep, mclip = media.build_work_clips(frames, grown, crop, (96, 64), "replace")
        np.testing.assert_array_equal(keep[0], frames[0])
        self.assertEqual(0, int(rep[0][grown[0] > 0].max()))
        self.assertEqual(255, int(mclip[0][grown[0] > 0].min()))
        raw = [np.zeros_like(f) for f in frames] + [np.zeros_like(frames[0])]
        out, report = media.paste_back(frames, raw, crop, grown, feather=2)
        for f, o, g in zip(frames, out, grown):
            far = np.ones(g.shape, bool)
            ys, xs = np.nonzero(g)
            far[max(0, ys.min() - 4):ys.max() + 5, max(0, xs.min() - 4):xs.max() + 5] = False
            np.testing.assert_array_equal(o[far], f[far])
            self.assertLessEqual(int(o[g > 0].max()), 5)
        self.assertTrue(all(r["outside_changed_pixels"] == 0 for r in report))
        with self.assertRaises(ValueError):
            media.paste_back(frames, raw[:3], crop, grown)

    def test_validate_source_limits(self):
        frames, _ = synthetic(n=4)
        with self.assertRaises(ValueError):
            media.validate_source(frames, 24.0)
        frames, _ = synthetic(n=9)
        with self.assertRaises(ValueError):
            media.validate_source(frames, 30.0)
        media.validate_source(frames, 24.0)


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.frames, masks = synthetic()
        self.video = self.root / "src.mp4"
        write_clip(self.video, self.frames)
        self.masks = self.root / "masks"
        self.masks.mkdir()
        for i, m in enumerate(masks):
            Image.fromarray(m).save(self.masks / f"{i:05d}.png")

    def args(self, **kw):
        base = dict(task="video_inpaint", backend="wan", video=str(self.video), masks=str(self.masks),
                    mask_object=1, prompt="p", mode="keep", grow=2, feather=2, pad=4, crop=None,
                    strength=1.0, negative=None, seed=11, shot_id=None, name="t", resume=False,
                    output_dir=str(self.root / "out"))
        base.update(kw)
        return SimpleNamespace(**base)

    def test_validate_rejects_bad_values(self):
        video_edit.validate(self.args())
        for kw in ({"grow": 99}, {"strength": 0}, {"crop": "1,2,3"}, {"mask_object": 0}):
            with self.assertRaises(ValueError):
                video_edit.validate(self.args(**kw))

    def test_h3_backend_is_rejected(self):
        # PR 8.3b:video_inpaint 整個交給 runner(完整流程見 test_video_inpaint_runner);backend 檢查仍在最前面
        with self.assertRaises(SystemExit):
            video_edit.run_with_runner(RunContext(device={}), self.args(backend="h3"), "http://127.0.0.1:1",
                                       runner_main=lambda *a, **k: 0)


class RegionToolTests(unittest.TestCase):
    def setUp(self):
        from tools_src import vfx_alpha_tools
        self.tool = vfx_alpha_tools
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.frames, self.masks = synthetic(w=300, h=200)
        self.video = self.root / "src.mp4"
        write_clip(self.video, self.frames)

    def test_working_size_and_editor_mask(self):
        self.assertEqual((300, 200), self.tool.working_size(300, 200))
        self.assertEqual((1280, 720), self.tool.working_size(1920, 1080))
        with self.assertRaises(ValueError):
            self.tool.working_size(200, 100)
        editor = Image.new("RGBA", (600, 400), (0, 0, 0, 255))
        editor.paste((255, 255, 255, 255), (100, 100, 200, 200))
        m = np.asarray(self.tool.editor_mask_to_l(editor, (300, 200)))
        self.assertEqual({0, 255}, set(np.unique(m)))
        self.assertEqual(255, m[75, 75])
        self.assertEqual(0, m[10, 10])

    def test_keyframes_segment_plan_unpack_and_preview(self):
        t = self.tool
        self.assertEqual(0, t.main(["keyframes", "--video", str(self.video), "--frames", "0,4",
                                    "--output-dir", str(self.root / "kf")]))
        self.assertTrue((self.root / "kf" / "frame_00004.png").is_file())
        painted = self.root / "painted.png"
        Image.fromarray(self.masks[0]).convert("RGBA").save(painted)
        self.assertEqual(1, t.main(["segment-plan", "--video", str(self.video), "--mask", f"3={painted}",
                                    "--output-dir", str(self.root / "bad")]))
        self.assertEqual(0, t.main(["segment-plan", "--video", str(self.video), "--mask", f"0={painted}",
                                    "--mask", f"4={painted}", "--output-dir", str(self.root / "plan")]))
        plan = json.loads((self.root / "plan" / "segment_plan.json").read_text(encoding="utf-8"))
        self.assertEqual("segment", plan["operation"])
        self.assertEqual([0, 4], [p["frame"] for p in plan["objects"][0]["prompts"]])
        self.assertEqual(300, plan["width"])
        self.assertLessEqual(plan["end"], 9 / 24)
        with Image.open(plan["objects"][0]["prompts"][0]["mask"]) as im:
            self.assertEqual(("L", (300, 200)), (im.mode, im.size))
        seg = self.root / "seg"
        seg.mkdir()
        with zipfile.ZipFile(seg / "layers.zip", "w") as archive:
            for i, m in enumerate(self.masks):
                buf = io.BytesIO()
                Image.fromarray(m).resize((150, 100), Image.Resampling.NEAREST).save(buf, format="PNG")
                archive.writestr(f"masks/object-001/{i:06d}.png", buf.getvalue())
        self.assertEqual(0, t.main(["unpack-masks", "--segment-dir", str(seg), "--video", str(self.video),
                                    "--output-dir", str(self.root / "masks")]))
        with Image.open(self.root / "masks" / "00000.png") as im:
            self.assertEqual((300, 200), im.size)
        self.assertEqual(0, t.main(["mask-preview", "--video", str(self.video), "--masks", str(self.root / "masks"),
                                    "--output", str(self.root / "preview.png")]))
        self.assertTrue((self.root / "preview.png").is_file())


if __name__ == "__main__":
    unittest.main()
