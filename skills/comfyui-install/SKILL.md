---
name: comfyui-install
description: 在新機器上依硬體與既有狀態安裝、部署 ComfyUI 遊戲美術產線；遇到模型和版本時沿用核准基準，不自行升級。
---

# ComfyUI 產線安裝

當使用者要在新機器設置產線，或 repo 的 `local_config.json` 不存在時使用。這是一份目標清單，不是固定腳本：先判斷各項在這台機器是否已成立，再選合適方法補足，保留使用者既有版本與設定意圖。

開始操作前，從[總工具庫](../../docs/knowledge/TOOLS.md)確認涵蓋的能力，再讀[安裝知識索引](../../docs/knowledge/installation/README.md)，並依本次範圍讀取：

- [完整安裝目標與檢查流程](../../docs/knowledge/installation/install-guide.md)
- [模型家族、來源與容量](../../docs/knowledge/installation/models-and-sources.md)
- [LoRA 訓練工具（僅使用者要訓練時）](../../docs/knowledge/installation/lora-training.md)
- [`docs/tested-versions.md`](../../docs/tested-versions.md) 的實際版本／hash 捕捉狀態

在任何模型或套件下載前，先說明所選能力需要的磁碟空間並確認可用空間足夠。模型選擇以已核准設定檔和 tested-version manifest 為準；安裝時看到較新模型，不代表要評估或替換它。不同平台的 smoke test 必須在該機器實際完成，離線部署檢查不等於生成驗證。
