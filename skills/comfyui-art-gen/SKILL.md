# ComfyUI 遊戲美術產圖

給任何操作這個 repo 的 agent(Claude Code、Codex、Gemini CLI 等)使用的技能說明。

## 何時使用

當使用者用自然語言要求產生遊戲美術素材(概念圖、角色動作圖/姿勢圖、構圖控制、角色一致性、局部修改/局部重繪、圖生圖精緻化/材質變體、去背)時使用。

**不要用於**:
- 整個 UI 畫面/版面配置(多元件同時排版、要考慮版面與 Design Token)→ 已有 Claude Code + Figma MCP + design system 的流程,不屬於這裡
- Logo、中文字排版 → 本機模型的先天弱項,需要另外走雲端 API 路線(GPT-Image),目前尚未設定 Comfy 帳號,如實告知使用者這塊做不到,不要硬做
- 要影片/讓靜幀動起來/過場動畫/這個角色去做別的動作(影片) → `skills/comfyui-video-gen/SKILL.md`,不要拿這裡的圖片 task 假裝會產影片。靜態 `style_lock` 不能拿來產影片;影片身份鎖是 `character_video`

**可以用於**(容易誤判成「UI 圖」而不敢做的邊界情況):單一 UI 小圖示/symbol/物件素材(按鈕圖示、道具圖示、轉盤這類複合元件裡的單一構件)本質上跟遊戲道具素材沒有差別,屬於 `icon_asset` task,不算「整個 UI 畫面」。

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
- 如果 `local_config.json` 不存在:代表這台機器還沒裝好,照 `skills/comfyui-install/SKILL.md` 的流程完成安裝,它會產生這份設定檔；沒有這份檔案就不要假裝可以做實機產圖
- 執行方式:`<python_exe> <generate_script> <task> [options]`
- 前提:ComfyUI 伺服器要在 `<comfyui_url>` 跑著(沒開的話先執行 `<start_script>`)
- **URL 要明確傳入**:部署在 ComfyUI 目錄裡的 `generate.py` 不會依相對路徑自動尋找 repository 的 `local_config.json`。優先用 `--comfy-url <comfyui_url>`；也可用 `--config <local_config.json>`，或設定 `COMFY_URL`/`COMFYUI_URL`。解析優先順序是 CLI URL → URL 環境變數 → 明確指定的 runtime config(`--config` 或 `COMFY_CONFIG`/`COMFYUI_CONFIG`/`COMFY_CONFIG_PATH`)；沒有來源就先報錯，不要送到預設 port 猜測。
- **等待上限要依任務調整**:共同選項 `--timeout <秒數>` 控制 prompt 送達 ComfyUI 後輪詢生成結果的上限，必須是有限正數；上傳、送出與下載各自另有不超過 30 秒的 HTTP request timeout，所以它不是整支 CLI 的 wall-clock 上限。CPU、batch 或 upscale 需要較久時才提高。它不會改變 `steps`，也不代表 ComfyUI 在逾時後停止背景工作，逾時後不要未確認狀態就重複送出同一任務。
- 原始碼版本控管在這個 repo 的 `tools_src/generate.py`,`<generate_script>` 只是部署後的執行副本
- **產出圖片一律要存回 `<output_dir>`(repo 裡的 `output/`),不要讓使用者需要跑去 ComfyUI 安裝目錄找圖**:每次呼叫都加上 `--output-dir <output_dir>`。腳本執行完會印出實際路徑,直接把這個路徑告訴使用者。`generate.py` 本身部署在 ComfyUI 安裝目錄底下只是執行環境,使用者體感上應該完全感覺不到 ComfyUI 這個東西的存在
- **換到別的設備時**:照 `skills/comfyui-install/SKILL.md` 的流程重新走一次(或至少重跑 `tools_src/detect_device.py`),會依 GPU/VRAM 自動產生 `device_config.json`,`generate.py` 會自動讀這份設定決定 checkpoint/解析度,不用手動改程式碼

### 目前支援的 tier

`device_config.json` 的 tier 是能力契約，不只是解析度建議。SDXL 家族(`sdxl_high`、`sdxl`、`sdxl_light`)目前是 ControlNet/IPAdapter/風格底模的實測路線；`sd15` 只能走不依賴 SDXL add-on 的基礎路徑。`pose_only`、`style_lock`、`character_action` 永遠需要 SDXL；`icon_asset` 只有不帶 `--structure-ref`/`--appearance-ref` 時可走基礎路徑；`guided_inpaint` 只有不帶 ControlNet 與外觀參考圖時可走一般 inpaint。`--style` 的 `realistic`/`illustration`/`anime` 以及任何 SDXL ControlNet/IPAdapter 參數在 `sd15` 上會在上傳前被拒絕。這些不是替 SD1.5 選一套模型就會自動修好，必須另行匹配並實機驗證。

## 任務判斷(先分類,再決定要問什麼)

| 使用者說的像... | task | 判斷依據 |
|---|---|---|
| 「畫一個...」「幫我生一張概念圖/場景/道具」,沒有提到任何參考圖 | `concept` | 沒有輸入圖 |
| 「幫我做一個XX的圖示/symbol/按鈕圖案」「單一遊戲小物件,要疊加到別的畫面上用」 | `icon_asset` | 訴求是單一、獨立、預期會疊到其他畫面上的小型元素,不是完整場景/整個 UI 畫面版面 |
| 「照這個姿勢/線稿畫」,但沒有指定要哪個角色(全新角色、或角色不重要) | `pose_only` | 只有姿勢/線稿參考圖,不需要角色一致性 |
| 「這個角色/風格套到新場景」「姿勢隨意,但要是這個角色」 | `style_lock`(靜態圖)。若要的是影片、第一幀不必是那張定稿圖 → `skills/comfyui-video-gen/SKILL.md` 的 `character_video` | 只有角色/風格參考圖,不需要指定姿勢 |
| 「這個角色換個姿勢/動作」「照這個線稿套進這個角色」 | `character_action` | 需要角色參考圖 **+** 姿勢/線稿參考圖(兩者都要) |
| 「幫我把這張草稿上色/精緻化」「同一個造型換材質/換顏色」 | `refine` | 有來源圖,想保留大致構圖但改細節/材質/顏色 |
| 「這裡崩壞了幫我修」「只改這個區域」「局部調整」 | `inpaint` | 有來源圖 + 需要指定修改區域,而且改動不涉及「結構要保持、外觀要換」這種衝突需求 |
| 「換武器/道具但要保持握姿」「換材質紋路但造型不能變」「這個部位要換,但骨架/輪廓不能崩」 | `guided_inpaint` | 有來源圖 + 修改區域,而且該區域有「結構(關節/輪廓)要鎖住、外觀要自由換」的衝突需求——純 `inpaint` 對這類需求容易讓模型同時賭結構跟外觀,失敗率高 |
| 「這張圖放大」「解析度不夠」「細節加銳利一點」「要交件/要印出來所以要更高解析度」 | `upscale` | 已經有確定要用的成品圖,想要更高解析度 + 補細節,不是想重新構圖 |
| 「這張已經定稿的合成圖,幫我拆出外框/中心鈕這幾塊各自的圖層」 | `layer_split` | 已經有一張定稿的完成圖,想事後切出幾個大塊區域各自疊放/調色,不是重新生成內容;拆幾層呼叫幾次,細節/使用限制見「複合元件的圖層」小節 |
| 「去背」「透明背景」 | 加 `--remove-bg` 旗標,可疊加在 `concept`/`pose_only`/`style_lock`/`character_action`/`refine` 之後(`icon_asset` 永遠去背,不用加旗標) | — |
| 「多出幾個版本比較」「一次看幾種可能性」 | 加 `--batch N` 旗標,只有 `concept`/`icon_asset`/`pose_only`/`style_lock`/`character_action` 支援(探索型任務才需要);問使用者要幾張,沒概念就用 3 | — |

## 各 task 該問的固定問題

> **這四個 task(concept / pose_only / style_lock / character_action)都要多問一題:圖片尺寸/比例有沒有要求?** 例如直式角色圖、橫式場景圖、正方形圖示、遊戲引擎規定的固定尺寸。使用者沒概念或沒特別要求就用預設值(不用主動報數字出來),有要求就用 `--width`/`--height` 帶入(數值必須是正整數且為 8 的倍數,實際可用上限仍受 VRAM/設備限制,常見值:1024x1024 方形、832x1216 直式、1216x832 橫式)。這題容易被忽略但常常很重要——遊戲素材有固定尺寸規格是常態,產出來尺寸不對通常等於要重做。

> **`--style`(除 `layer_split` 外全部 task 都支援)不用主動問,使用者對這次美術方向有明確偏好時才用。** 例如「這次想要偏插畫感/概念設計稿的感覺」→ `--style illustration`,「二次元/動漫風」→ `--style anime`,「寫實一點」→ `--style realistic`。不給就完全沿用這台機器裝機時鎖定的預設 checkpoint,不要為了「風格更好」自作主張加這個旗標。只支援 SDXL 家族 tier,對應 checkpoint 沒下載過會直接報錯,細節見 `reference/full-params.md` 跟 `reference/known-limitations.md`。**用 `--style anime` 時,prompt 開頭一定要加 `score_9, score_8_up, score_7_up`(Pony Diffusion V6 XL 的固定用法,至少 3 個 score 標籤),不加實測會出現灰階/構圖跑掉的不穩定結果,細節見 `skills/comfyui-install/reference/models.md`「使用眉角」。**

### concept(概念圖)
1. 想畫什麼(轉成英文 prompt,SDXL 對英文 prompt 理解較準)
2. 有沒有想避開的東西(負向詞,沒有就用預設 `blurry, low quality, extra fingers, deformed, watermark`)
3. 需不需要透明背景(去背)
4. 尺寸/比例有沒有要求(見上面提示)

### icon_asset(單一小型圖示/物件素材)
1. 想畫的圖示/物件內容(轉成英文 prompt)——不用特別強調「單一置中、無背景」,`icon_asset` 已經固定在 prompt 尾端加這段引導詞,加了反而是重複
2. 有沒有想避開的東西(負向詞,沒有就用預設)
3. 尺寸/比例**預設 1024x1024 正方形,不用主動問**——這是跟 `concept`/`pose_only`/`style_lock`/`character_action` 四個 task 不同的地方,圖示類素材幾乎都是方形/近方形,只有使用者主動提出別的比例才用 `--width`/`--height` 覆蓋。**但如果這批圖示是要替換/匹配一組現成的素材包(例如既有遊戲的 symbol 資料夾),先看那組素材實際的解析度**(常常遠小於 1024,例如 300x300、140x140)**,生成/探索階段仍用預設 1024 跑,只在最後交付前統一縮放+壓縮到目標尺寸**——不用整個探索期間都用完稿解析度來回讀圖,浪費且沒必要
4. **不用問要不要去背**——`icon_asset` 永遠輸出透明背景,沒有 `--remove-bg` 旗標
5. **判斷這個圖示的結構/顏色配置有沒有明確答案、不該讓 AI 自己瞎猜**(例如「精確等分成 N 塊放射狀分區」這種計數幾何需求,**或圖示內容本身就是文字/字母/數字這類有精確筆畫答案的元素**,例如撲克牌花色符號 A/K/Q/J/10)——這種情況純靠文字描述給 SDXL 不可靠,改用 `--structure-ref <範本圖路徑>`,範本圖從哪來、怎麼判斷要不要用,見 `reference/structure-ref.md`,不是每次都要讀,只有遇到「結構描述用文字講不清楚/AI 一直畫不準」時才需要。**範本圖如果是文字/字母,額外問使用者一句「要工整易讀,還是重視風格/連筆流暢」**——兩者常有取捨(例如連筆花體字型的大寫 K/J 對一般人來說幾乎認不出原本的字母),先問清楚優先順序,不要生完一輪才發現方向不對,細節/字型建議見 `reference/known-limitations.md`
6. **使用者手上有一張現成圖,想要「材質/質感偏向那張圖」才問要不要用 `--appearance-ref <路徑>`**(IPAdapter,原則同 `guided_inpaint` 的同名參數)——**參考圖如果帶文字(例如成品截圖上印的按鈕字),`--appearance-weight` 要從低值(0.3~0.4)開始試,不要用預設 0.8**,不然文字視覺印象會被一起帶進來變成畫面裡一坨假字,細節見 `reference/known-limitations.md`
7. **使用者的描述如果偏抽象形容詞(例如「科技感」「有質感」「精緻一點」),先問有沒有現成的參考圖或具體關鍵字,不要急著動手生成再靠使用者一輪輪反饋修正方向**——反覆生成+確認的來回成本,遠高於先問一次把方向問清楚
8. **這批圖示如果是「一整組」的系列(例如撲克花色 A/K/Q/J/10、或一套配色系統的一整套 symbol),先挑其中一張代表性的內容把風格/材質配方定案(生成+確認),確認滿意後再套用到其餘張數**——不要邊做邊決定風格,每換一次方向就要重跑全部張數,成本會直接乘上張數

### layer_split(從定稿完成圖拆出單一圖層)
1. 來源圖路徑(**必須是已經定稿的完成圖**,不是重新生成——這個 task 不吃 prompt,純粹裁切透明度)
2. **一定要請使用者提供這一層的遮罩圖**,原則同 `inpaint`(alpha 語意一樣:要保留進這一層的區域 alpha=0,其餘 alpha=255),建議用 MaskEditor 畫
3. 這一層要取什麼名字(`--layer-name`,用來組輸出檔名前綴,例如 `border`、`center_hub`)
4. 一次呼叫只拆一層,要拆幾層就呼叫幾次——**適合大塊、邊界明確的區域**(例如外框/中心鈕),不適合切太細碎或太多張視覺相似的區域(例如轉盤裡 8 片幾乎一樣的分區隔板),這種高度重複的元素該怎麼處理,見下面「複合元件的圖層」小節,不要硬用 `layer_split` 切

### 複合元件的圖層(例如轉盤的外框/分區隔板/中心鈕)
使用者要「一個複合元件,但各個構件要能分開疊放/調色/動畫」時,依構件類型判斷用哪種做法,不要不分青紅皂白都套同一招:
- **結構相異的大塊**(外框、中心鈕、指針這類長相彼此不同、只有一個的構件):各自用 `icon_asset` 呼叫一次獨立生成。想讓幾次呼叫的色調/材質風格盡量一致,prompt 裡重複寫同一組風格關鍵字(例如都寫 "gold ornate fantasy style, teal gemstone accents"),但**不保證完全一致**,仍需要美術後製微調——AI 獨立生成之間本來就沒有像素級一致性保證
- **高度重複的元素**(例如轉盤的每個分區隔板,肉眼看起來該長一樣的那種):**不要**逐一各自生成,也**不要**事後用 `layer_split` 從一張合成圖裡切割相鄰的相似色塊——兩種做法都不可靠(前者色差/比例不一致,後者邊界抓不準)。看使用者要的是「一片樣板自己去複製組裝」還是「一張結構已經對的完整成品圖」:前者用 `icon_asset` 生一片分區樣板,交給使用者在自己的工具(Figma/遊戲引擎)裡旋轉複製組成整圈;後者用 `icon_asset` 的 `--structure-ref`(見 `reference/structure-ref.md`)在單次生成裡把整個放射狀結構跟顏色配置一次鎖住,不用使用者自己組裝,但代價是精細裝飾細節會被結構鎖一定程度壓掉
- **已經有一張定稿合成圖,想事後切出幾個大塊區域**:用 `layer_split`,見上面固定問題
- **目前沒有「AI 自動判斷圖層邊界、不用手動畫遮罩」的能力**(沒有裝語意分割模型),如實告知使用者這塊做不到,不要假裝可以,細節見 `reference/known-limitations.md`

> 判斷理由/背景說明見 `reference/layered-assets.md`,平常照上面判斷就好,不用每次都讀。

### pose_only(單獨姿勢/構圖控制)
1. 想要的畫面文字描述
2. **一定要跟使用者要姿勢/線稿參考圖的檔案路徑**(照片、簡筆骨架圖、線稿都可以)
3. 尺寸/比例有沒有要求(見上面提示)
4. 姿勢的精準度(--pose-strength,預設 1.0)通常不用問
5. 構圖控制來源(--control-type,預設 canny)通常不用問,選擇判斷跟稀疏線稿的踩坑細節見 `reference/control-type-selection.md`
6. 文字描述的動作要跟姿勢參考圖裡實際的動作一致,原則同上,細節見 `reference/control-type-selection.md`

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
6. 構圖控制來源(--control-type,預設 canny)通常不用問,判斷原則同 `pose_only`,見 `reference/control-type-selection.md`
7. 文字描述的動作要跟姿勢參考圖裡實際的動作一致,原則同 `pose_only`,見 `reference/control-type-selection.md`

### refine(圖生圖:精緻化/材質變體)
1. 來源圖路徑
2. 想要的新內容/材質/顏色描述
3. 保留原圖程度(--denoise):0.3~0.4 大致保留原色只上色/微調;0.6~0.7(預設)細節大幅改變;0.9+ 幾乎重畫。使用者沒概念的話用預設 0.6,並提醒「如果變化太小可以再調高」

### inpaint(局部調整)
1. 來源圖路徑
2. **一定要請使用者提供遮罩圖**,最簡單的方式是明確說「請用 ComfyUI 介面的 MaskEditor 塗好存成一張圖給我」(MaskEditor 存出來的格式一定對,不用管底層細節)——不要自己用文字描述去猜測要修改的區域,座標/範圍必須來自使用者提供的實際遮罩檔案
3. 想要新內容的描述
4. 保留原圖程度(denoise,預設 1.0 = 完全重畫遮罩區域,想保留更多原圖細節可以問要不要調低)

> **遮罩檔案格式是個真實陷阱,已實測踩過一次**(alpha 通道語意、沒生效卻不報錯的坑)**,遇到「遮罩好像沒生效」「局部修圖結果變差」時讀 `reference/masking.md`。** 不規則遮罩(多邊形等)的預覽驗證流程、以及貼合度/羽化範圍/`--denoise` 三者的搭配原則也在同一份文件裡。

### guided_inpaint(局部重繪 + 結構鎖定 / 外觀參考圖)
1. 來源圖路徑
2. **一定要請使用者提供遮罩圖**,原則同 `inpaint`(alpha 語意一樣,遮罩最好只蓋要換外觀的區域,不要順手蓋到不想動的部分,例如肩章/徽章這種容易被模型腦補補回來的細節——經驗上遮罩範圍越貪心,不想要的東西越容易一起被重新生成)
3. **判斷外觀要靠文字描述、還是使用者有現成的一張參考圖(例如自己畫的材質/紋理圖)**——有圖的話優先用 `--appearance-ref`,純文字描述紋理細節通常講不清楚
   - 有參考圖:跟使用者要圖的檔案路徑,提醒最好是**乾淨的材質特寫**(就一塊紋理,不要整張場景照),不然背景/光影會一起被帶進來污染結果(原則同 IPAdapter 角色參考圖要裁緊的教訓)
   - 沒有參考圖:正常問想要的新內容文字描述
4. **判斷這次需求要不要鎖結構、要鎖哪種**(`--control-type`,選用,不給就不鎖結構——只有外觀參考圖/文字描述在跑):
   - 需求是「手部/肢體姿勢不能變,換手上拿的東西」→ `pose`
   - 需求是「物體輪廓/立體起伏不能變,換材質紋路顏色」→ `canny`(輪廓線)或 `depth`(立體感,例如鱗片、盔甲浮雕這類有明顯凹凸的表面)
   - 兩種需求都有(換材質紋路,同時要保持物體外形)可以兩個都用:`--control-type` 鎖形狀 + `--appearance-ref` 決定外觀
5. 結構鎖定強度(--control-strength,預設 1.0)、外觀貼合強度(--appearance-weight,預設 0.8)通常不用問
6. 保留原圖程度(--denoise,預設 1.0)通常不用問,原則同 `inpaint`
7. 結構引導來源圖(--control-ref)預設用來源圖本身抽取結構,通常不用問;只有使用者想套用「別張圖的姿勢/輪廓」而不是這張圖原本的姿勢時才需要另外指定

> **`--appearance-ref` 抓的是參考圖的風格/色彩印象,不是逐像素複製圖案。** 已實測:丟一張像素化數位迷彩紋理當參考,結果變成同色系的條紋質感,不是精確複製那個像素圖案——IPAdapter 本來就不是這樣設計的,不要跟使用者保證「會做出一模一樣的紋理」,只能說「風格/色調會參考那張圖」。另外遮罩邊界外側(例如緊鄰的衣領)偶爾會被外觀參考圖的顏色牽動一起變化,遮罩要盡量貼合實際要換的區域,不要留太寬的羽化margin。

### upscale(放大精修,不是重新構圖)
1. 來源圖路徑(已經確定要用的成品圖)
2. **盡量沿用當初生成這張圖時用的 prompt**——二次取樣需要 prompt 才能補細節,風格才會跟原圖一致,問使用者「記得原本的描述嗎」,真的想不起來就用畫面內容重新描述一次
3. 要放大幾倍(--scale,預設 2,最高建議到 4)
4. 補細節強度(--denoise,預設 0.4)通常不用問,除非使用者說「細節補太多跑掉了」(調低)或「還是不夠銳利」(調高)

### 參數界線與送出前檢查

`generate.py` 會在建立 graph 或上傳參考圖前檢查可調參數；超出界線就直接報錯，不要用環境或手寫 workflow 繞過固定 CLI 契約：

- `width`、`height`:正整數且為 8 的倍數；沒有設定通用的最大像素值，是否能跑仍取決於該 tier 的 VRAM。
- `batch`:正整數（`>= 1`），只有探索型 task 支援；帶 `--structure-ref` 的 `icon_asset` 仍以單張範本 latent 為準。
- `ip-weight`、`pose-strength`、`control-strength`、`appearance-weight`、`lora-strength`、`denoise`:有限數值 `0..1`（包含端點）。
- `scale`:有限數值 `> 0` 且 `<= 4`。
- `timeout`:有限正數（秒）。`seed` 則必須是整數；`--style`/`--rating`/`--control-type` 維持白名單選項。

完整適用 task、預設值與何時使用見 `reference/full-params.md`。這裡列出的 0..1 是腳本實際接受的界線；不要再沿用舊文件中把 `pose-strength`/`control-strength` 寫成 0..10 的說法。

## 執行

確定好參數後,直接呼叫,不用再跟使用者確認一次(前面問過的就是確認過了)。**每一次呼叫都要加 `--output-dir <local_config.json 裡的 output_dir>`**,讓成品留在這個 repo 裡:

```
concept:
  <python_exe> <generate_script> concept --prompt "..." [--negative "..."] [--width W --height H] [--batch 3] [--lora <檔名> --lora-strength 0.8] [--style realistic|illustration|anime] [--remove-bg] --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>

icon_asset:
  <python_exe> <generate_script> icon_asset --prompt "..." [--negative "..."] [--width W --height H] [--batch 3] [--lora <檔名> --lora-strength 0.8] [--structure-ref <範本圖路徑>] [--appearance-ref <路徑> --appearance-weight 0.8] [--style realistic|illustration|anime] --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>

pose_only:
  <python_exe> <generate_script> pose_only --prompt "..." --pose-ref <path> [--pose-strength 1.0] [--control-type canny|pose|depth] [--width W --height H] [--batch 3] [--lora <檔名> --lora-strength 0.8] [--style realistic|illustration|anime] [--remove-bg] --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>

style_lock:
  <python_exe> <generate_script> style_lock --prompt "..." --character-ref <path> [--ip-weight 0.8] [--width W --height H] [--batch 3] [--lora <檔名> --lora-strength 0.8] [--style realistic|illustration|anime] [--remove-bg] --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>

character_action:
  <python_exe> <generate_script> character_action --prompt "..." --character-ref <path> --pose-ref <path> [--control-type canny|pose|depth] [--width W --height H] [--batch 3] [--lora <檔名> --lora-strength 0.8] [--style realistic|illustration|anime] [--remove-bg] --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>

refine:
  <python_exe> <generate_script> refine --prompt "..." --image <path> [--denoise 0.6] [--style realistic|illustration|anime] [--remove-bg] --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>

inpaint:
  <python_exe> <generate_script> inpaint --prompt "..." --image <path> --mask <path> [--denoise 1.0] [--style realistic|illustration|anime] --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>

guided_inpaint:
  <python_exe> <generate_script> guided_inpaint --prompt "..." --image <path> --mask <path> [--control-type pose|canny|depth] [--control-ref <path>] [--control-strength 1.0] [--appearance-ref <path>] [--appearance-weight 0.8] [--denoise 1.0] [--style realistic|illustration|anime] --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>

upscale:
  <python_exe> <generate_script> upscale --prompt "..." --image <path> [--scale 2.0] [--denoise 0.4] [--style realistic|illustration|anime] --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>

layer_split:
  <python_exe> <generate_script> layer_split --image <path> --mask <path> --layer-name <name> --comfy-url <comfyui_url> --timeout 180 --output-dir <output_dir>
```

(`<python_exe>`、`<generate_script>`、`<output_dir>` 都從 `local_config.json` 讀,不要寫死實際路徑)

執行完把腳本印出的圖片路徑告訴使用者,不用額外描述生成過程。如果使用者明確要求存到別的資料夾,才把 `--output-dir` 換成使用者指定的路徑。每次要把 `local_config.json` 的 `comfyui_url` 轉成 `--comfy-url`（或明確用 `--config`），並依任務耗時調整 `--timeout`。

## 離線檢查與實機 smoke test

修改產線或接手新機器時，先在 repository 根目錄跑 `python -m compileall -q tools_src tests` 與 `python -m unittest discover -s tests -p 'test_*.py' -v`。這兩條指令在 Windows、macOS、Linux 都不依賴 shell 展開 glob。這些檢查不需要 Pillow、GPU 或 ComfyUI；它們只驗證 graph/參數/HTTP 邊界。真正的節點相容性、模型載入、輸出尺寸、PNG/RGBA alpha 與去背品質，仍要在有 `local_config.json` 的已安裝機器上用 `--comfy-url` 做一次 smoke test，不能把離線測試結果當成實機產圖通過。

## 深入參考(邊界情況/踩過的坑,查這裡,不用每次都讀)

平常只問「各 task 該問的固定問題」列出的項目、照「執行」的指令模板呼叫就好。遇到下面這些狀況才需要多讀一份參考文件:

| 狀況 | 讀這份 |
|---|---|
| 使用者提出比較細的參數要求(例如「用跟上次一樣的種子」「圖再大一點」「套用某個 LoRA」) | `reference/full-params.md`(完整參數規格表 + 目前刻意鎖死不開放的參數) |
| `pose_only`/`character_action` 要判斷 `--control-type` 該用 canny/pose/depth,或參考圖是稀疏線稿 | `reference/control-type-selection.md` |
| `inpaint` 遮罩好像沒生效、局部修圖結果變差、要畫不規則遮罩 | `reference/masking.md` |
| 使用者問「這個能不能做到」「有沒有什麼做不到的」,或遇到看起來像已知限制的失敗結果 | `reference/known-limitations.md` |
| 複合式 UI 元件要拆圖層,想知道判斷理由/背景說明 | `reference/layered-assets.md` |
| `icon_asset` 的結構/顏色描述用文字講不清楚,或 AI 一直畫不準確定的數量/配置(例如放射狀等分) | `reference/structure-ref.md` |
