"""SAM3 text-prompt video tracking ("hammer") vs SAM 2.1 masks on the Skye hammer-ready clip.

Graph wiring/params copied from skills/comfyui-wan-animate/assets/scail2-api.json (nodes 30/31/33):
CheckpointLoaderSimple(sam3.1_multiplex_fp16) -> CLIPTextEncode(text) -> SAM3_VideoTrack(threshold 0.5,
max_objects 4, detect_interval 1) -> SAM3_TrackToMask(all objects) -> MaskToImage -> SaveImage.
Usage: python run_sam3.py run <text> | compare
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools_src"))
import vfx_alpha_tools as T  # noqa: E402
from comfyui_pipeline import client  # noqa: E402

HERE = Path(__file__).resolve().parent
EXP = HERE.parent / "vfx-research-20261007"
SOURCE = EXP / "inputs" / "skye_hammer_ready_FINAL_1024.mp4"
URL = "http://127.0.0.1:8188"


def run(text):
    slug = text.replace(" ", "_")
    out = T.new_directory(HERE / f"sam3_{slug}")
    video_fn = client.upload_image(str(SOURCE), comfy_url=URL)
    g = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": video_fn}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "30": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sam3.1_multiplex_fp16.safetensors"}},
        "31": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["30", 1], "text": text}},
        "33": {"class_type": "SAM3_VideoTrack", "inputs": {"images": ["2", 0], "model": ["30", 0], "conditioning": ["31", 0],
                                                          "detection_threshold": 0.5, "max_objects": 4, "detect_interval": 1}},
        "34": {"class_type": "SAM3_TrackToMask", "inputs": {"track_data": ["33", 0], "object_indices": ""}},
        "35": {"class_type": "MaskToImage", "inputs": {"mask": ["34", 0]}},
        "36": {"class_type": "SaveImage", "inputs": {"images": ["35", 0], "filename_prefix": f"vfx_sam3/{slug}"}},
    }
    (out / "workflow_api.json").write_text(json.dumps(g, indent=1), encoding="utf-8")
    started = time.perf_counter()
    history = client.submit_and_wait(g, timeout=1800, comfy_url=URL)
    seconds = time.perf_counter() - started
    raw = out / "raw"
    paths = client.download_outputs(history, output_dir=str(raw), node_ids=["36"], comfy_url=URL, allow_overwrite=False)
    masks = out / "masks"
    masks.mkdir()
    for k, p in enumerate(sorted(paths)):
        Image.open(p).convert("L").save(masks / f"{k:05d}.png")
    T.save_json(out / "run.json", {"text": text, "seconds": round(seconds, 1), "frames": len(paths),
                                   "prompt_id": history.get("_prompt_id")})
    print(text, round(seconds, 1), "s", len(paths), "frames")


def iou(a, b):
    a, b = a > 127, b > 127
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def compare():
    frames, _ = T.read_frames(SOURCE)
    sets = {
        "SAM2.1 box prompts (frames 0/18/40)": EXP / "req2" / "masks_hammer",
        "SAM2.1 painted frame 0 only": HERE.parent / "vfx-video-inpaint-smoke-20261007" / "masks",
        "SAM2.1 painted 0 + 18": HERE.parent / "vfx-video-inpaint-smoke-20261007" / "masks_2keys",
    }
    sets.update({f"SAM3 text '{d.name[5:].replace('_', ' ')}'": d / "masks" for d in sorted(HERE.glob("sam3_*")) if (d / "masks").is_dir()})
    sets.update({f"SAM3 frame-0 mask '{d.name[9:]}'": d / "masks" for d in sorted(HERE.glob("sam3mask_*")) if (d / "masks").is_dir()})
    sets = {k: v for k, v in sets.items() if "painted frame 0 only" not in k and "painted 0 + 18" not in k}
    loaded = {k: T.read_masks(v, len(frames), (1024, 1024)) for k, v in sets.items()}
    ref_key = "SAM2.1 box prompts (frames 0/18/40)"
    report = {}
    for name, ms in loaded.items():
        areas = [int((m > 127).sum()) for m in ms]
        adj = [iou(ms[t - 1], ms[t]) for t in range(1, len(ms))]
        report[name] = {"empty_frames": sum(a == 0 for a in areas), "area_min": min(areas), "area_max": max(areas),
                        "mean_adjacent_iou": float(np.mean(adj)), "min_adjacent_iou": float(np.min(adj)),
                        "mean_iou_vs_box_prompt_sam2": float(np.mean([iou(a, b) for a, b in zip(ms, loaded[ref_key])]))}
        print(name, json.dumps(report[name]))
    picks = [0, 4, 14, 28, 55]
    thumb = 220
    rows = []
    for name, ms in loaded.items():
        row = Image.new("RGB", (thumb * len(picks), thumb + 22), "#e5e5e5")
        from PIL import ImageDraw
        ImageDraw.Draw(row).text((6, 5), name, fill="black")
        for k, i in enumerate(picks):
            x = frames[i].astype(np.float32)
            sel = ms[i] > 127
            x[sel] = x[sel] * 0.45 + np.array([255, 0, 255], np.float32) * 0.55
            row.paste(Image.fromarray(x.astype(np.uint8)).crop((150, 150, 750, 750)).resize((thumb, thumb)), (k * thumb, 22))
        rows.append(row)
    board = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)))
    y = 0
    for r in rows:
        board.paste(r, (0, y))
        y += r.height
    board.save(HERE / "compare_board.png")
    T.save_json(HERE / "compare.json", report)


if __name__ == "__main__":
    run(sys.argv[2]) if sys.argv[1] == "run" else compare()
