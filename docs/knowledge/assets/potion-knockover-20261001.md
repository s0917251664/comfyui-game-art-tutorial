---
type: asset-record
status: candidate
asset_id: potion-knockover-20261001
date: 2026-10-01
---
# potion-knockover-20261001 — 瓶子打翻影片

## Version 1 — candidate

- 影片：[potion_knockover_00001_.mp4](../../../output/potion_knockover_20261001_01/potion_knockover_00001_.mp4)
- Sidecar：[potion_knockover_00001_.mp4.json](../../../output/potion_knockover_20261001_01/potion_knockover_00001_.mp4.json)
- QA contact sheet（12 個取樣時點，僅供檢視、不是正式影格序列）：![12 個取樣時點](../../../output/potion_knockover_20261001_01/review_contact_sheet.png)
- 輸入靜幀：[concept_00070_.png](../../../output/live_smoke_20261001_01/concept_00070_.png)，SHA-256：`34f4dba2a66e9f2b27ed33d4ac29f0ad827d6b7394e96c60f44855f9a60fa329`
- 狀態：candidate（待美術審核者驗收；未收到 accepted／rejected 決定）
- 日期：2026-10-01（使用者端日期）
- Task／backend／seed：`img2video`／`h3`／`2026100102`
- 請求時長：4 秒；實際輸出：4.458333 秒、107 幀、24 FPS、768×768、H.264 + AAC 立體聲 32 kHz
- 技術驗證：pass，無 errors／warnings；耗時 218.136 秒；`prompt_id`：`1a4ce851-d2ad-4293-825a-96fb719601e0`；cached nodes 為空
- 影片 SHA-256：`293cb4f75db235fb540dfa07bffbc7461bfc24b36e41205bf4c612d66f1835a4`
- Sidecar SHA-256：`d8d57183605d86dfa047181f2fd4d6d87c8513df5a9ef3b517e614a1cf640d00`
- 人工抽看 12 個時點：手抓握並推轉瓶子，瓶塞脫落，瓶子傾倒，綠液流成一灘。整體較像手動轉倒／倒出藥水，碰撞力道弱，瓶頸方向有輕微生成變形；不宣稱完全符合物理碰撞翻倒。音訊技術存在，尚未主觀聽音驗收。
- 原始 prompt 與完整執行紀錄留在 sidecar；產出檔留在 `output/potion_knockover_20261001_01/`，本頁只連結原檔。

起初 preflight 因能力快照 schema 不符，在 upload／queue 前停止；更新本機已安裝內容的 `detect_video_capabilities` 快照後，沿用既有 task/backend 成功生成。未改程式或模型。`technical_validation=pass` 不等於美術驗收通過，須由美術審核者看片並主觀聽音後決定。
