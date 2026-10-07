---
type: asset-record
status: candidate
asset_id: live-smoke-potion-20261001
date: 2026-10-01
---
# live-smoke-potion-20261001 — 實機 SDXL smoke

## Version 1 — candidate

- 圖片：!SDXL concept 實機候選（本機證據：`output/live_smoke_20261001_01/concept_00070_.png`）
- Manifest：concept.result.json（本機證據：`output/live_smoke_20261001_01/concept.result.json`）
- 狀態：candidate（待美術審核者驗收；未收到 accepted／rejected 決定）
- 日期：2026-10-01（使用者端日期）
- Task／profile：`concept`／`sdxl_standard`
- Checkpoint／seed：`sd_xl_base_1.0.safetensors`／`2026100101`
- 尺寸／模式：1024×1024／RGB，無透明
- 技術驗證：pass；ComfyUI `prompt_id`：`ca5bdf29-e4fc-4895-b735-4eca67abd329`
- 執行證據：fresh generation；history start `1790832939017`、success `1790832948493`，耗時 9.476 秒；`execution_cached` 節點為空。
- 圖片 SHA-256：`34f4dba2a66e9f2b27ed33d4ac29f0ad827d6b7394e96c60f44855f9a60fa329`
- Manifest SHA-256：`286a5d89b5fe5b82fabd2c7ad918fe52b4221e97899e5ea1da8cc7a5f69b6beb`
- 本次視覺觀察：單一圓玻璃瓶、綠液、棕色軟木塞，完整置中，未見文字；背景偏淡灰並有投影，未完全符合純白背景要求。這是單次輸出觀察，不代表所有 prompt 或模型表現。
- 原始 prompt 留在 manifest，不複製長 prompt 到素材頁。圖片與 JSON 保留於 `output/live_smoke_20261001_01/`；本頁只連結原檔，是否隨 repo 版控依 `.gitignore` 與實際提交狀態為準。

`technical_validation=pass` 不等於美術驗收通過；需由美術審核者看圖後決定是否接受。
