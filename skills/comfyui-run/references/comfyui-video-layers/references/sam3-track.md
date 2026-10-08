# SAM3 影片物件追蹤：固定 template（gameart.py run）

用途：指定影片裡的一個物件（例如角色手上的槌子），讓 SAM3 追蹤整支影片，產生逐幀遮罩（白色＝選取）。遮罩可以直接交給 `generate.py video_inpaint --masks`，或做為其他本機處理的選區。執行一律用 `gameart.py run`（[R2](../../../../../docs/knowledge/rules/fixed-graphs.md)）；這不是 `video_layers.py` 的一部分。

## Templates

| Template id | 起手方式 | 何時用 |
|---|---|---|
| [video/sam3/track-mask](../../../../../templates/video/sam3/track-mask/template.json) | 第 0 幀手繪遮罩（`SAM3_VideoTrack.initial_mask`），不給文字 | 美術要自己精確指定範圍（只換道具的一部分、避開手等） |
| [video/sam3/track-text](../../../../../templates/video/sam3/track-text/template.json) | 英文文字（`conditioning`） | 物件能用一個名詞清楚描述時，不必手繪 |

兩份 graph 都是：`LoadVideo` → `GetVideoComponents` → `SAM3_VideoTrack`（門檻 0.5、每幀偵測）→ `SAM3_TrackToMask`（全部物件）→ `MaskToImage` → `SaveImage`。參數沿用 SCAIL-2 template 的 SAM3 節點；遮罩版的 `max_objects` 設為 1，文字版設為 4。

| Slot | Template | 說明 |
|---|---|---|
| `source_video` | 兩份 | 要追蹤的影片（本機路徑，runner 負責上傳） |
| `seed_mask` | track-mask | 第 0 幀遮罩 PNG：白色＝物件，尺寸和影片相同；`mask_session.py` 的 `mask_editor.png` 可以直接用（graph 只讀紅色通道，不看 alpha） |
| `track_text` | track-text | 英文名詞片語，要具體 |

## 執行

以下 `<py>` 是 `local_config.json` 的 `python_exe`，在 repo 根目錄執行；路徑建議用絕對路徑。

1. 準備第 0 幀遮罩（遮罩版）：`vfx keyframes` 抽第 0 幀 → `mask_session.py` 讓美術手繪 → 得到 `mask_editor.png`。runner 的 pre 步驟會檢查遮罩尺寸和影片相同、不是全黑。
2. preflight：

   ```text
   <py> tools_src/gameart.py run video/sam3/track-mask --set source_video=<影片> --set seed_mask=<mask_editor.png> --preflight
   ```

   會核對 live `object_info` 有這份 graph 用到的每個 node class（track-mask 9 個、track-text 8 個；兩份共用 `LoadVideo`、`GetVideoComponents`、`CheckpointLoaderSimple`、`SAM3_VideoTrack`、`SAM3_TrackToMask`、`MaskToImage`、`SaveImage`，遮罩版另有 `LoadImage`、`ImageToMask`，文字版另有 `CLIPTextEncode`），以及 `sam3.1_multiplex_fp16.safetensors`（1,745,546,848 bytes）。實際檢查了哪些項目以 preflight 的輸出為準，不必自己對照清單。被擋下就停止，不下載、不換成相似檔名。文字版把 `--set seed_mask=...` 換成 `--set track_text=mallet`。
3. 實際執行：同一行拿掉 `--preflight`。結束碼 0＝完成且技術檢查通過；1＝失敗，看 `run.result.json` 的 `failure` 回報，不自動重跑；2＝參數錯誤。步驟細節、輸出資料夾內容、逾時處理與手動清理上傳檔見 [templates/README](../../../../../templates/README.md#使用)。

## 輸出與交接

- run 資料夾預設是 `output/runs/<日期>-video-sam3-track-mask-<run_id 前 8 碼>/`（template id 的 `/` 換成 `-`；文字版是 `video-sam3-track-text`），結束時 runner 會印出 `run.result.json` 的完整路徑。
- 遮罩在 run 資料夾的 `outputs/masks/`：逐幀 PNG，依檔名排序就是幀序。runner 的 post 步驟會核對張數等於來源幀數、尺寸和影片相同、R=G=B 灰階，並自動在 `keyframes/mask_preview.png` 產生原片疊遮罩的預覽條（選用步驟，失敗只會寫進 warnings）。
- `generate.py video_inpaint --masks <run>/outputs/masks` 與 `gameart.py vfx` 的遮罩參數，都接受這種 R=G=B 的 RGB 灰階 PNG；帶 alpha 的 RGBA 仍會被拒絕，因為它和圖片 inpaint 的反向 alpha 遮罩容易混淆。
- 交給下一步前，把 `mask_preview.png` 給美術確認範圍；需要其他取樣幀時，用 `gameart.py vfx mask-preview --video <來源> --masks <run>/outputs/masks --output <png>`。`run.result.json` 的 `content_review` 是 `pending`，美術審核者確認後才可以用 `gameart.py review accept|reject ... --by <決定的人>` 記錄。

## 實測（Skye 召槌 FINAL，1024²、56 幀，RTX 4080）

2026-10-07，runner 出現前直接呼叫 HTTP 送同一份 graph：

| 起手 | 結果 |
|---|---|
| 文字 `mallet` 或 `big hammer with gold frame` | 56 幀都抓到整把槌子，尾巴完全沒被誤選；約 9 秒 |
| 文字 `hammer` | 第 0–1 幀槌子橫放時只抓到握柄；名詞要具體 |
| 使用者手繪第 0 幀遮罩（只塗槌頭和槌柄） | 只追到塗的部分，握把、手、尾巴都沒被選進去；7.4 秒 |
| 包到尾巴的遮罩 | 整支片都一路追著尾巴：塗多少就追多少，不會自己修正 |
| 隨手框的方塊 | 前段把背景和角色都選進去，不可用 |

這些都是技術結果，遮罩範圍每次仍要美術看預覽確認。

2026-10-08 Windows 驗證：用 `gameart.py run video/sam3/track-mask`、手繪遮罩起手跑同一支 56 幀影片，GPU 執行 7.896 秒、全程 10.44 秒，輸出 56 張 1024² 遮罩，技術檢查全部通過。
