---
type: adr
status: proposed
date: 2026-10-08
---
# ADR 草稿：custom node 舊名稱別名的退場方式（PR 8.1）

> **狀態：proposed，需要使用者決定。** 離線部分（掃描、讀 ComfyUI 原始碼、用 core 程式離線驗證）已完成；實機測試已準備好，等主 session 統一排程。實機結果只影響方案一（Node Replacement）是否可行，不影響本頁的建議。

## 背景

PR 2.5（[D9](2026-10-07-phase2-template-runner.md)）把 repo 自己的 custom node 改成 `GameArt*`，舊 class 名稱和換臉的舊 socket 型別保留成隱藏別名，對照見[改名與別名](../maintenance/custom-node-renames.md)。舊名稱在程式裡只剩 `comfyui_*/contracts.py` 的 `LEGACY_*` 常數。第 8 階段要決定別名怎麼退場（[交接文件](../maintenance/restructure-handoff.md)第 4 節 8.1），[官方工具 ADR](2026-10-08-official-comfy-tooling.md) 第 5 點要求評估 ComfyUI core 的 Node Replacement API。

環境：Windows、ComfyUI v0.34.0（commit `12d52794`）、前端 `comfyui_frontend_package` 1.49.6、repo `develop` `5f1d31e`。

## 掃描結果（Windows，唯讀）

掃描 `<ComfyUI>/user/` 底下所有名為 `workflows` 的資料夾（本機只有 `user/default/workflows/`）。舊名稱從 `contracts.py` 的 `LEGACY_*` 讀，不寫死。掃描前後比對每個檔案的大小和 mtime，確認沒有改動。（本機證據：`output/verify-20261008-8.1/scan-workflows.json`）

| 項目 | 結果 |
|---|---|
| 掃描的 workflow | 9 份（全是 UI 格式） |
| 用到舊名稱的 workflow | **1 份**：`Ch8_影片換臉_Server.json` |
| 這份裡的舊節點 | 換臉讀取 1 個、換臉 ReActor 1 個（就是整個 workflow，共 2 個節點） |
| 舊 socket 型別 | 2 個 slot（讀取的輸出、ReActor 的 `source` 輸入）、1 條連線 |
| Video Layers 舊名稱 | 0 |
| 掃描後檔案有沒有變 | 沒有 |

另外掃了 repo 的 `output/`（ignored，只有這台機器有）：有 **21 份**舊的 API prompt（`workflow_api.json`）用到舊名稱，換臉 7 份、Video Layers 14 份；**21 份的舊名稱節點全部沒有 `_meta`**（repo 的 client 送出時本來就不寫 `_meta`）。這和問題 ④ 直接相關。（本機證據：`output/verify-20261008-8.1/scan-output-api-graphs.json`）

**Mac 還沒掃。** 移除前要在 Mac 用同一支唯讀腳本補掃（腳本在 `output/verify-20261008-8.1/scan_legacy_nodes.py`，要複製過去或改寫）。

## 四個問題的答案

標示：**已驗證**＝讀原始碼並用 core 程式離線執行確認；**讀程式**＝只讀原始碼；**等實機**＝要在測試實例跑過才能確定。離線驗證直接 import 本機 ComfyUI 的 `app/node_replace_manager.py` 與 `comfy_api.latest._io.NodeReplace`，`nodes` 用假的 mapping，不啟動 server、不寫 `__pycache__`。（本機證據：`output/verify-20261008-8.1/offline-replace-check.json`）

### ① V1 寫法的套件怎麼註冊 replacement（讀程式；等實機）

- `nodes.py` `load_custom_node`：模組有 `NODE_CLASS_MAPPINGS` 就走 V1 分支後直接 `return True`，`elif hasattr(module, "comfy_entrypoint")` 不會執行。所以**同一個套件同時放 `comfy_entrypoint` 沒有用**，官方文件寫的「在 extension 的 `on_load` 註冊」也就用不到。
- 官方文件（[node-replacement](https://docs.comfy.org/custom-nodes/backend/node-replacement.md)）只寫 V3 寫法，沒有 V1 的說明。
- 可行的三種做法：
  1. **V1 模組 import 時用同步 API**：`ComfyAPISync().node_replacement.register(io.NodeReplace(...))`。`main.py` 先建立 `PromptServer`（第 536 行）才載入 custom node（第 542 行），而 `ComfyAPISync` 會在 thread pool 裡另開 event loop 執行 async 版的 `register`，不會卡住正在跑的主 loop。這是公開 API（`comfy_api.latest`，但 `STABLE = False`）。
  2. 直接呼叫 `PromptServer.instance.node_replace_manager.register(...)`：同步、最簡單，但用的是內部屬性。
  3. 另外部署一個只有 `comfy_entrypoint`、沒有 `NODE_CLASS_MAPPINGS` 的小套件，在 `on_load` 註冊。符合官方寫法，但要多部署、多驗一個套件。
- 三種都還沒在真的 server 上跑過，列為實機 L1、L2。

### ② 換臉的舊 socket 型別能不能用 input/output mapping 表達（API 端已驗證；UI 端等實機）

- mapping 本身**不處理型別**：`input_mapping` 只對應輸入名稱或設定值，`output_mapping` 只對應輸出 index。
- **API prompt**：連線只存 `[node_id, output_idx]`，沒有型別字串。後端 `apply_replacements` 把讀取和 ReActor 兩個舊節點都換成新名稱、連線保持 `["1", 0]`；之後的型別檢查用的是新類別，兩端都是新型別，所以相符。離線驗證確認 class 名稱、所有輸入、連線都正確（案例「Q2」）。
- 要整組換：只換一半（舊讀取接新 ReActor）在別名還在時會型別不符。別名移除後兩個舊名稱都會被替換，不會出現一半的情況。
- 注意：`apply_replacements` 先清空輸入（`empty_inputs=True`），只搬 `input_mapping` 列出的輸入，**漏列的輸入會被丟掉**；而 `input_mapping` 列了、舊 prompt 卻沒有的輸入會 `KeyError`。離線驗證兩種情況都重現了，mapping 必須完整列出所有輸入。
- **UI workflow**：替換由前端做（`useNodeReplacement.ts`），只在節點「缺少」（沒有登記）時出現在錯誤面板，由使用者按替換；它搬 link 的 origin／target，但**沒有改 link 上記錄的型別字串**。換完後連線是否正常、存檔後的型別字串是什麼，要實機看（L7）。

### ③ 舊名稱還在 `NODE_CLASS_MAPPINGS` 時 replacement 不會觸發（已驗證）

- 後端：`apply_replacements` 只處理 `class_type not in nodes.NODE_CLASS_MAPPINGS` 而且有 replacement 的節點（`app/node_replace_manager.py` 第 69 行）。
- 前端：`missingNodeScan.ts` 跳過已登記的型別（`originalType in LiteGraph.registered_node_types`），所以不會出現替換選項。
- 離線驗證：新舊名稱都登記時，prompt 原封不動（案例「Q3」）。
- 結論：**Node Replacement 和隱藏別名不能同時生效**，採用 replacement 就一定要先刪掉別名類別。

### ④ 沒有 `_meta` 的 API prompt 會不會出錯（已驗證：會）

- `copy_node_struct` 無條件執行 `node_struct["_meta"].copy()`（第 25 行），對需要替換、但沒有 `_meta` 的節點會 `KeyError: '_meta'`。
- `server.py` 的 `/prompt` 處理（第 1110 行）呼叫 `apply_replacements` 時沒有 try/except，所以預期回 **HTTP 500**；`validate_prompt` 本身對缺 `_meta` 是安全的（用 `.get`），問題只在 replacement 這一步。
- 離線驗證：舊名稱、沒有 `_meta`、已移除別名 → `KeyError: '_meta'`（案例「Q4」）；同樣的 prompt 在別名還在時不受影響。
- 影響：repo 的 21 份舊 API prompt 全部沒有 `_meta`。採用方案一之後重送它們會得到 500，而不是清楚的「缺少節點」400。HTTP 狀態碼要實機確認（L4）。

## 三個方案比較

| | 方案一：Node Replacement | 方案二：直接移除別名 | 方案三：繼續保留 |
|---|---|---|---|
| 舊 UI workflow（本機 1 份） | 開啟時出現缺少節點，使用者按替換；連線型別字串要實機確認 | 開啟時出現缺少節點，要手動換成新節點（2 個節點、1 條線） | 照常載入、執行 |
| 舊 API prompt（`output/` 21 份） | 沒有 `_meta`，重送預期 HTTP 500 | 重送回 400 `missing_node_type`，訊息清楚 | 照常執行 |
| 程式裡的舊名稱 | 還在：replacement 的 `old_node_id` 要寫舊名稱；舊 socket 型別可以刪 | 全部刪除，`test_neutral_wording` 的例外也刪 | 維持現況（`LEGACY_*`＋例外） |
| 依賴 | `comfy_api.latest`（`STABLE = False`）；V1 要用同步 API 或內部屬性，或多一個套件 | 無 | 無 |
| 維護 | 新增註冊程式與測試；每次升級 ComfyUI 要留意 API | 最少 | 別名類別與測試要一直維護 |
| 風險 | `_meta` 的 500；input mapping 漏列會靜默丟輸入；實機未驗證 | 唯一的舊 workflow 要先遷移；Mac 未掃 | 無技術風險；舊名稱一直留在程式裡 |

## 建議

**採用方案二（直接移除別名），條件是先完成遷移與 Mac 掃描。** 理由：

1. 使用量極小：本機只有 1 份 UI workflow 用到，而且整份就是那 2 個節點，手動換掉只要幾分鐘。
2. Node Replacement 對我們的情況幫助很小：UI 端本來就要使用者自己按替換；API 端因為我們的 prompt 沒有 `_meta`，反而會從清楚的 400 變成 500。它也沒辦法讓舊名稱從程式消失（`old_node_id` 還是要寫），而且依賴標示為不穩定的 `comfy_api.latest`。
3. 方案二最簡單、錯誤最清楚，也能把舊名稱完全移出程式與測試例外。

8.2 的順序：

1. 使用者在 UI 開啟 `Ch8_影片換臉_Server.json`，把兩個節點換成 GameArt 節點後另存（agent 不改使用者的 workflow）。
2. Mac 用同一支唯讀腳本掃描；有用到就同樣處理。
3. 兩台都重新掃描、結果為 0 後，再做 8.2：刪別名類別與 `LEGACY_*`，同步 `test_neutral_wording` 與[改名頁](../maintenance/custom-node-renames.md)。
4. 改名頁註明：`output/` 裡改名前的 API prompt 只當紀錄，不能再重送；要重送就先把 `class_type` 換成新名稱。

如果使用者希望舊 API prompt 移除後仍能重送，比較合適的做法是在 repo 的 client 端（重送工具）改寫 `class_type`，而不是採用 Node Replacement。這不在 8.1 的範圍。

## 需要使用者決定

1. 選哪個方案：方案二（建議）／方案一／方案三。
2. 方案二的話：同意由使用者自己在 UI 遷移 `Ch8_影片換臉_Server.json`。
3. Mac 掃描由誰、什麼時候做；Mac 沒掃之前，8.2 是否先不開。
4. 接受 `output/` 裡 21 份改名前的 API prompt 從此只當紀錄、不能直接重送。
5. 是否等實機結果（L1–L7）出來再決定。只有選方案一才需要等；選方案二只需要 L6（確認移除後的錯誤是 400）。

## 實機測試（已準備，等主 session 排程）

測試用一個隔離的 CPU 測試實例（port 8199、`--base-directory` 指到測試資料夾、記憶體資料庫），custom_nodes 只有測試 stub，不載入、不修改使用者的 ComfyUI；stub 的名稱、socket 型別、輸入規格和 repo 節點一致，執行時不處理媒體。五個方案的 base、6 份 stub API prompt、合成的舊名稱 UI workflow、自動檢查腳本與步驟說明都已備妥。（本機證據：`output/verify-20261008-8.1/pending-live/README.md`）

| 編號 | 內容 | 狀態 |
|---|---|---|
| L1 | ① V1 套件 import 時用 `ComfyAPISync` 註冊 | 等實機 |
| L2 | ① 對照：內部屬性、獨立 V3 套件 | 等實機 |
| L3 | ③ 別名還在時不替換（server 端） | 等實機（離線已驗證） |
| L4 | ④ 沒有 `_meta` 時的 HTTP 狀態碼（預期 500） | 等實機（離線已驗證會 `KeyError`） |
| L5 | ② API 端整組替換、只換一半 | 等實機（離線已驗證整組替換） |
| L6 | 方案二：舊 prompt 的錯誤樣子（預期 400 `missing_node_type`） | 等實機（讀程式） |
| L7 | ② UI 端：前端替換後連線與型別字串、widget 值、重新載入 | 等實機 |

## 來源

- 本機 ComfyUI v0.34.0：`app/node_replace_manager.py`、`server.py`（`/prompt`）、`nodes.py`（`load_custom_node`）、`main.py`、`comfy_api/latest/__init__.py`、`comfy_api/latest/_io.py`（`NodeReplace`）、`comfy_api/internal/async_to_sync.py`、`comfy_extras/nodes_replacements.py`、`execution.py`（`validate_prompt`）。
- 前端 1.49.6 的 source map：`useNodeReplacement.ts`、`missingNodeScan.ts`、`nodeReplacementStore.ts`、`coreSettings.ts`（`Comfy.NodeReplacement.Enabled` 預設開）。
- https://docs.comfy.org/custom-nodes/backend/node-replacement.md
