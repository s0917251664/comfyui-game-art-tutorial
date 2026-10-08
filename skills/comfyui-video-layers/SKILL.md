---
name: comfyui-video-layers
description: 影片物件遮罩與 2D 層合成。物件追蹤預設用 SAM3 固定 template（`gameart.py run`）；SAM3 不可用時，以 ComfyUI server-side SAM 2.1 propagation（本工具）備援；另以固定 ordered layer graph 製作 2D 層合成候選。
---

# 影片圖層工具

圖層順序、遮擋意圖及內容驗收由[共用製作流程](../game-art-workflow/references/production.md)表達；本技能負責固定 ComfyUI server node 的部署、live preflight、SAM/runtime、遮罩／錨點契約及媒體驗證。共用圖層需求不能直接轉成平台影片操作；平台影片尚未整合。

當需求是從短影片追蹤一至數個區域，或將原片／透明圖片圖層按錨點合到靜態背景時，讀本技能。這是獨立的 ComfyUI server-side 工具，不是 `generate.py` task 或 video backend，也不會把靜態圖片 task 當影片處理。

先讀 [CLI、部署、plan 與實測限制](references/local-tool.md)。只使用固定 `GameArtVideoLayers` 單節點；`preflight` 核對 runtime、client/package/shared helper 檔案 hash、SAM 模型（segment 時）與 ComfyUI live schema，任一不符就停止，不 queue。Server node 另在工作開始時比對已載入 package hash，這項 gate 發生於執行階段。影片解碼、SAM propagation、仿射對齊、合成、編碼及完整輸出驗證都在 server；client 只查檔案/hash、送 queue 與下載。

要讓美術自己指定物件並追蹤整支影片時，預設用 SAM3 固定 template（[reference](references/sam3-track.md)；`video/sam3/track-mask` 第 0 幀手繪起手、`video/sam3/track-text` 英文名詞起手）：先 `gameart.py run <id> --preflight`，通過後實際執行，逐幀遮罩在 run 資料夾的 `outputs/masks/`，runner 也會產生 `keyframes/mask_preview.png` 給美術確認。SAM3 不可用時，才改用本工具：`vfx keyframes` → `mask_session.py` 手繪 → `vfx segment-plan`（第 0 幀必填，大動作片中段要加修正幀）→ 本工具 `run` → `vfx unpack-masks`；要只重畫遮罩內就交給 `generate.py video_inpaint`，見 [vfx-tools](../../docs/knowledge/video/vfx-tools.md#2-影片物件標記與局部重繪)。

`segment` 適合對 5 秒內片段，以 SAM 2.1 small 依首幀提示傳播 1–4 個物件遮罩；每個物件可在後續影格加提示修正。輸出白色選取、黑色排除的 `L` mask sequence，並附彩色遮罩預覽影片。這與 ComfyUI image edit 的反向 alpha 選區契約不同，不要直接互換。

`compose` 將靜態 RGB 背景與 1–8 個有順序的 source/image layer 合成。Source layer 需來自同來源影片、相同片段時間與畫布尺寸的 segment manifest，錨點由來源移動至目標固定位置；image layer 需 RGBA 圖與錨點，錨點從圖片位置追隨來源移動。image layer 使用 LK `track` 時可額外指定 `destination` 三點作起始 target placement，將跟蹤錨點映射到 target space，再帶動圖片錨點；`keyframes` 錨點則直接定義在 target space。兩者擇一。三點 LK forward/backward tracking（誤差大於 2 px 或追蹤失敗即停止）；keyframes 要首尾錨點，中間影格可選並線性插值。本機 Kabuto 原片 LK 曾在 frame 1 失敗，因此真實素材要逐段檢視；不能據合成平移單元測試推論實片追蹤可靠。需要前景後方保留底圖時提供目標尺寸白色遮擋 `L` mask。

來源遮罩可從原片 RGB 取用並搬移選中區域，未選部分由靜態底圖保留；仿射變換、混色與影片編碼會重採樣／改變像素，不能當作逐位元無損保留。它不會把已烘焙（baked）特效從背景、光照或材質中精確抽離。`screen` 只是帶來源污染的近似亮度疊加。這是 2D affine compositing，不做 3D 接觸、隱藏表面重建、重新打光或動畫目標身體替換；換臉也不等於替換整頭或身體。

實測輸出皆為 candidate。`segment` 的技術 pass 表示格式、影格 PTS/CFR grid、codec、音訊及完整解碼符合契約，不表示遮罩畫得準；`compose` technical status 固定 warning。2026-10-04 生產 8188 fresh preflight 及 production current segment/compose/occlusion smoke 均通過本次有界工具的技術檢查。獨立讀取逐幀 PNG 的 head/collar、手指遮擋與外套遮擋區域逐幀零變動；這不代表 MP4 無損或美術接受。甲片遮罩仍粗糙並漏選 glow，合成甲片貼到靜態人物的畫面左側衣袖且後段位置／比例／裁切錯。完整作品仍缺動態目標身體替換、形變／接觸處理及可用的精確特效遮罩；工具不承諾能從 baked effects exact 反演。道具手勢拇指離物、指緣不自然；腰帶尚未解決 3D 繞身接觸。每次仍需人工逐段檢查並由美術審核者決定接受與否。完整目標稽核見 completion audit（本機證據：`output/*-kabuto-upper-body/video-layers/completion-audit.md`）。
