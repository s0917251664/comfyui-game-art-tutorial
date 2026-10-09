---
type: tool-guide
status: active
---
# Video Layers：影片遮罩與 2D 圖層合成

`video_layers.py`（`gameart.py video-layers`）是固定 `GameArtVideoLayers` ComfyUI server node 加薄 client 的獨立工具，不是 `generate.py` task 或影片 backend，也不是 template。server 端做解碼、SAM 2.1 遮罩傳播、2D 仿射合成、音訊與輸出驗證；client 只做 preflight、queue、下載。plan 格式與旗標查 `video_layers.py --help`；部署與雙位置 package 一致性由 `gameart.py deploy` 與 preflight 處理。

## 什麼時候用

- **物件追蹤遮罩**：預設用 SAM3 template（[SAM3 追蹤](sam3-tracking.md)）；SAM3 不可用時才用這裡的 `segment` 備援。
- **2D 層合成**：把原片的選取區域或 RGBA 圖片，依錨點合到靜態背景上，可帶明確的前後遮擋 matte。2D 層合成一律用這個工具（compose）。

## 判斷與已知界線

- 遮罩約定：白色選取、黑色不選，和圖片 inpaint 的反向 alpha 不同，不可直接互換。
- `segment` 適合 5 秒內的片段（最多 300 幀）、1–4 個物件，首幀提示必填，後續影格可補修正。大動作片只塗第 0 幀會在中段漏選或多選（實測第 14 幀後尾巴被選進去）。技術 pass 只表示格式與影格時間軸正確，不表示遮罩畫準。
- `compose` 的錨點用 `track`（三點 LK 光流，誤差大於 2 px 或追蹤失敗就停止）或 `keyframes`（目標空間，首尾必填、中間線性插值），兩者擇一。真實素材的 LK 追蹤在第 1 幀失敗過，**要逐段檢視，不能由合成單元測試推論實片追蹤可靠**。technical status 固定 warning，內容永遠是 candidate。
- 它是 2D 仿射合成：不做 3D 接觸、隱藏表面重建、重新打光，也不替換動畫目標的身體。仿射重採樣、混色、H.264 編碼都會改像素，不是逐位元無損；`screen` 只是帶來源污染的近似亮度疊加。
- **無法從已烘焙的特效反演**：特效若已和背景、光照、材質烘在同一個畫面，無法精確抽成獨立 RGBA 層。
- 2026-10-04 的整合測試（甲片、道具、腰帶）顯示：甲片遮罩粗糙且漏選外溢光暈，合成位置、比例與裁切錯誤；靜態照片重複成影片，手勢的拇指離物、指緣不自然；腰帶的照片透視與 3D 繞身接觸沒解決。遮擋區域的 PNG 逐幀零變動，只代表 matte 區域像素正確，不等於 MP4 無損或美術接受。完整變身影片未完成：缺動態目標身體替換、形變與接觸處理、可用的精確特效遮罩。

## 部署提醒

- 輸出資料夾要用繼承上層權限的新資料夾（Windows 上 `mkdtemp()` 的私有權限在 rename 後會讓其他身份讀不到結果，工具已改用隨機名稱的 stage 資料夾再 rename）。
- 執行時 server 會核對已載入的 package hash；更新 package 後要重載 server 並重做 preflight。runtime 版本 pin 是本機 gate，不代表跨平台通用。
- 影片檢查、音訊編碼與時間軸 helper 已獨立在 `comfyui_video_layers/source_media.py`，不再借用其他套件；更新後要重新 deploy 並重做 preflight。
