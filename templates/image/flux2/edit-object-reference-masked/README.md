# FLUX.2 遮罩物件局部編修

狀態為 `draft`，各平台 `untested`。候選仍需美術驗收。

由 `image/flux2/edit-object-reference` 派生，使用待編修圖片與第二張參考，再加入已確認的遮罩。輸入契約、可調值與模型 pins 以 `gameart.py run show image/flux2/edit-object-reference-masked` 為準。

原圖經 VAE 編碼，同時作為 target reference 與採樣起點。RGBA 遮罩由 LoadImage 的 MASK 輸出讀取（alpha 0 選取、alpha 255 保留），經 MaskToImage、ImageScale 與 ImageToMask 對齊縮放後的 target，送入 SetLatentNoiseMask。採樣器使用這份 latent，並接收 SplitSigmasDenoise 的低噪聲輸出。模型與原始 scheduler 設定沿用來源模板；實際採樣步數取決於選用的低噪聲尾段。

這份派生依據本機 ComfyUI core commit `12d5279438bfefc058a269eae805ceab6047777f` 的節點實作；並非官方發布的 masked blueprint。不下載、替換模型，不以 Python 畫圖或修正幾何。

遮罩限制 latent 重繪，但 VAE 往返及縮放仍可能改變遮罩外 RGB。需逐像素保留時，使用既有 `edit composite` 將候選依原尺寸遮罩回貼。模型輸出、合成結果與各自紀錄應分開保存；遮罩外零變動不等於遮罩內修復成功。

## 用過的方式

- 3D 灰模照設計圖上色：見[圖轉 3D](../../../../docs/knowledge/art/image-to-3d.md)。
- 握柄交界的小範圍重繪：只框手或交界，見[橫向動作經驗](../../../../docs/knowledge/experiences/side-scroller-character-anim-2026-10.md)。
- 同角色第二參考改視角：2026-10-27 Skye 背面用角色母版加側面圖與全圖遮罩，爬梯影格以候選身分進了遊戲（本機證據：`output/skye-design/back6/`）。

## 已知失敗

- 遮罩框到錘柄時，柄被改成粗木棍、錘頭透視接不上；要連錘頭一起框，或完全不框柄。
- 同一區域反覆重繪只會越補越糊，依 [R5](../../../../docs/knowledge/rules/method-stop-loss.md) 最多一次。
- 雙手握短柄仍未解決，見[封面握錘失敗紀錄](../../../../docs/knowledge/experiences/cover-hammer-grip-2026-10.md)。

選路見[物件局部修正的取捨](../../../../docs/knowledge/art/local-object-repair-decisions.md)。

2026-10-13～29 本機共 296 次 run 都是 `completed`。這只是技術完成，平台狀態未升級。
