# `sd15_light` 設定檔：調校經驗

對應 `tools_src/comfyui_pipeline/profiles/sd15_light.json`。

**這份設定檔目前在任何平台都沒有實機驗證紀錄**，所有 task 的驗證狀態都是 `unverified`。使用前要先告訴使用者：結果沒有經過驗證，畫質上限低於 SDXL。

## 適用範圍

- 原本的 `sd15` tier（可用記憶體低於 8GB，或偵測不到記憶體的機器）。也可以在較大的機器上用 `--profile sd15_light`／`--default-profile sd15_light` 主動選用。
- 支援 CPU 後端，但速度以分鐘甚至十分鐘計。
- 只提供不依賴 SDXL add-on 的基礎路徑：`concept`、`icon_asset`（不帶 `--structure-ref`/`--appearance-ref`）、`inpaint`、`guided_inpaint`（不帶 ControlNet 與外觀參考）、`refine`、`upscale`、`layer_split`。
- **不支援** `pose_only`、`style_lock`、`character_action`、`--style`，以及任何 ControlNet/IPAdapter 參數。這些不是換一顆 SD1.5 模型就能開通，要照 `skills/comfyui-new-tool-checklist/SKILL.md`「情境 B」補齊 SD1.5 版 ControlNet/IPAdapter/CLIP Vision 並實機驗證。

## 模型與參數

- 底模：`dreamshaper_8.safetensors`；BiRefNet 與 4x-UltraSharp 跟 SDXL 共用（架構無關）。
- 取樣參數沿用 `steps=25`、`cfg=7.0`、`euler`／`normal`，**尚未針對 SD1.5 調校**。
- 預設畫布 512×512。SD1.5 以 512 訓練，明顯大於 768 的畫布容易出現重複主體。

## 已知待驗證項目

- 這組取樣參數在 DreamShaper 8 上的畫質是否可接受
- `icon_asset` 的構圖引導詞（為 SDXL 寫的）在 SD1.5 上是否仍有效
- `upscale` 的二次取樣（denoise 0.4）在 SD1.5 上是否會改變構圖

實測後把結果補在這裡，並依「情境 C」更新設定檔的 `validation`。
