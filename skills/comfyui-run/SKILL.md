---
name: comfyui-run
description: 用本機 ComfyUI 執行已登記的圖片／影片能力：generate.py 的 task（內部由 runner 填固定 template）、gameart.py run 直接跑 template（Wan Animate、SCAIL-2、SAM3 追蹤、VACE 影片局部重繪）、gameart.py recipe 多步驟流程；負責能力檢查、preflight、執行與技術驗收。平台生圖另走 platform-image-gen，不經 ComfyUI 的本機工具走 local-media-tools。
---

# ComfyUI 執行

選定本機 ComfyUI 路線後用這個技能。這裡只寫怎麼選、怎麼判斷；**參數與輸入契約不在文件裡，以 template.json 為準**。

## 三個入口，同一個 runner

- **`generate.py <task>`**：入口。它依 task 與旗標選出 template id（例如 `concept` 加 `--remove-bg` 選到 `image/sdxl/concept-transparent`），交給 runner 填值、送出、檢查。你只選 task，不選 graph。
- **`gameart.py run <template id>`**：直接指定 template。沒有對應 `generate.py` task 的固定流程（Wan Animate、SCAIL-2、SAM3 物件追蹤、VACE 影片局部重繪）走這裡。
- **`gameart.py recipe`**：多步驟、中間要人工確認的流程（例如 `object-mark-inpaint`）。停在確認點時等使用者確認才 `resume --confirm`。

所有路徑背後都是 `templates/` 的固定 graph。不臨場組 graph、不自己呼叫 ComfyUI HTTP（[R2](../../docs/knowledge/rules/fixed-graphs.md)）。

## 查用法

- template：`<python_exe> tools_src/gameart.py run show <id>`（slot、option、模型 pin、平台狀態）；`run list` 列全部；能力總表見 [template catalog](../../docs/knowledge/maintenance/template-catalog.md)。
- generate task：`generate.py <task> --help`。
- 文件不抄參數。想知道旗標，跑指令，不憑記憶或舊文件。

## 先判斷

1. **這台機器能不能做**：圖片看 `image_capabilities.json`，影片看 `video_capabilities.json`，快照可能過期先 `gameart.py doctor`。template 一律先 `run <id> --preflight`，被擋就在上傳前停下，不下載、不換相似檔名。
2. **缺能力**：如實說明，不換引擎、不用相似 task 頂替；要新增走 [comfyui-extend](../comfyui-extend/SKILL.md)。
3. **狀態**：template `draft` 或平台 `untested` 只有技術試驗意義；放行（`--allow-unverified-platform`）要使用者確認並記錄。

## 依需求選

| 需求 | 入口 | 判斷依據 |
|---|---|---|
| 概念圖、圖示、角色動作、姿勢、風格鎖、局部重繪、精修、放大、分層 | `generate.py` 圖片 task | [圖片 task 選擇](../../docs/knowledge/art-generation.md)、[參數判斷](../../docs/knowledge/art-parameters.md) |
| 靜幀轉短片、循環特效、接片、運鏡、角色參考影片、動作驅動 | `generate.py` 影片 task | [影片知識](../../docs/knowledge/video/README.md) |
| Wan Animate、SCAIL-2 | `gameart.py run video/wan-animate/<id>` | [取捨與限制](../../docs/knowledge/video/wan-animate-choice.md) |
| 物件追蹤遮罩、影片局部重繪 | `run video/sam3/*`、`run video/wan-vace/inpaint` 或 recipe | [SAM3 追蹤](../../docs/knowledge/video/sam3-tracking.md)、[vfx-tools](../../docs/knowledge/video/vfx-tools.md) |
| 同一張圖比較有限幾組參數 | `gameart.py edit sweep` | [edit-tools](../../docs/knowledge/art/edit-tools.md) |
| 一組角色動作、劇情多鏡 | 編排既有 task | [動作組](../../docs/knowledge/animation/workflow.md)、[劇情流程](../../docs/knowledge/video/production-flow.md) |

## 驗收

- 每次執行留技術紀錄（圖片 `*.result.json`、template `run.result.json`、影片 sidecar），`content_review` 一律 pending。
- 技術通過不等於美術接受（[R1](../../docs/knowledge/rules/candidate-review.md)）；accept／reject 只由使用者決定後用 `gameart.py review` 記錄。
- 首尾相接的動作依 [R3](../../docs/knowledge/rules/idle-anchoring.md) 與 template 的 `frame_anchoring` 選。
- 不自動用系統播放器開成品；不硬砍 ComfyUI、不呼叫 `/interrupt`、不清 queue；逾時不重送。
