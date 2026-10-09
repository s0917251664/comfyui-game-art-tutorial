---
type: adr
status: accepted
date: 2026-10-08
---
# ADR：圖片 template 的結構組合（D13 方案 A）與家族對應

使用者於交接時授權定案。本頁是生效決定；圖片 template 依此落地。

## 背景

第 4 階段把 [`image_graphs.py`](../../../tools_src/comfyui_pipeline/image_graphs.py) 的圖片 task 抽成 `templates/image/**`。[第二階段 ADR](2026-10-07-phase2-template-runner.md) 的 D13 把「會增刪或更換節點的組合」留到這裡。runner（`runner/template.py`）的 slot 只能改既有 input；`check_patched` 禁止新增、刪除節點或改 `class_type`。

會改變 graph 結構的軸有：LoRA（插入 `LoraLoader`）、去背（尾端接上去背節點）、`control_type`（前處理節點類型）、`control_backend`（Union 多一個 `SetUnionControlNetType`）、icon 的結構／外觀參考、guided_inpaint 的 control／appearance。

## 決定

1. **D13 採方案 A。** 每種會增刪或更換節點的組合各一份固定 template。runner 只填值，不插入節點。離線產生器 [`build_image_templates.py`](../../../tools_src/maintenance/build_image_templates.py) 呼叫既有 builder（只讀）寫出 graph；它不在 runner 執行路徑上。第 5 階段用 [`image_template_select.py`](../../../tools_src/comfyui_pipeline/image_template_select.py) 把 task、家族與結構旗標換成 template id，再由 [`image_from_template.py`](../../../tools_src/comfyui_pipeline/image_from_template.py) 填 slot。圖片 task 的 `build_graph` 已走這條路徑。sd15 目錄還沒落地的 task 仍用 builder；SDXL、layer_split、FLUX.2 找不到 template 就停止，不改走 builder。
2. **每個模型家族一份。** `image/sdxl/*` 對應 profile `sdxl_standard`，`image/sd15/*` 對應 `sd15_light`。sdxl_high 與 sdxl 的 graph 相同，不另做。tier 只影響呼叫端傳入的寬高，不另做 template；template 預設尺寸維持該家族的原生尺寸（SDXL 1024、SD1.5 512）。icon_asset 用原生尺寸，sdxl_light 仍是 1024。inpaint、guided_inpaint、refine、upscale、layer_split 沒有預設寬高。FLUX.2 固定 1024。
3. **保留 builder 的 `filename_prefix`。** 做成一般 string slot，預設值就是 builder 的前綴（例如 `concept`）。去背後另一個 `SaveImage` 的前綴維持字面 `transparent`，不併進同一個 slot。不用 type `output_prefix`：那個會被改成 `gameart/...`，第 5 階段的 graph sha256 會對不上。
4. **checkpoint 是 slot**，預設是該家族的底模。`--style` 換檔時由呼叫端傳入。LoRA 檔是使用者自備，只出現在有 `LoraLoader` 的 variant 的 slot，不放進 models pin。
5. **圖片 `frame_anchoring.time_alignment` 允許 null。** `TIME_ALIGNMENTS` 含 `None`，[`template.schema.json`](../../../templates/_schema/template.schema.json) 的 `time_alignment` 允許 null。既有影片 template 維持原值。
6. **組合不刪。** CLI 能產生的結構都有 template：LoRA、remove-bg、control_type、control_backend、structure／appearance ref、guided_inpaint 的 control／appearance。sd15 做不到的（ControlNet、IPAdapter、character_action、pose_only、style_lock）不做 sd15 版。layer_split 與 FLUX.2 不分家族：`image/layer-split`、`image/flux2/concept`、`image/flux2/edit`。
7. **全部 `status: draft`。** 平台 `windows-cuda` 與 `macos-mps` 都是 `untested`。`min_comfyui_version` 是 `0.34.0`。官方 workflow template 是 UI 格式，對不上這些 API graph，`provenance.upstream.kind` 為 `none`（name、blob、comfyui_version 皆 null）。

### icon_asset 的兩份 graph

builder 的 `build_icon_asset` 本身不接去背；CLI（`tasks/__init__.py` 與 `cli.py`）在 `icon_asset` 回傳後一定呼叫 `attach_bg_removal`。兩種結構都保留：沒有 `-transparent` 的 id 對齊 builder／golden，有 `-transparent` 的 id 對齊 CLI。第 5 階段走 CLI 時要傳 `remove_bg=True`。

因此份數是 sdxl 72（icon 16）、sd15 13（icon 4）、layer_split 1、FLUX.2 2，合計 88。草稿表的約 78 份把 icon 算成一律去背（sdxl 8、sd15 2）。

### 模型 pin

每個 graph 裡的模型檔都要有 64 位 sha256 與整數 `size_bytes`。檔案不在磁碟上就不寫該 variant，也不捏造 hash。`source` 與 `url` 在不知道固定 revision 時都是 null。sha256 有值時 `path` 為 `models/<directory>/<filename>`，directory 來自 profile 的 `dir`（FLUX.2 為 `diffusion_models`、`text_encoders`、`vae`）。

`OpenposePreprocessor`／`DepthAnythingV2Preprocessor` 記 `comfyui_controlnet_aux`；`IPAdapterAdvanced`／`IPAdapterModelLoader` 記 `comfyui_ipadapter_plus`（套件 `pyproject.toml` 的 `name`）。`LoadBackgroundRemovalModel`、`SetUnionControlNetType`、`Canny`、`CheckpointLoaderSimple` 在 ComfyUI core 或 `comfy_extras`，不列入 `requires_custom_nodes`。

## 範圍

- 這份 ADR 不改候選由使用者驗收的規則。template 輸出角色仍是 candidate（去背時透明圖為 candidate，不透明圖為 preview）。
- 產生器讀本機 ComfyUI 的模型檔來 pin。本機沒有 `dreamshaper_8.safetensors` 時，sd15 variant 不落地；補上檔案後用同一支產生器寫出，規則不變。
