---
type: maintenance
status: current
---
# 技能收斂對照（PR 7.3，2026-10-08）

18 個技能收成 6 個。舊技能的資料夾整個搬到新技能的 `references/<舊名>/`，入口 `SKILL.md` 改名為 `README.md`，內容逐字保留（只有往外指的相對連結跟著改寫），所以**舊技能的每一條規則都還在新位置**。新技能的 `SKILL.md` 只寫怎麼選、怎麼判斷，細節連到這些 reference 與 [template catalog](template-catalog.md)。

`project-knowledge` 的兩個檔案位元組不變（sha256 仍和 `third_party/claude-obsidian-source.json` 記錄的相同），`.gitattributes` 的 `-text` 規則改到新路徑。全域安裝的那一份不受影響。

PR 8.3 刪掉了 5 個只剩轉址文字的舊 reference（下表標「已刪除」），程式改連正式頁；見[轉址檔索引](../archive/redirect-stubs.md)。

指向**本來就已刪除**的舊資產與舊轉址檔的紀錄（[轉址檔索引](../archive/redirect-stubs.md)、實驗腳本、`test_templates` 的舊位置檢查）維持原本的舊路徑，沒有改寫。

## 新技能

| 新技能 | 收進來的舊技能 |
|---|---|
| [`game-art-brief`](../../../skills/game-art-brief/SKILL.md) | game-art-workflow、game-art-edit-brief、game-art-initialize、project-knowledge |
| [`platform-image-gen`](../../../skills/platform-image-gen/SKILL.md) | （不變） |
| [`comfyui-run`](../../../skills/comfyui-run/SKILL.md) | comfyui-art-gen、comfyui-object-design、comfyui-video-gen、comfyui-character-animation-workflow、comfyui-film-workflow、comfyui-face-swap-workflow、comfyui-video-layers、comfyui-wan-animate、comfyui-image-sweep |
| [`local-media-tools`](../../../skills/local-media-tools/SKILL.md) | local-image-edit-tools；另外把 `gameart.py vfx`（去背、打包、Idle 量測）的入口放在這裡 |
| [`comfyui-extend`](../../../skills/comfyui-extend/SKILL.md) | comfyui-new-tool-checklist、comfyui-pipeline-review；新增固定 graph 照[擴充協議](extension-protocol.md) |
| [`comfyui-install`](../../../skills/comfyui-install/SKILL.md) | （不變） |

## 檔案對照

| 舊技能 | 舊路徑 | 新路徑 |
|---|---|---|
| comfyui-art-gen | `skills/comfyui-art-gen/SKILL.md` | [`skills/comfyui-run/references/comfyui-art-gen/README.md`](../../../skills/comfyui-run/references/comfyui-art-gen/README.md) |
| comfyui-art-gen | `skills/comfyui-art-gen/reference/masking.md` | `skills/comfyui-run/references/comfyui-art-gen/reference/masking.md`（PR 8.3 已刪除；正式內容在 [masking.md](../art/masking.md)） |
| comfyui-art-gen | `skills/comfyui-art-gen/reference/profiles/sd15_light.md` | `skills/comfyui-run/references/comfyui-art-gen/reference/profiles/sd15_light.md`（PR 8.3 已刪除；正式內容在 [sd15-light.md](../art/profiles/sd15-light.md)） |
| comfyui-art-gen | `skills/comfyui-art-gen/reference/profiles/sdxl_standard.md` | `skills/comfyui-run/references/comfyui-art-gen/reference/profiles/sdxl_standard.md`（PR 8.3 已刪除；正式內容在 [sdxl-standard.md](../art/profiles/sdxl-standard.md)） |
| comfyui-art-gen | `skills/comfyui-art-gen/reference/structure-ref.md` | `skills/comfyui-run/references/comfyui-art-gen/reference/structure-ref.md`（PR 8.3 已刪除；正式內容在 [structure-ref.md](../art/structure-ref.md)） |
| comfyui-character-animation-workflow | `skills/comfyui-character-animation-workflow/SKILL.md` | [`skills/comfyui-run/references/comfyui-character-animation-workflow/README.md`](../../../skills/comfyui-run/references/comfyui-character-animation-workflow/README.md) |
| comfyui-face-swap-workflow | `skills/comfyui-face-swap-workflow/SKILL.md` | [`skills/comfyui-run/references/comfyui-face-swap-workflow/README.md`](../../../skills/comfyui-run/references/comfyui-face-swap-workflow/README.md) |
| comfyui-face-swap-workflow | `skills/comfyui-face-swap-workflow/references/integration.md` | [`skills/comfyui-run/references/comfyui-face-swap-workflow/references/integration.md`](../../../skills/comfyui-run/references/comfyui-face-swap-workflow/references/integration.md) |
| comfyui-face-swap-workflow | `skills/comfyui-face-swap-workflow/references/local-tool.md` | [`skills/comfyui-run/references/comfyui-face-swap-workflow/references/local-tool.md`](../../../skills/comfyui-run/references/comfyui-face-swap-workflow/references/local-tool.md) |
| comfyui-face-swap-workflow | `skills/comfyui-face-swap-workflow/references/reactor.md` | [`skills/comfyui-run/references/comfyui-face-swap-workflow/references/reactor.md`](../../../skills/comfyui-run/references/comfyui-face-swap-workflow/references/reactor.md) |
| comfyui-film-workflow | `skills/comfyui-film-workflow/SKILL.md` | [`skills/comfyui-run/references/comfyui-film-workflow/README.md`](../../../skills/comfyui-run/references/comfyui-film-workflow/README.md) |
| comfyui-film-workflow | `skills/comfyui-film-workflow/references/audio-tools.md` | [`skills/comfyui-run/references/comfyui-film-workflow/references/audio-tools.md`](../../../skills/comfyui-run/references/comfyui-film-workflow/references/audio-tools.md) |
| comfyui-film-workflow | `skills/comfyui-film-workflow/references/lipsync-tools.md` | [`skills/comfyui-run/references/comfyui-film-workflow/references/lipsync-tools.md`](../../../skills/comfyui-run/references/comfyui-film-workflow/references/lipsync-tools.md) |
| comfyui-film-workflow | `skills/comfyui-film-workflow/references/production-plan.md` | [`skills/comfyui-run/references/comfyui-film-workflow/references/production-plan.md`](../../../skills/comfyui-run/references/comfyui-film-workflow/references/production-plan.md) |
| comfyui-film-workflow | `skills/comfyui-film-workflow/references/sources.md` | [`skills/comfyui-run/references/comfyui-film-workflow/references/sources.md`](../../../skills/comfyui-run/references/comfyui-film-workflow/references/sources.md) |
| comfyui-image-sweep | `skills/comfyui-image-sweep/SKILL.md` | [`skills/comfyui-run/references/comfyui-image-sweep/README.md`](../../../skills/comfyui-run/references/comfyui-image-sweep/README.md) |
| comfyui-image-sweep | `skills/comfyui-image-sweep/reference/plan-format.md` | [`skills/comfyui-run/references/comfyui-image-sweep/reference/plan-format.md`](../../../skills/comfyui-run/references/comfyui-image-sweep/reference/plan-format.md) |
| comfyui-new-tool-checklist | `skills/comfyui-new-tool-checklist/SKILL.md` | [`skills/comfyui-extend/references/comfyui-new-tool-checklist/README.md`](../../../skills/comfyui-extend/references/comfyui-new-tool-checklist/README.md) |
| comfyui-object-design | `skills/comfyui-object-design/SKILL.md` | [`skills/comfyui-run/references/comfyui-object-design/README.md`](../../../skills/comfyui-run/references/comfyui-object-design/README.md) |
| comfyui-pipeline-review | `skills/comfyui-pipeline-review/SKILL.md` | [`skills/comfyui-extend/references/comfyui-pipeline-review/README.md`](../../../skills/comfyui-extend/references/comfyui-pipeline-review/README.md) |
| comfyui-video-gen | `skills/comfyui-video-gen/SKILL.md` | [`skills/comfyui-run/references/comfyui-video-gen/README.md`](../../../skills/comfyui-run/references/comfyui-video-gen/README.md) |
| comfyui-video-layers | `skills/comfyui-video-layers/SKILL.md` | [`skills/comfyui-run/references/comfyui-video-layers/README.md`](../../../skills/comfyui-run/references/comfyui-video-layers/README.md) |
| comfyui-video-layers | `skills/comfyui-video-layers/references/local-tool.md` | [`skills/comfyui-run/references/comfyui-video-layers/references/local-tool.md`](../../../skills/comfyui-run/references/comfyui-video-layers/references/local-tool.md) |
| comfyui-video-layers | `skills/comfyui-video-layers/references/sam3-track.md` | [`skills/comfyui-run/references/comfyui-video-layers/references/sam3-track.md`](../../../skills/comfyui-run/references/comfyui-video-layers/references/sam3-track.md) |
| comfyui-wan-animate | `skills/comfyui-wan-animate/SKILL.md` | [`skills/comfyui-run/references/comfyui-wan-animate/README.md`](../../../skills/comfyui-run/references/comfyui-wan-animate/README.md) |
| comfyui-wan-animate | `skills/comfyui-wan-animate/references/comfyui-api.md` | [`skills/comfyui-run/references/comfyui-wan-animate/references/comfyui-api.md`](../../../skills/comfyui-run/references/comfyui-wan-animate/references/comfyui-api.md) |
| comfyui-wan-animate | `skills/comfyui-wan-animate/references/scail2.md` | [`skills/comfyui-run/references/comfyui-wan-animate/references/scail2.md`](../../../skills/comfyui-run/references/comfyui-wan-animate/references/scail2.md) |
| game-art-edit-brief | `skills/game-art-edit-brief/SKILL.md` | [`skills/game-art-brief/references/game-art-edit-brief/README.md`](../../../skills/game-art-brief/references/game-art-edit-brief/README.md) |
| game-art-edit-brief | `skills/game-art-edit-brief/references/openai-image-guidance.md` | [`skills/game-art-brief/references/game-art-edit-brief/references/openai-image-guidance.md`](../../../skills/game-art-brief/references/game-art-edit-brief/references/openai-image-guidance.md) |
| game-art-edit-brief | `skills/game-art-edit-brief/references/scenarios.md` | [`skills/game-art-brief/references/game-art-edit-brief/references/scenarios.md`](../../../skills/game-art-brief/references/game-art-edit-brief/references/scenarios.md) |
| game-art-initialize | `skills/game-art-initialize/SKILL.md` | [`skills/game-art-brief/references/game-art-initialize/README.md`](../../../skills/game-art-brief/references/game-art-initialize/README.md) |
| game-art-workflow | `skills/game-art-workflow/SKILL.md` | [`skills/game-art-brief/references/game-art-workflow/README.md`](../../../skills/game-art-brief/references/game-art-workflow/README.md) |
| game-art-workflow | `skills/game-art-workflow/references/production.md` | [`skills/game-art-brief/references/game-art-workflow/references/production.md`](../../../skills/game-art-brief/references/game-art-workflow/references/production.md) |
| game-art-workflow | `skills/game-art-workflow/references/responsibilities.md` | [`skills/game-art-brief/references/game-art-workflow/references/responsibilities.md`](../../../skills/game-art-brief/references/game-art-workflow/references/responsibilities.md) |
| local-image-edit-tools | `skills/local-image-edit-tools/SKILL.md` | [`skills/local-media-tools/references/local-image-edit-tools/README.md`](../../../skills/local-media-tools/references/local-image-edit-tools/README.md) |
| local-image-edit-tools | `skills/local-image-edit-tools/reference/examples/character-action.json` | [`skills/local-media-tools/references/local-image-edit-tools/reference/examples/character-action.json`](../../../skills/local-media-tools/references/local-image-edit-tools/reference/examples/character-action.json) |
| local-image-edit-tools | `skills/local-image-edit-tools/reference/examples/guided-inpaint.json` | [`skills/local-media-tools/references/local-image-edit-tools/reference/examples/guided-inpaint.json`](../../../skills/local-media-tools/references/local-image-edit-tools/reference/examples/guided-inpaint.json) |
| local-image-edit-tools | `skills/local-image-edit-tools/reference/plan-format.md` | [`skills/local-media-tools/references/local-image-edit-tools/reference/plan-format.md`](../../../skills/local-media-tools/references/local-image-edit-tools/reference/plan-format.md) |
| project-knowledge | `skills/project-knowledge/SKILL.md` | [`skills/game-art-brief/references/project-knowledge/README.md`](../../../skills/game-art-brief/references/project-knowledge/README.md) |
| project-knowledge | `skills/project-knowledge/references/runtime-binding.md` | [`skills/game-art-brief/references/project-knowledge/references/runtime-binding.md`](../../../skills/game-art-brief/references/project-knowledge/references/runtime-binding.md) |

## 路由走查

用典型需求走一次：從新技能入口選到哪個指令、哪份 template 或 recipe。template id 由 `image_template_select.variant_id` 與 recipe 檔實際算出，沒有連 ComfyUI、沒有送 prompt（本機證據：`output/verify-20261008-7.3/routing-walkthrough.md`）。

| 需求 | 技能 | 指令 | template／recipe | template 檔存在 |
|---|---|---|---|---|
| 圖示（icon） | game-art-brief → comfyui-run（平台路線則 platform-image-gen） | generate.py icon_asset [--structure-ref] [--appearance-ref] [--remove-bg] | image/sdxl/icon-asset；加結構參考＋去背是 image/sdxl/icon-asset-structure-transparent | 是 |
| 本機局部重繪（圖片 inpaint） | comfyui-run（只做像素合成、不重畫時是 local-media-tools 的 composite） | generate.py inpaint／guided_inpaint | image/sdxl/inpaint；有錨點＋pose 是 image/sdxl/guided-inpaint-pose | 是 |
| 物件遮罩＋VACE 影片局部重繪 | comfyui-run | gameart.py recipe run object-mark-inpaint（確認點後 resume --confirm）；單步可用 gameart.py run video/wan-vace/inpaint | recipe draft：track:template=video/sam3/track-mask、review_masks:confirm、inpaint:template=video/wan-vace/inpaint | 是 |
| 換道具（prop swap） | comfyui-run（貼道具那步是 local-media-tools 的 vfx prop-paste） | gameart.py recipe show prop-swap --draft（草稿，使用者核准前不能當正式流程） | recipe draft：master_still:note、prop_paste:local、review_master:confirm、pose_drive:template=video/h3/pose-drive-canny | 是 |
| Idle 動作（首尾相接） | comfyui-run（規則 R3、template 的 frame_anchoring） | gameart.py recipe show idle-anchored-action --draft；量測用 gameart.py vfx loop-metrics | recipe draft：review_idle:confirm、h3_img2video:template=video/h3/img2video-last、wan_img2video:note=video/wan/img2video | 是 |
| 特效去背輸出 | local-media-tools | gameart.py vfx luma-alpha｜chroma-alpha → pack；草稿 recipe fx-alpha-export | 不用 template；recipe draft：alpha:local、review_preview:confirm、pack:local | 是 |
| 新 node 提案 | comfyui-extend | 照 docs/knowledge/maintenance/extension-protocol.md 提案；不臨場組 graph | 新 template 從 draft 開始；先看官方範本或 core blueprint | 是 |

video/wan-vace/inpaint 狀態：technical_pass，平台：{'windows-cuda': 'technical_pass', 'macos-mps': 'untested'}
