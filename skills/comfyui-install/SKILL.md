---
name: comfyui-install
description: 在新機器上依硬體與既有狀態完成 ComfyUI 遊戲美術產線安裝、部署與能力偵測；這是判斷清單，不是固定腳本。
---

# ComfyUI 產線安裝

給任何操作這個 repo 的 agent(Claude Code、Codex、Gemini CLI 等)使用的技能說明。

## 何時使用

當使用者要在一台新機器上設置這條產線(不管是自己的電腦、還是要幫美術同事的電腦裝),或 `local_config.json` 不存在時使用。

## 核心原則

**這不是一支腳本,是一份目標清單。** 不同機器的 OS、硬體、既有安裝狀態都不一樣,不要照抄任何範例指令硬套——每個步驟看「這件事現在是不是已經成立」,不成立就用你判斷這台機器上最合適的方式做到。遇到這台機器特有的狀況(公司網路擋 huggingface、殘留安裝、CUDA 版本卡住、權限問題),照實跟使用者說清楚、想辦法繞過去,不要靜默失敗或編造結果。

之所以不寫死成 `.ps1`/`.sh` 腳本:硬體排列組合太多,腳本只會不斷長出新的特例分支,長期比讓 agent 臨場判斷更難維護。這跟 `generate.py`(必須鎖死參數以保證產圖可重複)是相反的情境——安裝是一次性任務,值得用判斷力換取彈性。

開始前先讀 [`docs/tested-versions.md`](../../docs/tested-versions.md)。它是已驗證版本的紀錄格式，不是「目前最新版」清單。若 `capture_status` 已是 `verified`，優先 checkout manifest 中的精確 commit；若仍是 `pending_on_installed_machine`，可以完成安裝，但要在同一台機器完成 smoke test 後擷取實際 commit、套件版本與模型 SHA-256，不能自行填入猜測值或宣稱已可重現。

## 開始裝之前:先告知硬碟空間需求

**動手下載任何東西之前,先跟使用者說清楚這台機器大概要花多少硬碟空間**,概估數字跟拆解見 `skills/comfyui-install/reference/models.md`「硬碟空間概估」那段(不含 LoRA 訓練工具約 26~28GB,含的話約 31~36GB)。念完概估數字、確認使用者這台機器有足夠可用空間,再開始走下面的步驟——不要裝到一半才發現空間不夠中斷,那樣通常要使用者自己回頭清理下載到一半的檔案才能重來,比事前講清楚麻煩很多。模型部分的空間依步驟 4b 選定的模型設定檔而定:`sdxl_standard` 看 SDXL 表格(選配模型可逐項省略),`sd15_light` 只需要 SD1.5 底模、BiRefNet 與放大模型。

## 目標(裝完之後,以下都要成立)

1. **前置工具**:`git` 在 PATH 上;ComfyUI 實際執行用的是步驟 3 的 `.venv`,**判斷標準是 `.venv` 裡的 Python 為 3.11+**。PATH 上的系統 `python3` 只用來建立 `.venv`:`.venv` 已存在且版本符合時,系統 Python 是 3.10 也算滿足;`.venv` 還不存在時,才需要找一個 3.11+ 的直譯器來建立(PATH 上的 `python3` 不夠新時,檢查 `python3.11`～`python3.14` 或 uv 管理的版本),都沒有就請使用者先手動安裝,不要代為安裝系統層級工具。回報時把「系統 Python 版本」與「`.venv` Python 版本」分開寫。
2. **ComfyUI 原始碼**:clone `https://github.com/comfyanonymous/ComfyUI.git` 到 `<ComfyUI 安裝路徑>`(沒有特殊需求的話,Windows 用 `%USERPROFILE%\ComfyUI`,Mac/Linux 用 `~/ComfyUI`)。已存在(`main.py` 在裡面)就跳過 clone。若 tested-version manifest 有 `comfyui.commit`，clone/fetch 後 checkout 該精確 commit；若欄位仍為 `null`，完成安裝後執行 `git -C <ComfyUI 安裝路徑> rev-parse HEAD` 記錄實際值，保持 manifest 的 pending 狀態直到 smoke test 完成。
    **已存在的安裝**:先記錄 `git -C <ComfyUI 安裝路徑> rev-parse HEAD` 與 `git status --short`。HEAD 跟 manifest 的 `comfyui.commit` 不同時,**不要自己判定「沒關係」,也不要自己 checkout**——使用者可能刻意用別的版本、或有未提交的修改。把兩個 commit 與工作區是否乾淨告訴使用者,讓使用者選:(a) checkout manifest 的 commit(工作區不乾淨時先講清楚會影響什麼);(b) 維持現有版本,但明講這台不是已驗證的版本組合,之後 smoke test 的結果要以這台實際 commit 記錄。注意 manifest 目前的 `verified` 紀錄來自 Windows + CUDA 機器,在其他平台 checkout 同一個 commit 也只代表「版本一致」,不代表該平台已驗證。
3. **Python 虛擬環境**:`<ComfyUI 安裝路徑>/.venv`。已存在就跳過建立,但確認裡面的 python 可以正常執行。
4. **設備偵測**:把這個 repo 的 `tools_src/detect_device.py` 複製到 `<ComfyUI 安裝路徑>/tools/detect_device.py`,執行它；預設會把 `device_config.json` 寫在腳本同一個 `tools/` 目錄，也可用 `--out <明確路徑>` 覆寫。這支腳本本身是固定邏輯,不要修改它。輸出除了 tier，還有模型設定檔要用的平台欄位：`platform_key`（如 `windows-cuda`、`macos-mps`）、`usable_memory_mb`、`memory_kind`、`compute_capability`、`precision_support`；缺這些欄位的舊版 `device_config.json` 一律視為過期，要重跑。
4b. **選擇模型設定檔(下載任何模型之前)**:先把 `tools_src/detect_image_capabilities.py` 與整個 `tools_src/comfyui_pipeline/`(含 `profiles/`)部署到 `<ComfyUI 安裝路徑>/tools/`,執行 `detect_image_capabilities.py --comfyui-path <ComfyUI 安裝路徑> --out <ComfyUI 安裝路徑>/tools/image_capabilities.preview.json`。此時還沒裝模型,只看每份設定檔的 `eligible`/`eligibility_reasons` 與各 task 的 `validation`。**這個階段每個 task 的 `available` 一律是 `false`(模型還沒裝),不能拿來說明設定檔提供什麼**;「提供哪些 task」要讀設定檔 JSON(`tools_src/comfyui_pipeline/profiles/<id>.json`)的 `tasks` 鍵,各 task 的限制見 `skills/comfyui-art-gen/reference/profiles/<id>.md`。把**所有 `eligible: true` 的設定檔**(都算符合這台平台,都要列為選項)、各自提供的 task、在這台平台與記憶體級距的驗證狀態(`verified`/`experimental`/`unverified`)、概估模型空間(見 `skills/comfyui-install/reference/models.md` 各設定檔的空間表)念給使用者,讓使用者選:
    - 預設建議 tier 對應的設定檔(`sdxl_high`/`sdxl`/`sdxl_light` → `sdxl_standard`,`sd15` → `sd15_light`)
    - 使用者想在較大的機器上用較小的管線(例如省空間、只做基礎產圖)可以選較小的,之後步驟 8b 要加 `--default-profile`
    - 不符合平台的設定檔不列為選項;全部都是 `unverified` 時要明講,這台會是該平台的第一台驗證機
    記下選擇與理由,步驟 8 只裝這份設定檔需要的模型。選完即可刪除 preview 檔。
5. **PyTorch**:依 `device_config.json` 裡的 `backend`(`cuda`/`mps`/`cpu`)跟 `torch_index_url` 裝對應版本進 `.venv`。已裝的話檢查版本合理即可,不用強制重裝。
6. **ComfyUI 依賴**:`.venv` 裡 `pip install -r requirements.txt`(在 `<ComfyUI 安裝路徑>` 底下)。**判斷是否已裝好**(不會安裝任何東西):在 `<ComfyUI 安裝路徑>` 底下用 `.venv` 的 Python 執行 `python -m pip install -r requirements.txt --dry-run`,輸出只有 `Requirement already satisfied`、沒有 `Would install` 才算滿足;再執行 `python -m pip check` 確認沒有版本衝突。`--dry-run` 需要 pip 22.2+;pip 太舊或 dry-run 需要連網解析而失敗時,如實回報「無法確認」,不要猜測為已滿足。
7. **Custom nodes**(clone 進 `<ComfyUI 安裝路徑>/custom_nodes/`,已存在就跳過):
   - `ComfyUI-Manager`:`https://github.com/Comfy-Org/ComfyUI-Manager.git`
   - `ComfyUI_IPAdapter_plus`:`https://github.com/cubiq/ComfyUI_IPAdapter_plus.git`
   - `comfyui_controlnet_aux`:`https://github.com/Fannovel16/comfyui_controlnet_aux.git`(提供 `OpenposePreprocessor`、`DepthAnythingV2Preprocessor` 等前處理節點,第 7 章 pose/depth 控制類型要用)
   若 manifest 有對應的 `custom_nodes.<name>.commit`，各 repo 都要 checkout 那個精確 commit；欄位為 `null` 時，安裝後擷取各自的 `git rev-parse HEAD`，不要把 `main` 當成鎖定版本。裝完後確認各自的 `requirements.txt`(如果有)也裝了。`comfyui_controlnet_aux` 的前處理器模型(DWPose、Depth Anything 權重)會在第一次真的執行到的時候自己下載到它自己的 `ckpts/` 資料夾,不用手動預先下載。
   - **Repository 內建 Simple Mask Tool**：把 `tools_src/simple_mask_tool/` 完整複製到 `<ComfyUI 安裝路徑>/custom_nodes/comfyui-simple-mask-tool/`，並把同一資料夾與 `tools_src/mask_session.py` 同步部署到 `<ComfyUI 安裝路徑>/tools/`。它不需要模型或額外 pip 套件，使用 ComfyUI 已有的 `aiohttp`、Pillow 與瀏覽器 Canvas；部署或更新後必須重啟 ComfyUI。這是獨立的本機手動畫遮罩入口，不是 SAM 自動分割，也不得因為未安裝 SAM 而失效。SAM 若另外安裝或開發，只能以標準遮罩檔案／API 作為選配銜接。
   - **SAM 2.1 自動候選遮罩工具**（最後確認：2026-09-05）：把 `tools_src/sam_segment.py` 複製到 `<ComfyUI 安裝路徑>/tools/`。固定使用 Meta 官方 Hugging Face 權重 `facebook/sam2.1-hiera-small`（Apache-2.0，約 184 MB safetensors）；首次執行下載到使用者模型快取。已驗證 PyTorch 2.13.0+cu130、Transformers 5.15.0、RTX 4080 16 GB。它不綁 SDXL／SD1.5，也不依賴 ComfyUI custom node。此 runtime 使用 `float16` 會在 TorchVision NMS 發生 dtype mismatch，因此工具鎖定 `float32`。
8. **模型**:依步驟 4b 選定的設定檔決定要裝哪一組——設定檔 JSON 的 `models` 列出每顆模型的檔名與子資料夾,標 `optional` 的依使用者要用的功能逐項詢問(例如不需要姿勢控制就先不裝 OpenPose/Depth),`experimental` 的只有使用者明確要做 A/B 才裝。**這件事不是只有底模(checkpoint)要跟著 tier 換,ControlNet/IPAdapter/CLIP Vision 全部都是跟底模綁定的,底模架構變了,這些都要跟著換成對應版本,不能只換 checkpoint、其他照抄。** 完整清單(SDXL 家族的檔名/下載來源表,以及 sd15 tier 的處理方式)見 `skills/comfyui-install/reference/models.md`——那是安裝流程的模型家族、檔名與來源基準，不是 hash-level 的可重現版本鎖定；真正可重現的 commit、套件版本與模型 SHA-256 以 `docs/tested-versions.md` 為準。若 manifest 仍是 `pending_on_installed_machine`，不要把表格裡的歷史日期、檔名或大小當成已鎖定版本，也不要自行換成更新模型；真的想評估升級用 `skills/comfyui-pipeline-review/SKILL.md`,不是安裝流程該做的事。每個實際使用的模型都要在 manifest 記錄檔案路徑、模型家族、來源與 SHA-256；目前 manifest 未擷取完成前不可捏造 hash。
8b. **圖片能力偵測**(模型與 custom node 都裝好、ComfyUI 啟動後):把 `tools_src/detect_image_capabilities.py` 與整個 `tools_src/comfyui_pipeline/`（含 `profiles/`）複製到 `<ComfyUI 安裝路徑>/tools/`，用 `.venv` 執行 `detect_image_capabilities.py --comfyui-path <ComfyUI 安裝路徑>`；ComfyUI 已啟動時加 `--comfy-url http://127.0.0.1:<port>` 一併檢查 custom node。模型放在共享模型庫時用 `--model-root` 指定（可重複）。輸出預設 `<ComfyUI 安裝路徑>/tools/image_capabilities.json`，已有檔案需明確給 `--overwrite`。它**不下載任何東西**，只回報每份設定檔是否符合這台平台、裝了哪些模型、每個 task 是否可用（缺哪個模型/node）與驗證狀態（`verified`／`experimental`／`unverified`，記憶體低於驗證值或該平台沒有紀錄時會自動降為 `unverified`）。把不可用的 task 與 `unverified` 狀態如實告訴使用者，不要因為模型裝了就宣稱已驗證。`default_profile` 預設是 tier 對應且底模已裝的設定檔；使用者明確想在較大的機器上用較小的管線時，才加 `--default-profile <設定檔 id>`（例如 `sd15_light`），它必須符合這台平台且底模已安裝，否則工具會拒絕，不會自動換成別的設定檔。
9. **影片能力偵測(只有要開影片時)**:把 `tools_src/detect_video_capabilities.py` 與 `tools_src/generate.py` 複製到 `<ComfyUI 安裝路徑>/tools/`，等 ComfyUI、custom nodes、影片模型與 `.venv` 都確認存在後，使用該 `.venv` 執行 detector。可帶 `--comfy-url http://127.0.0.1:<port>` 檢查 `/object_info`，也可省略 URL 先只掃描檔案/runtime；偵測器**不會下載模型、套件或前處理權重**。不給 `--default-backend` 就把 `default_backend` 保持 `null`，每次 CLI 必須明確給 `--backend`；若明確給 `--default-backend h3|wan`，它必須是這台機器已完整具備的 backend。`pose`/`depth` 的 `comfyui_controlnet_aux` 前處理模型若尚未在 `ckpts/`，先停下告知使用者，不能讓 smoke test 靜默觸發大型下載。輸出預設是 `<ComfyUI 安裝路徑>/tools/video_capabilities.json`，已有檔案時需明確給 `--overwrite`。
偵測器預設只記錄既有模型的 `size_bytes`，避免每次對 80+ GiB 重算 SHA-256；只有明確給 `--hash-models` 才計算並寫入 SHA-256。

10. **產圖腳本**:把 `tools_src/generate.py` 複製(覆蓋)到 `<ComfyUI 安裝路徑>/tools/generate.py`——**這支永遠以 repo 裡的原始碼為準**,不要在部署副本上直接改邏輯。影片 detector 也要跟 source 同步部署。
    使用極簡遮罩頁面時，`tools_src/mask_session.py` 與整個 `tools_src/simple_mask_tool/` 也必須同步到 `<ComfyUI 安裝路徑>/tools/`；不能只部署 facade，否則 `mask_session.py` 找不到 client/core 模組。
    使用 SAM 自動候選遮罩時，`tools_src/sam_segment.py` 也必須同步到 `<ComfyUI 安裝路徑>/tools/`，並實際跑一次模型下載與圖片 smoke test；只確認 Python import 不算安裝完成。
11. **啟動用的小捷徑**(方便使用者之後自己開伺服器,不一定要是腳本,一行指令也行):在 `<ComfyUI 安裝路徑>` 附近留一個能一鍵/一行啟動 `main.py --listen 127.0.0.1 --port <port>` 的方式。**先確認 port 8188 沒被佔用**(例如這台機器如果已經裝了 ComfyUI 桌面版且常駐執行,要換別的 port,如 8189)。把最後使用的 URL 寫入 `local_config.json`；產圖 CLI 不會自動猜測部署副本旁的 repo 設定。
12. **寫入 repo 根目錄的 `local_config.json`**(不進版控,每台機器內容不同):
    ```json
    {
      "comfyui_path": "<ComfyUI 安裝路徑>",
      "python_exe": "<.venv 裡 python 執行檔的完整路徑>",
      "generate_script": "<ComfyUI 安裝路徑>/tools/generate.py",
      "image_config": "<ComfyUI 安裝路徑>/tools/image_capabilities.json",
      "video_config": "<ComfyUI 安裝路徑>/tools/video_capabilities.json",
      "comfyui_url": "http://127.0.0.1:<實際用的 port>",
      "start_script": "<步驟 11 的啟動方式,路徑或指令>",
      "output_dir": "<這個 repo 根目錄>/output"
    }
    ```
    執行 task 時要把這個 URL 明確傳給 `generate.py`：可用 `--comfy-url <URL>`，或 `--config <此檔案>`；也可在執行環境設定 `COMFY_URL`/`COMFYUI_URL`。等待上限用 `--timeout <秒數>` 覆寫，必須是有限正數；它不是 ComfyUI server 的 port，也不會改變模型本身的生成步數。
13. **離線部署驗證**:在 repo 根目錄執行 `python tools_src/verify_portable_install.py --repo-root . --config local_config.json`；有安裝影片能力時再加 `--require-video`；已跑過步驟 8b 時加 `--require-image`，驗證 `image_capabilities.json` 的設備指紋沒過期、`default_profile` 符合這台平台且底模檔案存在（沒加這個旗標時，檔案存在也會驗證，不存在只列 INFO）。這支工具不下載、不覆寫設定，也不要求來源機與目標機使用同一個 GPU/tier；它會用目前設備重新執行硬體偵測，確認 `device_config.json` 是針對這台機器產生，並核對 repo／ComfyUI 內的 `generate.py`、`detect_device.py`（影片模式再加 `detect_video_capabilities.py`）沒有版本漂移。影片模式也會交叉檢查 capability config 內嵌的設備資料、ComfyUI/Python 路徑、可用 backend 與實際模型檔。任何 FAIL 都要先修正再做 smoke test。

    離線驗證通過只代表「部署內容與動態選型規則一致」，不代表不同 GPU 的生成結果逐位元相同，也不取代版本／模型 hash 與實際輸出的驗收。之後仍須依 `docs/tested-versions.md` 核對目標 tier 的 commit、模型 SHA-256，並完成至少一次圖片與影片 smoke test。

## 進階(選配):LoRA 訓練工具

### 產線模組部署補充

`tools_src/generate.py` 是維持既有 CLI/API 相容性的 facade；圖片 graph、影片 catalog、不吃 runtime 狀態的影片 helper 分別位於 `tools_src/comfyui_pipeline/image_graphs.py`、`video_catalog.py`、`video_graphs.py`。圖片模型檔名與取樣參數則放在 `comfyui_pipeline/profiles.py` 讀取的 `comfyui_pipeline/profiles/*.json` 模型設定檔。部署時必須把整個資料夾（含 `profiles/`）同步到 `<ComfyUI 安裝路徑>/tools/comfyui_pipeline/`，不能只複製 `generate.py`；少了設定檔，`generate.py` 會在匯入時直接報錯。離線部署驗證會同時核對這五個模組檔案，以及部署端 `profiles/*.json` 與 repo 完全一致（少檔、多出舊檔或內容不同都算 FAIL），確保換設備後仍由該機器自己的 `device_config.json` 與 `image_capabilities.json` 動態選擇圖片模型設定檔與解析度。真正組 ComfyUI graph 又要吃機器 capability config(`ACTIVE_VIDEO_CONFIG`)的影片 builder(`build_img2video_wan/h3` 等)仍留在 `generate.py` 裡,不在 `comfyui_pipeline/` 套件內。

**只有使用者明確要準備訓練角色/風格 LoRA 時才裝,不是每台機器的基本配備。** 跟 ComfyUI 完全獨立的另一套工具(`kohya_ss`),裝法跟已知的編碼/踩坑細節見 `skills/comfyui-install/reference/lora-training.md`。

## 進階(選配):風格底模(`--style`)

**只有使用者明確要用 `generate.py` 的 `--style` 切換風格才裝,不是每台機器的基本配備。** 只在選用 `sdxl_standard` 設定檔的機器才問,`sd15_light` 不提。

三個候選(寫實/插畫/二次元)清單、檔名、授權注意事項見 `skills/comfyui-install/reference/models.md`「選用風格底模」那段。流程:

1. 先問使用者要哪幾個風格方向,不用三個全裝
2. **動手下載任何一顆之前,先告知該顆的檔名跟概估大小(每顆 ~6.5~7GB),加總這台機器目前已用空間 + 想裝的這幾顆,確認硬碟還有沒有足夠可用空間**——原則同前面「開始裝之前先告知硬碟空間需求」,不是另一套邏輯
3. 下載到 `<ComfyUI 安裝路徑>/models/checkpoints/`,不用額外裝 ControlNet/IPAdapter/CLIP Vision(這些綁的是 SDXL 架構,不是特定微調版,現有那份就夠用)
4. 裝完不用改程式碼(檔名定義在 `sdxl_standard.json` 的 `variants`),使用者之後用 `--style realistic`/`illustration`/`anime` 就能直接切換;各風格的 prompt 眉角見 `skills/comfyui-art-gen/reference/profiles/sdxl_standard.md`

## 進階(選配):影片模型(`img2video` / `character_video`)

**只有使用者明確要產短片才裝,不是每台機器的基本配備。** 跟 SDXL 完全不同的一組模型,清單/大小見 `skills/comfyui-install/reference/models.md`「選用影片模型」。該段的日期與大小是歷史安裝/實測紀錄，不等於已捕捉的可重現版本；實際 ComfyUI、PyAV、模型 SHA-256 與影片 smoke test 要填回 [`docs/tested-versions.md`](../../docs/tested-versions.md)，在 `pending_on_installed_machine` 期間不可捏造或宣稱已鎖定。動手下載前先講空間(Wan + H3 FL2VA 約 56GB;若要 `character_video` / h3 的 `pose_drive` 再加 H3 Ref2VA ~19.5GB,合計約 76GB)。不要把影片 checkpoint 寫進 `device_config.json` 的圖片 `CKPT` 欄位。h3 的角色參考跟動作驅動都用 Ref2VA UNET(跟 I2V 那顆 FL2VA 不同),對照表見 `skills/comfyui-video-gen/reference/backends.md`。

## 進階（選配）：FLUX.2 Klein 4B PoC

只有使用者明確核准 `flux2_concept` / `flux2_edit` 實驗路線才安裝。它是跟 SDXL 平行的 diffusion model + Qwen text encoder + FLUX.2 VAE 組合，不是 `device_config.json` 的 checkpoint，也不能沿用 SDXL ControlNet/IPAdapter/LoRA/`--style`。四個模型合計約 15.4 GiB，精確檔名、來源、bytes 與架構邊界見 `skills/comfyui-install/reference/models.md`「選用 FLUX.2 Klein 4B PoC」。安裝前確認空間，安裝後確認 ComfyUI `/object_info` 有 `EmptyFlux2LatentImage`、`Flux2Scheduler`、`ReferenceLatent` 等 Core 節點，再部署完整 `tools/` 模組並各跑一次 text-to-image 與 image-edit smoke；兩個都通過前保持實驗狀態。

## 進階（選配）：BiRefNet 變體 benchmark

只有使用者明確核准重新評估去背模型時才下載 general／HR／HR-matting／dynamic 四份官方 Hugging Face snapshot，並安裝 manifest 鎖定的 `timm`。模型位置、原生推論尺寸、Core loader 固定 1024 的限制與指令見 `skills/comfyui-install/reference/models.md`「選用 BiRefNet A/B benchmark 權重」。這是維護 benchmark，不是新的美術 task；先用固定資料集跑 `tools_src/benchmark_birefnet.py`，有穩定勝者才另開正式整合，不直接覆蓋 `birefnet.safetensors`。

## 執行原則

- **冪等**:每一步先檢查是否已經成立,成立就跳過,不要盲目重跑或覆蓋使用者已經調整過的東西(`generate.py` 除外——它永遠要跟 repo 同步)
- **換機器/換顯卡**:至少重跑步驟 4(設備偵測)、步驟 8b(圖片能力偵測)、步驟 9(影片 capability 若有使用)、步驟 12(重寫 `local_config.json`)與步驟 13(離線部署驗證),不要假設 checkpoint、tier、預設解析度、backend 或路徑沒變；若 tier 變成 `sd15`，先看 `skills/comfyui-art-gen/SKILL.md`「這台機器能跑什麼」小節與 `sd15_light` 設定檔提供的 task，ControlNet/IPAdapter/CLIP Vision 不可沿用 SDXL 版本。
- **下載失敗/網路受限**:如實回報,不要用假路徑頂替或假裝下載成功
- **版本收尾**:完成安裝後擷取 ComfyUI/custom node commit、Python/PyTorch/Pillow 版本、實際模型 SHA-256，再記錄至少一次實機 smoke test 的日期、指令與輸出；在這些資料齊全前，manifest 保持 `pending_on_installed_machine`。
- **平台驗證紀錄**:smoke test 與人工驗收通過的 task,依 `skills/comfyui-new-tool-checklist/SKILL.md`「情境 C」更新設定檔的 `validation`(記錄 `platform_key` 與這台的 `usable_memory_mb`)並附上證據;只跑出檔案、沒做人工驗收的不能標 `verified`。
- **收尾**:全部完成後,把最終的 `local_config.json` 內容念給使用者確認一次,並**分三層回報**,不要混成一句「裝好了」:
    1. **部署結構**:`verify_portable_install.py` 的結果(PASS 只代表原始碼同步、設備快照沒過期)
    2. **可用範圍**:`image_capabilities.json`(與 `video_capabilities.json`)列出的 `default_profile`、可用 task、不可用 task 與缺什麼
    3. **實機驗證**:這次實際 smoke test 並人工驗收過的 task,以及各 task 在這台平台的驗證狀態(`verified`/`experimental`/`unverified`)
    接著提醒使用者下一步可以直接用自然語言要求產圖(見 `skills/comfyui-art-gen/SKILL.md`)。若這台機器沒有可用的 ComfyUI/模型，就只能完成文件與離線檢查，必須明確回報尚未 deploy/smoke test。
