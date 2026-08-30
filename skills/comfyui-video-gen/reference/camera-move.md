# `camera_move`

攝影組運鏡:主體盡量靜止,只有攝影機在動。`--camera` 是鎖死枚舉,不要臨場寫「往左推一點」。

## 為什麼不是 Fun Camera 14B

設計稿原本想接 Wan 2.2 Fun Camera 的 `WanCameraEmbedding`(Pan/Zoom 是 Plücker 相機碼,不是 prompt)。這台 RTX 4080 16GB **不當那條當預設**:

| 路徑 | 為什麼現在不用 |
|---|---|
| Comfy-Org Fun Camera **14B** | 官方模板就是這個。high+low noise 兩顆 fp8 約 30GB,還要 `wan_2.1_vae`(跟現有 `wan2.2_vae` 不同)。16GB 卡 DESIGN 已寫 14B 不當預設 |
| alibaba-pai Fun Camera **5B** | 有公開權重(~10.5GB `diffusion_pytorch_model.safetensors`),但是 VideoX-Fun 全家桶格式,Comfy-Org **沒有** `wan2.2_fun_camera_5B` 單檔 UNET。要另裝 `LoadWan2_2FunModel` 那類 custom node,不進這條產線的安裝清單 |
| 現況 | 有 `last_frame` 的 backend:來源靜幀當首幀 + **幾何終點靜幀當尾幀**(跟 `transition` 同一招),prompt 輔助。沒有尾幀的 backend 只靠 prompt。`orbit_*` 平面裁切做不出繞拍,一律只走 prompt。哪個 backend 有 `last_frame` 見 `backends.md` |

之後若要接真正的 Fun Camera,走 `comfyui-pipeline-review` 核准再換 backend,task 名稱不變。

## 鎖死的參數

- `--camera`: `static` / `pan_up` / `pan_down` / `pan_left` / `pan_right` / `zoom_in` / `zoom_out` / `orbit_cw` / `orbit_ccw`
- 時長 2~6 秒,畫布最長邊 768,20 steps
- `--prompt` 選填,只補場景;運鏡以枚舉為準。不給就當主體完全靜止
- 沒有 `--speed` 旗標(鎖慢速)
- zoom 倍率鎖 `1.35`,pan 終點裁 `0.82`(Ken Burns:靜幀沒有畫面外像素,不能真的揭示原圖外面的東西)
- 終點靜幀寫到 `output/_camera_end.png`(下次會覆蓋)

## 已實測(2026-08-27,這台 RTX 4080 16GB,不要自動播成品)

同一張轉盤、`--camera zoom_in --duration 2 --seed 42`:

| | 只靠 prompt(`00001`) | 首尾幀幾何終點(`00002`) |
|---|---|---|
| 牆鐘 | 96.5 秒 | 106.8 秒 |
| 首尾平均像素差 | 16.0 | **41.8**(zoom 明顯較大) |
| 最後一幀 vs 幾何終點圖 | 35.2 | **3.9**(幾乎貼齊 `_camera_end.png`) |
| 檔案 | `camera_move_h3_00001_.mp4` | `camera_move_h3_00002_.mp4`(768×768、56 幀、H.264+AAC) |

目視 `00002` 末幀轉盤明顯變大、分區沒有自己轉起來。`orbit_*` 這輪沒測幾何終點。

## 什麼時候不該用

- 角色自己要演、構圖可以改 → `img2video` 或 `character_video`
- 要循環特效 → `fx_loop`
- 要 mocap/姿勢影片驅動角色 → `pose_drive`
