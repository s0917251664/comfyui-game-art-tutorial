# 完整參數規格

`skills/comfyui-art-gen/SKILL.md` 指向這裡——邊界情況查這裡,不用每次都問。平常只問 SKILL.md「各 task 該問的固定問題」列出的項目就好,不要主動逐一念出下面所有參數嚇跑使用者。但如果使用者提出比較細的要求(例如「用跟上次一樣的種子」「圖再大一點」),對照這張表決定要不要加對應旗標。

| 參數 | 適用 task | 說明 | 什麼時候該用 |
|---|---|---|---|
| `--seed N` | 全部 | 固定隨機種子(整數),不給的話每次隨機 | 使用者要「重現上次結果」或「鎖住構圖只改小地方」時才用,平常不用主動問 |
| `--width` / `--height` | `concept`、`pose_only`、`style_lock`、`character_action` | 覆蓋預設解析度(預設值來自 `device_config.json`),數值須為 8 的倍數 | **這四個 task 都要主動問**,不是邊界情況——見 SKILL.md「各 task 該問的固定問題」開頭的提示 |
| `--width` / `--height` | `icon_asset` | 覆蓋預設解析度(**預設 1024x1024 正方形,固定值,不吃 `device_config.json`**) | 圖示類素材幾乎都是方形,**不用主動問**,只有使用者主動提出別的比例才用 |
| `--layer-name` | `layer_split` | 這一層的名稱,組輸出檔名前綴 | 每次都要問,已在 SKILL.md 固定問題裡 |
| `--negative "..."` | 全部 | 負向詞,不給用預設 `blurry, low quality, extra fingers, deformed, watermark` | 使用者主動提到不想要的東西時才問 |
| `--ip-weight N`(0~1,預設 0.8)| `style_lock`、`character_action` | 角色/風格參考圖的貼合強度,越高越像參考圖但可能犧牲文字描述的內容 | 使用者說「太像參考圖了」或「一致性不夠」時可以往下/往上調;**同樣要注意的訊號是「文字描述的具體特徵沒有出現在結果裡」**(不限於髮色,任何跟參考圖衝突的文字指定特徵都可能被蓋過)——實際比對產出後再判斷要不要調低重跑,不要假設某個數字對所有情境都通用 |
| `--pose-strength N`(0~10,預設 1.0)| `pose_only`、`character_action` | 姿勢控制的嚴格程度 | 使用者說「姿勢跑掉了」(調高)或「動作太死板」(調低)時可以調 |
| `--control-type canny\|pose\|depth`(預設 canny)| `pose_only`、`character_action` | 構圖控制來源,選擇判斷見 `reference/control-type-selection.md` | 見 SKILL.md「各 task 該問的固定問題」的判斷原則,通常不用主動問 |
| `--control-type canny\|pose\|depth`(選用,預設不鎖結構)| `guided_inpaint` | 遮罩範圍內要鎖住的結構類型:`pose`=關節骨架,`canny`/`depth`=輪廓/立體起伏 | 每次都要主動判斷要不要鎖、鎖哪種,見 SKILL.md `guided_inpaint` 固定問題第 4 點 |
| `--control-ref <path>`(預設用 `--image` 本身)| `guided_inpaint` | 結構引導來源圖,不給就從來源圖自己抽取結構 | 只有要套用「別張圖的姿勢/輪廓」時才問;沒給 `--control-type` 的話這個參數沒作用 |
| `--control-strength N`(0~10,預設 1.0)| `guided_inpaint` | 結構鎖定的嚴格程度 | 通常不用問,原則同 `--pose-strength` |
| `--appearance-ref <path>`(選用)| `guided_inpaint` | 外觀參考圖(例如美術自畫的材質/紋理圖),用 IPAdapter 決定遮罩範圍內的外觀,不給就純靠文字描述 | 使用者手上有現成參考圖時優先用這個,見 SKILL.md `guided_inpaint` 固定問題第 3 點 |
| `--appearance-weight N`(0~1,預設 0.8)| `guided_inpaint` | 外觀參考圖的貼合強度,原則同 `--ip-weight` | 通常不用問 |
| `--denoise N`(0~1)| `refine`(預設 0.6)、`inpaint`(預設 1.0)、`guided_inpaint`(預設 1.0)、`upscale`(預設 0.4)| 保留原圖程度,見 SKILL.md 各 task 說明 | 已經在固定問題裡問過 |
| `--scale N`(預設 2.0,最高建議 4)| `upscale` | 相對原圖的放大倍率 | 已經在固定問題裡問過 |
| `--batch N`(預設 1)| `concept`、`pose_only`、`style_lock`、`character_action` | 一次生成幾個版本比較 | 使用者要「多看幾個版本」時用,沒概念的話建議 3 |
| `--lora <檔名>`(models/loras/ 底下)+ `--lora-strength N`(0~1,預設 0.8)| `concept`、`pose_only`、`style_lock`、`character_action` | 套用已經訓練好的角色/風格 LoRA,比 IPAdapter 穩但需要事前訓練過(見 `教學.md` 第 8 章)| **使用者要指名用某個已經練好的 LoRA 才問**,平常不用主動提;沒有現成 LoRA 檔案就不要假裝有,如實說要嘛用 IPAdapter(`style_lock`/`character_action` 的 `--ip-weight`)要嘛先去訓練 |
| `--remove-bg` | 除 `inpaint`、`upscale`、`icon_asset`、`layer_split` 外全部 | 去背,輸出透明背景 PNG | 使用者要「透明背景」「去背」時加。**`icon_asset` 永遠去背,沒有這個旗標**——圖示素材預期本來就要疊到別的畫面上用,透明背景不是可選項 |
| `--output-dir <路徑>` | 全部 | 成品存放位置 | 固定帶 `local_config.json` 裡的 `output_dir`,除非使用者指定別的地方 |

## 目前沒有開放的參數(刻意鎖死,不要嘗試加旗標繞過)

`steps`(固定 25)、`cfg`(固定 7.0)、`sampler_name`/`scheduler`(固定 euler/normal)。這些是畫質/速度的細部調校參數,鎖死是為了「穩定產圖」——如果使用者對這幾個有明確需求(例如要更快出圖、更高品質),回報這是目前的已知限制,不要自己土法煉鋼組 workflow 繞過 `generate.py`。
