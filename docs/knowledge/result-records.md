# 圖片結果與素材版本／驗收紀錄

圖片生成 JSON manifest 是選用的技術追溯資料；要保存素材版本與人工決定時，使用 `docs/knowledge/assets/<asset-id>.md` 按需新增一頁 Markdown。一般出圖不需要建立素材頁。這套紀錄不改生成參數、不自動學習，也不取代能力檢查或看圖驗收。

## 生成 manifest（選用）

在圖片 task 命令加上 `--result-json <新 JSON 檔路徑>`。此旗標選用且僅支援圖片 task。目的路徑需以 `.json` 結尾，父資料夾必須已存在，不能覆寫既有檔案；生成成功且 PNG 技術檢查通過後才會建立 manifest。需 Pillow 讀取 PNG。路徑可以放在本次 `--output-dir`，不必改變預設圖片輸出位置。

Schema v1 的頂層欄位：

| 欄位 | 說明 |
|---|---|
| `schema_version`, `kind`, `status` | 固定為 `1`、`image_generation_result`、`completed` |
| `task`, `profile_id`, `profile_sha256` | task 與所選 profile；FLUX.2 的 profile 欄位為 null，profile hash 是 profile JSON 檔內容 SHA-256 |
| `backend`, `prompt_id` | 執行 backend 與 ComfyUI prompt id |
| `resolved_seeds`, `graph_output_dimensions`, `graph_sha256`, `selected_models`, `effective_conditioning` | 實際送出的 seed、尺寸、graph 摘要、模型檔名與文字編碼節點內容 |
| `task_parameters` | 非機密 task 參數、原始 prompt、實際 seed（可唯一判斷時）與實際輸出尺寸 |
| `inputs` | 輸入用途角色、圖片絕對路徑與 SHA-256 |
| `outputs` | PNG 的絕對路徑、SHA-256、寬高、mode、alpha channel 與實際透明像素狀態 |
| `technical_validation` | pass 僅代表輸出 PNG 可讀、尺寸有效且已記錄 hash；**不代表美術內容驗收通過** |
| `content_review` | 固定為 `pending`；人工決定由使用者明確給出並記在素材 Markdown 頁 |

CLI 例子（以所選 task 支援的參數為準）：

```powershell
<python_exe> <generate_script> concept --prompt "..." --comfy-url <comfyui_url> --output-dir <output_dir> --result-json <output_dir>\concept.result.json
```

manifest 是可選的追溯摘要，不足以保證逐像素重現。若使用，會記錄 prompt、實際參數、seed（單一值可解析時）、profile JSON digest、graph digest／conditioning、模型檔名及輸入／輸出 hash；`selected_models` 不含模型權重 SHA，graph digest 也不包含完整 graph JSON。完整重跑需要相符的模型權重、runtime、ComfyUI/nodes 和該機器版本證據（repo 檔案路徑：`docs/tested-versions.md`），backend 不承諾 PNG bytes 或 pixels 完全相同。

## 按需建立素材 Markdown 頁

只有要追蹤某素材的版本或驗收時才建立 `docs/knowledge/assets/<asset-id>.md`，不要預建大量空白模板。每個輸出版本單獨記錄；至少寫清楚圖片、狀態、日期和決定／理由。manifest 連結與 SHA-256 都是可選欄位。來源圖片與 manifest 留在原位置，可用相對路徑連出 vault；是否隨 repo 版控，以 `.gitignore` 和實際提交狀態為準，不要複製大型圖片來填滿知識庫。

以下模板可直接複製，示例欄位可依實際證據移除或補充：

```markdown
# <asset-id>

## Version 1 — candidate

- 圖片：![<版本描述>](<相對圖片路徑>)
- Manifest（選用）：[result.json](<相對manifest路徑>)
- 狀態：candidate（待 Steve 驗收）
- 日期：YYYY-MM-DD
- Steve 的明確決定與理由：尚未收到；不要將此版本標成 accepted 或 rejected。
- SHA-256（選用）：<若已取得則填實際值>
- 生成條件（選用）：task、profile、必要輸入與適用平台證據。
```

狀態只用 `candidate`、`accepted` 或 `rejected`。agent 可記 candidate 和客觀檢查結果，但不能代 Steve 選 accepted／rejected；只有 Steve 明確決定後，才更新狀態並逐字意涵忠實地摘要其理由和日期。`technical_validation=pass` 代表技術檢查通過，不代表圖像內容符合需求。新生成的輸出是新版本，必須從 candidate 開始，絕不繼承舊版 accepted 狀態。拒絕時保留版本紀錄與理由，不刪除來源圖片或證據。

素材頁是決策紀錄，不是 prompt log 或學習資料。長篇執行 log 留在原位置，不複製進頁面或 prompt；筆記不會自動更動技能、profile、CLI 預設或生成規則。要將觀察升為正式規則，須有可重現證據、明確適用範圍並經人工核准，再更新相應決策／設定。

## 使用者要求沿用已接受版本

使用者明確要求沿用既有版本時，依素材頁查找上一版，不依靠自動解析服務：

1. 確認素材頁中的某個版本確實由 Steve 明確標為 `accepted`；查看該版本原圖及可用的 manifest。
2. 原圖片必須仍存在並先查看。若素材頁有 manifest 或 hash 紀錄，就核對可用紀錄及必要輸入；若沒有，依素材頁已有資訊沿用並說明無法驗證完整同條件，不因缺少 manifest 而要求重建紀錄。核對可用的 task、profile、prompt、rating、輸入角色與 seed；素材頁已明確記錄的 seed 可照用；有 manifest 時先用 `task_parameters.seed` 的單一值，否則依該 task graph 的 `resolved_seeds` 判讀，不猜測。
3. 先按原 task 的現行 capability gate 確認本機支援，再照素材頁和可用 manifest 中記錄的資訊、以原 task 支援的旗標發出請求。若 manifest 有 `task_parameters.prompt`，它是使用者原始 CLI prompt；不要把 `effective_conditioning` 再 prepend 到 prompt。不要自行改 profile、增加未記錄的 conditioning 或盲目抽圖。
4. 新輸出記成新版本 candidate，需再次由 Steve 看圖決定；不得沿用原版 accepted 狀態。

若原圖片缺失，停止並告知無法沿用。若可用 manifest/hash 或必要輸入已變／缺失，或模型、runtime、ComfyUI/nodes 的版本證據不符，先說明條件差異，不得宣稱同條件重跑；沒有必要生成資訊時，詢問是否依當前可用條件繼續。沒有 manifest/hash 不會自動阻止工作，但須清楚說明驗證限制。

## 撤回前的舊作法（僅歷史）

2026-10-01 Steve 決定撤回先前的 SQLite `asset_library.py` 追溯方案，改以本頁規定的 Markdown 素材頁記錄版本與人工驗收。舊 CLI、SQLite 部署與資料庫要求都不是目前契約；相關測試／smoke 數字僅描述撤回前的歷史版本，不代表目前測試結果。撤回前測試中的真實候選已遷移到[素材頁範例](assets/smoke-potion.md)，仍為待 Steve 驗收。
