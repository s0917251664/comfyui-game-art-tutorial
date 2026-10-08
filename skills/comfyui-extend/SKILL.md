---
name: comfyui-extend
description: 需要的能力目前沒有、要新增或擴充技能／固定 graph／task／custom node／本機 helper 時，照擴充協議提案與驗證；或使用者明確要求審視技能庫、執行路線、架構與新技術時盤點並提出建議。不臨場組 graph，不自行下載或替換模型。
---

# 擴充與審視

## 什麼時候用

- 使用者要的能力在 [template catalog](../../docs/knowledge/maintenance/template-catalog.md)、`generate.py` task 與既有工具裡都沒有，或要擴充既有能力。
- 使用者明確要求審視技能庫、執行路線、架構，或查新模型、新技術。

## 怎麼做

1. **新增固定 graph**：照 [擴充協議](../../docs/knowledge/maintenance/extension-protocol.md)。順序是：提案 → 使用者確認 → 固定 revision、sha256 pin → 優先從官方範本或 core blueprint 派生 → template 標 `draft` → 測試 → 實機證據 → 另開狀態 PR。不臨場組、改接或拼接 graph（[R2](../../docs/knowledge/rules/fixed-graphs.md)）。
2. **新增或擴充其他能力**（技能、task、custom node、本機 helper、平台路線）：照 [comfyui-new-tool-checklist](references/comfyui-new-tool-checklist/README.md)，依實際路線核對發現入口、依賴、證據、測試與文件。不強制所有能力都用 ComfyUI 或 Python。
3. **審視**：照 [comfyui-pipeline-review](references/comfyui-pipeline-review/README.md)，盤點現況、比較適配度、提出可追溯的建議；只提案，不實作、不下載、不替換。

## 判斷原則

- 安裝 custom node、Python 套件或下載模型之前，先說明容量與影響，取得使用者同意；下載用固定 revision，逐檔驗 sha256。
- 新能力的狀態從 `draft` 開始；平台狀態只能附實機證據、經 PR 修改，runner 不會自動升級。
- 技術證據和美術驗收分開記錄（[R1](../../docs/knowledge/rules/candidate-review.md)）。

舊技能 `comfyui-new-tool-checklist`、`comfyui-pipeline-review` 的完整內容保留在 `references/` 底下，對照表見 [技能收斂對照](../../docs/knowledge/maintenance/skills-6-mapping.md)。
