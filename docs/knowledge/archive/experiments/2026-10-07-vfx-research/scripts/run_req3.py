"""Requirement 3 measurement run (vfx-research-20261007). Writes ./analysis/ (must not exist)."""
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools_src"))
import vfx_alpha_tools as T  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = T.new_directory(HERE / "analysis")
IDLE = HERE.parent / "inputs" / "skye_idle_square_1024.png"
PY = sys.executable
CLIPS = {
    "fx_loop_h3_first_last_idle": "r3_idle_loop_fxloop_00001_.mp4",
    "transition_h3_idle_attack_idle": "r3_attack_idle_transition_00001_.mp4",
    "img2video_h3_first_only": "r3_idle_img2video_h3_00001_.mp4",
    "img2video_wan_first_only": "r3_idle_img2video_wan_00001_.mp4",
}

summary = {}
for label, name in CLIPS.items():
    video = HERE / name
    if not video.is_file():
        summary[label] = {"status": "missing", "video": str(video)}
        continue
    frames, fps = T.read_frames(video)
    h, w = frames[0].shape[:2]
    report, ref = T.loop_metrics(frames, np.asarray(Image.open(IDLE).convert("RGB")), "00FF00")
    roi = tuple(report["roi"])
    report["adjacent_mae_roi_series"] = [round(T.frame_difference(frames[t - 1], frames[t], roi)["mae"], 3)
                                         for t in range(1, len(frames))]
    # Floor: the same reference canvas through libx264 yuv420p only (no model).
    floor_path = OUT / f"{label}_codec_floor.mp4"
    with av.open(str(floor_path), "w") as c:
        s = c.add_stream("libx264", rate=Fraction(24))
        s.width, s.height, s.pix_fmt = w, h, "yuv420p"
        for _ in range(3):
            for p in s.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(ref), format="rgb24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    floor = T.read_frames(floor_path)[0][0]
    report["codec_floor_reference_vs_h264"] = T._finite(T.frame_difference(floor, ref))
    report["codec_floor_reference_vs_h264_roi"] = T._finite(T.frame_difference(floor, ref, roi))
    d = OUT / label
    d.mkdir()
    Image.fromarray(ref).save(d / "reference_canvas.png")
    Image.fromarray(frames[0]).save(d / "first.png")
    Image.fromarray(frames[-1]).save(d / "last.png")
    for pair, (src, edt) in {"first_vs_reference": ("reference_canvas.png", "first.png"),
                             "last_vs_first": ("first.png", "last.png")}.items():
        subprocess.run([PY, str(REPO / "tools_src" / "image_edit_tools.py"), "compare", "--source", str(d / src),
                        "--edited", str(d / edt), "--output-dir", str(d / f"compare_{pair}")], check=True,
                       capture_output=True)
    picks = list(range(0, len(frames), max(1, len(frames) // 8))) + [len(frames) - 1]
    x0, y0, x1, y1 = roi
    tile_w = x1 - x0
    strip = Image.new("RGB", (tile_w * len(picks), y1 - y0))
    for k, i in enumerate(picks):
        strip.paste(Image.fromarray(frames[i][y0:y1, x0:x1]), (k * tile_w, 0))
    strip.save(d / "frames_strip_roi.png")
    report.update({"video": T.file_record(video), "fps": fps, "strip_frames": picks})
    T.save_json(d / "loop_metrics.json", report)
    summary[label] = {k: report.get(k) for k in (
        "frames", "size", "roi", "first_vs_reference_roi", "last_vs_reference_roi", "last_vs_first_roi",
        "adjacent_mae_roi", "seam_to_median_adjacent_ratio_roi", "codec_floor_reference_vs_h264_roi")}
T.save_json(OUT / "req3_summary.json", summary)
print(json.dumps(summary, indent=1))
