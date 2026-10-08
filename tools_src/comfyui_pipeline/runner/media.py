"""runner 讀媒體的地方:只回傳量測值,不做判斷(判斷在 steps.py)。

影片用 PyAV、圖片用 Pillow;兩者都在 ComfyUI 的 Python 環境裡。缺套件時丟 :class:`MediaDependencyError`,
訊息會提示改用 ``local_config.json`` 的 ``python_exe`` 執行。測試可以換成假的 media 物件(同名函式)。
"""
import os
from fractions import Fraction

from ..video_media import _fps_fraction


class MediaDependencyError(RuntimeError):
    """缺 PyAV／Pillow。"""


def _import(name):
    try:
        if name == "av":
            import av
            return av
        from PIL import Image
        return Image
    except ImportError as exc:
        package = "PyAV" if name == "av" else "Pillow"
        raise MediaDependencyError(
            f"檢查媒體需要 {package},目前的 Python 沒有安裝;請用 ComfyUI 的 Python"
            "(local_config.json 的 python_exe)執行 gameart.py run") from exc


def probe_image(path):
    """回傳 {width, height, mode, has_alpha};讀不了丟 ValueError。"""
    Image = _import("PIL")
    try:
        with Image.open(path) as im:
            im.load()
            return {"width": im.width, "height": im.height, "mode": im.mode,
                    "has_alpha": im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info}
    except OSError as exc:
        raise ValueError(f"圖片讀取失敗 {path}: {exc}") from exc


def mask_stats(path, channel="red"):
    """遮罩圖指定通道的統計:{width, height, nonzero, has_transparency}。"""
    Image = _import("PIL")
    index = {"red": 0, "green": 1, "blue": 2}.get(channel, 0)
    try:
        with Image.open(path) as im:
            im.load()
            has_transparency = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
            rgb = im.convert("RGB")
    except OSError as exc:
        raise ValueError(f"遮罩讀取失敗 {path}: {exc}") from exc
    band = rgb.getchannel(index)
    histogram = band.histogram()
    return {"width": rgb.width, "height": rgb.height, "nonzero": sum(histogram[1:]),
            "has_transparency": has_transparency}


def probe_video(path):
    """解碼整支影片:{width, height, frames, fps(分數字串), fps_value, pts_uniform, has_audio, duration_seconds}。"""
    av = _import("av")
    try:
        container = av.open(os.fspath(path))
    except Exception as exc:  # noqa: BLE001 - PyAV 例外種類多
        raise ValueError(f"影片無法開啟 {path}: {exc}") from exc
    try:
        streams = container.streams.video
        if not streams:
            raise ValueError(f"影片沒有 video stream: {path}")
        stream = streams[0]
        rate = _fps_fraction(getattr(stream, "average_rate", None))
        pts = []
        for frame in container.decode(video=0):
            pts.append(frame.pts)
        if not pts:
            raise ValueError(f"影片沒有影格: {path}")
        has_audio = bool(getattr(container.streams, "audio", ()) or ())
        width, height = int(stream.width), int(stream.height)
        time_base = stream.time_base
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"影片解碼失敗 {path}: {exc}") from exc
    finally:
        container.close()
    uniform = None
    if all(p is not None for p in pts) and len(pts) > 1:
        deltas = {b - a for a, b in zip(pts, pts[1:])}
        uniform = len(deltas) == 1 and next(iter(deltas)) > 0
    elif len(pts) == 1:
        uniform = True
    if (rate is None or rate <= 0) and uniform and len(pts) > 1 and time_base:
        rate = 1 / (Fraction(pts[1] - pts[0]) * Fraction(time_base))
    return {"width": width, "height": height, "frames": len(pts),
            "fps": f"{rate.numerator}/{rate.denominator}" if rate else None,
            "fps_value": float(rate) if rate else None, "pts_uniform": uniform, "has_audio": has_audio,
            "duration_seconds": round(len(pts) / float(rate), 6) if rate else None}


def png_frame_stats(path):
    """單張 PNG:{width, height, grayscale(R=G=B), mode}。"""
    Image = _import("PIL")
    try:
        with Image.open(path) as im:
            im.load()
            mode = im.mode
            if mode in ("L", "1", "I", "I;16", "F"):
                gray = True
            else:
                rgb = im.convert("RGB")
                r, g, b = rgb.split()
                from PIL import ImageChops
                gray = ImageChops.difference(r, g).getbbox() is None and ImageChops.difference(r, b).getbbox() is None
            return {"width": im.width, "height": im.height, "mode": mode, "grayscale": gray}
    except OSError as exc:
        raise ValueError(f"PNG 讀取失敗 {path}: {exc}") from exc


def extract_keyframes(video_path, which, dest_dir):
    """抽 first／middle／last 幀存成 PNG,回傳 {名稱: 路徑}。"""
    av = _import("av")
    container = av.open(os.fspath(video_path))
    try:
        frames = [frame.to_image() for frame in container.decode(video=0)]
    finally:
        container.close()
    if not frames:
        raise ValueError(f"影片沒有影格: {video_path}")
    index = {"first": 0, "middle": (len(frames) - 1) // 2, "last": len(frames) - 1}
    os.makedirs(dest_dir, exist_ok=True)
    written = {}
    for name in which:
        path = os.path.join(dest_dir, f"{name}.png")
        frames[index[name]].save(path)
        written[name] = {"path": path, "frame_index": index[name]}
    return written


def mask_preview(video_path, mask_paths, dest_path):
    """原片疊遮罩的預覽條(用 vfx_alpha_tools);回傳寫出的路徑。"""
    import vfx_alpha_tools as vat  # tools_src 頂層模組;部署後也在同一層
    frames, _ = vat.read_frames(video_path)
    masks_dir = os.path.dirname(mask_paths[0])
    masks = vat.read_masks(masks_dir, len(frames), (frames[0].shape[1], frames[0].shape[0]))
    n = len(frames)
    picks = sorted({0, n // 4, n // 2, 3 * n // 4, n - 1})
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    vat.mask_overlay_strip(frames, masks, picks, dest_path)
    return dest_path
