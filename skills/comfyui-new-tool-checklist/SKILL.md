---
name: comfyui-new-tool-checklist
description: 為新增圖片、影片或本機工具能力建立適用的安裝、程式、實測與文件檢查；依能力類型勾選，不把不相關流程強加進來。
---

# 新工具/新能力上線檢查清單

給任何操作這個 repo 的 agent(Claude Code、Codex、Gemini CLI 等)使用的技能說明。

## 何時使用

當要幫這條產線新增工具、技術、task 或既有 task 的新參數時使用——包括圖片 task／模型、影片 task／backend，或 Simple Mask、SAM、合成等本機工具。先辨認本次受影響的能力類型，可同時涉及多類；逐項檢查適用性，不能因改動小而省略適用項目。既有能力的純文件修正不套用完整新增能力流程。

這份清單不是憑空想的,是把這個專案實際新增 ControlNet Pose/Depth、Upscale 這兩個能力時走過的完整流程整理出來的——過程中踩過的坑(文件跟程式碼講的不一樣、workflow JSON 手滑寫壞格式、模型寫死綁定 SDXL 卻沒講清楚)都變成了下面的檢查項目。

## 核心原則

- 檢查要和能力類型及風險相稱：圖片生成才檢查圖片 graph／模型與 `comfyui-art-gen`，影片才檢查影片 backend／runtime 與 `comfyui-video-gen`，本機工具才檢查自己的 CLI、輸出與部署；不要一律要求 custom node、ComfyUI queue 或另一個 skill。
- 適用的每一步都要真的做，跳過時寫明原因；文件/程式碼/部署不同步會讓接手的人看到矛盾資訊。
- 完成後要能有信心回答這句話:「如果現在讓一個完全沒看過這次對話的人接手,他讀這些文件能不能正確理解、正確使用這個新工具?」
- 不因為清單存在就增加沒有必要的流程、資料夾或 workflow；只留下能證明這項能力可用的最小證據。

## 檢查清單

### 1. 安裝面（依能力類型）

- [ ] **圖片模型／custom node：** 模型來源加進 `skills/comfyui-install/reference/models.md`，custom node 安裝步驟更新 `skills/comfyui-install/SKILL.md`，附用途、最後確認日期與底模家族；實際安裝或如實記錄尚未安裝。
- [ ] **影片模型／runtime／node：** 更新影片安裝與 capability 說明，標明 backend 綁定與實際依賴；實際安裝或如實記錄尚未安裝。
- [ ] **本機工具：** 檢查自己的 Python 套件、外部 runtime、本機路徑與部署契約；若工具包含 Simple Mask 這類 custom node，照其契約同步 `tools/` 與 `custom_nodes/`，沒有則不新增無關依賴。

### 2. 程式碼與部署面

- [ ] **圖片／影片 task：** 保持必要輸入與參數最小化；圖片模型檔名、取樣參數、解析度與 task 範圍放在既有 image profile，影片能力放在 video catalog／capability config；FLUX.2 維持獨立路線，不套用 image profile。
- [ ] **修改 `tools_src/generate.py` 或 `tools_src/comfyui_pipeline/` 時：** 至少檢查語法與受影響的測試；圖片 graph 有刻意變更才執行 `python tests/golden_image_graphs.py --write`，並審查 diff 確認只有預期節點變更。
- [ ] **部署產線 facade／package 時：** 同步 `tools_src/generate.py` 與整個 `tools_src/comfyui_pipeline/` 到 `<ComfyUI 安裝路徑>/tools/`；只改本機工具時改走該工具自己的部署契約。
- [ ] **本機工具程式碼：** 依其實際入口與 package 一起驗證、部署；若有 custom node，確認 `tools/` 與 `custom_nodes/` 的同步範圍。
- [ ] 至少確認受影響 Python 檔案語法沒錯（例如 `python -c "import ast; ast.parse(open(...).read())"`）。
- [ ] 非顯而易見的技術決策與已知限制寫在受影響的程式碼或文件中。

### 3. 實測驗證（依能力類型）

- [ ] **圖片：** 實際呼叫受影響的 task／參數，檢查 ComfyUI graph、輸出尺寸／格式／通道與主觀畫面驗收；模型設定檔的 `validation` 只有實機驗收後才能標 `verified` 或 `experimental`。
- [ ] **影片：** 實際呼叫受影響的 task／backend，檢查 runtime、輸出契約、sidecar、音訊與畫面驗收。
- [ ] **本機工具：** 直接執行工具的 smoke test，檢查輸出檔案、格式與錯誤處理；不要求 ComfyUI queue。
- [ ] 沒有相符的實機環境時，如實記錄未驗證項目，不把離線檢查當成實測通過。

### 4. 文件面（只更新受影響入口）

- [ ] **圖片 task／參數：** 更新 `skills/comfyui-art-gen/SKILL.md` 的任務判斷、必要輸入與 CLI；參數細節放 `skills/comfyui-art-gen/reference/full-params.md`。
- [ ] **影片 task／backend：** 更新 `skills/comfyui-video-gen/SKILL.md` 與必要的影片 reference。
- [ ] **本機工具：** 更新該工具自己的 skill／reference、`AGENTS.md` 部署說明或 `教學.md` 受影響段落，不補無關圖片流程。
- [ ] 新增技能時，在 `AGENTS.md` 核心文件清單加入入口與觸發條件；既有技能分工改變時同步更新。
- [ ] `教學.md` 的功能地圖或操作段落只有在能力對外可用時才更新，並附實測證據；尚未實測就明確標示。
- [ ] SKILL.md 保留每次都要走的判斷、必要輸入與指令；踩坑、完整參數與邊界情況放 reference，避免入口膨脹。

### 5. workflows/(選配,不是義務性同步)

`workflows/` 不進版控(見 `.gitignore`),是維護者(不是美術)本機除錯/開發用的視覺化參考,不是要交付給使用者的東西,**不要把「補 workflow JSON」當成每個新能力都一定要做的步驟**。

- [ ] 真的有花時間在 ComfyUI 網頁介面手動組過對應節點圖(例如開發新能力時拿來驗證邏輯),順手存一份到 `workflows/*.json` 沒問題,命名跟現有檔案慣例(`ChN[字母]_描述.json`)對齊——但這是「剛好做了就留著」,不是額外再花時間去補
- [ ] 如果真的手動寫或修改了這份 JSON(而不是從 ComfyUI 介面存出來的),**要寫程式驗證過**再交付:每個節點的 `pos` 是不是恰好 2 個數字、`last_link_id` 是否等於實際最大 link id、每條 link 兩端指到的節點 id 是否存在——這些是這個專案實際踩過的低級錯誤(手滑寫壞格式),不要重蹈覆轍

### 6. 收尾

- [ ] 跟使用者總結:裝了什麼、改了哪些檔案、測過什麼(附證據,例如輸出尺寸/格式)、還缺什麼——如實講,不要隱瞞
- [ ] 過程中如果發現「寫的時候才發現」的既有問題(像這個專案發現 ControlNet/IPAdapter 寫死 SDXL 的技術債那樣),要明確講出來,不要悄悄繞過去當作沒看到

## 情境 B：新增模型設定檔

要讓同一組 task 跑在另一套模型上（例如輕量 SDXL 蒸餾版、補齊 SD1.5 版 ControlNet/IPAdapter）。**設定檔代表一組彼此相容的模型與參數，不是單換一個檔名**；上面的完整清單照走，另外確認：

- [ ] 先用 `skills/comfyui-pipeline-review/SKILL.md` 或明確的使用者需求決定候選模型，不要臨場挑
- [ ] 新增 `tools_src/comfyui_pipeline/profiles/<id>.json`：`family`、`tiers`（沒有對應 tier 就給空清單，只能用 `--profile` 選用）、`requirements`（後端／最低可用記憶體／精度）、`models`（每顆模型的 `dir`、`file`、`loader`、`nodes`，選配標 `optional`，實驗性標 `experimental`）、`sampling`、`resolution.by_memory`、`tasks`（只列實際支援的）
- [ ] 同一個 tier 不能對應兩份設定檔（測試會擋）；若新設定檔要取代某個 tier 的預設，要同時改 `detect_device.py` 的 `TIERS` 並確認 `tests/test_image_profiles.py` 的一致性測試
- [ ] 取樣參數與 graph 結構不同時（例如蒸餾版需要 4–8 步、低 cfg，或需要不同 loader node），先確認現有 builder 能否只靠設定檔表達；不能的話是程式碼變更，要補 golden fixture 並說明
- [ ] 新增 `skills/comfyui-art-gen/reference/profiles/<id>.md`，設定檔的 `notes_ref` 指過去；內容只寫實測發現
- [ ] `validation` 一開始保持空的（全部 `unverified`），實機驗證後才依情境 C 補
- [ ] 安裝清單（`skills/comfyui-install/reference/models.md`）補上這份設定檔需要的模型、來源、大小、最後確認日期

## 情境 C：在新平台或新記憶體級距驗證既有設定檔

例如在 `macos-mps` 第一次跑 `sdxl_standard`，或在 8GB 的 `windows-cuda` 機器補驗。**不改程式碼**，只補證據與驗證紀錄：

- [ ] 在該機器照 `skills/comfyui-install/SKILL.md` 完成安裝、`detect_image_capabilities.py` 與 `verify_portable_install.py --require-image`
- [ ] 逐 task 實際產圖並做人工驗收（`skills/comfyui-art-gen/SKILL.md` 的產後驗收），記下指令、輸出尺寸／格式、耗時與發現的問題；只跑出檔案、沒看過內容的不算
- [ ] 更新設定檔 JSON 的 `validation.<platform_key>`：
  - `status`：全部驗收通過才用 `verified`；能出圖但品質或穩定性有疑慮用 `experimental`；確認跑不起來（OOM、精度不支援、node 不相容）用 `unsupported`
  - `tasks`：只列實際驗收過的 task
  - `min_verified_memory_mb`：這台機器 `device_config.json` 的 `usable_memory_mb`
  - `evidence`：指向證據位置
- [ ] 證據寫進 `docs/tested-versions.md`（該機器的 commit、套件版本、模型 SHA-256、smoke 紀錄），不可捏造或沿用其他機器的數字
- [ ] 同一平台已有紀錄時，新的 `min_verified_memory_mb` 只能在實測較低記憶體級距通過後才往下調
- [ ] 平台特有的發現（例如 MPS 某個 task 很慢、某精度不支援）補進 `reference/profiles/<id>.md`
- [ ] 設定檔 JSON 變了，部署端也要同步；`verify_portable_install.py` 會把內容不同判為 FAIL

## 已知限制

這份清單本身也會過時。如果之後這條產線的架構有大幅變動(例如真的換了另一套生成引擎,不只是 ComfyUI 裡加新節點),這份清單要跟著重新檢視,不要當成永遠不變的教條。
