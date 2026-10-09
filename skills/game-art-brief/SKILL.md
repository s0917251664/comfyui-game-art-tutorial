---
name: game-art-brief
description: 遊戲美術需求的共用入口：第一次使用時盤點需求與路線、把產圖／編修／特效需求整理成可執行可驗收的 brief、把多參考圖與指定部位編修對到既有 task，以及按需讀寫本專案知識庫（docs/knowledge/）。本技能不執行生成、不安裝。
---

# 遊戲美術 brief 與路線

需求端的入口：先把「要做什麼、保留什麼、怎麼驗收」講清楚，再交給執行技能。本技能不生成、不安裝、不呼叫 ComfyUI。

## 怎麼選

| 情況 | 做法 |
|---|---|
| 第一次使用、還沒選路線 | 先整理需求、盤點能力，不預設安裝。可以只用需求整理與平台圖片工具，不必裝 ComfyUI 或 Python。已有 ComfyUI 專案就沿用已選路線，用 `gameart.py doctor`（唯讀）看三份機器快照是否缺少或過期。見 [初始化](../../docs/knowledge/installation/initialization.md) |
| 整理產圖、編修、特效需求 | 照 [brief 與驗收](../../docs/knowledge/art/brief-and-acceptance.md)：來源與參考圖各自的用途、要改與要保留的、分階段、版本、驗收條件 |
| 多張參考圖、指定部位編修、要保留角色或結構 | 對照 [編修情境](../../docs/knowledge/art/edit-scenarios.md) 找到對應的 task 與界線；task 有沒有這個輸入以 `generate.py <task> --help` 為準 |
| 物件系列、特效、角色動作的製作方法 | 看 brief 頁的製作方法段，再交給執行技能 |
| 讀寫專案知識庫 | 先看 [TOOLS.md](../../docs/knowledge/TOOLS.md) 找主題，只讀需要的頁面，不載入整庫 |

## 交給哪個技能

| 選定的路線 | 技能 |
|---|---|
| 平台本身提供的圖片工具 | [platform-image-gen](../platform-image-gen/SKILL.md) |
| 本機 ComfyUI（圖片、影片、template、recipe） | [comfyui-run](../comfyui-run/SKILL.md) |
| 不經 ComfyUI 的本機像素、音訊、影片處理 | [local-media-tools](../local-media-tools/SKILL.md) |
| 安裝或部署 | [comfyui-install](../comfyui-install/SKILL.md) |
| 需要的能力目前沒有 | [comfyui-extend](../comfyui-extend/SKILL.md)，不臨場組 graph |

## 判斷原則

- brief 至少寫清楚：來源與參考圖的用途、要改與要保留的、交付格式、技術檢查與美術驗收分開。
- 技術通過不等於美術接受（[R1](../../docs/knowledge/rules/candidate-review.md)）；agent 不 accept、不 reject，只整理證據。
- 缺能力就如實說明，不自動換引擎，也不用相似 task 頂替（[R2](../../docs/knowledge/rules/fixed-graphs.md)）。
- 平台圖片、本機 ComfyUI、外部付費 API 是不同路線，不能互相推定模型或參數可用；目前沒有接外部付費服務。
- 知識筆記是參考，不是規則；不能只因為一則筆記就改 profile、參數或驗收結果。升格成規則要有可重現證據與使用者決定。
- 要停下來問使用者的時機：關鍵來源或修改範圍判斷不了、要安裝或下載、要接受或拒絕候選。已知的答案不重問。
