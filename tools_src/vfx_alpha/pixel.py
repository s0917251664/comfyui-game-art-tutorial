"""像素：去背、色相旋轉、疊色。BiRefNet 仍呼叫 repo 內的 benchmark_birefnet。"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

import local_pixels


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

def over(rgba, background):
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    bg = np.empty(rgba.shape[:2] + (3,), dtype=np.float32)
    bg[...] = background
    return np.round(rgba[..., :3].astype(np.float32) * a + bg * (1.0 - a)).astype(np.uint8)

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
