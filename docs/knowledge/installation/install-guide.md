---
type: guide
status: current
---
# ComfyUI 產線安裝：目標清單與判斷

給任何操作這個 repo 的 agent 用。**這是目標清單，不是固定腳本**：硬體與既有狀態組合太多，腳本只會長出特例分支；安裝是一次性任務，值得用判斷力換彈性。每一步先看「這件事現在是否已成立」，成立就跳過（冪等），不成立才補。遇到機器特有的狀況（網路擋下載、殘留安裝、CUDA 版本、權限），如實說明並想辦法繞過，不靜默失敗、不編造結果。

## 何時進入安裝

只有使用者明確要求安裝本機 ComfyUI，或已選定需本機 ComfyUI 的路線而依賴缺失時。缺 `local_config.json` 本身不代表要安裝；還沒選路線先走[初始化](initialization.md)。需求整理、平台圖片、不經 ComfyUI 的本機工具不需要這份文件。

## 開始前

1. 讀 [已驗證版本](../../tested-versions.md)：它是已驗證版本的紀錄格式，不是「最新版」清單。`capture_status` 為 `verified` 就 checkout 精確 commit；仍是 `pending_on_installed_machine` 可以裝，但要在同一台機器 smoke 後擷取實際 commit、套件版本與模型 SHA-256，不填猜測值。
2. 已存在的 ComfyUI：記錄 `git rev-parse HEAD` 與 `git status --short`。與基準不同時**不要自己判定沒關係，也不要自己 checkout**，把差異告訴使用者讓他選：(a) checkout 基準 commit；(b) 維持現狀，但明講這台不是已驗證組合。基準的驗證來自 Windows＋CUDA，其他平台 checkout 同 commit 只代表版本一致。
3. **先告知磁碟空間**再下載任何東西，概估見 [模型清單](models-and-sources.md)「硬碟空間概估」；不要裝到一半才發現空間不夠。

## 目標（依本次選定的能力完成適用項目）

1. **前置**：`git` 在 PATH；ComfyUI 實際用 `.venv`，判斷標準是 `.venv` 的 Python 為 3.11 以上（系統 Python 只用來建 `.venv`）。沒有合適的直譯器就請使用者先裝，不代裝系統層級工具。回報時系統 Python 與 `.venv` Python 分開寫。
2. **ComfyUI 原始碼**到 `<ComfyUI>`，已存在就跳過 clone。
3. **虛擬環境** `<ComfyUI>/.venv`。
4. **設備偵測**：執行 `detect_device.py`（`gameart.py detect-device`）產生機器專用的 `device_config.json`（平台、可用記憶體、精度、tier）。缺平台欄位的舊檔視為過期。
5. **選擇模型設定檔**（下載模型之前）：用 `detect-image` 預覽哪些設定檔符合這台平台、提供哪些 task、驗證狀態、概估空間，念給使用者選。tier 與設定檔 id 是兩套名稱；目前只有 `sdxl_standard` 一份設定檔。
6. **PyTorch**：依 `device_config.json` 的 `backend` 與 `torch_index_url` 裝對應版本；已裝且版本合理就不重裝。
7. **ComfyUI 依賴**：判斷是否已滿足用 `pip install -r requirements.txt --dry-run` 加 `pip check`（只讀）；無法確認就如實說無法確認。
8. **Custom nodes 與本機工具**，只裝本次所選功能需要的：
   - 外部節點 clone 到 `custom_nodes/`：ComfyUI-Manager、ComfyUI_IPAdapter_plus、comfyui_controlnet_aux（姿勢與深度前處理）。有基準 commit 就 checkout 精確 commit，不把 `main` 當鎖定版本。macOS 上 controlnet_aux 的 `onnxruntime-gpu` 沒有 arm64 wheel，改裝 `onnxruntime`，不改 custom node 的 requirements。
   - 手繪遮罩（Simple Mask）、邊界貼合（OpenCV）、SAM 候選的準備與部署見 [遮罩](../art/masking.md)、[SAM 候選](../art/sam-segmentation.md)；它們獨立於生成模型，缺 SAM 不影響手繪。
9. **模型**：先檢查 `extra_model_paths.yaml`，共享模型庫已有且 hash 一致就沿用，不重複下載；同名但 hash 或大小不同的另裝到本機 `models/` 並告知差異。依第 5 步選定的設定檔裝它需要的組，`optional` 的逐項問使用者（例如不需要姿勢控制就先不裝 OpenPose／Depth）。底模與 ControlNet／IPAdapter／CLIP Vision 都綁定同一模型家族，不能只換 checkpoint。檔名與來源基準見 [模型清單](models-and-sources.md)；**看到較新的模型也不自作主張替換**（升級評估是另一件需要使用者明確觸發的工作）。
10. **能力偵測**：圖片 `detect-image`（ComfyUI 啟動後加 `--comfy-url` 一併查 custom node）；要開影片才跑 `detect-video`。它們只掃描、不下載；快照缺失、過期或不可用的 task 如實告知，不因模型裝了就宣稱已驗證。使用者要在大機器上用較小設定檔才加 `--default-profile`。
11. **部署 repo 工具**：`python tools_src/gameart.py deploy`（先 dry run 確認計畫，再 `--yes`）。清單由 `deploy_manifest.py` 單一定義，包含 `generate.py` 與整個 `comfyui_pipeline/`（含 `profiles/`）、`templates/`、單檔工具與已安裝的 custom node。寫入前備份、寫入後驗證、失敗自動還原（`--rollback`、`--list-backups`）。**永遠以 repo 原始碼為準**，不在部署副本上改邏輯；有 custom node 變更要在 queue 為空時重啟 ComfyUI。
12. **啟動方式與 `local_config.json`**：留一個一行就能啟動的方式（先確認 8188 沒被其他 ComfyUI 佔用，必要時換 port）；把路徑與最後使用的 URL 寫進 repo 根目錄的 `local_config.json`（不進版控，欄位見 `art-generation.md` 的環境段）。
13. **離線部署驗證**：`gameart.py verify-install`（有影片能力加 `--require-video`，有圖片快照加 `--require-image`）。它不下載、不覆寫，只核對部署內容、設備快照與版本漂移。通過只代表部署一致，不代表生成結果相同，也不取代 hash 與實際輸出的驗收。

## 選配項目（使用者明確要才裝）

- **LoRA 訓練工具**：獨立的 kohya_ss，見 [LoRA](lora-training.md)。
- **風格底模**（`--style`）：寫實、插畫、二次元三選項，各約 7 GB，只選要的；不需額外裝 ControlNet 等。授權注意見模型清單。
- **影片模型**：與 SDXL 完全不同的一組。Wan＋H3 約 56 GB，加 Ref2VA 約 76 GB；不要把影片 checkpoint 寫進圖片的 checkpoint 欄位。
- **FLUX.2 Klein 4B**：實驗路線，四個模型約 15.4 GiB；確認 `/object_info` 有 `EmptyFlux2LatentImage`、`Flux2Scheduler`、`ReferenceLatent` 等 Core 節點，各跑一次文字生圖與圖片編修 smoke 才算通過，通過前保持實驗狀態。
- **Wan Animate／SCAIL-2**：獨立的 template 路線，安裝 pin 見 [安裝紀錄](../video/wan-animate-install.md)。
- **BiRefNet 變體 benchmark**：維護者用，先經使用者核准。

## 收尾

- 換機或換顯卡：重跑設備偵測、圖片與影片能力偵測，重寫 `local_config.json`，再做離線驗證；不假設 checkpoint、tier、解析度、backend 或路徑沒變。
- 下載失敗或網路受限：如實回報，不用假路徑頂替。
- 版本收尾：擷取 ComfyUI／custom node commit、Python／PyTorch／Pillow 版本、實際模型 SHA-256，並記錄至少一次實機 smoke（日期、指令、輸出）；齊全前該機器的紀錄保持 `pending_on_installed_machine`，不覆寫其他機器的證據。
- smoke 與人工驗收通過的 task，依[新增能力清單](../maintenance/new-capability-checklist.md)「情境 C」更新設定檔的 `validation`；只跑出檔案、沒人工驗收的不能標 `verified`。
- **分三層回報**，不要混成一句「裝好了」：部署結構（`verify-install` 結果）、可用範圍（能力快照列的 default profile 與可用、不可用 task）、實機驗證（實際跑過並驗收的 task 與其驗證狀態）。最後念出 `local_config.json` 內容請使用者確認。

## 機器等級與舊部署的殘留

- 設備偵測不再有低記憶體的舊架構 tier：顯卡可用記憶體低於 8000 MB（包含只有 CPU、或讀不到 Apple 記憶體）時 `device_config.json` 的 tier 是 `null`。圖片 task 會在上傳前停下並建議改用 [platform-image-gen](../../../skills/platform-image-gen/SKILL.md)，**不會自動降級**；不要手改 `device_config.json` 湊出 tier。
- 圖片 graph 的唯一來源是 `templates/`；Python graph builder 已移除，只剩驗證函式與常數的小模組。部署時 `templates/` 必須一併同步（`gameart.py deploy` 已包含）。
- Video Layers 共用的影片檢查、音訊編碼與時間軸 helper 已搬到 `tools_src/comfyui_video_layers/source_media.py`；升級後要重新 `deploy`，並在 queue 為空時重啟 ComfyUI、重做 preflight。
- 已移除的影片人臉替換功能，如果這台機器的 ComfyUI 端還留著舊的部署副本（`tools/` 底下的 人臉替換的 client 與 package、`custom_nodes/` 底下的對應節點資料夾），`deploy` 不會清掉它們，由使用者自行刪除；刪 custom node 後要重啟 ComfyUI。
