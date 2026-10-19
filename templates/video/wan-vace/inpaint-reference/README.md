# video/wan-vace/inpaint-reference

**Wan2.1 VACE 影片局部重繪＋參考圖（遮罩內畫成指定物件、貼回原片）**（v0.1.1，technical_pass）

和 [`video/wan-vace/inpaint`](../inpaint/README.md) 相同的 graph 與前後處理，多一張參考圖接到 `WanVaceToVideo.reference_image`。用途是把遮罩內換成指定設計的道具，例如照道具母版重畫武器。

- **參考圖處理（graph 內，只用 core 節點）**：
  1. `LoadImage`
  2. 依圖片 alpha，把透明處合成到白底（`GetImageSize`→`EmptyImage` 白色→`InvertMask`→`ImageCompositeMasked`）
  3. `ResizeAndPadImage`：等比縮放到工作區尺寸、置中、白邊補滿
  4. 送進 `reference_image`；`TrimVideoLatent` 裁掉參考幀
- **做法來源**：白底置中參考自 WanGP（`shared/utils/vace_preprocessor.py` 的 `prepare_source`），只借做法，沒有複製程式碼。
- **必填**：`source_video`（24 FPS、5～81 幀）、`masks`、`reference_image`、`prompt`
- **選填**：`mode`（預設 **replace**）、`grow`、`pad`、`crop`、`feather`、`mask_object`、`strength`、`negative`、`seed`
- **prompt**：除了描述畫面，要具體寫出參考物件的形狀、顏色、材質、部件。
- **固定參數**：同 inpaint（VACE 1.3B、shift 5、20 步、cfg 6、uni_pc／simple、24 FPS；工作區最多 832×480 像素）。
- **輸出**：同 inpaint，`outputs/raw/` 加上貼回結果 `composited/`。

## 依據與限制

2026-10-19 E4 研究（[results.md](../../../../docs/knowledge/archive/experiments/2026-10-19-wangp-reverse/results.md)）：

- **replace 模式**：沒有參考圖時，錘子設計會跑掉（模型自己發明）；有參考圖時，兩個 seed 都回到母版設計。
- **keep 模式**：原片已經提供形狀，加參考圖的差異不明顯。
- **第 0 幀**：道具比較扁、缺部件，從第 1 幀起才穩定。要逐幀檢查。
- **小部件**：小尺寸下的紅寶石等細部不明顯。

研究時參考圖是在本機先合成白底、縮到 90% 再送進去；這份 template 改在 graph 內處理，而且縮放會填滿工作區，不留 10% 邊。

## 平台

- windows-cuda：technical_pass（2026-10-19，seed 202／203，遮罩外 56 幀不變；本機證據 output/experiments/wangp-reverse-20261019/e4_template_live）
- macos-mps：untested

完整欄位用 `python tools_src/gameart.py run show video/wan-vace/inpaint-reference` 查看。
