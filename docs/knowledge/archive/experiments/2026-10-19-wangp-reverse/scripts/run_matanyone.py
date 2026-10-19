"""研究用：MatAnyone2 影片去背（E7，不是產線入口；⚠ MatAnyone 只限非商業用途）。

python run_matanyone.py --video <src.mp4> --seed-mask <首幀遮罩.png，白＝前景> --out <新資料夾> [--warmup 10] [--erode 0] [--dilate 0]

把影片與遮罩複製到 ComfyUI/input/wangp_research/，送一張研究 graph：
LoadVideo→GetVideoComponents→MatAnyone2（首幀 MASK）→matte→ImageToMask→InvertMask→JoinImageWithAlpha→SaveImage（RGBA PNG），
另存 matte（灰階 alpha）。完成後把輸出 PNG 複製到 <out>/rgba、<out>/alpha，並寫 run.json。
"""
import argparse
import json
import shutil
import time
import urllib.request
import uuid
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
COMFY_DIR = Path(r"C:\Users\XU\ComfyUI")
SUB = "wangp_research"


def post(path, data):
    req = urllib.request.Request(COMFY + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(COMFY + path) as r:
        return json.load(r)


def graph(video_name, mask_name, prefix, warmup, erode, dilate):
    return {
        "1": {"class_type": "LoadVideo", "inputs": {"file": f"{SUB}/{video_name}"}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "LoadImage", "inputs": {"image": f"{SUB}/{mask_name}"}},
        "4": {"class_type": "ImageToMask", "inputs": {"image": ["3", 0], "channel": "red"}},
        "5": {"class_type": "MatAnyone2", "inputs": {"src_video": ["2", 0], "mask_frame": 0, "n_warmup": warmup,
                                                      "foreground_MASK": ["4", 0], "r_erode": erode, "r_dilate": dilate,
                                                      "max_internal_size": -1, "max_mem_frames": 5, "use_long_term": False}},
        "6": {"class_type": "ImageToMask", "inputs": {"image": ["5", 0], "channel": "red"}},
        "7": {"class_type": "InvertMask", "inputs": {"mask": ["6", 0]}},
        "8": {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["2", 0], "alpha": ["7", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": f"{prefix}/rgba"}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["5", 0], "filename_prefix": f"{prefix}/alpha"}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--seed-mask", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--erode", type=int, default=0)
    ap.add_argument("--dilate", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"{out} 已存在")
    tag = uuid.uuid4().hex[:8]
    dest = COMFY_DIR / "input" / SUB
    dest.mkdir(parents=True, exist_ok=True)
    video_name = f"{tag}_{Path(args.video).name}"
    mask_name = f"{tag}_{Path(args.seed_mask).name}"
    shutil.copy2(args.video, dest / video_name)
    shutil.copy2(args.seed_mask, dest / mask_name)
    prefix = f"wangp_matanyone/{tag}"
    g = graph(video_name, mask_name, prefix, args.warmup, args.erode, args.dilate)
    t0 = time.time()
    pid = post("/prompt", {"prompt": g, "client_id": tag})["prompt_id"]
    while True:
        hist = get(f"/history/{pid}")
        if pid in hist:
            break
        time.sleep(2)
    elapsed = round(time.time() - t0, 1)
    entry = hist[pid]
    status = entry.get("status", {})
    out.mkdir(parents=True)
    copied = {}
    for node, kind in (("9", "rgba"), ("10", "alpha")):
        (out / kind).mkdir()
        imgs = entry.get("outputs", {}).get(node, {}).get("images", [])
        for i, img in enumerate(imgs):
            src = COMFY_DIR / "output" / img["subfolder"] / img["filename"]
            shutil.copy2(src, out / kind / f"{i:05d}.png")
        copied[kind] = len(imgs)
    (out / "run.json").write_text(json.dumps({
        "prompt_id": pid, "status": status.get("status_str"), "elapsed_seconds": elapsed,
        "video": str(Path(args.video).resolve()), "seed_mask": str(Path(args.seed_mask).resolve()),
        "warmup": args.warmup, "erode": args.erode, "dilate": args.dilate, "frames": copied, "graph": g,
        "note": "MatAnyone2（NTU S-Lab License 1.0，只限非商業用途）研究輸出"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"status": status.get("status_str"), "elapsed": elapsed, "frames": copied}, ensure_ascii=False))


if __name__ == "__main__":
    main()
