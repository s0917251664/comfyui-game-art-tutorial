---
type: index
status: current
generated: true
---
# Template 能力索引

自動產生，勿手改。改 template.json 後重跑 tools_src/maintenance/build_catalog.py。

機器可讀的同一份清單是 [templates/catalog.json](../../../templates/catalog.json)。
這頁不記 graph hash，也不代替 `template.json` 的模型 pin。

## `image/flux2/concept`

- 用途：FLUX.2 文字概念圖
- 摘要：FLUX.2 文字概念圖。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：flux-2-klein-4b-fp8.safetensors（diffusion_models，unet）、qwen_3_4b.safetensors（text_encoders，clip）、flux2-vae.safetensors（vae，vae）
- 上游：none

## `image/flux2/edit`

- 用途：FLUX.2 參考圖編修
- 摘要：FLUX.2 參考圖編修。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：flux-2-klein-base-4b-fp8.safetensors（diffusion_models，unet）、qwen_3_4b.safetensors（text_encoders，clip）、flux2-vae.safetensors（vae，vae）
- 上游：none

## `image/layer-split`

- 用途：遮罩拆層
- 摘要：遮罩拆層。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：（無）
- 上游：none

## `image/sdxl/character-action-canny`

- 用途：角色動作（SDXL、canny）
- 摘要：角色動作（SDXL、canny）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/character-action-canny-lora`

- 用途：角色動作（SDXL、canny、LoRA）
- 摘要：角色動作（SDXL、canny、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/character-action-canny-lora-transparent`

- 用途：角色動作（SDXL、canny、LoRA、去背）
- 摘要：角色動作（SDXL、canny、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/character-action-canny-transparent`

- 用途：角色動作（SDXL、canny、去背）
- 摘要：角色動作（SDXL、canny、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/character-action-depth`

- 用途：角色動作（SDXL、depth）
- 摘要：角色動作（SDXL、depth）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/character-action-depth-lora`

- 用途：角色動作（SDXL、depth、LoRA）
- 摘要：角色動作（SDXL、depth、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/character-action-depth-lora-transparent`

- 用途：角色動作（SDXL、depth、LoRA、去背）
- 摘要：角色動作（SDXL、depth、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/character-action-depth-transparent`

- 用途：角色動作（SDXL、depth、去背）
- 摘要：角色動作（SDXL、depth、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/character-action-pose`

- 用途：角色動作（SDXL、pose）
- 摘要：角色動作（SDXL、pose）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/character-action-pose-lora`

- 用途：角色動作（SDXL、pose、LoRA）
- 摘要：角色動作（SDXL、pose、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/character-action-pose-lora-transparent`

- 用途：角色動作（SDXL、pose、LoRA、去背）
- 摘要：角色動作（SDXL、pose、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/character-action-pose-transparent`

- 用途：角色動作（SDXL、pose、去背）
- 摘要：角色動作（SDXL、pose、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/concept`

- 用途：文字概念圖（SDXL）
- 摘要：文字概念圖（SDXL）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）
- 上游：none

## `image/sdxl/concept-lora`

- 用途：文字概念圖（SDXL、LoRA）
- 摘要：文字概念圖（SDXL、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）
- 上游：none

## `image/sdxl/concept-lora-transparent`

- 用途：文字概念圖（SDXL、LoRA、去背）
- 摘要：文字概念圖（SDXL、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/concept-transparent`

- 用途：文字概念圖（SDXL、去背）
- 摘要：文字概念圖（SDXL、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/guided-inpaint`

- 用途：有錨點的局部重繪（SDXL）
- 摘要：有錨點的局部重繪（SDXL）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）
- 上游：none

## `image/sdxl/guided-inpaint-appearance`

- 用途：有錨點的局部重繪（SDXL、外觀參考）
- 摘要：有錨點的局部重繪（SDXL、外觀參考）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）
- 上游：none

## `image/sdxl/guided-inpaint-canny`

- 用途：有錨點的局部重繪（SDXL、canny）
- 摘要：有錨點的局部重繪（SDXL、canny）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/guided-inpaint-canny-appearance`

- 用途：有錨點的局部重繪（SDXL、canny、外觀參考）
- 摘要：有錨點的局部重繪（SDXL、canny、外觀參考）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/guided-inpaint-depth`

- 用途：有錨點的局部重繪（SDXL、depth）
- 摘要：有錨點的局部重繪（SDXL、depth）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/guided-inpaint-depth-appearance`

- 用途：有錨點的局部重繪（SDXL、depth、外觀參考）
- 摘要：有錨點的局部重繪（SDXL、depth、外觀參考）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/guided-inpaint-pose`

- 用途：有錨點的局部重繪（SDXL、pose）
- 摘要：有錨點的局部重繪（SDXL、pose）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/guided-inpaint-pose-appearance`

- 用途：有錨點的局部重繪（SDXL、pose、外觀參考）
- 摘要：有錨點的局部重繪（SDXL、pose、外觀參考）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/icon-asset`

- 用途：圖示素材（SDXL）
- 摘要：圖示素材（SDXL）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）
- 上游：none

## `image/sdxl/icon-asset-appearance`

- 用途：圖示素材（SDXL、外觀參考）
- 摘要：圖示素材（SDXL、外觀參考）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）
- 上游：none

## `image/sdxl/icon-asset-appearance-lora`

- 用途：圖示素材（SDXL、外觀參考、LoRA）
- 摘要：圖示素材（SDXL、外觀參考、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）
- 上游：none

## `image/sdxl/icon-asset-appearance-lora-transparent`

- 用途：圖示素材（SDXL、外觀參考、LoRA、去背）
- 摘要：圖示素材（SDXL、外觀參考、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/icon-asset-appearance-transparent`

- 用途：圖示素材（SDXL、外觀參考、去背）
- 摘要：圖示素材（SDXL、外觀參考、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/icon-asset-lora`

- 用途：圖示素材（SDXL、LoRA）
- 摘要：圖示素材（SDXL、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）
- 上游：none

## `image/sdxl/icon-asset-lora-transparent`

- 用途：圖示素材（SDXL、LoRA、去背）
- 摘要：圖示素材（SDXL、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/icon-asset-structure`

- 用途：圖示素材（SDXL、結構參考）
- 摘要：圖示素材（SDXL、結構參考）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/icon-asset-structure-appearance`

- 用途：圖示素材（SDXL、結構參考、外觀參考）
- 摘要：圖示素材（SDXL、結構參考、外觀參考）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/icon-asset-structure-appearance-lora`

- 用途：圖示素材（SDXL、結構參考、外觀參考、LoRA）
- 摘要：圖示素材（SDXL、結構參考、外觀參考、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/icon-asset-structure-appearance-lora-transparent`

- 用途：圖示素材（SDXL、結構參考、外觀參考、LoRA、去背）
- 摘要：圖示素材（SDXL、結構參考、外觀參考、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/icon-asset-structure-appearance-transparent`

- 用途：圖示素材（SDXL、結構參考、外觀參考、去背）
- 摘要：圖示素材（SDXL、結構參考、外觀參考、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/icon-asset-structure-lora`

- 用途：圖示素材（SDXL、結構參考、LoRA）
- 摘要：圖示素材（SDXL、結構參考、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/icon-asset-structure-lora-transparent`

- 用途：圖示素材（SDXL、結構參考、LoRA、去背）
- 摘要：圖示素材（SDXL、結構參考、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/icon-asset-structure-transparent`

- 用途：圖示素材（SDXL、結構參考、去背）
- 摘要：圖示素材（SDXL、結構參考、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/icon-asset-transparent`

- 用途：圖示素材（SDXL、去背）
- 摘要：圖示素材（SDXL、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/inpaint`

- 用途：局部重繪（SDXL）
- 摘要：局部重繪（SDXL）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）
- 上游：none

## `image/sdxl/pose-only-canny`

- 用途：姿勢控制（SDXL、canny）
- 摘要：姿勢控制（SDXL、canny）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-canny-lora`

- 用途：姿勢控制（SDXL、canny、LoRA）
- 摘要：姿勢控制（SDXL、canny、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-canny-lora-transparent`

- 用途：姿勢控制（SDXL、canny、LoRA、去背）
- 摘要：姿勢控制（SDXL、canny、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-canny-transparent`

- 用途：姿勢控制（SDXL、canny、去背）
- 摘要：姿勢控制（SDXL、canny、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-canny-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-depth`

- 用途：姿勢控制（SDXL、depth）
- 摘要：姿勢控制（SDXL、depth）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-depth-lora`

- 用途：姿勢控制（SDXL、depth、LoRA）
- 摘要：姿勢控制（SDXL、depth、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-depth-lora-transparent`

- 用途：姿勢控制（SDXL、depth、LoRA、去背）
- 摘要：姿勢控制（SDXL、depth、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-depth-transparent`

- 用途：姿勢控制（SDXL、depth、去背）
- 摘要：姿勢控制（SDXL、depth、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-depth-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-pose`

- 用途：姿勢控制（SDXL、pose）
- 摘要：姿勢控制（SDXL、pose）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-pose-lora`

- 用途：姿勢控制（SDXL、pose、LoRA）
- 摘要：姿勢控制（SDXL、pose、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-pose-lora-transparent`

- 用途：姿勢控制（SDXL、pose、LoRA、去背）
- 摘要：姿勢控制（SDXL、pose、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-pose-transparent`

- 用途：姿勢控制（SDXL、pose、去背）
- 摘要：姿勢控制（SDXL、pose、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、controlnet-openpose-sdxl-1.0.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-union-canny`

- 用途：姿勢控制（SDXL、Union、canny）
- 摘要：姿勢控制（SDXL、Union、canny）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-union-canny-lora`

- 用途：姿勢控制（SDXL、Union、canny、LoRA）
- 摘要：姿勢控制（SDXL、Union、canny、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-union-canny-lora-transparent`

- 用途：姿勢控制（SDXL、Union、canny、LoRA、去背）
- 摘要：姿勢控制（SDXL、Union、canny、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-union-canny-transparent`

- 用途：姿勢控制（SDXL、Union、canny、去背）
- 摘要：姿勢控制（SDXL、Union、canny、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-union-depth`

- 用途：姿勢控制（SDXL、Union、depth）
- 摘要：姿勢控制（SDXL、Union、depth）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-union-depth-lora`

- 用途：姿勢控制（SDXL、Union、depth、LoRA）
- 摘要：姿勢控制（SDXL、Union、depth、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-union-depth-lora-transparent`

- 用途：姿勢控制（SDXL、Union、depth、LoRA、去背）
- 摘要：姿勢控制（SDXL、Union、depth、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-union-depth-transparent`

- 用途：姿勢控制（SDXL、Union、depth、去背）
- 摘要：姿勢控制（SDXL、Union、depth、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-union-pose`

- 用途：姿勢控制（SDXL、Union、pose）
- 摘要：姿勢控制（SDXL、Union、pose）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-union-pose-lora`

- 用途：姿勢控制（SDXL、Union、pose、LoRA）
- 摘要：姿勢控制（SDXL、Union、pose、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）
- 上游：none

## `image/sdxl/pose-only-union-pose-lora-transparent`

- 用途：姿勢控制（SDXL、Union、pose、LoRA、去背）
- 摘要：姿勢控制（SDXL、Union、pose、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/pose-only-union-pose-transparent`

- 用途：姿勢控制（SDXL、Union、pose、去背）
- 摘要：姿勢控制（SDXL、Union、pose、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、xinsir-controlnet-union-sdxl-1.0-promax.safetensors（controlnet，controlnet）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/refine`

- 用途：圖生圖精修（SDXL）
- 摘要：圖生圖精修（SDXL）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）
- 上游：none

## `image/sdxl/refine-transparent`

- 用途：圖生圖精修（SDXL、去背）
- 摘要：圖生圖精修（SDXL、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/style-lock`

- 用途：外觀鎖定（SDXL）
- 摘要：外觀鎖定（SDXL）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）
- 上游：none

## `image/sdxl/style-lock-lora`

- 用途：外觀鎖定（SDXL、LoRA）
- 摘要：外觀鎖定（SDXL、LoRA）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）
- 上游：none

## `image/sdxl/style-lock-lora-transparent`

- 用途：外觀鎖定（SDXL、LoRA、去背）
- 摘要：外觀鎖定（SDXL、LoRA、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/style-lock-transparent`

- 用途：外觀鎖定（SDXL、去背）
- 摘要：外觀鎖定（SDXL、去背）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_ipadapter_plus [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors（clip_vision，clip_vision）、ip-adapter-plus_sdxl_vit-h.safetensors（ipadapter，ipadapter）、birefnet.safetensors（background_removal，bg_removal）
- 上游：none

## `image/sdxl/upscale`

- 用途：放大精修（SDXL）
- 摘要：放大精修（SDXL）。固定 API graph，runner 只填 slot。
- 媒體：image
- 能力：image_generation
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=null、continuity=null
- 模型：sd_xl_base_1.0.safetensors（checkpoints，checkpoint）、4x-UltraSharp.pth（upscale_models，upscale）
- 上游：none

## `video/h3/character-video-1`

- 用途：MiniMax H3 角色參考影片（1 張）
- 摘要：MiniMax H3 Ref2VA，1 張參考圖各一個 LoadImage。上限讀 CHARACTER_REF_MAX（9）。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：character_ref
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/character-video-2`

- 用途：MiniMax H3 角色參考影片（2 張）
- 摘要：MiniMax H3 Ref2VA，2 張參考圖各一個 LoadImage。上限讀 CHARACTER_REF_MAX（9）。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：character_ref
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/character-video-3`

- 用途：MiniMax H3 角色參考影片（3 張）
- 摘要：MiniMax H3 Ref2VA，3 張參考圖各一個 LoadImage。上限讀 CHARACTER_REF_MAX（9）。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：character_ref
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/character-video-4`

- 用途：MiniMax H3 角色參考影片（4 張）
- 摘要：MiniMax H3 Ref2VA，4 張參考圖各一個 LoadImage。上限讀 CHARACTER_REF_MAX（9）。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：character_ref
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/character-video-5`

- 用途：MiniMax H3 角色參考影片（5 張）
- 摘要：MiniMax H3 Ref2VA，5 張參考圖各一個 LoadImage。上限讀 CHARACTER_REF_MAX（9）。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：character_ref
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/character-video-6`

- 用途：MiniMax H3 角色參考影片（6 張）
- 摘要：MiniMax H3 Ref2VA，6 張參考圖各一個 LoadImage。上限讀 CHARACTER_REF_MAX（9）。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：character_ref
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/character-video-7`

- 用途：MiniMax H3 角色參考影片（7 張）
- 摘要：MiniMax H3 Ref2VA，7 張參考圖各一個 LoadImage。上限讀 CHARACTER_REF_MAX（9）。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：character_ref
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/character-video-8`

- 用途：MiniMax H3 角色參考影片（8 張）
- 摘要：MiniMax H3 Ref2VA，8 張參考圖各一個 LoadImage。上限讀 CHARACTER_REF_MAX（9）。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：character_ref
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/character-video-9`

- 用途：MiniMax H3 角色參考影片（9 張）
- 摘要：MiniMax H3 Ref2VA，9 張參考圖各一個 LoadImage。上限讀 CHARACTER_REF_MAX（9）。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：character_ref
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/img2video`

- 用途：MiniMax H3 圖生影片
- 摘要：MiniMax H3 圖生影片，沒有尾幀。graph 由 build_img2video_h3（video_config=None）產生。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：i2v
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=image、last=none、reference_role=none、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_fl2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/img2video-last`

- 用途：MiniMax H3 圖生影片（含尾幀）
- 摘要：MiniMax H3 圖生影片，含尾幀 LoadImage。fx_loop、transition、有終點靜幀的 camera_move 用這份。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：i2v
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=image、last=image、reference_role=none、time_alignment=source_from_frame_0、continuity=null
- 模型：minimax_h3_fl2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/pose-drive-canny`

- 用途：MiniMax H3 動作驅動（canny）
- 摘要：MiniMax H3 Ref2VA，靜幀加 canny 前處理後的動作片。graph 由 build_pose_drive_h3（video_config=None）產生。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：control_video
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=per_source_frame、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/pose-drive-depth`

- 用途：MiniMax H3 動作驅動（depth）
- 摘要：MiniMax H3 Ref2VA，靜幀加 depth 前處理後的動作片。graph 由 build_pose_drive_h3（video_config=None）產生。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：control_video
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=per_source_frame、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/h3/pose-drive-pose`

- 用途：MiniMax H3 動作驅動（pose）
- 摘要：MiniMax H3 Ref2VA，靜幀加 pose 前處理後的動作片。graph 由 build_pose_drive_h3（video_config=None）產生。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：control_video
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=per_source_frame、continuity=null
- 模型：minimax_h3_ref2va_pruned_int8_convrot.safetensors（diffusion_models，diffusion）、qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors（text_encoders，text_encoder）、minimax_h3_video_vae_fp16.safetensors（vae，vae）、minimax_h3_audio_vae_fp32.safetensors（vae，audio_vae）
- 上游：none

## `video/sam3/track-mask`

- 用途：SAM3 影片物件追蹤（第 0 幀手繪遮罩起手）
- 摘要：以第 0 幀遮罩指定一個物件，SAM3 追蹤整支影片，輸出逐幀灰階遮罩（白色＝選取）
- 媒體：video
- 能力：object_track
- 狀態：technical_pass（v1.0.2）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda technical_pass、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=selection、time_alignment=per_source_frame、continuity=null
- 模型：sam3.1_multiplex_fp16.safetensors（checkpoints，sam3）
- 上游：workflow_templates `video_wan21_scail2_character_replacement`

## `video/sam3/track-text`

- 用途：SAM3 影片物件追蹤（英文文字起手）
- 摘要：以英文名詞指定物件，SAM3 追蹤整支影片，輸出逐幀灰階遮罩（白色＝選取）
- 媒體：video
- 能力：object_track
- 狀態：technical_pass（v1.0.2）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda technical_pass、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=per_source_frame、continuity=null
- 模型：sam3.1_multiplex_fp16.safetensors（checkpoints，sam3）
- 上游：workflow_templates `video_wan21_scail2_character_replacement`

## `video/wan-animate/mix`

- 用途：Wan Animate Mix（單段 17／33 幀）
- 摘要：把參考角色置入來源影片（保留來源背景），以 SAM2 點位決定替換範圍
- 媒體：video
- 能力：wan_animate_mix
- 狀態：technical_pass（v1.1.2）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui-kjnodes [registry]、comfyui-segment-anything-2 [registry]
- 平台：windows-cuda technical_pass、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors（diffusion_models，diffusion）、lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors（loras，lora_distill）、WanAnimate_relight_lora_fp16.safetensors（loras，lora_relight）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan_2.1_vae.safetensors（vae，vae）、clip_vision_h.safetensors（clip_vision，clip_vision）、yolox_l.onnx（directory 未填，pose_bbox）、dw-ll_ucoco_384.onnx（directory 未填，pose_estimator）、sam2_hiera_base_plus.safetensors（sam2，sam2）
- 上游：workflow_templates `video_wan2_2_14B_animate`

## `video/wan-animate/mix-extend`

- 用途：Wan Animate Mix（兩段串接 61 幀）
- 摘要：把參考角色置入來源影片（保留來源背景），以 SAM2 點位決定替換範圍；兩段 33＋28＝61 幀
- 媒體：video
- 能力：wan_animate_mix
- 狀態：technical_pass（v1.1.2）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]、comfyui-kjnodes [registry]、comfyui-segment-anything-2 [registry]
- 平台：windows-cuda technical_pass、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity={"segments": 2, "overlap_frames": 5, "seam_frames": [32, 33], "manual_check": "seam"}
- 模型：Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors（diffusion_models，diffusion）、lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors（loras，lora_distill）、WanAnimate_relight_lora_fp16.safetensors（loras，lora_relight）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan_2.1_vae.safetensors（vae，vae）、clip_vision_h.safetensors（clip_vision，clip_vision）、yolox_l.onnx（directory 未填，pose_bbox）、dw-ll_ucoco_384.onnx（directory 未填，pose_estimator）、sam2_hiera_base_plus.safetensors（sam2，sam2）
- 上游：workflow_templates `video_wan2_2_14B_animate`

## `video/wan-animate/move`

- 用途：Wan Animate Move（單段 17／33 幀）
- 摘要：參考角色跟著來源影片的動作動起來（背景由參考圖與 prompt 決定）
- 媒體：video
- 能力：wan_animate_move
- 狀態：technical_pass（v1.1.2）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda technical_pass、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors（diffusion_models，diffusion）、lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors（loras，lora_distill）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan_2.1_vae.safetensors（vae，vae）、clip_vision_h.safetensors（clip_vision，clip_vision）、yolox_l.onnx（directory 未填，pose_bbox）、dw-ll_ucoco_384.onnx（directory 未填，pose_estimator）
- 上游：workflow_templates `video_wan2_2_14B_animate`

## `video/wan-animate/move-extend`

- 用途：Wan Animate Move（兩段串接 61 幀）
- 摘要：參考角色跟著來源影片的動作動起來（背景由參考圖與 prompt 決定）；兩段 33＋28＝61 幀
- 媒體：video
- 能力：wan_animate_move
- 狀態：technical_pass（v1.1.2）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda technical_pass、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity={"segments": 2, "overlap_frames": 5, "seam_frames": [32, 33], "manual_check": "seam"}
- 模型：Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors（diffusion_models，diffusion）、lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors（loras，lora_distill）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan_2.1_vae.safetensors（vae，vae）、clip_vision_h.safetensors（clip_vision，clip_vision）、yolox_l.onnx（directory 未填，pose_bbox）、dw-ll_ucoco_384.onnx（directory 未填，pose_estimator）
- 上游：workflow_templates `video_wan2_2_14B_animate`

## `video/wan-animate/scail2`

- 用途：SCAIL-2 角色替換／動畫（單段 33 幀）
- 摘要：用參考圖驅動角色跟著來源影片動，或把來源影片裡的人換成參考角色；SAM3 依文字追蹤人物並以彩色遮罩綁定身份
- 媒體：video
- 能力：scail2
- 狀態：technical_pass（v1.0.2）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda technical_pass、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity=null
- 模型：wan2.1_14B_SCAIL_2_fp8_scaled.safetensors（diffusion_models，diffusion）、wan2.1_SCAIL_2_DPO_lora_bf16.safetensors（loras，lora_dpo）、lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors（loras，lora_distill）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan_2.1_vae.safetensors（vae，vae）、clip_vision_h.safetensors（clip_vision，clip_vision）、sam3.1_multiplex_fp16.safetensors（checkpoints，sam3）
- 上游：workflow_templates `video_wan21_scail2_character_replacement`

## `video/wan-animate/scail2-extend`

- 用途：SCAIL-2 角色替換／動畫（兩段串接 61 幀）
- 摘要：用參考圖驅動角色跟著來源影片動，或把來源影片裡的人換成參考角色；SAM3 依文字追蹤人物並以彩色遮罩綁定身份
- 媒體：video
- 能力：scail2
- 狀態：technical_pass（v1.0.2）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda technical_pass、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=source_from_frame_0、continuity={"segments": 2, "overlap_frames": 5, "seam_frames": [32, 33], "manual_check": "seam"}
- 模型：wan2.1_14B_SCAIL_2_fp8_scaled.safetensors（diffusion_models，diffusion）、wan2.1_SCAIL_2_DPO_lora_bf16.safetensors（loras，lora_dpo）、lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors（loras，lora_distill）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan_2.1_vae.safetensors（vae，vae）、clip_vision_h.safetensors（clip_vision，clip_vision）、sam3.1_multiplex_fp16.safetensors（checkpoints，sam3）
- 上游：workflow_templates `video_wan21_scail2_character_replacement`

## `video/wan-vace/inpaint`

- 用途：Wan2.1 VACE 影片局部重繪（遮罩內重畫、貼回原片）
- 摘要：只重畫遮罩內（白色＝重畫），遮罩外貼回原片並逐 byte 檢查不變；和 generate.py video_inpaint 同一個 graph 與前後處理
- 媒體：video
- 能力：masked_edit
- 狀態：technical_pass（v0.1.1）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda technical_pass、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=none、time_alignment=per_source_frame、continuity=null
- 模型：wan2.1_vace_1.3B_fp16.safetensors（diffusion_models，vace_unet）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan_2.1_vae.safetensors（vae，vae）
- 上游：workflow_templates `video_wan_vace_inpainting`

## `video/wan/img2video`

- 用途：Wan 2.2 5B 圖生影片
- 摘要：Wan 2.2 5B 圖生影片，沒有尾幀。graph 由 build_img2video_wan（video_config=None）產生。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：i2v
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=image、last=none、reference_role=none、time_alignment=source_from_frame_0、continuity=null
- 模型：wan2.2_ti2v_5B_fp16.safetensors（diffusion_models，diffusion）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan2.2_vae.safetensors（vae，vae）
- 上游：workflow_templates `video_wan2_2_5B_ti2v`

## `video/wan/pose-drive-canny`

- 用途：Wan Fun Control 動作驅動（canny）
- 摘要：Wan Fun Control 5B，動作片前處理是 canny。graph 由 build_pose_drive_wan（video_config=None）產生。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：control_video
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：（只用 core）
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=per_source_frame、continuity=null
- 模型：wan2.2_fun_control_5B_bf16.safetensors（diffusion_models，diffusion）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan2.2_vae.safetensors（vae，vae）
- 上游：workflow_templates `video_wan2_2_5B_fun_control`

## `video/wan/pose-drive-depth`

- 用途：Wan Fun Control 動作驅動（depth）
- 摘要：Wan Fun Control 5B，動作片前處理是 depth。graph 由 build_pose_drive_wan（video_config=None）產生。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：control_video
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=per_source_frame、continuity=null
- 模型：wan2.2_fun_control_5B_bf16.safetensors（diffusion_models，diffusion）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan2.2_vae.safetensors（vae，vae）
- 上游：none

## `video/wan/pose-drive-pose`

- 用途：Wan Fun Control 動作驅動（pose）
- 摘要：Wan Fun Control 5B，動作片前處理是 pose。graph 由 build_pose_drive_wan（video_config=None）產生。變數是 placeholder，seed 是 -1。status draft，平台未實測。
- 媒體：video
- 能力：control_video
- 狀態：draft（v0.1.0）
- 最低 ComfyUI：0.34.0
- 第三方節點：comfyui_controlnet_aux [registry]
- 平台：windows-cuda untested、macos-mps untested
- 首尾幀：first=none、last=none、reference_role=identity、time_alignment=per_source_frame、continuity=null
- 模型：wan2.2_fun_control_5B_bf16.safetensors（diffusion_models，diffusion）、umt5_xxl_fp8_e4m3fn_scaled.safetensors（text_encoders，text_encoder）、wan2.2_vae.safetensors（vae，vae）
- 上游：none
