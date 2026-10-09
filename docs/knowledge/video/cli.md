---
type: command-reference
status: active
---

# 影片 CLI

先由技能 `skills/comfyui-run/references/comfyui-video-gen/README.md` 核對需求與能力；這頁保存既有 task 的 CLI 寫法。生成影片使用本機 capability 支援的 backend；config 有 `default_backend` 才可省 `--backend`。一般 timeout 建議 1800 秒。每個生成 task 明確帶 `--config` 或 `--comfy-url`、可選 `--video-config` 與 `--output-dir`。不要為單次需求改 graph 或臆造旗標。

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

## `video_inpaint`

```text
<python_exe> <generate_script> video_inpaint --config <local_config.json> [--video-config <video_capabilities.json>] --backend wan --timeout 1800 --video <src.mp4> --masks <masks_dir|layers.zip> [--mask-object 1] --mode keep|replace --prompt "..." [--seed N] [--grow 8] [--feather 4] [--pad 48] [--crop x0,y0,x1,y1] [--name <name>] --output-dir <output_dir>
```

遮罩為白色＝重畫的灰階 PNG（L，或 R=G=B 的 RGB）。預設由 SAM3 固定 graph（[sam3-track](../../../skills/comfyui-run/references/comfyui-video-layers/references/sam3-track.md)）產生；SAM3 不可用時，才用 SAM2 備援路線 `gameart.py vfx segment-plan` → `video_layers.py run` → `vfx unpack-masks`（`--masks` 也可直接給 `layers.zip`）。指令與旗標不變（`--resume` 除外，見下）。PR 8.3b 起整個交給 template runner 執行 `video/wan-vace/inpaint`（[R2](../rules/fixed-graphs.md)；先 preflight，平台不是 `technical_pass` 就擋下）。輸出在 `<output-dir>/<名稱>_run/`（`--name`／`--shot-id` 決定名稱）：runner 的 `run.result.json`、`outputs/raw/`（工作區原始 MP4）、`composited/`（無損 PNG 主檔、H.264 預覽，以及和舊版欄位相同的 `result.json`）。不再寫影片 sidecar；`--resume` 不支援（runner 不會重送，失敗時看 `run.result.json`，用新的 `--name` 重跑）。部署端要先用 `gameart.py deploy` 部署 `templates/`。完整流程與限制見 [`vfx-tools.md`](vfx-tools.md)。

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
