---
type: catalog
status: current
---
# 工具與技能總表

能力發現與路由，不取代技能與 `--help`。用法以 `template.json`（`gameart.py run show <id>`）與各工具的 `--help` 為準，這裡不抄參數。技術執行成功不等於美術驗收（[R1](rules/candidate-review.md)）；生成前依路線核對本機能力、當下平台 schema 或 live preflight。

## 三種執行方式

| 執行方式 | 說明 | 技能 |
|---|---|---|
| 固定 template＋runner | `templates/<id>/` 的固定 API graph，由 runner 填 slot、預檢、上傳、送出、下載、檢查（[R2](rules/fixed-graphs.md)）。清單與能力見自動產生的 [catalog](maintenance/template-catalog.md) | [comfyui-run](../../skills/comfyui-run/SKILL.md) |
| `generate.py` task | 依 task 與旗標選出 template id，再交給同一個 runner。你選 task，不選 graph | comfyui-run |
| 本機 Python 工具 | Pillow／NumPy／PyAV／音訊工具，不組 ComfyUI graph，不套 template | [local-media-tools](../../skills/local-media-tools/SKILL.md) |

## 能力索引

| 能力 | 入口 | 狀態與判斷 |
|---|---|---|
| 需求 brief、驗收、編修情境 | [game-art-brief](../../skills/game-art-brief/SKILL.md) | [brief 與驗收](art/brief-and-acceptance.md)、[編修情境](art/edit-scenarios.md)；不執行生成 |
| 平台原生圖片工具 | [platform-image-gen](../../skills/platform-image-gen/SKILL.md) | 依本次會話 schema；單張文字生圖與編修曾技術完成，候選待驗收；多參考、其他平台、影片未測 |
| 圖片 task（概念、圖示、角色動作、姿勢、風格鎖、局部重繪、精修、放大、分層、FLUX.2） | `generate.py` | SDXL 為既有基線，FLUX.2 為獨立實驗路線；[task 選擇](art-generation.md)、[參數判斷](art-parameters.md)、[已知限制](art/known-limitations.md) |
| 影片 task（靜幀轉影片、循環特效、轉場、接續、角色參考、運鏡、動作驅動、局部重繪） | `generate.py` | H3／Wan backend 依本機 `video_capabilities.json`；[影片知識](video/README.md)、[CLI 對照](video/cli.md) |
| 接片、綠幕合成、抽幀 | `generate.py video_concat`／`video_composite` | 本機 PyAV，不連 ComfyUI |
| 物件追蹤遮罩 | `gameart.py run video/sam3/*` | SAM3 template，內容仍須美術確認；[SAM3 追蹤](video/sam3-tracking.md) |
| 影片局部重繪 | `gameart.py run video/wan-vace/inpaint`、`generate.py video_inpaint`、recipe `object-mark-inpaint` | 遮罩外逐 byte 不變；[vfx-tools](video/vfx-tools.md) |
| Wan Animate、SCAIL-2 | `gameart.py run video/wan-animate/*` | 技術通過、內容 candidate；[取捨](video/wan-animate-choice.md)、[安裝紀錄](video/wan-animate-install.md) |
| SAM2 影片遮罩備援與 2D 圖層合成 | `gameart.py video-layers`（server node＋薄 client） | 不是 template；[Video Layers](video/layers.md) |
| 多步驟含確認點的流程 | `gameart.py recipe` | [templates/README](../../templates/README.md)「recipe」 |
| 參數比較 sweep | `gameart.py edit sweep` | 包裝四個既有圖片 task，最多 16 個候選；[edit-tools](art/edit-tools.md) |
| 本機像素處理 | `gameart.py edit`（composite、recolor、compare、reference-board、asset-audit） | Pillow／NumPy；[edit-tools](art/edit-tools.md)、[單一物件換色](art/single-object-color.md) |
| 物件展示組裝 | `gameart.py design`（scene、sheet、pattern） | 純 Pillow，輸出不透明 RGB；[物件組裝](art/object-design-workflows.md) |
| 特效去背、打包、Idle 量測、道具貼回 | `gameart.py vfx` | [vfx-tools](video/vfx-tools.md) |
| 配音、Animatic、對嘴 | `gameart.py film-audio`、`film-qwen`、`film-lipsync` | 本機 Python 工具；技術 smoke 通過，內容待聽驗；[劇情流程](video/production-flow.md) |
| 遮罩：手繪、邊界貼合、SAM 候選 | `gameart.py mask-session`、`mask-refine`、`sam` | 手繪服務需 ComfyUI 網頁服務；[遮罩](art/masking.md)、[SAM](art/sam-segmentation.md) |
| 角色動作組編排 | 既有圖片／影片 task | [動作組](animation/workflow.md) |
| 素材決定紀錄 | `gameart.py review` | `list` 唯讀；`accept\|reject --by` 只在使用者明確決定後；[result-records](result-records.md) |
| 設備與能力偵測 | `gameart.py detect-device`／`detect-image`／`detect-video`、`doctor` | 只掃描不下載；換機或環境變動後 `doctor --refresh` |
| 部署、驗證、煙霧測試 | `gameart.py deploy`、`verify-install`、`smoke`、`validation` | `deploy` 預設 dry run；`validation approve` 只由使用者決定；[驗證流程](maintenance/validation-workflow.md) |
| 安裝 ComfyUI 與模型 | [comfyui-install](../../skills/comfyui-install/SKILL.md) | [安裝指南](installation/install-guide.md)、[模型清單](installation/models-and-sources.md) |
| 新增能力、審視 | [comfyui-extend](../../skills/comfyui-extend/SKILL.md) | [擴充協議](maintenance/extension-protocol.md)、[新增能力清單](maintenance/new-capability-checklist.md) |
| LoRA 訓練 | 外部 kohya_ss | repo 沒有訓練程式；[LoRA](installation/lora-training.md) |
| 去背模型 A/B | `gameart.py benchmark-birefnet` | 維護者用，不是日常 task |

圖片、影片與本機工具各有自身依賴與狀態；`unverified` 的 task 先告知使用者。repo 沒有 ComfyUI MCP 生成入口，不可列作 fallback。能力目錄只記入口，不能把不同的 gate 壓成通用的 `verified` 標籤。

## 統一入口 `gameart.py`

`python tools_src/gameart.py <tool> [args...]` 轉發到對應腳本，argv、`--help`、結束碼與直接執行相同；`gameart.py list` 列出全部工具。`deploy`、`validation`、`verify-install`、`benchmark-birefnet`、`run`、`recipe` 只能從 repo 執行。部署副本（`<ComfyUI>/tools/`）仍可直接呼叫各腳本。輸出位置慣例：多數工具的 `--output-dir` 必填且要求新資料夾；`generate.py` 省略時預設寫到腳本旁的 `generated/`，技能要求明確帶 `--output-dir <output_dir>`（`local_config.json`，即 repo 的 `output/`）。
