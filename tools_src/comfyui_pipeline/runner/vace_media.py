"""VACE 局部重繪的本機媒體處理:讀片/遮罩、裁切工作區、無損上傳片段與貼回原片。

遮罩契約沿用 video_layers segment:``L`` PNG,白色=要重畫,黑色=保留。和圖片 inpaint 的
alpha 遮罩(0=編修)方向相反,這裡不接受那種格式。貼回後遮罩(擴張+羽化範圍)外的像素
逐 byte 等於來源解碼結果;MP4 交付另經 H.264 編碼,不是無損。

PR 3.3 從 ``comfyui_pipeline/video_edit_media.py`` 搬過來,原模組保留為薄轉接(``generate.py video_inpaint``
仍然用它)。template runner 的 ``vace_work_area``／``paste_back``／``qa_outside_mask_unchanged`` 步驟
透過 :func:`prepare_work_area`、:func:`composite`、:func:`outside_mask_changes` 使用同一份實作。
需要 numpy、PyAV、Pillow(ComfyUI 的 Python 環境都有)。
"""
import io
import math
import os
import zipfile

from ..video_catalog import VACE_MAX_FRAMES, VACE_MAX_PIXELS, VIDEO_FPS, VIDEO_FPS_TOLERANCE
import local_pixels

ALIGN = 16
MIN_SIDE = 128


def _np():
    import numpy as np
    return np


def read_video_frames(path):
    """Decode every frame as RGB uint8; returns (frames, fps)."""
    frames, fps = local_pixels.decode_video_frames(path, "RGB")
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


def _gray_mask(im):
    """Return (ok, L array). Accept L/1 and R=G=B RGB (e.g. SAM3 SaveImage); reject alpha modes and colour."""
    arr = local_pixels.decode_selected_white_mask(im)
    if arr is None:
        return False, None
    return True, arr


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
                items.append((n, im.mode, im.size) + _gray_mask(im))
    elif zipfile.is_zipfile(source):
        prefix = f"masks/object-{int(object_id):03d}/"
        with zipfile.ZipFile(source) as archive:
            names = sorted(n for n in archive.namelist() if n.startswith(prefix) and n.lower().endswith(".png"))
            if not names:
                raise ValueError(f"{source} 沒有物件 {object_id} 的遮罩（找 {prefix}*.png）")
            for n in names:
                with Image.open(io.BytesIO(archive.read(n))) as im:
                    items.append((n, im.mode, im.size) + _gray_mask(im))
    else:
        raise ValueError(f"--masks 必須是遮罩 PNG 資料夾或 video_layers 的 layers.zip: {source}")
    if len(items) != count:
        raise ValueError(f"遮罩數量 {len(items)} 和影片幀數 {count} 不一致；不會自動補幀或重採樣")
    masks = []
    for name, mode, msize, ok, arr in items:
        if not ok:
            raise ValueError(f"遮罩 {name} 必須是白色=選取的灰階 PNG（L，或 R=G=B 的 RGB），目前 mode={mode}（圖片 inpaint 的 alpha 遮罩方向相反，不能直接用）")
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
    return local_pixels.encode_video_frames(
        frames, path, codec="ffv1", pix_fmt="bgr0", ndarray_format="rgb24",
        fps=fps, container_format="matroska")


def paste_weight(grown_mask, feather):
    """貼回權重(uint8,0=完全保留來源):擴張遮罩再向外 ``feather`` 像素,邊緣高斯羽化。"""
    return local_pixels.feather_weight(grown_mask, feather)


def paste_back(source_frames, raw_frames, crop, grown_masks, feather=4):
    """Resize the raw crop back, then blend only inside grown(+feather) masks.

    Returns (frames, per_frame_report). Pixels outside the dilated mask are copied from
    the source and verified byte-identical.
    """
    from PIL import Image
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
        weight = paste_weight(g, feather)
        blended, stats = local_pixels.blend_inside_mask(src, edited, weight)
        if stats["outside_changed_pixels"]:
            raise RuntimeError("貼回後遮罩外像素被改動，已停止")
        report.append({
            "edited_pixels": stats["inside_pixels"],
            "outside_changed_pixels": 0,
            "edited_mean_abs_rgb_delta": stats["inside_mean_abs_rgb_delta"],
        })
        out.append(blended)
    return out, report


def encode_mp4(frames, path, fps=VIDEO_FPS, crf=18):
    return local_pixels.encode_video_frames(
        frames, path, codec="libx264", pix_fmt="yuv420p", ndarray_format="rgb24",
        fps=fps, options={"crf": str(crf)}, contiguous=True)


def write_composited(frames, out_dir):
    """貼回結果寫成 ``frames/00000.png…``(無損母帶)與 ``composited.mp4``(H.264 crf 18,不是無損)。"""
    from PIL import Image
    out_dir = os.fspath(out_dir)
    frame_dir = os.path.join(out_dir, FRAMES_DIR)
    os.makedirs(frame_dir)
    paths = []
    for i, f in enumerate(frames):
        path = os.path.join(frame_dir, f"{i:05d}.png")
        Image.fromarray(f).save(path)
        paths.append(path)
    mp4 = encode_mp4(frames, os.path.join(out_dir, COMPOSITED_MP4))
    return {"frames": paths, "mp4": mp4}


# ---------- template runner 的步驟(PR 3.3) ----------

CONTROL_CLIP = "control.mkv"
MASK_CLIP = "mask.mkv"
FRAMES_DIR = "frames"
COMPOSITED_MP4 = "composited.mp4"


def _require_empty(folder):
    folder = os.fspath(folder)
    if os.path.isdir(folder) and os.listdir(folder):
        raise FileExistsError(f"輸出資料夾不是空的,不覆寫: {folder}")
    os.makedirs(folder, exist_ok=True)
    return folder


def prepare_work_area(video, masks, out_dir, *, mask_object=1, grow=8, pad=48, crop=None, mode="keep"):
    """``vace_work_area`` 步驟。順序和 ``generate.py video_inpaint`` 的 prepare 相同,寫出兩支 FFV1 工作片段。

    回傳 (info, state)。info 是可以寫進 manifest 的量測值與檔案路徑;state 是給 :func:`composite` 與
    :func:`outside_mask_changes` 用的來源影格、擴張後遮罩等陣列,不寫進 manifest。
    """
    frames, fps = read_video_frames(video)
    validate_source(frames, fps)
    height, width = frames[0].shape[:2]
    mask_list = read_masks(masks, len(frames), (width, height), mask_object)
    grown = grow_masks(mask_list, grow)
    work_crop = compute_crop(grown, (width, height), pad, tuple(crop) if crop is not None else None)
    size = processing_size(work_crop[2] - work_crop[0], work_crop[3] - work_crop[1])
    controls, mask_clip = build_work_clips(frames, grown, work_crop, size, mode)
    length = vace_length(len(frames))
    out_dir = _require_empty(out_dir)
    control = write_lossless_video(controls, os.path.join(out_dir, CONTROL_CLIP))
    mask = write_lossless_video(mask_clip, os.path.join(out_dir, MASK_CLIP))
    info = {"frames": len(frames), "fps": fps, "source_width": int(width), "source_height": int(height),
            "crop": [int(v) for v in work_crop], "width": size[0], "height": size[1], "length": length,
            "mode": mode, "grow": grow, "pad": pad, "mask_object": mask_object,
            "control": os.path.abspath(control), "mask": os.path.abspath(mask)}
    state = {"frames": frames, "grown": grown, "crop": work_crop, "size": size, "length": length}
    return info, state


def composite(state, raw_video, out_dir, *, feather=4):
    """``paste_back`` 步驟:VACE 工作區輸出縮回原尺寸,只在擴張＋羽化遮罩內貼回來源,寫 PNG 序列與 MP4。

    raw 影片比來源長時(VACE 長度是 4k+1)只用前面和來源一樣多的幀。遮罩外改動時 :func:`paste_back` 會丟錯。
    """
    raw, _ = read_video_frames(raw_video)
    frames = state["frames"]
    composed, per_frame = paste_back(frames, raw[:len(frames)], state["crop"], state["grown"], feather)
    written = write_composited(composed, _require_empty(out_dir))
    return {"raw_frames": len(raw), "used_frames": len(frames), "feather": feather,
            "frames": written["frames"], "mp4": os.path.abspath(written["mp4"]),
            "outside_changed_pixels_total": sum(r["outside_changed_pixels"] for r in per_frame),
            "per_frame": per_frame}


def outside_mask_changes(state, frame_paths, feather=4):
    """``qa_outside_mask_unchanged`` 步驟:重新讀寫出的 PNG,逐幀數遮罩(擴張＋羽化)外和來源不同的像素數。"""
    from PIL import Image
    np = _np()
    frames, grown = state["frames"], state["grown"]
    if len(frame_paths) != len(frames):
        raise ValueError(f"貼回結果有 {len(frame_paths)} 幀,來源有 {len(frames)} 幀")
    counts = []
    for src, g, path in zip(frames, grown, frame_paths):
        with Image.open(path) as im:
            got = np.asarray(im.convert("RGB"))
        if got.shape != src.shape:
            raise ValueError(f"{path} 尺寸 {got.shape[1]}x{got.shape[0]} 和來源 {src.shape[1]}x{src.shape[0]} 不同")
        outside = paste_weight(g, feather) == 0
        counts.append(int(np.any(got[outside] != src[outside], axis=1).sum()))
    return counts
