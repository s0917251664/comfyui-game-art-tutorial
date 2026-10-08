"""Local VFX alpha extraction, packing, video object marking/paste-back and Idle loop measurements.

Pure Pillow/NumPy pixel operations; PyAV is only needed to read MP4 input or to
write WebM. No ComfyUI server, no model download, no generation graph. BiRefNet
per-frame matting reuses ``benchmark_birefnet`` and needs the local CUDA runtime
plus already-installed weights.

Alpha conventions:
- RGBA outputs are *straight* (unpremultiplied) alpha, 0 = transparent.
- SAM / video_layers masks are ``L`` images, white = selected.
- image_edit_tools masks are PNG alpha, 0 = edited, 255 = preserve.
  ``sam-to-edit-mask`` converts the former into the latter.

Every output directory must not exist yet; nothing is overwritten. Numbers are
technical diagnostics, not art acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

import local_pixels

DARK_BG = (24, 27, 33)
LIGHT_BG = (232, 231, 225)
EDGE_LOW, EDGE_HIGH = 0.05, 0.95
VISIBLE = 0.02


# ---------------------------------------------------------------- file helpers

def file_record(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def new_directory(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=False)
    return path


def save_json(path, payload):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def _png_paths(directory):
    paths = sorted(p for p in Path(directory).iterdir() if p.suffix.lower() == ".png")
    if not paths:
        raise ValueError(f"No PNG frames in {directory}")
    return paths


def read_frames(source, mode="RGB"):
    """Return (frames, fps). ``source`` is a video file or a directory of PNG frames."""
    source = Path(source)
    if source.is_dir():
        frames = []
        for p in _png_paths(source):
            with Image.open(p) as im:
                frames.append(np.asarray(im.convert(mode)))
        return frames, None
    frames, fps = local_pixels.decode_video_frames(source, mode)
    if not frames:
        raise ValueError(f"No decodable video frames in {source}")
    return frames, fps


def gray_mask_array(im, name="mask"):
    """Selected-white mask as L array. Accept L/1 and R=G=B RGB (SAM3 SaveImage); reject alpha and colour."""
    arr = local_pixels.decode_selected_white_mask(im)
    if arr is None:
        raise ValueError(f"Mask {name} must be selected-white grayscale (L, or RGB with R=G=B); got mode {im.mode}. "
                         "Alpha masks (image inpaint, 0=edit) use the opposite convention")
    return arr


def read_masks(directory, count=None, size=None):
    masks = []
    for p in _png_paths(directory):
        with Image.open(p) as im:
            if size is not None and im.size != size:
                raise ValueError(f"Mask {p.name} is {im.size}, expected {size}; automatic resizing is not allowed")
            masks.append(gray_mask_array(im, p.name))
    if count is not None and len(masks) != count:
        raise ValueError(f"Mask count {len(masks)} does not match frame count {count}")
    return masks


def write_sequence(frames, directory):
    directory = new_directory(directory)
    for i, frame in enumerate(frames):
        Image.fromarray(frame).save(directory / f"{i:05d}.png")
    return directory


# ---------------------------------------------------------------- alpha extraction

def _check_unit(name, value, low=0.0, high=1.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and between {low} and {high}")


def luma_alpha(rgb, black_point=0.0, white_point=1.0, gamma=1.0):
    """Black-background effect -> straight RGBA.

    The source is treated as premultiplied colour over ``black_point``. Alpha is the
    max channel remapped to [black_point, white_point]; colour is unpremultiplied so
    ``over`` compositing reproduces the source on black. For additive blending use
    the original black-background RGB directly.
    """
    _check_unit("black_point", black_point)
    _check_unit("white_point", white_point)
    if white_point <= black_point:
        raise ValueError("white_point must be greater than black_point")
    if isinstance(gamma, bool) or not isinstance(gamma, (int, float)) or not math.isfinite(gamma) or gamma <= 0:
        raise ValueError("gamma must be positive and finite")
    x = rgb[..., :3].astype(np.float32) / 255.0
    premultiplied = np.clip((x - black_point) / (white_point - black_point), 0.0, 1.0)
    peak = premultiplied.max(axis=2)
    alpha = peak ** gamma if gamma != 1.0 else peak
    safe = np.where(alpha > 0, alpha, 1.0)[..., None]
    straight = np.clip(premultiplied / safe, 0.0, 1.0)
    straight[alpha <= 0] = 0.0
    out = np.empty(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.round(straight * 255.0).astype(np.uint8)
    out[..., 3] = np.round(alpha * 255.0).astype(np.uint8)
    return out


def parse_hex(colour):
    colour = str(colour).strip().lstrip("#")
    if len(colour) != 6 or any(c not in "0123456789abcdefABCDEF" for c in colour):
        raise ValueError(f"Colour must be 6 hex digits, got {colour!r}")
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


def chroma_alpha(rgb, key="00FF00", tolerance=60.0, softness=40.0, despill=False, unmix=False):
    """Green-screen key with the same alpha ramp as ``video_composite`` (baseline).

    ``unmix`` removes the key colour contribution from semi-transparent pixels;
    ``despill`` clamps the key's dominant channel to the max of the other two.
    Both default off so the baseline matches the existing pipeline.
    """
    if not 0.0 <= tolerance <= 255.0:
        raise ValueError("tolerance must be between 0 and 255")
    if not 0.0 < softness <= 255.0:
        raise ValueError("softness must be in (0, 255]")
    key_rgb = np.array(parse_hex(key), dtype=np.float32)
    x = rgb[..., :3].astype(np.float32)
    distance = np.abs(x - key_rgb).max(axis=2)
    alpha = np.clip((distance - tolerance) / softness, 0.0, 1.0)
    colour = x
    if unmix:
        safe = np.where(alpha > 0, alpha, 1.0)[..., None]
        colour = np.clip((x - (1.0 - alpha[..., None]) * key_rgb) / safe, 0.0, 255.0)
    if despill:
        dominant = int(np.argmax(key_rgb))
        others = [c for c in range(3) if c != dominant]
        colour = colour.copy()
        colour[..., dominant] = np.minimum(colour[..., dominant], colour[..., others].max(axis=2))
    out = np.empty(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.round(colour).astype(np.uint8)
    out[..., 3] = np.round(alpha * 255.0).astype(np.uint8)
    out[out[..., 3] == 0, :3] = 0
    return out


def birefnet_alpha(frames, model_root, variant="general"):
    """Per-frame BiRefNet matte (no temporal model). Returns (rgba_frames, seconds_per_frame)."""
    import torch
    try:
        import benchmark_birefnet as bb
    except ImportError as exc:
        raise RuntimeError("birefnet-alpha 只能在 repo 的 tools_src/ 執行（需要 benchmark_birefnet.py，未部署）") from exc
    if variant not in bb.VARIANTS:
        raise ValueError(f"Unknown variant {variant!r}; choose from {sorted(bb.VARIANTS)}")
    if not torch.cuda.is_available():
        raise RuntimeError("BiRefNet per-frame matting requires CUDA in this pipeline")
    device = torch.device("cuda")
    directory, size = bb.VARIANTS[variant]
    model_dir = Path(model_root) / directory
    if not (model_dir / "model.safetensors").is_file():
        raise FileNotFoundError(f"missing model: {model_dir / 'model.safetensors'}")
    model = bb.load_variant(model_dir, device)
    out, elapsed = [], []
    try:
        for frame in frames:
            image = Image.fromarray(frame[..., :3])
            mask, seconds, _ = bb.infer_mask(model, image, size, device)
            rgba = np.dstack([frame[..., :3], np.asarray(mask)]).astype(np.uint8)
            out.append(rgba)
            elapsed.append(seconds)
    finally:
        del model
        torch.cuda.empty_cache()
    return out, float(np.mean(elapsed))


# ---------------------------------------------------------------- measurements

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


def over(rgba, background):
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    bg = np.empty(rgba.shape[:2] + (3,), dtype=np.float32)
    bg[...] = background
    return np.round(rgba[..., :3].astype(np.float32) * a + bg * (1.0 - a)).astype(np.uint8)


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


# ---------------------------------------------------------------- packing

def sprite_sheet(rgba_frames, target, columns=None, fps=24):
    n = len(rgba_frames)
    h, w = rgba_frames[0].shape[:2]
    if any(f.shape[:2] != (h, w) for f in rgba_frames):
        raise ValueError("All frames must have the same size")
    columns = columns or math.ceil(math.sqrt(n))
    if columns < 1:
        raise ValueError("columns must be >= 1")
    rows = math.ceil(n / columns)
    sheet = Image.new("RGBA", (columns * w, rows * h), (0, 0, 0, 0))
    rects = []
    for i, frame in enumerate(rgba_frames):
        x, y = (i % columns) * w, (i // columns) * h
        sheet.paste(Image.fromarray(frame, "RGBA"), (x, y))
        rects.append({"index": i, "x": x, "y": y, "w": w, "h": h})
    sheet.save(target, format="PNG")
    meta = {"image": Path(target).name, "frame_width": w, "frame_height": h, "columns": columns,
            "rows": rows, "frame_count": n, "fps": fps, "alpha": "straight", "frames": rects}
    save_json(Path(target).with_suffix(".json"), meta)
    return meta


def write_apng(rgba_frames, target, fps=24):
    images = [Image.fromarray(f, "RGBA") for f in rgba_frames]
    images[0].save(target, format="PNG", save_all=True, append_images=images[1:],
                   duration=round(1000 / fps), loop=0, disposal=1, blend=0)
    return target


def write_webm_alpha(rgba_frames, target, fps=24, crf=18):
    """VP9 + alpha (yuva420p). Chroma is subsampled and lossy; PNG stays the master."""
    h, w = rgba_frames[0].shape[:2]
    if w % 2 or h % 2:
        raise ValueError("WebM yuva420p needs even width and height")
    local_pixels.encode_video_frames(
        rgba_frames, target, codec="libvpx-vp9", pix_fmt="yuva420p", ndarray_format="rgba",
        fps=fps, container_format="webm", options={"crf": str(crf), "b": "0", "auto-alt-ref": "0"},
        contiguous=True)
    return target


def read_webm_alpha(path):
    """Decode a VP9 alpha WebM with libvpx (FFmpeg's native vp9 decoder drops alpha)."""
    import av
    frames = []
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        decoder = av.CodecContext.create("libvpx-vp9", "r")
        # demux() ends with an empty packet, which also flushes the decoder.
        for packet in container.demux(stream):
            for frame in decoder.decode(packet):
                frames.append(frame.to_ndarray(format="rgba"))
    return frames


# ---------------------------------------------------------------- masked recomposition

def sam_to_edit_mask(selected_l):
    """SAM ``L`` mask (255 = selected) -> image_edit_tools RGBA mask (alpha 0 = edit)."""
    alpha = 255 - np.asarray(selected_l, dtype=np.uint8)
    out = np.zeros(alpha.shape + (4,), dtype=np.uint8)
    out[..., :3] = 255
    out[..., 3] = alpha
    return out


def masked_hue_rotate(rgb, selected, from_hue, to_hue, hue_range=45.0, min_saturation=0.12):
    """Hue rotation limited to ``selected`` (bool) and a source-hue window. Non-AI, exact elsewhere.

    Degrees stay float32. image_edit_tools.recolor uses float64 and can differ by a pixel.
    """
    for name, value, upper in (("from_hue", from_hue, 360), ("to_hue", to_hue, 360),
                               ("hue_range", hue_range, 180), ("min_saturation", min_saturation, 1)):
        _check_unit(name, value, 0, upper)
    hsv = local_pixels.rgb_to_hsv(rgb)
    degrees = hsv[..., 0].astype(np.float32) * (360 / 255)
    distance = np.abs((degrees - from_hue + 180) % 360 - 180)
    hit = selected & (distance <= hue_range) & (hsv[..., 1] / 255 >= min_saturation)
    shifted = np.round(((degrees + to_hue - from_hue) % 360) * (255 / 360)).astype(np.uint8)
    hsv[..., 0][hit] = shifted[hit]
    out = local_pixels.write_hsv_hits(rgb, hsv, hit, local_pixels.hsv_to_rgb_fromarray)
    return out, int(hit.sum())


def mask_composite(original, edited, selected_masks, feather=0):
    """Paste ``edited`` inside the white mask over ``original``; outside stays byte-exact."""
    if not (len(original) == len(edited) == len(selected_masks)):
        raise ValueError(f"Frame counts differ: original={len(original)} edited={len(edited)} masks={len(selected_masks)}")
    if isinstance(feather, bool) or not isinstance(feather, int) or feather < 0:
        raise ValueError("feather must be a non-negative integer")
    out, per_frame = [], []
    for o, e, m in zip(original, edited, selected_masks):
        if o.shape[:2] != e.shape[:2] or o.shape[:2] != m.shape[:2]:
            raise ValueError("original, edited and mask sizes must match; automatic resizing is not allowed")
        weight = local_pixels.feather_weight(m, feather)
        blended, stats = local_pixels.blend_inside_mask(o, e, weight)
        if stats["outside_changed_pixels"]:
            raise RuntimeError("Outside-mask preservation invariant failed")
        per_frame.append({"outside_pixels": stats["outside_pixels"],
                          "outside_changed_pixels": stats["outside_changed_pixels"],
                          "inside_pixels": stats["inside_pixels"],
                          "inside_mean_abs_rgb_delta": stats["inside_mean_abs_rgb_delta"]})
        out.append(blended)
    return out, per_frame


def outside_mask_drift(original, candidate, selected_masks):
    """Per-frame difference outside the mask for a candidate that was *not* recomposited."""
    rows = []
    for o, c, m in zip(original, candidate, selected_masks):
        outside = m == 0
        delta = np.abs(o[..., :3].astype(np.int16) - c[..., :3].astype(np.int16)).max(axis=2)[outside]
        rows.append({"mean_abs_max_channel": float(delta.mean()) if delta.size else 0.0,
                     "fraction_gt_8": float((delta > 8).mean()) if delta.size else 0.0})
    return rows


# ---------------------------------------------------------------- loop / first-frame measurements

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


# ---------------------------------------------------------------- prop master paste-back (green screen)

def green_screen(rgb):
    """Green-screen pixels: G > 180, R < 120, B < 120 (pipeline #00FF00 backgrounds after H.264/AI drift)."""
    x = rgb[..., :3]
    return (x[..., 1] > 180) & (x[..., 0] < 120) & (x[..., 2] < 120)


def prop_paste(source, edited, painted, grow=6, near=30, key="auto", tolerance=40.0, softness=40.0):
    """Paste a re-designed prop from an AI-edited still back onto the untouched source still.

    ``source``/``edited``: RGB arrays of the same size on a green screen. ``painted``: selected-white L
    array of the prop to replace. The selection is the painted area grown by ``grow`` plus the new prop's
    non-green pixels within ``near`` of the painting, minus source character pixels outside the grown
    painting (hands, grip). The new prop is chroma-keyed (unmix + despill) from the edited still and
    laid over the *source's* green, so the background matches the rest of the frame. Pixels with zero
    selection weight are byte-identical to ``source``.
    """
    from PIL import ImageFilter
    if source.shape != edited.shape or source.shape[:2] != painted.shape:
        raise ValueError("source, edited and mask must have the same size; automatic resizing is not allowed")
    for name, value, upper in (("grow", grow, 64), ("near", near, 256)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= upper:
            raise ValueError(f"{name} must be an integer 0..{upper}")
    paint_img = Image.fromarray(((painted > 127) * 255).astype(np.uint8))
    if not (painted > 127).any():
        raise ValueError("painted mask is empty")
    paint = np.asarray(paint_img.filter(ImageFilter.MaxFilter(2 * grow + 1))) > 127 if grow else painted > 127
    near_zone = np.asarray(paint_img.filter(ImageFilter.MaxFilter(2 * near + 1))) > 127 if near else paint
    src_green, ed_green = green_screen(source), green_screen(edited)
    if not src_green.any() or not ed_green.any():
        raise ValueError("prop-paste needs a green-screen background in both stills")
    sel = paint | (~ed_green & near_zone)
    sel &= ~(~src_green & ~paint)
    weight = Image.fromarray((sel * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    w = np.asarray(weight).astype(np.float32)[..., None] / 255.0
    bg = np.median(source[src_green][:, :3], axis=0).astype(np.float32)
    if key == "auto":
        key_rgb = np.median(edited[ed_green][:, :3], axis=0)
        key = "%02X%02X%02X" % tuple(int(round(v)) for v in key_rgb)
    rgba = chroma_alpha(edited, key=key, tolerance=tolerance, softness=softness, unmix=True, despill=True)
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    prop = rgba[..., :3].astype(np.float32) * a + bg * (1.0 - a)
    out = np.round(prop * w + source[..., :3].astype(np.float32) * (1.0 - w)).astype(np.uint8)
    zero = np.asarray(weight) == 0
    out[zero] = source[..., :3][zero]
    changed_outside = int(np.any(out[zero] != source[..., :3][zero], axis=1).sum())
    if changed_outside:
        raise RuntimeError("prop-paste preservation invariant failed")
    region_bg = (np.asarray(weight) > 0) & (a[..., 0] < 0.02)
    stats = {
        "key": key, "source_green_median": [float(v) for v in bg],
        "selected_pixels": int((np.asarray(weight) > 0).sum()),
        "outside_changed_pixels": changed_outside,
        "pasted_region_background_mean": [float(v) for v in out[region_bg].mean(axis=0)] if region_bg.any() else None,
        "pasted_region_background_std": [float(v) for v in out[region_bg].std(axis=0)] if region_bg.any() else None,
    }
    return out, np.asarray(weight), stats


# ---------------------------------------------------------------- manual region marking (video_layers bridge)

SEGMENT_MIN_WIDTH, SEGMENT_MAX_WIDTH = 256, 1280


def working_size(width, height, requested=None):
    """video_layers segment working canvas: even width 256..1280, aspect kept, even height."""
    target = requested or min(width, SEGMENT_MAX_WIDTH)
    target -= target % 2
    if not SEGMENT_MIN_WIDTH <= target <= SEGMENT_MAX_WIDTH:
        raise ValueError(f"working width must be even and within {SEGMENT_MIN_WIDTH}..{SEGMENT_MAX_WIDTH}")
    h = round(height * target / width)
    return target, h - h % 2


def editor_mask_to_l(image, size):
    """Simple Mask editor export (white paint on opaque black, RGBA) or any mask -> binary L at ``size``.

    Alpha is ignored on purpose (same rule as simple_mask_tool.core) so browsers cannot invert semantics.
    """
    gray = image.convert("RGB").convert("L")
    if gray.size != tuple(size):
        gray = gray.resize(tuple(size), Image.Resampling.NEAREST)
    return gray.point(lambda v: 255 if v > 127 else 0)


def _posix(path):
    return Path(path).resolve().as_posix()


def segment_plan(video, masks_by_frame, frame_count, fps, work, object_id=1):
    """Build a video_layers segment plan whose prompts are hand-painted masks."""
    if 0 not in masks_by_frame:
        raise ValueError("A frame-0 mask is required (video_layers needs a frame-0 prompt)")
    for frame in masks_by_frame:
        if not 0 <= frame < frame_count:
            raise ValueError(f"mask frame {frame} is outside 0..{frame_count - 1}")
    end = math.floor(frame_count / fps * 1000) / 1000.0
    return {"schema_version": 1, "operation": "segment", "video": _posix(video),
            "start": 0, "end": end, "width": work[0],
            "objects": [{"id": object_id, "prompts": [
                {"frame": f, "mask": _posix(masks_by_frame[f])} for f in sorted(masks_by_frame)]}]}


def mask_overlay_strip(frames, masks, picks, target, thumb=256):
    tiles = []
    for i in picks:
        x = frames[i][..., :3].astype(np.float32)
        sel = masks[i] > 127
        x[sel] = x[sel] * 0.45 + np.array([255, 0, 255], np.float32) * 0.55
        tiles.append(_label_tile(np.round(x).astype(np.uint8), f"frame {i}", thumb))
    canvas = Image.new("RGB", (thumb * len(tiles), max(t.height for t in tiles)), "#e5e5e5")
    for k, t in enumerate(tiles):
        canvas.paste(t, (k * thumb, 0))
    canvas.save(target, format="PNG")
    return target


# ---------------------------------------------------------------- CLI

def _cmd_alpha(args):
    frames, fps = read_frames(args.input)
    started = time.perf_counter()
    if args.command == "luma-alpha":
        rgba = [luma_alpha(f, args.black_point, args.white_point, args.gamma) for f in frames]
        params = {"black_point": args.black_point, "white_point": args.white_point, "gamma": args.gamma}
        key = None
    elif args.command == "chroma-alpha":
        rgba = [chroma_alpha(f, args.key, args.tolerance, args.softness, args.despill, args.unmix) for f in frames]
        params = {"key": args.key, "tolerance": args.tolerance, "softness": args.softness,
                  "despill": args.despill, "unmix": args.unmix}
        key = args.key
    else:
        rgba, _ = birefnet_alpha(frames, args.model_root, args.variant)
        params = {"variant": args.variant, "model_root": str(args.model_root), "temporal_model": False}
        key = args.key
    seconds = time.perf_counter() - started
    out = new_directory(args.output_dir)
    write_sequence(rgba, out / "frames")
    reference = read_frames(args.reference_alpha, mode="RGBA")[0] if args.reference_alpha else None
    report = {"schema_version": 1, "kind": f"vfx_{args.command.replace('-', '_')}", "status": "candidate",
              "input": file_record(args.input) if Path(args.input).is_file() else {"path": str(Path(args.input).resolve())},
              "parameters": params, "fps": fps or args.fps, "frames": len(rgba),
              "processing_seconds_total": round(seconds, 3),
              "processing_seconds_per_frame": round(seconds / len(rgba), 4),
              "metrics": alpha_metrics(rgba, key=key,
                                       reference_alpha=[r[..., 3] for r in reference] if reference else None),
              "alpha": "straight", "acceptance": "pending human review"}
    comparison_board(frames[len(frames) // 2], [(args.command.upper(), rgba[len(rgba) // 2])], out / "board_mid.png")
    save_json(out / "result.json", report)
    return report


def _cmd_metrics(args):
    frames, _ = read_frames(args.input, mode="RGBA")
    report = alpha_metrics(frames, key=args.key)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _cmd_board(args):
    original, _ = read_frames(args.original)
    index = args.frame if args.frame >= 0 else len(original) // 2
    candidates = []
    for item in args.candidate:
        label, _, path = item.partition("=")
        if not path:
            raise ValueError("--candidate must be LABEL=DIR")
        frames, _ = read_frames(path, mode="RGBA")
        candidates.append((label, frames[index]))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    if Path(args.output).exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")
    comparison_board(original[index], candidates, args.output, args.thumb)
    return {"status": "complete", "output": str(Path(args.output).resolve()), "frame": index}


def _cmd_pack(args):
    frames, _ = read_frames(args.input, mode="RGBA")
    out = new_directory(args.output_dir)
    result = {"schema_version": 1, "kind": "vfx_pack", "status": "candidate", "frames": len(frames), "outputs": {}}
    meta = sprite_sheet(frames, out / "sheet.png", args.columns, args.fps)
    result["outputs"]["sprite_sheet"] = {**file_record(out / "sheet.png"), "columns": meta["columns"], "rows": meta["rows"]}
    if args.apng:
        write_apng(frames, out / "anim.png", args.fps)
        result["outputs"]["apng"] = file_record(out / "anim.png")
    if args.webm:
        write_webm_alpha(frames, out / "anim.webm", args.fps, args.crf)
        decoded = read_webm_alpha(out / "anim.webm")
        alpha_err = [float(np.abs(d[..., 3].astype(np.int16) - f[..., 3].astype(np.int16)).mean())
                     for d, f in zip(decoded, frames)]
        result["outputs"]["webm_vp9_alpha"] = {**file_record(out / "anim.webm"), "decoded_frames": len(decoded),
                                               "decoded_alpha_mean_abs_error": float(np.mean(alpha_err)) if alpha_err else None,
                                               "note": "lossy yuva420p; decode with libvpx-vp9 to keep alpha"}
    save_json(out / "result.json", result)
    return result


def _cmd_sam_to_edit(args):
    out = new_directory(args.output_dir)
    for p in _png_paths(args.masks):
        with Image.open(p) as im:
            Image.fromarray(sam_to_edit_mask(np.asarray(im.convert("L"))), "RGBA").save(out / p.name)
    return {"status": "complete", "output_dir": str(out)}


def _cmd_mask_recolor(args):
    frames, fps = read_frames(args.input)
    masks = read_masks(args.masks, len(frames), (frames[0].shape[1], frames[0].shape[0]))
    edited, hits = [], []
    for f, m in zip(frames, masks):
        e, n = masked_hue_rotate(f, m >= args.threshold, args.from_hue, args.to_hue, args.hue_range, args.min_saturation)
        edited.append(e)
        hits.append(n)
    composed, per_frame = mask_composite(frames, edited, masks, args.feather)
    out = new_directory(args.output_dir)
    write_sequence(composed, out / "frames")
    report = {"schema_version": 1, "kind": "vfx_mask_recolor", "status": "candidate", "model_generation": False,
              "fps": fps, "frames": len(composed), "matched_pixels_per_frame": hits,
              "outside_changed_pixels_total": sum(r["outside_changed_pixels"] for r in per_frame),
              "per_frame": per_frame, "acceptance": "pending human review"}
    save_json(out / "result.json", report)
    return report


def _cmd_mask_composite(args):
    original, fps = read_frames(args.original)
    edited, _ = read_frames(args.edited)
    masks = read_masks(args.masks, len(original), (original[0].shape[1], original[0].shape[0]))
    if len(edited) != len(original):
        raise ValueError(f"edited has {len(edited)} frames, original has {len(original)}")
    if edited[0].shape != original[0].shape:
        raise ValueError(f"edited frame size {edited[0].shape} differs from original {original[0].shape}")
    drift = outside_mask_drift(original, edited, masks)
    composed, per_frame = mask_composite(original, edited, masks, args.feather)
    out = new_directory(args.output_dir)
    write_sequence(composed, out / "frames")
    report = {"schema_version": 1, "kind": "vfx_mask_composite", "status": "candidate", "fps": fps,
              "frames": len(composed), "feather": args.feather,
              "edited_outside_mask_drift_before_composite": drift,
              "outside_changed_pixels_total": sum(r["outside_changed_pixels"] for r in per_frame),
              "per_frame": per_frame, "acceptance": "pending human review"}
    save_json(out / "result.json", report)
    return report


def _cmd_loop(args):
    frames, fps = read_frames(args.video)
    reference = np.asarray(Image.open(args.reference).convert("RGB")) if args.reference else None
    report, ref = loop_metrics(frames, reference, args.key)
    out = new_directory(args.output_dir)
    Image.fromarray(frames[0]).save(out / "first.png")
    Image.fromarray(frames[-1]).save(out / "last.png")
    if ref is not None:
        Image.fromarray(ref).save(out / "reference_canvas.png")
    report = {"schema_version": 1, "kind": "vfx_loop_metrics", "video": file_record(args.video),
              "reference": file_record(args.reference) if args.reference else None, "fps": fps, **report,
              "note": "Pixel metrics locate candidate seams; they do not judge identity or motion quality"}
    save_json(out / "loop_metrics.json", report)
    return report


def _frame_list(text, count):
    picks = sorted({int(x) for x in text.split(",") if x.strip()})
    for i in picks:
        if not 0 <= i < count:
            raise ValueError(f"frame {i} is outside 0..{count - 1}")
    return picks


def _cmd_keyframes(args):
    frames, fps = read_frames(args.video)
    h, w = frames[0].shape[:2]
    work = working_size(w, h, args.width)
    picks = _frame_list(args.frames, len(frames))
    out = new_directory(args.output_dir)
    written = []
    for i in picks:
        im = Image.fromarray(frames[i])
        if im.size != work:
            im = im.resize(work, Image.Resampling.LANCZOS)
        im.save(out / f"frame_{i:05d}.png")
        written.append(str(out / f"frame_{i:05d}.png"))
    report = {"status": "complete", "video": str(Path(args.video).resolve()), "frames": len(frames), "fps": fps,
              "working_size": list(work), "keyframes": written,
              "next": "open each keyframe with mask_session.py create; paint the object white"}
    save_json(out / "keyframes.json", report)
    return report


def _cmd_segment_plan(args):
    frames, fps = read_frames(args.video)
    h, w = frames[0].shape[:2]
    work = working_size(w, h, args.width)
    out = new_directory(args.output_dir)
    masks = {}
    for item in args.mask:
        frame, _, path = item.partition("=")
        if not path:
            raise ValueError("--mask must be FRAME=PATH")
        frame = int(frame)
        with Image.open(path) as im:
            converted = editor_mask_to_l(im, work)
        if not np.asarray(converted).any():
            raise ValueError(f"mask for frame {frame} is empty")
        target = out / f"seed_mask_{frame:05d}.png"
        converted.save(target)
        masks[frame] = target
    plan = segment_plan(args.video, masks, len(frames), fps or 24.0, work, args.object_id)
    (out / "segment_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "complete", "plan": str(out / "segment_plan.json"), "working_size": list(work)}


def _cmd_unpack_masks(args):
    import io
    import zipfile
    source = Path(args.segment_dir)
    zpath = source / "layers.zip" if source.is_dir() else source
    prefix = f"masks/object-{args.object_id:03d}/"
    size = None
    if args.video:
        frames, _ = read_frames(args.video)
        size = (frames[0].shape[1], frames[0].shape[0])
    out = new_directory(args.output_dir)
    with zipfile.ZipFile(zpath) as archive:
        names = sorted(n for n in archive.namelist() if n.startswith(prefix) and n.lower().endswith(".png"))
        if not names:
            raise ValueError(f"no masks for object {args.object_id} in {zpath}")
        for k, n in enumerate(names):
            with Image.open(io.BytesIO(archive.read(n))) as im:
                m = im.convert("L")
            if size and m.size != size:
                m = m.resize(size, Image.Resampling.NEAREST)
            m.save(out / f"{k:05d}.png")
    return {"status": "complete", "output": str(out), "masks": len(names)}


def _cmd_mask_preview(args):
    frames, _ = read_frames(args.video)
    masks = read_masks(args.masks, len(frames), (frames[0].shape[1], frames[0].shape[0]))
    n = len(frames)
    picks = _frame_list(args.frames, n) if args.frames else sorted({0, n // 4, n // 2, 3 * n // 4, n - 1})
    if Path(args.output).exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    mask_overlay_strip(frames, masks, picks, args.output)
    return {"status": "complete", "output": str(Path(args.output).resolve()), "frames": picks}



def _cmd_prop_paste(args):
    def rgb(path):
        with Image.open(path) as im:
            return np.asarray(im.convert("RGB"))
    with Image.open(args.mask) as im:
        painted = np.asarray(im.convert("RGB").convert("L"))  # editor export: white paint on black, alpha ignored
    out, weight, stats = prop_paste(rgb(args.source), rgb(args.edited), painted, args.grow, args.near,
                                    args.key, args.tolerance, args.softness)
    directory = new_directory(args.output_dir)
    Image.fromarray(out).save(directory / "composited.png")
    Image.fromarray(weight).save(directory / "selection.png")
    report = {"schema_version": 1, "kind": "vfx_prop_paste", "status": "candidate",
              "inputs": {"source": file_record(args.source), "edited": file_record(args.edited), "mask": file_record(args.mask)},
              "parameters": {"grow": args.grow, "near": args.near, "tolerance": args.tolerance, "softness": args.softness},
              **stats, "outputs": [file_record(directory / "composited.png"), file_record(directory / "selection.png")],
              "acceptance": "pending human review; this only replaces the prop region, it does not judge the design"}
    save_json(directory / "result.json", report)
    return report


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def alpha_common(p):
        p.add_argument("--input", required=True, help="MP4 or directory of PNG frames")
        p.add_argument("--output-dir", required=True, help="New directory; existing directories are rejected")
        p.add_argument("--reference-alpha", help="Optional PNG RGBA sequence directory with ground-truth alpha")
        p.add_argument("--fps", type=float, default=24.0, help="FPS recorded for PNG-directory input")

    p = sub.add_parser("luma-alpha", help="Black-background effect -> straight RGBA PNG sequence")
    alpha_common(p)
    p.add_argument("--black-point", type=float, default=0.0, help="0..1; background level mapped to alpha 0")
    p.add_argument("--white-point", type=float, default=1.0)
    p.add_argument("--gamma", type=float, default=1.0)
    p = sub.add_parser("chroma-alpha", help="Green-screen key (video_composite ramp) -> RGBA PNG sequence")
    alpha_common(p)
    p.add_argument("--key", default="00FF00")
    p.add_argument("--tolerance", type=float, default=60.0)
    p.add_argument("--softness", type=float, default=40.0)
    p.add_argument("--despill", action="store_true")
    p.add_argument("--unmix", action="store_true", help="Remove key colour from semi-transparent pixels")
    p = sub.add_parser("birefnet-alpha", help="Per-frame BiRefNet matte (CUDA, local weights only)")
    alpha_common(p)
    p.add_argument("--model-root", required=True, type=Path)
    p.add_argument("--variant", default="general")
    p.add_argument("--key", help="Optional key colour used only for the fringe diagnostic")
    p = sub.add_parser("metrics", help="Print alpha metrics for an RGBA PNG sequence")
    p.add_argument("--input", required=True)
    p.add_argument("--key")
    p = sub.add_parser("board", help="Original vs RGBA candidates on alpha/dark/light")
    p.add_argument("--original", required=True)
    p.add_argument("--candidate", action="append", required=True, help="LABEL=RGBA_PNG_DIR")
    p.add_argument("--frame", type=int, default=-1, help="Frame index; default middle")
    p.add_argument("--thumb", type=int, default=320)
    p.add_argument("--output", required=True)
    p = sub.add_parser("pack", help="RGBA PNG sequence -> sprite sheet (+JSON), optional APNG/WebM VP9 alpha")
    p.add_argument("--input", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--columns", type=int)
    p.add_argument("--fps", type=float, default=24.0)
    p.add_argument("--apng", action="store_true")
    p.add_argument("--webm", action="store_true")
    p.add_argument("--crf", type=int, default=18)
    p = sub.add_parser("sam-to-edit-mask", help="SAM white=selected L masks -> image_edit alpha masks (0=edit)")
    p.add_argument("--masks", required=True)
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("mask-recolor", help="Hue rotation inside SAM masks; outside stays byte-exact")
    p.add_argument("--input", required=True)
    p.add_argument("--masks", required=True, help="Directory of L masks, white=selected, one per frame")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--from-hue", type=float, required=True)
    p.add_argument("--to-hue", type=float, required=True)
    p.add_argument("--hue-range", type=float, default=45.0)
    p.add_argument("--min-saturation", type=float, default=0.12)
    p.add_argument("--threshold", type=int, default=128)
    p.add_argument("--feather", type=int, default=0)
    p = sub.add_parser("mask-composite", help="Paste an edited video inside SAM masks over the original")
    p.add_argument("--original", required=True)
    p.add_argument("--edited", required=True)
    p.add_argument("--masks", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--feather", type=int, default=0)
    p = sub.add_parser("loop-metrics", help="First frame vs reference, last vs first, loop seam")
    p.add_argument("--video", required=True)
    p.add_argument("--reference")
    p.add_argument("--key", help="Background key colour used to crop a subject ROI, e.g. 00FF00")
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("keyframes", help="Extract frames (video_layers working size) for hand-painted object masks")
    p.add_argument("--video", required=True)
    p.add_argument("--frames", default="0", help="Comma list, e.g. 0,24 (frame 0 is required later)")
    p.add_argument("--width", type=int, help="Working width (even, 256..1280); default source width capped at 1280")
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("segment-plan", help="Hand-painted masks -> video_layers segment plan (mask prompts)")
    p.add_argument("--video", required=True)
    p.add_argument("--mask", action="append", required=True, help="FRAME=PATH of a painted mask (white = object)")
    p.add_argument("--object-id", type=int, default=1)
    p.add_argument("--width", type=int)
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("unpack-masks", help="video_layers layers.zip -> per-frame L masks (optionally at source size)")
    p.add_argument("--segment-dir", required=True, help="video_layers run output dir or its layers.zip")
    p.add_argument("--object-id", type=int, default=1)
    p.add_argument("--video", help="Resize masks (nearest) to this video's size")
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("mask-preview", help="Magenta mask overlay strip for human confirmation")
    p.add_argument("--video", required=True)
    p.add_argument("--masks", required=True)
    p.add_argument("--frames", help="Comma list; default 5 evenly spaced frames")
    p.add_argument("--output", required=True)
    p = sub.add_parser("prop-paste", help="Paste a re-designed prop from an edited still onto the source green screen")
    p.add_argument("--source", required=True, help="Original still (green screen)")
    p.add_argument("--edited", required=True, help="AI-edited still with the new prop (e.g. flux2_edit output)")
    p.add_argument("--mask", required=True, help="Painted prop mask, white = prop (mask_session mask_editor.png)")
    p.add_argument("--grow", type=int, default=6)
    p.add_argument("--near", type=int, default=30, help="How far (px) the new prop may extend beyond the painting")
    p.add_argument("--key", default="auto", help="Edited still's green, RRGGBB or auto (median)")
    p.add_argument("--tolerance", type=float, default=40.0)
    p.add_argument("--softness", type=float, default=40.0)
    p.add_argument("--output-dir", required=True)
    return parser


COMMANDS = {"luma-alpha": _cmd_alpha, "chroma-alpha": _cmd_alpha, "birefnet-alpha": _cmd_alpha,
            "metrics": _cmd_metrics, "board": _cmd_board, "pack": _cmd_pack,
            "sam-to-edit-mask": _cmd_sam_to_edit, "mask-recolor": _cmd_mask_recolor,
            "mask-composite": _cmd_mask_composite, "loop-metrics": _cmd_loop,
            "keyframes": _cmd_keyframes, "segment-plan": _cmd_segment_plan,
            "unpack-masks": _cmd_unpack_masks, "mask-preview": _cmd_mask_preview,
            "prop-paste": _cmd_prop_paste}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = COMMANDS[args.command](args)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.command != "metrics":
        print(json.dumps({"status": result.get("status", "complete"),
                          "output": result.get("output") or getattr(args, "output_dir", None)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
