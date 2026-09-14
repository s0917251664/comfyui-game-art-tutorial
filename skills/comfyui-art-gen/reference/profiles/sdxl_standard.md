# `sdxl_standard` 設定檔：調校經驗

對應 `tools_src/comfyui_pipeline/profiles/sdxl_standard.json`。這份文件放「用這份設定檔產圖時要知道的經驗」；模型檔名、下載來源與授權見 `skills/comfyui-install/reference/models.md`，參數規則見 `../full-params.md`。

**這裡只記實測發現的事，沒列出的代表還沒實測過，不要當成已驗證。**

## 適用範圍

- 原本的 `sdxl_high`（24GB+）、`sdxl`（12GB+）、`sdxl_light`（8GB+）三個 tier 都用這份設定檔。
- 提供全部 SDXL 圖片 task：`concept`、`icon_asset`、`character_action`、`pose_only`、`style_lock`、`inpaint`、`guided_inpaint`、`refine`、`upscale`、`layer_split`。
- ControlNet（canny/pose/depth）、IPAdapter、CLIP Vision、BiRefNet、放大模型都是選配；沒裝的部分只影響用到它的 task 或參數，`image_capabilities.json` 的 `features` 會列出。
- `controlnet.union`（xinsir ProMax）是實驗性 A/B，只接在 `pose_only --control-backend union`，不能滿足其他 task 的 ControlNet 需求。

## 鎖定的取樣參數

`steps=25`、`cfg=7.0`、`euler`／`normal`。這組是 SDXL base 的實測路線；換成蒸餾版（Lightning/Turbo/DMD2）等需要 4–8 步、低 cfg 的模型時，不能沿用這份設定檔，要另開設定檔並重新驗證。

## 預設解析度

| 可用記憶體（`usable_memory_mb`） | 預設畫布 |
|---|---|
| ≥ 12000 MB | 1024×1024 |
| 8000–11999 MB | 768×768 |

- Apple Silicon 的可用記憶體是統一記憶體的一半（`detect_device.py` 保守折算）。
- `icon_asset` 固定用 1024×1024，不吃這張表。
- 使用者明確給 `--width`/`--height` 時以使用者為準；8–12GB 機器開 1024 以上有 OOM 風險，先提醒。

## 風格變體（`--style`）

三個變體共用同一套 ControlNet/IPAdapter/CLIP Vision（綁的是 SDXL 架構，不是特定微調版）。

- **`anime`（Pony Diffusion V6 XL）**：2026-08-19 實測，**prompt 沒帶 `score_9, score_8_up, score_7_up`（至少 3 個 score 標籤）時輸出不穩定**（實測出現灰階、跟描述無關的圓形徽章構圖）；補上這組標籤後同一個 prompt 出圖正常。已排除 VAE 是原因：隔離變數測試只加 score 標籤、不改 VAE 就解決了。建議搭配的獨立 `sdxl_vae.safetensors` 可以放在 `models/vae/`，但 `generate.py` 目前一律用 `CheckpointLoaderSimple` 內建 VAE，沒有接這顆的必要。
- **`realistic`（Juggernaut XL Ragnarok）**：2026-08-19 實測，不需要特殊 prompt 慣例，預設參數直接出圖正常。官方建議解析度是 832×1216 直式，想更貼近官方建議可以帶 `--width 832 --height 1216`。
- **`illustration`（Illustrious XL v1.1）**：2026-08-19 實測，`--rating safe` 正常出圖，沒有 `anime` 那種畫質問題。官方文件說分級標籤幾乎必填，沒加可能結果不穩定。

## 驗證紀錄摘要

以設定檔 JSON 的 `validation` 為準，這裡只是方便閱讀的摘要：

| 平台 | 狀態 | 驗證時的可用記憶體 | 證據 |
|---|---|---|---|
| `windows-cuda` | `verified`（全部 10 個 task） | 16GB（RTX 4080） | `docs/tested-versions.md` |
| 其他平台（含 `macos-mps`、`linux-cuda`） | 沒有紀錄 → `unverified` | — | — |

可用記憶體低於 16000 MB 的 `windows-cuda` 機器（例如 8–12GB 卡）也會降為 `unverified`，直到補上該級距的實測紀錄。補紀錄的流程見 `skills/comfyui-new-tool-checklist/SKILL.md`「情境 C」。
