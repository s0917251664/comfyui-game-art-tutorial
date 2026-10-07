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
4. 記錄進 repo：跑的時候加 `--record <repo_root>`（可再加 `--record-images` 一併複製總覽圖 JPG），或事後對既有報告執行 `python tools_src/gameart.py smoke record <report.json> [--repo-root .] [--with-images]`。報告會複製到 `docs/knowledge/validation/<platform_key>/<日期>-<suite>-<profile>.json`，同名不覆寫，內容相同的報告不重複記錄。這一步不改任何 profile 的 `validation`。（`smoke run --output-dir ...` 是明確形式，與裸 `smoke --output-dir ...` 相同。）
5. 提案（唯讀）：`python tools_src/gameart.py validation propose <repo 內的報告>`。檢查報告在 `docs/knowledge/validation/` 內、報告綁的設定檔雜湊與目前設定檔一致，列出哪些 task 會升為 `verified`（只有 `pass`；`not_installed`／`skipped` 只是沒有證據，中性略過）與將寫入的證據項目。不寫任何檔案。
6. **使用者決定**：把 propose 輸出與總覽圖給使用者；美術與是否採信由使用者判斷。
7. 核准：`python tools_src/gameart.py validation approve <報告> --by <使用者>`，把證據項目附加到 profile 的 `validation`。報告不在 repo 內、設定檔雜湊不符、沒有任何 pass task、同一報告已核准過都會拒絕。之後檢視 `git diff` 並由使用者決定是否 commit。

> **agent 不得自行執行 `validation approve`。** 只有使用者在對話中明確要求核准，才可代為執行，`--by` 填使用者；不可替使用者決定，也不可為了讓狀態變綠而核准。propose／status 與 `smoke record` 可自行執行。

## 驗證證據綁定報告與環境

profile 的 `validation[<platform_key>]` 是證據項目清單：

```json
{"report": "docs/knowledge/validation/macos-mps/2026-10-06-image-core-sdxl_standard.json",
 "report_sha256": "...", "tasks": ["concept", "..."], "profile_sha256": "...",
 "env": {"comfyui_version": "0.34.0", "comfyui_commit": "...", "models_hash": "...", "custom_nodes_hash": "..."},
 "min_memory_mb": 18432, "approved_by": "reviewer", "approved_at": "2026-10-07T10:00:00+00:00"}
```

- task 在該平台是 `verified`：有證據項目涵蓋它，且可用記憶體不低於 `min_memory_mb`。
- **環境綁定**：`detect_image_capabilities`、`doctor`、`generate` 會用目前的環境指紋（ComfyUI 版本／commit、`models_hash`、`custom_nodes_hash`）與設定檔內容雜湊比對證據。證據存在但不一致 → `verified_other_env`，說明「已在 <日期> 的環境驗證；目前環境不同（comfyui 版本 x→y）」。這只是提醒，生成不阻擋；`edit`（image_edit_tools）仍須明確同意才跑非 verified 的 task。環境未知（讀不到指紋）時不比對、不降級。
- **legacy 項目**：舊式手寫紀錄（`legacy: true`、`report: null`，證據是 `docs/tested-versions.md`）沒有環境紀錄，視同 `verified`（能力快照的 `validation_basis: "legacy"`，`doctor` 註明「已驗證但無環境紀錄」）。沒有失敗證據前不降級；有新報告證據後會優先採用。舊式 dict 寫法仍可讀。
- **設定檔雜湊 `profile_sha256`** 是 `profiles.profile_content_sha256`：對 canonical JSON 取雜湊，**不含 `validation` 區塊**，所以記錄證據不會讓自己綁的雜湊失效；改模型、取樣、解析度或 task 需求則會變。新報告帶 `profile_hash_scheme: "content-v1"`。舊報告（沒有此欄位）是整檔原始位元組雜湊，`propose`／`approve` 一律拒絕，請用目前版本重跑 smoke 產生新報告。`image_results` manifest 的 `profile_sha256` 同樣改用內容雜湊（舊 manifest 是整檔雜湊）。
- `validation status [--profile] [--platform]` 列出 task × 平台的 `verified`／`legacy`／`unverified` 與證據連結。

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

## 規劃中（尚未實作）

以下兩項已討論設計，2026-10-06 決定**暫不實作**。目前沒有對應工具，不要假設已存在或自行臨場拼湊；要做時從這裡的設計接續。

### 變化偵測（`smoke compare`，未實作）

不是品質評分——品質只由人判斷。實測顯示同平台、同環境、同 seed 的 smoke 輸出 bit-identical，因此可比較兩份**同平台**報告：列出每個 task 為相同／已變更／未安裝，並把已變更者新舊並排成總覽圖給人看。不評分、不寫驗收紀錄；跨平台（如 MPS 與 CUDA）hash 本來就不同，不可比較。用途：升級 ComfyUI、換模型或改 graph 後，只需人工查看輸出有變的 task。

### 模型迭代流程（`gameart experiment`，未實作）

適用調整 profile 預設參數，或換模型／新增 profile。原則：工具只收集證據、讓比較容易，決定一律由人做；不自動評分、不自動改 profile、不跨平台比較 A/B。

1. profile 加 `stage: experimental | candidate | stable`；`experimental` 永不成為預設，需明確 `--profile`（FLUX.2 PoC 可用此表達）。stage 是採用決策，validation 是平台技術驗證，兩者分開。
2. `experiment new <名稱>`：在 `docs/knowledge/experiences/<日期>-<名稱>/` 建 `plan.json`（假設、baseline、candidate、task、固定 prompt／seed，預設沿用 smoke 套件輸入）。
3. `experiment run`：A／B 同 prompt、同 seed 各跑一次，每組並排總覽圖（即把 sweep 擴充為可比較 profile／模型）；自動產生實驗筆記草稿，事實欄位（環境、hash、耗時、未安裝項目）自動填，結論留空。
4. `experiment judge`：人逐組選 A 較好／B 較好／差不多／無法判斷，綁定兩邊輸出 hash、需 `--by`；彙整進筆記。這是人的判斷紀錄，不是工具分數。
5. 採用時由實驗筆記產生 `decisions/` ADR 草稿，人確認後才改 profile（commit 引用 ADR）。profile 內容 hash 改變會使各平台驗證自動失效，需各平台重跑 smoke → `validation propose` → 使用者同意後 `approve`。

追溯鏈：假設 → experiment run → 人工判斷 → 實驗筆記 → ADR → profile 變更 → 各平台 smoke／validation。
