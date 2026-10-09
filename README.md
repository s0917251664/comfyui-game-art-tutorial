# 遊戲美術 AI 協作與產線

這個專案把遊戲美術的需求整理、圖片或短片生成，以及本機素材處理分成不同職責。使用者用自然語言描述想完成的工作；agent 先釐清素材與驗收方式，再依選定的執行路線操作。美術不需要自己拉 ComfyUI 節點。

生成結果、機械檢查和美術是否接受會分開處理：技術檢查通過不等於美術接受（[R1](docs/knowledge/rules/candidate-review.md)）。

## 快速開始：先選工作，再選執行路線

1. **說明要做的事**：例如從文字做概念圖、修改一張既有圖片、製作同系列物件、做短動態特效，或處理本機圖片檔。
2. **說明來源與保留項**：哪張是編修目標，其他圖各自提供角色、姿勢、材質、結構或背景；本輪要改什麼、哪些細節要保留，怎麼判斷結果可用。
3. **選執行路線**：初次使用或尚未選引擎時，先依[初始化](docs/knowledge/installation/initialization.md)整理需求並盤點能力，不推定安裝意圖。選 ComfyUI 就沿用該引擎並核對能力 gate；選平台原生圖片工具就只用當下會話實際提供的欄位，不需本機 GPU 或 ComfyUI。兩者不能互相代替實測結果。
4. **逐項檢查並選版本**：由美術決定接受、退回修改或停止。

| 工作情境 | 技能 | 界線 |
|---|---|---|
| 整理需求、參考圖用途、驗收；多參考編修 | [game-art-brief](skills/game-art-brief/SKILL.md) | 不執行生成；方法見 [brief 與驗收](docs/knowledge/art/brief-and-acceptance.md) |
| 概念圖、圖示、角色圖（平台圖片工具） | [platform-image-gen](skills/platform-image-gen/SKILL.md) | 依當下工具 schema，不需本機 GPU 或設定 |
| 概念圖、圖示、角色動作、局部重繪、放大、分層、短影片、Wan Animate、物件追蹤 | [comfyui-run](skills/comfyui-run/SKILL.md) | 用 `generate.py` task、`gameart.py run` template 或 `gameart.py recipe`；缺能力時如實說明 |
| 像素處理、物件展示組裝、特效去背與打包、配音、對嘴 | [local-media-tools](skills/local-media-tools/SKILL.md) | 本機 Python 工具，不經 ComfyUI graph，輸出都是 candidate |
| 缺能力要新增、技能庫與架構審視 | [comfyui-extend](skills/comfyui-extend/SKILL.md) | 照擴充協議提案，不臨場組 graph |
| 安裝與部署 | [comfyui-install](skills/comfyui-install/SKILL.md) | 使用者明確要求才裝 |

平台原生圖片工具和外部付費 API 是不同路線。本專案尚未接入外部付費服務，不會因為有平台圖片工具就假定可呼叫付費服務。

## 用法以程式為準

文件不抄參數。要知道某個 template 怎麼填：

```bash
python tools_src/gameart.py run list
python tools_src/gameart.py run show <template id>
```

其他工具查 `python tools_src/gameart.py <tool> --help`，`gameart.py list` 列出全部工具；圖片與影片 task 查 `generate.py <task> --help`。`generate.py` 依 task 與旗標選出 template id 並交給 runner；`gameart.py run` 直接執行 template；`gameart.py recipe` 串多步驟與人工確認點。細節見 [templates/README](templates/README.md)。

## ComfyUI 本機產線：安裝與驗證

若這台機器尚未安裝，先依[安裝流程](skills/comfyui-install/SKILL.md)建置 ComfyUI、模型和本機設定；安裝會偵測硬體並產生機器專用的 `local_config.json`。換電腦或換顯卡時，不要複製舊機器的 `local_config.json`、`device_config.json`、`image_capabilities.json`、`video_capabilities.json`，在新機器重新偵測。

驗證部署（不需要啟動 ComfyUI）：

```bash
python tools_src/verify_portable_install.py --repo-root . --config local_config.json
```

## 測試

測試以標準庫 `unittest` 為主，也可用 pytest；設定在 `pyproject.toml`（只宣告相依與測試設定，不要 `pip install .`）。需要第三方套件的測試模組缺套件時會自動 skip。

```bash
python -m pip install pillow numpy av opencv-python pytest
PYTHONPATH=tools_src python -m unittest discover -s tests
```

只跑單一模組時把 `tests` 也加進 `PYTHONPATH`，用模組名稱執行，例如 `PYTHONPATH=tools_src:tests python -m unittest test_doc_links`（Windows 的分隔符是 `;`）。不要寫成 `tests.test_xxx`：ComfyUI venv 裡的 color_matcher 會裝一個頂層 `tests` 套件，把 repo 的 `tests/` 蓋掉。完整測試建議用 ComfyUI 的 venv（已有 av／cv2／torch）。測試會 mock 掉 ComfyUI 與模型，不能取代實機 smoke test。`tests/test_docs_converged.py` 防止文件回到舊的堆疊方式（SKILL.md 篇幅、舊名詞、連結）。

## 文件導覽

| 文件 | 內容 |
|---|---|
| [`AGENTS.md`](AGENTS.md) | agent 入口：技能路由與執行原則 |
| [`skills/README.md`](skills/README.md) | 6 個技能索引 |
| [知識庫索引](docs/knowledge/INDEX.md) / [工具總表](docs/knowledge/TOOLS.md) | 判斷依據與能力索引 |
| [安裝流程](skills/comfyui-install/SKILL.md) / [模型清單](docs/knowledge/installation/models-and-sources.md) | 新機器環境與模型來源 |
| [已驗證版本](docs/tested-versions.md) | commit、套件版本、模型 SHA-256 與 smoke test 紀錄 |
| [templates/README](templates/README.md) | 固定 API graph 的規則、runner 與 recipe |

發現文件與實作衝突時，先核對實作並修正說明；不要為了符合舊文件臨場改 graph、換模型或補不存在的旗標（[R2](docs/knowledge/rules/fixed-graphs.md)）。

## 授權

本 repository 沒有附 `LICENSE`，程式碼、文件與圖片不應視為可任意再利用。ComfyUI、custom nodes 與各模型請遵守各自上游的授權條款。
