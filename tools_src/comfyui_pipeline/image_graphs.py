"""圖片 task 的常數、參數驗證與機器／設定檔狀態。

圖片 graph 本身在 ``templates/image/``（固定 API graph，由 ``image_from_template`` 經 runner 填值）；
這裡不再有組 graph 的 builder。保留的是：參數驗證、模型檔名常數（來自 profiles/*.json）、
FLUX.2 檔名常數、icon_asset 的 prompt 後綴，以及 ``DEVICE`` / ``CKPT`` / ``ACTIVE_PROFILE_ID``
這組由 ``image_runtime.sync_image_runtime`` 同步的模組層級狀態。
"""

import json
import math
import os
import sys

try:
    from PIL import Image as PILImage
except ImportError:  # Pillow is only needed by the local media helpers.
    PILImage = None

from . import profiles as _profiles

# 模型檔名與取樣參數的單一來源是 profiles/*.json(全平台共用、隨 comfyui_pipeline/ 部署)。
# 下面的模組常數只是從 sdxl_standard 設定檔衍生出來的別名;不要在這裡直接改檔名,改設定檔，
# 並用 maintenance/ 之外的流程重新確認 templates/ 的 pin(templates/ 是 graph 的唯一來源)。
DEFAULT_PROFILE_ID = "sdxl_standard"
_SDXL_PROFILE = _profiles.load_profile(DEFAULT_PROFILE_ID)
SDXL_TIERS = frozenset(_SDXL_PROFILE["tiers"])
# 機器快照預設在腳本所在資料夾(部署端 <ComfyUI>/tools)。smoke 從 repo 執行時會設 GAMEART_SNAPSHOT_DIR
# 指向 <ComfyUI>/tools,讓 generate 子程序讀同一份快照(見 runtime_config.SNAPSHOT_DIR_ENV)。
_SNAPSHOT_DIR = os.environ.get("GAMEART_SNAPSHOT_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEVICE_CONFIG_PATH = os.path.join(os.path.abspath(_SNAPSHOT_DIR), "device_config.json")

def _require_pillow():
    if PILImage is None:
        raise RuntimeError("這個 helper 需要 Pillow；產圖核心的 HTTP/graph 功能不需要 Pillow。")

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

def require_sdxl_capability(feature, tier=None):
    """ControlNet/IPAdapter 只有 SDXL 家族的模型；機器 tier 不是 SDXL 家族時，送出前就停止。"""
    if tier is None and ACTIVE_PROFILE_ID is not None:
        profile = _active_profile()
        if profile["family"] != "sdxl":
            raise RuntimeError(
                f"{feature} 目前需要 SDXL 家族的 ControlNet/IPAdapter，"
                f"但選用的模型設定檔是 {profile['id']!r}（{profile['family']}）；這個設定檔不支援這項功能。"
            )
        return
    current_tier = DEVICE.get("tier") if tier is None else tier
    if current_tier is not None and current_tier not in SDXL_TIERS:
        raise RuntimeError(
            f"{feature} 目前需要 SDXL 家族的 ControlNet/IPAdapter，"
            f"但這台機器的 tier 是 {current_tier!r}，不是 SDXL 家族。"
        )

# --style 選填參數的白名單(選配,不裝也完全不影響預設行為)。都是 SDXL 架構的社群微調底模，
# 只在 SDXL 家族 tier 生效,見 cli 的 tier 檢查。
# 各風格的授權/檔案來源見 docs/knowledge/installation/models-and-sources.md,商用前務必自行覆核授權條款
# ——這三顆各自授權都不一樣(Juggernaut/Pony 都有針對「做成付費服務」的限制;Illustrious 依版本
# 不同差很多,2026-08-19 曾經記錯成 MIT,見 models.md 更正說明),不要憑這裡的常數名稱就假設能商用。
STYLE_CHECKPOINTS = {
    style: variant["checkpoint"] for style, variant in _SDXL_PROFILE["variants"].items()
}

# --rating 選填參數(選配,不給就完全不影響 prompt)。只對 anime/illustration 這兩個 --style
# 有意義——這兩顆底模的訓練資料本身就用分級標籤控制內容尺度(Pony 用 rating_xxx,Illustrious
# 沿用 Danbooru 的 rating:xxx),不是這個腳本自己發明的機制。realistic/預設底模沒有對應標籤慣例,
# 給了 --rating 也沒意義,cli 裡會直接擋掉,不要讓它靜默沒效果。
RATING_TAGS = {
    style: dict(variant["rating_tags"])
    for style, variant in _SDXL_PROFILE["variants"].items()
    if variant.get("rating_tags")
}

# 實驗性 A/B 的 ControlNet Union 與 preflight 比對用的模型檔名。
CONTROLNET_UNION_MODEL = _profiles.model_file(_SDXL_PROFILE, "controlnet.union")
IPADAPTER_MODEL = _profiles.model_file(_SDXL_PROFILE, "ipadapter")
BG_REMOVAL_MODEL = _profiles.model_file(_SDXL_PROFILE, "bg_removal")

# FLUX.2 Klein is a separate image backend, not an SDXL checkpoint.  Keep the
# official ComfyUI FP8 filenames here so the experimental tasks cannot silently
# pick up another precision, model generation, or similarly named file.
FLUX2_DISTILLED_UNET = "flux-2-klein-4b-fp8.safetensors"
FLUX2_BASE_UNET = "flux-2-klein-base-4b-fp8.safetensors"
FLUX2_CLIP = "qwen_3_4b.safetensors"
FLUX2_VAE = "flux2-vae.safetensors"


def validate_flux2_dimensions(width, height):
    """FLUX.2 Core latent nodes require dimensions aligned to 16 pixels."""
    validate_dimensions(width, height)
    if width % 16 or height % 16:
        raise ValueError(
            f"FLUX.2 的 width/height 必須是 16 的倍數，目前是 {width}x{height}"
        )
    return width, height


def load_device_config():
    """讀設備偵測結果(detect_device.py 產出),決定用哪個 checkpoint/預設解析度。
    沒有這份設定檔就用保守的 SDXL 預設值,並提醒使用者先跑一次偵測。"""
    if not os.path.exists(DEVICE_CONFIG_PATH):
        print(f"[提醒] 找不到 {DEVICE_CONFIG_PATH},建議先執行 detect_device.py。目前用預設 SDXL 設定。", file=sys.stderr)
        width, height = _SDXL_PROFILE["resolution"]["native"]
        return {
            "checkpoint": _profiles.model_file(_SDXL_PROFILE, "checkpoint"),
            "default_width": width, "default_height": height,
        }
    with open(DEVICE_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

DEVICE = load_device_config()
CKPT = DEVICE["checkpoint"]
# 明確選用的模型設定檔 id(generate.py 的 --profile 或 image_capabilities.json 的 default_profile)。
# None = 沿用 tier 對應:底模與預設解析度讀 DEVICE(device_config.json)。
ACTIVE_PROFILE_ID = None


def _active_profile():
    """回傳目前使用的設定檔。

    有 ACTIVE_PROFILE_ID 時用它;否則依 DEVICE 的 tier 對應。沒有 tier(找不到 device_config.json
    時的預設值)或 tier 不在任何設定檔時沿用 sdxl_standard;
    未知 tier 需要 add-on 時仍由 require_sdxl_capability 擋下。
    """
    if ACTIVE_PROFILE_ID is not None:
        return _profiles.load_profile(ACTIVE_PROFILE_ID)
    profile_id = _profiles.profile_id_for_tier(DEVICE.get("tier")) or DEFAULT_PROFILE_ID
    return _profiles.load_profile(profile_id)


def _default_checkpoint():
    if ACTIVE_PROFILE_ID is None:
        return CKPT
    return _profiles.model_file(_active_profile(), "checkpoint")


def _default_size():
    """預設畫布。選了設定檔時依這台機器的可用記憶體從設定檔挑,讓大機器選小設定檔也拿到對應解析度。"""
    if ACTIVE_PROFILE_ID is None:
        return DEVICE["default_width"], DEVICE["default_height"]
    return _profiles.default_resolution(_active_profile(), DEVICE.get("usable_memory_mb") or 0)


def _resolve_sampling(steps=None, cfg=None):
    """設定檔的鎖死取樣參數;呼叫端明確傳入 steps/cfg 時才覆寫。"""
    sampling = dict(_active_profile()["sampling"])
    if steps is not None:
        sampling["steps"] = steps
    if cfg is not None:
        sampling["cfg"] = cfg
    return sampling

def seed_or_random(seed):
    return seed if seed is not None else int.from_bytes(os.urandom(6), "big")

# icon_asset 的 prompt/negative 固定 append 的構圖引導詞：把生成結果導向「單一置中物件、無場景背景」，
# 讓輸出更像可用的圖示素材，也讓後面的去背(BiRefNet)邊緣更乾淨。icon_asset 一定去背，沒有旗標可關。
ICON_ASSET_PROMPT_SUFFIX = ", single centered object, icon design, isolated on plain simple background, clean readable silhouette, no scene, no extra props"
ICON_ASSET_NEGATIVE_SUFFIX = ", cluttered scene, multiple objects, full illustration background, cropped edges"
