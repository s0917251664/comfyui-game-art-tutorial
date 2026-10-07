---
type: rule
id: R1
status: current
source: ../decisions/2026-10-01-asset-result-records.md
---
# R1 候選與美術驗收：技術通過不等於美術接受

## 規則

1. 所有生成或處理後的輸出（圖片、影片、音訊、遮罩、合成、打包檔）都從 `candidate` 開始。
2. 技術檢查只證明技術條件。CLI／工具成功、queue 完成、`technical_validation=pass`、影片 sidecar 契約、smoke、像素統計、遮罩外 0 變動、loop 量測等，都**不代表**內容或美術合格，也不代表跨平台 `verified`。
3. 只有美術審核者明確決定後，才能把版本標成 `accepted` 或 `rejected`。agent 不得自行決定、捏造或推定；代為記錄時要忠實摘要理由和日期。
4. 狀態只用 `candidate`、`accepted`、`rejected`。新生成的輸出是新版本，必須從 `candidate` 開始，絕不繼承舊版的 `accepted`。
5. 拒絕時保留版本紀錄與理由，不刪除來源圖片或證據。
6. 回報與記錄時分開寫三件事：引擎／檔案的技術檢查結果、agent 的可見內容觀察、美術審核者的決定。

## 適用範圍

所有路線：ComfyUI 圖片與影片、平台原生圖片工具、本機像素與媒體工具、音訊與劇情片。各路線的技術契約（例如影片 sidecar 的 `pass`／`warning`／`fail`）在各自技能說明，但都只代表技術狀態。

平台驗證升格（`gameart.py validation approve`）是另一個只能由使用者決定的動作，見 [validation-workflow](../maintenance/validation-workflow.md)。

## 怎麼記錄

- 圖片技術 manifest、`gameart.py review accept|reject --by <審核者>` 的 decisions 檔與素材 Markdown 頁格式：見 [result-records.md](../result-records.md)。
- 沿用已接受版本的程序：見 [result-records.md 的「使用者要求沿用已接受版本」](../result-records.md#使用者要求沿用已接受版本)。

## 來源

[ADR 2026-10-01：素材結果紀錄](../decisions/2026-10-01-asset-result-records.md)。
