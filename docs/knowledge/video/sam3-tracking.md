---
type: guide
status: current
---
# SAM3 影片物件追蹤：判斷與實測

用途：指定影片裡的一個物件（例如角色手上的槌子），讓 SAM3 追蹤整支影片，產生逐幀遮罩（白色＝選取）。遮罩可交給 `generate.py video_inpaint --masks` 或 `gameart.py vfx`。執行一律用 `gameart.py run`（[R2](../rules/fixed-graphs.md)）；slot、起手方式與模型 pin 以 `gameart.py run show video/sam3/track-mask`（或 `track-text`）為準。

## 兩種起手方式怎麼選

| template | 起手 | 何時用 |
|---|---|---|
| `video/sam3/track-mask` | 第 0 幀手繪遮罩 | 美術要精確指定範圍（只換道具的一部分、避開手） |
| `video/sam3/track-text` | 英文名詞 | 物件能用一個名詞講清楚時，不必手繪 |

先 `run <id> --preflight` 再實際執行；被擋下就停止，不下載、不換相似檔名。遮罩版的第 0 幀遮罩可由 `vfx keyframes` 抽首幀、`mask-session` 手繪得到（尺寸要和影片相同，白色＝物件）。

## 判斷

- **遮罩範圍每次都要美術看預覽確認**（runner 會產生 `keyframes/mask_preview.png`；需要其他取樣幀用 `vfx mask-preview`）。技術檢查只核對張數、尺寸、灰階，不代表遮罩畫對。
- **塗多少就追多少**：手繪遮罩不會自己修正。只塗槌頭槌柄就只追到那兩塊；包到尾巴就一路追著尾巴。
- **文字要具體**：2026-10-07 實測 `hammer` 在槌子橫放的前兩幀只抓到握柄，`mallet` 或 `big hammer with gold frame` 整把都抓到。有人形怪人的鏡頭，`man` 會同時追蹤主角與怪人，改 `man with black hair` 才只追主角。送進 SCAIL-2 之前，可先用 `track-text` 以同一個詞追蹤，看遮罩是否只框到目標。
- **隨手框的方塊不可用**：前段會把背景和角色一起選進去。
- 遮罩給下一步（`video_inpaint`、`vfx`）時用 R=G=B 的灰階 PNG；帶 alpha 的 RGBA 會被拒絕，避免和圖片 inpaint 的反向 alpha 遮罩混淆。
- 被握住的物件，手會被一起重畫變形：局部重繪前要從物件遮罩扣掉手（見 [第 3–8 階段總結](../maintenance/restructure-summary-phase3-8.md) 的待開發）。
- `content_review` 一律 pending，使用者確認遮罩後才用 `gameart.py review` 記錄。

## SAM2 備援（`video_layers.py`）

SAM3 不可用時才用。流程：`vfx keyframes` 抽首幀、`mask-session` 手繪、`vfx segment-plan`（第 0 幀必填，大動作片中段要補修正幀）、`video_layers.py run`、`vfx unpack-masks`。這是 ComfyUI server 端的固定 node 加薄 client，不是 template；限制見 [Video Layers](layers.md)。

## 實測

- 2026-10-07（Skye 召槌 FINAL，1024²、56 幀、RTX 4080，runner 出現前直接送同一份 graph）：文字 `mallet` 約 9 秒、整把槌子 56 幀都抓到且尾巴沒被誤選；手繪遮罩 7.4 秒，只追到塗的部分。
- 2026-10-08 Windows：`gameart.py run video/sam3/track-mask`、手繪遮罩起手跑同一支影片，GPU 7.9 秒、全程 10.4 秒，輸出 56 張遮罩，技術檢查全部通過。

這些都是技術結果，不是遮罩品質保證。
