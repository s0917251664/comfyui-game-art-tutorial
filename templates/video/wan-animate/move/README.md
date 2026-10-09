# video/wan-animate/move

**Wan Animate Move（單段 17／33 幀）**（v1.1.2，technical_pass）

參考角色跟著來源影片的動作動起來（背景由參考圖與 prompt 決定）。

- 必填：`reference_image`、`source_video`、`prompt`
- 選填：`frames`、`width`、`height`、`seed`
- option：`keep_audio`
- 固定參數：16 FPS、6 steps、CFG 1、euler/simple、shift 8、text encoder 在 CPU、DWPose 解析度 384
- 平台：windows-cuda technical_pass、macos-mps untested

完整欄位用 `python tools_src/gameart.py run show video/wan-animate/move` 查看。操作契約與實測紀錄見 [wan-animate-choice.md](../../../../docs/knowledge/video/wan-animate-choice.md)。
