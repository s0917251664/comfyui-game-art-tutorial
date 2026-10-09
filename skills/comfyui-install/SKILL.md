---
name: comfyui-install
description: 在新機器上依硬體與既有狀態安裝、部署 ComfyUI 遊戲美術產線，並補齊缺失的依賴；遇到模型和版本時沿用核准基準，不自行升級。
---

# ComfyUI 產線安裝

使用者明確要求在新機器設置 ComfyUI 產線，或已選定本機路線而依賴缺失時才用。單純缺 `local_config.json` 不構成安裝意圖；還沒選路線先走 [game-art-brief](../game-art-brief/SKILL.md) 的初始化。需求整理、平台圖片、不經 ComfyUI 的本機工具不因缺本機環境而要求安裝。

## 這是目標清單，不是固定腳本

先判斷每一項在這台機器「是否已成立」，再選方法補足，保留使用者既有版本與設定意圖。遇到機器特有的狀況（網路擋下載、殘留安裝、CUDA 版本、權限），如實說明，不靜默失敗、不編造結果。

## 開始前

1. 讀 [安裝知識索引](../../docs/knowledge/installation/README.md)，依本次範圍讀 [安裝指南](../../docs/knowledge/installation/install-guide.md) 與 [模型清單](../../docs/knowledge/installation/models-and-sources.md)。
2. 版本以 [已驗證版本](../../docs/tested-versions.md) 為準。已存在的安裝若與基準不同，把差異告訴使用者讓他選，不自己 checkout、不自己升級。
3. 下載任何東西之前，先說明所選能力需要的磁碟空間並確認足夠；模型、套件、custom node 分開列。

## 判斷原則

- 只裝本次所選能力需要的項目；影片模型、選配模型、LoRA 訓練工具都不是基本配備。
- 部署 repo 工具一律用 `gameart.py deploy`（先 dry run，確認後 `--yes`），不手動複製；有 custom node 變更要重啟 ComfyUI，且 queue 為空才重啟。
- 離線檢查（`verify-install`）通過只代表部署內容一致；能力要靠 `gameart.py doctor`、`run <id> --preflight` 與實機 smoke（[驗證流程](../../docs/knowledge/maintenance/validation-workflow.md)）。
- 換機或換顯卡：重跑偵測（`gameart.py doctor --refresh`），不複製舊機器的 `local_config.json` 與各份能力快照。
- 平台驗證升格（`validation approve`）由使用者決定，agent 不自行執行。
- 回報分三層：部署結構、可用範圍、實機驗證，不混成「裝好了」。
