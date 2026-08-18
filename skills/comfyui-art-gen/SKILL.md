# ComfyUI 遊戲美術產圖

給任何操作這個 repo 的 agent(Claude Code、Codex、Gemini CLI 等)使用的技能說明。

## 何時使用

當使用者用自然語言要求產生遊戲美術素材(概念圖、角色動作圖/姿勢圖、構圖控制、角色一致性、局部修改/局部重繪、圖生圖精緻化/材質變體、去背)時使用。

**不要用於**:
- UI/介面圖 → 已有 Claude Code + Figma MCP + design system 的流程,不屬於這裡
- Logo、中文字排版 → 本機模型的先天弱項,需要另外走雲端 API 路線(GPT-Image),目前尚未設定 Comfy 帳號,如實告知使用者這塊做不到,不要硬做

## 核心原則

把使用者的自然語言需求,轉成呼叫 `generate.py` 的結構化參數。目的是**穩定產圖**,不是即興生成——每個 task 對應鎖死大部分參數的 ComfyUI workflow,只有明確列出的欄位可調。

**先問清楚必要資訊,再執行一次;不要開放式閒聊,不要重複生成瞎猜。** 每個 task 只問下面列出的固定問題,使用者答不出來的欄位就用預設值,不要無限追問——這是為了減少 token 浪費跟避免「用自然語言盲猜結果」的狀況。

**產出後自己驗收,不要只看有沒有報錯。** 腳本執行成功、檔案格式/尺寸正確,不代表內容真的符合使用者要求——實際打開圖片檢查使用者提出的具體特徵(例如指定的顏色、動作、構圖是否真的出現)。不符合時,先判斷是哪個參數的貼合強度蓋過了文字描述(常見是 `--ip-weight`、`--pose-strength`、`--denoise` 這類「參考圖 vs. 文字描述」的拉鋸參數),調整後重新生成一次再比對,不要把單次結果沒達標的參數硬算過關,也不要因為之前某次測試用某個數字有效就把那個數字寫死當成通用預設。

## 環境

**執行任何 task 之前,先讀 repo 根目錄的 `local_config.json`**,取得這台機器實際的路徑:

```json
{
  "comfyui_path": "...",       // ComfyUI 安裝路徑
  "python_exe": "...",         // 要用這個 python.exe 執行,不要用系統的 python
  "generate_script": "...",    // generate.py 的實際路徑
  "comfyui_url": "http://127.0.0.1:xxxx",
  "start_script": "...",       // 啟動 ComfyUI 伺服器用
  "output_dir": "..."          // 固定要存圖回去的資料夾(repo 根目錄的 output/)
}
```

- **這份檔案不進版控,每台機器內容不一樣**——不要把裡面的實際路徑寫死抄進任何會進版控的文件(包括這份 SKILL.md 自己)
- 如果 `local_config.json` 不存在:代表這台機器還沒裝好,照 `skills/comfyui-install/SKILL.md` 的流程完成安裝,它會產生這份設定檔
- 執行方式:`<python_exe> <generate_script> <task> [options]`
- 前提:ComfyUI 伺服器要在 `<comfyui_url>` 跑著(沒開的話先執行 `<start_script>`)
- 原始碼版本控管在這個 repo 的 `tools_src/generate.py`,`<generate_script>` 只是部署後的執行副本
- **產出圖片一律要存回 `<output_dir>`(repo 裡的 `output/`),不要讓使用者需要跑去 ComfyUI 安裝目錄找圖**:每次呼叫都加上 `--output-dir <output_dir>`。腳本執行完會印出實際路徑,直接把這個路徑告訴使用者。`generate.py` 本身部署在 ComfyUI 安裝目錄底下只是執行環境,使用者體感上應該完全感覺不到 ComfyUI 這個東西的存在
- **換到別的設備時**:照 `skills/comfyui-install/SKILL.md` 的流程重新走一次(或至少重跑 `tools_src/detect_device.py`),會依 GPU/VRAM 自動產生 `device_config.json`,`generate.py` 會自動讀這份設定決定 checkpoint/解析度,不用手動改程式碼

## 任務判斷(先分類,再決定要問什麼)

| 使用者說的像... | task | 判斷依據 |
|---|---|---|
| 「畫一個...」「幫我生一張概念圖/場景/道具」,沒有提到任何參考圖 | `concept` | 沒有輸入圖 |
| 「照這個姿勢/線稿畫」,但沒有指定要哪個角色(全新角色、或角色不重要) | `pose_only` | 只有姿勢/線稿參考圖,不需要角色一致性 |
| 「這個角色/風格套到新場景」「姿勢隨意,但要是這個角色」 | `style_lock` | 只有角色/風格參考圖,不需要指定姿勢 |
| 「這個角色換個姿勢/動作」「照這個線稿套進這個角色」 | `character_action` | 需要角色參考圖 **+** 姿勢/線稿參考圖(兩者都要) |
| 「幫我把這張草稿上色/精緻化」「同一個造型換材質/換顏色」 | `refine` | 有來源圖,想保留大致構圖但改細節/材質/顏色 |
| 「這裡崩壞了幫我修」「只改這個區域」「局部調整」 | `inpaint` | 有來源圖 + 需要指定修改區域 |
| 「這張圖放大」「解析度不夠」「細節加銳利一點」「要交件/要印出來所以要更高解析度」 | `upscale` | 已經有確定要用的成品圖,想要更高解析度 + 補細節,不是想重新構圖 |
| 「去背」「透明背景」 | 加 `--remove-bg` 旗標,可疊加在 `concept`/`pose_only`/`style_lock`/`character_action`/`refine` 之後 | — |
| 「多出幾個版本比較」「一次看幾種可能性」 | 加 `--batch N` 旗標,只有 `concept`/`pose_only`/`style_lock`/`character_action` 支援(探索型任務才需要);問使用者要幾張,沒概念就用 3 | — |

## 各 task 該問的固定問題

> **這四個 task(concept / pose_only / style_lock / character_action)都要多問一題:圖片尺寸/比例有沒有要求?** 例如直式角色圖、橫式場景圖、正方形圖示、遊戲引擎規定的固定尺寸。使用者沒概念或沒特別要求就用預設值(不用主動報數字出來),有要求就用 `--width`/`--height` 帶入(數值必須是 8 的倍數,常見值:1024x1024 方形、832x1216 直式、1216x832 橫式)。這題容易被忽略但常常很重要——遊戲素材有固定尺寸規格是常態,產出來尺寸不對通常等於要重做。

### concept(概念圖)
1. 想畫什麼(轉成英文 prompt,SDXL 對英文 prompt 理解較準)
2. 有沒有想避開的東西(負向詞,沒有就用預設 `blurry, low quality, extra fingers, deformed, watermark`)
3. 需不需要透明背景(去背)
4. 尺寸/比例有沒有要求(見上面提示)

### pose_only(單獨姿勢/構圖控制)
1. 想要的畫面文字描述
2. **一定要跟使用者要姿勢/線稿參考圖的檔案路徑**(照片、簡筆骨架圖、線稿都可以)
3. 尺寸/比例有沒有要求(見上面提示)
4. 姿勢的精準度(--pose-strength,預設 1.0)通常不用問
5. 構圖控制來源(--control-type,預設 canny)通常不用問——如果使用者提供的是「一張人物照片,想照這個人的動作姿勢」,建議用 `pose`(骨架抽取,忽略背景/衣服細節,只鎖姿勢);如果是「線稿/簡筆畫」就維持預設 `canny`;如果要控制的是空間深度/前後景關係而不是姿勢,用 `depth`
6. 文字描述的動作要跟姿勢參考圖裡實際的動作一致——兩者衝突時(例如圖是動態格鬥姿勢,文字卻寫靜態站姿)容易生出構圖矛盾的結果,寫 prompt 前先看一眼參考圖在做什麼

### style_lock(單獨角色/風格一致性)
1. 想要的新場景/情境文字描述
2. **一定要跟使用者要角色/風格參考圖的檔案路徑**(沒有的話無法保持一致性,不要憑空生成後假裝有一致性)
3. 尺寸/比例有沒有要求(見上面提示)
4. 貼合強度(--ip-weight,預設 0.8)通常不用問,除非使用者主動提

### character_action(角色動作圖,姿勢 + 角色都要鎖)
1. 想要的動作/姿勢文字描述
2. **一定要跟使用者要角色參考圖的檔案路徑**
3. **一定要跟使用者要姿勢/線稿參考圖的檔案路徑**——如果使用者沒有,可以建議「拍一張自己擺拍的照片,或畫一個簡單火柴人也行」
4. 尺寸/比例有沒有要求(見上面提示)
5. 角色貼合強度(--ip-weight,預設 0.8)、姿勢精準度(--pose-strength,預設 1.0)通常不用問
6. 構圖控制來源(--control-type,預設 canny)通常不用問,判斷原則同 `pose_only`——姿勢參考是人物照片就建議 `pose`
7. 文字描述的動作要跟姿勢參考圖裡實際的動作一致,原則同 `pose_only` 第 6 點

### refine(圖生圖:精緻化/材質變體)
1. 來源圖路徑
2. 想要的新內容/材質/顏色描述
3. 保留原圖程度(--denoise):0.3~0.4 大致保留原色只上色/微調;0.6~0.7(預設)細節大幅改變;0.9+ 幾乎重畫。使用者沒概念的話用預設 0.6,並提醒「如果變化太小可以再調高」

### inpaint(局部調整)
1. 來源圖路徑
2. **一定要請使用者提供遮罩圖**,最簡單的方式是明確說「請用 ComfyUI 介面的 MaskEditor 塗好存成一張圖給我」(MaskEditor 存出來的格式一定對,不用管底層細節)——不要自己用文字描述去猜測要修改的區域,座標/範圍必須來自使用者提供的實際遮罩檔案
3. 想要新內容的描述
4. 保留原圖程度(denoise,預設 1.0 = 完全重畫遮罩區域,想保留更多原圖細節可以問要不要調低)

> **遮罩檔案格式是個真實陷阱,已實測踩過一次:** `generate.py` 背後的 ComfyUI `LoadImage` 節點,`MASK` 輸出的邏輯是「**1.0 − 圖片的 alpha 通道**」,而且**圖片完全沒有 alpha 通道時,會直接回傳一個空白遮罩(等於什麼都不選、什麼都不會被重畫)**。也就是說:
> - 要重畫的區域 = 那個像素的 **alpha 要是透明(0)**
> - 要保留的區域 = alpha 要不透明(255)
> - **不是**一般直覺以為的「存一張白色區域代表要重畫的灰階/RGB 圖」——如果遮罩圖沒有 alpha 通道(例如存成 RGB、或用 `.convert('RGB')` 處理過),不會報錯,但整個遮罩會靜默失效,產出看起來幾乎和原圖一樣,容易誤以為「有跑但沒什麼變化」而不是「根本沒吃到遮罩」
> - 如果是 agent 自己用程式產生遮罩圖(不是透過 MaskEditor),**一定要存成帶 alpha 通道的 RGBA 圖片,要重畫的區域 alpha=0,其餘 alpha=255**,存完最好實際跑一次確認遮罩區域真的有變化,不要只看有沒有報錯就當作成功

### upscale(放大精修,不是重新構圖)
1. 來源圖路徑(已經確定要用的成品圖)
2. **盡量沿用當初生成這張圖時用的 prompt**——二次取樣需要 prompt 才能補細節,風格才會跟原圖一致,問使用者「記得原本的描述嗎」,真的想不起來就用畫面內容重新描述一次
3. 要放大幾倍(--scale,預設 2,最高建議到 4)
4. 補細節強度(--denoise,預設 0.4)通常不用問,除非使用者說「細節補太多跑掉了」(調低)或「還是不夠銳利」(調高)

## 執行

確定好參數後,直接呼叫,不用再跟使用者確認一次(前面問過的就是確認過了)。**每一次呼叫都要加 `--output-dir <local_config.json 裡的 output_dir>`**,讓成品留在這個 repo 裡:

```
concept:
  <python_exe> <generate_script> concept --prompt "..." [--negative "..."] [--width W --height H] [--batch 3] [--lora <檔名> --lora-strength 0.8] [--remove-bg] --output-dir <output_dir>

pose_only:
  <python_exe> <generate_script> pose_only --prompt "..." --pose-ref <path> [--pose-strength 1.0] [--control-type canny|pose|depth] [--width W --height H] [--batch 3] [--lora <檔名> --lora-strength 0.8] [--remove-bg] --output-dir <output_dir>

style_lock:
  <python_exe> <generate_script> style_lock --prompt "..." --character-ref <path> [--ip-weight 0.8] [--width W --height H] [--batch 3] [--lora <檔名> --lora-strength 0.8] [--remove-bg] --output-dir <output_dir>

character_action:
  <python_exe> <generate_script> character_action --prompt "..." --character-ref <path> --pose-ref <path> [--control-type canny|pose|depth] [--width W --height H] [--batch 3] [--lora <檔名> --lora-strength 0.8] [--remove-bg] --output-dir <output_dir>

refine:
  <python_exe> <generate_script> refine --prompt "..." --image <path> [--denoise 0.6] [--remove-bg] --output-dir <output_dir>

inpaint:
  <python_exe> <generate_script> inpaint --prompt "..." --image <path> --mask <path> [--denoise 0.9] --output-dir <output_dir>

upscale:
  <python_exe> <generate_script> upscale --prompt "..." --image <path> [--scale 2.0] [--denoise 0.4] --output-dir <output_dir>
```

(`<python_exe>`、`<generate_script>`、`<output_dir>` 都從 `local_config.json` 讀,不要寫死實際路徑)

執行完把腳本印出的圖片路徑告訴使用者,不用額外描述生成過程。如果使用者明確要求存到別的資料夾,才把 `--output-dir` 換成使用者指定的路徑。

## 完整參數規格(邊界情況查這裡,不用每次都問)

平常只問「各 task 該問的固定問題」列出的項目就好,不要主動逐一念出下面所有參數嚇跑使用者。但如果使用者提出比較細的要求(例如「用跟上次一樣的種子」「圖再大一點」),對照這張表決定要不要加對應旗標。

| 參數 | 適用 task | 說明 | 什麼時候該用 |
|---|---|---|---|
| `--seed N` | 全部 | 固定隨機種子(整數),不給的話每次隨機 | 使用者要「重現上次結果」或「鎖住構圖只改小地方」時才用,平常不用主動問 |
| `--width` / `--height` | `concept`、`pose_only`、`style_lock`、`character_action` | 覆蓋預設解析度(預設值來自 `device_config.json`),數值須為 8 的倍數 | **這四個 task 都要主動問**,不是邊界情況——見「各 task 該問的固定問題」開頭的提示 |
| `--negative "..."` | 全部 | 負向詞,不給用預設 `blurry, low quality, extra fingers, deformed, watermark` | 使用者主動提到不想要的東西時才問 |
| `--ip-weight N`(0~1,預設 0.8)| `style_lock`、`character_action` | 角色/風格參考圖的貼合強度,越高越像參考圖但可能犧牲文字描述的內容 | 使用者說「太像參考圖了」或「一致性不夠」時可以往下/往上調;**同樣要注意的訊號是「文字描述的具體特徵沒有出現在結果裡」**(不限於髮色,任何跟參考圖衝突的文字指定特徵都可能被蓋過)——實際比對產出後再判斷要不要調低重跑,不要假設某個數字對所有情境都通用 |
| `--pose-strength N`(0~10,預設 1.0)| `pose_only`、`character_action` | 姿勢控制的嚴格程度 | 使用者說「姿勢跑掉了」(調高)或「動作太死板」(調低)時可以調 |
| `--control-type canny\|pose\|depth`(預設 canny)| `pose_only`、`character_action` | 構圖控制來源:`canny`=線稿邊緣,`pose`=骨架姿勢(OpenPose,適合拿人物照片鎖動作、忽略衣服/背景),`depth`=深度圖(適合鎖空間前後景關係) | 見「各 task 該問的固定問題」的判斷原則,通常不用主動問 |
| `--denoise N`(0~1)| `refine`(預設 0.6)、`inpaint`(預設 1.0)、`upscale`(預設 0.4)| 保留原圖程度,見上面各 task 說明 | 已經在固定問題裡問過 |
| `--scale N`(預設 2.0,最高建議 4)| `upscale` | 相對原圖的放大倍率 | 已經在固定問題裡問過 |
| `--batch N`(預設 1)| `concept`、`pose_only`、`style_lock`、`character_action` | 一次生成幾個版本比較 | 使用者要「多看幾個版本」時用,沒概念的話建議 3 |
| `--lora <檔名>`(models/loras/ 底下)+ `--lora-strength N`(0~1,預設 0.8)| `concept`、`pose_only`、`style_lock`、`character_action` | 套用已經訓練好的角色/風格 LoRA,比 IPAdapter 穩但需要事前訓練過(見 `教學.md` 第 8 章)| **使用者要指名用某個已經練好的 LoRA 才問**,平常不用主動提;沒有現成 LoRA 檔案就不要假裝有,如實說要嘛用 IPAdapter(`style_lock`/`character_action` 的 `--ip-weight`)要嘛先去訓練 |
| `--remove-bg` | 除 `inpaint`、`upscale` 外全部 | 去背,輸出透明背景 PNG | 使用者要「透明背景」「去背」時加 |
| `--output-dir <路徑>` | 全部 | 成品存放位置 | 固定帶 `local_config.json` 裡的 `output_dir`,除非使用者指定別的地方 |

**目前沒有開放的參數(刻意鎖死,不要嘗試加旗標繞過)**:`steps`(固定 25)、`cfg`(固定 7.0)、`sampler_name`/`scheduler`(固定 euler/normal)。這些是畫質/速度的細部調校參數,鎖死是為了「穩定產圖」——如果使用者對這幾個有明確需求(例如要更快出圖、更高品質),回報這是目前的已知限制,不要自己土法煉鋼組 workflow 繞過 `generate.py`。

## 已知限制(如實告知使用者,不要假裝能做到)

- 只有本機 SDXL 一條路線,Logo/中文字排版品質不會好
- **只在 SDXL 家族機器(`sdxl_high`/`sdxl`/`sdxl_light` tier)上驗證過。** 如果 `device_config.json` 的 `tier` 是 `sd15`(低 VRAM 機器,底模會自動換成 SD1.5 系列),`character_action`/`style_lock`/`pose_only`/`character_action` 這些用到 ControlNet 或 IPAdapter 的 task **目前會壞掉**——`generate.py` 裡這幾個模型檔名是寫死指向 SDXL 版本,沒有跟著 tier 換,直接跑會 shape mismatch。遇到 `sd15` tier 的機器,如實告知使用者這條路線還沒補上,不要假裝能動
- 需要角色/姿勢一致性的 task,沒有對應參考圖就不要硬做,結果不會有一致性
- `refine` 的顏色/材質改變幅度受 `--denoise` 影響很大,denoise 太低時強烈的顏色指令可能蓋不過原圖(這是參數特性,不是 bug,提醒使用者可以調高再試)
- **`--lora` 的觸發詞可靠度取決於訓練方式,不要假設「打觸發詞就一定觸發」。** 這個專案的訓練流程用 SDXL 官方建議的 `--network_train_unet_only`(只練 U-Net),實測發現單獨丟觸發詞、不搭配任何特徵描述詞時,效果不穩定;請使用者生圖時觸發詞旁邊還是搭配幾個關鍵特徵詞一起下,不要只丟一個詞賭它記得(細節見 `教學.md` 第 8 章)
