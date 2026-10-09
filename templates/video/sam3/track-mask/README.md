# video/sam3/track-mask

**SAM3 影片物件追蹤（第 0 幀手繪遮罩起手）**（v1.0.2，technical_pass）

以第 0 幀遮罩指定一個物件，SAM3 追蹤整支影片，輸出逐幀灰階遮罩（白色＝選取）。

- 必填：`source_video`、`seed_mask`
- 固定參數：detection_threshold 0.5、detect_interval 1、max_objects 1、object_indices 空字串（全部物件）
- 平台：windows-cuda technical_pass、macos-mps untested

完整欄位用 `python tools_src/gameart.py run show video/sam3/track-mask` 查看。操作說明見 [sam3-track.md](../../../../skills/comfyui-run/references/comfyui-video-layers/references/sam3-track.md)。
