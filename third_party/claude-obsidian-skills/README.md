# claude-obsidian 上游技能（專案改編副本）

這裡放 15 個來自 [`claude-obsidian`](https://github.com/AgriciDaniel/claude-obsidian) 固定 commit `32ac5a02c4e082e4a5628ca810776375e134708e` 的技能。2026-10-07 從 `skills/` 移到這裡，讓產線技能探索路徑只剩本專案技能。

- 每個技能和 `../claude-obsidian/skills/<同名>/` 的上游原檔相比只差兩處：
  - `SKILL.md` 末尾多一段「Codex runtime binding」；
  - 多一個 `references/runtime-binding.md`，從自身位置用 `../../../claude-obsidian` 解析 `PRODUCT_ROOT`。
- hash 紀錄在 [`../claude-obsidian-source.json`](../claude-obsidian-source.json) 的 `adapted_skills`。`.gitattributes` 對本資料夾設定 `-text`，保持位元組不變。
- **專案知識庫 `docs/knowledge/` 的讀寫不需要這些技能。** 依 [`skills/project-knowledge/SKILL.md`](../../skills/project-knowledge/SKILL.md) 用一般 Markdown 檔案工具即可。這些技能是給另外初始化的 claude-obsidian vault 用的。
- 要用時，直接讀 `<技能>/SKILL.md`；或依 agent 工具的規則，把整個技能資料夾複製或連結到它的技能探索目錄。範圍與限制見 [Obsidian 技能庫與專案知識庫](../../docs/knowledge/maintenance/obsidian-integration.md)。

技能：`autoresearch`、`canvas`、`defuddle`、`obsidian-bases`、`obsidian-markdown`、`save`、`think`、`wiki`、`wiki-cli`、`wiki-fold`、`wiki-ingest`、`wiki-lint`、`wiki-mode`、`wiki-query`、`wiki-retrieve`。
