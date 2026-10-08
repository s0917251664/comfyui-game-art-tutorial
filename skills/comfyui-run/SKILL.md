---
name: comfyui-run
description: 用本機 ComfyUI 執行已登記的遊戲美術能力：generate.py 圖片／影片 task、templates/ 的固定 API graph（gameart.py run，例如 Wan Animate、SCAIL-2、SAM3 物件追蹤、VACE 影片局部重繪）、多步驟 recipe（gameart.py recipe）、換臉、影片分層、物件系列與有限參數比較；負責能力檢查、preflight、執行與技術驗收。平台生圖另走 platform-image-gen。
---

# ComfyUI 執行

選定本機 ComfyUI 路線後用這個技能。這裡只寫怎麼選、怎麼判斷；參數、輸入契約、踩坑都在 `references/` 與 [template catalog](../../docs/knowledge/maintenance/template-catalog.md)。

## 先判斷三件事

1. **這是哪一種執行方式**（[R2](../../docs/knowledge/rules/fixed-graphs.md)）：`generate.py` 的固定 task、`templates/` 的固定 API graph（`gameart.py run`）、recipe（`gameart.py recipe`），或 repo 內的 server-side custom node（換臉、影片分層）。不能把其中一種假寫成另一種，不臨場組 graph。
2. **這台機器有沒有這個能力**：圖片看 `image_capabilities.json`，影片看 `video_capabilities.json`；快照可能過期時先 `gameart.py doctor`。template 一律先 `gameart.py run <id> --preflight`（平台狀態、node、模型、ComfyUI 版本），不通過就在上傳前停下。
3. **缺能力怎麼辦**：如實說明，不換引擎、不用相似 task 頂替；要新增能力走 [comfyui-extend](../comfyui-extend/SKILL.md)。

## 依需求選

| 需求 | 入口 | 細節 |
|---|---|---|
| 概念圖、圖示、角色動作、姿勢、風格鎖、局部重繪、精修、放大、分層、FLUX.2 | `generate.py <task>`（內部由 runner 填 `templates/image/**`） | [comfyui-art-gen](references/comfyui-art-gen/README.md) |
| 同一張圖比較有限幾組參數 | `gameart.py edit sweep` | [comfyui-image-sweep](references/comfyui-image-sweep/README.md) |
| 物件系列、展示背景、檢視表、圖樣重複 | 圖片 task＋`gameart.py design`（純 Pillow） | [comfyui-object-design](references/comfyui-object-design/README.md) |
| 靜幀轉短片、循環特效、接片、運鏡、角色參考影片、動作驅動 | `generate.py <video task>`（內部填 `templates/video/wan|h3/**`） | [comfyui-video-gen](references/comfyui-video-gen/README.md) |
| 角色動作組（多張動作幀＋驗收） | 編排既有圖片／影片 task | [comfyui-character-animation-workflow](references/comfyui-character-animation-workflow/README.md) |
| 劇情多鏡、配音、Animatic | 編排既有 task＋`film_audio.py` | [comfyui-film-workflow](references/comfyui-film-workflow/README.md) |
| 影片物件遮罩追蹤 | `gameart.py run video/sam3/track-mask`（手繪第 0 幀）或 `track-text`；SAM3 不可用才用 SAM2 備援 | [comfyui-video-layers](references/comfyui-video-layers/README.md) |
| 影片局部重繪（只改遮罩內，遮罩外逐 byte 不變） | `gameart.py run video/wan-vace/inpaint`，或相容入口 `generate.py video_inpaint`；從物件標記一路做到重繪用 recipe `object-mark-inpaint` | [templates/README](../../templates/README.md)、[vfx-tools](../../docs/knowledge/video/vfx-tools.md) |
| Wan Animate（Mix／Move、延伸段、音訊、寬高）、SCAIL-2 | `gameart.py run video/wan-animate/<id>` | [comfyui-wan-animate](references/comfyui-wan-animate/README.md) |
| 影片換臉 | `face_swap.py preflight` → `swap` | [comfyui-face-swap-workflow](references/comfyui-face-swap-workflow/README.md) |
| 2D 層合成（ordered video layers） | `video_layers.py` | [comfyui-video-layers](references/comfyui-video-layers/README.md) |
| 多步驟、中間要人工確認的流程 | `gameart.py recipe list|show|run|resume`；停在確認點時要等使用者確認，再 `resume DIR --confirm`；`_drafts/` 底下的草稿要加 `--draft`，不能用在一般流程 | [templates/README](../../templates/README.md)「recipe」 |

template 的能力、狀態、平台與首尾幀語意查 [template catalog](../../docs/knowledge/maintenance/template-catalog.md)（`templates/catalog.json` 是同一份的機器可讀版）。`draft` 的 template 只有技術試驗意義；平台是 `untested` 時預設拒跑，`--allow-unverified-platform` 才放行並記錄。

## 驗收

- 每次執行都留技術紀錄：圖片 `*.result.json`，template `run.result.json`，影片 sidecar。`content_review` 一律 pending。
- 技術通過不等於美術接受（[R1](../../docs/knowledge/rules/candidate-review.md)）。accept／reject 只能由使用者決定後用 `gameart.py review` 記錄；`validation approve` 也只能由使用者決定。
- Idle 等首尾相接的動作，依 [R3](../../docs/knowledge/rules/idle-anchoring.md) 和 template 的 `frame_anchoring` 選。
- 不要自動用系統播放器打開成品。不硬砍 ComfyUI、不呼叫 `/interrupt`、不清 queue。

舊技能 `comfyui-art-gen`、`comfyui-object-design`、`comfyui-video-gen`、`comfyui-character-animation-workflow`、`comfyui-film-workflow`、`comfyui-face-swap-workflow`、`comfyui-video-layers`、`comfyui-wan-animate`、`comfyui-image-sweep` 的完整內容都保留在 `references/` 底下，對照表見 [技能收斂對照](../../docs/knowledge/maintenance/skills-6-mapping.md)。
