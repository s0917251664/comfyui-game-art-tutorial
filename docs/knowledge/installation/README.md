# 安裝與模型知識

這裡是 ComfyUI 產線安裝決策與模型來源的 canonical 說明。先依當前任務讀取所需頁面：

先從[總工具庫](../TOOLS.md)選出這次要用的工具，再讀取下列必要資料。

- [完整安裝目標與檢查流程](install-guide.md)：新機器現況盤點、安裝與部署、能力偵測、離線檢查和實機 smoke。
- [模型家族、來源與容量](models-and-sources.md)：profile 對應模型、下載來源、選配項目和空間估算。
- [LoRA 訓練工具](lora-training.md)：只有使用者要建立／訓練角色或風格 LoRA 時讀取。

此知識庫不會授權模型升級。版本重現依 repo 的 `docs/tested-versions.md` 與各機器實際 capture 狀態；升級評估是另一個明確觸發的維護工作。

專案知識庫及上游技能的支援範圍見[Obsidian 整合說明](../maintenance/obsidian-integration.md)。知識庫以既有 Markdown 與一般檔案操作維護，與模型、ComfyUI 節點及圖片／影片能力無關。
