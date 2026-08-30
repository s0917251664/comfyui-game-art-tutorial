# 影片 backend(實作層,不是 task 契約)

對外契約是 **task 名 + `--backend`**。模型檔名、節點、prompt tag 只活在對應 backend 裡。換實作時 task 名稱不變。

backend 的可用性與預設值來自已安裝機器的 `video_capabilities.json`，不是 source code 常數。這台 XU-Nano-PC 的歷史 bake-off 偏好 H3，但只有在該機器的 capability config 明確寫入 `default_backend: h3` 時才成立；若是 `null`，每次影片 CLI 都必須明確給 `--backend`。某個 task 若這個 backend 還沒接,`generate.py` 會直接報錯——不要因此改成另一個 task，也不會靜默 fallback。

## 現在誰接得上什麼

| 能力 | 意思 | 已接 |
|---|---|---|
| `i2v` | 靜幀當第一幀生短片 | `h3`, `wan` |
| `last_frame` | 還能餵最後一幀(loop / 轉場 / 幾何運鏡終點) | `h3` |
| `character_ref` | 參考圖鎖身份、第一幀不必是那張定稿圖 | `h3` |
| `control_video` | 角色靜幀 + 動作參考影片(pose/canny/depth) | `h3`, `wan` |
| `audio` | 輸出帶音軌 | `h3` |

| task | 需要的能力 |
|---|---|
| `img2video` / `clip_extend` / `camera_move` | `i2v` |
| `fx_loop` / `transition` | `i2v` + `last_frame` |
| `character_video` | `character_ref` |
| `pose_drive` | `control_video` |

`camera_move` 在有 `last_frame` 的 backend 會再餵幾何終點靜幀;沒有就只靠運鏡枚舉收成的 prompt。`orbit_*` 平面裁切做不出繞拍,一律只走 prompt。

## Capability config 與 fail-fast

`tools_src/detect_video_capabilities.py` 只檢查指定的 ComfyUI `.venv`、既有 `models/` 檔案與（若提供 URL）`/object_info`；它不會下載模型、custom node 或 Python 套件。產出的 `video_capabilities.json` 由 `generate.py` 在影片 task 上傳任何輸入前重新驗證：

- backend 必須由 `--backend` 或 config 的 `default_backend` 選定；沒有選定就停止。
- config 宣告的模型檔案、Python/PyTorch/Pillow/PyAV 與 CUDA/GPU 必須仍與目前執行環境一致。
- 目前 ComfyUI `/object_info` 必須包含該 task graph 的必要 nodes；缺任何一項都不會進 upload 或 queue。
- 圖片的 `device_config.json`/SDXL tier 與影片 backend 是兩套責任。`--style`、圖片 checkpoint 不會替影片選 H3/Wan。

使用已安裝機器時，可先用 `detect_video_capabilities.py --default-backend h3` 明確記錄偏好；若不想設偏好，省略該旗標，之後在每次影片 CLI 明確傳 `--backend`。若要用 `pose`/`depth`，先確認 `comfyui_controlnet_aux` 的前處理模型已存在；缺少時不要在沒有使用者同意下讓第一次 smoke test 觸發下載。

## 這台機器對應的檔(裝機用,不要寫進 CLI)

| backend | 主要 UNET | 備註 |
|---|---|---|
| `h3` I2V / 首尾幀 | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 跟 `character_ref` 那顆不能混 |
| `h3` 角色參考 / 動作驅動 | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 私有 prompt tag `<Picture i>` / `<Video k>`,CLI 不要叫使用者寫。`pose_drive` 也用這顆:靜幀當圖參考、動作片預處理後當影片參考。不是 Fun ControlNet Union(ComfyUI 0.34.0 還沒有那個節點) |
| `wan` I2V | `wan2.2_ti2v_5B_fp16.safetensors` | 較快、無聲、沒有尾幀 |
| `wan` 動作驅動 | `wan2.2_fun_control_5B_bf16.safetensors` | 跟 I2V 那顆不能混;`--backend wan` 的 `pose_drive` 用這個 |

2026-08-26 同一張靜幀 I2V 對打:h3 保原圖較好有聲音;wan 較快無聲、身份較易漂。

Fun Camera 14B / 雲端 API 若以後要接,加一個新 backend 名,不要把 task 改名。
