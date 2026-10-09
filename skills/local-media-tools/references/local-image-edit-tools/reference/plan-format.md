# Image edit tools：參數與輸出

## `composite`

必要參數：`--source`、`--edited`、`--mask`、`--output-dir`。三張輸入必須是單影格，尺寸一致；source 與 edited 會解碼為 RGBA。mask 必須是同尺寸、含 Alpha 的 PNG。工具以 Alpha byte 選擇／插值 RGBA channels：0 完全取 edited，255 完全取 source，介於兩者按 byte 權重混合。`--keep-source-alpha` 選用時，合成後將來源 Alpha 原樣放回；省略時維持既有完整 RGBA 合成契約。既有輸出資料夾（即使空目錄）也會拒絕。

輸出新目錄中的 `composited.png` 與 `result.json`。manifest 記錄輸入輸出路徑與 SHA-256、尺寸、保留像素數及候選狀態。alpha=255 區域會做逐 byte invariant 檢查；它不評分編修內容。

## `recolor`

```powershell
<python> <image_edit_tools.py> recolor --source <source.png> --mask <alpha-mask.png> --from-hue 180 --to-hue 0 --hue-range 45 --min-saturation 0.12 --output-dir <new-dir>
```

需要既有、同尺寸、單影格且帶 Alpha 的 PNG 遮罩；Alpha 小於 255 為可編輯選區，255 排除。只改 Alpha 可見、來源 hue 距離 `from-hue` 不超過 `hue-range`，且 saturation 大於等於 `min-saturation` 的像素。色相範圍 0–360 度，`hue-range` 範圍 0–180 度，`min-saturation` 範圍 0–1。Hue rotation 保留 HSV saturation/value 到 RGB 量化前；不是物理亮度保留，不保證精確目標 RGB，也不生成材質、紋理或改變反射。來源 Alpha、遮罩外及未匹配 RGBA 逐 byte 保留。沒有語意分割或畫遮罩功能，輸出選區與效果均待人工檢查。

輸出新目錄含 `recolored.png`、`comparison.png` 和 `result.json`，狀態為 candidate。此操作不屬於 sweep，不新增 generation task 或 graph。實測與限制見[單一物件換色紀錄](../../../../../docs/knowledge/art/single-object-color.md)。

## `compare`

必要參數：`--source`、`--edited`、`--output-dir`；`--mask` 選填，但提供時仍須是同尺寸 Alpha PNG。尺寸不符就停止，不自動對齊、縮放或旋轉。

輸出 `difference.png`、`comparison.png`、`comparison.json`；提供遮罩且遮罩含非 255 alpha 區域時才輸出 `detail.png`。差異圖將每像素最大 RGBA byte 差映成紅色強度，沒有 perceptual threshold。統計包含 whole；有 mask 時另列 alpha 0 的 edited、0–255 的 transition、255 的 preserved 區域。RGBA 統計包含完全透明像素內的 RGB 值，不能當成可見差異或美術品質分數。

## `sweep` plan JSON

ComfyUI 專屬規則已移至[有限參數比較規格](../../../../comfyui-run/references/comfyui-image-sweep/reference/plan-format.md)。本頁其餘操作不需要 ComfyUI。

### 執行與停止

見[ComfyUI sweep 執行與停止](../../../../comfyui-run/references/comfyui-image-sweep/reference/plan-format.md#執行與停止)。

## 範例調整

既有 sweep 範例仍保留於 `reference/examples/`；路徑與使用方式見[新規格](../../../../comfyui-run/references/comfyui-image-sweep/reference/plan-format.md#範例調整)。
