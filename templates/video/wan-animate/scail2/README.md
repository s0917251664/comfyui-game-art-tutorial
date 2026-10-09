# video/wan-animate/scail2

**SCAIL-2 角色替換／動畫（單段 33 幀）**（v1.0.2，technical_pass）

用參考圖驅動角色跟著來源影片動，或把來源影片裡的人換成參考角色；SAM3 依文字追蹤人物並以彩色遮罩綁定身份。

- 必填：`reference_image`、`source_video`、`prompt`、`sam3_video_object`、`sam3_image_object`
- 選填：`seed`、`replacement_mode`、`object_indices`、`width`、`height`
- option：`keep_audio`
- 固定參數：16 FPS、每段 33 幀、DPO LoRA 1.0＋LightX2V 0.8、shift 5、6 steps、CFG 1、euler/simple、text encoder 在 CPU、negative prompt 空字串、SAM3 門檻 0.5、max_objects 4
- 平台：windows-cuda technical_pass、macos-mps untested

完整欄位用 `python tools_src/gameart.py run show video/wan-animate/scail2` 查看。操作契約與實測紀錄見 [scail2.md](../../../../skills/comfyui-run/references/comfyui-wan-animate/references/scail2.md)。
