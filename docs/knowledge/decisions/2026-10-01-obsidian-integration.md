---
type: adr
status: accepted
date: 2026-10-01
---
# ADR：以標準 Markdown 維護專案知識庫

## 決策

沿用 `docs/knowledge/` 現有目錄、Markdown 筆記和文件規範，使用一般檔案工具讀寫。需要專案知識路由時讀 `skills/project-knowledge/SKILL.md`；小模型撰寫草稿，由 root review 後更新筆記。不新增本機專用知識 IO 程式。

## 原因與界線

現有 Markdown 知識庫已可讀寫，不需額外程式。Obsidian app 是可選編輯器，WSL 不是現有筆記讀寫的依賴。仍須區分「既有 Markdown 可用」與「上游完整 ingest/query runtime 已就緒」：上游 Windows guide 將若干唯讀／預覽、檢查、dry-run、retrieval 與需 WSL 的寫入流程分開；本機 `doctor --vault docs/knowledge` 結果為 `legacy_layout=true`、`ok=false`，因 vault 不含上游預期的 `wiki/`、`.raw/` 等結構，因此不宣稱其完整 ingest/query 已接通。

此決策不改模型 profile、圖片／影片 capability gate 或人工資產驗收。`accepted`／`rejected` 與 profile 升級仍由 Steve 明確決定。

## 來源

保留上游 `claude-obsidian` 固定 commit `32ac5a02c4e082e4a5628ca810776375e134708e` 的 15 個技能與產品 runtime；MIT 授權及歸屬見[上游 LICENSE](https://github.com/AgriciDaniel/claude-obsidian/blob/32ac5a02c4e082e4a5628ca810776375e134708e/LICENSE)和[ATTRIBUTION](https://github.com/AgriciDaniel/claude-obsidian/blob/32ac5a02c4e082e4a5628ca810776375e134708e/ATTRIBUTION.md)，repo source digest 在 `third_party/claude-obsidian-source.json`。15 個上游 skill 與專案 `project-knowledge` 共 16 個全域 skills 已安裝並完成 hash 驗證，下個 turn 會載入 Codex skill discovery。未執行 setup/hooks，也未建立 `.agents` links。
