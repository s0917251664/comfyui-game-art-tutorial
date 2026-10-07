"""Requirement 2 measurement run (vfx-research-20261007). Writes ./analysis/ (must not exist).

Source: accepted Skye hammer-ready FINAL clip (1024^2, 56 frames). SAM 2.1 hammer masks from video_layers.
A. local_recolor_cyan_to_magenta/ (already produced by vfx_alpha_tools mask-recolor): measure + H.264 drift.
B. r2_wan_canny_regen (existing pose_drive --backend wan --control-type canny, ref = recoloured frame 0):
   explicit 768->1024 Lanczos resize and first-56-frame trim (documented, not hidden), outside-mask drift
   before paste-back, then mask_composite (feather 4) and outside-mask check.
"""
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
original, fps = T.read_frames(HERE.parent / "inputs" / "skye_hammer_ready_FINAL_1024.mp4")
masks = T.read_masks(HERE / "masks_hammer", len(original), (1024, 1024))
results = {"frames": len(original), "mask_area_px": [int((m > 127).sum()) for m in masks]}

# Direction conversion evidence (SAM white=selected -> image_edit alpha 0=edit), frame 0 only.
Image.fromarray(T.sam_to_edit_mask(masks[0]), "RGBA").save(OUT / "frame000_edit_mask_alpha0_edit.png")


def h264(frames, path, crf=18):
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=Fraction(24))
        s.width, s.height, s.pix_fmt = frames[0].shape[1], frames[0].shape[0], "yuv420p"
        s.options = {"crf": str(crf)}
        for f in frames:
            for p in s.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(f), format="rgb24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    return T.read_frames(path)[0]


def inside_temporal(frames, masks_):
    vals = []
    for t in range(1, len(frames)):
        sel = (masks_[t] > 127) | (masks_[t - 1] > 127)
        vals.append(float(np.abs(frames[t].astype(int) - frames[t - 1].astype(int))[sel].mean()))
    return float(np.mean(vals))


def hue_stats(frames, masks_):
    """Share of saturated in-mask pixels per hue family (cyan 160-220, magenta/purple 260-330)."""
    cyan = magenta = total = 0
    for f, m in zip(frames, masks_):
        hsv = np.asarray(Image.fromarray(f).convert("HSV")).astype(float)
        sel = (m > 127) & (hsv[..., 1] > 0.3 * 255)
        deg = hsv[..., 0][sel] * 360 / 255
        total += sel.sum()
        cyan += ((deg >= 160) & (deg <= 220)).sum()
        magenta += ((deg >= 260) & (deg <= 330)).sum()
    return {"saturated_in_mask_px": int(total), "cyan_share": float(cyan / max(1, total)),
            "magenta_share": float(magenta / max(1, total))}


results["original"] = {"inside_mask_adjacent_mae": inside_temporal(original, masks), **hue_stats(original, masks)}

# ---- A. local recolor
local, _ = T.read_frames(HERE / "local_recolor_cyan_to_magenta" / "frames")
results["local_recolor"] = {
    "outside_drift_png": T.outside_mask_drift(original, local, masks)[:1],
    "outside_changed_pixels_total_png": int(sum(int(np.any(l[m == 0] != o[m == 0], axis=1).sum())
                                                for o, l, m in zip(original, local, masks))),
    "inside_mask_adjacent_mae": inside_temporal(local, masks), **hue_stats(local, masks)}
local_mp4 = h264(local, OUT / "local_recolor_h264_crf18.mp4")
orig_mp4 = h264(original, OUT / "original_reencoded_h264_crf18.mp4")
drift_mp4 = T.outside_mask_drift(original, local_mp4, masks)
drift_orig = T.outside_mask_drift(original, orig_mp4, masks)
results["local_recolor"]["after_h264_outside_mean_abs"] = float(np.mean([r["mean_abs_max_channel"] for r in drift_mp4]))
results["original_reencode_outside_mean_abs"] = float(np.mean([r["mean_abs_max_channel"] for r in drift_orig]))

# ---- B. AI regen + paste back
regen_raw, _ = T.read_frames(HERE / "r2_wan_canny_regen_00001_.mp4")
results["ai_regen_raw"] = {"frames": len(regen_raw), "size": list(regen_raw[0].shape[1::-1])}
regen = [np.asarray(Image.fromarray(f).resize((1024, 1024), Image.Resampling.LANCZOS)) for f in regen_raw[:len(original)]]
T.write_sequence(regen, OUT / "ai_regen_resized_1024_trim56")
drift = T.outside_mask_drift(original, regen, masks)
results["ai_regen_raw"]["outside_drift_before_paste"] = {
    "mean_abs_max_channel": float(np.mean([r["mean_abs_max_channel"] for r in drift])),
    "mean_fraction_gt_8": float(np.mean([r["fraction_gt_8"] for r in drift]))}
results["ai_regen_raw"].update(hue_stats(regen, masks))
composed, per_frame = T.mask_composite(original, regen, masks, feather=4)
T.write_sequence(composed, OUT / "ai_regen_pasted_feather4")
results["ai_regen_pasted"] = {"outside_changed_pixels_total": sum(r["outside_changed_pixels"] for r in per_frame),
                              "inside_mask_adjacent_mae": inside_temporal(composed, masks), **hue_stats(composed, masks)}

picks = [0, 12, 18, 40]
rows = []
for label, seq in (("ORIGINAL", original), ("LOCAL RECOLOR", local), ("AI REGEN RAW (resized)", regen),
                   ("AI REGEN PASTED IN MASK", composed)):
    row = Image.new("RGB", (300 * len(picks), 322), "#e5e5e5")
    for k, i in enumerate(picks):
        row.paste(Image.fromarray(seq[i]).crop((160, 220, 700, 760)).resize((300, 300)), (k * 300, 22))
    from PIL import ImageDraw
    ImageDraw.Draw(row).text((6, 5), f"{label}  frames {picks}", fill="black")
    rows.append(row)
board = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)))
for k, r in enumerate(rows):
    board.paste(r, (0, k * r.height))
board.save(OUT / "board_req2.png")
T.save_json(OUT / "req2_results.json", results)
import json
print(json.dumps(results, indent=1)[:3000])
