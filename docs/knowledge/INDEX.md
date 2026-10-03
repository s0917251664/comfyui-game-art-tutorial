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

1. 讀 [TOOLS.md](TOOLS.md) 了解現在有的工具、能力狀態與各技能觸發條件。
2. 新圖片需求由 [art-generation.md](art-generation.md) 分類，只有使用者提出特定參數時查 [art-parameters.md](art-parameters.md)。
3. 影片由 [video/README.md](video/README.md) 路由；同一角色的一組動作由 [animation/workflow.md](animation/workflow.md) 編排。
4. 安裝依 [installation/README.md](installation/README.md)；明確盤點升級依 [maintenance/README.md](maintenance/README.md)。
5. 決策從 [DECISIONS.md](DECISIONS.md) 開始；經驗依模型/task 到 [experiences/](experiences/) 找相符項目。

需要查找或修改專案知識筆記時，先讀 `skills/project-knowledge/SKILL.md`，再依 `TOOLS.md` 使用標準 Markdown 和一般檔案讀寫方式操作。沿用既有目錄與文件規範，草稿由小模型撰寫、root review；整合來源與上游能力限制見[維護說明](maintenance/obsidian-integration.md)。

若某分支已有更具體的 task 頁，只讀相關小節。能力是否可跑仍以當前機器的 capability snapshot、preflight 與適用平台實測為準，經驗頁不能代替這些 gate。

## 記錄與提升規則

- 生成圖片的 JSON manifest 是選用技術追溯資料；需要保存素材版本或人工驗收時，依 [result-records.md](result-records.md) 在 [assets/smoke-potion.md](assets/smoke-potion.md) 所示位置按需建立 Markdown 頁。
- 不把長篇 log 複製進 prompt，不從 accepted/rejected 自動訓練或改寫生成參數。
- 每項經驗保留日期、模型、平台／硬體、task／輸入、證據、觀察、適用範圍與限制，避免把單次結果當成通則。
- 歷史觀察只有在新增可重現證據並經人工核准後才能提升成正式 profile／技能規則；更新時同步改正式設定與能力 gate，並記錄決策理由。

## 遊戲美術工具參考

- [遮罩格式、Simple Mask、GrabCut 與 SAM](art/masking.md)：準備局部修改或拆層選區時查閱，遮罩預覽仍需人工確認。
- [本機圖片編修工具](art/edit-tools.md)：遮罩內 recolor、composite、compare、有限 sweep、參考圖板與 Alpha 稽核的契約及驗證。
- [物件平面組裝流程](art/object-design-workflows.md)：`scene`／`sheet`／`pattern` 的使用範圍與限制。
- [單一物件換色](art/single-object-color.md)：HSV 色相旋轉案例、像素保留證據與限制。

## 決策與經驗

- [生效中決策](DECISIONS.md)
- [日期化決策紀錄](decisions/)
- [依模型與 task 查經驗](experiences/)
- [資產紀錄實測](experiences/asset-records-2026-10-01.md)
- [FLUX.2 與結構鎖觀察](experiences/flux2-and-structure-lock-observations.md)

## Obsidian 內建功能

repo 附最小 `.obsidian/app.json` 和 `core-plugins.json`，使用檔案瀏覽、搜尋、反向連結、出站連結、標籤與圖譜等內建能力；不依賴社群外掛。此設定只是開啟 vault 的初始工作方式，使用者可在本機 Obsidian 調整。
