---
type: experiment-result
status: measured
date: 2026-11-05
---
# 去背：ComfyUI 能做什麼、不能做什麼（Windows，RTX 4080，2026-11-05 實測）

## 1. 靜圖去背（`--remove-bg`）：可用，沒壞
`generate.py concept --remove-bg` 在這台機器正常：流程用核心節點 `LoadBackgroundRemovalModel` 載入 `birefnet.safetensors`，`RemoveBackground` 產生前景遮罩，再 `InvertMask`、`JoinImageWithAlpha` 存成 RGBA PNG（1024×1024，約 1 秒）。透明度檢查：完全透明 76.9%、半透明 20.9%、不透明 2.2%（人物本體 alpha 為 254，被算成半透明）。棋盤格預覽目視邊緣乾淨，披風半透明也保留。沒有缺節點或缺模型。

## 2. 半透明特效（黑底發光、煙）：BiRefNet 不行；亮度轉透明可用核心節點做到大部分
用一張合成特效（軟光暈、火星、一條硬核光軌，加亮疊加在黑底）當標準答案，把結果疊到深藍紫背景，與標準答案比平均誤差 MAE（越小越好）：

| 做法 | MAE | 說明 |
|---|---|---|
| ComfyUI AI 去背（BiRefNet） | 0.088 | alpha 平均只有 0.015：只留下最亮的光軌，光暈與火星全被當背景切掉 |
| ComfyUI 亮度轉透明（核心節點），一般（straight）合成 | 0.074 | 保留軟邊，但顏色沒有除回透明度，疊上去偏暗、周圍有暗暈 |
| 同上，用預乘（premultiplied）合成 | 0.046 | 遊戲引擎若以預乘或加亮模式疊，接近正確 |
| 現有本機腳本 `vfx luma-alpha` | 0.029 | 會把顏色除回 alpha（反預乘），誤差最小 |

數字在 `fx_compare.json`。對照圖與測試用特效圖不進 repo（見[實驗紀錄說明](../README.md)）。

可重用流程：`luma_alpha_core.api.json`（核心節點：三個色版各取遮罩、反相、相乘、再接 `JoinImageWithAlpha`，等於 1−(1−R)(1−G)(1−B)，約 0.5 秒）。注意 `JoinImageWithAlpha` 吃的是「透明度遮罩」，所以輸入要是相乘後的結果（等於已反相），與 `--remove-bg` 範本要先 `InvertMask` 同一個道理。

ComfyUI 做不到的：核心節點沒有「影像除以影像」，無法把顏色除回 alpha（反預乘）；`MaskComposite` 的 `or` 會先二值化，不能當取最大值。要反預乘或調黑點、白點、gamma，仍要用本機腳本（或另裝影像運算節點包）。

## 結論
- 靜圖去背在 ComfyUI 內可用（BiRefNet）。
- 半透明特效不要用 AI 去背；ComfyUI 可用核心節點做亮度轉透明（軟邊保留），但顏色品質略輸腳本；精確版仍用本機腳本。
- 沒有做成正式 template（`templates/` 需要 schema 與測試），目前只提供可載入的 API graph，是否升格為 template 待決定。
- 單一合成特效、單一次；真實特效與影片沒有逐幀驗證；影片版 ComfyUI 流程沒有測。
