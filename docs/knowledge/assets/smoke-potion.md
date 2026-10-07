---
type: asset-record
status: candidate
asset_id: smoke-potion
---
# smoke-potion — 技術測試素材

此頁遷移自 2026-10-01 產線 refactor smoke。狀態是候選、待美術審核者驗收，沒有已接受決定。

## Version 1 — candidate

- 圖片：![Smoke 測試候選圖](../../../output/agent_refactor_smoke_20261001/recorded/concept_00069_.png)
- Manifest：[concept.json](../../../output/agent_refactor_smoke_20261001/concept.json)
- 狀態：candidate（待驗收）
- 來源事件時間：2026-09-30T17:29:57+00:00（台灣時間 2026-10-01 01:29:57）
- Task／profile：`concept`／`sdxl_standard`
- Seed／尺寸：73101／512×512
- 決定與理由：測試事件的原始狀態為 agent candidate；理由為「Technical smoke test only; image contains multiple bottles despite a single-object request, pending [reviewer] review.」（原文的審核者姓名以 [reviewer] 代替）尚未收到美術審核者的 accepted/rejected 決定。
- 圖片 SHA-256：`168015dfd4de1c5f935c99e5329b8676036471be9ad4df8fcefe99827269ae38`
- Manifest SHA-256：`0f28673c81c72ef00b9c24df3eaeb40d6c62c9a8aa950a20adee0dddef743980`
- 檔案所在位置：圖片與 manifest 留在 repo 的 `output/agent_refactor_smoke_20261001/`，素材頁只提供相對連結，不複製圖檔。輸出內容包含多個瓶子，與單一物件要求不符。

這是一筆技術 smoke 的歷史候選，不是美術驗收通過或正式資產基準。`technical_validation=pass` 不能取代內容審核。
