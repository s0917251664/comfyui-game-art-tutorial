# AGENTS.md

這是遊戲美術 AI 產線專案。先按需求選技能，再依技能與能力 gate 操作；不要把不同執行路線合併推定。

## 文件分工（每種資訊只放一個地方）

- **技能**（`skills/*/SKILL.md`，共 6 個）只寫思路：怎麼判斷、選哪條路、什麼時候停下來問使用者。
- **用法以程式為準**：template 的 slot、option、模型 pin 查 `python tools_src/gameart.py run show <id>`（以 `template.json` 為準）；工具旗標查 `gameart.py <tool> --help`；`gameart.py list` 列出全部工具。文件不抄參數。
- **知識庫**（`docs/knowledge/`）只寫判斷依據：美術判斷、已知限制、經驗、規則。入口 [`INDEX.md`](docs/knowledge/INDEX.md)、能力索引 [`TOOLS.md`](docs/knowledge/TOOLS.md)；按需讀一頁，不載入整庫。`docs/knowledge/archive/` 是歷史資料，平常不讀。
- 跨路線規則只在 [`docs/knowledge/rules/`](docs/knowledge/rules/README.md) 寫一次：R1 候選與美術驗收、R2 固定流程、R3 Idle 錨定。

## 技能路由

| 需求 | 技能 |
|---|---|
| 第一次使用、選路線、整理 brief 與驗收、多參考編修需求、讀寫知識庫 | [`game-art-brief`](skills/game-art-brief/SKILL.md) |
| 平台本身提供的圖片工具 | [`platform-image-gen`](skills/platform-image-gen/SKILL.md) |
| 本機 ComfyUI：圖片／影片 task（`generate.py`）、固定 template（`gameart.py run`）、多步驟 recipe（`gameart.py recipe`） | [`comfyui-run`](skills/comfyui-run/SKILL.md) |
| 不經 ComfyUI 的本機 Python 工具：像素處理、物件組裝、特效去背與打包、配音與對嘴、遮罩輔助 | [`local-media-tools`](skills/local-media-tools/SKILL.md) |
| 缺能力要新增、技能庫與架構審視 | [`comfyui-extend`](skills/comfyui-extend/SKILL.md) |
| 安裝 ComfyUI 與模型、部署 repo 工具 | [`comfyui-install`](skills/comfyui-install/SKILL.md) |

## 執行方式

- **`generate.py <task>`** 是圖片與影片 task 的入口：依 task 與旗標選出 template id，交給 runner 執行。
- **`gameart.py run <template id>`** 直接執行沒有 `generate.py` task 的固定流程（Wan Animate、SCAIL-2、SAM3 追蹤、VACE 局部重繪）。順序：`run show` → `--dry-run` → `--preflight` → 實際執行（寫 `run.result.json`）。
- **`gameart.py recipe`**：多步驟、中間要人工確認的流程；停在確認點，使用者確認後才 `resume --confirm`。
- **本機 Python 工具**（`edit`、`design`、`vfx`、`film-audio`、`film-qwen`、`film-lipsync`、`mask-session`、`mask-refine`、`sam`、`video-layers`）不經 template，不套 template 做法；文件寫清楚它們是本機工具。
- 不臨場組或改 ComfyUI graph（[R2](docs/knowledge/rules/fixed-graphs.md)）；新的固定 graph 走[擴充協議](docs/knowledge/maintenance/extension-protocol.md)。缺能力不自動換引擎，只整理需求不啟動生成。

## 執行與驗收原則

- 生成前按路線查能力：圖片查 `image_capabilities.json`，影片查 `video_capabilities.json`；template 一律先 `--preflight`。`unverified` 先告知；能力不足在 upload／queue 前停止。換機或環境變動後先 `gameart.py doctor` 看快照是否過期，再 `doctor --refresh`。detector 只掃描不下載；不能從圖片 tier 推定影片 backend。
- 候選與驗收依 [R1](docs/knowledge/rules/candidate-review.md)：技術檢查不等於美術接受；`gameart.py review accept|reject --by <使用者>` 與 `validation approve` 只在使用者明確決定後才執行，agent 不自行決定。素材紀錄格式見 [`result-records.md`](docs/knowledge/result-records.md)。
- 圖片模型設定檔在 `tools_src/comfyui_pipeline/profiles/*.json`，驗證以 `platform_key` 為準；FLUX.2 使用獨立 preflight。大機器要指定較小設定檔時用 `--profile` 或 detector 選項，不手改 `device_config.json`。
- 不自動用系統播放器開成品；逾時不重送，不呼叫全域 `/interrupt`，不清 queue。
- [`local_config.json`](local_config.json) 是本機實際路徑（不進版控，缺此檔不代表需要安裝）；依所選路線核對設定與依賴。安裝見 `comfyui-install`。
- 本專案目前無預算，使用本機免費模型；日後接外部雲端服務須依使用者明確選擇的路線處理。新增 `.ps1` 必須使用帶 BOM 的 UTF-8，以支援 Windows PowerShell 5.1。
- 文件草稿由小模型撰寫、主 agent 審核實際差異、來源、連結與規則影響。
