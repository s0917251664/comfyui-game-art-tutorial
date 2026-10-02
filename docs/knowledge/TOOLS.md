---
type: catalog
status: current
---
# 工具與技能總表

只列 repo 目前有原始碼或文件支援的能力狀態與路由。可執行不代表該機器已安裝或經實測；生成前仍依 [art-generation.md](art-generation.md)、影片依 [video/README.md](video/README.md) 核對本機能力快照與證據。

| 能力／入口 | 現況與限制 | 何時讀哪份技能 |
|---|---|---|
| 圖片生成：`tools_src/generate.py` facade + `tools_src/comfyui_pipeline/` | 現有 12 個圖片 task：`concept`、`flux2_concept`、`flux2_edit`、`icon_asset`、`pose_only`、`style_lock`、`character_action`、`refine`、`inpaint`、`guided_inpaint`、`upscale`、`layer_split`。固定 graph；SDXL/SD1.5 查 image capability/profile；FLUX.2 有獨立 preflight 與實機證據，不套 image profile。不可自行組 graph。 | 自然語言遊戲圖片需求讀 `skills/comfyui-art-gen/SKILL.md`；路由看 [art-generation.md](art-generation.md)。 |
| 遊戲圖片編修需求整理：brief | 純文件型規劃技能；整理來源、修改／保留項、參考圖用途、提示與既有 task 輸入映射，不執行生成或增加能力。OpenAI 官方提示方法僅供需求表達參考。 | 多參考圖、指定局部修改、要求維持角色／結構或想先整理編修需求時讀 `skills/game-art-edit-brief/SKILL.md`；實際生成仍依 `skills/comfyui-art-gen/SKILL.md`。 |
| 本機圖片編修工具：`tools_src/image_edit_tools.py` | `composite` 以 Alpha 0 選編修圖、255 保留來源；`compare` 產生 RGBA byte 差異及區域統計；`sweep` 固定 prompt/seed/參考，只呼叫 `refine`、`inpaint`、`guided_inpaint`、`character_action`，上限 16 個候選。尺寸不符即停止，不做美術評分。2026-10-01 本機 smoke 已完成；候選畫面觀察與人工驗收狀態見 canonical page。 | 合成、差異檢視或使用者明確要求有限參數比較時讀 `skills/local-image-edit-tools/SKILL.md`；技術細節與驗證狀態見 [edit-tools.md](art/edit-tools.md)。 |
| 影片生成與影片本機處理：`generate.py` + PyAV helpers | 7 個生成 task：`img2video`、`fx_loop`、`transition`、`clip_extend`、`character_video`、`camera_move`、`pose_drive`；2 個本機 task：`video_concat`、`video_composite`。影片查 `video_capabilities.json`，concat/composite 不需 ComfyUI server；不得猜 backend 或切換 task。 | 影片需求讀 `skills/comfyui-video-gen/SKILL.md`，規格與能力見 [video/README.md](video/README.md)。 |
| 結果 manifest：`--result-json` | 選用圖片 task manifest，schema v1；只記技術輸出檢查，不代表內容驗收。 | 需要追溯時看 [art-generation.md](art-generation.md) 的結果紀錄小節與技能的 [result-records.md](result-records.md)。 |
| 素材版本與驗收紀錄：Markdown | 需要保存時才在 `docs/knowledge/assets/<asset-id>.md` 建頁；只記有實際產出的版本。candidate 不代表驗收；accepted/rejected 需對應 Steve 明確決定與理由。 | 產圖後需要留存版本或驗收理由時看 [result-records.md](result-records.md)。 |
| 遮罩手繪：`tools_src/mask_session.py` + `tools_src/simple_mask_tool/` | 獨立工具，不生成圖、不含 SAM；client 部署到 `<ComfyUI>/tools/`，同 package 部署到 `<ComfyUI>/custom_nodes/comfyui-simple-mask-tool/`。repo 部署規則在 `AGENTS.md`。 | 局部修改前由 `skills/comfyui-art-gen/SKILL.md` 路由，操作查 [art/masking.md](art/masking.md)。 |
| SAM 2.1 候選遮罩：`tools_src/sam_segment.py` | 固定官方 small 權重；輸出候選與預覽，候選必須人工挑選／驗收後才能下游使用。 | 局部遮罩邊界需求，讀 [art/sam-segmentation.md](art/sam-segmentation.md)。 |
| 設備偵測：`tools_src/detect_device.py` | 掃描 GPU/VRAM/OS 並產生本機 `device_config.json`；換設備要重跑。 | 新機器／換 GPU 讀 `skills/comfyui-install/SKILL.md`。 |
| 圖片能力偵測：`tools_src/detect_image_capabilities.py` | 依 profiles 掃描已裝模型、nodes 與驗證狀態；只掃描、不下載。FLUX.2 不在此 snapshot。 | 安裝／更新 SDXL/SD1.5 模型後讀 `skills/comfyui-install/SKILL.md`；產圖依 art-generation.md gate。 |
| 影片能力偵測：`tools_src/detect_video_capabilities.py` | 掃描現有模型、runtime、nodes；不下載。不能由圖片 tier 猜影片 backend。 | 讀 [video/README.md](video/README.md) 與 `skills/comfyui-video-gen/SKILL.md`。 |
| 部署驗證：`tools_src/verify_portable_install.py` | 核對部署 facade/package、profiles 等安裝內容；實際選項依安裝文件。 | 新機器 setup 讀 `skills/comfyui-install/SKILL.md`。 |
| BiRefNet benchmark：`tools_src/benchmark_birefnet.py` | 維護者專用去背模型 A/B；不是日常圖片 task，現有驗證沒有足以取代正式模型的證據。 | 只有明確要求重新比較去背模型時，先讀 `skills/comfyui-pipeline-review/SKILL.md` 及 checklist；一般透明素材照 art-generation。 |
| LoRA 訓練：外部 kohya_ss / sd-scripts | repo 沒有訓練程式碼；是否安裝依機器而異。專案記錄過 RTX 4080 一次完整 SDXL 訓練 smoke，不代表這台或 clean clone 可用。 | 只有需要建立角色／風格 LoRA 時讀 [LoRA 訓練知識](installation/lora-training.md) 與安裝技能的 LoRA 小節。 |
| 遊戲角色多動作編排 | 只串既有產圖／產影片與人工驗收點，不新增模型參數或未接入 provider。 | 同一角色一組動作或逐支驗收時讀 `skills/comfyui-character-animation-workflow/SKILL.md` 與 [animation/workflow.md](animation/workflow.md)。 |
| 專案知識庫讀寫：標準 Markdown | `docs/knowledge/` 是既有 Markdown 知識庫，可直接用一般檔案工具讀寫；按需讀相關筆記，小模型起草、root review。Obsidian app 非必要。 | 讀寫前讀 `skills/project-knowledge/SKILL.md`；導覽見 [INDEX.md](INDEX.md)，上游與 vault 支援界線見 [Obsidian 整合說明](maintenance/obsidian-integration.md)。 |
| Obsidian 上游技能：15 個 `skills/<name>/SKILL.md` | 依各自觸發條件按需使用。repo 內技能與 vendor runtime 有固定來源；上游完整 runtime 仍受平台／vault schema 限制，本機 legacy vault 不代表完整 ingest/query 已就緒。 | 按需求讀對應上游技能；原生 Windows 限制、WSL 寫入需求及尚未接入能力見 [Obsidian 整合說明](maintenance/obsidian-integration.md)。 |
| 安裝／升級評估／新增能力 | 獨立的安裝、盤點、開發流程；upgrade review 只有明確要求才觸發。 | 新機器：`skills/comfyui-install/SKILL.md`；明確要求盤點升級：`skills/comfyui-pipeline-review/SKILL.md`；新增 task/工具：`skills/comfyui-new-tool-checklist/SKILL.md`。 |

總計 21 個 `generate.py` task；遮罩、素材紀錄和檢測等依各自文件處理。本機 edit tools 的 sweep 只是既有 task 的有限參數包裝，不增加 task。repo 尚未提供 ComfyUI MCP 生成入口，不要將不存在的能力列為 fallback。影片與動畫細節以各自 vault canonical page 為準，本表只保留可發現性和觸發路由。
