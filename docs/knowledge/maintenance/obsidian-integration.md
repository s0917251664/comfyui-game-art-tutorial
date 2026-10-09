---
type: maintenance-guide
status: current
---
# Obsidian 技能庫與專案知識庫

本專案知識庫是 `docs/knowledge/` 的既有目錄與標準 Markdown 筆記。一般讀寫直接使用檔案工具；不需要 Obsidian app、WSL、社群外掛或額外安裝工具。依 [TOOLS.md](../TOOLS.md) 和 [INDEX.md](../INDEX.md) 選擇少量相關知識頁，不把整個 vault 載入 prompt。讀寫規範：小模型撰寫草稿，主 agent review 後再更新 Markdown；知識筆記是參考，不是自動規則。

## 上游來源與技能路由

固定上游來源為 `claude-obsidian` commit `32ac5a02c4e082e4a5628ca810776375e134708e`。產品 runtime 的 repo 路徑是 `third_party/claude-obsidian/`，原始 [MIT LICENSE](https://github.com/AgriciDaniel/claude-obsidian/blob/32ac5a02c4e082e4a5628ca810776375e134708e/LICENSE) 和 [ATTRIBUTION](https://github.com/AgriciDaniel/claude-obsidian/blob/32ac5a02c4e082e4a5628ca810776375e134708e/ATTRIBUTION.md) 可在固定 commit 查閱；來源 hash 紀錄在 repo `third_party/claude-obsidian-source.json`。來源 manifest 的 `product_root` 是相對於 manifest 的 `claude-obsidian`；解析時以 `manifest.parent / product_root` resolve 成絕對路徑。上游 runtime script 若需執行，shell command 必須明確設定 `PRODUCT_ROOT` 或使用完整絕對路徑。

十五個上游技能的 repo 副本自 2026-10-07 起位於 [`third_party/claude-obsidian-skills/`](../../../third_party/claude-obsidian-skills/README.md)（原本在 `skills/`；移出後產線技能探索路徑只剩本專案技能），依各自觸發條件閱讀 `third_party/claude-obsidian-skills/<skill-name>/SKILL.md`。各副本的 `references/runtime-binding.md` 以 `../../../claude-obsidian` 解析 `PRODUCT_ROOT`，hash 與位置（`adapted_skills.skills_root`）記在來源 manifest。**本專案知識庫的讀寫不經過這些技能**：一般檔案工具直接處理 `docs/knowledge/` 的 Markdown，`wiki-query`、`wiki-ingest`、`save` 等只用於另外初始化的 claude-obsidian vault。各技能分工：`wiki` 負責 vault 初始化／路由；`wiki-cli`、`wiki-query`、`wiki-retrieve`、`wiki-lint`、`wiki-fold`、`wiki-mode` 分別處理 CLI、知識查詢、檢索、健康檢查、log 摺疊與方法設定；`wiki-ingest` 處理來源匯入；`obsidian-markdown` 和 `obsidian-bases` 處理格式及 Bases；`canvas` 處理畫布；`save` 保存使用者明確要求保留的回答；`autoresearch` 執行有來源的研究；`defuddle` 處理明確授權的外部網頁抽取；`think` 用於需要結構化思考的決策。不要只因提到 Obsidian 就推定特定外部工具或 runtime 已可用。十五個上游技能與 `project-knowledge` 在 2026-10-01 曾安裝為全域 skills，hash 驗證結果存於本機 `%TEMP%\claude-obsidian-install-verification.json`。全域安裝的是另一份副本，不受這次 repo 內搬移影響；2026-10-07 搬移時只改了 `runtime-binding.md` 的相對路徑，manifest 的 `project_binding_sha256` 已同步更新。未執行 setup/hooks，也未建立 `.agents` links。

## Windows 與 vault 支援範圍

上游 [Windows／WSL 指南](https://github.com/AgriciDaniel/claude-obsidian/blob/32ac5a02c4e082e4a5628ca810776375e134708e/docs/windows-wsl.md) 說明原生 Windows 支援唯讀讀取／預覽、檢查、dry-run 和 retrieval；`init`、`adopt`、`migrate`、transaction `apply`、capture `apply`、`mode set` 等寫入路徑要求 WSL。此主機只有 Docker Desktop 的 WSL backend，沒有通用 WSL distro；不以 Docker 代替 WSL，也不安裝 WSL。

既有 `docs/knowledge/` 可用一般 Markdown 檔案方式讀寫，不受上游 schema readiness 限制。但 `doctor --vault docs/knowledge` 回報 `legacy_layout=true`、`ok=false`，因上游預期的 `wiki/`、`.raw/` 等目錄不存在；因此不宣稱上游完整 ingest/query runtime 已對此 vault 就緒。完整 upstream ingest ledger、hybrid retrieval、Canvas 與需 WSL 的寫入流程尚不能視為已接入本專案。這些限制不影響現有 Markdown 文件可讀寫，也不改變人工 review 或 profile 升級規範；素材版本與人工驗收依 vault 的 Markdown 紀錄格式處理。

本整合未安裝 Obsidian app、WSL 或社群外掛，也未修改上游 guard。知識筆記屬文件內容，不是圖片／影片能力驗證；不得以這批技能取代本機 capability snapshot、模型 preflight 或人工美術驗收。
