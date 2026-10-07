# skills/ 索引

技能必須維持扁平的 `skills/<name>/SKILL.md`：Agent 以此路徑探索技能，`.gitattributes`、`docs/knowledge/maintenance/obsidian-integration.md` 與各 SKILL 內的相對連結也依賴它，因此**不做子資料夾分組**，只在此以清單區分。

## A. 遊戲美術產線技能（本專案核心，路由見 [`AGENTS.md`](../AGENTS.md)）

| 技能 | 用途 |
|---|---|
| `game-art-initialize` | 新使用者初始化、選路線 |
| `game-art-workflow` | 共用 brief、參考用途、版本與美術驗收 |
| `game-art-edit-brief` | 編修 brief 相容入口 |
| `platform-image-gen` | 平台圖片工具路線 |
| `comfyui-art-gen` | ComfyUI 圖片生成與編修 |
| `comfyui-object-design` | 物件系列、展示背景、檢視表、圖樣重複 |
| `local-image-edit-tools` | 本機像素操作（Pillow／NumPy） |
| `comfyui-image-sweep` | 有限參數比較 |
| `comfyui-video-gen` | 影片生成 |
| `comfyui-character-animation-workflow` | 角色動作組編排 |
| `comfyui-film-workflow` | 劇情多鏡、聲音、Animatic |
| `comfyui-face-swap-workflow` | 影片換臉 |
| `comfyui-video-layers` | 影片物件遮罩（SAM3 固定 graph 為預設、SAM2 為備援）／ordered video layers |
| `comfyui-wan-animate` | Wan Animate（Mix／Move、延伸段、音訊、寬高）與 SCAIL-2 固定 API graph |
| `comfyui-install` | 安裝與依賴補齊 |
| `comfyui-new-tool-checklist` | 新增／擴充能力檢查表 |
| `comfyui-pipeline-review` | 技能庫、架構審視 |
| `project-knowledge` | 專案知識庫（`docs/knowledge/`）按需讀寫 |

## B. 知識庫／Obsidian 上游技能（與出圖產線無關）

來源為 `third_party/claude-obsidian`，僅在使用者明確要處理 Obsidian vault／wiki 時才觸發；範圍與限制見 [`docs/knowledge/maintenance/obsidian-integration.md`](../docs/knowledge/maintenance/obsidian-integration.md)。
`wiki` 比上游多 `references/runtime-binding.md`（本專案路徑綁定）。

`autoresearch`、`canvas`、`defuddle`、`obsidian-bases`、`obsidian-markdown`、`save`、`think`、`wiki`、`wiki-cli`、`wiki-fold`、`wiki-ingest`、`wiki-lint`、`wiki-mode`、`wiki-query`、`wiki-retrieve`

產線工作不需要讀這一組。
