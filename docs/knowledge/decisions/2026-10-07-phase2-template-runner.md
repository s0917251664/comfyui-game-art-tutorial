---
type: adr
status: accepted
date: 2026-10-07
---
# ADR：第二階段 template 格式與通用 runner 的 14 項決定

## 背景

Wan Animate（6 份）與 SAM3（2 份）的固定 API JSON，目前都靠 agent 手動呼叫 HTTP 執行。第二階段要定一套 template 格式和通用 runner，先接這 8 份，之後再把圖片 task 遷過來。規劃提出 14 個待決事項（D1–D14），使用者在 2026-10-07 全數採用建議方案。這一頁只記錄決定本身；格式細節以實作時的 `templates/_schema/` 與 runner 程式為準。

## 決定

| # | 主題 | 決定 | 落實時點 |
|---|---|---|---|
| D1 | template 位置 | 頂層 `templates/`，每份一個資料夾（`graph.api.json`＋`template.json`＋`README.md`）。graph 用 `git mv` 搬過去，位元組不變 | PR 2.1 |
| D2 | CLI 與 id | `gameart.py run <id>`，id 是路徑形式（例如 `video/wan-animate/mix`）；另有 `run list`／`run show` | PR 2.1 |
| D3 | 設定檔解析 | 從 repo 執行時，沒給 `--config` 就自動用 `<repo>/local_config.json` 並印出路徑；部署端維持不自動尋找。相對 `--config` 一律以 repo 根目錄解析，傳給子程序前轉成絕對路徑 | PR 1.5-B（smoke）、PR 2.1（runner） |
| D4 | seed | 允許 `auto`：runner 產生明確整數並寫進 result manifest；送出的 graph 不會有 `-1`。延伸段第二段 seed 預設等於第一段 | PR 2.1 |
| D5 | 模型 hash | 預設只核對檔案大小；`--verify-hashes` 才完整計算 sha256，並快取結果 | PR 2.2 |
| D6 | 未驗證平台 | template 標為 `untested` 的平台預設拒絕執行；加 `--allow-unverified-platform` 才送出，並記錄在 manifest。Mix graph 寫死 `device=cuda` 的問題，等 Mac 實測後再決定是否宣告平台覆寫 | PR 2.2 |
| D7 | result manifest | 新 kind `template_run_result`，欄位名稱和 `image_generation_result` 共用；`asset_review` 兩種都接受 | PR 2.3 |
| D8 | 規則變更 | [R2](../rules/fixed-graphs.md) 第 1 點改為「固定 API JSON 一律透過 template＋runner 執行」；技能文件裡「不要建立 Python client／CLI」的說法一併移除。手動 HTTP 只保留作除錯用的短附錄 | PR 2.4（runner 完成後才改規則正文；在那之前 R2 附註預定變更） |
| D9 | custom node 名稱 | 新名稱前綴 `GameArt`、分類 `GameArt/Video`。舊的 class 名稱與 socket 型別先保留為隱藏別名（對照見[改名與別名](../maintenance/custom-node-renames.md)），已存的 workflow 不會壞；第 8 階段唯讀掃描各機器的 saved workflows，確認沒有使用後才移除 | PR 2.5；移除在第 8 階段 |
| D10 | `output/` 連結 | 改寫成純文字標註「標籤（本機證據：`output/...`）」，並由 `tests/test_doc_links.py` 防止回歸；少數小型證據之後可視需要複製進 repo | PR 1.5-A（已完成，見[文件連結規則](../maintenance/doc-links.md)） |
| D11 | 換行與 hash | 有 hash 紀錄的檔案在 `.gitattributes` 設 `-text`；runner 比對 graph 時用 canonical JSON hash，不受換行影響 | PR 1.5-A（`.gitattributes`）、PR 2.1（canonical hash） |
| D12 | 舊 `template-manifest.json` | PR 2.1 先保留並改成指向新位置，PR 2.4 刪除並記錄在[轉址檔索引](../archive/redirect-stubs.md) | PR 2.1／2.4 |
| D13 | 圖片的結構變化 | LoRA、去背、ControlNet 等需要插入節點的變化，第二階段不決定；第 4 階段在「variant template」與「擴充 option 操作」之間擇一，以 99 組圖片 golden 的等價測試作為判準 | 第 4 階段 |
| D14 | Wan 單段幀數 | 只允許 17／33 幀（契約與實測範圍）；其他長度需要新的實測與 template 版本 | PR 2.1 |

落實狀態：D8 與 D12 已在 PR 2.4（2026-10-08）完成，R2 第 1 點改寫、技能改用 `gameart.py run`、舊 `template-manifest.json` 刪除。D9 的改名與別名在 PR 2.5（2026-10-08）完成，見[改名與別名](../maintenance/custom-node-renames.md)；移除舊名稱仍排在第 8 階段。

## 範圍與界線

- 這些決定不改變 R1：runner 的輸出一律維持 candidate，美術驗收仍由使用者決定。
- 平台狀態只能透過 PR 修改，runner 不會因為一次成功就自動升級。
- 第二階段不部署 `templates/`，runner 只從 repo 執行；部署留到第 8 階段。
