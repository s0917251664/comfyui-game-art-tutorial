---
type: maintenance-playbook
status: current
last_updated: 2026-10-06
---

# 專案技能、執行路線與產線審視流程

本流程涵蓋技能庫、使用者路由、ComfyUI／平台／本機工具分工及技術基準。審視本身以只讀盤點和具體建議為主，不自動產生素材、改檔、下載或替換模型。開始時先從[總工具庫](../TOOLS.md)找到目前路由；再用[技能庫路線與盤點](skill-library.md)辨認已實作／待評估路線。只按本次範圍讀必要技能、相關 source、案例和驗證紀錄。

## 選擇審視模式

| 使用者要求 | 做法 | 不應默認執行 |
|---|---|---|
| 「審視／盤點技能庫」、「這條線應怎麼用 API」、「工具或 agent workflow 有沒有更簡單」 | 離線檢查現行 skill、路由、入口、固定 graph、程式和已存實測；整理路線責任、摩擦、缺口與是否值得另評估。 | 不需要先查最新論文／模型，不掃描所有模型類別，不改檔或執行生成。 |
| 「查新的模型／技術」、「評估要不要升級某個模型／能力」 | 依明確範圍核對現行基準，查相關一手來源，記錄查詢日期、兼容性、需求和風險並建議。 | 不下載、安裝、替換 profile／參數、queue 產圖或把候選說成 verified。 |
| 明確授權某份 skill／維護文件的具體編修 | 依同一要求或先前上下文中已授權的範圍直接實作，再做來源與路由情境檢查。 | 不因「review」字眼要求使用者重複授權已明確指定的文件工作。 |

若使用者只要 review，即使結果顯示應改也先提交具體方案與影響；審視授權本身不等於實作或外部付費。若同一要求已明確要整理文件／技能，依其原授權修改，不重問。技術能力新增流程只有當實際新增／改變可執行能力時才套用[新增能力清單](new-capability-checklist.md)；純技能治理、brief 路由更新不強制生圖或跑生成 smoke。

## 離線技能庫／路線審視

1. **界定問題：** 確認要審查的使用者流程、技能家族或具體卡點。若已有可沿用 brief 就不重做需求收集。
2. **對照現況：** 根據 skill description/body、`AGENTS.md`、TOOLS、INDEX、reference、code source 和當前案例確認觸發條件、依賴、設定／schema gate、呼叫方式、輸出位置與內容驗收。按需核對小範圍，不載入整個 vault。
3. **分類路線：** brief／需求規劃、平台原生、直接 ComfyUI HTTP API 固定 graph、既有 `generate.py` CLI/profile、需要本機 helper/custom node 的媒體或狀態處理。考慮操作步驟、當前工具 schema、版本／asset 重用、server support、runtime、狀態恢復、output contract 和可追溯性。
4. **標明證據等級：** 區分程式存在、文件描述、offline structure/schema check、當前 live preflight、實際 bounded execution、技術 contract、內容人工觀察和美術審核者的接受決定。只成功 queue 不算完成；技術 pass 也不等同美術 accepted。
5. **評估 API 適配時：** 逐能力說明 direct API 是否可用固定 assets 取代現有 CLI、Python 是不是必要於批次 media/state、哪些 profile/backend gate 要保留、哪些 caller 尚未改走。結論標記「已實作」、「候選可研究」、「目前不適合」或「證據不足」。不以非 Python 作為所有路線目標，也不將建議寫成已遷移。

此模式無需 web research；若現有資料無法確認遠端當前狀態，標記未知。需執行 API 或平台原生路線以確認當前實作能力時，需有明確任務／授權，並依該 executor 的輸入限制實際操作；離線 read-only review 不得 queue。

## 模型／當前技術研究（只在明確要求時）

1. 列出本機 profile、task/backend、模型和實測證據的最後確認日期。對照需要研究的特定類別；不要把整張模型表全部重查。
2. 使用官方文件、論文、release notes、model card 或 upstream source 核對候選的任務、版本、license、硬體／VRAM、精度、ComfyUI integration、缺依賴及已知限制。比較應包含本機實際 workflow 是否能用，不以 benchmark 一項推定適用。
3. 報告目前做法及限制、候選差異、未解問題、可行測試和建議狀態。每個結論區分來源明載、目前專案實測及推論；給 source link 和查詢日期。
4. 不下載模型、不改 profiles／預設、不部署、不 queue。使用者若選一項實作，再按新增能力流程做可檢視的計畫和實作，不擴大到其他未授權項目。

## 報告內容

按照工作大小擇要列：

- 審視範圍、日期與看過的專案來源。
- 現況分類：每條路線做什麼、需要什麼、已實測到哪裡。
- 卡點或風險，需有 repo 文件、源碼或實測依據。
- direct API／CLI／helper 哪些已實作，哪些只適合後續比較、哪些尚無證據；清楚寫明「未遷移」狀態。
- 可選方案、變更範圍、所需 gate 和尚待證據；建議不得直接改寫 project defaults。

對技能庫整體 review，引用[技能庫現況表](skill-library.md)並按任務需要深入，不複製全部文件進報告。若發現 metadata、AGENTS、TOOLS、INDEX 或跨技能 handoff 錯誤，只作為問題／具體差異記錄；除非使用者同一要求已授權文件修正，不自行改動。
