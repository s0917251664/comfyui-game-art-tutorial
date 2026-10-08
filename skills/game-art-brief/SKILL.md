---
name: game-art-brief
description: 遊戲美術需求的共用入口：第一次使用時盤點需求與路線、把產圖／編修／特效需求整理成可執行可驗收的 brief、把多參考圖與指定部位編修映射到既有 task，以及按需讀寫本專案知識庫（docs/knowledge/）。本技能不執行生成、不安裝。
---

# 遊戲美術 brief 與路線

這是需求端的入口。先在這裡把「要做什麼、保留什麼、怎麼驗收」講清楚，再交給執行技能。本技能本身不生成、不安裝、不呼叫 ComfyUI。

## 怎麼選

| 情況 | 讀哪裡 |
|---|---|
| 第一次使用、還沒選路線，或不知道該用哪個引擎 | [game-art-initialize](references/game-art-initialize/README.md)：先盤點需求與能力，不預設安裝 |
| 一般產圖、編修、特效需求要整理成 brief、分階段、定驗收 | [game-art-workflow](references/game-art-workflow/README.md)；物件系列、VFX、角色動作的方法看它的 `references/production.md` |
| 多張參考圖、指定部位編修、要保留角色或結構，要對到既有 ComfyUI 圖片 task | [game-art-edit-brief](references/game-art-edit-brief/README.md) |
| 讀寫專案知識庫（經驗筆記、決策、實測紀錄） | [project-knowledge](references/project-knowledge/README.md)，再從 [TOOLS.md](../../docs/knowledge/TOOLS.md) 找主題，只讀需要的段落 |

## 交給哪個執行技能

| 選定的路線 | 技能 |
|---|---|
| 平台本身提供的圖片工具 | [platform-image-gen](../platform-image-gen/SKILL.md) |
| 本機 ComfyUI（圖片、影片、固定 template、recipe） | [comfyui-run](../comfyui-run/SKILL.md) |
| 不用模型的本機像素／媒體處理（合成、換色、比較、去背、打包） | [local-media-tools](../local-media-tools/SKILL.md) |
| 安裝或部署 ComfyUI | [comfyui-install](../comfyui-install/SKILL.md) |
| 需要的能力目前沒有 | [comfyui-extend](../comfyui-extend/SKILL.md)：照擴充協議提案，不臨場組 graph |

## 判斷原則

- brief 至少寫清楚：來源與參考圖各自的用途、要改與要保留的部分、交付格式、技術檢查與美術驗收分開記錄。
- 技術通過不等於美術接受（[R1](../../docs/knowledge/rules/candidate-review.md)）。agent 不 accept、不 reject，只整理證據。
- 缺能力就如實說明，不自動換引擎，也不用相似的 task 頂替（[R2](../../docs/knowledge/rules/fixed-graphs.md)）。
- 平台圖片、本機 ComfyUI、外部付費 API 是不同路線，不能互相推定模型或參數可用。
- 知識筆記是參考，不是自動規則；不能只因為一則筆記就改 profile、參數或驗收結果。

舊技能 `game-art-workflow`、`game-art-edit-brief`、`game-art-initialize`、`project-knowledge` 的完整內容都保留在 `references/` 底下，對照表見 [技能收斂對照](../../docs/knowledge/maintenance/skills-6-mapping.md)。
