# video/h3/pose-drive-depth

**MiniMax H3 動作驅動（depth）**（v0.1.0，draft）

MiniMax H3 Ref2VA，靜幀加 depth 前處理後的動作片。graph 由 build_pose_drive_h3（video_config=None）產生。

- builder：`build_pose_drive_h3`，`video_config=None`（檔名與第 6.1 階段 golden 相同）
- 平台：windows-cuda untested、macos-mps untested。模型 `platforms` 只記 windows-cuda，且與頂層 pin 相同
- prompt、檔名前綴、seed、寬、高、長度都是 slot。檔名前綴是 string，預設為 builder 的預設值
- template 不改寫 prompt。h3 的角色參考與動作驅動若要 `<Picture>`／`<Video>` 前綴，呼叫端要自己放進 prompt
- `tasks/video.py` 尚未改走這份 template（第 6.3 階段）

決定見 [影片模型 pin](../../../../docs/knowledge/decisions/2026-10-08-video-model-pins.md)。
