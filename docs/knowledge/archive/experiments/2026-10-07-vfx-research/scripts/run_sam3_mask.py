"""SAM3 video tracking seeded by a frame-0 mask (no text): SAM3_VideoTrack.initial_mask, conditioning omitted.

Usage: python run_sam3_mask.py <label> <frame0_mask.png>   (white = object; RGBA alpha ignored)
Writes ./sam3mask_<label>/ with workflow_api.json, raw/, masks/, run.json.
"""
import json
import sys
import time
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools_src"))
import vfx_alpha_tools as T  # noqa: E402
from comfyui_pipeline import client  # noqa: E402

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "vfx-research-20261007" / "inputs" / "skye_hammer_ready_FINAL_1024.mp4"
URL = "http://127.0.0.1:8188"

label, mask_path = sys.argv[1], Path(sys.argv[2])
out = T.new_directory(HERE / f"sam3mask_{label}")
seed = out / "seed_mask_rgb.png"
with Image.open(mask_path) as im:
    im.convert("RGB").convert("L").point(lambda v: 255 if v > 127 else 0).convert("RGB").save(seed)
video_fn = client.upload_image(str(SOURCE), comfy_url=URL)
mask_fn = client.upload_image(str(seed), comfy_url=URL)
g = {
    "1": {"class_type": "LoadVideo", "inputs": {"file": video_fn}},
    "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
    "10": {"class_type": "LoadImage", "inputs": {"image": mask_fn}},
    "11": {"class_type": "ImageToMask", "inputs": {"image": ["10", 0], "channel": "red"}},
    "30": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sam3.1_multiplex_fp16.safetensors"}},
    "33": {"class_type": "SAM3_VideoTrack", "inputs": {"images": ["2", 0], "model": ["30", 0], "initial_mask": ["11", 0],
                                                      "detection_threshold": 0.5, "max_objects": 1, "detect_interval": 1}},
    "34": {"class_type": "SAM3_TrackToMask", "inputs": {"track_data": ["33", 0], "object_indices": ""}},
    "35": {"class_type": "MaskToImage", "inputs": {"mask": ["34", 0]}},
    "36": {"class_type": "SaveImage", "inputs": {"images": ["35", 0], "filename_prefix": f"vfx_sam3mask/{label}"}},
}
(out / "workflow_api.json").write_text(json.dumps(g, indent=1), encoding="utf-8")
started = time.perf_counter()
history = client.submit_and_wait(g, timeout=1800, comfy_url=URL)
seconds = time.perf_counter() - started
paths = client.download_outputs(history, output_dir=str(out / "raw"), node_ids=["36"], comfy_url=URL, allow_overwrite=False)
(out / "masks").mkdir()
for k, p in enumerate(sorted(paths)):
    Image.open(p).convert("L").save(out / "masks" / f"{k:05d}.png")
T.save_json(out / "run.json", {"label": label, "seed_mask": str(mask_path), "seconds": round(seconds, 1),
                               "frames": len(paths), "prompt_id": history.get("_prompt_id")})
print(label, round(seconds, 1), "s", len(paths), "frames")
