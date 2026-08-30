# 影片產線設計稿

> **狀態:第一波 CLI 已上線並實測。** 對外契約是 **task 名 + `--backend`**,不是模型名。`img2video` / `fx_loop` / `transition` / `clip_extend` / `video_concat` / `character_video` / `camera_move` / `pose_drive` 都在 `generate.py`。哪個 backend 接了哪些能力見 `reference/backends.md`。操作走 `SKILL.md`。
> Agent 看到「幫我產一段影片」時讀 `SKILL.md`,不要臨場組節點。**不要自動播放成品。**
>
> 日期:2026-08-26
> 分支:`feature/video-pipeline`
> 對齊對象:現有靜態圖產線(`skills/comfyui-art-gen/SKILL.md` + `tools_src/generate.py`)

---

## 0. 一句話定位

**ComfyUI 在這條產線裡是「虛擬攝影組 + VFX 元素組」,不是剪接台、不是導演、不是調色房。**

一次產出的單位是 **2~5 秒的鏡頭(shot)** 或 **可循環的特效元素(element)**。超過這個長度的東西——過場串接、劇情長片、預告片——是把多支鏡頭在外部剪接軟體 / 遊戲引擎裡組起來,不是讓模型一次吐出整部片。

這跟圖片產線「一次一張、task 對應一種輸入」是同一套哲學,只是單位從「圖」換成「鏡頭」。

---

## 1. 為什麼不能把影片當成「會動的 concept」

圖片產線能穩,是因為每個 task 的輸入輸出都很乾淨:`concept` 吃文字、`inpaint` 吃圖+遮罩、`character_action` 吃角色圖+姿勢圖。影片如果也想穩,必須先承認它**不是同一個引擎上多一個旗標**。

| 差異 | 靜態圖(現況) | 影片(要新建) |
|---|---|---|
| 模型家族 | SDXL(+ 選用 Juggernaut/Illustrious/Pony) | Wan 2.2 系列(跟 SDXL 的 ControlNet/IPAdapter **完全不相容**) |
| 工作單位 | 一張圖 | 一支 2~5 秒鏡頭,或一組可循環的 frames |
| 失敗模式 | 構圖跑掉、手崩、假字 | 上面全部 + 時間軸漂移(臉越變越不像)、動作不閉環、前後鏡連戲斷 |
| 一致性工具 | IPAdapter / LoRA / ControlNet | 還能用,但要接到**影片模型自己的控制接口**(Fun Control 的 pose/canny/depth、首尾幀),不能把現有 SDXL 節點直接串上去 |
| 時長 | 無關 | 結構性上限。本機 5B 級模型一次就是數秒;「長片」= 多鏡頭 + 外部組裝 |
| 透明通道 | `--remove-bg`(BiRefNet,已驗證) | 影片去背**不是同一套**,不要假設有 `--remove-bg` 能直接加在 mp4 上 |
| 輸出位置 | `output/` 的 png | 同樣進 `output/`,但副檔名是 mp4/webm;遊戲用的話還要再抽 frames |

**結論:影片是一條新產線,掛在同一個 ComfyUI 行程裡,走同一套 `generate.py` 呼叫習慣。不是幫 `concept` 加 `--animate`。**

---

## 2. 影視工程師會怎麼用 ComfyUI

把一部片子(或一段遊戲過場)拆成部門,每個部門問「ComfyUI 能當這個部門的哪一台機器」。這比從模型名稱倒推功能地圖準。

| 影視部門 | 他們實際在做什麼 | ComfyUI 能當什麼 | 這條產線該不該做 | 對應後面的 task |
|---|---|---|---|---|
| 劇本 / 分鏡 | 把故事拆成鏡頭表(鏡號、景別、動作、時長、進出點) | **不當這個部門。** Agent 當助導,產出鏡頭表,再逐鏡呼叫生成 | 要,但是 **skill 層的編導流程**,不是 `generate.py` 的一個 task | 見第 5.2 節「編導流程」 |
| 前視覺 / Animatic | 用粗畫面上時間,確認節奏跟鏡頭夠不夠 | 靜態圖 + 極短 I2V / 鏡頭運動,畫質可以醜 | 要,而且是長片的**真正起點**。先能排出 30 秒醜的 animatic,再把單鏡換成精緻鏡頭 | `img2video`(低解析、短) |
| 攝影組 | 在已經 lock 的畫面裡運鏡(推、搖、升、繞) | Fun Camera Control:pan / tilt / zoom / static | 要。遊戲過場跟預告很常用「名畫動起來」 | `camera_move` |
| 演員 / 動作捕捉 | 把一段表演套到角色身上 | Fun Control:參考圖(這是誰)+ 控制影片(pose/canny/depth 這段怎麼動)。沒有動作影片時,H3 Ref2VA 用角色靜幀鎖身份再組新鏡頭 | 要。沒 mocap 的身份鎖定走 `character_video`;有動作參考影片才走 `pose_drive` | `character_video`(已上線) / `pose_drive` |
| VFX 元素組 | 獨立拍火、煙、魔法、火花,交給合成師疊 | 短循環影片,題材單純、鏡頭鎖定 | **要,而且該最先做。** 題材單純、失敗成本低、遊戲跟影片都用得到 | `fx_loop` |
| 合成 / 轉場 | 鏡 A 接到鏡 B:硬切、疊化、match cut、變形 | 首幀 + 尾幀生中間(`FLF2V`) | 要。遊戲 UI/場景切換、片子裡的魔法轉場都是這個 | `transition` |
| 場記 / 連戲 | 同一角色下一鏡還是同一套服裝、同一張臉、同一盞光 | 靜態圖階段先 lock 角色(現有 IPAdapter/LoRA),影片階段用 I2V 從 lock 過的靜幀出發;鏡與鏡之間用上一鏡尾幀當下一鏡首幀 | 要,但是**紀律**,不是新模型。長片死在這裡的次數會比死在畫質上多 | `clip_extend` + 鏡頭聖經 |
| 清理組 | 去電線、修崩壞的手、補穿幫 | 影片 inpaint(時間軸上的遮罩) | 後期再做。靜態 `inpaint` 的坑(遮罩語意)會原樣放大到每一幀 | `video_inpaint`(不做第一波) |
| 剪接 | 把鏡頭排成時間線、對白、音樂、節奏 | **不當。** Premiere / DaVinci / 遊戲引擎 / 甚至 ffmpeg concat | 產線輸出「帶鏡號的素材」,組裝留給使用者的剪接工具 | 無 |
| 聲音 | 對白、音效、配樂、口型 | 本機 Wan 2.2 **不產聲音**。LTX 系列有原生音訊但授權/顯存/生態跟我們現況不合,不當第一波鎖定 | 第一波當純畫面。口型/對白等有預算再走雲端 | 無(第一波) |
| 調色 / 成片 | 統一片感、交 DCP / 上架規格 | 影片放大、色匹配 | 後期。靜態已有 `upscale`,影片版另外做 | `video_upscale`(不做第一波) |

**影視工程師不會做的事:** 對 ComfyUI 說「幫我做一部 8 分鐘有劇情的片子」然後等一條 mp4。那是把導演、場記、剪接、聲音的工作全塞進一個會一次吐 5 秒的模型。

**影視工程師會做的事:** 寫鏡頭表 → 每鏡先有 lock 的靜幀(這條產線已經會) → 每鏡變成 2~5 秒 → 需要循環的做成 loop → 需要接的用首尾幀 → 全部丟進剪接時間線。

---

## 3. 三個需求方向,加上漏掉的那些

使用者點名的三個方向都成立,但粒度不一樣,不能做成「三個按鈕」。

### 3.1 單純動畫特效

**本質:** VFX 元素庫。鏡頭鎖定、題材單純、最好能 loop。

遊戲側例子:技能特效、命中火花、火把、旗幟、法陣、UI 光暈、寶箱打開。
影片側例子:爆炸元素、魔法拖尾、雨、煙,給合成師當 plate。

正確做法:

1. 盡量從一張已經 lock 的靜幀出發(現有 `icon_asset` / `concept`),不要純文字賭第一幀長什麼樣
2. 運動寫「原地循環、鏡頭鎖定」,不要寫情節
3. 需要進引擎的,生成後抽 frames 做成 sprite sheet(這步是 ffmpeg / PIL,不是 ComfyUI 節點)
4. 需要透明的,第一波**不要承諾影片去背**;能接受的話先在單色背景上生、再逐幀去背(沿用現有 BiRefNet,當後期步驟,不是影片模型的能力)

這是 **ROI 最高、最該先做** 的方向。失敗了重跑成本低,成功了遊戲跟影片兩邊都能用。

### 3.2 有劇情的長片

**本質:** 不是生成問題,是製片問題。

一部 60 秒片子,24fps,大約 1440 幀。本機模型一次生 81 幀(~3~5 秒)。所以 60 秒 = 至少 12~20 個鏡頭,還不含重拍。每個鏡頭還要過連戲:同一張臉、同一套衣服、同一盞光、動作從上一鏡的出點接到下一鏡的進點。

正確的生產順序(影視標準,不是 AI 標準):

1. **劇本 → 鏡頭表**(鏡號、景別、動作一句話、時長、進出點、用哪張靜幀當 lock)
2. **Animatic**:每鏡用現有靜態圖 + 很短的 I2V,先排出時間,確認鏡夠不夠
3. **單鏡精修**:把 animatic 裡過關的靜幀,用較認真的 I2V / `pose_drive` 換成正片鏡頭
4. **接戲**:上一鏡尾幀 = 下一鏡首幀(`clip_extend`),或兩張 lock 靜幀做 `transition`
5. **外部剪接**:ComfyUI 交出帶鏡號的 mp4,使用者在剪接軟體裡對音樂、對白、字幕

這條產線要做的是步驟 3 跟 4 的穩定 task,加上步驟 1 的 skill 層編導流程。步驟 5 永遠不進 ComfyUI。

**不要承諾的事:** 「一個 prompt 出完整劇情片」「角色全程不崩」「自動對口型」「自動配樂」。

### 3.3 動態轉場

**本質:** 已知 A 畫面、已知 B 畫面,模型只負責中間那一段。這比「憑空生一段情節」可控得多,是首尾幀(`FLF2V`)的本命題。

三種完全不同的轉場,不要混成一個參數:

| 類型 | 輸入 | 誰該做 | 備註 |
|---|---|---|---|
| 硬切 / 疊化 / 擦除 | 兩段已生成的鏡頭 | **剪接軟體**,不要用 AI | 用模型做傳統轉場是浪費,而且不可重複 |
| 內容轉場(A 變成 B、場景溶解、角色傳送門) | 首幀圖 + 尾幀圖 + 一句描述中間發生什麼 | `transition` task | 這才是 AI 該做的 |
| 遊戲 UI/關卡切換 | 兩張已經定稿的 UI 或場景靜幀 | 同樣走 `transition` | 結構要穩的話,靜幀階段先用現有 `structure-ref` lock |

首尾幀官方 14B 路徑畫質較好,但 14B 不是這台 16GB 卡的預設鎖定(見第 6 節)。第一波能跑的是 5B 家族能做的 I2V 近似(同一張圖當首尾做 loop),以及 Fun Control 5B;真正的 A→B `transition` 可能要等 14B GGUF 路徑驗證過,或接受 5B 的畫質上限。**這一點必須實測後才能寫進操作手冊,現在不能裝成已經能做。**

### 3.4 使用者沒點名、但影視工程師會立刻補上的方向

這些不是「以後有空再加的點子」,是做片子時**缺了就會卡死**的能力。排序依這條產線的現況:

1. **從已 lock 的靜幀做 I2V(`img2video`)** —— 這條產線最大的存量資產就是靜態圖。影片的第一個 task 應該是「讓這張已經過關的圖動起來」,不是重新文生影片。沒有這個,上面三個方向都在空轉。
2. **鏡頭延續(`clip_extend`)** —— 長片的實際做法:上一鏡最後一幀當下一鏡第一幀。沒有這個就沒有「同一場戲的第二個鏡頭」。
3. **運鏡(`camera_move`)** —— 角色可以完全靜止,只有攝影機在動。過場、預告、展示武器/場景極常用,而且比「角色自己演」穩定。
4. **表演驅動(`pose_drive`)** —— 一段參考動作影片(自己擺拍、或下載的 mocap/影片)驅動已經 lock 的角色。對應現有 `character_action`,只是姿勢來源從一張靜態 pose 圖變成一段 pose 影片。
5. **Animatic 模式** —— 刻意用低解析、短時長、醜一點沒關係,目的是排出時間。這不是新模型,是 `img2video` 的一組鎖死低成本預設。
6. **環境循環 plate** —— 天空、城市遠景、旗幟、燭火。跟 3.1 同類,但用途是當背景層而不是特效層。現有 `layer_split` 的「分層疊放」思想在影片裡一樣成立。
7. **Insert / cutaway** —— 劇情片剪接需要「手部特寫、道具、反應鏡頭」當覆蓋。生成單位仍是短鏡頭,只是景別不同。編導流程要會問「這場缺不缺 insert」。
8. **抽幀交引擎** —— 遊戲動畫的正道往往是「影片模型懂運動 → 再收成 frames」,不是叫 SDXL 一張張想像中間幀。這是後期包裝,不是生成 task。

刻意**不**放進第一波的:

- 對白口型(需要聲音模型或雲端)
- 影片去背當一等公民
- 影片 inpaint / 影片 upscale
- 用 AI 做傳統剪接轉場
- 在 ComfyUI 裡排時間線

---

## 4. 產線原則(沿用圖片,不另發明一套)

跟 `AGENTS.md`、`generate.py` 開頭註解同一套:

- 每個 task 對應一組**鎖死大部分參數**的 ComfyUI graph,只留必要欄位可調
- 不靠 LLM 每次臨場組節點
- 上層 skill 只把自然語言收成結構化參數
- 目前沒預算,本機免費模型;之後有預算走 ComfyUI 內建 API 節點(Kling 等),**不重建產線**
- 換機器至少重跑 `detect_device.py`,不要假設影片 checkpoint 檔名跟這台一樣
- 新能力上線走 `skills/comfyui-new-tool-checklist/SKILL.md` 完整輪,不因為「先做最小可用」就跳過實測跟文件

額外為影片加上的硬規則:

- **先有靜幀,再有鏡頭。** 角色/場景/道具能用現有圖片產線 lock 的,不要改用文生影片賭第一幀。
- **一次一支鏡頭。** 使用者說「做一部片子」時,skill 拆鏡頭表,不要把它收成一個超長 prompt。
- **組裝在 ComfyUI 外面。** 產線交出檔名帶鏡號的素材(`output/shot_A12_img2video.mp4`),不負責 concat、字幕、配樂。
- **bake-off 結束前不鎖死單一影片 backend。** Wan 14B 仍不當預設;社群 GGUF 把 14B 塞進 16GB 是研究項,不是這一輪要裝的東西。
- **不要把 SDXL 的 ControlNet/IPAdapter 節點接到影片 graph 上。** 這是已知會 shape mismatch 的架構邊界,比 `sd15` tier 那筆技術債更硬。
- **對外契約是 task + `--backend`,不是模型名。** 輸出檔名前綴用 task 名。模型檔、節點、私有 prompt tag 只活在 backend 實作裡。某個 task 還沒接某個 backend 時直接報錯,不要改 task 名稱硬接。

---

## 5. 建議的 task 切法

### 5.1 `generate.py` 要新增的 task(第一波只做打勾的)

命名跟現有 task 同一風格:動詞或用途,不叫模型名。

| task | 影視對應 | 必要輸入 | 可調欄位(鎖定以外) | 第一波 |
|---|---|---|---|---|
| `img2video` | 讓 lock 過的靜幀活起來 | `--image` + 運動描述(`--prompt`) | 時長(短,鎖上限)、解析度走 device_config | **是,第一個要做的** |
| `character_video` | 演員組:角色參考圖鎖身份,新鏡頭(第一幀不必是那張定稿圖) | `--character-ref`(可多張) + 新鏡頭描述 | 時長、`--backend` | **是。對應靜態 `style_lock`,不是 `img2video` 加旗標** |
| `fx_loop` | VFX 元素 / 環境循環 | 運動描述;有靜幀就加 `--image` | 預設強制「鏡頭鎖定、動作循環」;時長短 | **是,跟 `img2video` 幾乎同 graph,差在預設 prompt 約束跟抽幀包裝** |
| `camera_move` | 攝影組運鏡 | `--image` + `--camera` 枚舉 | 時長、`--backend` | **是。有 last_frame 的 backend 餵幾何終點靜幀** |
| `transition` | 內容轉場 | `--start` + `--end` + 中間發生什麼 | 時長 | 第二波(5B 能不能做合格 A→B 必須實測;不行就標成 14B/雲端路徑) |
| `pose_drive` | 動作捕捉套角色 | `--image`(角色) + `--motion-ref`(動作影片) | `--control-type` canny/pose/depth、時長、`--backend` | **是。對應靜態 `character_action`** |
| `clip_extend` | 場記連戲 / 同一場下一鏡 | `--image`(上一鏡尾幀) + 接下來發生什麼 | 時長 | 第二波,但是長片的前提,不能一直拖 |
| `txt2video` | 純文字賭畫面 | 只有 prompt | — | **預設不做獨立 task。** 沒有靜幀時,先走現有 `concept` 出圖,再 `img2video`。純 T2V 當 `img2video` 省略 `--image` 的後門即可,不要鼓勵這條路 |
| `video_inpaint` | 清理組 | 影片 + 時間遮罩 | — | 不做第一波 |
| `video_upscale` | 成片放大 | 已定稿短片 | — | 不做第一波 |

`fx_loop` 跟 `img2video` 會不會最後合併成同一個 graph、只差預設值,實作時再決定。設計層先分開,是因為**驗收標準不同**:`img2video` 驗「還是不是這張圖、動作是不是使用者要的」;`fx_loop` 驗「最後一幀接回第一幀能不能看、進引擎抽幀後循環是否成立」。

### 5.2 編導流程(skill 層,不是 generate.py task)

使用者說出「有劇情的長片 / 過場動畫 / 預告」時,agent **不准**直接呼叫任何影片 task。固定先產出一份鏡頭表,問完再逐鏡生成:

每鏡必填:

1. 鏡號(A1、A2…)
2. 景別(遠/中/近/特寫)
3. 這鏡做什麼(一句話,對應 `--prompt`)
4. 時長(秒,超過單次上限就拆鏡)
5. 靜幀從哪來(現有圖 / 先跑圖片產線 / 上一鏡尾幀)
6. 用哪個 task(`img2video` / `character_video` / `camera_move` / `pose_drive` / `transition` / `fx_loop`)
7. 跟前一鏡怎麼接(硬切 / 首尾幀 / 尾幀延續)

這份鏡頭表是「影片版的固定問題」,對應 `comfyui-art-gen/SKILL.md` 裡每個 task 那組必問清單。等第一個 task 實作時,再寫成 `skills/comfyui-video-gen/SKILL.md`。現在不要先寫操作 skill,以免 agent 拿尚未存在的 CLI 去跑。

---

## 6. 模型鎖定(2026-08-26 重掃過本機開源現況,尚未實測)

> 第一次選 Wan 2.2 5B,有一部分是因為 `教學.md` 跟 Mac 上已經有 Fun Control 5B——那是路徑依賴,不是 2026-08 的 bake-off。使用者追問後重掃過「這台 4080 16GB 現在真正能本機跑、有 ComfyUI 官方模板」的候選,結論寫在這裡。**2.2 5B 仍當第一個煙測預設,但不再假裝它是畫質最新的本機模型。**

> 這張表是**設計階段的選擇**,不是 `models.md` 那種已鎖定、裝機必裝的清單。真的要下載之前,還要走 install skill + 硬碟空間告知 + 實測,才能寫進 `models.md`。

這台機器:Windows 11、RTX 4080 16GB。Mac M3 Max 上已經有 `wan2.2_fun_control_5B_bf16.safetensors` + `wan2.2_vae` + `umt5_xxl_fp8`,但那是舊機器紀錄,不能當成這台 Windows 已安裝。

| 候選 | 適不適合當產線預設 | 理由 |
|---|---|---|
| **Wan 2.2 TI2V 5B**(`wan2.2_ti2v_5B_fp16.safetensors`) | **預設鎖定** | ComfyUI 官方原生 workflow;同一顆同時做 T2V/I2V;官方說 8GB VRAM + native offload 可跑;Apache 2.0,商用條款清楚。對 16GB 4080 是唯一「不用量化特技就能當產線預設」的選項 |
| **Wan 2.2 Fun Control 5B** | 第二波鎖定 | Mac 上已有檔。做 `pose_drive` / 部分 `camera_move`。控制接口對應現有圖片產線的 canny/pose/depth 思想,只是接在 Wan 上不是 SDXL 上 |
| **Wan 2.2 Fun Camera 5B** | 第二波,跟 Fun Control 分開評估 | 官方支援 pan/zoom 等運鏡枚舉,剛好對上 `camera_move`。檔案大小 / 這台機器能不能跑要實測 |
| Wan 2.2 14B I2V/T2V/FLF2V | **不當預設** | 官方路徑要的 VRAM 遠超 16GB。社群 GGUF/FP8 能塞進 16GB 是 enticing,但那是另一條易碎路徑(量化、offload、custom node),不能當「鎖死可重複」的預設。需要 `transition` 畫質不夠時再當**選用升級**,走 pipeline-review 核准流程 |
| LTX 2.3 | 不當第一波 | 有原生音訊、16GB 能擠,但授權不是乾淨 Apache、顯存/系統 RAM 需求說法混亂,生態跟我們現有 ComfyUI native 節點不完全同一套。等有聲音需求再評估 |
| HunyuanVideo 1.5 | 不當第一波 | 人臉寫實口碑好,但不是這條遊戲美術產線的第一優先,且 VRAM 說法偏 24GB |
| Kling / Luma / Runway 等 API | 有預算再接 | `教學.md` 第 0.5 章 C 段已列。產線預留「同一 task 名稱、換 backend」的位置,第一波不實作 |
| **Wan 2.5 / 2.6 / 2.7 / 3.0** | **不當本機預設,有預算當同一 task 的雲端 backend** | 見下面「為什麼不用 2.5」 |

### 為什麼鎖定 2.2、不用已經出的 2.5(以及後面的 2.6/2.7/3.0)

2026-08-26 核過:ComfyUI 官方 Partner Node 已經有 `wan2.5-t2v-preview` / `wan2.5-i2v-preview`,而且預設還直接跳到 `wan2.6-t2v` / `wan2.6-i2v`,v0.33.4 起連 Wan 3.0 都進模板了。畫質、時長、原生音訊,雲端這條線確實比本機 2.2 5B 強(2.5 約 10 秒 + 音訊 + 1080p;2.6 到 15 秒;3.0 號稱單次 30 秒)。

**不用它當第一波預設的理由不是「2.5 比較差」,是它跟 2.2 不是同一種東西:**

| | Wan 2.2 TI2V 5B(本機) | Wan 2.5 起(2.5/2.6/2.7/3.0) |
|---|---|---|
| 權重 | Hugging Face 可下載,Apache 2.0 | **沒有公開權重**。Alibaba 從 2.5 開始改走商業 API,GitHub 上「2.5 會不會開源」的 issue 從 2025-09 開到現在都沒關閉 |
| 跑在哪 | 這台 4080,電費以外 $0 | 阿里雲 / Comfy Partner Node / fal 等,每支片子計費,素材要離機 |
| ComfyUI 接法 | 原生 local 節點(UNETLoader + Wan22ImageToVideoLatent) | `comfy_api_nodes/nodes_wan.py` 的 Partner Node,要 API key |
| 這條產線現況 | 符合「目前沒預算,只用本機免費模型」 | 符合第 0.5 章 C 段「之後有預算再接」,不是現在 |

網路上「Wan 2.5 ComfyUI workflow」大多數是 Partner Node 或代跑平台,不是你可以下載進 `models/diffusion_models/` 的 checkpoint。另外 **LTX 2.5** 是 Lightricks 的另一個本機模型,名字容易跟 Wan 2.5 混,不是同一個東西。

產線預留的位置仍然是:**task 名稱不變(`img2video` 等),有預算時加雲端 backend,預設繼續走本機 2.2。** 不要為了追版本號把本機產線改成必須刷卡才能跑。如果哪天 Wan 真的再出一版開源權重,走 `comfyui-pipeline-review` 核准再換,跟圖片產線換底模同一套紀律。

### 2026-08-26 本機開源 bake-off(這台 4080 16GB)

「更新的編號」跟「這台卡上更能當產線預設」不是同一件事。只看**有公開權重、ComfyUI 官方模板、16GB 消費者卡理論上跑得動**的三個:

| | Wan 2.2 TI2V 5B | LTX-2.5 distilled(2026-08-11) | MiniMax H3(2026-08-03) |
|---|---|---|---|
| 新舊 | 2025-07,最舊 | **15 天前**,目前本機開源裡最值得認真看的新模型 | 23 天前 |
| 權重 | 公開,Apache 2.0 | 公開但 **Hugging Face gated**,LTX Community License(年營收 < $10M 免費) | 公開,MiniMax Community License(有品牌標示義務的說法,商用前要自己讀條款) |
| ComfyUI | 官方 native 模板 | 官方 day-0 模板:T2V / I2V / **FLF2V** | 官方 day-0 模板 |
| 這張卡 | 官方 8GB 可跑,16GB 很鬆 | 官方宣傳 16GB 下限;完整 bf16 包約 66GB 硬碟,Comfy int8 distilled 才能往 16GB 擠 | 官方 footprint ~42.5GB,16GB 要靠 offload,社區測 4080 級是「能跑但慢」 |
| 音訊 | 無 | **原生對白/音效** | **原生立體聲** |
| 時長 | ~5 秒 | 官方談 10 秒 + native multi-shot | 最長約 15 秒 |
| 對這條產線 | Fun Control(pose/canny/depth/運鏡)生態最熟,對得上現有 `character_action` | FLF2V、multi-shot 直接對 `transition` 跟短劇情;pose 驅動要另查 IC-LoRA | I2V 保原圖最好(社區測),剛好對「先 lock 靜幀再動」 |
| 迭代速度 | 中 | 社區測明顯最快 | 社區測最慢(同一測約 14 分鐘 vs LTX ~1.5 分鐘) |

**2026-08-26 使用者拍板(後改):這一輪 bake-off 只用 Wan 2.2 5B 跟 MiniMax H3。** LTX-2.5 官方權重 gated,使用者選擇不走授權申請,本輪不下、不測。產線仍先不鎖死單一模型;第 1 階段用**同一張靜幀、同一個運動 prompt**兩邊對打,再決定 `generate.py` 預設走哪顆(也可以依 task 選不同 backend)。Skill / CLI 要能選 backend。LTX 若以後使用者願意在 Hugging Face 按 Agree,再當第三顆補測,不提前裝。

對打規則(還沒跑,先寫下來以免之後臨場亂比):

- 同一張已經過關的靜幀(現有 `output/` 裡的角色或場景)
- 同一句運動描述、同一個解析度檔位(先用 16GB 卡跑得動的低一檔,例如 832x480 附近、數秒)
- 記:牆鐘時間、峰值 VRAM、還是不是那張圖、動作有沒有做對、能不能當 loop、有沒有聲音
- H3 在 16GB 上預期要 offload、會明顯比較慢——慢不是取消資格,是評估項目

LTX-2.5 實務:Hugging Face gated,沒接受 Community License、沒 `HF_TOKEN` 會 403。ComfyUI 官方模板用 int8 distilled,不是 66GB 的 bf16 全家桶。

MiniMax H3 實務:權重公開、不 gated。這台機器是 torch 2.13+cu130,照 Comfy-Org README 用 `int8_convrot` 不要用 `fp8_scaled`。16GB 走官方最小組(FL2VA pruned int8 + NVFP4 文字編碼器 + 兩個 VAE),**不裝** bf16 全家桶、這輪也不先裝 Ref2VA(那是 R2V,多 ~19.5 GiB)。授權是 MiniMax H3 Community License,商用/要不要標品牌下載前使用者自己讀一次原文,不要只看這份摘要。

官方 5B 要的三個檔(Comfy-Org repackaged,2026-08-26 核過 Hugging Face API 的實際 size):

| 檔案 | 放到 | 實際大小 |
|---|---|---|
| `wan2.2_ti2v_5B_fp16.safetensors` | `models/diffusion_models/` | 9.31 GiB |
| `wan2.2_vae.safetensors` | `models/vae/` | 1.31 GiB |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors`(來自 Wan 2.1 repackaged) | `models/text_encoders/` | 6.27 GiB |
| **第 1 階段合計** | | **約 16.9 GiB** |

### 2026-08-26 第一次實測(832x480、同一張 `character_action_00026_.png`、同一句 idle prompt、seed 42、20 steps)

這台 RTX 4080 16GB,ComfyUI 0.34.0,DynamicVRAM 開啟:

| | Wan 2.2 TI2V 5B | MiniMax H3 pruned int8 |
|---|---|---|
| 牆鐘 | **42.4 秒** | **66.2 秒** |
| 輸出 | 832x480, 49 幀, 2.04 秒, 24fps, **無聲** mp4 | 832x480, 56 幀, 2.33 秒, 24fps, **立體聲 AAC** mp4 |
| 首幀保原圖 | 弱:帽子幾乎不見、畫面被拉成 16:9 後身份漂得比較兇 | 明顯較好:帽子、項鍊、法杖、臉還認得出是同一張靜幀 |
| 運動 | 有動,但比較像整張在溶、漂 | 頭髮/緞帶/法球有位移,身體姿勢鎖得比較住 |
| 檔案 | `output/bakeoff_wan22.mp4` | `output/bakeoff_h3.mp4` |

注意:來源靜幀是正方形,這次兩邊都硬出 16:9,等於先被裁/拉過,不是最終產線預設比例。這次是「流程能出片 + 保原圖誰比較像」的煙測,不是交件級畫質評比。H3 在 2 秒短片、int8、16GB 上沒有社區傳說的「十幾分鐘」,但更長/更高解析還要另測。

Fun Control 5B(`wan2.2_fun_control_5B_bf16.safetensors`,約 9.32 GiB)是第 2 波,不跟第 1 階段 bake-off 綁在一起下載。

MiniMax H3 官方最小組(Comfy-Org,2026-08-26 核過 Hugging Face API):

| 檔案 | 放到 | 實際大小 |
|---|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `models/diffusion_models/` | 19.53 GiB |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `models/text_encoders/` | 14.61 GiB |
| `minimax_h3_video_vae_fp16.safetensors` | `models/vae/` | 4.85 GiB |
| `minimax_h3_audio_vae_fp32.safetensors` | `models/vae/` | 0.56 GiB |
| **H3 FL2VA 最小組合計** | | **約 39.6 GiB** |

三邊 bake-off 硬碟(Wan 16.9 + H3 39.6 + LTX int8 distilled 預估再 30 上下)落在約 90 GiB 級,這台 C: 2026-08-26 剩約 268 GB,空間夠。H3 bake-off 當下不另外再下 Ref2VA / bf16 / 非 pruned 的 34GB int8。**2026-08-27 已補裝 Ref2VA**(`minimax_h3_ref2va_pruned_int8_convrot.safetensors`,19.53 GiB)給 `character_video`;CLIP 跟兩個 VAE 跟 FL2VA 共用,不用再下一份。

`detect_device.py` 之後要多一個影片 family(例如 `wan5b`),**不要**把 Wan checkpoint 塞進現有 `sdxl` tier 的 `CKPT` 欄位。圖片跟影片的 device_config 應該是兩組鍵,同一張卡可以同時是 `sdxl` + `wan5b`。

---

## 7. 已知限制(設計階段就能預告,實測後再搬進 known-limitations)

這些現在就可以跟使用者講,不要等做完才失望:

- **一次數秒,不是數分鐘。** 「長片」= 多鏡頭 + 外部剪接。
- **身分會漂。** 同一角色連續多鏡,I2V 比靜態 IPAdapter 更容易越走越不像。緩解:永遠從 lock 靜幀出發、鏡不要太長、下一鏡吃上一鏡尾幀;要新鏡頭(第一幀不必是那張定稿圖)走 `character_video`(H3 Ref2VA),不要拿 SDXL IPAdapter 接上影片 graph。
- **Loop 不是預設能力。** 要循環必須特別做(首尾同一張、或後製丟掉不閉環的尾幀)。`img2video` 預設不保證能 loop;`fx_loop` 才驗這個。
- **影片沒有跟靜態同等的去背。** 第一波輸出當不透明畫面。要透明素材走「單色背景 + 逐幀 BiRefNet」的後期,並誠實講這條又慢又可能閃爍。
- **文字、Logo、UI 字還是弱項。** 靜態已經承認這點,影片只會更差。
- **聲音不在第一波。** 產出是無聲 mp4。
- **5B 畫質是草稿/中段可用,不是院線。** 交件級鏡頭以後可能要 14B 選用路徑或雲端 API,那是明確的升級決策,不是裝完 5B 就自動變好。
- **Windows 這台現在什麼影片模型都沒裝。** Mac 有 Fun Control 5B 不代表這裡能跑。

---

## 8. 分階段落地

每一階段結束都要能回答「現在使用者可以穩定地要到什麼,不能要到什麼」。不一次做完。

### 第 0 階段(本文件,進行中)

- 寫完設計、對齊哲學、標出開放問題
- **不下載模型、不改 `generate.py`、不寫操作 SKILL.md**

### 第 1 階段:這台機器能跑出第一段影片(雙模型 bake-off)

- 更新 ComfyUI 到能用官方 native 影片節點的版本(已快轉到 v0.34.0)
- 已下載 Wan 2.2 TI2V 5B 跟 MiniMax H3 FL2VA pruned int8。LTX-2.5 本輪不下
- 每個 backend 先跑通官方 template(至少 I2V),再用同一張靜幀對打
- 紀錄實際 VRAM、耗時、解析度、幀數、保原圖程度。這些數字進 `教學.md`,不靠網路上的「應該可以」
- 此階段結束的驗收:**兩邊都能手動出 mp4,有對打紀錄,還沒有 CLI**

### 第 2 階段:第一個穩定 task = `img2video`

- `generate.py` 新增 task,鎖死模型檔名、步數、預設解析度/幀數
- skill 固定問題:要動的那張圖、怎麼動、要不要 loop(不要就走 `img2video`,要就走 `fx_loop` 或同一 task 的 loop 預設)
- 用現有產線的一張角色圖、一張圖示、一張場景,各跑一次,打開影片驗收(動作對不對、還是不是那張圖)
- 文件:`教學.md` 功能地圖那一列改掉「還沒裝」;install `models.md` 加影片段落;new-tool-checklist 走完
- 此階段結束的驗收:**使用者用自然語言說「讓這張圖動起來」,agent 能穩定交一支短 mp4**

### 第 3 階段:`fx_loop` + 抽幀包裝

- 循環驗收(最後接回第一幀)
- 可選:ffmpeg 抽幀到 `output/` 子目錄,給遊戲引擎
- 此階段結束的驗收:**火/法陣/旗幟這種題材能交出可循環短片或 frames**

### 第 4 階段:轉場與運鏡

- 實測 5B 做 A→B 首尾幀夠不夠用;不夠就標成已知限制,不要硬做
- `camera_move` 枚舉以實測 Fun Camera 為準
- 此階段結束的驗收:**兩張定稿靜幀能變成一段內容轉場;一張定稿靜幀能被指定運鏡帶動**

### 第 5 階段:長片所需的最小連戲

- `clip_extend` + `pose_drive`
- 寫 `SKILL.md` 的編導流程(鏡頭表)
- 用一個**刻意很短**的題目當端到端(例如 15~20 秒、4~6 鏡的遊戲技能展示或角色入場),驗證鏡頭表 → 逐鏡生成 → 外部 concat 的完整路徑
- 此階段結束的驗收:**不是「能做長片」,是「能做一支有分鏡的短過場,連戲不離譜」**

### 第 6 階段以後(有明確需求才開)

- 14B GGUF 選用路徑(走 pipeline-review 核准)
- 雲端 API backend
- `video_inpaint` / `video_upscale` / 口型
- 影片去背是否值得做成一等公民

---

## 9. 跟現有圖片產線怎麼接

推薦的日常路徑:

```
需求
  ├─ 還會動嗎? 不會 → 現有 comfyui-art-gen
  └─ 會動
        ├─ 還沒有過關的靜幀 → 先走圖片產線 lock 畫面
        ├─ 有靜幀、只要它動(構圖不動) → img2video / fx_loop / camera_move
        ├─ 有角色靜幀、要新鏡頭(第一幀不必是那張圖) → character_video
        ├─ 有兩張靜幀、要中間那段 → transition
        ├─ 有角色靜幀 + 動作參考影片 → pose_drive
        └─ 使用者以為自己在要「一部片子」 → 先出鏡頭表,再逐鏡走上面幾條
```

風格(`--style realistic/illustration/anime`)繼續活在**圖片階段**。影片模型吃的是已經長對的圖,不要指望 Wan 的 prompt 再切一次 Pony/Juggernaut。這也代表:動畫風過場,先用 `--style anime` 出 lock 靜幀,再 I2V。

輸出慣例:

- 跟圖片一樣進 repo 的 `output/`,加 `--output-dir`
- 檔名帶 task 名,方便之後當鏡頭素材找回來
- 遊戲要 frames 時另開子目錄,不要覆蓋 mp4

---

## 10. 已拍板的產品決定(2026-08-26)

這些原本是開放問題,使用者已拍板,後續實作當約束,不要再自己改方向:

1. **四種成品都要,不刪階段。** 特效循環、靜幀 I2V、內容轉場、有分鏡的短過場全部是產品範圍。落地順序仍按第 8 節走(一次穩一個),但任何階段都不能因為「先做最小可用」就被拿掉。
2. **交付格式:mp4 plate 跟 sprite frames 兩個都要。** `img2video` / `fx_loop` 從第一個可執行的 CLI 開始,就要能留下影片檔,並可選(預設要開)抽幀到 `output/` 子目錄。不要等「以後有空再補抽幀」。
3. **這台 4080 第 1 階段是雙模型 bake-off,不鎖死單一 backend:** 已裝 Wan 2.2 TI2V 5B 跟 MiniMax H3。LTX-2.5 本輪不做。先各自跑通官方 template,再用同一張靜幀對打,然後才寫 CLI。
4. **「有劇情的長片」是近半年真的要交的產品,不是北極星。** 鏡頭表從第一份影片操作 skill 就是一等公民——就算當下只實作得出 `img2video`,使用者說「做一部片子」時仍然先出鏡頭表再逐鏡生成,不准收成一個超長 prompt。`clip_extend` / `pose_drive` 可以晚一點有 CLI,編導紀律不能晚。

---

## 11. 刻意沒做的決定

- 不在這份文件裡鎖死步數、CFG、精確幀數、精確解析度——那要第 1 階段實測後才能寫進 `generate.py`
- 不把 Hunyuan / Wan 14B GGUF / LTX-2.5 寫成這一輪必測。Wan 2.2 5B 跟 MiniMax H3 是這一輪要對打的兩顆,對打完再鎖預設
- 不設計 ComfyUI 內建時間線 UI——跟「使用者不用學拉節點」衝突
- 不把影片 skill 現在就寫成可執行的 SKILL.md——CLI 還不存在,寫了只會害 agent 去呼叫假指令
