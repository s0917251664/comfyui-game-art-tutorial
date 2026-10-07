# SAM3 影片物件追蹤：固定 ComfyUI API graph

用途：指定影片裡的一個物件（例如角色手上的槌子），讓 SAM3 追蹤整支影片，下載逐幀遮罩（白色＝選取）。遮罩可以直接交給 `generate.py video_inpaint --masks`，或做為其他本機處理的選區。這是直接 HTTP 呼叫的固定 graph，沒有 Python 入口，也不是 `video_layers.py` 的一部分。

## 素材

| Template | 起手方式 | 何時用 |
|---|---|---|
| [track-mask](../../../templates/video/sam3/track-mask/graph.api.json)（`templates/video/sam3/track-mask/`） | 第 0 幀手繪遮罩（`SAM3_VideoTrack.initial_mask`），不給文字 | 美術要自己精確指定範圍（只換道具的一部分、避開手等） |
| [track-text](../../../templates/video/sam3/track-text/graph.api.json)（`templates/video/sam3/track-text/`） | 英文文字（`conditioning`） | 物件能用一個名詞清楚描述時，不必手繪 |

兩份 graph 都是：`LoadVideo` → `GetVideoComponents` → `SAM3_VideoTrack`（門檻 0.5、每幀偵測）→ `SAM3_TrackToMask`（全部物件）→ `MaskToImage` → `SaveImage`。參數沿用 [SCAIL-2 範本](../../../templates/video/wan-animate/scail2/graph.api.json)的 SAM3 節點；遮罩版的 `max_objects` 設為 1，文字版設為 4。

## 動態欄位

只可以改這些欄位，其他照 template：

| 欄位 | Node | 說明 |
|---|---|---|
| `__SOURCE_VIDEO__` | 1 `file` | 上傳後的 server path（`subfolder/name`） |
| `__SEED_MASK_IMAGE__`（僅遮罩版） | 10 `image` | 第 0 幀遮罩 PNG 上傳後的 path。白色＝物件，尺寸和影片相同；`mask_session.py` 的 `mask_editor.png` 可以直接用（graph 只讀紅色通道，不看 alpha） |
| `__TRACK_TEXT__`（僅文字版） | 31 `text` | 英文名詞片語 |
| `__OUTPUT_PREFIX__` | 36 `filename_prefix` | 唯一前綴，例如 `sam3_track/<uuid>` |

## Preflight

queue 前用 `GET /object_info` 確認以下節點都存在：`LoadVideo`、`GetVideoComponents`、`LoadImage`、`ImageToMask`、`CheckpointLoaderSimple`、`CLIPTextEncode`、`SAM3_VideoTrack`、`SAM3_TrackToMask`、`MaskToImage`、`SaveImage`。另外確認 `CheckpointLoaderSimple` 的選項裡有 `sam3.1_multiplex_fp16.safetensors`（1,745,546,848 bytes，來源和 hash 見 [SCAIL-2 reference](../../comfyui-wan-animate/references/scail2.md)）。缺任何一項就停止，不下載、不換成相似檔名。

上傳、queue、輪詢 `/history/{prompt_id}`、只以 success／`completed=true` 判定完成、逾時處理、下載與證據保存，都照 [固定 API graph 契約](../../comfyui-wan-animate/references/comfyui-api.md)。queue 前要掃描整份 graph，確認沒有剩下任何 `__` 開頭的占位欄位。

## 輸出與交接

- 輸出：`SaveImage` 逐幀 PNG，數量應等於來源影片幀數。檔案是 RGB 灰階（R=G=B），白色＝選取。依檔名排序就是幀序。
- `generate.py video_inpaint --masks <下載資料夾>` 與 `gameart.py vfx` 的遮罩參數，都接受這種 R=G=B 的 RGB 灰階 PNG；帶 alpha 的 RGBA 仍會被拒絕，因為它和圖片 inpaint 的反向 alpha 遮罩容易混淆。
- 交給下一步前，先用 `gameart.py vfx mask-preview --video <來源> --masks <下載資料夾> --output <png>` 產生疊圖，給美術確認範圍。

## 2026-10-07 實測（Skye 召槌 FINAL，1024²、56 幀，RTX 4080）

| 起手 | 結果 |
|---|---|
| 文字 `mallet` 或 `big hammer with gold frame` | 56 幀都抓到整把槌子，尾巴完全沒被誤選；約 9 秒 |
| 文字 `hammer` | 第 0–1 幀槌子橫放時只抓到握柄；名詞要具體 |
| 使用者手繪第 0 幀遮罩（只塗槌頭和槌柄） | 只追到塗的部分，握把、手、尾巴都沒被選進去；7.4 秒 |
| 包到尾巴的遮罩 | 整支片都一路追著尾巴：塗多少就追多少，不會自己修正 |
| 隨手框的方塊 | 前段把背景和角色都選進去，不可用 |

這些都是技術結果，遮罩範圍每次仍要美術看預覽確認。
