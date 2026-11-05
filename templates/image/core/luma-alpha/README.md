# 黑底特效亮度轉透明（核心節點，草稿）

`image/core/luma-alpha` 把**純黑底**的特效靜圖（發光、火花、光暈、亮色煙）轉成透明 PNG：越亮越不透明，純黑完全透明，算式是 alpha = 1 −(1−R)(1−G)(1−B)。只用 ComfyUI 核心節點（`ImageToMask`、`InvertMask`、`MaskComposite` 相乘、`JoinImageWithAlpha`），不用模型。

**什麼時候用哪一種去背，先看 [去背選方法](../../../../docs/knowledge/art/background-removal.md)。**

## 定位

- 只有一張黑底特效靜圖、想留在 ComfyUI 裡處理時用。
- 影片、或要最乾淨的顏色時，用本機 `gameart.py vfx luma-alpha`：它會把顏色除回透明度、能設黑點與 gamma；ComfyUI 核心節點做不到這兩件事。
- 不是黑底的圖、暗色煙霧、實心物體都不適用：暗的地方會被當成透明。

## 狀態

draft，兩個平台都是 `untested`。同一份 graph 在 2026-11-05 Windows／RTX 4080 直接送 ComfyUI 跑過一次（約 0.5 秒），還沒經過 runner；只測一張合成特效。輸出是 candidate。

實測誤差（疊到深藍紫底，越小越好）：一般疊法 0.074、預乘疊法 0.046；AI 去背 0.088、本機腳本 0.029。數據見 [實驗紀錄](../../../../docs/experiments/2026-11-05-bg-removal/README.md)。

## 使用

```text
python tools_src/gameart.py run show image/core/luma-alpha
python tools_src/gameart.py run image/core/luma-alpha --set image=<黑底特效.png> --preflight --allow-unverified-platform
python tools_src/gameart.py run image/core/luma-alpha --set image=<黑底特效.png> --allow-unverified-platform
```

輸出的 RGB 沒有除回透明度，看起來像「預乘」：遊戲引擎用加亮（additive）或預乘方式疊時接近正確；用一般 alpha 疊時會偏暗、周圍有暗暈。
