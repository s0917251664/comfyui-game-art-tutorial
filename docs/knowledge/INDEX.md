---
type: index
status: current
---
# Game Art Pipeline Knowledge Vault

這個資料夾是可直接開啟的 Obsidian vault，內容也可用一般 Markdown 閱讀（Obsidian 選 **Open folder as vault** 指到 `docs/knowledge/`，不需外掛）。不要把 vault 筆記灌進每個 prompt：先讀 [工具與技能總表](TOOLS.md) 找入口，再按任務讀一頁。

## 這裡放什麼、不放什麼

- 放**判斷依據**：美術判斷、已知限制、經驗、規則。
- **不放用法**：參數與輸入契約以 `template.json`（`gameart.py run show <id>`）與各工具的 `--help` 為準。
- **歷史資料**（進度、交接、交付頁、實驗過程、舊 review、舊設計文件）都在 [archive/](archive/)。**agent 平常不讀 archive**，只有使用者要追溯當時的做法時才開；現行文件不連到它。

## 從哪裡開始

跨路線的執行規則只寫在 [rules/](rules/README.md)：R1 候選與美術驗收、R2 固定流程、R3 Idle 錨定。

| 要做什麼 | 讀這頁 |
|---|---|
| 找工具與入口 | [TOOLS.md](TOOLS.md) |
| 第一次使用、還沒選路線 | [初始化](installation/initialization.md)；整理需求見 [brief 與驗收](art/brief-and-acceptance.md) |
| 圖片：該用哪個 task | [art-generation.md](art-generation.md)；特殊參數才查 [art-parameters.md](art-parameters.md) |
| 圖片：做不到的事、失敗樣態 | [已知限制](art/known-limitations.md)、[編修情境](art/edit-scenarios.md) |
| 局部修改的遮罩 | [遮罩](art/masking.md)、[SAM 候選](art/sam-segmentation.md)、[控制來源判斷](art/control-type-selection.md) |
| 結構鎖定、複合元件圖層 | [結構範本](art/structure-ref.md)、[圖層拆分判斷](art/layered-assets.md) |
| 本機像素與物件組裝 | [edit-tools](art/edit-tools.md)、[單一物件換色](art/single-object-color.md)、[物件組裝](art/object-design-workflows.md) |
| 模型設定檔經驗 | [sdxl-standard](art/profiles/sdxl-standard.md) |
| 影片 | [影片知識](video/README.md)、[CLI 對照](video/cli.md)、[設計判斷](video/design.md) |
| 影片局部重繪、去背打包 | [vfx-tools](video/vfx-tools.md)、[SAM3 追蹤](video/sam3-tracking.md)、[Video Layers](video/layers.md) |
| Wan Animate、SCAIL-2 | [取捨](video/wan-animate-choice.md)、[評估](video/animation-evaluation.md)、[安裝紀錄](video/wan-animate-install.md) |
| 劇情多鏡、一組角色動作 | [劇情流程](video/production-flow.md)、[動作組](animation/workflow.md) |
| 安裝與模型來源 | [installation/](installation/README.md) |
| 素材紀錄與驗收 | [result-records](result-records.md)、[assets/](assets/smoke-potion.md) |
| 維護：新增能力、審視、驗證 | [maintenance/](maintenance/README.md) |
| 決策與經驗 | [DECISIONS.md](DECISIONS.md)、[decisions/](decisions/)、[experiences/](experiences/asset-records-2026-10-01.md) |
| 第 3–8 階段重構結案 | [結案摘要](maintenance/restructure-summary-phase3-8.md) |

能力能不能跑，以當前機器的能力快照、preflight 與適用平台實測為準，經驗頁不能代替這些 gate。

## 記錄與提升規則

- 圖片的 JSON manifest 是選用的技術追溯資料；要保存素材版本或人工驗收時，依 [result-records](result-records.md) 按需建立 Markdown 頁。
- 不把長篇 log 複製進 prompt，不從 accepted／rejected 自動訓練或改寫生成參數。
- 經驗按路線記日期、task、版本與環境、操作、結果、證據、範圍、限制；沒有的欄位省略，不存秘密與大型 payload，改引用證據檔。
- 穩定的操作契約留在 template 與工具的 `--help`；知識庫只存有範圍的條件性觀察，不據此改 profile 或 accepted／rejected 狀態。
- 觀察要升格成正式規則，需新增可重現證據並經使用者核准，同時改正式設定與能力 gate，並記錄決策理由。

知識庫以一般 Markdown 與檔案工具維護，Obsidian 內建功能（檔案瀏覽、搜尋、反向連結、圖譜）即可；整合範圍見 [Obsidian 整合說明](maintenance/obsidian-integration.md)。
