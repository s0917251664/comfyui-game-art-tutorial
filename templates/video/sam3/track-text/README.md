# video/sam3/track-text

**SAM3 影片物件追蹤（英文文字起手）**（v1.0.1，technical_pass）

以英文名詞指定物件，SAM3 追蹤整支影片，輸出逐幀灰階遮罩（白色＝選取）。

- 必填：`source_video`、`track_text`
- 固定參數：detection_threshold 0.5、detect_interval 1、max_objects 4、object_indices 空字串（全部物件）
- 平台：windows-cuda technical_pass、macos-mps untested

完整欄位用 `python tools_src/gameart.py run show video/sam3/track-text` 查看。操作說明見 [sam3-track.md](../../../../skills/comfyui-video-layers/references/sam3-track.md)。
