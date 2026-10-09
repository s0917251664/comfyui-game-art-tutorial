---
type: guide
status: current
---
# 圖片參數：什麼時候該動

旗標名稱、範圍與預設值以 `generate.py <task> --help` 為準（template 的 slot 以 `gameart.py run show <id>` 為準）。這頁只寫**什麼時候該用、用了代表什麼**。平常只補 [task 選擇](art-generation.md) 列出的必要資訊，不要逐一念出所有參數。

| 參數 | 什麼時候用、判斷 |
|---|---|
| `--seed` | 使用者要重現上次結果，或鎖住構圖只改小地方時才用；`layer_split` 沒有 |
| `--width`／`--height` | 前文與附件都沒有尺寸要求才問。須為 8 的倍數（FLUX.2 為 16 的倍數）；`icon_asset` 預設方形不用問；`inpaint` 類、`refine`、`upscale`、`flux2_edit` 不開放 |
| `--ip-weight` | 角色或風格參考的貼合強度。「太像參考圖」往下調、「一致性不夠」往上調；也留意**文字描述的特徵沒出現在結果裡**（任何與參考圖衝突的特徵都可能被蓋過），實際比對再決定，不假設某個數字通用 |
| `--pose-strength`／`--control-strength` | 姿勢或結構控制的嚴格程度：姿勢跑掉往上、動作太死板往下 |
| `--control-type` | 構圖控制來源，選擇見 [控制來源判斷](art/control-type-selection.md)。`guided_inpaint` 不給就不鎖結構 |
| `--control-backend union` | 只用於 `pose_only` 的 Union 評估，一般需求維持預設 |
| `--appearance-ref`／`--appearance-weight` | 使用者有現成參考圖、要風格質感像那張時才用；帶文字的參考圖權重從 0.3–0.4 試 |
| `--structure-ref` | `icon_asset` 結構或配置已有明確答案時才用，見 [結構範本](art/structure-ref.md) |
| `--denoise` | 保留原圖程度：`refine` 預設偏重畫、`inpaint` 與 `guided_inpaint` 預設完全重畫遮罩區、`upscale` 預設偏低（補細節不改構圖）。遮罩貼合度、羽化、denoise 要一起判斷（[遮罩](art/masking.md)） |
| `--scale` | `upscale` 的倍率，過高風險大（Mac 上 2048 級輸出曾在最後一步失敗，見 [已知限制](art/known-limitations.md)） |
| `--batch` | 要多看幾個版本才用，沒概念就建議 3 |
| `--lora`／`--lora-strength` | 使用者指名用某個已訓練好的 LoRA 才問；沒有現成檔案就不假裝有，只能用參考圖貼合或先去訓練。與 `--style` 同用的效果沒驗證過；觸發詞單獨使用不穩，要搭配幾個特徵詞 |
| `--remove-bg` | 使用者要透明背景才加；`icon_asset` 永遠去背 |
| `--style`、`--rating` | 使用者對 SDXL 美術風格有明確方向才問。`--rating` 只在 `anime`／`illustration` 有效，其餘組合直接被拒絕。FLUX.2 沒有這兩個旗標 |
| `--timeout` | CPU、batch、upscale 較慢才調高；逾時後先查狀態，不重送 |
| `--profile`、`--image-config` | 使用者明確要求換管線才用；不為避開錯誤自行換。設定檔不符合平台、不提供該 task、或快照過期時會在上傳前停止 |

## 刻意不開放的參數

SDXL 的 steps、CFG、sampler 與 FLUX.2 的 steps、CFG、scheduler 都鎖死，目的是穩定、可重複。使用者有這類需求時，回報這是目前限制，不要自己組 graph 繞過（[R2](rules/fixed-graphs.md)）；要改就走 [擴充協議](maintenance/extension-protocol.md)。

## 去背模型

正式的 `--remove-bg` 與 `icon_asset` 鎖定 `birefnet.safetensors`。2026-09-01 的 general／HR／HR-matting／dynamic A/B 沒有證明新變體可全面勝過 general。只有再次明確要求評估才跑 `gameart.py benchmark-birefnet`，不要把變體選擇暴露成日常旗標。

## 能力閘門

task 能不能跑由選定的模型設定檔與能力快照決定；送出前還會做安裝狀態 preflight（比對 `/object_info` 的 node 與模型選項），缺任何一項就在上傳前停止並列出缺什麼。FLUX.2 有獨立的 preflight，模型與 node 存在不等於硬體驗證通過。
