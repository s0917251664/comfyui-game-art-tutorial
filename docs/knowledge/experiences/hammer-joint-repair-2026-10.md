---
type: experience
status: current
---
# 錘子接合修正實驗（2026-10-12）

封面 v4 的局部接合偏移修正紀錄。這是此來源及設定的觀察，不是模型排名或普遍失敗率。通用的選路與方法見[物件局部修正的取捨](../art/local-object-repair-decisions.md)。

本機證據都在 `output/`，另機未必存在。

## 第一輪比較

決策紀錄（本機證據：`output/hammer-alignment-v4-new-task/decisions.json`）包含文字編修、裁圖、遮罩重繪與原圖幾何草稿。FLUX.2 曾將小套筒改成大金色結構；SDXL 遮罩重繪曾出現灰塊，調高重繪幅度後又改錯材質與手部。

用歷史成功圖作為結構參考的第 4 輪排除於獨立比較。使用者也要求**這次修復**只能用既有 ComfyUI 流程：Python 幾何移位、像素補畫與補縫的 `geometry*`、`seam*`，以及以幾何草稿為輸入的第 8 輪，均排除於這次的比較與成功證據。

這項排除只限這次實驗。之後的遊戲動畫產線已確立道具一律程式貼原圖，見[橫向動作經驗](side-scroller-character-anim-2026-10.md)與 [R5](../rules/method-stop-loss.md)。

## 獨立比較

新實驗分別採用既有 ComfyUI 流程與 GPT 連續三輪編修，兩者從相同原始 v4 開始，不輸入既有成功圖。

- **GPT 三輪**（本機證據：`output/hammer-independent-gpt-agent/experiment.json`）：第一輪仍偏心，第二輪目視接合合理，第三輪維持改善；手部與細節有變動，不能宣稱完全保留，也不能用此案例宣稱「GPT 三次都修不好」。此組只有複製模型原始輸出，沒有程式修圖。
- **ComfyUI 六輪**（本機證據：`output/hammer-independent-comfy-agent/decisions.json`）：包含固定 FLUX.2 編修、既有引導式局部重繪與原圖裁切編修。六輪都未同時滿足接合與保留條件：有接點仍偏、套筒消失、材質改變或手部重畫等失配。第六輪的裁切只縮小輸入範圍，沒有幾何位移、補畫或補縫。

這是此次既有模型與設定的結果，不代表 ComfyUI 平台所有方法的能力；兩組輪次與策略不同，也不能當成模型效能排行。具體結果與驗收狀態以實驗紀錄為準。
