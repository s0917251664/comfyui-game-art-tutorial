---
type: experiment-result
status: partial
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

## 2. Grok（Grok CLI，`image_edit`，3 次）——未完成
- 我在 Windows 上呼叫 `grok -p`（headless）兩次，立刻失敗，訊息原文：`Not signed in. To authenticate without a browser, run: grok login --device-code. Alternatively, set the XAI_API_KEY environment variable or run grok login on a machine with a browser.`
- 之前（2026-10-19）同一台機器的 Grok 是已登入的，現在登入狀態失效。登入需要你本人操作，我不能代填帳號；也不會去找或設定 API 金鑰。
- 因此：Grok 的每次耗時、CLI 回報的 token／額度數字、輸出尺寸是否與原圖相同、範圍外變動比例，**都沒有新資料**。
- 參考（舊資料，2026-10-19，同一張 A.png、不同提示詞，來自 `2026-10-19-windows-results.md`）：Grok 改圖約 72 秒／次，輸出 832×1232（與原圖 832×1216 不同，無法逐像素比對）；CLI 沒有回報 token 或額度數字（當時沒有取得，記為「無」）。這不是這次任務的量測，只能當背景。

## 3. 限制
- 我方只有 3 次、單一素材、單一機器；時間含模型載入（首次較長）。
- 我方貼回前的輸出整張都不同於原圖（原始輸出尺寸也不同），「範圍外 0」是貼回工序的結果，不是模型本身的行為。
- Grok 側沒有量測，不能下成本結論。補跑只需要你先在 PowerShell 執行 `grok login --device-code` 並完成登入，我再跑 3 次。
