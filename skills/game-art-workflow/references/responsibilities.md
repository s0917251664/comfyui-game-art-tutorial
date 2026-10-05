# 遊戲美術產線職責盤點

這份盤點說明現有方法可以在哪些地方共用，以及哪些執行仍綁定 ComfyUI、本機程式、模型或 runtime。它是文件盤點，不是另一份執行入口，也不表示清單內每項能力目前在任一台機器都已可用。

## 職責分層

| 職責 | 工作內容 | 可攜性與驗證界線 |
|---|---|---|
| 需求／美術工作流程 | 目標、輸入來源、參考圖各自用途、修改與保留、階段、版本、驗收條件 | 方法可攜；不代表任何模型可遵循，也不代表已跨平台實測 |
| 生成執行 | 依引擎輸入契約呼叫圖片或影片生成模型 | ComfyUI 生成 task 綁定本機模型、node、設定與能力 gate；平台 Agent 必須按當下實際工具 schema 判斷 |
| 遮罩及圖像處理 | 手繪／候選遮罩、Alpha 合成、差異比較、換色、Core 裁切及檢查 | 有些是確定性操作，有些需 ComfyUI web service 或 SAM runtime；不能由文字流程取代，也不能假定平台 Agent 可執行 |
| 影片處理與合成 | 抽幀、接片、綠幕、分割傳播、圖層合成、編碼及驗證 | 各工具有不同輸入與 runtime；不需 ComfyUI server 仍可能依賴 facade/package 和媒體套件，不能歸為單一「影片能力」 |
| 美術驗收 | 評估造型、身份、內容、遮罩、接縫及實際用途是否合格 | 可共用檢查問題；決定接受與否仍由美術使用者作出 |

**共用規則**：需求需寫清楚，素材需標明用途，修改需列出保留項，候選需可追溯，驗收需區分技術與美術。這些是工作方法，不是已驗證的跨平台執行結果。

**引擎差異**：ComfyUI 路線先核對本機 config、能力快照、模型／node、task 輸入契約與實測證據，再呼叫固定 task；平台圖片路線只在當下會話確有工具時查看其即時 schema 與可用能力。文字、單圖、任意多參考、遮罩、透明輸出、版本控制等能力須分別確認。不得將 ComfyUI 的 task、seed、denoise、ControlNet、Alpha mask 或保留像素行為直接映射成平台功能。平台影片生成／影片處理目前未由本盤點接入；文字上的特效計畫也不構成 runtime 驗證。

## 技能存取與規則擁有者

只讀本次需求所需入口及相關參考小節；需求已完整時，executor 直接沿用 brief，不重新經過規劃。以下路徑是本專案定位資訊，移植共用方法不要求這些執行技能同時存在。

| 需求／規則 | 唯一維護入口 | 按需存取與交接 |
|---|---|---|
| 需求、參考用途、修改／保留、版本、內容驗收 | `game-art-workflow/SKILL.md` | 只整理需求不執行生成；輸出 brief 交給已選定 executor |
| 物件／VFX／角色動作方法 | `game-art-workflow/references/production.md` | 只讀相關小節；精確規格由 executor 回報能力差距 |
| ComfyUI 圖片 task、模型及輸入 gate | `comfyui-art-gen/SKILL.md` | 本專案預設 ComfyUI 路線；現有參數仍查專屬 art-parameters/task 文件 |
| 平台原生圖片工具 | `platform-image-gen/SKILL.md` | 只查當下工具必要欄位；不走本機 config、不以 API Key CLI 代替 |
| 本專案編修映射的舊入口 | `game-art-edit-brief/SKILL.md` | 共用方法轉交 workflow；只保留 ComfyUI 輸入映射與平台交接 |
| 五個本機圖片檔案操作 | `local-image-edit-tools/SKILL.md` | 可接任一來源的原始檔；只需 Python、Pillow、NumPy 與檔案存取 |
| 固定輸入的 ComfyUI 參數比較 | `comfyui-image-sweep/SKILL.md` | 只有明確比較需求才讀 plan 格式；不是通用平台重試 |
| 物件固定 Core 合成 | `comfyui-object-design/SKILL.md` | 使用共用系列方法；執行仍需要 Core schema／server 與既有 helper |
| 影片生成／接片／綠幕／抽幀 | `comfyui-video-gen/SKILL.md` | 共用 VFX 需求與實際 task/backend 分開；本機處理也有 facade/package 依賴 |
| 角色動作組的本機執行編排 | `comfyui-character-animation-workflow/SKILL.md` | 使用共用動作方法，再接圖片／影片及抽幀契約 |
| SAM 影片遮罩／ordered layer compose | `comfyui-video-layers/SKILL.md` | 與生成、綠幕合成分開 gate；只讀相應 segment 或 compose 契約 |

## ComfyUI、平台原生工具與外部 API 的差別

| 面向 | ComfyUI 專案執行 | 平台原生圖片工具 | 外部 API／CLI |
|---|---|---|---|
| 算力與環境 | 執行端需已裝模型／runtime；依快照與實測判斷 | 由平台提供工具，Agent 不需本機生成 GPU；仍需工具存取與額度 | 需另外接入服務、憑證與計費規則；目前未接入 |
| 輸入與控制 | 固定 task/profile 開放欄位；不同路線可用欄位不同 | 依當下 schema；不能假設 mask、多參考、seed 或模型選項 | 要依正式服務文件／實作驗證，不能採用參考 repo 的宣稱代替 |
| 局部保留 | 生成仍會漂移；另做已確認遮罩的確定性合成可檢查像素保留 | 語意要求不保證逐像素保留；確定性後處理是另一職責 | 即使支援 mask，也不能推定保留或輸出行為相同 |
| 追溯 | 依 task 可有圖片 manifest 或影片 sidecar，仍不保證逐像素重現 | 只記工具實際提供的資訊，不捏造本機 manifest／seed | 另記請求及服務回傳，不繼承本機技術驗證 |
| 影片與後製 | 既有影片 task 與本機／server helper 各自 gate | 本次技能只處理靜態圖；沒有平台影片接入 | 本次未新增影片 provider |

## 可交付與未完成的界線

- `game-art-workflow/`（含自帶 references）可作為共用方法包；`platform-image-gen/` 可作原生平台圖片執行指引。兩者是文字技能，接收端要能載入技能或閱讀內容，不宣稱任何聊天介面可自動安裝。
- 五個本機圖片操作若要交付，另需 `image_edit_tools.py`、Pillow／NumPy、原始素材與程式／檔案權限；只給 SKILL.md 不會取得執行能力。它們可處理平台原檔，但不是平台圖片模型的內建能力。
- 本次實際拆分的是技能責任、共用規則來源與讀取路由；`generate.py`、`image_edit_tools.py` 及現有 helper 沒有物理拆檔，沒有新增 task、provider、部署依賴或技術驗證狀態。
- 2026-10-05 已使用本會話原生 `image_gen.imagegen` 完成一次文字生圖＋單一來源圖編修：透明藍色藥水瓶改成紅色液體，兩張均為 1254×1254 RGBA。目視瓶身、瓶塞與金屬構圖接近，但玻璃高光、液體細節與 Alpha 有變動；藍版有可見像素碰畫布邊界。兩張仍為 candidate，無遮罩故不證明修改區外逐像素保留；多參考、其他平台及影片尚未實測。專案紀錄為 `output/platform-image-smoke-20261005/execution-review.json`，移植共用方法不要求取得此證據檔；本次結果不改寫本機 task/profile 驗證。
- 劇情分鏡、聲音、唇形與 ReActor 換臉仍由既有專用技能維護，本次產圖／VFX 分拆不改動它們的執行與驗收契約。

## 現有圖片職責：12 個 ComfyUI task

以下 task 是固定圖片產線入口。task 名稱和可選參數不應直接當成其他平台的功能名稱。SDXL／SD1.5 另依 profile 與本機 image capability snapshot 決定；FLUX.2 有獨立 preflight 與本機證據路線。每次實際使用都由 ComfyUI 產圖入口核對當前狀態。

| task | 產線職責 | 可共用的方法 | 執行差異／驗證界線 |
|---|---|---|---|
| `concept` | 從文字探索概念／場景／道具 | 描述主體、用途、畫幅與排除項 | 固定 ComfyUI task；平台需確認文字生圖工具 |
| `flux2_concept` | FLUX.2 純文字概念生圖 | 同上 | 獨立 Core node／模型 preflight 與實機證據；不套 image profile |
| `flux2_edit` | 單來源圖的整圖語意修改 | 指明來源與整體修改 | 僅單張來源，不支援多參考、mask 或自訂 denoise；不是局部修補 |
| `icon_asset` | 單一遊戲圖示／透明物件候選 | 描述物件、輪廓、數量及透明需求 | ComfyUI task 對去背／結構參考有固定契約；透明及細節需檢查 |
| `pose_only` | 依姿勢／線稿參考創作，不要求身份保留 | 區分姿勢來源與內容描述 | 姿勢控制受模型、參考與本機 task 能力影響 |
| `style_lock` | 角色參考放入新場景，姿勢可變 | 標示角色身份參考與場景要求 | 不保證角色一致性；本機 task 有既定欄位 |
| `character_action` | 角色參考配姿勢／線稿參考生成動作圖 | 明確標記角色和姿勢圖職責 | 參考污染或控制失敗可能發生，姿勢與身份需人工檢查 |
| `refine` | 以來源圖整體精緻化或改外觀 | 指明整圖改動及全局保留項 | 未使用遮罩時不能保證未提及區域不變；ComfyUI denoise 為本機 task 概念 |
| `inpaint` | 遮罩指定區域內編修 | 指明來源、編修目標和範圍 | 要已確認且符合本機反向 Alpha 選區契約的 mask；模型輸出可能越界 |
| `guided_inpaint` | 局部編修並依 task 支援的參考／控制維持結構 | 同上，另區分 appearance 與 structure/control 參考 | 只可用已開放輸入；不能假定平台有對應控制，也不能承諾遮罩外原像素不變 |
| `upscale` | 放大既有定稿圖 | 指出沿用來源版本與細節優先項 | 放大不代表真實細節恢復或視覺驗收通過 |
| `layer_split` | ComfyUI Core 以遮罩從定稿圖裁出單一圖層 | 指定來源、遮罩範圍與圖層用途 | 不使用生成底模，但仍是既有 ComfyUI task，走同一入口／gate；不會自動拆出整套角色動畫圖層，遮罩需人工確認 |

### 圖片本機輔助工具

這些工具沒有生成模型能力，不屬於上述 12 個 task。依執行依賴分別處理：

- **Simple Mask Tool／`mask_session.py`**：手繪遮罩不使用生成模型，但使用 ComfyUI web service；OpenCV GrabCut `mask_refine.py` 是 CPU 邊界候選 helper。畫遮罩、refine 候選與下游 task 所需 mask 契約分開驗收。
- **`sam_segment.py`**：固定 SAM 2.1 small 的候選遮罩、預覽及 cutout；需相應權重與 runtime，不是只處理普通 PNG 的免依賴工具。它是候選來源，不是已確認遮罩，使用前要人工驗收。
- **`image_edit_tools.py`**：`composite` 在已確認 Alpha mask 內合成生成結果、`compare` 做 RGBA byte 差異、`recolor` 在遮罩內調整符合條件可見像素色相、`reference-board` 排列用途標籤、`asset-audit` 檢查 Alpha／尺寸／碰邊。這五個命令依賴本機 Pillow/NumPy，不需 ComfyUI server。`sweep` 同檔中的另一命令依賴 ComfyUI task、config 與能力 gate，對白名單 task 做固定輸入有限比較；不是通用重試。工具均非語意理解或自動美術評分。
- **`layer_split`**：由 ComfyUI Core 做遮罩裁切，不需生成底模；仍屬 ComfyUI task 入口與契約，不應歸入免 ComfyUI 的本機 Pillow/NumPy 工具。
- **`comfyui_design.py` 物件 helper**：`scene` 將透明物件放上不透明背景、`sheet` 排多個透明素材供檢視、`pattern` 重複單一透明圖樣。依賴 ComfyUI Core 的固定確定性合成，非生成 task；輸出不透明 RGB，不重打光、不保證 seamless，也不替多個生成物統一風格。

`image_edit_tools.py sweep` 應作為獨立的 ComfyUI task 比較職責路由。其 CLI 仍是既有腳本 `image_edit_tools.py sweep`，會呼叫 `refine`、`inpaint`、`guided_inpaint` 或 `character_action`，最多 16 個候選並依 task validation gate 執行。它沿用 ComfyUI 產線能力與本機參數，不是平台 Agent 通用重試機制；詳細規則見專用的 ComfyUI sweep 技能。

## 影片生成及處理職責

### ComfyUI 影片生成 task（7 個）

| task | 職責 | 方法可攜及界線 |
|---|---|---|
| `img2video` | 讓輸入靜幀產生動態 | 可共用主體、動作、鏡頭及保留項描述；實際生成依 backend／模型能力 |
| `fx_loop` | 循環特效或環境動態候選 | 可共用效果、背景、節奏及接縫驗收；loop 名稱不保證無縫 |
| `transition` | 起始畫面過渡至結束畫面 | 可共用起訖和變化方向；不等於傳統硬切／疊化／擦除工具 |
| `clip_extend` | 延續既有片段 | 可共用前後鏡連續性描述；要符合輸入影片／尾幀契約 |
| `character_video` | 角色參考進入新鏡頭或動作 | 可共用角色、場景、動作需求；不承諾身份、姿勢精準一致 |
| `camera_move` | 主體大致靜止時的鏡頭運動 | 可共用主體固定和鏡頭方向描述；本機鏡頭參數限於 task 枚舉 |
| `pose_drive` | 以動作影片驅動角色靜幀 | 可共用驅動影片用途與身份保留檢查；受來源首幀及動作控制限制 |

生成短片的尺寸、時長、FPS、音訊和 backend 由本機影片技能及 capability gate 管理。平台端可沿用 brief 方法；沒有實際影片工具與 live schema 時，只能交付計畫，不標成執行或 runtime 驗證。目前平台影片尚未整合。

### 本機影片處理

- **`video_concat`**：以既有 `generate.py` facade/package 與 PyAV runtime 依明確順序接合影片；需選擇音訊處理及尺寸策略，不默默縮放或丟棄音軌。它不需 ComfyUI server，但不是可任意抽出單檔的平台工具。
- **`video_composite`**：以既有 facade/package、PyAV/Pillow 與相應依賴，對乾淨純綠幕前景做 chroma key 合成；不需 ComfyUI server，但不是語意分割或透明影片生成。
- **抽幀 helper**：使用既有影片 facade/package 與 PyAV 解碼已驗收影片，不重新生成；不是透明影片生成或圖集打包。
- **`video_layers.py`／Video Layers server node**：固定 ComfyUI server-side node，包含 SAM 2.1 短片遮罩傳播、source 片段層及 RGBA image ordered layer 合成、錨點追蹤／仿射處理、音訊和編碼驗證。client 只 preflight／queue／download，server 做媒體工作。這與一般 ComfyUI 影片生成、`video_composite`、逐幀動畫拆件是不同職責。

Video Layers 的工具契約有 2026-10-04 生產 8188 preflight 與 current strict codec/CFR smoke 記錄；產物仍是 candidate，且有追蹤、遮罩、遮擋、接觸等已知限制。技術 gate pass 不等於 VFX 美術驗收。它不宣稱可精確反演已烘焙特效、做 3D 接觸或重建動態目標身體。

影片生成、concat、綠幕 composite、SAM propagation 與 ordered layer compose 不能合併稱作一項已驗證的「特效產線」。它們各有獨立輸入、工具、測試證據和人工檢查。

## 組織方式參考

按需求入口分工、以短技能作路由入口、將細節放入按需閱讀的 references，以及分開標示平台原生工具和外部付費 API／CLI 的文件組織方式，參考使用者提供的 [GPT-Image2-Skill README](https://github.com/wuyoscar/GPT-Image2-Skill/blob/main/README.zh.md) 與其 [gpt-image 技能入口](https://github.com/wuyoscar/GPT-Image2-Skill/blob/main/skills/gpt-image/SKILL.md)。本專案只借用文件組織方式，不導入該專案模型、API、提示詞資料庫或能力宣稱；本盤點的執行狀態仍以本 repo 專屬技能與實測紀錄為準。
