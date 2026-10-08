# 遊戲美術 AI 協作與產線

這個專案把遊戲美術需求整理、圖片或短片生成，以及本機素材處理分成不同職責。使用者用自然語言描述想完成的工作；agent 先釐清素材與驗收方式，再依選定的執行路線操作。美術不需要自己拉 ComfyUI 節點。

共用工作流程整理需求、來源和參考圖用途、這輪要改與要保留的內容、版本關係及人工驗收。它不代表每個執行器都有相同能力。生成結果、機械檢查和美術是否接受，會分開處理。

## 快速開始：先選工作，再選執行路線

1. **說明要做的事**：例如從文字做概念圖、修改一張既有圖片、製作同系列物件、做短動態特效，或處理本機圖片檔。
2. **說明來源與保留項**：指出哪張是編修目標，其他圖各自提供角色、姿勢、材質、結構或背景資訊；列出本輪要改什麼、哪些細節要保留，以及如何判斷結果可用。
3. **選執行路線**：初次使用或尚未選引擎時，先依[初始化技能](skills/game-art-brief/references/game-art-initialize/README.md)整理需求並盤點能力；不由舊預設推定安裝意圖。若明確選 ComfyUI，已配置專案的日常工作沿用該引擎，按 task 核對其能力 gate；若選平台原生圖片工具，只使用當下會話實際提供的功能與欄位，不需本機 GPU 或 ComfyUI 設定。兩者不能互相代替實測結果。
4. **逐項檢查並選版本**：確認內容、格式和素材規格，再由美術決定接受、退回修改或停止。[技術檢查通過不等於美術接受](docs/knowledge/rules/candidate-review.md)。

| 工作情境 | 共用方法 | 執行路線與界線 |
|---|---|---|
| 概念圖、道具、圖示、角色圖 | 釐清用途、主體、參考來源與交付條件 | 初次使用或尚未選引擎先走[初始化技能](skills/game-art-brief/references/game-art-initialize/README.md)；已選／已配置路線依其 gate 執行。平台圖片能力依當下工具 schema 確認，不需本機 GPU/config。 |
| 編修既有圖片、多參考圖、指定局部或保留角色結構 | 標示每張參考圖職責，寫清修改與保留項及版本 | 先讀[共用工作流程](skills/game-art-brief/references/game-art-workflow/README.md)，再選 [ComfyUI 圖片技能](skills/comfyui-run/references/comfyui-art-gen/README.md)或[平台圖片技能](skills/platform-image-gen/SKILL.md)。工具不支援的輸入要列明，不能只靠提示文字假裝可控。 |
| 物件系列、展示圖、檢視表或重複圖樣 | 先驗收單件，再依規則擴展系列；`scene`、`sheet`、`pattern` 是不同展示目的 | 製作方法見[共用 production reference](skills/game-art-brief/references/game-art-workflow/references/production.md)；現有 `comfyui_design.py` 是本機 Pillow 合成 helper，不生成物件、不組 ComfyUI graph，輸出為不透明 RGB。 |
| 本機 PNG 素材處理 | 對齊尺寸和遮罩契約，保留來源並人工檢查輸出 | `image_edit_tools.py` 的 `composite`、`recolor`、`compare`、`reference-board`、`asset-audit` 五個操作使用 Pillow／NumPy，不需 GPU、ComfyUI server 或 `local_config.json`；需要可執行 Python 並取得實際圖片檔。 |
| 固定來源的有限參數比較 | 來源、prompt、seed 和參考固定，只比較事先列明的參數 | 由[ComfyUI sweep 技能](skills/comfyui-run/references/comfyui-image-sweep/README.md)處理；它呼叫既有 `image_edit_tools.py sweep`，需 ComfyUI task 與本機能力 gate，不是一般重試功能。 |
| 靜態或短動態特效、角色動作集合 | 先定效果外觀、起訖／循環條件或角色母圖與代表動作，再逐支驗收 | 共用製作方法見 [production reference](skills/game-art-brief/references/game-art-workflow/references/production.md)；ComfyUI 影片技能只使用已接入 task。平台影片生成目前未整合，圖片工具不能代替影片工具。影片驅動角色或影片角色替換可用[Wan Animate／SCAIL-2 技能](skills/comfyui-run/references/comfyui-wan-animate/README.md)，固定 template，以 `gameart.py run` 執行。 |

平台原生圖片工具和外部付費 API／CLI 是不同路線。本專案尚未接入外部付費 API／CLI；不會因為有平台圖片工具，就假定可安裝客戶端、取得 API key 或呼叫付費服務。

## 新增技能導覽

- [本專案初始化與路線選擇](skills/game-art-brief/references/game-art-initialize/README.md)：初次使用先整理需求與盤點能力；不預設安裝或啟動生成。
- [遊戲美術共用工作流程](skills/game-art-brief/references/game-art-workflow/README.md)：共用需求、參考用途、修改／保留、分階段、版本和驗收規則，不執行生成。
- [職責盤點](skills/game-art-brief/references/game-art-workflow/references/responsibilities.md)：按需查看 ComfyUI task、本機工具、平台路線、影片處理的職責與依賴。
- [製作方法](skills/game-art-brief/references/game-art-workflow/references/production.md)：物件系列、靜態／短動態 VFX、角色動作編排的共用工作方法。
- [平台圖片生成](skills/platform-image-gen/SKILL.md)：本次會話原生圖片工具的獨立執行指引；按需檢查工具欄位，能力未知時交回 brief。
- [ComfyUI 圖片 sweep](skills/comfyui-run/references/comfyui-image-sweep/README.md)：既有 task 的固定輸入有限比較，依 ComfyUI 能力 gate 執行。
- [遊戲圖片編修 brief](skills/game-art-brief/references/game-art-edit-brief/README.md)：專案相容入口，保留 ComfyUI task 輸入映射；共用 brief 規則由共用工作流程維護。

## 平台圖片工具的實測範圍

2026-10-05，在當前會話使用平台原生圖片工具完成文字生圖與單張來源圖編修各一張：先生成透明背景的藍色魔法藥水瓶，再要求只把液體改成紅色。兩張輸出均為 1254×1254 RGBA PNG，具有實際透明像素。瓶身、瓶塞與金屬構圖目視接近，但玻璃高光、液體細節及部分 Alpha 有變化；藍版可見內容碰到畫布邊界，紅版未出現碰邊問題。這說明語意編修可完成顏色變更，但不能據此承諾其他細節或像素完全保留。

兩張圖都只是待美術審核者驗收的 candidate。紅色修改沒有使用遮罩，因此不能判斷指定區域外是否精確保留；這次也沒有驗證多參考輸入、其他平台或任何影片能力。這是單一會話及兩個案例的紀錄，不代表通用平台能力或跨平台驗證。

實測詳細 JSON 位於本機 `output/platform-image-smoke-20261005/execution-review.json`。`output/` 與 `reports/` 依 `.gitignore` 忽略，相關報告、生成圖與 ZIP 不會納入一般 Git 提交，目前也未發布到 GitHub Pages；它們只能說明該次本機觀察，不能作為 repo 可攜能力或其他平台 runtime 已驗證的依據。

## ComfyUI 本機產線：安裝與 CLI

ComfyUI 產線把固定流程鎖在 `tools_src/generate.py` 與 `tools_src/comfyui_pipeline/`，不靠每次臨時組節點。若這台機器尚未安裝，先依[安裝流程](skills/comfyui-install/SKILL.md)建置 ComfyUI、模型和本機設定。安裝會偵測硬體並產生機器專用的 `local_config.json`。

驗證部署（不需要啟動 ComfyUI）：

```bash
python tools_src/verify_portable_install.py --repo-root . --config local_config.json
```

產第一張圖（先啟動 ComfyUI；路徑從 `local_config.json` 取得）：

```bash
<python_exe> <generate_script> concept --prompt "fantasy armor character concept art" --config local_config.json --output-dir output
```

Windows PowerShell 可在 repo 根目錄直接讀取設定執行：

```powershell
$artConfig = Get-Content -Raw -Encoding UTF8 .\local_config.json | ConvertFrom-Json
& $artConfig.python_exe $artConfig.generate_script concept --prompt "fantasy armor character concept art" --config .\local_config.json --output-dir $artConfig.output_dir
```

換電腦或換顯卡時，不要複製舊機器的 `local_config.json`、`device_config.json`、`image_capabilities.json` 或 `video_capabilities.json`；要在新機器重新偵測。以上 `<...>` 是指令模板，需替換為實際設定值。

## 測試

測試以標準庫 `unittest` 為主，也可用 pytest；設定在 `pyproject.toml`（該檔只宣告相依與測試設定，不是可安裝套件，不要 `pip install .`）。需要第三方套件的測試模組在缺套件時會自動 skip，不會報錯。

```bash
# 安裝開發相依（對應 pyproject.toml 的 image / video / dev 群組）
python -m pip install pillow numpy av opencv-python pytest

# 在 repository 根目錄執行；unittest 需讓 Python 找到 tools_src/
PYTHONPATH=tools_src python -m unittest discover -s tests
python -m pytest
```

只跑單一測試模組時，把 `tests` 也加進 `PYTHONPATH`，用模組名稱執行，例如 `PYTHONPATH=tools_src:tests python -m unittest test_doc_links`（Windows 的 `PYTHONPATH` 用 `;` 分隔）。不要寫成 `tests.test_xxx`：ComfyUI venv 裡的 color_matcher 會裝一個頂層 `tests` 套件，把 repo 的 `tests/` 蓋掉。

要跑完整測試（含 av／cv2／torch 相關），建議直接用 ComfyUI 的 venv，例如 `<ComfyUI>/.venv/bin/python -m unittest discover -s tests`（Windows 為 `.venv\Scripts\python.exe`），其中已有這些套件。用系統 Python 時缺套件的模組會被 skip。Graph golden fixture 在 `tests/fixtures/image_graphs_golden/<tier>.json`，只在刻意改 graph 時以 `python tests/golden_image_graphs.py --write` 重產。

測試會 mock 掉 ComfyUI 與模型，不能取代實機 smoke test。

## 其他文件

| 文件 | 內容 |
|---|---|
| [`教學.md`](教學.md) | 完整建置紀錄、功能地圖、設備選型 |
| [`AGENTS.md`](AGENTS.md) | agent 入口、原則與工具職責 |
| [產圖技能](skills/comfyui-run/references/comfyui-art-gen/README.md) / [task 參數](docs/knowledge/art-parameters.md) | ComfyUI 圖片 task、輸入、能力 gate 與限制 |
| [產影片技能](skills/comfyui-run/references/comfyui-video-gen/README.md) / [單角色動畫](skills/comfyui-run/references/comfyui-character-animation-workflow/README.md) | ComfyUI 影片 task、backend 與角色動作交付 |
| [安裝流程](skills/comfyui-install/SKILL.md) / [模型清單](docs/knowledge/installation/models-and-sources.md) | 新機器環境與模型準備 |
| [模型設定檔設計](docs/model-profiles-design.md) | SDXL／SD1.5 設定檔與平台驗證狀態 |
| [本機圖片工具](skills/local-media-tools/references/local-image-edit-tools/README.md) / [物件組裝](skills/comfyui-run/references/comfyui-object-design/README.md) / [工具總表](docs/knowledge/TOOLS.md) | 本機像素操作、Pillow 物件組裝與能力入口 |
| [單一物件換色紀錄](docs/knowledge/art/single-object-color.md) | HSV 色相旋轉案例與限制 |
| [已驗證版本](docs/tested-versions.md) | commit、套件版本、模型 SHA-256 與 smoke test 紀錄 |

### 文件與實作如何對照

| 要確認的事情 | 依據 |
|---|---|
| 共用需求及驗收方式 | `skills/game-art-brief/references/game-art-workflow/` 與對應 executor 技能 |
| CLI 真正接受的參數、輸出與錯誤處理 | `tools_src/` parser 與實作；reference 應與它一致 |
| SDXL／SD1.5 模型、預設參數與平台驗證狀態 | `tools_src/comfyui_pipeline/profiles/*.json` |
| 當前機器的路徑與已安裝能力 | 本機 config／capability 快照及執行時 preflight |
| 固定 ComfyUI API-format graph 的輸入契約、request／response 和輸出檢查 | `templates/<id>/template.json`、[templates/README](templates/README.md) 與對應技能的操作契約；live schema／模型由 `gameart.py run <id> --preflight` 核對 |
| 某次實測的版本、hash 與結果 | `docs/tested-versions.md` 與已追蹤的日期化實測紀錄；`output/` 下的本機檔案不會隨 repository 發布 |
| 架構理由與未實作構想 | 設計稿、歷史升級評估；不能據此宣稱能力已可用 |

發現文件與實作衝突時，先核對實作並修正說明；不要為了符合舊文件而臨場改 graph、換模型或補不存在的旗標（[R2](docs/knowledge/rules/fixed-graphs.md)）。

## 授權

本 repository 沒有附 `LICENSE`，程式碼、文件與圖片不應視為可任意再利用。ComfyUI、custom nodes 與各模型請遵守各自上游的授權條款。
