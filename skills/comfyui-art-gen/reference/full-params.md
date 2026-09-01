# 完整參數規格

`skills/comfyui-art-gen/SKILL.md` 指向這裡——邊界情況查這裡,不用每次都問。平常只問 SKILL.md「各 task 該問的固定問題」列出的項目就好,不要主動逐一念出下面所有參數嚇跑使用者。但如果使用者提出比較細的要求(例如「用跟上次一樣的種子」「圖再大一點」),對照這張表決定要不要加對應旗標。

`generate.py` 部署副本不會猜測 repository 的 `local_config.json`。每次執行都要明確提供 ComfyUI 位址（建議 `--comfy-url`），或明確指定含 `comfyui_url` 的 runtime config；URL 解析優先順序是 CLI → `COMFY_URL`/`COMFYUI_URL` → `--config`／`COMFY_CONFIG` 等明確指定的設定檔。`--timeout` 是 prompt 送達 ComfyUI 後輪詢生成結果的上限（秒），必須是有限正數；上傳、送出與下載各自另有不超過 30 秒的 HTTP request timeout，所以它不是整支 CLI 的 wall-clock 上限。逾時不代表伺服器已停止背景工作。

| 參數 | 適用 task | 說明 | 什麼時候該用 |
|---|---|---|---|
| `--seed N` | 除 `layer_split` 外全部 | 固定隨機種子(整數),不給的話每次隨機 | 使用者要「重現上次結果」或「鎖住構圖只改小地方」時才用,平常不用主動問 |
| `--width` / `--height` | `flux2_concept` | 覆蓋 FLUX.2 預設 1024x1024，兩者須為 16 的倍數 | 每次問尺寸／比例；RTX 4080 PoC 先以約 1MP 為主，不要未實測就拉高 |
| `--width` / `--height` | `concept`、`pose_only`、`style_lock`、`character_action` | 覆蓋預設解析度(預設值來自 `device_config.json`),數值須為 8 的倍數 | **這四個 task 都要主動問**,不是邊界情況——見 SKILL.md「各 task 該問的固定問題」開頭的提示 |
| `--width` / `--height` | `icon_asset` | 覆蓋預設解析度(**預設 1024x1024 正方形,固定值,不吃 `device_config.json`**) | 圖示類素材幾乎都是方形,**不用主動問**,只有使用者主動提出別的比例才用 |
| `--layer-name` | `layer_split` | 這一層的名稱,組輸出檔名前綴 | 每次都要問,已在 SKILL.md 固定問題裡 |
| `--structure-ref <路徑>` | `icon_asset` | 結構/顏色配置已有明確答案時用的範本圖(img2img + Canny ControlNet 雙重鎖,denoise/strength 都鎖死 0.85,不開放調整),細節見 `reference/structure-ref.md` | 圖示的結構描述用文字講不清楚、或 AI 一直畫不準確定的數量/配置時才用,平常不用主動問 |
| `--negative "..."` | 除 `layer_split`、`flux2_concept`、`flux2_edit` 外全部 | SDXL／影片既有 task 的負向詞；FLUX.2 PoC 刻意不開放 | 使用者主動提到不想要的東西時才問；FLUX.2 請直接把正向要求寫清楚，不要繞過 CLI |
| `--image <路徑>` | `flux2_edit` | 單張來源／參考圖；上傳後以官方 graph 正規化到約 1MP，輸出沿用正規化後比例 | 每次都要提供；目前不支援多參考圖、mask 或自訂 denoise |
| `--ip-weight N`(0~1,預設 0.8)| `style_lock`、`character_action` | 角色/風格參考圖的貼合強度,越高越像參考圖但可能犧牲文字描述的內容 | 使用者說「太像參考圖了」或「一致性不夠」時可以往下/往上調;**同樣要注意的訊號是「文字描述的具體特徵沒有出現在結果裡」**(不限於髮色,任何跟參考圖衝突的文字指定特徵都可能被蓋過)——實際比對產出後再判斷要不要調低重跑,不要假設某個數字對所有情境都通用 |
| `--pose-strength N`(0~1,預設 1.0)| `pose_only`、`character_action` | 姿勢控制的嚴格程度 | 使用者說「姿勢跑掉了」(調高)或「動作太死板」(調低)時可以調 |
| `--control-type canny\|pose\|depth`(預設 canny)| `pose_only`、`character_action` | 構圖控制來源,選擇判斷見 `reference/control-type-selection.md` | 見 SKILL.md「各 task 該問的固定問題」的判斷原則,通常不用主動問 |
| `--control-backend verified\|union`（預設 `verified`） | 只限 `pose_only` | `verified` 是三顆已驗證的專用 ControlNet；`union` 是 xinsir ProMax 的隔離 A/B，會明確設定 Union type | 美術一般需求不用問、維持預設。只有明確做 Union regression／評估時使用 `union`；它目前不代表其他 task 已支援或已升格主線 |
| `--control-type canny\|pose\|depth`(選用,預設不鎖結構)| `guided_inpaint` | 遮罩範圍內要鎖住的結構類型:`pose`=關節骨架,`canny`/`depth`=輪廓/立體起伏 | 每次都要主動判斷要不要鎖、鎖哪種,見 SKILL.md `guided_inpaint` 固定問題第 4 點 |
| `--control-ref <path>`(預設用 `--image` 本身)| `guided_inpaint` | 結構引導來源圖,不給就從來源圖自己抽取結構 | 只有要套用「別張圖的姿勢/輪廓」時才問;沒給 `--control-type` 的話這個參數沒作用 |
| `--control-strength N`(0~1,預設 1.0)| `guided_inpaint` | 結構鎖定的嚴格程度 | 通常不用問,原則同 `--pose-strength` |
| `--appearance-ref <path>`(選用)| `guided_inpaint` | 外觀參考圖(例如美術自畫的材質/紋理圖),用 IPAdapter 決定遮罩範圍內的外觀,不給就純靠文字描述 | 使用者手上有現成參考圖時優先用這個,見 SKILL.md `guided_inpaint` 固定問題第 3 點 |
| `--appearance-ref <path>` + `--appearance-weight N`(0~1,預設 0.8)(選用)| `icon_asset` | 外觀參考圖(例如使用者提供的一張成品圖),用 IPAdapter 讓畫面材質/質感偏向那張圖,不給就純靠文字描述 | 使用者手上有現成參考圖、想要「風格/質感像那張」時用;**參考圖如果帶文字,權重從低值(0.3~0.4)開始試,不要用預設 0.8**,細節見 `reference/known-limitations.md` |
| `--appearance-weight N`(0~1,預設 0.8)| `guided_inpaint` | 外觀參考圖的貼合強度,原則同 `--ip-weight` | 通常不用問 |
| `--denoise N`(0~1)| `refine`(預設 0.6)、`inpaint`(預設 1.0)、`guided_inpaint`(預設 1.0)、`upscale`(預設 0.4)| 保留原圖程度,見 SKILL.md 各 task 說明 | 已經在固定問題裡問過 |
| `--scale N`(預設 2.0,必須 >0 且 <=4)| `upscale` | 相對原圖的放大倍率 | 已經在固定問題裡問過 |
| `--batch N`(預設 1)| `concept`、`icon_asset`、`pose_only`、`style_lock`、`character_action` | 一次生成幾個版本比較 | 使用者要「多看幾個版本」時用,沒概念的話建議 3 |
| `--lora <檔名>`(models/loras/ 底下)+ `--lora-strength N`(0~1,預設 0.8)| `concept`、`icon_asset`、`pose_only`、`style_lock`、`character_action` | 套用已經訓練好的角色/風格 LoRA,比 IPAdapter 穩但需要事前訓練過(見 `教學.md` 第 8 章)| **使用者要指名用某個已經練好的 LoRA 才問**,平常不用主動提;沒有現成 LoRA 檔案就不要假裝有,如實說要嘛用 IPAdapter(`style_lock`/`character_action` 的 `--ip-weight`)要嘛先去訓練 |
| `--remove-bg` | `concept`、`pose_only`、`style_lock`、`character_action`、`refine` | 去背,輸出透明背景 PNG | 使用者要「透明背景」「去背」時加。**`icon_asset` 永遠去背,沒有這個旗標**——圖示素材預期本來就要疊到別的畫面上用,透明背景不是可選項 |

### BiRefNet 模型 benchmark 不是產圖參數

`tools_src/benchmark_birefnet.py` 是維護者用的回歸工具，不是 `generate.py` task，也不會出現在一般美術需求的固定問題中。2026-09-01 的 general／HR／HR-matting／dynamic A/B 沒有證明新變體可全面勝過 general，因此正式 `--remove-bg` 與 `icon_asset` 仍鎖定 `birefnet.safetensors`。只有再次明確要求評估模型時才執行 benchmark；不要把變體選擇暴露成日常 CLI 旗標。
| `--output-dir <路徑>` | 全部 | 成品存放位置 | 固定帶 `local_config.json` 裡的 `output_dir`,除非使用者指定別的地方 |
| `--comfy-url <URL>` | 全部 | ComfyUI HTTP base URL（例如 `http://127.0.0.1:8188`） | 優先從 `local_config.json` 的 `comfyui_url` 傳入；也可由 URL 環境變數提供，但不要依賴預設 port |
| `--config <路徑>` | 全部 | 明確指定含 `comfyui_url`（或相容的 `comfy_url`）的 JSON runtime config | 不想把 URL 寫在命令列時使用；不會自動尋找 repository 的 `local_config.json` |
| `--timeout N`（有限正數，預設 180 秒） | 全部 | prompt 送達後輪詢生成結果的上限；不含完整 CLI 的上傳與下載牆鐘時間 | CPU、`batch` 或 `upscale` 較慢時調高；逾時後先查狀態，不要直接重送同一任務 |
| `--style realistic\|illustration\|anime`(選配,不給用這台機器裝機時鎖定的預設 checkpoint)| 除 `layer_split`、`flux2_concept`、`flux2_edit` 外全部圖片 task | 換一顆 SDXL 風格底模；FLUX.2 是另一個 backend，parser 會拒絕這個旗標 | 使用者對 SDXL 產出的美術風格有明確方向時才問；其餘規則同原有 style 模型清單。**用 `anime` 時 prompt 開頭仍要手動加 `score_9, score_8_up, score_7_up`** |
| `--rating safe\|questionable\|explicit`(選配,不給就不加任何分級標籤,prompt 完全不變)| SDXL 圖片 task，且只在同時有 `--style anime` 或 `--style illustration` 時有效 | Pony/Illustrious 的內容分級標籤；FLUX.2 parser 不提供此旗標 | 使用者明確要求特定分級才加；`--style realistic`、沒給 `--style` 或 FLUX.2 task 都會拒絕 |

## tier 能力閘門

`device_config.json` 的 `tier` 會限制能安全使用的 graph，不只是選擇預設解析度。`sdxl_high`、`sdxl`、`sdxl_light` 可使用目前鎖定的 SDXL ControlNet、IPAdapter 與風格底模；`sd15` 目前只允許不依賴這些 SDXL add-on 的基礎路徑：

- `concept`、`refine`、一般 `inpaint`、`upscale` 可走基礎路徑。
- `icon_asset` 只有不帶 `--structure-ref` 與 `--appearance-ref` 時可走基礎路徑；任一參考圖都需要 SDXL。
- `pose_only`、`style_lock`、`character_action` 固定需要 SDXL；`guided_inpaint` 只在不帶 `--control-type` 與 `--appearance-ref` 時等同一般 inpaint。
- `--style` 三個候選底模也只支援 SDXL 家族。
- `flux2_concept` / `flux2_edit` 不使用這個 SDXL tier 契約；它們有獨立模型／Core node preflight，缺任一 FLUX.2 模型或節點時會在圖片上傳／queue 前停止。這不代表低 VRAM 機器自動支援，仍以該機 smoke test 為準。

不符合 tier 的組合會在參考圖上傳或建立 ComfyUI 佇列前被拒絕，避免先產生一個必然 shape mismatch 的工作。若要支援 SD1.5 的 ControlNet/IPAdapter，必須另配同家族模型並完成實機驗證，不能只替換 checkpoint 檔名。

## 目前沒有開放的參數(刻意鎖死,不要嘗試加旗標繞過)

SDXL 圖片 task 的 `steps` 固定 25、CFG 固定 7.0、sampler/scheduler 固定 euler/normal。`flux2_concept` 固定 distilled 4 steps、CFG 1.0、Euler + Flux2Scheduler；`flux2_edit` 固定 base 20 steps、CFG 5.0、Euler + Flux2Scheduler。這些是畫質/速度的細部調校參數,鎖死是為了「穩定產圖」——如果使用者對這幾個有明確需求,回報這是目前限制,不要自己組 workflow 繞過 `generate.py`。
