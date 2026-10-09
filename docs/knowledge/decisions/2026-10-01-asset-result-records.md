---
type: adr
status: accepted
date: 2026-10-01
---
# ADR：以 Markdown 素材頁記錄版本與驗收

## 決策

保留圖片 task 的選用 `--result-json` 技術 manifest。需要比較或保留圖片素材版本時，在 `docs/knowledge/assets/<asset-id>.md` 按需新增 Markdown 頁，逐版列圖片位置、candidate／accepted／rejected 狀態、日期及美術審核者的明確決定和理由。一般生成不要求建立素材頁。

## 理由

技術通過與美術內容合格是兩種判斷：manifest 記錄 task、參數、輸入／輸出摘要及 PNG 技術檢查；美術是否符合要求仍須看圖並由美術審核者決定。以簡單 Markdown 留下少量有意義版本紀錄，不增加日常工具或資料庫需求，也不將經驗自動餵回生成。

## 契約

- `--result-json` 選用且只適用圖片 task；`technical_validation=pass` 不能當成內容驗收。
- candidate 只表示待檢查；只有美術審核者明確決定後才能標 accepted 或 rejected，需記錄實際日期與理由。不得捏造決定。
- 每個新輸出都是新版本、從 candidate 開始，不能繼承舊版 accepted 狀態；拒絕紀錄不刪除舊圖與證據。
- 素材頁只在需要保存版本時建立，不預製大量空頁。圖片／manifest 可用相對路徑連結既有輸出，不複製大型檔案。
- 要求沿用已接受版本時，有 manifest/hash 紀錄就先核對原圖、manifest 和必要輸入仍存在且 hash 未變，再按原 task、原參數與當前 capability gate 執行。沒有 manifest/hash 時只能依素材頁可用資訊沿用，並說明無法驗證完整同條件；原圖片不能缺失，缺必要生成資訊才詢問。
- 經驗筆記與素材驗收頁是不同用途；觀察不會自動變成 accepted 決策或正式生成規則。

## 撤回的前案

2026-10-01，使用者明確決定撤回此前短暫採用的 SQLite `asset_library.py` CLI／部署／資料庫設計，改以本 ADR 的 Markdown 素材頁作為人工版本與驗收紀錄。SQLite 只作為撤回前歷史，不是本專案現行或必要能力；不得再要求安裝、部署、執行或保存資料庫。撤回前 smoke 事件已轉寫為 [smoke-potion candidate 素材頁](../assets/smoke-potion.md)，保留原始狀態和理由，沒有改成 accepted。

## 驗證狀態

Markdown 範例依照實際 smoke candidate 和可用 JSON manifest 填寫。撤回前的測試數字只代表當時程式版本；撤回後驗證見[重構報告](../archive/agent-pipeline-refactor-2026-10-01.md)，不可沿用撤回前數字宣稱現況。
