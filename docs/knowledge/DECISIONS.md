---
type: decision-index
status: current
---
# 生效中的產線決策

決策細節與證據寫在日期化 ADR。這一頁只列目前採用的方向；歷史實測仍需按適用 task、模型與平台閱讀，不能憑一個結果自動改設定檔。

| 日期 | 決策 | ADR |
|---|---|---|
| 2026-10-01 | 維持固定 task／能力 gate；`--result-json` 是選用技術追溯資料；素材版本與人工驗收以按需 Markdown 素材頁記錄，不自動回寫生成規則。 | [素材 Markdown 紀錄；撤回先前 SQLite 方案](decisions/2026-10-01-asset-result-records.md) |
| 2026-10-01 | SDXL 是既有穩定基線；FLUX.2 保持獨立實驗路徑，不能由單機 PoC 推論可取代主線。 | [FLUX.2 維持獨立 PoC](decisions/2026-10-01-flux2-remains-poc.md) |
| 2026-10-01 | 沿用既有 Markdown 知識庫和檔案讀寫規範；保留固定版本的上游技能與產品 runtime，並明確記錄其原生 Windows 支援範圍。 | [以標準 Markdown 維護專案知識庫](decisions/2026-10-01-obsidian-integration.md) |
