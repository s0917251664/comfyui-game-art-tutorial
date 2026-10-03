---
type: reference
status: current
---
# 單一物件換色

**日期：** 2026-10-03  
**適用範圍：** 本機 Windows／CUDA／RTX 4080；透明藥水瓶單一候選的局部色相調整。  
**狀態：** recolor 工具與本案例已實測；輸出仍為待 Steve 驗收的 candidate。

## 適用方式

單一物件已有可用外觀，只需把指定區域的既有色彩轉到另一色相時，可使用 `image_edit_tools.py recolor`。它不是生成或材質轉換：需要一張已有 Alpha 的 PNG 遮罩做空間選取，並依來源像素色相範圍與飽和度門檻篩選可見像素。它保留選中像素原有 HSV 飽和度與明度（在 RGB 量化前），不保證精確目標 RGB，也不做物理光照或材質重算。

遮罩 Alpha 小於 255 的像素屬可編輯範圍；Alpha 255 完全排除。遮罩尺寸須與來源相同，且只能是帶 Alpha 的單影格 PNG。工具沒有語意分割或畫遮罩功能；若選區由其他方式產生，仍須由人檢查。輸出只修改同時符合可見 Alpha、選區、來源色相範圍及最低飽和度門檻的像素；其餘 RGBA（包含遮罩外與透明像素）精確保留。低飽和中性色或超出色相範圍的部分會留下原色。

```powershell
python <ComfyUI>\tools\image_edit_tools.py recolor --source <source.png> --mask <alpha-mask.png> --from-hue 180 --to-hue 0 --hue-range 45 --min-saturation 0.12 --output-dir <new-output-dir>
```

色相以度數表示，範圍 0–360；`hue-range` 範圍 0–180，`min-saturation` 範圍 0–1。每次必須指定全新且不存在的輸出目錄；輸出 `recolored.png`、`comparison.png`、`result.json`。manifest 記錄匹配／改動像素數、來源與遮罩 hash，並將美術接受狀態留為待人工檢視。

## 與生成、遮罩及合成的分工

推薦順序是先用既有生成 task 取得單件候選並檢查輪廓；確認換色區域後，純顏色需求可用本機 `recolor`，需要改反光、紋理、材質或形狀時才考慮既有外觀生成 task，最後視需要用 `composite` 控制哪些像素回到原圖，再逐張檢視與驗收。這些步驟不保證生成能完整控制材質。

`composite` 的 `--keep-source-alpha` 是選配，會保留來源 Alpha；省略時維持原本以 Alpha 遮罩選擇／插值完整 RGBA 的契約。此選項不影響 `recolor` 的 Alpha 保留行為。

本案例的 `body-mask.png` 是為後合成／換色製作的實驗選區，從未送入生成 task。它不代表 Steve 已接受此遮罩，也不構成可重用遮罩。recolor 對選區及未匹配像素的技術保留檢查，不能替代選區品質或美術驗收。

## 2026-10-03 實測

來源是 768×768 RGBA 青綠玻璃瓶候選。先以既有 `refine` task、seed `202610034` 分別試 denoise 0.5 與 0.75；兩次都未命中紅色，0.75 對瓶塞／形狀改動更多，因此停止繼續抽樣。其後以 `from-hue=180`、`to-hue=0`、`hue-range=45`、`min-saturation=0.12` 執行本機 HSV 色相旋轉。瓶身轉紅，但邊緣仍有少量青綠，底部也留有原色；保持 candidate，尚待 Steve 驗收。

為了避免柔邊碰到瓶頸與瓶身接合處，將後處理選區更新為 `body-mask-v2.png`，強制 y<350 全部保留；沒有增加生成次數。最終輸出匹配 65,562 像素、改動 65,398 像素。獨立比對確認來源最上方 350 列、全圖 Alpha 及遮罩保留區 RGBA 完全相同；比較報告中 510,083 個 mask-preserved 像素皆未變。瓶身轉紅，但仍有少量青綠邊緣與底部原色，維持 candidate。Hue rotation 保留飽和度／HSV value 到 RGB 量化前，並非物理亮度保留或重打光；工具也不新增紋理、金屬／玻璃反射等材質特徵。

- 執行與人工觀察摘要：[review.json](../../../output/single_object_color_20261003/review.json)
- ComfyUI 執行追溯：[execution-proof.json](../../../output/single_object_color_20261003/execution-proof.json)
- 本機換色 manifest：[result.json](../../../output/single_object_color_20261003/final-red/result.json)
- RGBA 差異與選區統計：[comparison.json](../../../output/single_object_color_20261003/final-red-diff/comparison.json)
- 最終換色候選：[recolored.png](../../../output/single_object_color_20261003/final-red/recolored.png)

單元測試 43 項通過；部署 verifier 19 項通過、0 項失敗，且部署版 recolor 與 `composite --keep-source-alpha` 的解碼像素均與原始碼一致。此次記錄只證明此版本工具的色相旋轉、Alpha／未匹配像素保留及本案例輸出；沒有建立新的生成 task、graph 或 profile，也不代表一般材質控制能力。無新增套件或模型，部署只需同步 `image_edit_tools.py`。
