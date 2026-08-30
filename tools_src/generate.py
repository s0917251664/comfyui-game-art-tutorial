"""
穩定產圖核心腳本(不吃自然語言,只吃結構化參數)。

設計原則:
- 每個 task 對應一組鎖死大部分參數的 ComfyUI graph,只有明確列出的欄位可調
- 不靠 LLM 每次臨場組 JSON,參數集固定、行為可預期、可重複
- 上層(Skill/agent)的工作只是把自然語言整理成這裡要的結構化參數,不做生成邏輯本身

Usage:
    python generate.py --config local_config.json concept --prompt "a female game character concept art, fantasy armor" [--negative ...] [--seed N] [--width 1024] [--height 1024] [--remove-bg]
    python generate.py --comfy-url http://127.0.0.1:8188 character_action --prompt "..." --character-ref path.png --pose-ref path.png [--pose-strength 1.0] [--remove-bg]
    python generate.py --config local_config.json inpaint --prompt "..." --image path.png --mask path.png [--denoise 1.0]
    python generate.py --config local_config.json img2video --image still.png --prompt "camera locked, idle motion" [--backend h3|wan] [--duration 2] [--timeout 1800]
    python generate.py --comfy-url http://127.0.0.1:8188 character_video --character-ref char.png --prompt "the same character running through a corridor" [--duration 2]
    python generate.py --config local_config.json camera_move --image still.png --camera zoom_in [--duration 2]
    python generate.py --config local_config.json pose_drive --image char.png --motion-ref motion.mp4 --prompt "the character performs the motion"
"""
import argparse
import json
import math
import mimetypes
import ntpath
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

try:
    from PIL import Image as PILImage, ImageDraw, ImageFilter
except ImportError:  # Pillow is only needed by the local template/mask helpers.
    PILImage = None
    ImageDraw = None
    ImageFilter = None

# The deployment copy can live outside this repository.  Do not infer a URL from
# the source tree; callers must provide one explicitly, through the CLI, an
# environment variable, an explicitly named config file, or this compatibility
# override when embedding the module.
COMFY_URL = None
COMFY_URL_ENV_VARS = ("COMFY_URL", "COMFYUI_URL")
COMFY_CONFIG_ENV_VARS = (
    "COMFY_CONFIG", "COMFYUI_CONFIG", "COMFY_CONFIG_PATH", "COMFYUI_CONFIG_PATH",
)
DEFAULT_TIMEOUT = 180.0
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_POLL_TIMEOUT = 15.0
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_POLL_RETRIES = 3
DEFAULT_NEGATIVE = "blurry, low quality, extra fingers, deformed, watermark"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")
DEVICE_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "device_config.json")

SDXL_TIERS = frozenset(("sdxl_high", "sdxl", "sdxl_light"))


def _require_pillow():
    if PILImage is None or ImageDraw is None or ImageFilter is None:
        raise RuntimeError("這個 helper 需要 Pillow；產圖核心的 HTTP/graph 功能不需要 Pillow。")


def _normalise_comfy_url(url):
    """Validate and normalise a ComfyUI base URL without inventing a default."""
    if url is None:
        return None
    value = str(url).strip().rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"ComfyUI URL 必須是完整的 http(s) URL: {url!r}")
    return value


def _read_runtime_config(config_path):
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError as exc:
        raise RuntimeError(f"找不到指定的 runtime config: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"runtime config 不是有效 JSON: {config_path}") from exc
    if not isinstance(config, dict):
        raise RuntimeError(f"runtime config 必須是 JSON object: {config_path}")
    return config


def resolve_comfy_url(cli_url=None, config_path=None):
    """Resolve the ComfyUI URL with CLI > environment > explicit config priority.

    There is deliberately no automatic ``local_config.json`` lookup: a copied
    script must not accidentally connect to a path relative to the source repo.
    """
    for candidate in (cli_url, *(os.environ.get(name) for name in COMFY_URL_ENV_VARS), COMFY_URL):
        if candidate:
            return _normalise_comfy_url(candidate)

    explicit_config = config_path
    if explicit_config is None:
        explicit_config = next((os.environ.get(name) for name in COMFY_CONFIG_ENV_VARS if os.environ.get(name)), None)
    if explicit_config:
        config = _read_runtime_config(explicit_config)
        candidate = config.get("comfyui_url") or config.get("comfy_url")
        if candidate:
            return _normalise_comfy_url(candidate)

    raise RuntimeError(
        "未設定 ComfyUI URL；請使用 --comfy-url、COMFY_URL/COMFYUI_URL，"
        "或透過 --config/COMFY_CONFIG 指定含 comfyui_url 的 JSON。"
    )


def _comfy_endpoint(path, comfy_url=None):
    base = _normalise_comfy_url(comfy_url) if comfy_url else resolve_comfy_url()
    return f"{base}/{path.lstrip('/')}"


def validate_batch(batch):
    if isinstance(batch, bool) or not isinstance(batch, int) or batch < 1:
        raise ValueError(f"batch 必須是正整數，目前是 {batch!r}")
    return batch


def validate_dimensions(width, height):
    for name, value in (("width", width), ("height", height)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value % 8:
            raise ValueError(f"{name} 必須是正整數且為 8 的倍數，目前是 {value!r}")
    return width, height


def validate_unit_interval(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} 必須落在 0..1，目前是 {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必須落在 0..1，目前是 {value!r}") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} 必須落在 0..1，目前是 {value!r}")
    return value


def validate_lora_strength(value):
    return validate_unit_interval(value, "lora_strength")


def validate_scale(scale):
    try:
        number = float(scale)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"scale 必須大於 0 且不超過 4，目前是 {scale!r}") from exc
    if not math.isfinite(number) or not 0.0 < number <= 4.0:
        raise ValueError(f"scale 必須大於 0 且不超過 4，目前是 {scale!r}")
    return scale


def validate_timeout(timeout):
    try:
        number = float(timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"timeout 必須是正數，目前是 {timeout!r}") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"timeout 必須是正數，目前是 {timeout!r}")
    return timeout


def require_sdxl_capability(feature, tier=None):
    """Fail before uploads/queueing when an SD1.5 graph needs SDXL add-ons."""
    current_tier = DEVICE.get("tier") if tier is None else tier
    if current_tier == "sd15" or (current_tier is not None and current_tier not in SDXL_TIERS):
        raise RuntimeError(
            f"{feature} 目前需要 SDXL 家族的 ControlNet/IPAdapter，"
            f"但這台機器的 tier 是 {current_tier!r}；sd15 尚未支援這項功能。"
        )

# pose_only / character_action 的構圖控制來源,依 --control-type 選擇對應 ControlNet 模型
# (canny=線稿邊緣,pose=骨架姿勢,depth=深度圖),需要 comfyui_controlnet_aux custom node
# 提供 OpenposePreprocessor / DepthAnythingV2Preprocessor,細節見 skills/comfyui-install/SKILL.md
#
# 已知技術債:這裡跟下面 build_character_action/build_style_lock 裡的 ipadapter_file/clip_name
# 都是寫死指向 SDXL 版本,沒有跟著 CKPT(見 load_device_config)的 tier 走。目前只在 SDXL 家族
# tier(sdxl_high/sdxl/sdxl_light)上驗證過。如果之後真的有機器落在 sd15 tier(底模自動換成
# SD1.5 系列),這幾個常數也要跟著換成 SD1.5 對應版本,不然底模跟 ControlNet/IPAdapter 架構
# 對不上,執行期會 shape mismatch——換 tier 時記得回來檢查這裡,不要假設現有檔名通用。
CONTROLNET_MODELS = {
    "canny": "controlnet-canny-sdxl-1.0.safetensors",
    "pose": "controlnet-openpose-sdxl-1.0.safetensors",
    "depth": "controlnet-depth-sdxl-1.0.safetensors",
}

# --style 選填參數的白名單(選配,不裝也完全不影響預設行為)。都是 SDXL 架構的社群微調底模,
# 換掉 CKPT 不用連帶換 ControlNet/IPAdapter/CLIP Vision。只在 SDXL 家族 tier 生效,見 main() 裡的
# tier 檢查——sd15 機器上這幾顆會跟 ControlNet/IPAdapter shape mismatch。
# 各風格的授權/檔案來源見 skills/comfyui-install/reference/models.md,商用前務必自行覆核授權條款
# ——這三顆各自授權都不一樣(Juggernaut/Pony 都有針對「做成付費服務」的限制;Illustrious 依版本
# 不同差很多,2026-08-19 曾經記錯成 MIT,見 models.md 更正說明),不要憑這裡的常數名稱就假設能商用。
STYLE_CHECKPOINTS = {
    "realistic": "juggernautXL_ragnarok.safetensors",
    "illustration": "Illustrious-XL-v1.1.safetensors",
    "anime": "ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
}

# --rating 選填參數(選配,不給就完全不影響 prompt)。只對 anime/illustration 這兩個 --style
# 有意義——這兩顆底模的訓練資料本身就用分級標籤控制內容尺度(Pony 用 rating_xxx,Illustrious
# 沿用 Danbooru 的 rating:xxx),不是這個腳本自己發明的機制。realistic/預設底模沒有對應標籤慣例,
# 給了 --rating 也沒意義,main() 裡會直接擋掉,不要讓它靜默沒效果。
RATING_TAGS = {
    "anime": {"safe": "rating_safe", "questionable": "rating_questionable", "explicit": "rating_explicit"},
    "illustration": {"safe": "rating:general", "questionable": "rating:questionable", "explicit": "rating:explicit"},
}

# 影片 task 的對外契約是 task 名 + --backend,不是模型名。下面這組是各 backend 的實作檔名,
# 不能接 SDXL ControlNet/IPAdapter/--style,也不跟圖片 CKPT/tier 走。
# 預設 backend 是這台 4080 bake-off 的結果,換機器/換實作時改 DEFAULT_VIDEO_BACKEND,
# 不要把 h3/wan 寫進 task 名稱或輸出檔名前綴。
VIDEO_BACKENDS = ("h3", "wan")
DEFAULT_VIDEO_BACKEND = "h3"
# 每個 backend 現在接得上哪些能力。task 要的能力在 VIDEO_TASK_CAPS;對不上就報錯,不要靜默改 task。
VIDEO_BACKEND_CAPS = {
    "h3": frozenset({"i2v", "last_frame", "character_ref", "control_video", "audio"}),
    "wan": frozenset({"i2v", "control_video"}),
}
VIDEO_TASK_CAPS = {
    "img2video": "i2v",
    "clip_extend": "i2v",
    "camera_move": "i2v",
    "fx_loop": "last_frame",
    "transition": "last_frame",
    "character_video": "character_ref",
    "pose_drive": "control_video",
}
CHARACTER_REF_MAX = 9
VIDEO_WAN_UNET = "wan2.2_ti2v_5B_fp16.safetensors"
VIDEO_WAN_FUN_UNET = "wan2.2_fun_control_5B_bf16.safetensors"
VIDEO_WAN_CLIP = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VIDEO_WAN_VAE = "wan2.2_vae.safetensors"
VIDEO_H3_UNET = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
VIDEO_H3_REF_UNET = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
VIDEO_H3_CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_H3_VAE = "minimax_h3_video_vae_fp16.safetensors"
VIDEO_H3_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
VIDEO_MAX_SIDE = 768
VIDEO_STEPS = 20
VIDEO_FPS = 24
VIDEO_DURATION_MIN = 2
VIDEO_DURATION_MAX = 6
DEFAULT_VIDEO_TIMEOUT = 1800.0
VIDEO_NEG_DEFAULT = (
    "blurry, low quality, morphing face, extra limbs, camera movement, "
    "zoom, pan, text, watermark, still image, frozen"
)
VIDEO_LOOP_SUFFIX = (
    "seamless looping animation, cyclical motion that returns to the first frame, "
    "camera locked, subject stays in place"
)

# camera_move 的運鏡枚舉(task 契約)。有 last_frame 能力的 backend 會再餵幾何終點靜幀;
# 沒有的 backend 只靠下面這組英文運鏡句。orbit 平面裁切做不出繞拍終點,一律只走 prompt。
CAMERA_MOVES = {
    "static": "locked static camera, no camera movement",
    "pan_up": "slow camera pan up",
    "pan_down": "slow camera pan down",
    "pan_left": "slow camera pan left",
    "pan_right": "slow camera pan right",
    "zoom_in": "slow camera zoom in toward the subject",
    "zoom_out": "slow camera zoom out from the subject",
    "orbit_cw": "slow camera orbit clockwise around the subject",
    "orbit_ccw": "slow camera orbit counter-clockwise around the subject",
}
CAMERA_STILL_SUFFIX = (
    "the subject stays completely still, no character animation, no morphing, "
    "only the camera moves, keep identity and framing except for the camera move"
)
CAMERA_ZOOM = 1.35       # zoom_in 終點是來源中心 1/1.35 再拉回畫布
CAMERA_PAN_CROP = 0.82   # pan_* 終點保留這個比例、往運鏡方向裁



def build_control_preprocessor(control_type, image_node_id):
    """依 control_type 回傳對應的前處理節點(從 image_node_id 的圖片輸出接進去)。"""
    if control_type == "canny":
        return {"class_type": "Canny", "inputs": {"image": [image_node_id, 0], "low_threshold": 0.4, "high_threshold": 0.8}}
    elif control_type == "pose":
        return {"class_type": "OpenposePreprocessor", "inputs": {"image": [image_node_id, 0]}}
    elif control_type == "depth":
        return {"class_type": "DepthAnythingV2Preprocessor", "inputs": {"image": [image_node_id, 0]}}
    raise ValueError(f"未知 control_type: {control_type}(可用: canny/pose/depth)")


def load_device_config():
    """讀設備偵測結果(detect_device.py 產出),決定用哪個 checkpoint/預設解析度。
    沒有這份設定檔就用保守的 SDXL 預設值,並提醒使用者先跑一次偵測。"""
    if not os.path.exists(DEVICE_CONFIG_PATH):
        print(f"[提醒] 找不到 {DEVICE_CONFIG_PATH},建議先執行 detect_device.py。目前用預設 SDXL 設定。", file=sys.stderr)
        return {"checkpoint": "sd_xl_base_1.0.safetensors", "default_width": 1024, "default_height": 1024}
    with open(DEVICE_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


DEVICE = load_device_config()
CKPT = DEVICE["checkpoint"]


def upload_image(path, comfy_url=None, request_timeout=DEFAULT_HTTP_TIMEOUT):
    """上傳本機圖片或影片到 ComfyUI input，回傳 LoadImage/LoadVideo 使用的檔名。"""
    validate_timeout(request_timeout)
    filename = os.path.basename(path)
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        _comfy_endpoint("upload/image", comfy_url),
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = urllib.request.urlopen(req, timeout=request_timeout)
    result = json.loads(resp.read().decode())
    try:
        return result["name"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("ComfyUI upload 回應缺少 name") from exc


def _is_transient_poll_error(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (408, 425, 429, 500, 502, 503, 504)
    return isinstance(exc, (urllib.error.URLError, TimeoutError, OSError))


def _poll_error_text(exc):
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read().decode(errors="replace")
        except Exception:
            body = ""
        return f"HTTP {exc.code}" + (f": {body}" if body else "")
    return str(exc) or exc.__class__.__name__


def submit_and_wait(prompt, timeout=DEFAULT_TIMEOUT, comfy_url=None,
                    poll_interval=DEFAULT_POLL_INTERVAL, max_poll_retries=DEFAULT_POLL_RETRIES):
    """Queue a prompt and poll history, retaining prompt_id in every terminal error."""
    validate_timeout(timeout)
    validate_timeout(poll_interval if poll_interval else 0.000001)
    if isinstance(max_poll_retries, bool) or not isinstance(max_poll_retries, int) or max_poll_retries < 0:
        raise ValueError(f"max_poll_retries 必須是 0 以上的整數，目前是 {max_poll_retries!r}")

    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        _comfy_endpoint("prompt", comfy_url), data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=min(DEFAULT_HTTP_TIMEOUT, float(timeout)))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"送出失敗: {e.code} {e.read().decode(errors='replace')}") from e

    try:
        result = json.loads(resp.read().decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("ComfyUI queue 回應不是有效 JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("ComfyUI queue 回應必須是 JSON object")
    if result.get("node_errors"):
        raise RuntimeError(f"節點參數錯誤: {json.dumps(result['node_errors'], ensure_ascii=False)}")
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise RuntimeError("ComfyUI 回應缺少 prompt_id")

    start = time.monotonic()
    transient_failures = 0
    while time.monotonic() - start < float(timeout):
        remaining = float(timeout) - (time.monotonic() - start)
        poll_timeout = min(DEFAULT_POLL_TIMEOUT, max(0.001, remaining))
        try:
            hist_req = urllib.request.urlopen(
                _comfy_endpoint(f"history/{urllib.parse.quote(str(prompt_id), safe='')}", comfy_url),
                timeout=poll_timeout,
            )
            history = json.loads(hist_req.read().decode())
        except Exception as exc:
            if not _is_transient_poll_error(exc):
                raise RuntimeError(f"輪詢生成狀態失敗: {_poll_error_text(exc)}, prompt_id={prompt_id}") from exc
            transient_failures += 1
            if transient_failures > max_poll_retries:
                raise RuntimeError(
                    f"輪詢生成狀態暫時失敗，已重試 {max_poll_retries} 次: "
                    f"{_poll_error_text(exc)}, prompt_id={prompt_id}"
                ) from exc
            remaining = float(timeout) - (time.monotonic() - start)
            if remaining <= 0:
                break
            backoff = min(float(poll_interval) * (2 ** (transient_failures - 1)), remaining)
            time.sleep(backoff)
            continue

        transient_failures = 0
        if not isinstance(history, dict):
            raise RuntimeError(f"ComfyUI history 回應格式錯誤, prompt_id={prompt_id}")
        if prompt_id in history:
            entry = history[prompt_id]
            if not isinstance(entry, dict):
                raise RuntimeError(f"ComfyUI history entry 回應格式錯誤, prompt_id={prompt_id}")
            status = entry.get("status", {})
            if not isinstance(status, dict):
                raise RuntimeError(f"ComfyUI history status 回應格式錯誤, prompt_id={prompt_id}")
            if status.get("status_str") == "error":
                raise RuntimeError(f"生成失敗: {json.dumps(status, ensure_ascii=False)}, prompt_id={prompt_id}")
            if status.get("completed"):
                return entry
        remaining = float(timeout) - (time.monotonic() - start)
        if remaining > 0:
            time.sleep(min(float(poll_interval), remaining))
    raise TimeoutError(f"等待生成逾時({timeout}s), prompt_id={prompt_id}")


def _safe_output_path(output_dir, filename):
    if not isinstance(filename, str) or not filename:
        raise ValueError("ComfyUI output 缺少有效 filename")
    # Check both POSIX and Windows spellings because a Windows deployment may
    # send back a backslash path even when this process runs on POSIX.
    if os.path.isabs(filename) or ntpath.isabs(filename) or ntpath.splitdrive(filename)[0]:
        raise ValueError(f"拒絕不安全的 output filename: {filename!r}")
    components = filename.replace("\\", "/").split("/")
    if ".." in components:
        raise ValueError(f"拒絕 path traversal output filename: {filename!r}")

    output_root = os.fspath(output_dir)
    root = os.path.abspath(output_root)
    root_real = os.path.realpath(root)
    candidate = os.path.abspath(os.path.join(output_root, *components))
    candidate_real = os.path.realpath(candidate)
    try:
        # Resolve symlinks for the security check, but return the lexical path
        # the caller supplied so output paths remain stable on macOS (/private).
        inside = os.path.commonpath((root_real, candidate_real)) == root_real
    except ValueError:
        inside = False
    if not inside:
        raise ValueError(f"拒絕 path traversal output filename: {filename!r}")
    # Preserve the caller's relative/absolute output-dir convention.
    return os.path.join(output_root, *components)


def download_outputs(history_entry, output_dir=None, node_ids=None, comfy_url=None,
                     request_timeout=DEFAULT_HTTP_TIMEOUT):
    """Download selected image/video outputs with safe paths and atomic writes."""
    validate_timeout(request_timeout)
    if not isinstance(history_entry, dict) or not isinstance(history_entry.get("outputs"), dict):
        raise RuntimeError("ComfyUI history 沒有有效的 outputs")
    output_dir = output_dir or OUTPUT_DIR
    paths = []
    os.makedirs(output_dir, exist_ok=True)
    selected_ids = {str(node_id) for node_id in node_ids} if node_ids is not None else None
    for node_id, node_out in history_entry.get("outputs", {}).items():
        if selected_ids is not None and str(node_id) not in selected_ids:
            continue
        if not isinstance(node_out, dict):
            continue
        for key in ("images", "videos", "gifs"):
            items = node_out.get(key) or []
            if not isinstance(items, (list, tuple)):
                continue
            for item in items:
                filename = item.get("filename") if isinstance(item, dict) else None
                local_path = _safe_output_path(output_dir, filename)
                query = urllib.parse.urlencode({
                    "filename": filename,
                    "subfolder": str(item.get("subfolder", "")),
                    "type": str(item.get("type", "output")),
                })
                url = f"{_comfy_endpoint('view', comfy_url)}?{query}"
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                partial_path = f"{local_path}.{uuid.uuid4().hex}.part"
                try:
                    with urllib.request.urlopen(url, timeout=request_timeout) as response, open(partial_path, "wb") as output:
                        while chunk := response.read(1024 * 1024):
                            output.write(chunk)
                    os.replace(partial_path, local_path)
                except Exception:
                    try:
                        os.unlink(partial_path)
                    except FileNotFoundError:
                        pass
                    raise
                paths.append(local_path)
    if not paths:
        selected = f" node_ids={sorted(selected_ids)}" if selected_ids is not None else ""
        raise RuntimeError(f"ComfyUI 沒有產生任何可下載的 output{selected}")
    return paths


def seed_or_random(seed):
    return seed if seed is not None else int.from_bytes(os.urandom(6), "big")


def model_clip_refs(graph, lora_name=None, lora_strength=0.8, ckpt_node_id="1", lora_node_id="1b"):
    """回傳這個 graph 後面該接的 MODEL/CLIP 節點參照。
    有指定 --lora 的話,插入一個 LoraLoader 節點(套在 checkpoint 後面),回傳它的輸出;
    後面所有節點的 model/clip 輸入都要用這裡回傳的參照,不要直接寫死 [ckpt_node_id, 0]/[ckpt_node_id, 1],
    不然 LoRA 會被跳過沒套用到。沒指定 --lora 就直接回傳 checkpoint 節點本身的輸出,行為跟原本一樣。"""
    validate_lora_strength(lora_strength)
    if not lora_name:
        return [ckpt_node_id, 0], [ckpt_node_id, 1]
    graph[lora_node_id] = {
        "class_type": "LoraLoader",
        "inputs": {
            "model": [ckpt_node_id, 0], "clip": [ckpt_node_id, 1],
            "lora_name": lora_name, "strength_model": lora_strength, "strength_clip": lora_strength,
        },
    }
    return [lora_node_id, 0], [lora_node_id, 1]


# ---------- task: concept (Ch3 系列:純文字概念圖) ----------
def build_concept(prompt, negative=None, width=None, height=None, seed=None, steps=25, cfg=7.0, batch_size=1,
                   lora_name=None, lora_strength=0.8, checkpoint=None):
    width = DEVICE["default_width"] if width is None else width
    height = DEVICE["default_height"] if height is None else height
    validate_dimensions(width, height)
    validate_batch(batch_size)
    validate_lora_strength(lora_strength)
    negative = negative or DEFAULT_NEGATIVE
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": model_ref, "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "concept"}},
    })
    return graph, "6"  # 回傳 (prompt, 最終圖片節點id) 方便後續接去背


# ---------- task: icon_asset(單一小型 UI 圖示/物件素材,不是整個 UI 畫面)----------
# 跟 concept 的差異只有三點,其餘 graph 結構完全共用 concept 的模式:
#   1. prompt/negative 固定 append 一段構圖引導詞,把生成結果導向「單一置中物件、無場景背景」
#      ——這同時讓輸出更像可用的圖示素材,也讓後面接的去背(BiRefNet)邊緣更乾淨(背景乾淨的
#      單一主體比「背景也有大量裝飾元素在跟主體搶前景」的構圖更容易被正確分離)
#   2. 預設畫布是 1024x1024 正方形,不吃 DEVICE["default_width/height"](那組預設是給人像
#      直式構圖調的,不適合圖示)
#   3. main() 呼叫這個 task 時一定會接去背,沒有 --remove-bg 旗標讓使用者選——圖示素材預期
#      本來就是要疊加到別的畫面上用,透明背景是這個 task 存在的前提,不是可選項
ICON_ASSET_PROMPT_SUFFIX = ", single centered object, icon design, isolated on plain simple background, clean readable silhouette, no scene, no extra props"
ICON_ASSET_NEGATIVE_SUFFIX = ", cluttered scene, multiple objects, full illustration background, cropped edges"
# icon_asset 的 --structure-ref 用的鎖死參數(這條產線的設計哲學:先求穩定可重複)。
# 2026-08-19 實測踩過三種失敗模式(當時的情境是「輪盤要精準等分成 N 塊」,但結論適用於任何
# 「結構/色塊配置有明確答案、不該讓 AI 自己瞎猜」的圖示):純靠文字描述數量/配置,SDXL 對這種
# 精確計數幾何任務不可靠;改成只用線稿 ControlNet 鎖邊緣位置後,邊緣位置雖然鎖住了,但色塊
# 配置沒被鎖住,SDXL 還是會整張畫成單一漸層蓋過色塊邊界(ControlNet canny 只鎖邊緣結構,不會
# 連帶鎖住「這幾塊顏色要交錯」這種區域級語意)。最後改成:範本圖本身直接畫好目標結構+顏色,
# 同時當 img2img 的底圖(denoise < 1.0,結構/色塊配置跟著像素直接繼承,不用 SDXL 自己決定)
# 加 Canny ControlNet(邊緣位置再鎖一層,img2img 的 denoise 沒到 1.0 時邊緣仍可能被畫糊,兩層
# 一起上比較保險)。denoise 太低(0.55/0.65 實測過)結構顏色鎖得住,但 SDXL 幾乎沒空間疊材質/
# 光澤,畫面會很平;denoise=0.85 是目前實測結構仍然穩、質感明顯提升的甜蜜點。
STRUCTURE_REF_CONTROL_STRENGTH = 0.85
STRUCTURE_REF_DENOISE = 0.85


def build_wheel_segment_template(n_segments, width=1024, height=1024,
                                  colors=((124, 40, 168), (20, 158, 148)), gold=(212, 175, 55),
                                  frame_ratio=None, bead_count=0, hub_ratio=0.12):
    """畫一張『交錯色塊扇形 + 金色分隔線/外框/中心軸』的範本圖,是 icon_asset 的 --structure-ref
    的其中一種產生方式(輪盤/放射狀等分圖示適用)——不是獨立的 CLI task,是給呼叫端(agent 或
    人類)在需要「放射狀精準等分」這種結構時自己呼叫來產生範本檔案用,範例見
    skills/comfyui-art-gen/reference/structure-ref.md。

    frame_ratio(選用,0~1):給了就額外畫一圈獨立的外框環帶(獎區扇形只填到 frame_ratio 對應
    的內側半徑,環帶本身填 gold 顏色),不給就跟原本一樣只在最外緣畫一條細外框線。
    bead_count(選用,搭配 frame_ratio 用):在外框環帶中線畫幾顆等間距白色圓珠裝飾。
    hub_ratio:中心鈕半徑佔整體半徑的比例,搭配 build_wheel_layer_masks() 拆圖層時務必用同一個值,
    否則遮罩邊界會跟這張範本對不齊。
    """
    validate_dimensions(width, height)
    _require_pillow()
    img = PILImage.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.45
    line_width = max(3, min(width, height) // 200)
    wedge_radius = radius * frame_ratio if frame_ratio else radius

    if frame_ratio:
        # 先畫滿版外框圓蓋住整個範圍,獎區扇形疊上去之後,外圍那圈環帶(wedge_radius~radius
        # 之間)自然只留下框色沒被蓋到,不用另外算環狀多邊形。
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=gold)

    for i in range(n_segments):
        a0 = 2 * math.pi * i / n_segments - math.pi / 2
        a1 = 2 * math.pi * (i + 1) / n_segments - math.pi / 2
        points = [(cx, cy)]
        for s in range(13):
            a = a0 + (a1 - a0) * s / 12
            points.append((cx + wedge_radius * math.cos(a), cy + wedge_radius * math.sin(a)))
        draw.polygon(points, fill=colors[i % len(colors)])

    if frame_ratio and bead_count:
        bead_r = (radius + wedge_radius) / 2
        bead_size = (radius - wedge_radius) * 0.35
        for i in range(bead_count):
            a = 2 * math.pi * i / bead_count
            bx = cx + bead_r * math.sin(a)
            by = cy - bead_r * math.cos(a)
            draw.ellipse([bx - bead_size, by - bead_size, bx + bead_size, by + bead_size], fill=(255, 255, 255))

    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=gold, width=line_width)
    for i in range(n_segments):
        angle = 2 * math.pi * i / n_segments
        x = cx + wedge_radius * math.sin(angle)
        y = cy - wedge_radius * math.cos(angle)
        draw.line([cx, cy, x, y], fill=gold, width=line_width)
    hub_radius = radius * hub_ratio
    draw.ellipse([cx - hub_radius, cy - hub_radius, cx + hub_radius, cy + hub_radius], fill=gold)
    return img


def build_wheel_layer_masks(width=1024, height=1024, frame_ratio=0.86, hub_ratio=0.22):
    """搭配 build_wheel_segment_template(frame_ratio=...) 產生的合成圖,回傳三張跟 layer_split
    格式相容的遮罩(RGBA,要保留進該圖層的區域 alpha=0,其餘 alpha=255):外框環帶、內部獎區、
    中心指針。frame_ratio/hub_ratio 務必跟產生合成圖時用的值一致,否則裁出來的圖層邊界會對不齊。

    中心指針的機關形狀(例如彈片)常常會伸出 hub 圓圈一小段延伸到獎區範圍,這裡刻意把
    hub_ratio 訂得比範本圖畫的中心鈕大一些(範本圖固定畫 0.12,這裡預設 0.22),
    讓指針延伸出去的部分還是被歸進指針圖層,不會被切給獎區圖層。
    """
    validate_dimensions(width, height)
    _require_pillow()
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.45
    wedge_radius = radius * frame_ratio
    hub_radius = radius * hub_ratio

    def _ring_mask(r_inner, r_outer):
        m = PILImage.new("RGBA", (width, height), (0, 0, 0, 255))
        d = ImageDraw.Draw(m)
        if r_outer > 0:
            d.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=(0, 0, 0, 0))
        if r_inner > 0:
            d.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=(0, 0, 0, 255))
        return m

    frame_mask = _ring_mask(wedge_radius, radius)
    prize_mask = _ring_mask(hub_radius, wedge_radius)
    pointer_mask = _ring_mask(0, hub_radius)
    return frame_mask, prize_mask, pointer_mask


def build_icon_asset(prompt, negative=None, width=1024, height=1024, seed=None, steps=25, cfg=7.0,
                      batch_size=1, lora_name=None, lora_strength=0.8,
                      structure_ref_filename=None, control_strength=STRUCTURE_REF_CONTROL_STRENGTH,
                      structure_ref_denoise=STRUCTURE_REF_DENOISE, checkpoint=None,
                      appearance_ref_filename=None, appearance_weight=0.8):
    validate_dimensions(width, height)
    validate_batch(batch_size)
    validate_lora_strength(lora_strength)
    validate_unit_interval(control_strength, "control_strength")
    validate_unit_interval(structure_ref_denoise, "structure_ref_denoise")
    validate_unit_interval(appearance_weight, "appearance_weight")
    if structure_ref_filename:
        require_sdxl_capability("icon_asset 的 structure-ref/ControlNet")
    if appearance_ref_filename:
        require_sdxl_capability("icon_asset 的 appearance-ref/IPAdapter")
    negative = (negative or DEFAULT_NEGATIVE) + ICON_ASSET_NEGATIVE_SUFFIX
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt + ICON_ASSET_PROMPT_SUFFIX, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
    })

    if appearance_ref_filename:
        # --appearance-ref:跟 guided_inpaint/style_lock 用同一顆 IPAdapter 模型,把「畫面看起來
        # 像哪張參考圖」的責任從純文字描述轉移到圖片級別的參考,對材質/質感這類文字講不清楚的
        # 特徵比較有效。套在 model_ref 上,KSampler 用的 model 要接這裡回傳的新參照,不要漏接。
        graph["1b2"] = {"class_type": "LoadImage", "inputs": {"image": appearance_ref_filename}}
        graph["1b3"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}}
        graph["1b4"] = {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}}
        graph["1b5"] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref, "ipadapter": ["1b4", 0], "image": ["1b2", 0], "clip_vision": ["1b3", 0],
                "weight": appearance_weight, "weight_type": "linear", "combine_embeds": "concat",
                "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only",
            },
        }
        model_ref = ["1b5", 0]

    if structure_ref_filename:
        # --structure-ref:img2img 吃範本圖當底(denoise < 1.0,結構/色塊配置繼承像素),
        # batch_size 在這個分支沒有作用(單張圖片編碼出來的 latent 本來就是 batch=1)。
        graph["4"] = {"class_type": "LoadImage", "inputs": {"image": structure_ref_filename}}
        graph["4z"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}}
        latent_ref = ["4z", 0]
        denoise = structure_ref_denoise
    else:
        graph["4"] = {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}}
        latent_ref = ["4", 0]
        denoise = 1.0

    positive_ref, negative_ref = ["2", 0], ["3", 0]
    if structure_ref_filename:
        graph["4c"] = build_control_preprocessor("canny", "4")
        graph["4d"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODELS["canny"]}}
        graph["4e"] = {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": positive_ref, "negative": negative_ref, "control_net": ["4d", 0], "image": ["4c", 0],
                "strength": control_strength, "start_percent": 0.0, "end_percent": 1.0,
            },
        }
        positive_ref, negative_ref = ["4e", 0], ["4e", 1]

    graph["5"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_ref, "positive": positive_ref, "negative": negative_ref, "latent_image": latent_ref,
            "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
            "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
        },
    }
    graph["6"] = {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}}
    graph["7"] = {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "icon_asset"}}
    return graph, "6"


# ---------- task: character_action(Ch7 ControlNet + Ch8 IPAdapter 合併)----------
def build_character_action(prompt, character_ref_filename, pose_ref_filename, negative=None,
                            width=None, height=None, seed=None, steps=25, cfg=7.0,
                            ip_weight=0.8, pose_strength=1.0, batch_size=1, control_type="canny",
                            lora_name=None, lora_strength=0.8, checkpoint=None):
    require_sdxl_capability("character_action (ControlNet/IPAdapter)")
    validate_dimensions(
        DEVICE["default_width"] if width is None else width,
        DEVICE["default_height"] if height is None else height,
    )
    width = DEVICE["default_width"] if width is None else width
    height = DEVICE["default_height"] if height is None else height
    validate_batch(batch_size)
    validate_unit_interval(ip_weight, "ip_weight")
    validate_unit_interval(pose_strength, "pose_strength")
    validate_lora_strength(lora_strength)
    negative = negative or DEFAULT_NEGATIVE
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
        "4": {"class_type": "LoadImage", "inputs": {"image": character_ref_filename}},
        "5": {"class_type": "LoadImage", "inputs": {"image": pose_ref_filename}},
        # 明確指定 IPAdapter 模型 + CLIP Vision 檔名,不用 IPAdapterUnifiedLoader 的自動猜測
        # (它的 preset 自動配對邏輯會挑到 bigG 版 CLIP Vision,跟我們裝的 ViT-H 版 IPAdapter 模型維度對不上)
        "6a": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}},
        "6b": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}},
        "7": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref, "ipadapter": ["6b", 0], "image": ["4", 0], "clip_vision": ["6a", 0],
                "weight": ip_weight, "weight_type": "linear", "combine_embeds": "concat",
                "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only",
            },
        },
        "8": build_control_preprocessor(control_type, "5"),
        "9": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODELS[control_type]}},
        "10": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["2", 0], "negative": ["3", 0], "control_net": ["9", 0], "image": ["8", 0],
                "strength": pose_strength, "start_percent": 0.0, "end_percent": 1.0,
            },
        },
        "11": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}},
        "12": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["7", 0], "positive": ["10", 0], "negative": ["10", 1], "latent_image": ["11", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}},
        "14": {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": "character_action"}},
    })
    return graph, "13"


# ---------- task: inpaint(Ch6:局部調整)----------
# 遮罩檔案格式陷阱(已實測踩過):ComfyUI 的 LoadImage 節點,MASK 輸出 = 1.0 - 圖片的 alpha 通道,
# 完全沒有 alpha 通道時會靜默回傳空白遮罩(不報錯,但整個遮罩失效,產出看起來幾乎跟原圖一樣)。
# 不是「白色區域=要重畫」的灰階慣例——要重畫的區域必須是 alpha=0(透明),要保留的區域 alpha=255。
# 如果不是透過 ComfyUI 的 MaskEditor 存檔(那個格式一定對),而是agent自己用程式產生遮罩,
# 務必存成帶 alpha 通道的 RGBA 圖,不要用 .convert('RGB') 之類的操作把 alpha 弄丟。
def build_inpaint(prompt, image_filename, mask_filename, negative=None, denoise=1.0,
                   seed=None, steps=25, cfg=7.0, grow_mask_by=6, checkpoint=None):
    validate_unit_interval(denoise, "denoise")
    negative = negative or DEFAULT_NEGATIVE
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "5": {"class_type": "LoadImage", "inputs": {"image": mask_filename}},
        "6": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {"pixels": ["4", 0], "vae": ["1", 2], "mask": ["5", 1], "grow_mask_by": grow_mask_by},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["6", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "inpaint"}},
    }, "8"


# ---------- task: guided_inpaint(局部重繪 + ControlNet 結構鎖定 + IPAdapter 外觀參考)----------
# 解決 inpaint 大範圍全自由重繪的失敗模式:遮罩範圍內同時要求「結構(手指關節/物體輪廓)
# 不能崩」跟「外觀(武器造型/材質紋路)要換」時,純 inpaint 沒有任何錨點,兩者一起賭,
# 失敗率會疊乘(2026-08-18 女角色武器置換連續失敗多次才確認這個問題,不是遮罩位置或
# prompt 措辭能解決的)。guided_inpaint 額外疊兩層可選的錨點:
#   - ControlNet(control_type 給了才接):遮罩範圍內結構被控制圖釘住——pose 用於手部/
#     肢體姿勢類需求(換武器同時保持握姿),canny/depth 用於物體輪廓/立體起伏類需求
#     (換材質紋路同時保持造型,例如龍鱗紋路、道具圖示材質變體)。control_ref 預設沿用
#     --image 本身(從同一張圖抽取結構)。
#   - IPAdapter(appearance_ref_filename 給了才接):外觀不再只靠文字描述,改用一張參考圖
#     的外觀特徵(2026-08-18 補上,因應「美術自己畫一張材質/紋理圖,要套到角色身上某個
#     部位」這類需求——純文字描述紋理細節通常描述不清楚,需要圖片級別的參考)。跟
#     style_lock/character_action 用同一顆 IPAdapter 模型,參考圖建議是乾淨的材質特寫
#     (不要整張場景圖),不然背景/光影會一起被帶進來污染結果,原則同 IPAdapter 角色參考
#     圖裁緊一點的教訓(見 skills/comfyui-art-gen/reference/ 內對應說明)。
# 兩層都可選、可以同時用、也可以都不用(退化成一般 inpaint 只是多繞一層)。
def build_guided_inpaint(prompt, image_filename, mask_filename, negative=None,
                          control_ref_filename=None, control_type=None, control_strength=1.0,
                          appearance_ref_filename=None, appearance_weight=0.8,
                          denoise=1.0, seed=None, steps=25, cfg=7.0, grow_mask_by=6, checkpoint=None):
    validate_unit_interval(denoise, "denoise")
    validate_unit_interval(control_strength, "control_strength")
    validate_unit_interval(appearance_weight, "appearance_weight")
    if control_type:
        require_sdxl_capability("guided_inpaint 的 ControlNet")
    if appearance_ref_filename:
        require_sdxl_capability("guided_inpaint 的 IPAdapter")
    negative = negative or DEFAULT_NEGATIVE
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "5": {"class_type": "LoadImage", "inputs": {"image": mask_filename}},
        "6": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {"pixels": ["4", 0], "vae": ["1", 2], "mask": ["5", 1], "grow_mask_by": grow_mask_by},
        },
    }

    model_ref = ["1", 0]
    if appearance_ref_filename:
        graph["7a"] = {"class_type": "LoadImage", "inputs": {"image": appearance_ref_filename}}
        graph["7b"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}}
        graph["7c"] = {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}}
        graph["7d"] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref, "ipadapter": ["7c", 0], "image": ["7a", 0], "clip_vision": ["7b", 0],
                "weight": appearance_weight, "weight_type": "linear", "combine_embeds": "concat",
                "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only",
            },
        }
        model_ref = ["7d", 0]

    positive_ref, negative_ref = ["2", 0], ["3", 0]
    if control_type:
        graph["8"] = {"class_type": "LoadImage", "inputs": {"image": control_ref_filename or image_filename}}
        graph["9"] = build_control_preprocessor(control_type, "8")
        graph["10"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODELS[control_type]}}
        graph["11"] = {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": positive_ref, "negative": negative_ref, "control_net": ["10", 0], "image": ["9", 0],
                "strength": control_strength, "start_percent": 0.0, "end_percent": 1.0,
            },
        }
        positive_ref, negative_ref = ["11", 0], ["11", 1]

    graph["12"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_ref, "positive": positive_ref, "negative": negative_ref, "latent_image": ["6", 0],
            "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
            "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
        },
    }
    graph["13"] = {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}}
    graph["14"] = {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": "guided_inpaint"}}
    return graph, "13"


# ---------- task: pose_only(Ch7:單獨 ControlNet,不鎖角色)----------
def build_pose_only(prompt, pose_ref_filename, negative=None, width=None, height=None,
                     seed=None, steps=25, cfg=7.0, pose_strength=1.0, batch_size=1,
                     control_type="canny", lora_name=None, lora_strength=0.8, checkpoint=None):
    require_sdxl_capability("pose_only (ControlNet)")
    width = DEVICE["default_width"] if width is None else width
    height = DEVICE["default_height"] if height is None else height
    validate_dimensions(width, height)
    validate_batch(batch_size)
    validate_unit_interval(pose_strength, "pose_strength")
    validate_lora_strength(lora_strength)
    negative = negative or DEFAULT_NEGATIVE
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
        "4": {"class_type": "LoadImage", "inputs": {"image": pose_ref_filename}},
        "5": build_control_preprocessor(control_type, "4"),
        "6": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODELS[control_type]}},
        "7": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["2", 0], "negative": ["3", 0], "control_net": ["6", 0], "image": ["5", 0],
                "strength": pose_strength, "start_percent": 0.0, "end_percent": 1.0,
            },
        },
        "8": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}},
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": model_ref, "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["8", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "pose_only"}},
    })
    return graph, "10"


# ---------- task: style_lock(Ch8:單獨 IPAdapter,不鎖姿勢)----------
def build_style_lock(prompt, character_ref_filename, negative=None, width=None, height=None,
                      seed=None, steps=25, cfg=7.0, ip_weight=0.8, batch_size=1,
                      lora_name=None, lora_strength=0.8, checkpoint=None):
    require_sdxl_capability("style_lock (IPAdapter)")
    width = DEVICE["default_width"] if width is None else width
    height = DEVICE["default_height"] if height is None else height
    validate_dimensions(width, height)
    validate_batch(batch_size)
    validate_unit_interval(ip_weight, "ip_weight")
    validate_lora_strength(lora_strength)
    negative = negative or DEFAULT_NEGATIVE
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
        "4": {"class_type": "LoadImage", "inputs": {"image": character_ref_filename}},
        "5": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}},
        "6": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}},
        "7": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref, "ipadapter": ["6", 0], "image": ["4", 0], "clip_vision": ["5", 0],
                "weight": ip_weight, "weight_type": "linear", "combine_embeds": "concat",
                "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only",
            },
        },
        "8": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}},
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["7", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["8", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "style_lock"}},
    })
    return graph, "10"


# ---------- task: refine(Ch5:圖生圖,草稿精緻化/材質變體)----------
def build_refine(prompt, image_filename, negative=None, denoise=0.6,
                  seed=None, steps=25, cfg=7.0, checkpoint=None):
    validate_unit_interval(denoise, "denoise")
    negative = negative or DEFAULT_NEGATIVE
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["5", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "refine"}},
    }, "7"


# ---------- task: upscale(放大精修:放大模型 + 二次 KSampler 補細節)----------
UPSCALE_MODEL = "4x-UltraSharp.pth"  # 4 倍放大模型,scale 參數透過 ImageScaleBy 縮回使用者要的倍率


def build_upscale(prompt, image_filename, negative=None, scale=2.0, denoise=0.4,
                   seed=None, steps=25, cfg=7.0, checkpoint=None):
    validate_scale(scale)
    validate_unit_interval(denoise, "denoise")
    negative = negative or DEFAULT_NEGATIVE
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "5": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALE_MODEL}},
        "6": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["5", 0], "image": ["4", 0]}},
        # UPSCALE_MODEL 固定放大 4 倍,這裡再縮回使用者要的實際倍率(scale/4),避免要另外讀原圖尺寸算絕對像素
        "7": {
            "class_type": "ImageScaleBy",
            "inputs": {"image": ["6", 0], "upscale_method": "lanczos", "scale_by": scale / 4.0},
        },
        "8": {"class_type": "VAEEncode", "inputs": {"pixels": ["7", 0], "vae": ["1", 2]}},
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["8", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            },
        },
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "upscale"}},
    }, "10"


def build_layer_split(image_filename, mask_filename, layer_name):
    """把一張已經畫好的完成圖,依遮罩切成一張跟原圖等尺寸/位置對齊的透明圖層。

    不重新生成畫面內容,純粹是既有圖片的透明度裁切——用於複合式 UI 元件(例如轉盤的外框/
    中心鈕)已經有一張定稿合成圖,想事後切出幾個大塊區域各自疊放/調色的情境。遮罩 alpha
    慣例沿用既有 inpaint/guided_inpaint 那一套(見 skills/comfyui-art-gen/reference/masking.md):
    alpha=0 的區域 = 要保留進這一層,alpha=255 = 不屬於這一層。

    節點邏輯跟 attach_bg_removal() 是同一招:LoadImage 的 MASK 輸出是「1 − alpha」,也就是
    alpha=0(要保留的區域)對應 mask=1;但 JoinImageWithAlpha 內部會把傳入的 alpha 再做一次
    `1 − x` 換算,兩次換算方向相反,所以中間一樣要插 InvertMask,才能讓「mask=1(要保留)」
    最終變成「輸出 alpha=1(不透明)」。
    """
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "2": {"class_type": "LoadImage", "inputs": {"image": mask_filename}},
        "3": {"class_type": "InvertMask", "inputs": {"mask": ["2", 1]}},
        "4": {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["1", 0], "alpha": ["3", 0]}},
        "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": f"layer_{layer_name}"}},
    }, "4"


def backend_has(backend, cap):
    return cap in VIDEO_BACKEND_CAPS.get(backend, ())


def require_video_backend(task, backend):
    """task 要的能力這個 backend 若還沒接,直接說,不要改成另一個 task、也不要假裝跑過。
    若呼叫端沒寫 --backend、而預設又還沒接、且全場只剩一個實作,就改走那個(task 契約不變)。"""
    if backend not in VIDEO_BACKENDS:
        raise SystemExit(f"未知 --backend {backend!r},可用: {', '.join(VIDEO_BACKENDS)}")
    need = VIDEO_TASK_CAPS.get(task)
    if need and not backend_has(backend, need):
        ok = [b for b, caps in VIDEO_BACKEND_CAPS.items() if need in caps]
        explicit = any(a == "--backend" or a.startswith("--backend=") for a in sys.argv)
        if not explicit and len(ok) == 1:
            print(
                f"[backend] {task} 目前只有 {ok[0]} 實作,改走 {ok[0]}(預設 {backend} 還沒接)",
                file=sys.stderr,
            )
            return ok[0]
        raise SystemExit(
            f"{task} 目前沒有 {backend} 實作(缺 {need})。"
            f"可用: {', '.join(ok) or '無'}。"
            f"不要因此改 task 名稱;接上這個 backend 之後同一個 CLI 就能跑。"
        )
    return backend


def run_i2v(backend, prompt, image_filename, width, height, seed, duration,
            last_image_filename=None, filename_prefix="img2video", negative=None):
    """I2V 的 backend 入口。main() 不要自己挑 graph。"""
    if backend == "wan":
        return build_img2video_wan(
            prompt, image_filename, negative=negative,
            width=width, height=height, seed=seed, duration=duration,
            filename_prefix=filename_prefix,
        )
    if backend == "h3":
        return build_img2video_h3(
            prompt, image_filename, width=width, height=height,
            seed=seed, duration=duration, last_image_filename=last_image_filename,
            filename_prefix=filename_prefix,
        )
    raise SystemExit(f"未知 --backend {backend!r}")


def run_character_video(backend, prompt, ref_filenames, width, height, seed, duration,
                        filename_prefix="character_video"):
    if backend == "h3":
        return build_character_video_h3(
            prompt, ref_filenames, width=width, height=height,
            seed=seed, duration=duration, filename_prefix=filename_prefix,
        )
    raise SystemExit(f"character_video 目前沒有 {backend} 實作")


def run_pose_drive(backend, prompt, image_filename, motion_filename, width, height, seed,
                   duration, control_type="pose", filename_prefix="pose_drive", negative=None):
    if backend == "h3":
        return build_pose_drive_h3(
            prompt, image_filename, motion_filename, width=width, height=height,
            seed=seed, duration=duration, control_type=control_type,
            filename_prefix=filename_prefix,
        )
    if backend == "wan":
        return build_pose_drive_wan(
            prompt, image_filename, motion_filename, width=width, height=height,
            seed=seed, duration=duration, control_type=control_type,
            filename_prefix=filename_prefix, negative=negative,
        )
    raise SystemExit(f"pose_drive 目前沒有 {backend} 實作")


def _require_video_duration(duration):
    if not (VIDEO_DURATION_MIN <= duration <= VIDEO_DURATION_MAX):
        raise SystemExit(
            f"--duration 鎖在 {VIDEO_DURATION_MIN}~{VIDEO_DURATION_MAX} 秒,"
            f"更長請拆成多個鏡頭(目前給的是 {duration})。"
        )
    return duration


def _require_wh_pair(args):
    if (getattr(args, "width", None) is None) ^ (getattr(args, "height", None) is None):
        raise SystemExit("--width 跟 --height 要一起給,或兩個都不給(跟來源圖比例走)。")


def video_canvas(image_path, width=None, height=None):
    _require_pillow()
    """把輸出畫布收到 VIDEO_MAX_SIDE 以內、且寬高都是 32 的倍數。
    不給寬高就跟來源圖比例走(先縮最長邊)。16GB 實測只鎖到 768,再大要另測。"""
    if width and height:
        src_w, src_h = width, height
    else:
        with PILImage.open(image_path) as im:
            src_w, src_h = im.size
    long_side = max(src_w, src_h)
    scale = min(1.0, VIDEO_MAX_SIDE / float(long_side))
    w = max(32, int(src_w * scale) // 32 * 32)
    h = max(32, int(src_h * scale) // 32 * 32)
    return w, h


def wan_frame_count(duration_sec):
    """Wan22ImageToVideoLatent 的 length 是 4k+1(預設 49)。"""
    target = int(round(duration_sec * VIDEO_FPS))
    k = max(2, int(round((target - 1) / 4.0)))
    return k * 4 + 1


def h3_frame_count(duration_sec):
    """MiniMaxH3ImageToVideo 的 length 要落在 17k+5(官方 Math Expression)。"""
    x = max(5, int(round(duration_sec * VIDEO_FPS)))
    return x + (5 - (x % 17)) % 17


def build_img2video_wan(prompt, image_filename, negative=None, width=832, height=480,
                        seed=None, duration=2.0, filename_prefix="img2video"):
    seed = seed_or_random(seed)
    length = wan_frame_count(duration)
    negative = negative or VIDEO_NEG_DEFAULT
    g = {
        "37": {"class_type": "UNETLoader", "inputs": {
            "unet_name": VIDEO_WAN_UNET, "weight_dtype": "default"}},
        "38": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": VIDEO_WAN_CLIP, "type": "wan", "device": "default"}},
        "39": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_WAN_VAE}},
        "48": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["37", 0], "shift": 8.0}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["38", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["38", 0]}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "55": {"class_type": "Wan22ImageToVideoLatent", "inputs": {
            "vae": ["39", 0], "start_image": ["56", 0],
            "width": width, "height": height, "length": length, "batch_size": 1}},
        "3": {"class_type": "KSampler", "inputs": {
            "model": ["48", 0], "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["55", 0], "seed": seed, "steps": VIDEO_STEPS, "cfg": 5.0,
            "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["39", 0]}},
        "57": {"class_type": "CreateVideo", "inputs": {"images": ["8", 0], "fps": float(VIDEO_FPS)}},
        "58": {"class_type": "SaveVideo", "inputs": {
            "video": ["57", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "58"


def build_pose_drive_wan(prompt, image_filename, motion_filename, width=768, height=768,
                         seed=None, duration=2.0, control_type="pose",
                         filename_prefix="pose_drive", negative=None):
    """pose_drive 的 wan 實作:Fun Control 5B,角色靜幀當 ref_image,動作影片抽幀後走 canny/pose/depth。
    跟 I2V 用的 TI2V 5B 是不同 UNET,task 層不要寫這個檔名。"""
    seed = seed_or_random(seed)
    length = wan_frame_count(duration)
    negative = negative or VIDEO_NEG_DEFAULT
    g = {
        "37": {"class_type": "UNETLoader", "inputs": {
            "unet_name": VIDEO_WAN_FUN_UNET, "weight_dtype": "default"}},
        "38": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": VIDEO_WAN_CLIP, "type": "wan", "device": "default"}},
        "39": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_WAN_VAE}},
        "48": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["37", 0], "shift": 8.0}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["38", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["38", 0]}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "80": {"class_type": "LoadVideo", "inputs": {"file": motion_filename}},
        "81": {"class_type": "GetVideoComponents", "inputs": {"video": ["80", 0]}},
        "82": build_control_preprocessor(control_type, "81"),
        "55": {"class_type": "Wan22FunControlToVideo", "inputs": {
            "positive": ["6", 0], "negative": ["7", 0], "vae": ["39", 0],
            "width": width, "height": height, "length": length, "batch_size": 1,
            "ref_image": ["56", 0], "control_video": ["82", 0]}},
        "3": {"class_type": "KSampler", "inputs": {
            "model": ["48", 0], "positive": ["55", 0], "negative": ["55", 1],
            "latent_image": ["55", 2], "seed": seed, "steps": VIDEO_STEPS, "cfg": 5.0,
            "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["39", 0]}},
        "57": {"class_type": "CreateVideo", "inputs": {"images": ["8", 0], "fps": float(VIDEO_FPS)}},
        "58": {"class_type": "SaveVideo", "inputs": {
            "video": ["57", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "58"


def extract_video_frames(video_path, output_dir=None):
    """把 mp4 抽成 png 序列,給遊戲引擎用。依賴 ComfyUI 環境裡的 av。"""
    import av
    output_dir = output_dir or os.path.dirname(os.path.abspath(video_path))
    # SaveVideo 常吐 foo_00001_.mp4,直接加 _frames 會變成 foo_00001__frames。
    stem = os.path.splitext(os.path.basename(video_path))[0].rstrip("_")
    frame_dir = os.path.join(output_dir, stem + "_frames")
    os.makedirs(frame_dir, exist_ok=True)
    container = av.open(video_path)
    paths = []
    for i, frame in enumerate(container.decode(video=0)):
        p = os.path.join(frame_dir, f"{i:03d}.png")
        frame.to_image().save(p)
        paths.append(p)
    container.close()
    print(f"[抽幀] {len(paths)} 張 -> {frame_dir}")
    return paths, frame_dir


def extract_last_frame(video_path, dest_path):
    """clip_extend:上一鏡最後一幀當下一鏡靜幀。"""
    import av
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)) or ".", exist_ok=True)
    container = av.open(video_path)
    last = None
    for frame in container.decode(video=0):
        last = frame
    container.close()
    if last is None:
        raise RuntimeError(f"影片沒有畫面: {video_path}")
    last.to_image().save(dest_path)
    return dest_path


def concat_videos(video_paths, dest_path):
    """外部組裝短過場。解析度/fps 跟第一支對齊,必要時重編碼。不是剪接台。
    每支都有音軌才把立體聲接上去;有任何一支無聲就整段當無聲,
    不要一半有聲一半靜音造成時間軸錯位。"""
    _require_pillow()
    import av
    if len(video_paths) < 2:
        raise RuntimeError("video_concat 至少要兩支影片")
    first = av.open(video_paths[0])
    vs = first.streams.video[0]
    width, height = vs.width, vs.height
    fps = vs.average_rate or VIDEO_FPS
    first.close()
    keep_audio = True
    for src in video_paths:
        inp = av.open(src)
        if not inp.streams.audio:
            keep_audio = False
        inp.close()
        if not keep_audio:
            break
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)) or ".", exist_ok=True)
    out = av.open(dest_path, "w")
    out_v = out.add_stream("libx264", rate=fps)
    out_v.width = width
    out_v.height = height
    out_v.pix_fmt = "yuv420p"
    # 兩個 stream 都要在寫任何 packet 之前建好,不然 mp4 mux 會 EINVAL
    out_a = out.add_stream("aac", rate=32000) if keep_audio else None
    for src in video_paths:
        inp = av.open(src)
        for frame in inp.decode(video=0):
            img = frame.to_image()
            if img.size != (width, height):
                img = img.resize((width, height), PILImage.Resampling.LANCZOS)
            of = av.VideoFrame.from_image(img)
            for packet in out_v.encode(of):
                out.mux(packet)
        inp.close()
    for packet in out_v.encode():
        out.mux(packet)
    if out_a:
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=32000)
        sample_i = 0
        for src in video_paths:
            ain = av.open(src)
            frames_in = list(ain.decode(audio=0))
            ain.close()
            frames_in.append(None)
            for frame in frames_in:
                resampled = resampler.resample(frame) or []
                if not isinstance(resampled, (list, tuple)):
                    resampled = [resampled]
                for rf in resampled:
                    if rf is None:
                        continue
                    rf.pts = sample_i
                    sample_i += rf.samples
                    for packet in out_a.encode(rf) or []:
                        out.mux(packet)
        for packet in out_a.encode(None) or []:
            out.mux(packet)
    out.close()
    note = "含立體聲" if keep_audio else "無聲(有鏡頭沒有音軌,整段不接聲音)"
    print(f"[接片] {len(video_paths)} 支 -> {dest_path} ({note})")
    return dest_path


def build_img2video_h3(prompt, image_filename, width=768, height=768, seed=None, duration=2.0,
                       last_image_filename=None, filename_prefix="img2video"):
    seed = seed_or_random(seed)
    length = h3_frame_count(duration)
    g = {
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": VIDEO_H3_UNET, "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": VIDEO_H3_CLIP, "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_H3_VAE}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_H3_AUDIO_VAE}},
        "shift": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "104": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["13", 0], "vae": ["11", 0], "first_frame": ["56", 0],
            "prompt": prompt, "width": width, "height": height, "length": length}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {
            "model": ["shift", 0], "scheduler": "simple", "steps": VIDEO_STEPS, "denoise": 1.0}},
        "16": {"class_type": "BasicGuider", "inputs": {
            "model": ["shift", 0], "conditioning": ["104", 0]}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
            "sigmas": ["9", 0], "latent_image": ["104", 1]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["11", 0]}},
        "23": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["24", 0]}},
        "91": {"class_type": "CreateVideo", "inputs": {
            "images": ["10", 0], "audio": ["23", 0], "fps": float(VIDEO_FPS), "bit_depth": 8}},
        "92": {"class_type": "SaveVideo", "inputs": {
            "video": ["91", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    if last_image_filename:
        g["56b"] = {"class_type": "LoadImage", "inputs": {"image": last_image_filename}}
        g["104"]["inputs"]["last_frame"] = ["56b", 0]
    return g, "92"


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


def build_character_video_h3(prompt, ref_filenames, width=768, height=768, seed=None, duration=2.0,
                             filename_prefix="character_video"):
    """character_video 的 h3 實作(Ref2VA)。task 契約見 run_character_video,不要從 main 直接叫這個。
    ref_image_size 鎖 match;官方 max 保身份更好但每個 step 都帶參考 token,16GB 上沒實測過不開旗標。
    """
    if not (1 <= len(ref_filenames) <= CHARACTER_REF_MAX):
        raise ValueError(
            f"character_video 要 1~{CHARACTER_REF_MAX} 張參考圖,目前 {len(ref_filenames)}"
        )
    seed = seed_or_random(seed)
    length = h3_frame_count(duration)
    prompt = h3_ref_prompt(prompt, len(ref_filenames))
    g = {
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": VIDEO_H3_REF_UNET, "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": VIDEO_H3_CLIP, "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_H3_VAE}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_H3_AUDIO_VAE}},
        "shift": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "104": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
            "clip": ["13", 0], "vae": ["11", 0], "audio_vae": ["24", 0],
            "prompt": prompt, "width": width, "height": height, "length": length,
            "ref_image_size": "match"}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {
            "model": ["shift", 0], "scheduler": "simple", "steps": VIDEO_STEPS, "denoise": 1.0}},
        "16": {"class_type": "BasicGuider", "inputs": {
            "model": ["shift", 0], "conditioning": ["104", 0]}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
            "sigmas": ["9", 0], "latent_image": ["104", 1]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["11", 0]}},
        "23": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["24", 0]}},
        "91": {"class_type": "CreateVideo", "inputs": {
            "images": ["10", 0], "audio": ["23", 0], "fps": float(VIDEO_FPS), "bit_depth": 8}},
        "92": {"class_type": "SaveVideo", "inputs": {
            "video": ["91", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    for i, fn in enumerate(ref_filenames):
        nid = f"56r{i}"
        g[nid] = {"class_type": "LoadImage", "inputs": {"image": fn}}
        g["104"]["inputs"][f"ref_images.ref_image_{i}"] = [nid, 0]
    return g, "92"


def build_pose_drive_h3(prompt, image_filename, motion_filename, width=768, height=768,
                        seed=None, duration=2.0, control_type="pose",
                        filename_prefix="pose_drive"):
    """pose_drive 的 h3 實作:同一顆 Ref2VA,角色靜幀當 ref_image_0,動作片抽幀後走 pose/canny/depth 當 ref_video_0。
    ComfyUI 0.34.0 沒有 MiniMaxH3FunControlNetApply(PR #15860 還沒進),所以不是真正的 ControlNet Union;
    預處理動作片是為了不要把動作片裡那個人的臉漏進輸出。身份鎖比 wan Fun Control 穩,但仍不是像素鎖臉。
    負向詞這顆沒入口,呼叫端給了也忽略。"""
    seed = seed_or_random(seed)
    length = h3_frame_count(duration)
    prompt = h3_pose_drive_prompt(prompt)
    g = {
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": VIDEO_H3_REF_UNET, "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": VIDEO_H3_CLIP, "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_H3_VAE}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_H3_AUDIO_VAE}},
        "shift": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "80": {"class_type": "LoadVideo", "inputs": {"file": motion_filename}},
        "81": {"class_type": "GetVideoComponents", "inputs": {"video": ["80", 0]}},
        "82": build_control_preprocessor(control_type, "81"),
        "104": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
            "clip": ["13", 0], "vae": ["11", 0], "audio_vae": ["24", 0],
            "prompt": prompt, "width": width, "height": height, "length": length,
            "ref_image_size": "match",
            "ref_images.ref_image_0": ["56", 0],
            "ref_videos.ref_video_0": ["82", 0]}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {
            "model": ["shift", 0], "scheduler": "simple", "steps": VIDEO_STEPS, "denoise": 1.0}},
        "16": {"class_type": "BasicGuider", "inputs": {
            "model": ["shift", 0], "conditioning": ["104", 0]}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
            "sigmas": ["9", 0], "latent_image": ["104", 1]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["11", 0]}},
        "23": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["24", 0]}},
        "91": {"class_type": "CreateVideo", "inputs": {
            "images": ["10", 0], "audio": ["23", 0], "fps": float(VIDEO_FPS), "bit_depth": 8}},
        "92": {"class_type": "SaveVideo", "inputs": {
            "video": ["91", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "92"


def attach_bg_removal(prompt, image_node_id):
    """在既有 graph 後面接上去背,回傳新增節點後的 SaveImage 節點 id(RGBA)。

    RemoveBackground 輸出的 MASK 是「1=前景主體」,但 JoinImageWithAlpha 內部會把傳入的
    alpha 做 `1 - mask` 換算(慣例是 ComfyUI 的 MASK 語意「1=要挖掉的區域」),兩者語意相反,
    直接接會讓主體被挖空、背景保留——踩過一次的坑,照 ComfyUI 官方 blueprint
    「Remove Background (BiRefNet)」的做法,中間要插一個 InvertMask 反轉語意。

    節點 id 只能挑純數字的 key 取最大值——這個 graph 裡的節點 id 不保證全是純數字字串(例如
    LoraLoader 固定用 "1b"、icon_asset 的 ControlNet 分支用 "4a"/"4b"/"4c"),對這些 key 呼叫
    int() 會直接噴例外,踩過一次(--wheel-segments 8 --remove-bg 疊加時發現)。
    """
    next_id = str(max(int(k) for k in prompt.keys() if k.isdigit()) + 1)
    n1, n2, n3, n4 = next_id, str(int(next_id) + 1), str(int(next_id) + 2), str(int(next_id) + 3)
    prompt[n1] = {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}}
    prompt[n2] = {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": [n1, 0], "image": [image_node_id, 0]}}
    prompt[n3] = {"class_type": "InvertMask", "inputs": {"mask": [n2, 0]}}
    prompt[n4] = {"class_type": "JoinImageWithAlpha", "inputs": {"image": [image_node_id, 0], "alpha": [n3, 0]}}
    save_id = str(int(n4) + 1)
    prompt[save_id] = {"class_type": "SaveImage", "inputs": {"images": [n4, 0], "filename_prefix": "transparent"}}
    return save_id


def _add_runtime_arguments(parser):
    """Add runtime options to both root and subparser for ergonomic placement."""
    parser.add_argument(
        "--comfy-url", dest="comfy_url", default=argparse.SUPPRESS,
        help="ComfyUI base URL；優先於 COMFY_URL/COMFYUI_URL 與 --config。",
    )
    parser.add_argument(
        "--config", "--runtime-config", dest="config_path", default=argparse.SUPPRESS,
        help="明確指定含 comfyui_url 的 runtime JSON（不會自動搜尋 repo local_config.json）。",
    )
    parser.add_argument(
        "--timeout", type=float, default=argparse.SUPPRESS,
        help=(f"prompt 送達後輪詢生成結果的秒數上限；圖片預設 {DEFAULT_TIMEOUT:g}，"
              f"影片預設 {DEFAULT_VIDEO_TIMEOUT:g}。"),
    )


def _validate_cli_args(args):
    default_timeout = DEFAULT_VIDEO_TIMEOUT if args.task in VIDEO_TASK_CAPS else DEFAULT_TIMEOUT
    args.timeout = getattr(args, "timeout", default_timeout)
    validate_timeout(args.timeout)
    if args.task in {"concept", "icon_asset", "character_action", "pose_only", "style_lock"}:
        validate_batch(args.batch)
        validate_lora_strength(args.lora_strength)
    if args.task in {"concept", "character_action", "pose_only", "style_lock", "icon_asset"}:
        validate_dimensions(args.width, args.height)
    if args.task in {"inpaint", "guided_inpaint", "refine", "upscale"}:
        validate_unit_interval(args.denoise, "denoise")
    if args.task == "upscale":
        validate_scale(args.scale)
    if args.task in {"character_action", "style_lock"}:
        validate_unit_interval(args.ip_weight, "ip_weight")
    if args.task in {"character_action", "pose_only"}:
        validate_unit_interval(args.pose_strength, "pose_strength")
    if args.task == "icon_asset":
        validate_unit_interval(args.appearance_weight, "appearance_weight")
    if args.task == "guided_inpaint":
        validate_unit_interval(args.control_strength, "control_strength")
        validate_unit_interval(args.appearance_weight, "appearance_weight")
    if args.task in VIDEO_TASK_CAPS and args.width is not None and args.height is not None:
        validate_dimensions(args.width, args.height)


def _validate_task_capabilities(args):
    try:
        if args.task == "character_action":
            require_sdxl_capability("character_action (ControlNet/IPAdapter)")
        elif args.task == "pose_only":
            require_sdxl_capability("pose_only (ControlNet)")
        elif args.task == "style_lock":
            require_sdxl_capability("style_lock (IPAdapter)")
        elif args.task == "icon_asset":
            if args.structure_ref:
                require_sdxl_capability("icon_asset 的 structure-ref/ControlNet")
            if args.appearance_ref:
                require_sdxl_capability("icon_asset 的 appearance-ref/IPAdapter")
        elif args.task == "guided_inpaint":
            if args.control_type:
                require_sdxl_capability("guided_inpaint 的 ControlNet")
            if args.appearance_ref:
                require_sdxl_capability("guided_inpaint 的 IPAdapter")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


def main(argv=None):
    ap = argparse.ArgumentParser(description="穩定產圖核心腳本")
    _add_runtime_arguments(ap)
    sub = ap.add_subparsers(dest="task", required=True)

    # 共用參數:每個 task 都能指定成品要存去哪(不指定就用預設的 tools/generated/)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-dir", help=f"成品存放資料夾,預設 {OUTPUT_DIR}")
    _add_runtime_arguments(common)

    # 會用到底模 checkpoint 的 task 額外共用 --style(layer_split 純裁切、不吃底模,不套用這組)
    model_common = argparse.ArgumentParser(add_help=False, parents=[common])
    model_common.add_argument(
        "--style", choices=list(STYLE_CHECKPOINTS),
        help="換一顆風格底模(選配,不給就用這台機器裝機時鎖定的預設 checkpoint)。"
             "realistic=寫實(Juggernaut XL)、illustration=插畫/概念藝術(Illustrious XL)、"
             "anime=二次元/動漫(Pony Diffusion V6 XL)。需要先在這台機器裝好對應 checkpoint,"
             "見 skills/comfyui-install/reference/models.md;只支援 SDXL 家族 tier。",
    )
    model_common.add_argument(
        "--rating", choices=["safe", "questionable", "explicit"],
        help="內容分級標籤(選配,不給就不加任何分級標籤,prompt 完全不變)。"
             "只在 --style anime/illustration 時有意義——這兩顆底模訓練時就用分級標籤控制內容尺度,"
             "不是這裡另外加的過濾機制;--style realistic 或不給 --style 時使用這個選項會直接報錯。",
    )

    # 有 --prompt 的 task(全部除了 layer_split)都共用 --negative/--seed
    prompt_common = argparse.ArgumentParser(add_help=False, parents=[model_common])
    prompt_common.add_argument("--negative")
    prompt_common.add_argument("--seed", type=int)

    # 從零/從參考圖生成的探索型 task(concept/icon_asset/character_action/pose_only/style_lock)
    # 才支援「多生幾版比較」跟套 LoRA——inpaint/guided_inpaint/refine/upscale 是修改既有圖片,
    # 這兩個概念對它們沒有意義,不要因為想共用參數就硬塞給不適用的 task
    batch_lora_common = argparse.ArgumentParser(add_help=False, parents=[prompt_common])
    batch_lora_common.add_argument("--batch", type=int, default=1, help="一次生成幾個版本比較")
    batch_lora_common.add_argument("--lora", help="LoRA 檔名(models/loras/ 底下),不給就不套用")
    batch_lora_common.add_argument("--lora-strength", type=float, default=0.8)

    p_concept = sub.add_parser("concept", help="概念圖(純文字)", parents=[batch_lora_common])
    p_concept.add_argument("--prompt", required=True)
    p_concept.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_concept.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_concept.add_argument("--remove-bg", action="store_true")

    p_icon = sub.add_parser("icon_asset", help="單一小型 UI 圖示/物件素材(不是整個 UI 畫面),永遠去背輸出透明背景", parents=[batch_lora_common])
    p_icon.add_argument("--prompt", required=True)
    p_icon.add_argument("--width", type=int, default=1024)
    p_icon.add_argument("--height", type=int, default=1024)
    p_icon.add_argument("--structure-ref", help="這個圖示的結構/色塊配置已經有明確答案、不該讓 AI 自己瞎猜時用(例如放射狀精準等分):給一張範本圖路徑,用 img2img + Canny ControlNet 把結構跟顏色配置都鎖住,SDXL 只負責疊材質/光澤;不給就跟以前一樣純靠文字描述。範本圖從哪來見 skills/comfyui-art-gen/reference/structure-ref.md")
    p_icon.add_argument("--appearance-ref", help="外觀參考圖路徑(選用,例如使用者提供的一張成品圖,想讓畫面材質/質感偏向那張圖)——用 IPAdapter,不給就純靠文字描述外觀,原則同 guided_inpaint 的 --appearance-ref")
    p_icon.add_argument("--appearance-weight", type=float, default=0.8, help="外觀參考圖的貼合強度,原則同 --ip-weight")

    p_char = sub.add_parser("character_action", help="角色動作圖(角色參考圖 + 姿勢線稿)", parents=[batch_lora_common])
    p_char.add_argument("--prompt", required=True)
    p_char.add_argument("--character-ref", required=True, help="角色參考圖路徑")
    p_char.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_char.add_argument("--ip-weight", type=float, default=0.8)
    p_char.add_argument("--pose-strength", type=float, default=1.0)
    p_char.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="姿勢/構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_char.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_char.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_char.add_argument("--remove-bg", action="store_true")

    p_inpaint = sub.add_parser("inpaint", help="局部調整(需要來源圖 + 遮罩圖)", parents=[prompt_common])
    p_inpaint.add_argument("--prompt", required=True)
    p_inpaint.add_argument("--image", required=True, help="來源圖路徑")
    p_inpaint.add_argument("--mask", required=True, help="遮罩圖路徑(需帶 alpha 通道,要重畫的區域 alpha=0/透明,其餘 alpha=255/不透明——用 ComfyUI MaskEditor 存的檔案格式一定對)")
    p_inpaint.add_argument("--denoise", type=float, default=1.0)

    p_guided = sub.add_parser(
        "guided_inpaint",
        help="局部重繪 + 結構鎖定/外觀參考圖(遮罩範圍內可選擇鎖住結構、可選擇用一張圖決定外觀,而不是只能靠文字描述;用於換武器/道具但要保持握姿、套用美術自畫材質紋理這類需求)",
        parents=[prompt_common],
    )
    p_guided.add_argument("--prompt", required=True)
    p_guided.add_argument("--image", required=True, help="來源圖路徑")
    p_guided.add_argument("--mask", required=True, help="遮罩圖路徑(同 inpaint,需帶 alpha 通道,要重畫的區域 alpha=0)")
    p_guided.add_argument("--control-ref", help="結構引導來源圖路徑,不給就用 --image 本身(從同一張圖抽取結構);沒給 --control-type 的話這個參數沒作用")
    p_guided.add_argument("--control-type", choices=["canny", "pose", "depth"],
                           help="要鎖定的結構類型(選用,不給就不鎖結構):pose=骨架關節(手部/肢體動作類需求),canny=輪廓邊緣、depth=立體起伏(材質/紋路類需求)")
    p_guided.add_argument("--control-strength", type=float, default=1.0)
    p_guided.add_argument("--appearance-ref", help="外觀參考圖路徑(選用,例如美術自己畫的材質/紋理圖)——不給就純靠文字描述外觀。建議用乾淨的材質特寫,不要整張場景圖,不然背景/光影會一起被帶進來")
    p_guided.add_argument("--appearance-weight", type=float, default=0.8, help="外觀參考圖的貼合強度,原則同 --ip-weight")
    p_guided.add_argument("--denoise", type=float, default=1.0)

    p_pose = sub.add_parser("pose_only", help="單獨用姿勢/線稿控制構圖,不鎖角色一致性", parents=[batch_lora_common])
    p_pose.add_argument("--prompt", required=True)
    p_pose.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_pose.add_argument("--pose-strength", type=float, default=1.0)
    p_pose.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_pose.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_pose.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_pose.add_argument("--remove-bg", action="store_true")

    p_style = sub.add_parser("style_lock", help="單獨鎖角色/風格一致性,姿勢隨意(不需要姿勢參考圖)", parents=[batch_lora_common])
    p_style.add_argument("--prompt", required=True)
    p_style.add_argument("--character-ref", required=True, help="角色/風格參考圖路徑")
    p_style.add_argument("--ip-weight", type=float, default=0.8)
    p_style.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_style.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_style.add_argument("--remove-bg", action="store_true")

    p_refine = sub.add_parser("refine", help="圖生圖:草稿精緻化 / 材質顏色變體(保留原圖構圖)", parents=[prompt_common])
    p_refine.add_argument("--prompt", required=True)
    p_refine.add_argument("--image", required=True, help="來源圖路徑(草稿或要換材質的圖)")
    p_refine.add_argument("--denoise", type=float, default=0.6, help="0.3~0.4 大致保留構圖只上色;0.6~0.7 細節大幅改變;0.9+ 幾乎重畫")
    p_refine.add_argument("--remove-bg", action="store_true")

    p_upscale = sub.add_parser("upscale", help="放大精修(放大模型 + 二次取樣補細節,不是單純拉大)", parents=[prompt_common])
    p_upscale.add_argument("--prompt", required=True, help="用來引導二次取樣補細節,通常沿用原本生成這張圖時的 prompt")
    p_upscale.add_argument("--image", required=True, help="來源圖路徑(要放大的圖)")
    p_upscale.add_argument("--scale", type=float, default=2.0, help="相對原圖的放大倍率(預設 2 倍),最高 4 倍")
    p_upscale.add_argument("--denoise", type=float, default=0.4, help="二次取樣補細節的強度:太低細節補不夠,太高會偏離原圖構圖")

    p_layer = sub.add_parser(
        "layer_split",
        help="把一張已定稿的完成圖依遮罩切出單一圖層(不重新生成內容,純粹裁切透明度)——用於複合式 UI 元件想事後拆出幾個大塊可疊放區域,拆一層呼叫一次",
        parents=[common],
    )
    p_layer.add_argument("--image", required=True, help="來源圖路徑(已定稿的完成圖)")
    p_layer.add_argument("--mask", required=True, help="這一層的遮罩圖路徑(同 inpaint 慣例,需帶 alpha 通道,要保留進這一層的區域 alpha=0)")
    p_layer.add_argument("--layer-name", required=True, help="這一層的名稱,用來組輸出檔名前綴(例如 border、center_hub)")

    video_common = argparse.ArgumentParser(add_help=False, parents=[common])
    video_common.add_argument(
        "--backend", choices=list(VIDEO_BACKENDS), default=DEFAULT_VIDEO_BACKEND,
        help="影片實作後端。不給用這台機器的預設。某個 task 若還沒接這個 backend,會直接報錯,不要改 task 名。",
    )

    p_vid = sub.add_parser(
        "img2video",
        help="讓已過關的靜幀動起來(短片)。跟圖片產線的 --style / ControlNet / IPAdapter 不相容。",
        parents=[video_common],
    )
    p_vid.add_argument("--prompt", required=True, help="這段要怎麼動(鏡頭鎖定/運鏡/動作),英文較穩")
    p_vid.add_argument("--image", required=True, help="已過關的靜幀路徑,不要用文生影片賭第一幀")
    p_vid.add_argument("--duration", type=float, default=2.0,
                        help="秒數,鎖在 2~6(預設 2)。更長要拆鏡,不要一次生整部片")
    p_vid.add_argument("--width", type=int, help="輸出寬,不給就跟來源圖比例走,最長邊上限 768")
    p_vid.add_argument("--height", type=int, help="輸出高,不給就跟來源圖比例走,最長邊上限 768")
    p_vid.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_vid.add_argument("--seed", type=int)
    p_vid.add_argument("--extract-frames", action="store_true", help="順便抽 png 序列到 <mp4 檔名>_frames/")

    p_fx = sub.add_parser(
        "fx_loop",
        help="鏡頭鎖定的循環特效/環境元素(火、法陣、旗幟)。要能接首尾幀的 backend。預設抽幀交引擎。",
        parents=[video_common],
    )
    p_fx.add_argument("--prompt", required=True, help="循環怎麼動,會自動補上 seamless loop 約束")
    p_fx.add_argument("--image", required=True, help="特效/元件的靜幀")
    p_fx.add_argument("--duration", type=float, default=2.0, help="秒數,鎖在 2~6,預設 2")
    p_fx.add_argument("--width", type=int)
    p_fx.add_argument("--height", type=int)
    p_fx.add_argument("--seed", type=int)
    p_fx.add_argument("--no-extract-frames", dest="extract_frames", action="store_false",
                      help="不要抽 png 序列(預設會抽)")
    p_fx.set_defaults(extract_frames=True)

    p_tr = sub.add_parser(
        "transition",
        help="內容轉場:已知 A、已知 B,模型只負責中間。要能接首尾幀的 backend。傳統硬切/疊化不要用這個。",
        parents=[video_common],
    )
    p_tr.add_argument("--prompt", required=True, help="中間發生什麼")
    p_tr.add_argument("--start", required=True, help="起始靜幀")
    p_tr.add_argument("--end", required=True, help="結束靜幀")
    p_tr.add_argument("--duration", type=float, default=2.0)
    p_tr.add_argument("--width", type=int)
    p_tr.add_argument("--height", type=int)
    p_tr.add_argument("--seed", type=int)
    p_tr.add_argument("--extract-frames", action="store_true")

    p_ext = sub.add_parser(
        "clip_extend",
        help="同一場下一鏡:吃上一支 mp4 的最後一幀(或一張靜幀)再往後生成。長片連戲用這個,不要拉長單次 duration。",
        parents=[video_common],
    )
    p_ext.add_argument("--prompt", required=True, help="接下來發生什麼")
    p_ext.add_argument("--video", help="上一支 mp4,會抽最後一幀當本鏡靜幀")
    p_ext.add_argument("--image", help="若已有上一鏡尾幀靜幀,跟 --video 二選一")
    p_ext.add_argument("--duration", type=float, default=2.0)
    p_ext.add_argument("--width", type=int)
    p_ext.add_argument("--height", type=int)
    p_ext.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_ext.add_argument("--seed", type=int)
    p_ext.add_argument("--extract-frames", action="store_true")

    p_cat = sub.add_parser(
        "video_concat",
        help="把多支已生成的短片接成一支(外部組裝,不是剪接台)。解析度跟第一支對齊。每支都有音軌才接立體聲。",
        parents=[common],
    )
    p_cat.add_argument("--video", action="append", required=True, help="可重複給多次,順序就是播放順序")
    p_cat.add_argument("--name", default="video_concat", help="輸出檔名前綴,預設 video_concat")

    p_cam = sub.add_parser(
        "camera_move",
        help="攝影組運鏡:主體盡量靜止,只有攝影機在動。--camera 是鎖死枚舉。",
        parents=[video_common],
    )
    p_cam.add_argument("--image", required=True, help="已過關的靜幀")
    p_cam.add_argument(
        "--camera", required=True, choices=list(CAMERA_MOVES),
        help="運鏡:static/pan_up/pan_down/pan_left/pan_right/zoom_in/zoom_out/orbit_cw/orbit_ccw",
    )
    p_cam.add_argument(
        "--prompt", default="",
        help="選填場景描述。不給就當主體完全靜止;運鏡以 --camera 為準,不要在這裡另寫一種運鏡",
    )
    p_cam.add_argument("--duration", type=float, default=2.0)
    p_cam.add_argument("--width", type=int)
    p_cam.add_argument("--height", type=int)
    p_cam.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_cam.add_argument("--seed", type=int)
    p_cam.add_argument("--extract-frames", action="store_true")

    p_cv = sub.add_parser(
        "character_video",
        help="角色參考生影片:參考圖鎖身份,第一幀不必是那張定稿圖。對應靜態 style_lock,不是 img2video。",
        parents=[video_common],
    )
    p_cv.add_argument("--prompt", required=True, help="新鏡頭裡這個角色在做什麼(英文較穩)")
    p_cv.add_argument(
        "--character-ref", action="append", required=True,
        help="角色參考圖,可重複給最多 9 張(多角度/特寫較穩)。第一張同時決定預設畫布比例",
    )
    p_cv.add_argument("--duration", type=float, default=2.0, help="秒數,鎖在 2~6,預設 2")
    p_cv.add_argument("--width", type=int)
    p_cv.add_argument("--height", type=int)
    p_cv.add_argument("--seed", type=int)
    p_cv.add_argument("--extract-frames", action="store_true")

    p_pd = sub.add_parser(
        "pose_drive",
        help="表演驅動:角色靜幀 + 動作參考影片。對應靜態 character_action,姿勢來源是影片不是一張 pose 圖。",
        parents=[video_common],
    )
    p_pd.add_argument("--prompt", required=True, help="這段鏡頭裡角色在做什麼(英文較穩)")
    p_pd.add_argument("--image", required=True, help="角色參考靜幀(這是誰)")
    p_pd.add_argument("--motion-ref", required=True, help="動作參考影片(這段怎麼動)")
    p_pd.add_argument(
        "--control-type", choices=["canny", "pose", "depth"], default="pose",
        help="動作怎麼抽:pose=骨架(預設,表演/肢體),canny=邊緣,depth=前後景",
    )
    p_pd.add_argument("--duration", type=float, default=2.0, help="秒數,鎖在 2~6,預設 2。長過參考影片的部分控制會變弱")
    p_pd.add_argument("--width", type=int)
    p_pd.add_argument("--height", type=int)
    p_pd.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_pd.add_argument("--seed", type=int)
    p_pd.add_argument("--extract-frames", action="store_true")

    args = ap.parse_args(argv)
    try:
        _validate_cli_args(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    style_checkpoint = None
    if getattr(args, "style", None):
        if DEVICE.get("tier") not in ("sdxl_high", "sdxl", "sdxl_light"):
            raise SystemExit(
                f"--style 目前只支援 SDXL 家族機器(sdxl_high/sdxl/sdxl_light),"
                f"這台機器偵測到的 tier 是 {DEVICE.get('tier')!r}。"
                f"這幾個風格 checkpoint 都是 SDXL 架構,跟 sd15 tier 的 ControlNet/IPAdapter 對不上,"
                f"直接送出去 ComfyUI 執行期會 shape mismatch。"
            )
        style_checkpoint = STYLE_CHECKPOINTS[args.style]

    if getattr(args, "rating", None):
        if args.style not in RATING_TAGS:
            raise SystemExit(
                f"--rating 只在 --style anime/illustration 時有意義(這兩顆底模訓練資料本身用分級標籤"
                f"控制內容尺度),目前 --style={args.style!r} 沒有這個標籤慣例,加了也沒效果,直接擋下來。"
            )
        args.prompt = f"{RATING_TAGS[args.style][args.rating]}, {args.prompt}"

    _validate_task_capabilities(args)
    comfy_url = resolve_comfy_url(getattr(args, "comfy_url", None), getattr(args, "config_path", None))
    request_timeout = min(DEFAULT_HTTP_TIMEOUT, float(args.timeout))

    def upload(path):
        return upload_image(path, comfy_url=comfy_url, request_timeout=request_timeout)

    if args.task == "concept":
        prompt, out_id = build_concept(args.prompt, args.negative, args.width, args.height, args.seed,
                                        batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
                                        checkpoint=style_checkpoint)
    elif args.task == "icon_asset":
        structure_fn = upload(args.structure_ref) if args.structure_ref else None
        appearance_fn = upload(args.appearance_ref) if args.appearance_ref else None
        prompt, out_id = build_icon_asset(args.prompt, args.negative, args.width, args.height, args.seed,
                                           batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
                                           structure_ref_filename=structure_fn, checkpoint=style_checkpoint,
                                           appearance_ref_filename=appearance_fn, appearance_weight=args.appearance_weight)
    elif args.task == "character_action":
        char_fn = upload(args.character_ref)
        pose_fn = upload(args.pose_ref)
        prompt, out_id = build_character_action(
            args.prompt, char_fn, pose_fn, args.negative,
            width=args.width, height=args.height,
            seed=args.seed, ip_weight=args.ip_weight, pose_strength=args.pose_strength,
            batch_size=args.batch, control_type=args.control_type,
            lora_name=args.lora, lora_strength=args.lora_strength, checkpoint=style_checkpoint,
        )
    elif args.task == "inpaint":
        img_fn = upload(args.image)
        mask_fn = upload(args.mask)
        prompt, out_id = build_inpaint(args.prompt, img_fn, mask_fn, args.negative,
                                        denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint)
    elif args.task == "guided_inpaint":
        img_fn = upload(args.image)
        mask_fn = upload(args.mask)
        control_fn = None
        if args.control_type:
            control_fn = upload(args.control_ref) if args.control_ref else img_fn
        appearance_fn = upload(args.appearance_ref) if args.appearance_ref else None
        prompt, out_id = build_guided_inpaint(
            args.prompt, img_fn, mask_fn, args.negative,
            control_ref_filename=control_fn, control_type=args.control_type, control_strength=args.control_strength,
            appearance_ref_filename=appearance_fn, appearance_weight=args.appearance_weight,
            denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint,
        )
    elif args.task == "pose_only":
        pose_fn = upload(args.pose_ref)
        prompt, out_id = build_pose_only(args.prompt, pose_fn, args.negative,
                                          width=args.width, height=args.height,
                                          seed=args.seed, pose_strength=args.pose_strength,
                                          batch_size=args.batch, control_type=args.control_type,
                                          lora_name=args.lora, lora_strength=args.lora_strength,
                                          checkpoint=style_checkpoint)
    elif args.task == "style_lock":
        char_fn = upload(args.character_ref)
        prompt, out_id = build_style_lock(args.prompt, char_fn, args.negative,
                                           width=args.width, height=args.height,
                                           seed=args.seed, ip_weight=args.ip_weight,
                                           batch_size=args.batch,
                                           lora_name=args.lora, lora_strength=args.lora_strength,
                                           checkpoint=style_checkpoint)
    elif args.task == "refine":
        img_fn = upload(args.image)
        prompt, out_id = build_refine(args.prompt, img_fn, args.negative,
                                       denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint)
    elif args.task == "upscale":
        img_fn = upload(args.image)
        prompt, out_id = build_upscale(args.prompt, img_fn, args.negative,
                                        scale=args.scale, denoise=args.denoise, seed=args.seed,
                                        checkpoint=style_checkpoint)
    elif args.task == "layer_split":
        img_fn = upload(args.image)
        mask_fn = upload(args.mask)
        prompt, out_id = build_layer_split(img_fn, mask_fn, args.layer_name)
    elif args.task == "img2video":
        backend = require_video_backend(args.task, args.backend)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        prompt, out_id = run_i2v(
            backend, args.prompt, img_fn, width, height, args.seed, duration,
            filename_prefix="img2video", negative=args.negative,
        )
    elif args.task == "fx_loop":
        backend = require_video_backend(args.task, args.backend)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        loop_prompt = args.prompt if "loop" in args.prompt.lower() else f"{args.prompt}, {VIDEO_LOOP_SUFFIX}"
        prompt, out_id = run_i2v(
            backend, loop_prompt, img_fn, width, height, args.seed, duration,
            last_image_filename=img_fn, filename_prefix="fx_loop",
        )
    elif args.task == "transition":
        backend = require_video_backend(args.task, args.backend)
        duration = _require_video_duration(args.duration)
        if (args.width is None) ^ (args.height is None):
            raise SystemExit("--width 跟 --height 要一起給,或兩個都不給。")
        width, height = video_canvas(args.start, args.width, args.height)
        start_fn = upload(args.start)
        end_fn = upload(args.end)
        prompt, out_id = run_i2v(
            backend, args.prompt, start_fn, width, height, args.seed, duration,
            last_image_filename=end_fn, filename_prefix="transition",
        )
    elif args.task == "clip_extend":
        if bool(args.video) == bool(args.image):
            raise SystemExit("clip_extend 要 --video 上一支 mp4,或 --image 上一鏡尾幀,只能給一個。")
        backend = require_video_backend(args.task, args.backend)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        still = args.image
        if args.video:
            out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
            os.makedirs(out_dir, exist_ok=True)
            still = os.path.join(out_dir, "_clip_extend_last.png")
            extract_last_frame(args.video, still)
            print(f"[連戲] 上一鏡尾幀 -> {still}")
        width, height = video_canvas(still, args.width, args.height)
        img_fn = upload(still)
        prompt, out_id = run_i2v(
            backend, args.prompt, img_fn, width, height, args.seed, duration,
            filename_prefix="clip_extend", negative=args.negative,
        )
    elif args.task == "video_concat":
        out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)
        dest = os.path.join(out_dir, f"{args.name}.mp4")
        concat_videos(args.video, dest)
        print(f"[完成] {dest}")
        return
    elif args.task == "character_video":
        backend = require_video_backend(args.task, args.backend)
        refs = args.character_ref
        if len(refs) > CHARACTER_REF_MAX:
            raise SystemExit(
                f"--character-ref 最多 {CHARACTER_REF_MAX} 張,目前 {len(refs)}"
            )
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(refs[0], args.width, args.height)
        ref_fns = [upload(p) for p in refs]
        prompt, out_id = run_character_video(
            backend, args.prompt, ref_fns, width, height, args.seed, duration,
            filename_prefix="character_video",
        )
    elif args.task == "camera_move":
        backend = require_video_backend(args.task, args.backend)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        cam_prompt = camera_move_prompt(args.camera, args.prompt)
        last_fn = None
        if backend_has(backend, "last_frame"):
            if args.camera == "static":
                last_fn = img_fn
            elif args.camera not in ("orbit_cw", "orbit_ccw"):
                out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
                os.makedirs(out_dir, exist_ok=True)
                end_path = os.path.join(out_dir, "_camera_end.png")
                build_camera_end_still(args.image, args.camera, width, height, end_path)
                print(f"[運鏡] 終點靜幀 -> {end_path}")
                last_fn = upload(end_path)
        prompt, out_id = run_i2v(
            backend, cam_prompt, img_fn, width, height, args.seed, duration,
            last_image_filename=last_fn, filename_prefix="camera_move",
            negative=args.negative,
        )
    elif args.task == "pose_drive":
        backend = require_video_backend(args.task, args.backend)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        print(
            "[提醒] pose_drive 的角色靜幀姿勢/朝向要接近動作片第一幀;"
            "對不上(例如站姿去套走路)會雙人/重影。",
            file=sys.stderr,
        )
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        motion_fn = upload(args.motion_ref)
        prompt, out_id = run_pose_drive(
            backend, args.prompt, img_fn, motion_fn, width, height, args.seed, duration,
            control_type=args.control_type, filename_prefix="pose_drive",
            negative=args.negative,
        )
    else:
        raise SystemExit(f"未知 task: {args.task}")

    target_output_id = None
    if args.task == "icon_asset" or getattr(args, "remove_bg", False):
        target_output_id = attach_bg_removal(prompt, out_id)

    print(f"[送出] task={args.task}")
    history = submit_and_wait(prompt, timeout=args.timeout, comfy_url=comfy_url)
    paths = download_outputs(
        history,
        output_dir=getattr(args, "output_dir", None),
        node_ids=[target_output_id] if target_output_id else None,
        comfy_url=comfy_url,
        request_timeout=request_timeout,
    )
    for p in paths:
        print(f"[完成] {p}")
        if getattr(args, "extract_frames", False) and p.lower().endswith(".mp4"):
            extract_video_frames(p, getattr(args, "output_dir", None))


if __name__ == "__main__":
    main()
