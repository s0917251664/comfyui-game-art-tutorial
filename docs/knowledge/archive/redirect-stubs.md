---
type: archive-index
status: current
---
# 已移除的轉址檔（redirect stubs）索引

這些檔案原本只剩「內容已移到 canonical 頁」的轉址文字。2026-10 第一階段文件整理時移除，改由本表保留「舊路徑 → canonical 位置」的對照；原檔內容可從 git 歷史取得（`git log --all -- <舊路徑>`）。

新文件請直接連 canonical 頁，不要再連舊路徑。

## 已移除

PR 8.3（2026-10-08）移除了最後 5 個還被程式引用的轉址檔（程式改連正式頁）。其中 `skills/comfyui-art-gen/` 底下的 4 個，在 PR 7.3 到 8.3 之間曾經放在 `skills/comfyui-run/references/comfyui-art-gen/` 底下；PR 7.3 為 profile 筆記另外留的兩個轉址檔也一起移除。

| 舊路徑 | canonical 位置 |
|---|---|
| `skills/comfyui-art-gen/reference/control-type-selection.md` | [`docs/knowledge/art/control-type-selection.md`](../art/control-type-selection.md) |
| `skills/comfyui-art-gen/reference/full-params.md` | [`docs/knowledge/art-parameters.md`](../art-parameters.md) |
| `skills/comfyui-art-gen/reference/known-limitations.md` | [`docs/knowledge/art/known-limitations.md`](../art/known-limitations.md) |
| `skills/comfyui-art-gen/reference/layered-assets.md` | [`docs/knowledge/art/layered-assets.md`](../art/layered-assets.md) |
| `skills/comfyui-art-gen/reference/result-records.md` | [`docs/knowledge/result-records.md`](../result-records.md) |
| `skills/comfyui-art-gen/reference/sam-segmentation.md` | [`docs/knowledge/art/sam-segmentation.md`](../art/sam-segmentation.md) |
| `skills/comfyui-art-gen/reference/task-guide.md` | [`docs/knowledge/art-generation.md`](../art-generation.md) |
| `skills/comfyui-video-gen/DESIGN.md` | [`docs/knowledge/video/design.md`](../video/design.md) |
| `skills/comfyui-video-gen/reference/backends.md` | [`docs/knowledge/video/README.md#backend模型與-runtime`](../video/README.md#backend模型與-runtime) |
| `skills/comfyui-video-gen/reference/camera-move.md` | [`docs/knowledge/video/README.md#camera_move`](../video/README.md#camera_move) |
| `skills/comfyui-video-gen/reference/character-video.md` | [`docs/knowledge/video/README.md#character_video`](../video/README.md#character_video) |
| `skills/comfyui-video-gen/reference/pose-drive.md` | [`docs/knowledge/video/README.md#pose_drive`](../video/README.md#pose_drive) |
| `skills/comfyui-video-gen/reference/video-composite.md` | [`docs/knowledge/video/README.md#video_composite`](../video/README.md#video_composite) |
| `skills/comfyui-install/reference/lora-training.md` | [`docs/knowledge/installation/lora-training.md`](../installation/lora-training.md) |
| `skills/comfyui-pipeline-review/reference/scan-categories.md` | [`docs/knowledge/maintenance/scan-categories.md`](../maintenance/scan-categories.md) |
| `skills/comfyui-character-animation-workflow/reference/templates.md` | [`docs/knowledge/animation/workflow.md`](../animation/workflow.md) |
| `docs/knowledge/flux2-and-structure-lock-observations.md` | [`docs/knowledge/experiences/flux2-and-structure-lock-observations.md`](../experiences/flux2-and-structure-lock-observations.md) |
| `skills/comfyui-install/reference/models.md` | [`docs/knowledge/installation/models-and-sources.md`](../installation/models-and-sources.md) |
| `skills/comfyui-art-gen/reference/masking.md` | [`docs/knowledge/art/masking.md`](../art/masking.md) |
| `skills/comfyui-art-gen/reference/structure-ref.md` | [`docs/knowledge/art/structure-ref.md`](../art/structure-ref.md) |
| `skills/comfyui-art-gen/reference/profiles/sd15_light.md` | [`docs/knowledge/art/profiles/sd15-light.md`](../art/profiles/sd15-light.md) |
| `skills/comfyui-art-gen/reference/profiles/sdxl_standard.md` | [`docs/knowledge/art/profiles/sdxl-standard.md`](../art/profiles/sdxl-standard.md) |

## 已刪除的舊資產（第二階段）

不是轉址檔，但同樣是「舊路徑已不存在、內容改由別處負責」，依 [D12](../decisions/2026-10-07-phase2-template-runner.md) 記在這裡。原檔可從 git 歷史取得。

| 舊路徑 | 取代位置 | 說明 |
|---|---|---|
| `skills/comfyui-wan-animate/assets/template-manifest.json` | `templates/video/wan-animate/<名稱>/template.json`（見 [templates/README](../../../templates/README.md)） | 2026-10-08 PR 2.4 刪除。原本記錄 Wan Animate／SCAIL-2 固定 graph 的位置、模型 pin（repo、revision、bytes、sha256）與固定參數；這些都已在各 template.json 的 `models`、`fixed_notes`、`provenance`，刪除前逐一核對過 sha256 與 bytes 一致。`assets/` 資料夾隨之移除 |

## 暫時保留（仍被程式、設定檔或測試引用）

下列轉址檔還在原位，因為程式碼、profile JSON 或測試直接引用它們的路徑；第一階段只改文件，所以不動。文件內的連結已改指 canonical 頁。等之後改程式或 profile 時再一起移除。

| 轉址檔 | canonical 位置 | 引用來源 |
|---|---|---|
| `skills/comfyui-run/references/comfyui-art-gen/reference/profiles/sd15_light.md` | [`docs/knowledge/art/profiles/sd15-light.md`](../art/profiles/sd15-light.md) | `tools_src/comfyui_pipeline/profiles/sd15_light.json` 的 `notes_ref`，以及 `tests/test_image_profiles.py` 的 `test_profile_notes_ref_points_to_existing_document`。改 profile JSON 會改變 profile 內容雜湊，影響已記錄的驗證證據 |
| `skills/comfyui-run/references/comfyui-art-gen/reference/profiles/sdxl_standard.md` | [`docs/knowledge/art/profiles/sdxl-standard.md`](../art/profiles/sdxl-standard.md) | `tools_src/comfyui_pipeline/profiles/sdxl_standard.json` 的 `notes_ref`＋同一個測試（理由同上） |
| `skills/comfyui-install/reference/models.md` | [`docs/knowledge/installation/models-and-sources.md`](../installation/models-and-sources.md) | `tools_src/comfyui_pipeline/tasks/_common.py:58` 的錯誤訊息、`tools_src/comfyui_pipeline/image_graphs.py:97` 的註解 |
| `skills/comfyui-run/references/comfyui-art-gen/reference/structure-ref.md` | [`docs/knowledge/art/structure-ref.md`](../art/structure-ref.md) | `tools_src/comfyui_pipeline/tasks/image_basic.py:22` 的 `--structure-ref` help 文字、`image_graphs.py:402` 的 docstring |
| `skills/comfyui-run/references/comfyui-art-gen/reference/masking.md` | [`docs/knowledge/art/masking.md`](../art/masking.md) | `tools_src/comfyui_pipeline/image_graphs.py:901` 的註解 |
