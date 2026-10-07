# AGENTS.md

這是遊戲美術 AI 產線專案。先按需求選入口，再依其技能和能力 gate 操作；不要把不同執行路線合併推定。

## 快速入口

> 也可用統一入口 `python tools_src/gameart.py <tool> [args...]`（`gameart.py list` 列出工具對應，如 `gen`、`design`、`edit`）；argv 原樣轉發，各腳本仍可直接執行。

| 需求 | skill | 主要指令（`tools_src/`） |
|---|---|---|
| 初始化／選路線 | `game-art-initialize` | `detect_device.py`、`detect_image_capabilities.py`、`detect_video_capabilities.py` |
| 概念圖、圖示、角色動作、姿勢、風格鎖 | `comfyui-art-gen` | `generate.py concept` / `icon_asset` / `character_action` / `pose_only` / `style_lock` |
| 局部重繪、精修、放大、分層 | `comfyui-art-gen` | `generate.py inpaint` / `guided_inpaint` / `refine` / `upscale` / `layer_split` |
| FLUX.2 概念與編修（獨立 preflight） | `comfyui-art-gen` | `generate.py flux2_concept` / `flux2_edit` |
| 物件系列、展示背景、圖樣重複 | `comfyui-object-design` | `comfyui_design.py scene` / `sheet` / `pattern` |
| 本機像素合成與比較、參數掃描 | `local-image-edit-tools`、`comfyui-image-sweep` | `image_edit_tools.py composite` / `compare` / `recolor` / `sweep` / `asset-audit` / `reference-board` |
| 靜幀轉短片、循環特效、接片、運鏡 | `comfyui-video-gen` | `generate.py img2video` / `fx_loop` / `video_concat` / `camera_move` / `character_video` |
| 劇情多鏡、配音 | `comfyui-film-workflow` | `film_audio.py voices` / `tts` / `dub` |
| 影片換臉 | `comfyui-face-swap-workflow` | `face_swap.py preflight` / `swap` |
| 影片遮罩分層 | `comfyui-video-layers` | `video_layers.py preflight` / `run` |
| 影片局部重繪（美術標記物件，只改遮罩內） | `comfyui-video-gen` | 預設：SAM3 固定 graph（`skills/comfyui-video-layers/assets/sam3-track-*.json`）→ `gameart.py vfx mask-preview` → `generate.py video_inpaint`；SAM3 不可用時才改用 SAM2：`gameart.py vfx keyframes` / `segment-plan` → `video_layers.py run` → `vfx unpack-masks` |
| 特效去背輸出、sprite sheet／WebM 打包、Idle 首尾量測 | `comfyui-video-gen` | `gameart.py vfx luma-alpha` / `chroma-alpha` / `pack` / `loop-metrics` |
| 安裝 ComfyUI／模型 | `comfyui-install` | `verify_portable_install.py` |
| 部署 repo 工具到 ComfyUI | `comfyui-install` | `gameart.py deploy`（dry run）／ `deploy --yes` ／ `deploy --rollback` |
| 固定煙霧測試與驗證紀錄 | `comfyui-install` | `<python_exe> <ComfyUI>/tools/gameart.py smoke run --output-dir DIR --config <絕對路徑>/local_config.json [--tasks ..] [--record <repo>]` ／ `smoke record <report>` ／ `validation propose|status`（技術檢查，見 `docs/knowledge/maintenance/validation-workflow.md`） |

各 task 完整參數以 `generate.py <task> --help` 為準；其他入口見下方路由，指令不在表內者不要自行推定。

## 工作路由

- 共用 brief、參考用途、修改／保留項、版本與美術驗收：[`skills/game-art-workflow/SKILL.md`](skills/game-art-workflow/SKILL.md)。物件系列、VFX、角色動作方法按需讀 `references/production.md`；完整職責盤點只在維護／移植時讀 `references/responsibilities.md`。
- 新使用者初始化或尚未選路線：[`skills/game-art-initialize/SKILL.md`](skills/game-art-initialize/SKILL.md)，先整理需求與能力，不預設安裝。已配置 ComfyUI 專案的日常工作沿用所選引擎。選平台圖片工具讀 [`skills/platform-image-gen/SKILL.md`](skills/platform-image-gen/SKILL.md)；平台圖片、ComfyUI、外部付費 API／CLI 是不同路線，不能推定模型或參數可用。
- ComfyUI 圖片生成與編修：[`skills/comfyui-art-gen/SKILL.md`](skills/comfyui-art-gen/SKILL.md)；編修 brief 相容入口 [`skills/game-art-edit-brief/SKILL.md`](skills/game-art-edit-brief/SKILL.md)。依 task 選 executor 與自身 gate；不可一律要求本機 Python/config，也不臨場改 API 或組 graph（[R2](docs/knowledge/rules/fixed-graphs.md)）。缺能力不自動換引擎；只整理需求不啟動生成。
- 物件系列、展示背景、檢視表與圖樣重複：[`skills/comfyui-object-design/SKILL.md`](skills/comfyui-object-design/SKILL.md)。本機像素操作：[`skills/local-image-edit-tools/SKILL.md`](skills/local-image-edit-tools/SKILL.md)；有限參數比較：[`skills/comfyui-image-sweep/SKILL.md`](skills/comfyui-image-sweep/SKILL.md)。五個 Pillow／NumPy 操作不需 GPU、ComfyUI 或 `local_config.json`；Agent 須能執行程式並讀寫來源圖。
- 影片生成：[`skills/comfyui-video-gen/SKILL.md`](skills/comfyui-video-gen/SKILL.md)；角色動作組編排：[`skills/comfyui-character-animation-workflow/SKILL.md`](skills/comfyui-character-animation-workflow/SKILL.md)；劇情多鏡、聲音與 Animatic：[`skills/comfyui-film-workflow/SKILL.md`](skills/comfyui-film-workflow/SKILL.md)。既有影片能力及其 gate 不等於圖片 task；平台影片尚未整合。**不要自動用系統播放器開成品。**
- 既有換臉讀 [`skills/comfyui-face-swap-workflow/SKILL.md`](skills/comfyui-face-swap-workflow/SKILL.md)；SAM 遮罩／ordered video layers 讀 [`skills/comfyui-video-layers/SKILL.md`](skills/comfyui-video-layers/SKILL.md)；Wan Animate（含延伸段、音訊、寬高）與 SCAIL-2 固定 workflow/API 查詢讀 [`skills/comfyui-wan-animate/SKILL.md`](skills/comfyui-wan-animate/SKILL.md)。這些路線各有部署和驗收契約，依技能 reference 操作。
- 明確要求安裝，或已選本機 executor 且其依賴缺失時，讀 [`skills/comfyui-install/SKILL.md`](skills/comfyui-install/SKILL.md)；單純缺 `local_config.json` 不代表安裝意圖。新增／擴充能力讀 [`skills/comfyui-new-tool-checklist/SKILL.md`](skills/comfyui-new-tool-checklist/SKILL.md)；明確要求技能庫、架構或新技術審視才讀 [`skills/comfyui-pipeline-review/SKILL.md`](skills/comfyui-pipeline-review/SKILL.md)。專案知識庫依 [`skills/project-knowledge/SKILL.md`](skills/project-knowledge/SKILL.md) 和 [`docs/knowledge/TOOLS.md`](docs/knowledge/TOOLS.md) 按需讀取，不載入整庫；文件草稿由小模型撰寫、主 agent 審核實際差異、來源、連結與規則影響。

## 執行與驗收原則

- `tools_src/generate.py` 只是 CLI 入口（`main()` 與少數唯讀 re-export）；邏輯在 `comfyui_pipeline/`（task 在 `tasks/`，執行期狀態用明確傳入的 `RunContext`，不用全域），部署時須連同整個 `tools_src/comfyui_pipeline/`。固定流程按既有契約使用，見 [R2 只用已登記的固定流程](docs/knowledge/rules/fixed-graphs.md)。
- SDXL／SD1.5 模型檔名、取樣參數與平台驗證狀態由 `tools_src/comfyui_pipeline/profiles/*.json` 管理，不改 `image_graphs.py`；FLUX.2 使用獨立 preflight。大機器指定較小 profile 用 `--profile` 或 detector 選項，不手改 `device_config.json`。profile 驗證以 `platform_key` 為準。
- 生成前按路線查能力：圖片查 `image_capabilities.json`，影片查 `video_capabilities.json`；FLUX.2、遮罩、抽幀、合成等依各自 gate。`unverified` 先告知；能力不足在 upload／queue 前停止。換機／換 GPU、ComfyUI／node／模型／runtime 改變後，先 `python tools_src/gameart.py doctor` 看快照是否過期，再用 `doctor --refresh` 重跑三個 detector 並更新指紋（生成時若偵測到過期會在 stderr 提醒，不阻擋）。detector 只掃描，不下載；不能從圖片 tier 推定影片 backend。
- 平台驗證升格（`gameart.py validation approve --by <使用者>`，寫入 profile 的 `validation`）是使用者的決定：agent 不得在使用者沒有明確要求時執行 approve；`propose`／`status`／`smoke record` 可自行執行。證據綁報告與環境，環境不同顯示 `verified_other_env`（只提醒）。
- 候選與驗收依 [R1 技術檢查不等於美術接受](docs/knowledge/rules/candidate-review.md)。圖片預設寫技術 manifest（`*.result.json`），使用者明確決定後才可用 `gameart.py review accept|reject --by <使用者>` 記錄，agent 不得自行決定；素材紀錄格式見 [`docs/knowledge/result-records.md`](docs/knowledge/result-records.md)。
- 本專案目前無預算，使用本機免費模型；日後外部雲端服務須依使用者明確選擇的路線處理，參考 [`教學.md`](教學.md) 第 0.5 章 C 段。新增 `.ps1` 必須使用帶 BOM 的 UTF-8，以支援 Windows PowerShell 5.1。

## 入口與參考

- [`docs/knowledge/rules/`](docs/knowledge/rules/README.md)：跨路線規則只在這裡完整寫一次（R1 候選與美術驗收、R2 固定流程、R3 Idle 錨定），其他文件只引用編號。
- 技能索引見 [`skills/README.md`](skills/README.md)。`skills/` 只放本專案技能；Obsidian 上游技能已移到 [`third_party/claude-obsidian-skills/`](third_party/claude-obsidian-skills/README.md)，產線工作和知識庫讀寫都不需要它們。
- 文件分工：README 說明開始方式，AGENTS 保留路由與必要原則，TOOLS 提供能力索引；精確操作契約留在技能 references，日期化實測與狀態留在對應知識頁。入口引用主要紀錄，避免複製整段測試狀態。
- [`教學.md`](教學.md)：環境建置、功能地圖與設備／預算選型。
- [`docs/knowledge/TOOLS.md`](docs/knowledge/TOOLS.md)：能力、執行方式、狀態及文件路由；[`docs/knowledge/INDEX.md`](docs/knowledge/INDEX.md)：知識庫導覽。
- [`local_config.json`](local_config.json)：本機 ComfyUI 路徑，不進版控；依所選 executor 核對設定與依賴，缺此檔不代表需要安裝。
- `workflows/` 是不進版控的選用 UI 除錯／開發參考，不要求每個 task 補檔。ComfyUI Core 合成／裁切、手繪遮罩服務、SAM 與純圖片工具依賴不同，不能統稱為免 ComfyUI。
- Wan Animate 安裝、執行契約與驗收狀態見 [`skills/comfyui-wan-animate/SKILL.md`](skills/comfyui-wan-animate/SKILL.md) 及其連結的主紀錄 [`docs/knowledge/video/wan-animate-install.md`](docs/knowledge/video/wan-animate-install.md)。
