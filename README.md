# ComfyUI AI 產圖與視覺素材工作流

用 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 建立可控、可重複、方便維護的 AI 圖像生成與視覺素材產線，適用於概念圖、角色、圖示、介面元件、產品視覺與其他影像素材。

這個 repository（儲存庫）同時保存環境建置紀錄、產圖流程說明，以及一支把固定工作流封裝成 CLI（命令列介面）的穩定產圖腳本。它也提供給 AI agent（AI 代理）使用的任務判斷與操作規則，因此可以直接用自然語言控制這條產圖產線：AI agent 會判斷需求、準備結構化參數、呼叫固定流程，並把結果存回指定的 `output/` 資料夾。使用者不需要每次從零拉節點；維護者才需要深入調整 ComfyUI graph（節點圖）。

產線的可重現性以 [`docs/tested-versions.md`](docs/tested-versions.md) 為準。它只記錄已在同一台機器上驗證過的 commit、套件版本與模型 SHA-256；目前 manifest 仍是「待在已安裝機器擷取」，不能把未查證的版本或 hash 當成已驗證基準。

## AI agent 操作模式

這個專案的目標不只是「學會使用 ComfyUI」，而是讓 AI agent 成為視覺素材產線的操作入口。使用者可以直接描述需求，例如：

- 「幫我做一個可放到產品介面上的魔法水晶圖示。」
- 「把這張角色草稿精緻化，保留原本構圖。」
- 「把這張圖的武器換掉，但手部握姿不要變。」
- 「把定稿的 UI 合成圖拆出外框與中心鈕兩個透明圖層。」

AI agent 會依照 [`skills/comfyui-art-gen/SKILL.md`](skills/comfyui-art-gen/SKILL.md) 選擇 `concept`、`icon_asset`、`refine`、`guided_inpaint` 或 `layer_split` 等任務，向使用者索取必要的參考圖／遮罩，然後呼叫 [`tools_src/generate.py`](tools_src/generate.py)。產圖邏輯集中在固定腳本中，讓結果可重複、可追蹤，也避免每次由 AI 臨時拼接不同的 ComfyUI 節點圖。

## 可以做什麼

- 文生圖（`concept`）：從文字產生概念圖
- 圖示素材（`icon_asset`）：產生單一、置中、透明背景的 UI 圖示或小型物件
- 圖生圖（`refine`）：將草稿精緻化，或製作材質／顏色變體
- 局部重繪（`inpaint`）：只修改指定區域
- 結構鎖定局部重繪（`guided_inpaint`）：換武器、道具或材質時保留姿勢與輪廓
- 圖層拆分（`layer_split`）：把定稿合成圖依遮罩切成對齊的透明圖層，不重新生成內容
- ControlNet：使用 `canny`、`pose`、`depth` 控制構圖與姿勢
- IPAdapter／LoRA：維持角色或美術風格一致性
- 風格底模切換（`--style`）：選擇寫實、插畫或動漫風格
- 放大精修（`upscale`）：放大圖片並補充細節
- 批次生成（batch）與固定 seed，方便探索與重複產出
- 去背（`--remove-bg`），輸出透明背景素材

## 快速開始

### 1. 取得專案

```bash
git clone https://github.com/s0917251664/comfyui-game-art-tutorial.git
cd comfyui-game-art-tutorial
```

### 2. 建置 ComfyUI 產線

請依照 [ComfyUI 安裝流程](skills/comfyui-install/SKILL.md) 準備：

- ComfyUI 原始碼與 Python virtual environment（虛擬環境）
- 依顯示卡能力選擇的 checkpoint（底模）
- ControlNet、IPAdapter 與其他必要的 custom nodes（自訂節點）
- 設備偵測結果 `device_config.json`
- 本機專用設定 `local_config.json`

完整的硬體、模型、啟動方式與操作教學請看 [`教學.md`](教學.md)。

### 3. 啟動 ComfyUI

使用 `local_config.json` 中的 `start_script` 啟動 ComfyUI，並確認 `comfyui_url` 對應的服務正在執行。不同電腦的安裝路徑與 port（連接埠）可能不同，不要直接照抄其他機器的路徑。產圖腳本不會猜測或自動搜尋 `local_config.json`；執行時要明確傳入 `--comfy-url`，或用 `--config local_config.json`、`COMFY_URL`/`COMFYUI_URL` 指定服務位置。

### 4. 產生第一張圖

產圖腳本的原始碼在 [`tools_src/generate.py`](tools_src/generate.py)。安裝流程會把它部署到 ComfyUI 的 `tools/generate.py`；執行時使用 `local_config.json` 指定的 Python 與部署路徑：

```bash
<python_exe> <generate_script> concept --prompt "a female game character concept art, fantasy armor, standing pose, clean studio background" --comfy-url "<comfyui_url>" --timeout 180 --output-dir "<repo>/output"
```

腳本執行完成後會把產出的圖片存回 repository 的 `output/` 資料夾。`--timeout` 是 prompt 送達 ComfyUI 後輪詢生成結果的上限（秒），必須是正數；上傳、送出與下載各自另有不超過 30 秒的 HTTP request timeout，因此它不是整支 CLI 的 wall-clock（牆鐘時間）上限。CPU、批次生成或放大任務可依實際耗時調高。沒有 ComfyUI 服務時，CLI 會在送出前失敗，不會把產圖當成已完成。

也可以直接在 ComfyUI 網頁介面載入工作流（工作流檔不由本 repository 提供，詳見下方「工作流與 clone」）。

產生 UI 圖示時可以使用 `icon_asset`。它會固定加入單一置中物件與簡潔背景的引導，並且永遠輸出透明背景：

```bash
<python_exe> <generate_script> icon_asset --prompt "a magical blue gemstone" --comfy-url "<comfyui_url>" --timeout 180 --output-dir "<repo>/output"
```

如果圖示的幾何結構或色塊配置已經有明確答案，可以提供 `--structure-ref <template>` 範本圖；如果只想參考另一張圖的材質與質感，使用 `--appearance-ref <image>`。完整規則請看 [圖示結構參考說明](skills/comfyui-art-gen/reference/structure-ref.md)。

## 產圖任務選擇

| 使用情境 | task（任務） | 必要輸入 |
|---|---|---|
| 從文字發想新圖 | `concept` | prompt |
| 產生單一 UI 圖示或小型物件 | `icon_asset` | prompt；可選結構／外觀參考圖；永遠透明背景 |
| 照姿勢或線稿產圖 | `pose_only` | prompt、姿勢／線稿參考圖 |
| 保持角色或風格一致，姿勢自由 | `style_lock` | prompt、角色／風格參考圖 |
| 同時保持角色與指定姿勢 | `character_action` | prompt、角色參考圖、姿勢參考圖 |
| 草稿精緻化或材質變體 | `refine` | prompt、來源圖 |
| 修正圖片局部 | `inpaint` | prompt、來源圖、遮罩圖 |
| 修改外觀但鎖定結構 | `guided_inpaint` | prompt、來源圖、遮罩圖；可選 ControlNet／外觀參考圖 |
| 放大並補細節 | `upscale` | prompt、來源圖 |
| 從定稿圖拆出一個透明圖層 | `layer_split` | 定稿圖、遮罩圖、圖層名稱 |

需要選擇哪個 task、遮罩格式、參數界線以及 URL/timeout 設定時，請看 [`skills/comfyui-art-gen/SKILL.md`](skills/comfyui-art-gen/SKILL.md) 與 [`完整參數規格`](skills/comfyui-art-gen/reference/full-params.md)。

除 `layer_split` 外，各產圖任務都可以視需要使用 `--style realistic|illustration|anime` 切換風格底模；`--rating safe|questionable|explicit` 只適用於 `anime` 與 `illustration`，而且是模型提示標籤，不是內容審核機制。對應模型必須先依安裝文件準備好。

### CLI 設定來源與參數界線

`--comfy-url URL`、`--config PATH`、`--timeout SEC` 是執行環境設定。URL 優先順序是 CLI → `COMFY_URL`/`COMFYUI_URL` → 明確指定的 runtime config（`--config` 或 `COMFY_CONFIG`/`COMFYUI_CONFIG`/`COMFY_CONFIG_PATH`）；沒有任何來源時直接報錯。runtime config 至少要有 `comfyui_url`（`comfy_url` 也可相容），不會因為部署副本位於 ComfyUI 目錄就自動讀 repository 的 `local_config.json`。

產圖參數會在送出前檢查：尺寸必須是正整數且為 8 的倍數；`batch` 必須 ≥1；`denoise`、`ip-weight`、`pose-strength`、`control-strength`、`appearance-weight`、`lora-strength` 必須落在 0..1；`scale` 必須大於 0 且不超過 4；`timeout` 必須是有限正數。超出界線會立即拒絕，不會先上傳參考圖或建立 ComfyUI 佇列。

### SD1.5 能力範圍

目前 SD1.5 tier 只可使用不依賴 SDXL add-on 的基礎路徑（例如 `concept`、`refine`、一般 `inpaint`、`upscale`，以及不帶額外參考圖的 `icon_asset`）。`pose_only`、`style_lock`、`character_action`，以及使用 `structure-ref`/`appearance-ref` 或 ControlNet/IPAdapter 的 `icon_asset`、`guided_inpaint` 仍需要 SDXL 家族模型；腳本會在上傳或排隊前拒絕這些組合。`--style` 的三個風格 checkpoint 也只支援 SDXL tier。這不是 SD1.5 模型已完成相容性驗證；若要擴充，必須另找對應的 SD1.5 ControlNet/IPAdapter/CLIP Vision 並完成實機驗證。

### 本機檢查與測試

不需要 GPU 或 ComfyUI 服務即可在 repository 根目錄執行：

```bash
python -m compileall -q tools_src tests
python -m unittest discover -s tests -p 'test_*.py' -v
```

這些是 CI 的基本檢查；測試會 mock HTTP/模型邊界，不等同於真正生成圖片。要驗證節點、模型載入、圖片尺寸與 alpha，仍要在有 `local_config.json` 和已安裝 ComfyUI 的機器上做 smoke test，並把結果記到版本 manifest。

## Repository 結構

```text
.
├── 教學.md                              # 完整建置與操作教學
├── tools_src/
│   ├── detect_device.py                 # 偵測 GPU／VRAM／作業系統能力
│   └── generate.py                      # 穩定產圖腳本的原始碼
├── skills/
│   ├── comfyui-art-gen/                 # AI agent 的需求判斷與產圖流程
│   │   └── reference/                   # 遮罩、結構範本、參數與已知限制
│   ├── comfyui-install/                 # 新機器安裝檢查清單
│   ├── comfyui-new-tool-checklist/      # 新增工具或技術時的檢查清單
│   └── comfyui-pipeline-review/         # 明確要求升級盤點時使用
├── docs/
│   └── tested-versions.md                # 已驗證版本與模型 hash 的紀錄格式
├── .github/workflows/ci.yml              # compileall + stdlib unittest
├── output/                              # 本機產出；只保留 .gitkeep
├── 第一張測試圖.png                      # 初次建置驗證用範例
└── README.md
```

## 重要檔案與版本管理規則

- `tools_src/generate.py` 是產圖腳本的唯一原始碼；不要直接修改 ComfyUI 安裝目錄裡的部署副本。
- `local_config.json` 包含每台機器的實際路徑，已排除在 Git 版本控制之外；請在 CLI 明確傳入 `--comfy-url` 或 `--config`，不要依賴部署副本自行猜路徑。
- `workflows/` 是本機 ComfyUI workflow 參考檔，刻意不進 Git；新 clone 不會帶這些 JSON，換機器時需從已安裝機器匯出/複製，或直接依 CLI 流程操作。
- `output/` 的生成結果預設不進 Git，避免把大型或含私人內容的素材意外提交。
- 更換電腦或顯示卡後，至少重新執行 `detect_device.py`，不要假設 checkpoint 與解析度仍然相同。
- ComfyUI、custom node、Python/PyTorch/Pillow 與模型版本以 [`docs/tested-versions.md`](docs/tested-versions.md) 的已驗證 manifest 為準；未擷取完成前要保留 pending 狀態。

## 文件導覽

- [完整教學](教學.md)：從名詞、安裝、模型到各種產圖情境
- [產圖流程](skills/comfyui-art-gen/SKILL.md)：如何把需求分類並呼叫正確 task
- [安裝流程](skills/comfyui-install/SKILL.md)：新機器的環境與模型準備
- [模型清單](skills/comfyui-install/reference/models.md)：固定版本與硬碟空間估算
- [已驗證版本清單](docs/tested-versions.md)：版本、commit、模型 SHA-256 與 smoke test 紀錄格式
- [CI 基本檢查](.github/workflows/ci.yml)：`compileall` 與 Python 標準庫 `unittest`
- [圖示結構範本](skills/comfyui-art-gen/reference/structure-ref.md)：`icon_asset --structure-ref` 與圖層拆分
- [複合元件圖層](skills/comfyui-art-gen/reference/layered-assets.md)：重複元素與 UI 元件的拆分策略
- [已知限制](skills/comfyui-art-gen/reference/known-limitations.md)：目前能力邊界與常見失敗情況

## 授權與第三方模型

本 repository 目前沒有附加 repository-level `LICENSE`（授權檔），因此其中的程式碼、文件與圖片不應被視為可任意再利用。ComfyUI、custom nodes、checkpoint、ControlNet、IPAdapter、LoRA 與其他模型，請分別遵守各自上游專案或模型發布者的授權條款。

## 工作流與 clone

`workflows/` 只屬於維護者在本機用來開啟、除錯與對照的 ComfyUI JSON，已由 `.gitignore` 排除。它不會隨 `git clone` 提供，也不應在文件中假設某個 `workflows/*.json` 一定存在。要分享工作流，請在已安裝機器的 ComfyUI 介面另行匯出並交付；一般使用者也可以只透過 `generate.py` 的固定 CLI 流程產圖。
