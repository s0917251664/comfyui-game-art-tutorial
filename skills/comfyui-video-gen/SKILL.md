# ComfyUI 遊戲美術產影片

給任何操作這個 repo 的 agent 使用。設計背景見同資料夾 `DESIGN.md`。

## 何時使用

當使用者要影片、過場、循環特效、讓靜幀動起來、或一支有分鏡的短片時使用。

**不要用於**:
- 還沒有過關靜幀、想憑空文生影片 → 先走 `skills/comfyui-art-gen/SKILL.md` 出圖,再回來
- 傳統硬切/疊化/擦除 → 剪接軟體,不要用 `transition`
- Logo/中文字進影片 → 跟靜態一樣弱,如實說做不到
- 「這個角色去做別的動作/換場景,但第一幀不必是那張定稿圖」才用 `character_video`;只要這張靜幀原構圖動起來 → `img2video`

**不要自動用系統播放器打開成品。** 只回報路徑。

## 環境

先讀 `local_config.json`。ComfyUI 要在 `<comfyui_url>` 跑著；每個需要送工作給 ComfyUI 的 CLI 範例都要明確帶 `--comfy-url <URL>` 或 `--config <local_config.json>`，不要假設腳本會自動搜尋設定檔。影片生成等待上限建議帶 `--timeout 1800`（秒）；這是輪詢 ComfyUI 生成結果的上限，不是 server port。純本地的 `video_concat` 不需要 URL 或 timeout。

`<python_exe> <generate_script> <task> [--comfy-url <URL> | --config <local_config.json>] [--timeout 1800] [options] --output-dir <output_dir>`

## 任務判斷

| 使用者說的像... | task |
|---|---|
| 「讓這張圖動起來」「idle / 展示」 | `img2video` |
| 「推鏡/搖鏡/拉遠/繞一圈」「主體別動只運鏡」 | `camera_move`(細節見 `reference/camera-move.md`) |
| 「這個角色去做別的動作/換場景,第一幀不必是那張圖」 | `character_video`(對應靜態 `style_lock`;細節見 `reference/character-video.md`) |
| 「用這段動作/影片驅動這個角色」「表演套到角色上」 | `pose_drive`(對應靜態 `character_action`;細節見 `reference/pose-drive.md`) |
| 「循環特效、火、法陣、旗幟、進引擎的 frames」 | `fx_loop`(預設抽 png 序列) |
| 「從 A 畫面變成 B」「內容轉場、傳送門」 | `transition`(要兩張靜幀) |
| 「接下去下一鏡」「同一場繼續」 | `clip_extend` |
| 「把這幾支短片接成一支」 | `video_concat` |
| 「做一部有劇情的片子 / 15 秒過場」 | **先出鏡頭表**,再逐鏡呼叫上面的 task,最後 `video_concat`。不准收成一個超長 prompt |

`--backend` 通常不用問(用這台機器的預設)。只要快、可接受無聲才指定另一個。哪個 task 接了哪個 backend,見 `reference/backends.md`;沒接上的組合腳本會報錯,不要因此改 task 名。

時長沒要求就 **2 秒**,上限 6 秒,更長拆鏡。

## 固定問題

### img2video
1. 靜幀路徑
2. 要怎麼動(英文 prompt)
3. 時長(預設 2)

### fx_loop
1. 靜幀路徑
2. 循環怎麼動(會自動補 seamless loop)
3. 時長(預設 2)。預設抽幀;使用者不要 frames 才加 `--no-extract-frames`

`img2video` 預設只留下 mp4；需要 png 序列時才加 `--extract-frames`。其他影片 task 也只有明確加上 `--extract-frames` 才抽幀。

### transition
1. 起始靜幀 `--start`
2. 結束靜幀 `--end`
3. 中間發生什麼

### clip_extend
1. 上一支 mp4(`--video`)或上一鏡尾幀圖(`--image`),二選一
2. 接下來發生什麼

### character_video
1. 角色參考圖(`--character-ref`,可多張;第一張同時決定預設畫布比例)
2. 新鏡頭裡這個角色在做什麼(英文 prompt;第一幀不必是參考圖)
3. 時長(預設 2)

### camera_move
1. 靜幀路徑
2. 運鏡(`--camera`: static / pan_up / pan_down / pan_left / pan_right / zoom_in / zoom_out / orbit_cw / orbit_ccw)
3. 時長(預設 2)。場景描述選填,不給就當主體完全靜止

### pose_drive
1. 角色靜幀 `--image`
2. 動作參考影片 `--motion-ref`
3. **靜幀姿勢/朝向必須接近動作片第一幀**(跟靜態 `character_action` 一樣)。站姿持槍去套走路片會雙人/重影,不要硬跑——沒有接近的靜幀時,先抽動作片第一幀當角色圖,或先走圖片產線 `character_action` 擺成那個起點姿勢
4. 這段在做什麼(英文 prompt)
5. 時長(預設 2)。`--control-type` 預設 pose;細節見 `reference/pose-drive.md`

### 有劇情的短片(鏡頭表,必做)

使用者要「一部片子」時,**先寫鏡頭表再生成**,每鏡一行:

1. 鏡號(A1, A2…)
2. 這鏡做什麼(一句話 → `--prompt`)
3. 時長(秒)
4. 靜幀從哪來(現有圖 / 先產圖 / 上一鏡尾幀)
5. task(`img2video` / `character_video` / `camera_move` / `pose_drive` / `fx_loop` / `transition` / `clip_extend`)
6. 跟前一鏡怎麼接(硬切 concat / 尾幀延續 / 首尾幀轉場)

全部生成完用 `video_concat --video a.mp4 --video b.mp4 ...` 接起來。配樂字幕仍在 ComfyUI 外面。

## 執行

```
img2video:
  <python_exe> <generate_script> img2video --config <local_config.json> --timeout 1800 --image <path> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] --output-dir <output_dir>

fx_loop:
  <python_exe> <generate_script> fx_loop --config <local_config.json> --timeout 1800 --image <path> --prompt "..." [--backend h3|wan] [--duration 2] [--no-extract-frames] --output-dir <output_dir>

transition:
  <python_exe> <generate_script> transition --config <local_config.json> --timeout 1800 --start <A> --end <B> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] --output-dir <output_dir>

clip_extend:
  <python_exe> <generate_script> clip_extend --config <local_config.json> --timeout 1800 --video <prev.mp4> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] --output-dir <output_dir>

video_concat:
  <python_exe> <generate_script> video_concat --video <a.mp4> --video <b.mp4> --output-dir <output_dir>

character_video:
  <python_exe> <generate_script> character_video --config <local_config.json> --timeout 1800 --character-ref <path> [--character-ref <path2>] --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] --output-dir <output_dir>

camera_move:
  <python_exe> <generate_script> camera_move --config <local_config.json> --timeout 1800 --image <path> --camera zoom_in|zoom_out|pan_left|pan_right|pan_up|pan_down|orbit_cw|orbit_ccw|static [--prompt "..."] [--backend h3|wan] [--duration 2] [--extract-frames] --output-dir <output_dir>

pose_drive:
  <python_exe> <generate_script> pose_drive --config <local_config.json> --timeout 1800 --image <char.png> --motion-ref <motion.mp4> --prompt "..." [--control-type pose|canny|depth] [--backend h3|wan] [--duration 2] [--extract-frames] --output-dir <output_dir>
```

## 已知限制

- 一次 2~6 秒。長片 = 多鏡頭 + `clip_extend` + `video_concat`
- `character_video` 鎖身份、不鎖構圖;要構圖不動用 `img2video`
- `fx_loop` 首尾幀實測平均像素差可以很低,不保證任意題材都完美閉環
- 沒有影片去背
- `camera_move` 的 `--camera` 是枚舉;有 last_frame 的 backend 會再餵幾何終點靜幀(見 `reference/camera-move.md`)。`orbit_*` 只靠 prompt
- `video_concat` 每支都有音軌才接立體聲;有任何一支無聲,整段當無聲(不要半段有聲)
- `pose_drive` 要角色靜幀 + 動作影片,而且**靜幀姿勢要接近動作片第一幀**;對不上會雙人/重影,不要拿兩張不相干的素材硬綁。預設 h3 臉比 wan 穩,仍不是像素鎖臉;只要快才 `--backend wan`
- 各 backend 能力表 / 這台機器預設是誰,見 `reference/backends.md`

細節見 `DESIGN.md`。
