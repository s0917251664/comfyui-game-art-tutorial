# 維護與技術變更

此區收錄需要主動觸發的產線評估與新增能力流程：

先從[總工具庫](../TOOLS.md)確認工作對應的產線工具，再按需讀下列流程。

- [重構交接：第 3–8 階段](restructure-handoff.md)：重構期間每個 PR 的規則、流程、計畫與回報格式。
- [技能庫／路線審視與技術研究流程](pipeline-review.md)：明確要求時只讀盤點技能與執行方式；當前模型 research 亦只在使用者明確要求時查，不自行更換。
- [技術掃描類別](scan-categories.md)：執行盤點時依使用者範圍選取類別。
- [新增能力檢查流程](new-capability-checklist.md)：新增圖片、影片或本機工具能力時，逐類檢查安裝、程式、實測及文件。
- [技能庫路線與盤點](skill-library.md)：brief、平台原生、直接 ComfyUI API、既有 CLI 與 helper/custom node 的界線，17 個 repo 美術技能現況及維護原則。
- [Video Layers 新增能力檢查紀錄](video-layers-checklist.md)：本次影片／本機工具實作已完成項目、略過原因與仍待驗收 gate。
- [文件連結規則](doc-links.md)：相對連結與錨點由 `tests/test_doc_links.py` 檢查；`output/` 本機證據的寫法與允許的例外。
- [Obsidian 技能與專案知識庫](obsidian-integration.md)：上游來源固定版本、技能路由、原生 Windows 限制及既有 Markdown vault 的支援範圍。

本目錄只定義維護決策與能力變更的要求；一般產圖、安裝目標和模型來源請讀 `art/` 或 [installation](../installation/README.md)。
