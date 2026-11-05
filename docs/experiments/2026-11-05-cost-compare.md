---
type: experiment-result
status: measured
date: 2026-11-05
---
# 成本與用量對照：「把右手改成揮手，其他不變」（騎士圖 A.png）

狀態：**我方工具包已量測；Grok 側未跑成**（Windows 上 Grok CLI 目前未登入）。

## 1. 我方工具包（`gameart.py pose-edit run --custom`，3 個 seed，再貼回）
- 環境：Windows 11、NVIDIA GeForce RTX 4080（16 GB）、ComfyUI 0.34.0、模板 `image/flux2/edit`（FLUX.2 Klein 4B）。
- 指令：`pose-edit run --image A.png --custom "the hand on the right side of the image, currently resting on the hip, is raised high with an open palm waving, while the hand on the left side of the image keeps gripping the sword hilt on the shoulder exactly as before" --keep-extra "…" --avoid "…" --seeds <seed>`，每個 seed 各跑一次。
- 每張耗時（含載入與取圖，牆鐘）：seed 7 為 32.0 秒、seed 21 為 28.1 秒、seed 99 為 28.0 秒；3 張合計 88.1 秒（平均 29.4 秒）。
- 貼回（ECC 對位、只貼右側手臂區、顏色對齊、羽化）：每張約 0.5 秒（CPU），貼回區域約 11.3–11.7 萬像素。
- 輸出尺寸：pose-edit 原始輸出 832×1232，原圖 832×1216，**尺寸不同**；貼回後輸出與原圖同為 832×1216。
- 貼回區域外變動：0 像素（相對 A.png，貼回區域以外）。若以固定的多邊形範圍計，約 0.84–0.89% 的像素落在多邊形外緣的羽化帶內（貼回後有變動）。
- 費用：本機執行，不計雲端額度；耗電與設備成本未量。
- 這個 session 的 token 用量：**讀不到**（這個環境沒有提供查詢用量的工具），所以不寫數字。
- 對照圖（本機，不入版控）：`output/cost-compare/ours_compare.jpg`（原圖、seed 7、21、99 貼回後）。圖是目視挑選前的全部三張，沒有逐張評分。

## 2. Grok（Grok Build CLI 1.0.46，`grok -p`，`image_edit` 工具，3 次）
- 指令：在放有 A.png 的資料夾執行 `grok -p "請用 image_edit 工具編輯 A.png：只把畫面右側那隻原本扶在腰上的手改成揮手（舉高、手掌張開），其他一切保持不變，包括持劍的手與盔甲，存成 out/grok-N.png" --allow image_edit --allow image_gen --disable-web-search --output-format json`。每次都是新對話。
- 每次耗時（牆鐘，含代理程式規劃與取圖）：44 秒、51 秒、57 秒；合計 152 秒（平均 50.7 秒）。
- CLI 回報的用量（JSON 的 `usage` 與 `total_cost_usd`；模型欄位 `grok-4.7-build`，每次 5 個模型呼叫）：

| 次 | input_tokens | cache_read_input_tokens | output_tokens（其中 reasoning） | total_tokens | total_cost_usd |
|---|---|---|---|---|---|
| 1 | 53,492 | 75,264 | 2,789（1,781） | 131,545 | 0.054859 |
| 2 | 46,828 | 83,072 | 3,198（2,383） | 133,098 | 0.0524892 |
| 3 | 28,771 | 104,064 | 3,719（2,776） | 136,554 | 0.04484192 |
| 合計 | 129,091 | 262,400 | 9,706 | 401,197 | 0.1521901 美元 |

  這個 `total_cost_usd` 是 CLI 回報的代理程式文字模型呼叫費用，**我無法確認它是否包含生圖／改圖本身的費用**（CLI 沒有拆分），所以不能當作「一張圖的完整成本」。另外，一次只回 "ok" 的最小呼叫就是 20,509 tokens、0.0132 美元，代表每次呼叫有固定的系統提示成本。額度（quota）欄位：CLI 沒有回報。
- 輸出尺寸：三次都是 832×1232，原圖 832×1216，**尺寸與原圖不同**，無法逐像素比對。把輸出縮回 832×1216 後粗估，圖面固定多邊形以外有 17.0–20.6% 的像素差異超過 8 個色階（整張被重新畫過、略有位移與縮放，這是粗估，不是嚴格的「範圍外變動」）。
- 畫面目視：三張都有清楚的揮手，持劍手與劍保留；但整張圖是重畫的（盔甲細節、披風、臉都有細微不同），沒有「範圍外不變」的保證。
- 對照圖（本機，不入版控）：`output/cost-compare/grok_compare.jpg`（原圖與三次輸出）、`ours_compare.jpg`。

## 一眼對照
| 項目 | 我方工具包（本機） | Grok CLI |
|---|---|---|
| 每張耗時 | 28–32 秒（平均 29.4），貼回 +0.5 秒 | 44–57 秒（平均 50.7） |
| 雲端費用 | 無（本機；電費與設備未計） | CLI 回報約 0.045–0.055 美元／次（僅文字模型部分，是否含生圖未知），三次合計 0.152 美元 |
| 用量數字 | 此 session 的 token 讀不到；本機沒有 token 計費 | 每次約 13.1–13.7 萬 tokens（大部分是快取讀取） |
| 輸出尺寸與原圖 | 貼回後相同；模型原始輸出 832×1232 不同 | 832×1232，不同 |
| 範圍外不變 | 貼回區域外 0 像素 | 無保證，整張重畫（粗估 17–21% 像素有差異） |
| 揮手畫面 | 需要多 seed 挑選，部分候選手形或持劍手不對 | 3 次都清楚、好看 |

## 3. 限制
- 我方只有 3 次、單一素材、單一機器；時間含模型載入（首次較長）。
- 我方貼回前的輸出整張都不同於原圖（原始輸出尺寸也不同），「範圍外 0」是貼回工序的結果，不是模型本身的行為。
- Grok 只跑 3 次、單一提示詞；耗時含代理程式規劃，費用欄位是 CLI 自己的回報，不含已知的圖像費用，所以只能當量級參考。兩邊的圖片品質差異是目視，沒有盲評。
- 費用不可直接相比：我方是自有 GPU（沒有計入設備與電費），Grok 是雲端付費。
