"""video_inpaint 的本機媒體處理:讀片/遮罩、裁切工作區、無損上傳片段與貼回原片。

遮罩契約沿用 video_layers segment:``L`` PNG,白色=要重畫,黑色=保留。和圖片 inpaint 的
alpha 遮罩(0=編修)方向相反,這裡不接受那種格式。貼回後遮罩(擴張+羽化範圍)外的像素
逐 byte 等於來源解碼結果;MP4 交付另經 H.264 編碼,不是無損。
"""
import io
import math
import os
import zipfile
from fractions import Fraction

from .video_catalog import VACE_MAX_FRAMES, VACE_MAX_PIXELS, VIDEO_FPS, VIDEO_FPS_TOLERANCE

ALIGN = 16
MIN_SIDE = 128


def _np():
    import numpy as np
    return np


def read_video_frames(path):
    """Decode every frame as RGB uint8; returns (frames, fps)."""
    import av
    np = _np()
    frames = []
    with av.open(os.fspath(path)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate) if stream.average_rate else None
        for frame in container.decode(video=0):
            frames.append(np.asarray(frame.to_image().convert("RGB")))
    if not frames:
        raise ValueError(f"影片沒有可解碼影格: {path}")
    return frames, fps


def validate_source(frames, fps):
    if fps is None or not math.isclose(fps, float(VIDEO_FPS), rel_tol=0.0, abs_tol=VIDEO_FPS_TOLERANCE):
        raise ValueError(f"video_inpaint --video 必須接近 {VIDEO_FPS} FPS，目前是 {fps}；產線不會靜默重採樣")
    if len(frames) > VACE_MAX_FRAMES:
        raise ValueError(
            f"video_inpaint 一次最多 {VACE_MAX_FRAMES} 幀（VACE 訓練長度），目前 {len(frames)} 幀；請先拆段"
        )
    if len(frames) < 5:
        raise ValueError("video_inpaint 至少需要 5 幀")


def read_masks(source, count, size, object_id=1):
    """Read selected-white masks from a PNG directory or a video_layers ``layers.zip``."""
    from PIL import Image
    np = _np()
    source = os.fspath(source)
    items = []
    if os.path.isdir(source):
        names = sorted(n for n in os.listdir(source) if n.lower().endswith(".png"))
        for n in names:
            with Image.open(os.path.join(source, n)) as im:
                items.append((n, im.mode, im.size, np.asarray(im.convert("L"))))
    elif zipfile.is_zipfile(source):
        prefix = f"masks/object-{int(object_id):03d}/"
        with zipfile.ZipFile(source) as archive:
            names = sorted(n for n in archive.namelist() if n.startswith(prefix) and n.lower().endswith(".png"))
            if not names:
                raise ValueError(f"{source} 沒有物件 {object_id} 的遮罩（找 {prefix}*.png）")
            for n in names:
                with Image.open(io.BytesIO(archive.read(n))) as im:
                    items.append((n, im.mode, im.size, np.asarray(im.convert("L"))))
    else:
        raise ValueError(f"--masks 必須是遮罩 PNG 資料夾或 video_layers 的 layers.zip: {source}")
    if len(items) != count:
        raise ValueError(f"遮罩數量 {len(items)} 和影片幀數 {count} 不一致；不會自動補幀或重採樣")
    masks = []
    for name, mode, msize, arr in items:
        if mode not in ("L", "1"):
            raise ValueError(f"遮罩 {name} 必須是白色=選取的 L 灰階 PNG，目前 mode={mode}（圖片 inpaint 的 alpha 遮罩方向相反，不能直接用）")
        if tuple(msize) != tuple(size):
            raise ValueError(f"遮罩 {name} 尺寸 {msize} 和影片 {size} 不同；不會自動縮放")
        masks.append(arr)
    if not any((m > 127).any() for m in masks):
        raise ValueError("所有遮罩都是空的，沒有要重畫的區域")
    return masks


def grow_masks(masks, pixels):
    """Binary threshold at 128, then square dilation by ``pixels``."""
    from PIL import Image, ImageFilter
    np = _np()
    out = []
    for m in masks:
        binary = ((m > 127) * 255).astype("uint8")
        if pixels:
            binary = np.asarray(Image.fromarray(binary).filter(ImageFilter.MaxFilter(2 * pixels + 1)))
        out.append(binary)
    return out


def _fit_span(lo, hi, limit):
    """Grow [lo, hi) to a multiple of ALIGN inside [0, limit)."""
    size = max(MIN_SIDE, hi - lo)
    size = min(int(math.ceil(size / ALIGN)) * ALIGN, (limit // ALIGN) * ALIGN)
    center = (lo + hi) / 2.0
    start = int(round(center - size / 2.0))
    start = max(0, min(start, limit - size))
    return start, start + size


def compute_crop(grown_masks, frame_size, pad=48, explicit=None):
    """Union bbox of grown masks plus ``pad``, snapped to multiples of 16 within the frame."""
    np = _np()
    width, height = frame_size
    if explicit is not None:
        x0, y0, x1, y1 = explicit
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError(f"--crop {explicit} 超出畫面 {width}x{height}")
    else:
        union = np.zeros((height, width), dtype=bool)
        for g in grown_masks:
            union |= g > 0
        ys, xs = np.nonzero(union)
        x0, y0 = int(xs.min()) - pad, int(ys.min()) - pad
        x1, y1 = int(xs.max()) + 1 + pad, int(ys.max()) + 1 + pad
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(width, x1), min(height, y1)
    cx0, cx1 = _fit_span(x0, x1, width)
    cy0, cy1 = _fit_span(y0, y1, height)
    crop = (cx0, cy0, cx1, cy1)
    for g in grown_masks:
        outside = g.copy()
        outside[cy0:cy1, cx0:cx1] = 0
        if outside.any():
            raise ValueError(f"擴張後的遮罩超出工作區 {crop}；請放大 --crop 或減少 --grow")
    return crop


def processing_size(crop_width, crop_height, max_pixels=VACE_MAX_PIXELS):
    """Largest 16-aligned size with the crop's aspect and at most ``max_pixels`` (never upscales)."""
    scale = min(1.0, math.sqrt(max_pixels / float(crop_width * crop_height)))
    w = max(ALIGN, int(crop_width * scale) // ALIGN * ALIGN)
    h = max(ALIGN, int(crop_height * scale) // ALIGN * ALIGN)
    return w, h


def vace_length(frame_count):
    """WanVaceToVideo length is 4k+1; the node pads extra control frames grey with mask 1."""
    return int(math.ceil((frame_count - 1) / 4.0)) * 4 + 1


def build_work_clips(frames, grown_masks, crop, size, mode):
    """Crop/resize control frames and masks to the processing size.

    ``replace`` blacks out the masked area (official VACE inpainting template); ``keep`` leaves
    the source pixels inside the mask as guidance.
    """
    from PIL import Image
    np = _np()
    if mode not in ("keep", "replace"):
        raise ValueError(f"未知 --mode {mode!r}")
    x0, y0, x1, y1 = crop
    controls, masks = [], []
    for f, g in zip(frames, grown_masks):
        c = Image.fromarray(f[y0:y1, x0:x1])
        m = Image.fromarray(g[y0:y1, x0:x1])
        if c.size != tuple(size):
            c = c.resize(size, Image.Resampling.LANCZOS)
            m = m.resize(size, Image.Resampling.NEAREST)
        c, m = np.asarray(c).copy(), np.asarray(m)
        if mode == "replace":
            c[m > 0] = 0
        controls.append(c)
        masks.append(np.repeat(m[..., None], 3, axis=2))
    return controls, masks


def write_lossless_video(frames, path, fps=VIDEO_FPS):
    """FFV1 RGB in Matroska: decodes back to identical RGB bytes."""
    import av
    path = os.fspath(path)
    h, w = frames[0].shape[:2]
    with av.open(path, "w", format="matroska") as container:
        stream = container.add_stream("ffv1", rate=Fraction(fps).limit_denominator(1001))
        stream.width, stream.height, stream.pix_fmt = w, h, "bgr0"
        for f in frames:
            for packet in stream.encode(av.VideoFrame.from_ndarray(f, format="rgb24")):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def paste_back(source_frames, raw_frames, crop, grown_masks, feather=4):
    """Resize the raw crop back, then blend only inside grown(+feather) masks.

    Returns (frames, per_frame_report). Pixels outside the dilated mask are copied from
    the source and verified byte-identical.
    """
    from PIL import Image, ImageFilter
    np = _np()
    if len(raw_frames) < len(source_frames):
        raise ValueError(f"VACE 輸出只有 {len(raw_frames)} 幀，少於來源 {len(source_frames)} 幀")
    x0, y0, x1, y1 = crop
    crop_size = (x1 - x0, y1 - y0)
    out, report = [], []
    for src, raw, g in zip(source_frames, raw_frames, grown_masks):
        patch = Image.fromarray(raw)
        if patch.size != crop_size:
            patch = patch.resize(crop_size, Image.Resampling.LANCZOS)
        edited = src.copy()
        edited[y0:y1, x0:x1] = np.asarray(patch)[..., :3]
        weight = g
        if feather:
            grown = Image.fromarray(g).filter(ImageFilter.MaxFilter(2 * feather + 1))
            blurred = np.asarray(grown.filter(ImageFilter.GaussianBlur(feather / 2.0)))
            weight = np.where(np.asarray(grown) > 0, blurred, 0).astype("uint8")
        w = weight.astype("float32")[..., None] / 255.0
        blended = np.round(edited.astype("float32") * w + src.astype("float32") * (1.0 - w)).astype("uint8")
        outside = weight == 0
        blended[outside] = src[outside]
        changed_outside = int(np.any(blended[outside] != src[outside], axis=1).sum())
        if changed_outside:
            raise RuntimeError("貼回後遮罩外像素被改動，已停止")
        inside = ~outside
        delta = np.abs(blended.astype("int16") - src.astype("int16"))
        report.append({
            "edited_pixels": int(inside.sum()),
            "outside_changed_pixels": 0,
            "edited_mean_abs_rgb_delta": float(delta[inside].mean()) if inside.any() else 0.0,
        })
        out.append(blended)
    return out, report


def encode_mp4(frames, path, fps=VIDEO_FPS, crf=18):
    import av
    path = os.fspath(path)
    h, w = frames[0].shape[:2]
    with av.open(path, "w") as container:
        stream = container.add_stream("libx264", rate=Fraction(fps).limit_denominator(1001))
        stream.width, stream.height, stream.pix_fmt = w, h, "yuv420p"
        stream.options = {"crf": str(crf)}
        for f in frames:
            for packet in stream.encode(av.VideoFrame.from_ndarray(_np().ascontiguousarray(f), format="rgb24")):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path
