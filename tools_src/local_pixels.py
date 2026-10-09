"""本機像素與 PyAV 的單一實作。

``vfx_alpha_tools``、``image_edit_tools``、``runner/vace_media`` 都呼叫這裡。
色相公式不在這裡:image_edit 用 float64 度數、vfx 用 float32,部分色相會差一個以上的 byte,
所以公式留在呼叫端。這裡只負責讀成 HSV、把命中像素寫回,以及遮罩解碼、遮罩內貼回、影片讀寫。

遮罩語意(呼叫端的錯誤訊息各自保留):白=重畫,接受 L/1 與 R=G=B 的 RGB,拒絕 RGBA 與彩色。
"""
from __future__ import annotations


def _np():
    import numpy as np
    return np


def rgb_to_hsv(rgb):
    """uint8 RGB(或帶更多通道,只用前三個)→ HSV uint8 複本。"""
    from PIL import Image
    np = _np()
    image = Image.fromarray(np.ascontiguousarray(rgb[..., :3]))
    return np.asarray(image.convert("HSV")).copy()


def hsv_to_rgb_fromarray(hsv):
    """vfx 的 HSV→RGB(``Image.fromarray``)。和 frombytes 在抽樣上相同,仍分開以免改到呼叫端。"""
    from PIL import Image
    np = _np()
    return np.asarray(Image.fromarray(hsv, "HSV").convert("RGB"))


def hsv_to_rgb_frombytes(hsv):
    """image_edit 的 HSV→RGB(``Image.frombytes``)。"""
    from PIL import Image
    np = _np()
    hsv = np.ascontiguousarray(hsv)
    image = Image.frombytes("HSV", (hsv.shape[1], hsv.shape[0]), hsv.tobytes())
    return np.asarray(image.convert("RGB"))


def write_hsv_hits(source_rgb, hsv, hit, converter):
    """只把 ``hit`` 位置換成轉回的 RGB,其餘 byte 維持來源。"""
    np = _np()
    converted = converter(hsv)
    out = np.array(source_rgb[..., :3], copy=True)
    out[hit] = converted[hit]
    return out


def decode_selected_white_mask(im):
    """選取白遮罩 → L uint8;不是 L/1 或 R=G=B 的 RGB 時回傳 None(含 RGBA 與彩色)。"""
    np = _np()
    if im.mode in ("L", "1"):
        return np.asarray(im.convert("L"))
    if im.mode == "RGB":
        rgb = np.asarray(im)
        if np.array_equal(rgb[..., 0], rgb[..., 1]) and np.array_equal(rgb[..., 1], rgb[..., 2]):
            return rgb[..., 0].copy()
    return None


def feather_weight(mask, feather):
    """貼回權重。``feather`` 為 0 時原樣退回;否則先方形擴張再高斯,擴張範圍外維持 0。"""
    from PIL import Image, ImageFilter
    np = _np()
    if not feather:
        return mask
    grown = Image.fromarray(mask).filter(ImageFilter.MaxFilter(2 * int(feather) + 1))
    blurred = np.asarray(grown.filter(ImageFilter.GaussianBlur(feather / 2.0)))
    return np.where(np.asarray(grown) > 0, blurred, 0).astype(np.uint8)


def blend_inside_mask(original_rgb, edited_rgb, weight):
    """依 uint8 權重把 edited 疊上 original。權重 0 的像素抄來源,並回傳遮罩外是否被改。

    回傳 (blended RGB uint8, stats)。stats 的 outside/inside 計數給兩邊的報告各自命名。
    """
    np = _np()
    original = original_rgb[..., :3]
    edited = edited_rgb[..., :3]
    w = weight.astype(np.float32)[..., None] / 255.0
    blended = np.round(edited.astype(np.float32) * w + original.astype(np.float32) * (1.0 - w)).astype(np.uint8)
    outside = weight == 0
    blended[outside] = original[outside]
    changed = int(np.any(blended[outside] != original[outside], axis=1).sum())
    inside = ~outside
    delta = np.abs(blended.astype(np.int16) - original.astype(np.int16))
    mean = float(delta[inside].mean()) if inside.any() else 0.0
    return blended, {
        "outside_pixels": int(outside.sum()),
        "outside_changed_pixels": changed,
        "inside_pixels": int(inside.sum()),
        "inside_mean_abs_rgb_delta": mean,
    }


def decode_video_frames(path, mode="RGB"):
    """PyAV 解碼影格。空片不在這裡丟錯,讓呼叫端留自己的訊息。回傳 (frames, fps)。"""
    import os
    import av
    np = _np()
    frames = []
    with av.open(os.fspath(path)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate) if stream.average_rate else None
        for frame in container.decode(video=0):
            frames.append(np.asarray(frame.to_image().convert(mode)))
    return frames, fps


def encode_video_frames(frames, path, *, codec, pix_fmt, ndarray_format, fps,
                        container_format=None, options=None, contiguous=False):
    """PyAV 編碼迴圈。codec／像素格式／是否強制 contiguous 由呼叫端帶入,避免改到既有位元組。"""
    import os
    import av
    from fractions import Fraction
    np = _np()
    path = os.fspath(path)
    height, width = frames[0].shape[:2]
    open_kwargs = {}
    if container_format is not None:
        open_kwargs["format"] = container_format
    with av.open(path, "w", **open_kwargs) as container:
        stream = container.add_stream(codec, rate=Fraction(fps).limit_denominator(1001))
        stream.width, stream.height, stream.pix_fmt = width, height, pix_fmt
        if options is not None:
            stream.options = options
        for frame in frames:
            array = np.ascontiguousarray(frame) if contiguous else frame
            video_frame = av.VideoFrame.from_ndarray(array, format=ndarray_format)
            for packet in stream.encode(video_frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path
