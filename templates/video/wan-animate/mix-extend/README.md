# video/wan-animate/mix-extend

**Wan Animate Mix（兩段串接 61 幀）**（v1.1.1，technical_pass）

把參考角色置入來源影片（保留來源背景），以 SAM2 點位決定替換範圍；兩段 33＋28＝61 幀。

- 必填：`reference_image`、`source_video`、`prompt`、`positive_points`
- 選填：`width`、`height`、`seed`、`seed_segment2`、`negative_points`
- option：`keep_audio`
- 固定參數：16 FPS、6 steps、CFG 1、euler/simple、shift 8、text encoder 在 CPU、DWPose 解析度 384、GrowMask 10、BlockifyMask 32；node 300 length 固定 61，兩段各 33 幀
- 平台：windows-cuda technical_pass、macos-mps untested

完整欄位用 `python tools_src/gameart.py run show video/wan-animate/mix-extend` 查看。操作契約與實測紀錄見 [comfyui-api.md](../../../../skills/comfyui-wan-animate/references/comfyui-api.md)。
