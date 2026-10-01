---
type: command-reference
status: active
---

# 影片 CLI

先由技能 `skills/comfyui-video-gen/SKILL.md` 核對需求與能力；這頁保存既有 task 的 CLI 寫法。生成影片使用本機 capability 支援的 backend；config 有 `default_backend` 才可省 `--backend`。一般 timeout 建議 1800 秒。每個生成 task 明確帶 `--config` 或 `--comfy-url`、可選 `--video-config` 與 `--output-dir`。不要為單次需求改 graph 或臆造旗標。

## `img2video`

```text
<python_exe> <generate_script> img2video --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --image <path> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>
```

預設只留 MP4；明確加 `--extract-frames` 才抽 PNG 序列。

## `fx_loop`

```text
<python_exe> <generate_script> fx_loop --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --image <path> --prompt "..." [--backend h3|wan] [--duration 2] [--no-extract-frames] [--overwrite] --output-dir <output_dir>
```

預設抽幀；不要影格才加 `--no-extract-frames`。

## `transition`

```text
<python_exe> <generate_script> transition --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --start <A> --end <B> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>
```

## `clip_extend`

```text
<python_exe> <generate_script> clip_extend --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --video <prev.mp4> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>
```

也可使用已支援的 `--image` 尾幀輸入；輸入契約與裝置支援先以程式及 capability preflight 確認。

## `character_video`

```text
<python_exe> <generate_script> character_video --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --character-ref <path> [--character-ref <path2>] --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>
```

## `camera_move`

```text
<python_exe> <generate_script> camera_move --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --image <path> --camera zoom_in|zoom_out|pan_left|pan_right|pan_up|pan_down|orbit_cw|orbit_ccw|static [--prompt "..."] [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>
```

## `pose_drive`

```text
<python_exe> <generate_script> pose_drive --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --image <char.png> --motion-ref <motion.mp4> --prompt "..." [--control-type pose|canny|depth] [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>
```

## `video_concat`（本機）

```text
<python_exe> <generate_script> video_concat --video <a.mp4> --video <b.mp4> --name scene_A --output-dir <output_dir> [--resize-mode strict|fit|fill|stretch] [--audio-policy require-consistent|drop|silence-missing] [--resume|--overwrite]
```

不需 ComfyUI URL、模型或 timeout。混合音軌／不同尺寸的處理選項須先與使用者確認，詳見[video_concat 技術與驗收細節](README.md)。

## `video_composite`（本機）

```text
<python_exe> <generate_script> video_composite --foreground <greenscreen.mp4> --background <bg.mp4|bg.png> [--chroma-color 00FF00] [--tolerance 60] [--softness 40] [--resize-mode fill|strict|fit|stretch] [--overwrite] --output-dir <output_dir>
```

不需 ComfyUI URL、模型或 timeout；這是綠幕 chroma key，不是 AI 去背。合成音訊及尺寸行為詳見[video_composite 技術細節](README.md)。
