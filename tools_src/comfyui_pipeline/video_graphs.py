"""Pure video helpers: frame-count math, camera-move prompts/stills, h3 ref-prompt tags.

These have no dependency on machine-specific runtime state (unlike the graph
builders in generate.py, which resolve model file names against the active
video capability config and therefore stay there).
"""

import os

try:
    from PIL import Image as PILImage, ImageFilter
except ImportError:  # Pillow is only needed by build_camera_end_still.
    PILImage = None
    ImageFilter = None

from . import video_catalog

VIDEO_FPS = video_catalog.VIDEO_FPS
CAMERA_MOVES = video_catalog.CAMERA_MOVES
CAMERA_STILL_SUFFIX = video_catalog.CAMERA_STILL_SUFFIX
CAMERA_ZOOM = video_catalog.CAMERA_ZOOM
CAMERA_PAN_CROP = video_catalog.CAMERA_PAN_CROP


def _require_pillow():
    if PILImage is None or ImageFilter is None:
        raise RuntimeError("這個 helper 需要 Pillow;產圖核心的 HTTP/graph 功能不需要 Pillow。")


def wan_frame_count(duration_sec):
    """Wan22ImageToVideoLatent 的 length 是 4k+1(預設 49)。"""
    target = int(round(duration_sec * VIDEO_FPS))
    k = max(2, int(round((target - 1) / 4.0)))
    return k * 4 + 1


def h3_frame_count(duration_sec):
    """MiniMaxH3ImageToVideo 的 length 要落在 17k+5(官方 Math Expression)。"""
    x = max(5, int(round(duration_sec * VIDEO_FPS)))
    return x + (5 - (x % 17)) % 17


def camera_move_prompt(camera, prompt=None):
    """把 --camera 枚舉收成鎖死的 I2V prompt。使用者文字只補場景,運鏡句以枚舉為準。"""
    if camera not in CAMERA_MOVES:
        raise ValueError(f"未知 --camera: {camera}(可用: {', '.join(CAMERA_MOVES)})")
    scene = (prompt or "").strip() or "the subject stays completely still"
    return f"{scene}. {CAMERA_MOVES[camera]}. {CAMERA_STILL_SUFFIX}."


def build_camera_end_still(image_path, camera, width, height, dest_path):
    """給有 last_frame 能力的 backend 用的終點靜幀。zoom/pan 是對來源圖做幾何裁切/縮放。
    靜幀裡沒有畫面外的像素,所以 pan/zoom_out 會看起來像 Ken Burns(裁近或縮小置中),
    不能真的揭示原圖外面的東西。orbit 回傳 None。"""
    _require_pillow()
    if camera not in CAMERA_MOVES:
        raise ValueError(f"未知 --camera: {camera}")
    if camera in ("orbit_cw", "orbit_ccw"):
        return None
    src = PILImage.open(image_path).convert("RGB")
    canvas = src.resize((width, height), PILImage.Resampling.LANCZOS)
    if camera == "static":
        out = canvas
    elif camera == "zoom_in":
        cw = max(32, int(width / CAMERA_ZOOM) // 2 * 2)
        ch = max(32, int(height / CAMERA_ZOOM) // 2 * 2)
        x, y = (width - cw) // 2, (height - ch) // 2
        out = canvas.crop((x, y, x + cw, y + ch)).resize(
            (width, height), PILImage.Resampling.LANCZOS
        )
    elif camera == "zoom_out":
        sw = max(32, int(width / CAMERA_ZOOM))
        sh = max(32, int(height / CAMERA_ZOOM))
        small = canvas.resize((sw, sh), PILImage.Resampling.LANCZOS)
        out = canvas.filter(ImageFilter.GaussianBlur(radius=16))
        out.paste(small, ((width - sw) // 2, (height - sh) // 2))
    else:
        keep_w = max(32, int(width * CAMERA_PAN_CROP) // 2 * 2)
        keep_h = max(32, int(height * CAMERA_PAN_CROP) // 2 * 2)
        if camera == "pan_left":
            box = (0, (height - keep_h) // 2, keep_w, (height - keep_h) // 2 + keep_h)
        elif camera == "pan_right":
            box = (width - keep_w, (height - keep_h) // 2, width, (height - keep_h) // 2 + keep_h)
        elif camera == "pan_up":
            box = ((width - keep_w) // 2, 0, (width - keep_w) // 2 + keep_w, keep_h)
        elif camera == "pan_down":
            box = ((width - keep_w) // 2, height - keep_h, (width - keep_w) // 2 + keep_w, height)
        else:
            raise ValueError(f"未知 --camera: {camera}")
        out = canvas.crop(box).resize((width, height), PILImage.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)) or ".", exist_ok=True)
    out.save(dest_path)
    return dest_path


def h3_ref_prompt(prompt, n_refs):
    """h3 backend 私有:Ref2VA 要用 1-based <Picture i>。不要把這組 tag 寫進 CLI/SKILL 契約。
    使用者沒寫 tag 就自動補;寫了就原樣送。"""
    if "<Picture" in prompt:
        return prompt
    if n_refs == 1:
        prefix = (
            "<Picture 1> is the character identity reference. "
            "The video shows this same character in a new shot, not a copy of that still."
        )
    else:
        tags = ", ".join(f"<Picture {i}>" for i in range(1, n_refs + 1))
        prefix = (
            f"{tags} are identity references of the same character. "
            "The video shows this same character in a new shot, not a copy of those stills."
        )
    return f"{prefix} {prompt}"


def h3_pose_drive_prompt(prompt):
    """h3 backend 私有:身份走 <Picture 1>、動作走 <Video 1>。不要把這組 tag 寫進 CLI/SKILL。"""
    if "<Picture" in prompt or "<Video" in prompt:
        return prompt
    prefix = (
        "<Picture 1> is the character identity reference. "
        "<Video 1> is the motion to follow (pose skeleton, edges, or depth — not a second person). "
        "The output shows this same character performing that motion."
    )
    return f"{prefix} {prompt}"
