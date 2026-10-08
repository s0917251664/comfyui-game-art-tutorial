---
type: index
status: current
generated: true
---
# Template 能力索引

自動產生，勿手改。改 template.json 後重跑 tools_src/maintenance/build_catalog.py。

機器可讀的同一份清單是 [templates/catalog.json](../../../templates/catalog.json)。
這頁不記 graph hash，也不代替 `template.json` 的模型 pin。

## `video/sam3/track-mask`

- 用途：SAM3 影片物件追蹤（第 0 幀手繪遮罩起手）
- 摘要：以第 0 幀遮罩指定一個物件，SAM3 追蹤整支影片，輸出逐幀灰階遮罩（白色＝選取）
- 媒體：video
- 能力：object_track
- 狀態：technical_pass（v1.0.1）
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
- 狀態：technical_pass（v1.0.1）
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
- 狀態：technical_pass（v1.1.1）
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
- 狀態：technical_pass（v1.1.1）
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
- 狀態：technical_pass（v1.1.1）
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
- 狀態：technical_pass（v1.1.1）
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
- 狀態：technical_pass（v1.0.1）
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
- 狀態：technical_pass（v1.0.1）
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
