# skills/ 索引

技能必須維持扁平的 `skills/<name>/SKILL.md`：Agent 以此路徑探索技能，各 SKILL 內的相對連結也依賴它，因此**不做子資料夾分組**，只在此以清單區分。本資料夾只放本專案自己的技能；Obsidian 上游技能已移出（見 B 段）。

## A. 遊戲美術產線技能（本專案核心，路由見 [`AGENTS.md`](../AGENTS.md)）

PR 7.3（2026-10-08）把 18 個技能收成 6 個。技能入口只寫怎麼選、怎麼判斷；舊技能的完整內容搬到新技能的 `references/<舊名>/`，對照表見 [技能收斂對照](../docs/knowledge/maintenance/skills-6-mapping.md)。

| 技能 | 用途 | 收進來的舊技能 |
|---|---|---|
| [`game-art-brief`](game-art-brief/SKILL.md) | 需求盤點、選路線、brief 與驗收規劃、編修需求映射、專案知識庫 | game-art-workflow、game-art-edit-brief、game-art-initialize、project-knowledge |
| [`platform-image-gen`](platform-image-gen/SKILL.md) | 平台本身提供的圖片工具 | （不變） |
| [`comfyui-run`](comfyui-run/SKILL.md) | 本機 ComfyUI：圖片／影片 task、固定 template、recipe、換臉、影片分層、物件系列、參數比較 | comfyui-art-gen、comfyui-object-design、comfyui-video-gen、comfyui-character-animation-workflow、comfyui-film-workflow、comfyui-face-swap-workflow、comfyui-video-layers、comfyui-wan-animate、comfyui-image-sweep |
| [`local-media-tools`](local-media-tools/SKILL.md) | 不用模型的本機像素與媒體處理（合成、換色、比較、去背、打包） | local-image-edit-tools |
| [`comfyui-extend`](comfyui-extend/SKILL.md) | 缺能力時照擴充協議提案；技能庫與架構審視 | comfyui-new-tool-checklist、comfyui-pipeline-review |
| [`comfyui-install`](comfyui-install/SKILL.md) | 安裝、部署與依賴補齊 | （不變） |

`skills/comfyui-art-gen/reference/profiles/` 只剩兩個轉址檔，不是技能（沒有 `SKILL.md`）；保留原因見[轉址檔索引](../docs/knowledge/archive/redirect-stubs.md)。

## B. Obsidian 上游技能（不在本資料夾）

15 個 `claude-obsidian` 上游技能的專案副本放在 [`third_party/claude-obsidian-skills/`](../third_party/claude-obsidian-skills/README.md)（2026-10-07 從 `skills/` 移出）。只有使用者明確要處理另外初始化的 Obsidian vault 時才用，範圍與限制見 [`docs/knowledge/maintenance/obsidian-integration.md`](../docs/knowledge/maintenance/obsidian-integration.md)。

`autoresearch`、`canvas`、`defuddle`、`obsidian-bases`、`obsidian-markdown`、`save`、`think`、`wiki`、`wiki-cli`、`wiki-fold`、`wiki-ingest`、`wiki-lint`、`wiki-mode`、`wiki-query`、`wiki-retrieve`

產線工作和專案知識庫（`docs/knowledge/`）的讀寫都不需要這一組；知識庫依 A 段 `game-art-brief` 裡的 project-knowledge reference 用一般 Markdown 檔案工具讀寫。
