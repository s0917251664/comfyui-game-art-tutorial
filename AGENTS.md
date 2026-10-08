# AGENTS.md

這是遊戲美術 AI 產線專案。先按需求選入口，再依其技能和能力 gate 操作；不要把不同執行路線合併推定。

## 快速入口

> 也可用統一入口 `python tools_src/gameart.py <tool> [args...]`（`gameart.py list` 列出工具對應，如 `gen`、`design`、`edit`）；argv 原樣轉發，各腳本仍可直接執行。

| 需求 | skill | 主要指令（`tools_src/`） |
|---|---|---|
| 初始化／選路線 | `game-art-brief` | `detect_device.py`、`detect_image_capabilities.py`、`detect_video_capabilities.py` |
| 概念圖、圖示、角色動作、姿勢、風格鎖 | `comfyui-run` | `generate.py concept` / `icon_asset` / `character_action` / `pose_only` / `style_lock` |
| 局部重繪、精修、放大、分層 | `comfyui-run` | `generate.py inpaint` / `guided_inpaint` / `refine` / `upscale` / `layer_split` |
| FLUX.2 概念與編修（獨立 preflight） | `comfyui-run` | `generate.py flux2_concept` / `flux2_edit` |
| 物件系列、展示背景、圖樣重複 | `comfyui-run` | `comfyui_design.py scene` / `sheet` / `pattern` |
| 本機像素合成與比較、參數掃描 | `local-media-tools`、`comfyui-run` | `image_edit_tools.py composite` / `compare` / `recolor` / `sweep` / `asset-audit` / `reference-board` |
| 靜幀轉短片、循環特效、接片、運鏡 | `comfyui-run` | `generate.py img2video` / `fx_loop` / `video_concat` / `camera_move` / `character_video` |
| 劇情多鏡、配音 | `comfyui-run` | `film_audio.py voices` / `tts` / `dub` |
| 影片換臉 | `comfyui-run` | `face_swap.py preflight` / `swap` |
| 影片物件遮罩追蹤、遮罩分層 | `comfyui-run` | 遮罩追蹤預設：SAM3 固定 template `gameart.py run video/sam3/track-mask`（第 0 幀手繪起手）或 `video/sam3/track-text`（英文名詞起手），先 `--preflight` 再實際執行；SAM3 不可用時才用 SAM2 備援 `video_layers.py preflight` / `run`。2D 層合成（compose）一律用 `video_layers.py` |
| 影片局部重繪（美術標記物件，只改遮罩內） | `comfyui-run` | 預設：SAM3 固定 template（`gameart.py run video/sam3/track-mask` 或 `track-text`，先 `--preflight`）→ 看 `keyframes/mask_preview.png` → `generate.py video_inpaint --masks <run>/outputs/masks`；SAM3 不可用時才改用 SAM2：`gameart.py vfx keyframes` / `segment-plan` → `video_layers.py run` → `vfx unpack-masks` |
| 特效去背輸出、sprite sheet／WebM 打包、Idle 首尾量測 | `local-media-tools` | `gameart.py vfx luma-alpha` / `chroma-alpha` / `pack` / `loop-metrics` |
| 執行固定 API graph template（Wan Animate、SCAIL-2、SAM3、VACE；固定 graph 一律走這裡）與 recipe | `comfyui-run` | `<python_exe> tools_src/gameart.py run list` ／ `run show <id>` ／ `run <id> --dry-run --set NAME=VALUE ...` ／ `run <id> --preflight [--verify-hashes]`（只讀檢查）／`run <id> --set ...`（實際執行，寫 `run.result.json`；見 `templates/README.md`）→ `gameart.py review list <run 資料夾>`（accept／reject 要使用者決定） |
| 安裝 ComfyUI／模型 | `comfyui-install` | `verify_portable_install.py` |
| 部署 repo 工具到 ComfyUI | `comfyui-install` | `gameart.py deploy`（dry run）／ `deploy --yes` ／ `deploy --rollback` |
| 固定煙霧測試與驗證紀錄 | `comfyui-install` | `<python_exe> tools_src/gameart.py smoke run --output-dir DIR [--config local_config.json] [--tasks ..] [--record .]` ／ `smoke record <report>` ／ `validation propose|status`（技術檢查，見 `docs/knowledge/maintenance/validation-workflow.md`） |

各 task 完整參數以 `generate.py <task> --help` 為準；其他入口見下方路由，指令不在表內者不要自行推定。

## 工作路由

- 技能共 6 個（PR 7.3）：需求與 brief [`game-art-brief`](skills/game-art-brief/SKILL.md)、平台圖片 [`platform-image-gen`](skills/platform-image-gen/SKILL.md)、本機 ComfyUI 執行 [`comfyui-run`](skills/comfyui-run/SKILL.md)、本機媒體處理 [`local-media-tools`](skills/local-media-tools/SKILL.md)、擴充與審視 [`comfyui-extend`](skills/comfyui-extend/SKILL.md)、安裝部署 [`comfyui-install`](skills/comfyui-install/SKILL.md)。先讀技能入口選路線，下面各條是入口連到的詳細 reference。舊技能名稱的對照見 [技能收斂對照](docs/knowledge/maintenance/skills-6-mapping.md)。
- 接手第 3–8 階段重構時，先讀 [`docs/knowledge/maintenance/restructure-progress-2026-10-08.md`](docs/knowledge/maintenance/restructure-progress-2026-10-08.md)，再讀 [`docs/knowledge/maintenance/restructure-handoff.md`](docs/knowledge/maintenance/restructure-handoff.md)。進度頁記做到哪裡；交接頁記規則和原始計畫。給人讀的交付脈絡在 [`docs/knowledge/maintenance/restructure-delivery-2026-10-08.md`](docs/knowledge/maintenance/restructure-delivery-2026-10-08.md)。
- 共用 brief、參考用途、修改／保留項、版本與美術驗收：[`skills/game-art-brief/references/game-art-workflow/README.md`](skills/game-art-brief/references/game-art-workflow/README.md)。物件系列、VFX、角色動作方法按需讀 `references/production.md`；完整職責盤點只在維護／移植時讀 `references/responsibilities.md`。
- 新使用者初始化或尚未選路線：[`skills/game-art-brief/references/game-art-initialize/README.md`](skills/game-art-brief/references/game-art-initialize/README.md)，先整理需求與能力，不預設安裝。已配置 ComfyUI 專案的日常工作沿用所選引擎。選平台圖片工具讀 [`skills/platform-image-gen/SKILL.md`](skills/platform-image-gen/SKILL.md)；平台圖片、ComfyUI、外部付費 API／CLI 是不同路線，不能推定模型或參數可用。
- ComfyUI 圖片生成與編修：[`skills/comfyui-run/references/comfyui-art-gen/README.md`](skills/comfyui-run/references/comfyui-art-gen/README.md)；編修 brief 相容入口 [`skills/game-art-brief/references/game-art-edit-brief/README.md`](skills/game-art-brief/references/game-art-edit-brief/README.md)。依 task 選 executor 與自身 gate；不可一律要求本機 Python/config，也不臨場改 API 或組 graph（[R2](docs/knowledge/rules/fixed-graphs.md)；新的固定 graph 走[擴充協議](docs/knowledge/maintenance/extension-protocol.md)）。缺能力不自動換引擎；只整理需求不啟動生成。
- 物件系列、展示背景、檢視表與圖樣重複：[`skills/comfyui-run/references/comfyui-object-design/README.md`](skills/comfyui-run/references/comfyui-object-design/README.md)。本機像素操作：[`skills/local-media-tools/references/local-image-edit-tools/README.md`](skills/local-media-tools/references/local-image-edit-tools/README.md)；有限參數比較：[`skills/comfyui-run/references/comfyui-image-sweep/README.md`](skills/comfyui-run/references/comfyui-image-sweep/README.md)。五個 Pillow／NumPy 操作不需 GPU、ComfyUI 或 `local_config.json`；Agent 須能執行程式並讀寫來源圖。
- 影片生成：[`skills/comfyui-run/references/comfyui-video-gen/README.md`](skills/comfyui-run/references/comfyui-video-gen/README.md)；角色動作組編排：[`skills/comfyui-run/references/comfyui-character-animation-workflow/README.md`](skills/comfyui-run/references/comfyui-character-animation-workflow/README.md)；劇情多鏡、聲音與 Animatic：[`skills/comfyui-run/references/comfyui-film-workflow/README.md`](skills/comfyui-run/references/comfyui-film-workflow/README.md)。既有影片能力及其 gate 不等於圖片 task；平台影片尚未整合。**不要自動用系統播放器開成品。**
- 既有換臉讀 [`skills/comfyui-run/references/comfyui-face-swap-workflow/README.md`](skills/comfyui-run/references/comfyui-face-swap-workflow/README.md)；SAM 遮罩／ordered video layers 讀 [`skills/comfyui-run/references/comfyui-video-layers/README.md`](skills/comfyui-run/references/comfyui-video-layers/README.md)；Wan Animate（含延伸段、音訊、寬高）與 SCAIL-2 固定 workflow/API 查詢讀 [`skills/comfyui-run/references/comfyui-wan-animate/README.md`](skills/comfyui-run/references/comfyui-wan-animate/README.md)。這些路線各有部署和驗收契約，依技能 reference 操作。
- 明確要求安裝，或已選本機 executor 且其依賴缺失時，讀 [`skills/comfyui-install/SKILL.md`](skills/comfyui-install/SKILL.md)；單純缺 `local_config.json` 不代表安裝意圖。新增／擴充能力讀 [`skills/comfyui-extend/references/comfyui-new-tool-checklist/README.md`](skills/comfyui-extend/references/comfyui-new-tool-checklist/README.md)；明確要求技能庫、架構或新技術審視才讀 [`skills/comfyui-extend/references/comfyui-pipeline-review/README.md`](skills/comfyui-extend/references/comfyui-pipeline-review/README.md)。專案知識庫依 [`skills/game-art-brief/references/project-knowledge/README.md`](skills/game-art-brief/references/project-knowledge/README.md) 和 [`docs/knowledge/TOOLS.md`](docs/knowledge/TOOLS.md) 按需讀取，不載入整庫；文件草稿由小模型撰寫、主 agent 審核實際差異、來源、連結與規則影響。

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
- `workflows/` 是不進版控的選用 UI 除錯／開發參考，不要求每個 task 補檔。ComfyUI Core 裁切（`layer_split`）、本機 Pillow 物件組裝、手繪遮罩服務、SAM 與純圖片工具依賴不同，不能統稱為免 ComfyUI。
- Wan Animate 安裝、執行契約與驗收狀態見 [`skills/comfyui-run/references/comfyui-wan-animate/README.md`](skills/comfyui-run/references/comfyui-wan-animate/README.md) 及其連結的主紀錄 [`docs/knowledge/video/wan-animate-install.md`](docs/knowledge/video/wan-animate-install.md)。
