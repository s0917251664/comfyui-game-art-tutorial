# SAM 2.1 自動候選遮罩

`tools_src/sam_segment.py` 使用 Meta 官方 `facebook/sam2.1-hiera-small`，替單張圖片產生多個無語意標籤的候選遮罩。它不是自動完成 PSD／Spine 拆件的工具，也不會知道哪一片應命名為「尾巴」或「左手」。

固定輸出來源副本、`contact_sheet.png`、`manifest.json`，以及每個候選的 editor mask、Comfy mask、紅色預覽和透明 cutout。`mask_comfy.png` 遵守既有契約：選取區 alpha=0、其餘 alpha=255。

## 2026-09-05 實測

- 環境：RTX 4080 16 GB、PyTorch 2.13.0+cu130、Transformers 5.15.0。
- 832×1232 Skye 角色母圖產生 23 個原始候選，工具保留最高分且面積合理的 12 個。
- 可辨識完整角色、左右靴、尾巴、單耳、胸前口袋、袖口、左右腿與部分髮絲高光。
- 未自動提供可直接採用的眼睛、雙手、完整頭部與完整軀幹拆件。
- 尾巴候選接到既有 `layer_split` 後成功輸出 832×1232 RGBA；Alpha extrema `(0,255)`，透明像素 1,005,859、不透明像素 19,165、半透明像素 0。

## 限制

- Score 不代表候選符合動畫零件需求；本案例最高分是完整角色。
- 候選可能把陰影、高光或小配件當成物件，也可能漏掉眼睛、手指等小部位。
- 候選可以重疊；正式拆件仍需規劃前後層與補畫被遮住的內容。
- 此 runtime 的 `float16` 在 TorchVision NMS 後處理會發生 dtype mismatch，因此工具鎖定 `float32`。
- Windows 未啟用 Developer Mode 時，Hugging Face 快取無法使用 symlink，仍可執行但可能多占磁碟空間。

SAM 與 Simple Mask Tool 是獨立工具。SAM 先提出候選以節省大輪廓描邊時間；候選不準時再用 Simple Mask Tool 人工修正，兩者只交換標準 PNG 遮罩。
