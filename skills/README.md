# skills/ 索引

技能必須維持扁平的 `skills/<name>/SKILL.md`：Agent 以此路徑探索技能，所以**不做子資料夾分組**。每個 SKILL.md 只寫思路（怎麼判斷、選哪條路、什麼時候停下來問使用者），不超過 60 行，也不放 reference 資料夾。判斷依據在 [`docs/knowledge/`](../docs/knowledge/INDEX.md)，用法以 `template.json` 與 `--help` 為準（`gameart.py run show <id>`），由 `tests/test_docs_converged.py` 防止回到舊的堆疊方式。

## 遊戲美術產線技能（路由見 [`AGENTS.md`](../AGENTS.md)）

| 技能 | 用途 |
|---|---|
| [`game-art-brief`](game-art-brief/SKILL.md) | 需求盤點、選路線、brief 與驗收規劃、編修需求對應、專案知識庫讀法。不執行生成 |
| [`platform-image-gen`](platform-image-gen/SKILL.md) | 平台本身提供的圖片工具 |
| [`comfyui-run`](comfyui-run/SKILL.md) | 本機 ComfyUI：`generate.py` task、`gameart.py run` 的固定 template、`gameart.py recipe` 多步驟流程 |
| [`local-media-tools`](local-media-tools/SKILL.md) | 不經 ComfyUI 的本機 Python 工具：像素處理、物件組裝、特效去背與打包、配音與對嘴、遮罩輔助 |
| [`comfyui-extend`](comfyui-extend/SKILL.md) | 缺能力時照擴充協議提案；技能庫與架構審視 |
| [`comfyui-install`](comfyui-install/SKILL.md) | 安裝、部署與依賴補齊 |

## Obsidian 上游技能（不在本資料夾）

`claude-obsidian` 上游技能的專案副本放在 [`third_party/claude-obsidian-skills/`](../third_party/claude-obsidian-skills/README.md)，只有使用者明確要處理另外初始化的 Obsidian vault 時才用，範圍與限制見 [Obsidian 整合說明](../docs/knowledge/maintenance/obsidian-integration.md)。產線工作和專案知識庫（`docs/knowledge/`）的讀寫都不需要它們，用一般 Markdown 檔案工具即可。
