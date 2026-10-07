"""task 模組共用:argparse parent、runtime 參數、影片 plan 與共用驗證。"""
import argparse
from dataclasses import dataclass, field

from ..client import DEFAULT_TIMEOUT, OUTPUT_DIR
from ..image_graphs import STYLE_CHECKPOINTS, validate_batch, validate_dimensions, validate_lora_strength
from ..video_catalog import DEFAULT_VIDEO_TIMEOUT, VIDEO_BACKENDS


def add_runtime_arguments(parser):
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
        "--video-config", dest="video_config_path", default=argparse.SUPPRESS,
        help=("明確指定 machine-specific video_capabilities.json；影片不會從 task 名稱猜測 "
              "H3/Wan。未指定時可由 --config 的 video_config 或 ComfyUI/tools/video_capabilities.json 找到。"),
    )
    parser.add_argument(
        "--profile", dest="profile_id", default=argparse.SUPPRESS,
        help=("明確選用圖片模型設定檔（例如 sd15_light）；會檢查是否符合這台機器與 task。"
              "未指定時用 image_capabilities.json 的 default_profile，再沒有就沿用 tier 對應。"),
    )
    parser.add_argument(
        "--image-config", dest="image_config_path", default=argparse.SUPPRESS,
        help="明確指定 machine-specific image_capabilities.json。",
    )
    parser.add_argument(
        "--timeout", type=float, default=argparse.SUPPRESS,
        help=(f"prompt 送達後輪詢生成結果的秒數上限；圖片預設 {DEFAULT_TIMEOUT:g}，"
              f"影片預設 {DEFAULT_VIDEO_TIMEOUT:g}。"),
    )
    parser.add_argument(
        "--result-json", dest="result_json", default=argparse.SUPPRESS,
        help="選用：成功圖片 task 寫入技術結果 manifest（不得覆寫既有檔案）。",
    )


def build_parents():
    """建立各 task 子命令共用的 argparse parent(不可直接當子命令用)。"""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-dir", help=f"成品存放資料夾,預設 {OUTPUT_DIR}")
    add_runtime_arguments(common)

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

    video_common = argparse.ArgumentParser(add_help=False, parents=[common])
    video_common.add_argument(
        "--backend", choices=list(VIDEO_BACKENDS), default=argparse.SUPPRESS,
        help=("影片實作後端；不給時只使用 capability config 明確設定的 default_backend，"
              "不會無條件預設 H3。某個 task 若還沒接這個 backend，會直接報錯。"),
    )
    video_common.add_argument(
        "--overwrite", action="store_true",
        help="明確允許覆寫同名影片輸出；預設拒絕以免重跑破壞既有素材。",
    )
    video_common.add_argument(
        "--shot-id", help="安全鏡號；用於可追溯的輸出檔名前綴，例如 A01。",
    )
    video_common.add_argument(
        "--name", help="安全輸出檔名前綴；指定後優先於 --shot-id。",
    )
    video_common.add_argument(
        "--resume", action="store_true",
        help="只在同名影片 sidecar 的 task/backend/seed/input/config/contract 全相符且重新驗證通過時跳過",
    )

    return {"common": common, "model": model_common, "prompt": prompt_common,
            "batch_lora": batch_lora_common, "video": video_common}


@dataclass
class VideoPlan:
    """影片 task 的 prepare() 結果:graph 與送出後驗證/sidecar 需要的資訊。"""
    graph: dict
    out_id: str
    backend: str
    inputs: list
    prefix: str
    contract: dict
    continuity_refs: dict = field(default_factory=dict)
    prompt: str = None  # sidecar 記錄的 prompt;None 代表沿用 args.prompt
    # 選用:原始 mp4 通過契約驗證並寫完 sidecar 後才呼叫 finalize(mp4_path),做本機後處理(例如貼回原片)。
    finalize: object = None


def validate_explore_args(args):
    """concept/icon_asset/character_action/pose_only/style_lock 共用:批次、LoRA 強度、明確給的尺寸。"""
    validate_batch(args.batch)
    validate_lora_strength(args.lora_strength)
    # 沒給尺寸時由 builder 依選用的設定檔/device_config 補預設值,這裡只驗證使用者明確給的值。
    # validate_dimensions 需要兩個值;未給的那一邊用合法佔位值 8,讓錯誤訊息只指向真正給錯的欄位。
    if args.width is not None or args.height is not None:
        validate_dimensions(
            8 if args.width is None else args.width,
            8 if args.height is None else args.height,
        )
