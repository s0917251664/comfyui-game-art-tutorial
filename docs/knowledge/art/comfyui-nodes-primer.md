---
type: reference
status: current
---
# ComfyUI 節點入門：修圖相關的零件與組合

給需要「看懂現有 template 為什麼這樣接」或「現有做不到、想提實驗方案」的人與 agent。**這頁不是產線能力清單**：第三節的組合都是實驗想法，尚未在本 repo 實測；要進產線得先實驗，再照 [R2](../rules/fixed-graphs.md) 第 3 點與 [擴充協議](../maintenance/extension-protocol.md) 做成 template。交付用生成不臨場改 graph。

## 一、本 repo 的修圖 graph 長什麼樣

三個局部／整圖修改 template 的節點很少（以 `templates/image/sdxl/*/graph.api.json` 為準）：

| template | 核心節點 | 重點 |
|---|---|---|
| `inpaint` | `LoadImage`（圖＋遮罩）→ `VAEEncodeForInpaint`（`grow_mask_by` 6）→ `KSampler` → `VAEDecode` | 遮罩內像素先被抹成中性灰再編碼，所以要用 `denoise 1.0` |
| `guided_inpaint*` | 同上，加 ControlNet（pose／canny／depth）與可選 IPAdapter 外觀參考 | 遮罩內「結構鎖住、外觀自由」 |
| `refine` | `LoadImage` → `VAEEncode` → `KSampler` → `VAEDecode` | 沒有遮罩，`denoise` 決定保留多少原圖 |

遮罩的方向：`LoadImage` 的 `MASK` 輸出是「1 − alpha」，所以 alpha=0 才是要改的區域（[遮罩](masking.md)）。

## 二、常用核心節點（ComfyUI 內建）

| 節點 | 做什麼 | 修圖時的用途 |
|---|---|---|
| `VAEEncodeForInpaint` | 把遮罩內像素抹成灰後編碼；有 `grow_mask_by` 外擴遮罩 | 傳統 inpaint 做法；搭配 `denoise 1.0` |
| `SetLatentNoiseMask` | 保留 latent 內容，只在遮罩內加雜訊重繪 | 想要「遮罩內保留原內容再微調」（`denoise` < 1）時的標準替代 |
| `InpaintModelConditioning` | 專門的 inpaint 條件（配合 inpaint 專用模型） | 使用 inpaint 專用 checkpoint 時 |
| `DifferentialDiffusion` | 讓遮罩灰階值直接當成逐像素的重繪強度，邊緣漸變 | 減少接縫，羽化遮罩才有真正意義 |
| `GrowMask`／`FeatherMask` | 外擴或縮小遮罩、羽化邊界 | 調整遮罩貼合度，取代手動重畫 |
| `ImageCompositeMasked` | 以遮罩把一張圖貼到另一張 | graph 內直接把生成結果合回原圖，保證遮罩外不變 |
| `ImagePadForOutpaint` | 往外加空白邊並產生對應遮罩 | 擴圖（outpaint）的起點 |
| `ControlNetApplyAdvanced` | 套用 ControlNet 並控制強度與起訖步數 | 結構鎖定；起訖步數限制可減少對外觀的壓抑 |
| `LoadImageMask`／`ImageToMask`／`MaskToImage` | 遮罩與圖片的互轉 | 遮罩預覽、反選前處理 |
| `InvertMask` | 遮罩反選 | 「保留人物、重畫背景」 |

## 三、實驗想法（未實測，須先實驗）

每項都是針對本 repo 目前的缺口，列出「狀況 → 組法 → 要驗證什麼」。實驗結果記到 `output/`，成功再走擴充協議。

1. **低 denoise 的局部微調**
   - 狀況：要在遮罩內保留原形、只改一點細節，現有 `inpaint` 做不到（denoise 一低就變灰）。
   - 組法：`LoadImage` → `VAEEncode` → `SetLatentNoiseMask` → `KSampler`（denoise 0.4–0.7）→ `VAEDecode`。
   - 要驗證：遮罩內輪廓保留度、遮罩外漂移、與現行 `inpaint` 的差異。
2. **漸變邊緣的羽化重繪**
   - 狀況：羽化遮罩在 `VAEEncodeForInpaint` 路線上沒有真正的漸變效果，接縫明顯。
   - 組法：在上述組法前加 `DifferentialDiffusion` 模型修補，遮罩用 `FeatherMask`。
   - 要驗證：接縫與光暈是否減少、遮罩灰階是否被保留（[遮罩](masking.md) 要求柔邊不可二值化）。
3. **graph 內直接合回原圖**
   - 狀況：目前靠事後 `edit composite` 讓遮罩外不變，多一步人工作業。
   - 組法：`VAEDecode` 之後接 `ImageCompositeMasked`（原圖為底、生成圖為來源、同一遮罩）。
   - 要驗證：遮罩外逐 byte 相同；alpha 方向要和 `LoadImage` 的反轉對齊，容易寫反。
4. **擴圖（outpaint）**
   - 狀況：目前沒有擴圖能力。
   - 組法：`ImagePadForOutpaint` → 局部重繪組法。
   - 要驗證：新增區域與原圖的接縫、重複圖樣、尺寸需為 8 的倍數。
5. **小物件在大圖上的高解析重繪（裁切後縫回）**
   - 狀況：大圖上的小遮罩，模型只拿到一小塊像素，細節差。
   - 組法：社群的 [ComfyUI-Inpaint-CropAndStitch](https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch) 把遮罩周圍裁成固定尺寸送去重繪，再縫回原位；[Acly/comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes) 提供另一套 inpaint 前處理與模型。
   - 要驗證：這些是第三方 custom node，**安裝前先問使用者**（[R2](../rules/fixed-graphs.md) 第 4 點）；縫回處接縫、與 `local_config.json` 路徑相容。

## 四、判斷是否值得做成新 template

- 現有 task 加 `edit composite` 加 [失敗診斷](edit-failure-diagnosis.md) 的對策試過仍不行。
- 同一類需求出現不只一次（會重複用才值得固定）。
- 實驗在乾淨輸出下重現至少一次，並由使用者確認。
- 之後照 [擴充協議](../maintenance/extension-protocol.md) 與 [新增能力清單](../maintenance/new-capability-checklist.md) 走，不直接搬實驗用的 graph。
