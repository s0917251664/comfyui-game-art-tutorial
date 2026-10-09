"""去背與循環的技術量測，以及比較圖。不是美術驗收。"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from .pixel import over, parse_hex


DARK_BG = (24, 27, 33)

LIGHT_BG = (232, 231, 225)

EDGE_LOW, EDGE_HIGH = 0.05, 0.95

VISIBLE = 0.02

def alpha_metrics(rgba_frames, key=None, reference_alpha=None):
    """Distribution, temporal stability and fringe diagnostics for an RGBA sequence."""
    alphas = np.stack([f[..., 3] for f in rgba_frames]).astype(np.float32) / 255.0
    total = alphas.size
    bins = {
        "zero": float((alphas == 0).sum() / total),
        "0_to_0.1": float(((alphas > 0) & (alphas <= 0.1)).sum() / total),
        "0.1_to_0.5": float(((alphas > 0.1) & (alphas <= 0.5)).sum() / total),
        "0.5_to_0.9": float(((alphas > 0.5) & (alphas <= 0.9)).sum() / total),
        "0.9_to_1": float(((alphas > 0.9) & (alphas < 1)).sum() / total),
        "one": float((alphas == 1).sum() / total),
    }
    visible = alphas > 0
    semi_of_visible = float(((alphas > 0) & (alphas < 1)).sum() / max(1, visible.sum()))
    deltas, flickers = [], []
    for t in range(1, len(alphas)):
        union = (alphas[t] > VISIBLE) | (alphas[t - 1] > VISIBLE)
        deltas.append(float(np.abs(alphas[t] - alphas[t - 1])[union].mean()) if union.any() else 0.0)
    for t in range(1, len(alphas) - 1):
        union = (alphas[t] > VISIBLE) | (alphas[t - 1] > VISIBLE) | (alphas[t + 1] > VISIBLE)
        second = np.abs(alphas[t] - 0.5 * (alphas[t - 1] + alphas[t + 1]))
        flickers.append(float(second[union].mean()) if union.any() else 0.0)
    edge_rgb = np.concatenate([f[..., :3][(f[..., 3] > EDGE_LOW * 255) & (f[..., 3] < EDGE_HIGH * 255)]
                               for f in rgba_frames]).astype(np.float32) if rgba_frames else np.zeros((0, 3))
    fringe = {"edge_pixels": int(len(edge_rgb))}
    if len(edge_rgb):
        if key is not None:
            key_rgb = np.array(parse_hex(key), dtype=np.float32)
            dominant = int(np.argmax(key_rgb))
            others = [c for c in range(3) if c != dominant]
            excess = np.maximum(0.0, edge_rgb[:, dominant] - edge_rgb[:, others].max(axis=1))
            fringe.update({"key_channel": "RGB"[dominant],
                           "mean_key_excess": float(excess.mean()),
                           "fraction_key_excess_gt_16": float((excess > 16).mean())})
        fringe["mean_edge_rgb"] = [float(v) for v in edge_rgb.mean(axis=0)]
    report = {
        "frames": len(rgba_frames),
        "size": [int(rgba_frames[0].shape[1]), int(rgba_frames[0].shape[0])],
        "alpha_histogram_fraction": bins,
        "mean_alpha": float(alphas.mean()),
        "semi_transparent_fraction_of_visible": semi_of_visible,
        "temporal": {
            "mean_abs_adjacent_alpha_delta": float(np.mean(deltas)) if deltas else 0.0,
            "max_abs_adjacent_alpha_delta": float(np.max(deltas)) if deltas else 0.0,
            "max_delta_frame": int(np.argmax(deltas) + 1) if deltas else 0,
            "mean_second_difference_flicker": float(np.mean(flickers)) if flickers else 0.0,
            "max_second_difference_flicker": float(np.max(flickers)) if flickers else 0.0,
            "max_flicker_frame": int(np.argmax(flickers) + 1) if flickers else 0,
            "note": "Computed over pixels with alpha > 0.02 in any compared frame; motion also raises these values",
        },
        "fringe": fringe,
    }
    if reference_alpha is not None:
        ref = np.stack(reference_alpha).astype(np.float32) / 255.0
        if ref.shape != alphas.shape:
            raise ValueError("reference alpha shape does not match")
        edge = (ref > EDGE_LOW) & (ref < EDGE_HIGH)
        report["against_reference"] = {
            "alpha_mae": float(np.abs(alphas - ref).mean()),
            "soft_region_alpha_mae": float(np.abs(alphas - ref)[edge].mean()) if edge.any() else None,
            "visible_iou_0_5": float(((alphas >= .5) & (ref >= .5)).sum() / max(1, ((alphas >= .5) | (ref >= .5)).sum())),
        }
    return report

def _label_tile(image, label, width):
    image = Image.fromarray(image) if isinstance(image, np.ndarray) else image
    scale = width / image.width
    image = image.convert("RGB").resize((width, max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    tile = Image.new("RGB", (width, image.height + 22), "#e5e5e5")
    tile.paste(image, (0, 22))
    ImageDraw.Draw(tile).text((6, 5), label, fill="black")
    return tile

def comparison_board(original, candidates, target, thumb=320):
    """Rows: original + each RGBA candidate on alpha, dark and light backgrounds."""
    rows = [[_label_tile(original[..., :3], "ORIGINAL", thumb)]]
    for name, rgba in candidates:
        alpha = np.repeat(rgba[..., 3:4], 3, axis=2)
        rows.append([_label_tile(alpha, f"{name} ALPHA", thumb),
                     _label_tile(over(rgba, DARK_BG), f"{name} ON DARK", thumb),
                     _label_tile(over(rgba, LIGHT_BG), f"{name} ON LIGHT", thumb)])
    width = thumb * max(len(r) for r in rows)
    height = sum(r[0].height for r in rows)
    canvas = Image.new("RGB", (width, height), "#e5e5e5")
    y = 0
    for row in rows:
        for i, tile in enumerate(row):
            canvas.paste(tile, (i * thumb, y))
        y += row[0].height
    canvas.save(target, format="PNG")
    return target

def outside_mask_drift(original, candidate, selected_masks):
    """Per-frame difference outside the mask for a candidate that was *not* recomposited."""
    rows = []
    for o, c, m in zip(original, candidate, selected_masks):
        outside = m == 0
        delta = np.abs(o[..., :3].astype(np.int16) - c[..., :3].astype(np.int16)).max(axis=2)[outside]
        rows.append({"mean_abs_max_channel": float(delta.mean()) if delta.size else 0.0,
                     "fraction_gt_8": float((delta > 8).mean()) if delta.size else 0.0})
    return rows

def frame_difference(a, b, roi=None):
    a = a[..., :3].astype(np.int16)
    b = b[..., :3].astype(np.int16)
    if a.shape != b.shape:
        raise ValueError("frames must have the same shape")
    if roi is not None:
        x0, y0, x1, y1 = roi
        a, b = a[y0:y1, x0:x1], b[y0:y1, x0:x1]
    delta = np.abs(a - b)
    mse = float((delta.astype(np.float32) ** 2).mean())
    return {"mae": float(delta.mean()),
            "psnr_db": float("inf") if mse == 0 else float(10 * math.log10(255 ** 2 / mse)),
            "fraction_max_channel_gt_16": float((delta.max(axis=2) > 16).mean())}

def subject_roi(image, key="00FF00", tolerance=60, margin=16):
    """Bounding box of pixels farther than ``tolerance`` from the key colour, padded by ``margin``."""
    key_rgb = np.array(parse_hex(key), dtype=np.int16)
    distance = np.abs(image[..., :3].astype(np.int16) - key_rgb).max(axis=2)
    ys, xs = np.nonzero(distance > tolerance)
    if not len(xs):
        return None
    h, w = distance.shape
    return (max(0, int(xs.min()) - margin), max(0, int(ys.min()) - margin),
            min(w, int(xs.max()) + 1 + margin), min(h, int(ys.max()) + 1 + margin))

def _finite(d):
    return {k: (None if isinstance(v, float) and math.isinf(v) else v) for k, v in d.items()}

def loop_metrics(frames, reference=None, key=None):
    """First-frame fidelity, end-to-start return and loop seam against ordinary motion."""
    h, w = frames[0].shape[:2]
    ref = None
    if reference is not None:
        # H3 stretches the first keyframe to the canvas ("disabled" crop); match that geometry.
        ref = np.asarray(Image.fromarray(reference[..., :3]).resize((w, h), Image.Resampling.LANCZOS))
    roi = subject_roi(ref if ref is not None else frames[0], key) if key else None
    adjacent = [frame_difference(frames[t - 1], frames[t])["mae"] for t in range(1, len(frames))]
    adjacent_roi = [frame_difference(frames[t - 1], frames[t], roi)["mae"] for t in range(1, len(frames))] if roi else None
    seam = frame_difference(frames[-1], frames[0])
    report = {"frames": len(frames), "size": [w, h], "roi": list(roi) if roi else None,
              "adjacent_mae": {"median": float(np.median(adjacent)), "p95": float(np.percentile(adjacent, 95)),
                               "max": float(np.max(adjacent))},
              "last_vs_first": _finite(seam),
              "seam_to_median_adjacent_ratio": float(seam["mae"] / max(1e-6, np.median(adjacent)))}
    if roi:
        seam_roi = frame_difference(frames[-1], frames[0], roi)
        report["adjacent_mae_roi"] = {"median": float(np.median(adjacent_roi)), "p95": float(np.percentile(adjacent_roi, 95)),
                                      "max": float(np.max(adjacent_roi))}
        report["last_vs_first_roi"] = _finite(seam_roi)
        report["seam_to_median_adjacent_ratio_roi"] = float(seam_roi["mae"] / max(1e-6, np.median(adjacent_roi)))
    if ref is not None:
        report["first_vs_reference"] = _finite(frame_difference(frames[0], ref))
        report["last_vs_reference"] = _finite(frame_difference(frames[-1], ref))
        if roi:
            report["first_vs_reference_roi"] = _finite(frame_difference(frames[0], ref, roi))
            report["last_vs_reference_roi"] = _finite(frame_difference(frames[-1], ref, roi))
    return report, ref
