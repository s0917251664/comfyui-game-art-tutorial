# video/wan-vace/inpaint

**Wan2.1 VACE 影片局部重繪（遮罩內重畫、貼回原片）**（v0.1.1，technical_pass）

只重畫遮罩內（白色＝重畫），遮罩外貼回原片，並逐 byte 檢查遮罩外沒有改動。graph 由 `build_video_inpaint_wan` 產生，和 `generate.py video_inpaint` 相同；前後處理用 runner 的 `vace_work_area`、`paste_back`、`qa_outside_mask_unchanged` 步驟（見 [templates/README](../../../README.md)）。

- 必填：`source_video`（24 FPS、5～81 幀，本機讀取、不上傳）、`masks`（遮罩 PNG 資料夾或 `layers.zip`）、`prompt`
- 選填：`mode`（keep／replace）、`grow`、`pad`、`crop`、`feather`、`mask_object`、`strength`、`negative`、`seed`
- 由 pre 步驟決定：上傳的 `control_video`、`mask_video`，以及 graph 的寬、高、長度（`work_width`、`work_height`、`vace_length`）
- 固定參數：Wan2.1 VACE 1.3B、shift 5、20 步、cfg 6、uni_pc／simple、24 FPS；工作區最多 832×480 像素
- 輸出：VACE 原始輸出（`outputs/raw/`）、貼回結果（`composited/frames/*.png` 與 `composited/composited.mp4`，記在 `run.result.json` 的 `derived_outputs`）
- 平台：windows-cuda technical_pass（2026-10-08，規格與 2026-10-07 舊輸出相同，檔案 sha256 不同；本機證據 output/verify-20261008-3.4/live）、macos-mps untested

完整欄位用 `python tools_src/gameart.py run show video/wan-vace/inpaint` 查看。流程與參數說明見 [vfx-tools.md](../../../../docs/knowledge/video/vfx-tools.md)。
