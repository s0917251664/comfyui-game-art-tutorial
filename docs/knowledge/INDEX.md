---
type: index
status: current
---
# Game Art Pipeline Knowledge Vault

此資料夾本身就是可開啟的 Obsidian vault，內容也可直接用一般 Markdown 閱讀。不要把 vault 筆記直接灌入每個 prompt；先讀 [工具與技能總表](TOOLS.md) 找正確工具和入口，再按 task 查一頁相關知識。

## 從 Obsidian 開啟

在 Obsidian 的 vault chooser 選 **Open folder as vault**，選 repository 內的 `docs/knowledge/`。這會直接開啟此資料夾，不需要安裝 Obsidian 外掛或複製既有個人 vault 的私有內容。若已有自己的 vault，可以把它保留為另一個 vault；需要時從 chooser 切換。官方說明：[Manage vaults](https://obsidian.md/help/Files%2Band%2Bfolders/Manage%2Bvaults)、[Configuration folder](https://obsidian.md/help/Files%2Band%2Bfolders/Configuration%2Bfolder)。

此 vault 使用標準 Markdown 相對連結；沒有社群外掛或同步服務依賴。只需將希望版控的筆記提交在本資料夾。Obsidian 自己產生的 workspace/cache 狀態不納入版控。

## 先找工具，再查知識

跨路線的執行規則（R1 候選與美術驗收、R2 固定流程、R3 Idle 錨定）只寫在 [rules/](rules/README.md)。

1. 讀 [TOOLS.md](TOOLS.md) 了解現在有的工具、能力狀態與各技能觸發條件。
2. 新圖片需求由 [art-generation.md](art-generation.md) 分類，只有使用者提出特定參數時查 [art-parameters.md](art-parameters.md)。
3. 影片由 [video/README.md](video/README.md) 路由；同一角色的一組動作由 [animation/workflow.md](animation/workflow.md) 編排。
4. 安裝依 [installation/README.md](installation/README.md)；明確盤點升級依 [maintenance/README.md](maintenance/README.md)。
5. 決策從 [DECISIONS.md](DECISIONS.md) 開始；經驗依任務、工具、CLI/API、模型或 workflow 到 [experiences/](experiences/) 找相符項目。

需要查找或修改專案知識筆記時，先讀 `skills/project-knowledge/SKILL.md`，再依 `TOOLS.md` 使用標準 Markdown 和一般檔案讀寫方式操作。沿用既有目錄與文件規範，草稿由小模型撰寫、root review；整合來源與上游能力限制見[維護說明](maintenance/obsidian-integration.md)。

若某分支已有更具體的 task 頁，只讀相關小節。能力是否可跑仍以當前機器的 capability snapshot、preflight 與適用平台實測為準，經驗頁不能代替這些 gate。

第一次使用或尚未選執行路線時，先讀[專案初始化路線](installation/initialization.md)：可以只整理需求或使用當下可用的平台圖片技能，不需先安裝本機環境。明確選 ComfyUI 後按所選 task 與 executor 自身 gate 執行。

## 記錄與提升規則

- 生成圖片的 JSON manifest 是選用技術追溯資料；需要保存素材版本或人工驗收時，依 [result-records.md](result-records.md) 在 [assets/smoke-potion.md](assets/smoke-potion.md) 所示位置按需建立 Markdown 頁。
- 不把長篇 log 複製進 prompt，不從 accepted/rejected 自動訓練或改寫生成參數。
- 經驗可記 Python、CLI、ComfyUI HTTP API、模型使用與 workflow 操作；按路線記日期、task、版本／環境、操作、結果、證據、範圍、限制與 status。CLI 記 command、工作目錄、exit code／錯誤；API 記 endpoint/method、必要 request/response 欄位、prompt_id/history、逾時恢復與 output 核對；模型記型號／精度、node 版本、硬體及可得的 prompt/seed、品質／速度實測；workflow 記輸入順序、mask、固定／可調參數及驗收。無關欄位省略，不存秘密或大型 payload，改引用證據檔。
- 穩定操作契約留在技能及 references；知識庫只存有範圍的條件性觀察，按需引用，不據此改 profile 或 accepted/rejected 狀態。
- 歷史觀察只有在新增可重現證據並經人工核准後才能提升成正式 profile／技能規則；更新時同步改正式設定與能力 gate，並記錄決策理由。

## 遊戲美術工具參考

- [共用工作流程](../../skills/game-art-workflow/SKILL.md)：需求、版本與內容驗收；[物件／VFX／角色動作方法](../../skills/game-art-workflow/references/production.md)按需讀相關小節；[職責與移植盤點](../../skills/game-art-workflow/references/responsibilities.md)只在維護／移植時讀。
- [平台原生圖片執行](../../skills/platform-image-gen/SKILL.md)與[ComfyUI 有限參數比較](../../skills/comfyui-image-sweep/SKILL.md)：分開的執行責任，不新增平台影片或外部 API backend。

- [遮罩格式、Simple Mask、GrabCut 與 SAM](art/masking.md)：準備局部修改或拆層選區時查閱，遮罩預覽仍需人工確認。
- [本機圖片編修工具](art/edit-tools.md)：遮罩內 recolor、composite、compare、有限 sweep、參考圖板與 Alpha 稽核的契約及驗證。
- [物件平面組裝流程](art/object-design-workflows.md)：`scene`／`sheet`／`pattern` 的使用範圍與限制。
- [特效去背、物件標記局部重繪與 Idle 首尾量測](video/vfx-tools.md)：`gameart.py vfx` 與 `video_inpaint` 的操作契約和 2026-10-07 實測；Idle 規則本身見 [R3](rules/idle-anchoring.md)。
- [ComfyUI Video Layers](video/layers.md)：SAM 影片遮罩候選、ordered layer/明確遮擋 matte、部署與已知驗證缺口。
- [單一物件換色](art/single-object-color.md)：HSV 色相旋轉案例、像素保留證據與限制。

## 決策與經驗

- [生效中決策](DECISIONS.md)
- [日期化決策紀錄](decisions/)
- [依任務、工具與執行路線查經驗](experiences/)
- [已移除轉址檔的舊路徑對照](archive/redirect-stubs.md)：舊連結打不開時，從這裡找 canonical 位置。
- [資產紀錄實測](experiences/asset-records-2026-10-01.md)
- [FLUX.2 與結構鎖觀察](experiences/flux2-and-structure-lock-observations.md)
- [VFX 研究：去背、遮罩局部重繪、Idle 首尾（2026-10-07）](experiences/2026-10-07-vfx-research/design.md)：設計與[實測數據](experiences/2026-10-07-vfx-research/results.md)；`scripts/` 只供追溯，不是產線入口。
- [Skye 修圖平台 A／B 對照實驗（2026-10-07）](experiences/2026-10-07-skye-repair/platform-task-prompt.md)：平台用 prompt 與操作說明（進行中）。

## Obsidian 內建功能

repo 附最小 `.obsidian/app.json` 和 `core-plugins.json`，使用檔案瀏覽、搜尋、反向連結、出站連結、標籤與圖譜等內建能力；不依賴社群外掛。此設定只是開啟 vault 的初始工作方式，使用者可在本機 Obsidian 調整。

## Wan Animate／SCAIL-2 路由

- [Wan Animate／SCAIL-2 評估與受控學習方式](video/animation-evaluation.md)：包含官方 UI 範本、prompt-only 候選、mask 語義與逐階段停止條件。
- [SCAIL-2 API 操作契約與實測](../../skills/comfyui-wan-animate/references/scail2.md)：FP8 權重已安裝，替換／動畫與兩段延伸技術通過，內容 candidate。
- [SCAIL-2 角色替換實驗（2026-10-07）](video/scail2-character-replacement-experiment-2026-10-07.md)：用本人照片替換影片主角，比較整畫面重畫、只換頭＋換臉等四種做法。
- [Wan Animate／SCAIL-2 實驗紀錄（2026-10-06）](video/wan-animate-scail2-experiments-2026-10-06.md)：延伸段、音訊、直式寬高與 SCAIL-2 六支候選的條件、prompt、抽幀觀察與限制。
- [Wan Animate 技能入口](../../skills/comfyui-wan-animate/SKILL.md)：Mix／Move（單段、兩段延伸、音訊、寬高）與 SCAIL-2 固定 API graph 的本機能力查詢、brief 與候選驗收流程；[API 操作 reference](../../skills/comfyui-wan-animate/references/comfyui-api.md)記錄 live preflight 與 request 契約。
- [Wan Animate 安裝紀錄](video/wan-animate-install.md)：安裝 pins 與歷史 33 幀測試；目前 17 幀 API 證據及內容限制以技能/API reference 為準。輸出證據位於本機 ignored output，clean clone 不含。
- [角色動畫 brief 模板](video/templates/animation-brief.md)與[候選測試紀錄模板](video/templates/animation-test-record.md)：先固定輸入、身份錨點與驗收條件，再記錄實際候選與使用者決定。

## 技能庫與執行路線維護

- [技能庫現況與路線界線](maintenance/skill-library.md)：17 個美術技能現行實作、直接 API 與後續候選。
- [平台驗證流程（smoke suite）](maintenance/validation-workflow.md)：`deploy --yes` → `smoke` → `--record`，技術紀錄不等於美術接受（[R1](rules/candidate-review.md)）。
- [路線化新增能力清單](maintenance/new-capability-checklist.md)與[技能／產線審視流程](maintenance/pipeline-review.md)：依任務選驗證與研究範圍。
