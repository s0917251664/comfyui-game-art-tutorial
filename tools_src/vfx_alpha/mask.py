"""遮罩：選取白的讀取、貼回、道具貼回，以及 video_layers 的手繪起手。"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

import local_pixels

from .media import _png_paths
from .pixel import chroma_alpha
from .qa import _label_tile


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

def sam_to_edit_mask(selected_l):
    """SAM ``L`` mask (255 = selected) -> image_edit_tools RGBA mask (alpha 0 = edit)."""
    alpha = 255 - np.asarray(selected_l, dtype=np.uint8)
    out = np.zeros(alpha.shape + (4,), dtype=np.uint8)
    out[..., :3] = 255
    out[..., 3] = alpha
    return out

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
