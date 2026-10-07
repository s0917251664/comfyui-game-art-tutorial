"""Requirement 2 VACE 1.3B masked video edit experiment (vfx-research-20261007).

Research-only fixed graph mirroring the official ComfyUI template `video_wan_vace_inpainting.json`
(non-turbo branch: ModelSamplingSD3 shift 5, KSampler 20 steps / cfg 6 / uni_pc / simple, GrowMask,
control video blacked inside the mask, TrimVideoLatent). Not a generate.py task.

Mode A "template": control video filled black inside the grown mask (official inpainting wiring).
Mode B "keep":     original pixels kept inside the mask as guidance (reactive stream carries them).
Seeds 101/202/303. Work crop 576x576 at (160,176) of the 1024 source; frames 56 -> length 57
(WanVaceToVideo pads the 57th control frame grey with mask 1; that frame is dropped).

Usage: python run_vace.py prepare | run | analyse
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools_src"))
import vfx_alpha_tools as T  # noqa: E402
from comfyui_pipeline import client  # noqa: E402

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
SOURCE = EXP / "inputs" / "skye_hammer_ready_FINAL_1024.mp4"
MASKS = EXP / "req2" / "masks_hammer"
CROP = (160, 176, 736, 752)
SIZE = 576
GROW = 8
LENGTH = 57
SEEDS = (101, 202, 303)
MODES = ("template", "keep")
URL = "http://127.0.0.1:8188"
UNET = "wan2.1_vace_1.3B_fp16.safetensors"
PROMPT = ("A cute chibi horse girl with light blue bob hair and horse ears lifts a big hammer. The hammer has a "
          "dark navy blue body, ornate gold end frames and glowing magenta purple crystal windows with a bright "
          "magenta purple magic glow and magenta sparkles. Flat pure green chroma key background, static camera, "
          "2D anime game art.")
# Negative prompt copied verbatim from the official template (node 279).
NEGATIVE = ("过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
            "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，"
            "背景人很多，倒着走,过曝，")


def grown(mask):
    return np.asarray(Image.fromarray(((mask > 127) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * GROW + 1)))


def prepare():
    frames, _ = T.read_frames(SOURCE)
    masks = T.read_masks(MASKS, len(frames), (1024, 1024))
    x0, y0, x1, y1 = CROP
    for name in ("control_template", "control_keep", "mask_grown"):
        T.new_directory(HERE / name)
    for i, (f, m) in enumerate(zip(frames, masks)):
        crop = f[y0:y1, x0:x1].copy()
        g = grown(m)[y0:y1, x0:x1]
        Image.fromarray(crop).save(HERE / "control_keep" / f"{i:05d}.png")
        blank = crop.copy()
        blank[g > 0] = 0  # template: ImageCompositeMasked(source=MaskToImage(InvertMask(mask))) -> black
        Image.fromarray(blank).save(HERE / "control_template" / f"{i:05d}.png")
        Image.fromarray(g).save(HERE / "mask_grown" / f"{i:05d}.png")
    full = [grown(m) for m in masks]
    covered = all(int((g[:y0] > 0).sum() + (g[y1:] > 0).sum() + (g[:, :x0] > 0).sum() + (g[:, x1:] > 0).sum()) == 0 for g in full)
    print("prepared", len(frames), "frames; grown mask inside crop:", covered)


def graph(mode, seed):
    folder = str(HERE / f"control_{mode}")
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "4": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 5.0}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": PROMPT}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": NEGATIVE}},
        "7": {"class_type": "LoadImagesFromFolderKJ", "inputs": {"folder": folder, "width": SIZE, "height": SIZE, "keep_aspect_ratio": "stretch", "image_load_cap": 0, "start_index": 0}},
        "8": {"class_type": "LoadImagesFromFolderKJ", "inputs": {"folder": str(HERE / "mask_grown"), "width": SIZE, "height": SIZE, "keep_aspect_ratio": "stretch", "image_load_cap": 0, "start_index": 0}},
        "9": {"class_type": "ImageToMask", "inputs": {"image": ["8", 0], "channel": "red"}},
        "10": {"class_type": "WanVaceToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": SIZE, "height": SIZE, "length": LENGTH, "batch_size": 1, "strength": 1.0, "control_video": ["7", 0], "control_masks": ["9", 0]}},
        "11": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["10", 0], "negative": ["10", 1], "latent_image": ["10", 2], "seed": seed, "steps": 20, "cfg": 6.0, "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "12": {"class_type": "TrimVideoLatent", "inputs": {"samples": ["11", 0], "trim_amount": ["10", 3]}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": f"vfx_research_vace/{mode}_s{seed}"}},
    }


def run():
    log = []
    for mode in MODES:
        for seed in SEEDS:
            name = f"{mode}_s{seed}"
            out = T.new_directory(HERE / "raw" / name)
            g = graph(mode, seed)
            (out / "workflow_api.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
            started = time.perf_counter()
            history = client.submit_and_wait(g, timeout=1800, comfy_url=URL)
            elapsed = time.perf_counter() - started
            paths = client.download_outputs(history, output_dir=str(out), node_ids=["14"], comfy_url=URL, allow_overwrite=False)
            log.append({"run": name, "seconds": round(elapsed, 1), "frames": len(paths), "prompt_id": history.get("_prompt_id")})
            print(log[-1], flush=True)
            T.save_json(HERE / "raw" / "run_log.json", log)


def analyse():
    original, _ = T.read_frames(SOURCE)
    masks = T.read_masks(MASKS, len(original), (1024, 1024))
    grown_full = [grown(m) for m in masks]
    x0, y0, x1, y1 = CROP
    out = T.new_directory(HERE / "analysis")
    sat_hue = lambda frames: _hue(frames, masks)
    results = {"original": {"inside_mask_adjacent_mae": _inside_temporal(original, masks), **sat_hue(original)}, "runs": {}}
    boards = []
    for mode in MODES:
        for seed in SEEDS:
            name = f"{mode}_s{seed}"
            files = sorted(p for p in (HERE / "raw" / name).glob("*.png"))
            crops = [np.asarray(Image.open(p).convert("RGB")) for p in files][:len(original)]
            full = []
            for o, c in zip(original, crops):
                f = o.copy()
                f[y0:y1, x0:x1] = c
                full.append(f)
            crop_drift = []
            for o, f, g in zip(original, full, grown_full):
                outside = np.zeros(g.shape, bool)
                outside[y0:y1, x0:x1] = g[y0:y1, x0:x1] == 0
                d = np.abs(o.astype(int) - f.astype(int)).max(axis=2)[outside]
                crop_drift.append((float(d.mean()), float((d > 8).mean())))
            composed, per_frame = T.mask_composite(original, full, grown_full, feather=4)
            T.write_sequence(composed, out / f"{name}_pasted")
            results["runs"][name] = {
                "frames": len(crops),
                "outside_mask_in_crop_drift_before_paste": {"mean_abs_max_channel": float(np.mean([a for a, _ in crop_drift])),
                                                            "mean_fraction_gt_8": float(np.mean([b for _, b in crop_drift]))},
                "inside_mask_vs_original_mae": float(np.mean([np.abs(o.astype(int) - c.astype(int))[m > 127].mean() for o, c, m in zip(original, composed, masks)])),
                "outside_changed_pixels_total_after_paste": sum(r["outside_changed_pixels"] for r in per_frame),
                "inside_mask_adjacent_mae": _inside_temporal(composed, masks),
                **sat_hue(composed)}
            boards.append((name, composed))
            print(name, json.dumps(results["runs"][name]), flush=True)
    picks = [0, 12, 18, 40]
    rows = [("ORIGINAL", original)] + boards
    canvas = Image.new("RGB", (240 * len(picks), 262 * len(rows)), "#e5e5e5")
    draw = ImageDraw.Draw(canvas)
    for r, (label, seq) in enumerate(rows):
        draw.text((6, r * 262 + 5), f"{label} frames {picks}", fill="black")
        for k, i in enumerate(picks):
            canvas.paste(Image.fromarray(seq[i][y0:y1, x0:x1]).resize((240, 240)), (k * 240, r * 262 + 22))
    canvas.save(out / "board_vace.png")
    T.save_json(out / "vace_results.json", results)


def _inside_temporal(frames, masks_):
    vals = []
    for t in range(1, len(frames)):
        sel = (masks_[t] > 127) | (masks_[t - 1] > 127)
        vals.append(float(np.abs(frames[t].astype(int) - frames[t - 1].astype(int))[sel].mean()))
    return float(np.mean(vals))


def _hue(frames, masks_):
    cyan = magenta = total = 0
    for f, m in zip(frames, masks_):
        hsv = np.asarray(Image.fromarray(f).convert("HSV")).astype(float)
        sel = (m > 127) & (hsv[..., 1] > 0.3 * 255)
        deg = hsv[..., 0][sel] * 360 / 255
        total += sel.sum()
        cyan += ((deg >= 160) & (deg <= 220)).sum()
        magenta += ((deg >= 260) & (deg <= 330)).sum()
    return {"saturated_in_mask_px": int(total), "cyan_share": float(cyan / max(1, total)), "magenta_share": float(magenta / max(1, total))}


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "analyse": analyse}[sys.argv[1]]()
