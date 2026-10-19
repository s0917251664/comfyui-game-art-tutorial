"""研究用：量測 batch 輸出並做對照圖（不是產線入口）。

python analyze.py <experiment_dir> [--reference start.png] [--green]
- 每個 run 資料夾找 outputs/ 下的 mp4，抽 6 張等距關鍵幀拼成一列，所有 run 疊成 <experiment_dir>/compare.jpg。
- metrics.json：幀數、尺寸、耗時、相鄰幀平均差（閃爍／動態量）。
- --green：以綠幕判前景，記錄每幀前景外框高度相對首幀的最大比例（鏡頭推近）、外框是否碰到畫面邊（被裁）。
- --reference：首幀、末幀與參考圖（縮到同尺寸）的平均絕對差（0–255）。
"""
import argparse
import json
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw


def read_frames(path):
    with av.open(str(path)) as container:
        return [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]


def fg_mask(frame):
    f = frame.astype(np.int16)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    return ~((g > r + 40) & (g > b + 40))


def bbox(mask):
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def mad(a, b):
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def find_video(run_dir):
    vids = sorted(p for p in (run_dir / "outputs").rglob("*.mp4") if "composited" not in p.parts)
    composited = sorted((run_dir / "outputs").rglob("*composited*.mp4"))
    return (composited or vids or [None])[0]


def analyze_run(run_dir, reference, green):
    video = find_video(run_dir)
    if video is None:
        return None, None
    frames = read_frames(video)
    h, w = frames[0].shape[:2]
    m = {"run": run_dir.name, "video": str(video), "frames": len(frames), "size": [w, h]}
    result = run_dir / "run.result.json"
    if result.is_file():
        data = json.loads(result.read_text(encoding="utf-8"))
        m["status"] = data.get("status")
        m["elapsed_seconds"] = data.get("elapsed_seconds") or data.get("timing", {}).get("total_seconds")
    diffs = [mad(frames[i], frames[i + 1]) for i in range(len(frames) - 1)]
    m["adjacent_diff_mean"] = round(float(np.mean(diffs)), 3)
    m["adjacent_diff_max"] = round(float(np.max(diffs)), 3)
    if reference is not None:
        ref = np.asarray(Image.open(reference).convert("RGB").resize((w, h), Image.LANCZOS))
        m["first_vs_ref"] = round(mad(frames[0], ref), 2)
        m["last_vs_ref"] = round(mad(frames[-1], ref), 2)
    if green:
        boxes = [bbox(fg_mask(f)) for f in frames]
        h0 = (boxes[0][3] - boxes[0][1] + 1) if boxes[0] else None
        heights = [(b[3] - b[1] + 1) if b else 0 for b in boxes]
        m["fg_height_first"] = h0
        m["fg_height_max_ratio"] = round(max(heights) / h0, 3) if h0 else None
        m["fg_height_min_ratio"] = round(min(heights) / h0, 3) if h0 else None
        edge = [i for i, b in enumerate(boxes) if b and (b[0] <= 1 or b[1] <= 1 or b[2] >= w - 2 or b[3] >= h - 2)]
        m["frames_touching_edge"] = len(edge)
    idx = np.linspace(0, len(frames) - 1, 6).round().astype(int)
    thumbs = [Image.fromarray(frames[i]).resize((192, int(192 * h / w))) for i in idx]
    return m, thumbs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment_dir")
    ap.add_argument("--reference")
    ap.add_argument("--green", action="store_true")
    args = ap.parse_args()
    root = Path(args.experiment_dir)
    rows, metrics = [], []
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        m, thumbs = analyze_run(run_dir, args.reference, args.green)
        if m is None:
            metrics.append({"run": run_dir.name, "status": "no video"})
            continue
        metrics.append(m)
        rows.append((run_dir.name, thumbs))
    (root / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if rows:
        tw, th = rows[0][1][0].size
        label = 170
        sheet = Image.new("RGB", (label + tw * 6, th * len(rows)), "white")
        draw = ImageDraw.Draw(sheet)
        for r, (name, thumbs) in enumerate(rows):
            draw.text((6, r * th + th // 2 - 6), name, fill="black")
            for c, t in enumerate(thumbs):
                sheet.paste(t, (label + c * tw, r * th))
        sheet.save(root / "compare.jpg", quality=88)
    for m in metrics:
        print(json.dumps(m, ensure_ascii=False))


if __name__ == "__main__":
    main()
