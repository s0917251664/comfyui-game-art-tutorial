---
name: comfyui-extend
description: 需要的能力目前沒有、要新增或擴充技能／固定 graph（template）／task／custom node／本機工具時，照擴充協議提案與驗證；或使用者明確要求審視技能庫、執行路線、架構與新技術時盤點並提出建議。不臨場組 graph，不自行下載或替換模型。
---

# 擴充與審視

## 什麼時候用

- 使用者要的能力在 [template catalog](../../docs/knowledge/maintenance/template-catalog.md)、`generate.py` task 與本機工具裡都沒有，或要擴充既有能力。
- 使用者明確要求審視技能庫、執行路線、架構，或查新模型、新技術。

## 怎麼判斷

1. **能不能用既有的做到**：先對照 catalog 與 `gameart.py run list`。能用就用，不為「更快」新增。
2. **要新的固定 graph**：照 [擴充協議](../../docs/knowledge/maintenance/extension-protocol.md)。順序是提案、使用者確認、固定 revision 與 sha256、優先從官方範本或 core blueprint 派生、template 標 `draft`、測試、實機證據、另開變更改狀態。不臨場組、改接或拼接 graph（[R2](../../docs/knowledge/rules/fixed-graphs.md)）。
3. **要其他能力**（技能、task、custom node、本機工具、平台路線）：照 [新增能力檢查清單](../../docs/knowledge/maintenance/new-capability-checklist.md)，依實際路線核對發現入口、依賴、證據、測試與文件。不強制所有能力都走 ComfyUI 或 template；不經 ComfyUI 的像素／音訊工具維持 Python，文件寫清楚它是本機工具。
4. **只是審視**：照 [審視流程](../../docs/knowledge/maintenance/pipeline-review.md)，盤點現況、比較適配度、提出可追溯的建議。只提案，不實作、不下載、不替換。

## 什麼時候停下來問使用者

- 要安裝 custom node、Python 套件或下載模型：先說明容量與影響，取得同意；下載用固定 revision，逐檔驗 sha256。
- 新增 template 之前（協議第 2 步）、把狀態升為 `technical_pass` 之前、`validation approve` 之前。
- 查新模型或新技術：只在使用者明確要求時做，標來源日期。

## 原則

- 新能力的狀態從 `draft` 開始；平台狀態只能附實機證據、經獨立變更修改，runner 不會自動升級。
- 技術證據與美術驗收分開記錄（[R1](../../docs/knowledge/rules/candidate-review.md)）。
- 改完更新實際會走到的入口：`AGENTS.md`、[TOOLS.md](../../docs/knowledge/TOOLS.md)、[skills/README.md](../README.md)。
