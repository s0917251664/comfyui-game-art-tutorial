---
name: comfyui-pipeline-review
description: 使用者明確要求審視本專案技能庫、ComfyUI／平台／本機工具執行路線、架構或查找模型新技術時，盤點現況、比較適配度與提出可追溯建議；不實作、不下載或替換。
---

# 產線與技能路線審視

使用者明確要求審視技能庫／工作流程／ComfyUI 使用方式、產線架構或研究模型與新技術時使用。先讀[維護索引](../../docs/knowledge/maintenance/README.md)、[技能庫路線與盤點](../../docs/knowledge/maintenance/skill-library.md)與[審視流程](../../docs/knowledge/maintenance/pipeline-review.md)，再依使用者範圍閱讀相關 skills、source、現有案例或 evidence。不要預設這類 review 一定是換模型，也不必把所有技術類別全部重掃。

先區分兩種工作：

- **技能庫／執行路線／架構審視：** 先以 repository 目前文件、程式和實測紀錄做離線盤點；只讀與問題相關的部分，不強制 web research。比較 brief、平台原生、ComfyUI API、既有 CLI、helper/custom node 的責任、依賴與使用摩擦，提出具體缺口及方案。
- **模型／當前技術研究：** 只有使用者明確要查新模型、當前新技術或升級候選時，才按指定範圍查一手來源並標日期。只提出目前基準、候選、相容性疑問、成本及有界建議；不下載、安裝、queue、改模型或修改 profiles。

報告要分清已實作、已實測、內容仍 candidate、僅有檔案／節點、構想及未驗證部分。說明哪些路線適合維持 direct API、哪些確實要既有 CLI 或本機 code，哪些只是尚未評估；不得把「適合改」寫成「已遷移」。不因使用者要求 review 而自動呼叫生成、下載模型或改 profile。單純 review 不作這些變更；若同一要求或先前上下文已明確授權具體文件／技能修改，可按該範圍直接實作，不重問。其餘後續改動交付具體建議，依使用者新指示處理。
