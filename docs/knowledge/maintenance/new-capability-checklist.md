---
type: maintenance-checklist
status: current
last_updated: 2026-10-06
---

# 新增能力與技能檢查清單

此清單依執行路線檢查，而不是把 repo 現有 Python／ComfyUI 實作形式套用到每個新需求。先閱讀[技能庫路線與盤點](skill-library.md)，勾選本次適用路線；可以組合路線，但每項只核對實際受影響的層。

## 每種能力共同要交代的內容

- [ ] 觸發條件、目的、輸入／輸出、使用者如何操作及結果存在哪裡。
- [ ] 明確選定路線、依賴、已知平台／版本與資產來源；不由相似能力推定可用。
- [ ] 在 skill metadata 寫可被發現的名稱與描述，於 body 解釋觸發、不可跳過的 gate、最短操作和交付狀態；詳細欄位、錯誤與邊界放 references。
- [ ] 分開記錄技術狀態、內容候選及使用者驗收。`pass` 不代表畫面 accepted；未實測標為 `unverified` 或 `pending`。
- [ ] 更新相關技能、知識頁和專案入口；不是每份文件都要同步，只改實際路由依賴的頁面。
- [ ] 保存可回溯的最小證據（版本／hash、請求或 CLI 設定、輸出 metadata、必要時抽幀或人工觀察）；避免把完整大型 log 複製進 skill。

## 執行路線檢查

### A. 需求 brief 或工作流程規劃

- [ ] 明確說明此階段只整理需求、輸入用途、保留／修改項目、交付及驗收條件。
- [ ] 不要求 `local_config.json`、ComfyUI、Python 或圖片／影片能力快照；不偷偷執行生成。
- [ ] 若後續要執行，交接到使用者選定且已知可用的執行路線，不猜 fallback。

### B. 平台原生工具

- [ ] 直接檢查當下平台提供的工具 schema 與其輸入、參考圖、輸出限制。
- [ ] 不要求 ComfyUI config、模型 profile、Python、local detector 或本機 GPU gate。
- [ ] 只宣稱 schema 支援的實際功能。不得推測平台有影片、多參考、指定模型或未展示的 controls；外部付費工具的成本／同意流程依其路線處理。
- [ ] 建立／變更平台生成能力時，只有當下有實際工具且任務要求生成才做一個有界呼叫並檢查返回資產與基本格式；純路由或 brief 文件依來源、工具 schema、觸發情境做檢查，不強制生成。工具不存在或 schema 不支援時明確回報，不暗中改走 ComfyUI。
- [ ] 平台原生技能的執行路線不依賴 Python；維護者選用 Python quick validator 只是維護方式，不能當成終端使用者 runtime 或安裝要求。

### C. 直接 ComfyUI HTTP API 與固定 graph assets

用於有穩定 workflow、但不需要新 Python wrapper、`generate.py` task 或 backend 的能力。agent 可直接呼叫 ComfyUI API。

- [ ] 固定且版控 API-format graph JSON；記錄來源、版本/hash、所有可替換欄位和不允許變動的參數。UI-format JSON 不能未轉換就當 API-format。
- [ ] queue 前以目前 server `GET /object_info` 核對所有 node classes、input schema、模型 selectors；另檢查本機所需模型／sidecar assets 與版本。缺失即停止，不用同類名稱猜相容。
- [ ] 先驗證輸入，再按 API 契約 upload；保存回傳的 server path，填入固定 graph。未解析 placeholder、未知 input、檔案限制不符時不能 submit。
- [ ] 只提交一個可控、有界 prompt，立即保存 `prompt_id`；輪詢該 ID 的 history，以服務明確的 success／completed 狀態判定完成。Queue snapshot 或成功 submit 不算完成。
- [ ] 依 outputs descriptors 下載並核對尺寸、格式、幀數／FPS／音訊、完整解碼及 graph 約定。逾時保存 ID、history 和失敗收據；不得自動重送、全域 interrupt 或下載不存在的輸出。
- [ ] 有界實際 smoke 至少走過 preflight、輸入上傳、API submit/history、輸出下載與契約檢查，才可標技術 verified。離線 graph parse／node-list 存在或未真正呼叫的模板保持 pending。內容另列 candidate，等待人工驗收。
- [ ] 不因為用了 ComfyUI API 就新增 Python client、CLI、`generate.py` task/backend 或 capability catalog。只有請求本身確實需要本機大量解碼、時間軸／批次處理、狀態管理或專案既有 pipeline 暫存時，才另評估 helper/custom node 路線。

### D. 既有 `generate.py` CLI、profile 或 capability catalog

- [ ] 僅在能力屬於既有 `generate.py` task 時沿用它。圖片依相應 image profile／FLUX 獨立 gate；影片依 backend 與 `video_capabilities.json`。不混用圖片／影片 snapshot。
- [ ] 新增或改 task 時改 `tools_src/comfyui_pipeline/tasks/` 的 task 模組（`add_parser`／`validate`／`build_graph` 或 `prepare`／`run_local`），並登記到 `tasks/__init__.py` 的 `MODULES` 與 `TASK_ORDER`；不要把 task 邏輯寫回 `generate.py`，它只做 `main()` 與唯讀 re-export。上傳／排隊／下載在 `client.py`，共用流程在 `cli.py`。協作者直接從定義它的模組 import（沒有 facade／`rt.`），機器相關狀態（device、選用 profile／影片 config）經 `RunContext` 明確傳入，task 的 `check_capabilities`／`build_graph`／`prepare` 第一個參數是 `ctx`；不要新增模組層級可變全域，也不要在 package 內 `import generate`。測試 patch 目標是「呼叫端模組」的名稱（例如 `comfyui_pipeline.cli.submit_and_wait`）。
- [ ] 模型名稱、取樣、tier、支援 task 依既有 profile／catalog 契約更動；profile 代表經相容性驗證的組合，不是只改檔名。
- [ ] 程式有改動時按影響範圍檢查 code、既有 tests、portable deploy 和 fixtures；只有故意改固定 image graph 才更新 golden fixtures。
- [ ] 實測實際呼叫新增／修改 task 與指定 profile/backend，檢查 metadata、畫面／影片技術契約和內容品質。沒有對應機器時保留未驗證狀態。

### E. 本機 helper、server custom node、媒體／批次／狀態處理

- [ ] 確認功能確實需要本機 code，例如批次媒體解碼、長時間狀態、專案資產 staging、特定演算法或既有 CLI 自動化；可由固定 API graph 直做時，不額外包 Python。
- [ ] 列出 client、server、依賴、模型／node pins、安裝路徑、輸入輸出契約與失敗清理；只部署受影響的程式，保留既有 source-of-truth。
- [ ] 如果必須 custom node，說清楚 server 端處理責任與 client/API 邊界；若用既有 ComfyUI API helper，避免再實作重複 graph/transport。
- [ ] 執行有界 smoke，驗證部署後真正執行、成功及失敗產物、完整解碼／像素契約及狀態記錄。需要 media/runtime 的測試依工具契約，不強迫跑不相干的 `generate.py` tests。
- [ ] 僅當 code 維護／部署必要時才更新 portable install manifest、fixtures、同步清單、test suite；不為知識頁另增產品依賴。

## 收尾與曝光

- [ ] `AGENTS.md` 補 repo 核心路由，`TOOLS.md` 說明現況與觸發，`INDEX.md` 導覽知識文件；只改與新增能力有關的入口。
- [ ] 全域技能路由副本只應在使用者明確要其他 repo／全域也能發現時建立；全域副本指向唯一 canonical skill，不另維護第二份操作規則。
- [ ] `教學.md` 或 install files 只在產品能力與使用者操作有實際變動時更新，狀態根據實測，不把 pending graph 說成正式支援。
- [ ] 使用者交付包含路線、檔案、執行證據、技術／內容狀態及仍未驗證事項。
