---
type: maintenance
status: current
---
# 平台驗證流程（smoke suite）

用固定的煙霧測試套件在一台機器上留下可比較的技術紀錄。**只是技術檢查**（task 能否執行、輸出可讀、尺寸與 hash、實際種子），不是美術接受；報告標記 `technical_only: true`、`content_review: not_performed`，不要拿來宣稱「美術可用」。

## 步驟

1. 部署最新工具：`python tools_src/gameart.py deploy`（dry run 確認）→ `deploy --yes`。`smoke.py` 與 `comfyui_pipeline/smoke_suites/` 會一併部署。
2. 確認快照新鮮：`python <ComfyUI>/tools/gameart.py doctor`（過期就 `doctor --refresh`）。ComfyUI server 要在跑。
3. 跑套件（從部署目錄執行，才會用到這台機器的快照）：

   ```
   python <ComfyUI>/tools/gameart.py smoke --output-dir <某個新資料夾> [--tasks concept,inpaint] [--profile sdxl_standard]
   ```

   預設套件 `image-core`；`--tasks` 只跑子集（上游依賴自動補入）。輸出：`smoke-report.json`、`smoke-contact-sheet.jpg`、各 task 輸出、`logs/<task>.log`、`<task>.result.json`。
4. 記錄進 repo：加 `--record <repo_root>`（可再加 `--record-images` 一併複製總覽圖 JPG），報告會複製到 `docs/knowledge/validation/<platform_key>/<日期>-<suite>-<profile>.json`，同名不覆寫。這一步不改任何 profile 的 `validation`；是否升級驗證狀態是另外的人工決定。

## 狀態語意

模型與節點由使用者選裝，**沒裝不是錯誤**。

| 狀態 | 意義 | 影響套件整體判定 |
|---|---|---|
| `pass` | 實際執行成功 | 是 |
| `fail` | capability 判定可用，卻執行出錯或逾時 | 是（唯一會失敗的狀態） |
| `not_installed` | 未安裝（使用者未選用），列出缺的模型／節點 | 否 |
| `skipped` | 其他原因略過：設定檔不提供該 task、平台不適用、上游沒輸出 | 否 |

整體為 `pass`（有執行且無 fail）、`fail`、或 `no_runnable_tasks`。結束碼只有整體 `fail` 才非 0。

## 固定內容

套件定義在 `tools_src/comfyui_pipeline/smoke_suites/image-core.json`：提示詞、種子、尺寸固定，輸入由套件自己產生（concept 輸出與 smoke 產生的中央矩形 RGBA 遮罩）。除 `layer_split`（無 `--seed`）外每個 task 都明確傳 `--seed`，報告同時記錄要求的與 manifest 解析出的種子。改套件內容會改變 `suite.sha256`，舊報告不可與新套件直接比較。
