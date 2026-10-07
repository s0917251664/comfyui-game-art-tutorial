# video/wan-animate/move

**Wan Animate Move（單段 17／33 幀）**（v1.0.0，draft）

參考角色跟著來源影片的動作動起來（背景由參考圖與 prompt 決定）。

狀態說明：Windows CUDA 已技術通過；dw-ll_ucoco_384.onnx 的 pin 補齊（2.2）前依規則維持 draft。

- 必填：`reference_image`、`source_video`、`prompt`
- 選填：`frames`、`width`、`height`、`seed`
- option：`keep_audio`
- 固定參數：16 FPS、6 steps、CFG 1、euler/simple、shift 8、text encoder 在 CPU、DWPose 解析度 384
- 平台：windows-cuda technical_pass、macos-mps untested

完整欄位用 `python tools_src/gameart.py run show video/wan-animate/move` 查看。操作契約與實測紀錄見 [comfyui-api.md](../../../../skills/comfyui-wan-animate/references/comfyui-api.md)。
