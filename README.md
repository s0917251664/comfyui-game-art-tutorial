# ComfyUI AI 產圖與視覺素材工作流

用 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 建立可控、可重複的 AI 圖像與短片產線，適用於概念圖、角色、UI 圖示與其他遊戲美術素材。

產圖流程鎖在固定的 CLI 腳本（`tools_src/generate.py`）裡，不靠每次臨時拉節點。主要操作方式是直接用自然語言告訴 AI agent 需求，例如：

- 「幫我做一個魔法水晶圖示，透明背景。」
- 「把這張圖的武器換掉，但手部握姿不要變。」
- 「讓這張角色靜圖動起來，做成 2 秒待機動畫。」

agent 會依 [`AGENTS.md`](AGENTS.md) 找到對應的技能文件，確認這台機器撐得起後，才呼叫固定流程，並把結果存到 `output/`。

## 可以做什麼

美術可用自然語言提出需求；agent 依現有 task 和本機能力選入口，不需要自己拉 ComfyUI 節點。生成、圖片後處理與版面組裝是不同步驟：`generate.py` 產生候選，本機圖片工具負責遮罩內純色調整／合成／檢查，固定 ComfyUI Core helper 負責物件展示與排版組裝。產線也有概念圖、角色與姿勢控制、放大、拆層，以及實驗性 FLUX.2 圖片路線；可用性依 task、能力檢查和驗收結果而定。

| 需求 | 入口與能力 | 注意事項 |
|---|---|---|
| 概念圖、草稿精緻化、角色／姿勢／風格控制、放大或拆出透明圖層 | 依任務使用既有圖片 task；[產圖技能](skills/comfyui-art-gen/SKILL.md) | 需依本機能力與輸入選擇 task；角色、姿勢或結構控制的輸出仍要檢查。 |
| 單一透明物件或 UI 圖示 | `icon_asset`；[產圖技能](skills/comfyui-art-gen/SKILL.md) | 產生透明背景候選，仍須檢查外形與去背邊緣。 |
| 只改單一物件既有顏色 | 本機 `recolor`；[本機圖片編修技能](skills/local-image-edit-tools/SKILL.md) | 需已有 Alpha 遮罩；只旋轉符合色相／飽和度條件的像素，不新增紋理或改材質。 |
| 改材質或局部生成 | 依需求選既有 `refine`、`inpaint`、`guided_inpaint`；[產圖技能](skills/comfyui-art-gen/SKILL.md) | 生成結果要逐張驗收；不能保證精確材質控制或角色結構必定不變。 |
| 把物件放進平面背景、排列候選或重複圖樣 | 固定 Core `scene`／`sheet`／`pattern`；[物件組裝技能](skills/comfyui-object-design/SKILL.md) | 組裝既有素材，不是生成 task；輸出為不透明 RGB。 |
| 選取局部區域 | Simple Mask 手動畫、GrabCut 邊界候選或 SAM 候選遮罩 | 使用者檢查遮罩預覽，再交給既有圖片 task 或本機工具；SAM／GrabCut 結果是候選。 |
| 產短片 | [產影片流程](skills/comfyui-video-gen/SKILL.md) | 依既有影片 task 與影片能力快照判斷。 |

各 task 的選擇方式與參數見 [產圖流程](skills/comfyui-art-gen/SKILL.md) 與 [產影片流程](skills/comfyui-video-gen/SKILL.md)。

## 快速開始

1. **安裝**：請 AI agent 照 [安裝流程](skills/comfyui-install/SKILL.md) 在這台機器建置 ComfyUI、模型與設定。它會偵測硬體，選擇適合的模型設定檔，並寫出本機專用的 `local_config.json`。
2. **驗證部署**（不需要啟動 ComfyUI）：

   ```bash
   python tools_src/verify_portable_install.py --repo-root . --config local_config.json
   ```

3. **產第一張圖**（先啟動 ComfyUI，以下路徑與 URL 都用 `local_config.json` 裡的值）：

   ```bash
   <python_exe> <generate_script> concept --prompt "fantasy armor character concept art" --config local_config.json --output-dir output
   ```

換電腦或換顯卡時，不要複製舊機器的 `local_config.json`、`device_config.json`、`image_capabilities.json`、`video_capabilities.json`；要在新機器重新偵測。

以上 `<...>` 是指令模板，需替換成實際值。Windows PowerShell 可在 repo 根目錄直接讀取設定執行：

```powershell
$artConfig = Get-Content -Raw -Encoding UTF8 .\local_config.json | ConvertFrom-Json
& $artConfig.python_exe $artConfig.generate_script concept --prompt "fantasy armor character concept art" --config .\local_config.json --output-dir $artConfig.output_dir
```

## 開發檢查

在 repository 根目錄執行；先讓 Python 找到 `tools_src/` 的工具模組：

```powershell
$env:PYTHONPATH = "tools_src"
python -m unittest discover -s tests -p 'test_*.py'
```

測試會 mock 掉 ComfyUI 與模型，不能取代實機 smoke test。

## 文件導覽

| 文件 | 內容 |
|---|---|
| [`教學.md`](教學.md) | 完整建置紀錄、功能地圖、設備選型 |
| [`AGENTS.md`](AGENTS.md) | agent 的入口與原則、各原始碼的職責 |
| [產圖流程](skills/comfyui-art-gen/SKILL.md) / [完整參數](skills/comfyui-art-gen/reference/full-params.md) / [已知限制](skills/comfyui-art-gen/reference/known-limitations.md) | 圖片 task 的判斷、參數與能力邊界 |
| [產影片流程](skills/comfyui-video-gen/SKILL.md) / [單角色動畫流程](skills/comfyui-character-animation-workflow/SKILL.md) | 短片 task、backend 與整組動作的製作驗收 |
| [安裝流程](skills/comfyui-install/SKILL.md) / [模型清單](skills/comfyui-install/reference/models.md) | 新機器環境與模型準備 |
| [模型設定檔設計](docs/model-profiles-design.md) | SDXL/SD1.5 設定檔與各平台的驗證狀態 |
| [本機圖片編修](skills/local-image-edit-tools/SKILL.md) / [物件組裝](skills/comfyui-object-design/SKILL.md) / [工具總表](docs/knowledge/TOOLS.md) | 遮罩內換色、局部合成與檢查、平面展示／檢視表／圖樣組裝 |
| [單一物件換色紀錄](docs/knowledge/art/single-object-color.md) | HSV 色相旋轉的實測案例與能力限制 |
| [已驗證版本](docs/tested-versions.md) | commit、套件版本、模型 SHA-256 與 smoke test 紀錄 |

### 文件與實作如何對照

| 要確認的事情 | 依據 |
|---|---|
| 需求該走哪個流程、要驗收什麼 | `AGENTS.md` 與對應 `SKILL.md` |
| CLI 真正接受的參數、輸出與錯誤處理 | `tools_src/` 的 parser 與實作；reference 應與它一致 |
| SDXL／SD1.5 模型、預設參數與平台驗證狀態 | `tools_src/comfyui_pipeline/profiles/*.json` |
| 當前機器的路徑與已安裝能力 | 本機 config／capability 快照；送出前仍需即時 preflight（前置檢查） |
| 某次實測用的版本、hash 與結果 | `docs/tested-versions.md` 與附日期的實測紀錄 |
| 架構理由與未實作構想 | 設計稿、歷史升級評估；不能據此宣稱能力已可用 |

發現文件與實作衝突時，先核對實作並修正說明；不要為了符合舊文件而臨場改 graph、換模型或補不存在的旗標。

## 授權

本 repository 沒有附 `LICENSE`，程式碼、文件與圖片不應視為可任意再利用。ComfyUI、custom nodes 與各模型請遵守各自上游的授權條款。
