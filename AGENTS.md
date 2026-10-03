# AGENTS.md

這是一個遊戲美術 AI 產圖產線專案。核心文件:

- `教學.md` —— 完整的環境建置紀錄、功能地圖(哪種需求對應哪種技術)、設備/預算選型建議
- `skills/comfyui-art-gen/SKILL.md` —— **當使用者用自然語言要求產生遊戲美術素材時,讀這份文件並照它的流程操作**
- `skills/comfyui-object-design/SKILL.md` —— **當需求是物件系列檢視、透明物件放入平面背景、單一圖樣重複時讀取**；沿用既有生成 task 與固定 ComfyUI Core 合成 helper，不新增生成 task；部署 helper 單檔至 `<ComfyUI>/tools/comfyui_design.py`，依賴同目錄既有 `generate.py`、`image_edit_tools.py` 與 `comfyui_pipeline/`。狀態與限制見 `docs/knowledge/art/object-design-workflows.md`
- `skills/game-art-edit-brief/SKILL.md` —— **當使用者要先整理多參考圖、指定部位編修、角色／結構保留等遊戲圖片編修需求時讀取**；只整理需求並映射到既有 task，不接 API、不執行生成。OpenAI 圖片指南僅作需求表達參考，能力仍依產圖技能檢查
- `skills/local-image-edit-tools/SKILL.md` —— **當使用者要對本機圖片做 RGBA 遮罩合成、差異檢查、整理參考圖板、檢查透明素材 Alpha／邊界、使用既有遮罩局部換色，或明確要求固定輸入的有限參數 sweep 時讀取**；只包裝既有圖片 task，不新增生成 graph；情境見 `skills/game-art-edit-brief/references/scenarios.md`，實機驗證狀態見 `docs/knowledge/art/edit-tools.md` 與 `docs/knowledge/art/single-object-color.md`
- `skills/comfyui-install/SKILL.md` —— **當要在新機器上設置這條產線、或 `local_config.json` 不存在時,讀這份文件並照它的流程操作**。這是一份目標清單而不是腳本,不同機器的 OS/硬體/既有安裝狀態交給 agent 臨場判斷怎麼達成
- `skills/comfyui-pipeline-review/SKILL.md` —— **只有使用者明確要求「評估/盤點產線有沒有新技術可以升級」時才讀這份文件**,平常不要主動觸發。負責盤點現有模型清單 + 查現況 + 給建議,不負責自己動手換模型
- `skills/comfyui-new-tool-checklist/SKILL.md` —— **要幫這條產線新增任何新工具/新技術/新 task 時,讀這份文件並依能力類型勾選適用項目**。圖片、影片與本機工具各自檢查安裝、程式碼、實測與文件；`workflows/` 不是義務。純文件修正不套用完整新增能力流程。適用項目不要因改動小而省略。
- `skills/comfyui-video-gen/SKILL.md` —— **當使用者要讓靜幀動起來、產短片、角色參考生影片時讀這份並照它的流程操作**。設計背景/還沒做的 task 見同資料夾 `DESIGN.md`。**不要把 `comfyui-art-gen` 的圖片 task 假裝成會產影片,也不要自己臨場組 ComfyUI 影片節點冒充產線;不要自動用系統播放器打開成品**
- `skills/comfyui-character-animation-workflow/SKILL.md` —— **當使用者要同一角色的一整組遊戲動作，或要求從定稿靜幀一路做到逐支驗收與抽幀交付時讀這份文件**。它只編排既有產圖／產影片 task 與人工驗收點，不新增模型參數，不把尚未接入的第三方 provider、APNG 或透明影片假裝成現有能力
- `docs/knowledge/` —— repository 附帶的 Obsidian vault，可直接用標準 Markdown 閱讀。先看 `docs/knowledge/TOOLS.md` 選現有工具／技能，再按 task 讀對應知識；決策見 `DECISIONS.md`，適用範圍清楚的歷史觀察見 `experiences/`。不要把整個 vault 複製進 prompt，也不要讓經驗自動覆蓋 profile。Obsidian 本體不是必要依賴
- `skills/project-knowledge/SKILL.md` —— 讀寫專案知識庫時使用；依 `docs/knowledge/TOOLS.md` 按需檢索和閱讀，不要整庫灌入 prompt。以標準 Markdown 和一般檔案讀寫方式更新既有筆記；草稿由小模型撰寫、root review。知識觀察不自動改寫 profile／能力驗收；不要把上游尚未完整接入的 ingest/query runtime 當作現有能力
- `local_config.json` —— **這台機器的實際安裝路徑**(ComfyUI 裝在哪、python.exe 在哪),不進版控,每台機器內容都不一樣。不存在的話代表這台機器還沒裝好,照 `skills/comfyui-install/SKILL.md` 的流程走
- `tools_src/generate.py` 與 `tools_src/comfyui_pipeline/` —— 實際執行產圖/產影片的原始碼(版本控管在這裡)。部署時要把 `generate.py` 與整個 `comfyui_pipeline/` 一起複製到 `<ComfyUI 安裝路徑>/tools/`；`generate.py` 是相容 facade，不可只部署單一檔案
- 圖片 task 可選 `--result-json <新 JSON 路徑>` 產生技術追溯 manifest；不含美術驗收結論。需要保存素材版本時，在 `docs/knowledge/assets/<asset-id>.md` 按需建立 Markdown 記錄，明確寫 candidate／accepted／rejected 狀態、使用者決定與理由；不可捏造接受狀態或讓新輸出繼承舊版本驗收。格式與沿用規則見 `docs/knowledge/result-records.md`
- `tools_src/mask_session.py` 與 `tools_src/simple_mask_tool/` —— 給不知道 ComfyUI 的使用者畫局部修改範圍；由本機 ComfyUI 提供極簡網址，部署時 client 要同步到 `<ComfyUI>/tools/`，同一套 package 也要同步到 `<ComfyUI>/custom_nodes/comfyui-simple-mask-tool/`。這是獨立的純手動畫遮罩工具，不含也不依賴 SAM。SAM 自動分割若後續新增，必須作為另一個獨立工具／能力開發；兩者只能透過標準遮罩檔案選配串接
- `tools_src/mask_refine.py` —— 選用的 OpenCV GrabCut 遮罩邊界候選 helper；獨立部署至 `<ComfyUI>/tools/mask_refine.py`，不含模型或 SAM 依賴。Simple Mask 有整合 `/refine` 預覽操作，但手繪仍可獨立使用；白選黑不選的 editor 輸入、Alpha 輸出轉換與部署後新 session／重新整理要求見 `docs/knowledge/art/masking.md`
- `tools_src/image_edit_tools.py` —— 本機 RGBA composite（可選 `--keep-source-alpha`）、遮罩內 HSV 色相旋轉 recolor、差異診斷、既有 task 有界 sweep、帶用途標籤的參考圖板與素材 Alpha／尺寸／碰邊檢查；部署單檔至 `<ComfyUI>/tools/image_edit_tools.py`，沿用 ComfyUI Python 的 Pillow、NumPy，不需 custom node。CLI／實測狀態見 `skills/local-image-edit-tools/SKILL.md`、`docs/knowledge/art/edit-tools.md` 與 `docs/knowledge/art/single-object-color.md`
- `tools_src/comfyui_design.py` —— 固定 ComfyUI Core `scene`／`sheet`／`pattern` 合成 helper；部署單檔至 `<ComfyUI>/tools/comfyui_design.py`，同目錄依賴既有 `generate.py` facade、`image_edit_tools.py` 與整個 `comfyui_pipeline/`。不新增生成 task，Core 輸出為不透明 RGB；操作與實測限制見 `skills/comfyui-object-design/SKILL.md` 與 `docs/knowledge/art/object-design-workflows.md`
- `tools_src/sam_segment.py` —— SAM 2.1 自動候選遮罩工具；固定使用官方 `facebook/sam2.1-hiera-small`，輸出 contact sheet、預覽、cutout 與符合既有 Alpha 契約的 `mask_comfy.png`。候選必須人工驗收後才能交給 `layer_split`／局部重繪。
- `tools_src/comfyui_pipeline/profiles/*.json` —— **SDXL/SD1.5 圖片模型設定檔**(模型檔名、取樣參數、依記憶體的預設解析度、可用 task、各平台驗證狀態),全平台共用、進版控,隨 `comfyui_pipeline/` 一起部署;每台機器只是依 `device_config.json` 的 tier 選用其中一份。FLUX.2 `flux2_concept`/`flux2_edit` 不使用 image profile，改由 `generate.py` 的獨立 Core node／模型 preflight 與實機 smoke test 判斷。**要換這些 profile 的模型檔名或取樣參數,改設定檔,不要改 `image_graphs.py`**。使用者明確要在大機器用小管線時,用 `generate.py --profile <id>` 或 `detect_image_capabilities.py --default-profile <id>`,不要手改 `device_config.json`。設計見 `docs/model-profiles-design.md`
- `tools_src/detect_device.py` —— 設備能力偵測(GPU/VRAM/OS),輸出 `device_config.json` 給 `generate.py` 讀取,決定用哪個 checkpoint/解析度
- `tools_src/detect_image_capabilities.py` —— 圖片能力偵測(依模型設定檔掃描這台機器的平台資格、已裝模型、可選的 ComfyUI nodes 與各 task 驗證狀態),輸出 machine-specific `image_capabilities.json`;只掃描,不下載。`generate.py` 另會在上傳前用 `/object_info` 檢查 SDXL 路線 graph 需要的 node 與模型檔
- `tools_src/detect_video_capabilities.py` —— 影片能力偵測(既有模型、影片 runtime、可選的 ComfyUI nodes),輸出 machine-specific `video_capabilities.json`;只掃描已安裝內容,不下載模型或套件
- `workflows/` —— **不進版控**(見 `.gitignore`)。ComfyUI workflow JSON 檔案,是 `generate.py` 背後鎖死的產圖流程定義,給維護這條產線的人(不是美術)在 ComfyUI 網頁介面手動開、除錯、開發新能力時視覺化參考用,屬於本機個人產物,跟 `教學.md` 第 9 章「自己存一份到 `~/ComfyUI/user/default/workflows/`」是同一件事。不強制每個 `generate.py` 新能力都要補對應檔案——有空、真的會用到再補,不用當成義務性的同步負擔

## 給任何 agent 的原則

- ComfyUI 是產線裡的其中一個生成引擎/工具,不是要求使用者學會拉節點。多數情境下只需要呼叫 `skills/comfyui-art-gen/SKILL.md` 描述的流程
- 產圖流程要穩定、可重複——不要每次臨場亂組 ComfyUI 節點圖,新增能力時比照 `generate.py` 的模式(鎖死大部分參數,只留必要欄位可調)
- 安裝/裝機是相反的情境:硬體排列組合太多,**刻意不寫死成腳本**,交給 agent 臨場判斷,細節見 `skills/comfyui-install/SKILL.md`
- 換一台機器 / 換一顆顯卡時,至少重跑 `detect_device.py` 重新產生 `device_config.json`,再重跑 `detect_image_capabilities.py`,不要假設 checkpoint 名稱、解析度、可用 task 或驗證狀態跟這台機器一樣
- 規劃生成工作前先確認能力：SDXL/SD1.5 圖片查 `image_capabilities.json`，影片生成查 `video_capabilities.json`；FLUX.2 不在圖片快照內，依產圖技能的獨立 preflight 與實測紀錄判斷。遮罩、抽幀、串接與合成等本機工具依各自依賴檢查。`unverified` 的 task 要先告知使用者；圖片 profile 的驗證狀態以平台(`platform_key`)為單位，不是每台機器各自重新調校。
- 影片模型、ComfyUI 版本、custom node 或 runtime 改變時,也要重跑 `detect_video_capabilities.py`;影片 task 不從圖片 tier 或 source code 猜 backend,缺模型/runtime/node 必須在 upload/queue 前停止
- 目前沒有預算,只用本機免費模型;之後有預算要接外部雲端 API(GPT/BFL/Kling 等),ComfyUI 本身已經有對應的 API 節點,不用重建產線,詳見 `教學.md` 第 0.5 章 C 段
- 如果需要在這個 repo 裡寫 `.ps1` 檔案,要存成**帶 BOM 的 UTF-8**——Windows PowerShell 5.1 沒有 BOM 會照系統 ANSI 編碼讀檔,中文字會把語法解析弄壞(這個專案已經踩過一次這個坑)
