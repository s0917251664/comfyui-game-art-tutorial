# 維護與技術變更

需要主動觸發的產線評估與新增能力流程。先從[總工具庫](../TOOLS.md)確認工作對應的工具，再按需讀：

- [新增固定 graph 的擴充協議](extension-protocol.md)：使用者確認後，優先從官方範本派生，再標 draft、測試、實機、技術通過。
- [新增能力檢查清單](new-capability-checklist.md)：依執行路線檢查安裝、程式、實測與文件。
- [技能庫／路線審視流程](pipeline-review.md)：明確要求時只讀盤點與執行方式；當前模型研究也只在使用者明確要求時查。
- [技術掃描類別](scan-categories.md)：執行審視時依使用者範圍選取類別。
- [Template 能力索引](template-catalog.md)：由 `template.json` 自動產生，勿手改；機器可讀版是 `templates/catalog.json`。
- [平台驗證流程（smoke suite）](validation-workflow.md)：`deploy --yes`、`smoke`、`--record`；技術紀錄不等於美術接受。
- [文件連結規則](doc-links.md)：相對連結由 `tests/test_doc_links.py` 檢查；文件收斂規則由 `tests/test_docs_converged.py` 檢查。
- [custom node 改名紀錄](custom-node-renames.md)：`GameArt*` 名稱，舊名稱已移除。
- [Obsidian 技能與專案知識庫](obsidian-integration.md)：上游技能來源、原生 Windows 限制與既有 Markdown vault 的支援範圍。
- [第 3–8 階段結案摘要](restructure-summary-phase3-8.md)：各階段結果與待開發。

重構期間的進度、交接與交付頁、舊的技能庫盤點都在 [archive](../archive/)，平常不讀。本目錄只定義維護決策與能力變更的要求；一般產圖、安裝目標與模型來源請讀 `art/` 或 [installation](../installation/README.md)。
