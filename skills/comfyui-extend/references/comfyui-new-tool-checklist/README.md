---
name: comfyui-new-tool-checklist
description: 新增或擴充本專案技能、平台執行路線、ComfyUI API graph、generate.py task、custom node 或本機 helper 時，依實際路線核對發現入口、依賴、證據、測試與文件，不強制所有能力使用 ComfyUI 或 Python。
---

# 新能力與技能變更檢查

使用者要求新增一種能力、技能入口、執行路線，或改變既有能力契約時使用。新增 `generate.py` task 時，程式放在 `tools_src/comfyui_pipeline/tasks/` 的 task 模組，不寫進 `generate.py`（見 checklist D）。本技能涵蓋平台原生、直接 ComfyUI API、既有 `generate.py`、本機 helper/custom node 及純規劃路線。純文件修訂若沒有改變能力或規則，不套用生成能力實測；但仍檢查引用與狀態描述。

開始前讀[總工具庫](../../../../docs/knowledge/TOOLS.md)、[維護索引](../../../../docs/knowledge/maintenance/README.md)、[技能庫路線與盤點](../../../../docs/knowledge/maintenance/skill-library.md)及[路線化新增能力檢查清單](../../../../docs/knowledge/maintenance/new-capability-checklist.md)。先識別路線與需求，不從「ComfyUI 專案」推定必須新增 Python、CLI、task、custom node 或模型 profile。

## 必做判斷

1. 寫清技能觸發條件、輸入／輸出、使用者交付、依賴與版本，以及技術通過和內容驗收狀態。路線改變時，檢查既有 skill 是否仍會錯誤攔截或要求舊工具。
2. 為目標路線選用最小必要 runtime、gate 與證據。平台原生直接依實際工具 schema；ComfyUI API 直接比對 live schema、模型 selectors、固定 assets 和 request/history/output；既有 CLI 沿用對應 profile/capability gate；只有確實需要本機媒體、狀態或批次處理時才保留／新增程式碼；新增 `generate.py` task 時依 `comfyui_pipeline/tasks/` 慣例，狀態走 `RunContext`、不用全域或 facade。
3. 建立能讓 agent 正確呼叫的最小 `SKILL.md` 與必要 references／versioned assets。操作細節放 reference；skill 只保留觸發、不可跳過的 gate、基本操作與結果狀態。不要新增未使用的 workflow、資料夾或依賴。
4. 做該路線適用的驗證。brief／初始化／治理文件以來源引用、觸發路由和任務情境確認，不強制圖片生成；平台原生只有在本次會話確有工具且任務要求生成時才呼叫，技能使用本身不依賴 Python，即使維護者使用 Python quick validator 也不改變此點；新增 API／CLI／本機能力按下方清單做實機 smoke。不可用檔案存在、離線 schema parse、語法檢查或只成功 queue 代替輸出技術檢查。另行記錄內容候選與人工驗收，不能從技術通過推定 accepted。
5. 更新實際使用者與 agent 會走到的專案入口。技能屬 repo 可呼叫能力時更新 `AGENTS.md`、`docs/knowledge/TOOLS.md`、`docs/knowledge/INDEX.md` 等適用入口；全域技能副本／stub 僅在使用者明確要求跨專案或全域發現時才建立。

遇到 gate 失敗，保留失敗證據、指出阻塞項並停止依賴該能力的工作。不可自動切換到另一執行路線、下載模型或改設定來繞過。
