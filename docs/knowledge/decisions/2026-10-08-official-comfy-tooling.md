---
type: adr
status: accepted
date: 2026-10-08
---
# ADR：不採用 comfy-cli／comfy-mcp，只對齊官方範本欄位與 core subgraph blueprints

## 背景

使用者在 2026-10-08 要求評估官方的 Comfy MCP（https://comfy.org/mcp）和官方 CLI comfy-cli，看是否該引入官方做法，避免重複造輪子。評估對象：
- comfy-mcp 0.10.0：本機 stdio MCP server，本質是 comfy-cli 的薄包裝；
- Comfy Cloud MCP；
- comfy-cli 1.22.0；
- Comfy-Org/workflow_templates；
- ComfyUI core 的 subgraph blueprints 與 Node Replacement API。

評估報告存放在審核端，沒有收進 repo。這一頁只記錄決定和主要理由。

## 決定

1. **不採用 comfy-cli、comfy-mcp，也不安裝。** 不當 runtime 依賴、開發工具，也不當 agent 工具。Comfy Cloud 也不採用。
2. **只參考兩種官方格式：**
   - [官方 workflow_templates](https://github.com/Comfy-Org/workflow_templates) 的範本欄位；
   - ComfyUI core 的 subgraph blueprints（`blueprints/`）。
3. **`template.json` 新增對齊官方的欄位**（第 3 階段起）：

   | 我們的欄位 | 對應的官方欄位 |
   |---|---|
   | `min_comfyui_version` | `minComfyUIVersion` |
   | `requires_custom_nodes` | `requiresCustomNodes`（registry id；repo 自己的節點另外標示） |
   | `models[].url`、`models[].directory` | 節點 `properties.models` 的 `url`、`directory`（sha256 我們已經有） |
   | `provenance.upstream` | 官方範本名稱或 blueprint 檔名，加上 blob／commit 與 ComfyUI 版本 |

   落實狀態：PR 3.2 完成。validator 檢查欄位一致性，preflight 依 `min_comfyui_version` 擋下版本太舊的 ComfyUI；8 份 template 補齊欄位並各升 patch。欄位規則見 [templates/README](../../../templates/README.md)「規則」。

4. **新 template 的來源：** 官方已有對應的範本或 blueprint 時，從它派生並記錄 blob。我們仍然固定成 API 格式的 `graph.api.json`，雙 hash 等規則不變（見[第二階段 ADR](2026-10-07-phase2-template-runner.md)）。
5. **第 8 階段**評估過 ComfyUI core 的 Node Replacement API。結論是直接移除舊名稱，不採用 replacement。理由與條件見[退場決定](2026-10-08-node-alias-exit.md)。Node Replacement 是 ComfyUI 本體的功能，不是 comfy-cli。

## 理由

- **runner 語意不同：**
  - 官方上傳只能放到 input 根目錄，CLI 預設會覆蓋；我們上傳到 `input/<run_id>/` 且不覆蓋。
  - 官方的模型下載不驗 sha256。
  - 已登入 Comfy Cloud 時，官方工具會自動把指令送去雲端。
- **我們的核心官方沒有：** graph 位元組與 canonical hash、slot 差異白名單、模型 sha256 pin、平台 gate、`run.result.json`、技術通過與美術驗收分開（[R1](../rules/candidate-review.md)）。這些都必須保留，官方工具能取代的部分很少。
- **成熟度與依賴：**
  - comfy-mcp 是 pre-1.0（README 寫 beta），也沒有 Windows CI。
  - 兩者是 AGPL／GPL 授權，而且依賴一大串第三方套件；runner 的規則是只用標準庫。
- **官方格式本身值得對齊：** 對齊後，之後要和官方範本比對、從官方升級時成本較低，也不必引入任何執行期依賴。

## 範圍與界線

- 不改變 [R2](../rules/fixed-graphs.md)：固定 API graph 一律透過 template＋runner 執行。
- 官方範本與 blueprint 是 UI 格式，只用來當來源與對照，不直接執行。
- 要重新評估，必須由使用者提出。可能的時機：官方工具支援上傳子資料夾且不覆蓋、下載時驗 sha256，並且進入 1.0、有 Windows CI。

## 來源

- https://comfy.org/mcp
- https://docs.comfy.org/agent-tools/cli
- https://github.com/Comfy-Org/comfy-cli
- https://github.com/Comfy-Org/comfy-mcp
- https://github.com/Comfy-Org/workflow_templates （`docs/SPEC.md`、`templates/index.schema.json`）
- https://docs.comfy.org/custom-nodes/subgraph_blueprints.md
- https://docs.comfy.org/custom-nodes/backend/node-replacement.md
