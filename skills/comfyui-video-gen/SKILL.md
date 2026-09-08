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

**這個需求該不該走這條管線(有現成 task 覆蓋、機器 tier/backend 撐不撐得起、還是該用 MCP/轉正成新 task)照 `skills/comfyui-art-gen/SKILL.md` 的「決策順序」小節,圖片/影片是同一套邏輯,不重複寫一次。**

## 環境

先讀 `local_config.json`。影片另外需要已安裝機器的 `video_capabilities.json`：若不存在或模型/runtime/nodes 有變，先依 `skills/comfyui-install/SKILL.md` 執行 `tools_src/detect_video_capabilities.py`；偵測器只掃描既有內容，不下載模型或套件。ComfyUI 要在 `<comfyui_url>` 跑著；每個需要送工作給 ComfyUI 的 CLI 範例都要明確帶 `--comfy-url <URL>` 或 `--config <local_config.json>`，必要時再帶 `--video-config <video_capabilities.json>`，不要假設腳本會自動搜尋 repository 設定檔。影片生成等待上限建議帶 `--timeout 1800`（秒）；這是輪詢 ComfyUI 生成結果的上限，不是 server port。純本地的 `video_concat` 不需要 URL 或 timeout。

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
| 「把綠幕特效疊到背景上」「合成/疊圖成一支」 | `video_composite`(chroma key,純本機不經 ComfyUI,細節見下方與 `reference/video-composite.md`) |
| 「做一部有劇情的片子 / 15 秒過場」 | **先出鏡頭表**,再逐鏡呼叫上面的 task,最後 `video_concat`。不准收成一個超長 prompt |

`--backend` 只有在 capability config 明確寫了 `default_backend` 時才可以省略；若 config 是 `null`，必須問清楚或要求使用者明確指定。不要因模型缺失、node 缺失或 task 不支援而自動換 H3/Wan。哪個 task 接了哪個 backend,見 `reference/backends.md`;沒接上的組合腳本會在 upload/queue 前報錯,不要因此改 task 名。

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

### video_composite(綠幕合成)
1. 前景 mp4(`--foreground`,必須是這條產線輸出的綠幕素材——純綠 `#00FF00` 背景,不是任意影片)
2. 背景(`--background`,mp4 或靜態圖都可以;背景比前景短就循環,比前景長就截斷)
3. 前景色碼跟去背素材本身綠幕的實際色碼是否一致(預設 `00FF00`,通常不用問,除非使用者自己調過綠幕色)

這個 task **純本機用 PyAV+numpy 串流逐幀 chroma key**,不呼叫 ComfyUI、不經過任何生成模型,所以不需要 `--comfy-url`/`--config`/`--timeout`。音訊只保留前景；背景有聲、前景無聲時，輸出仍為無聲。背景尺寸不同時預設 `--resize-mode fill`；目前不支援 `--resume`。調整去背邊緣與完整限制見 `reference/video-composite.md`。

### 有劇情的短片(鏡頭表,必做)

使用者要「一部片子」時,**先寫鏡頭表再生成**,每鏡一行:

1. 鏡號(A1, A2…)
2. 這鏡做什麼(一句話 → `--prompt`)
3. 時長(秒)
4. 靜幀從哪來(現有圖 / 先產圖 / 上一鏡尾幀)
5. task(`img2video` / `character_video` / `camera_move` / `pose_drive` / `fx_loop` / `transition` / `clip_extend`)
6. 跟前一鏡怎麼接(硬切 concat / 尾幀延續 / 首尾幀轉場)

全部生成完用 `video_concat --video a.mp4 --video b.mp4 ...` 接起來。配樂字幕仍在 ComfyUI 外面。

每支影片都會產生同名 `.mp4.json` sidecar，記錄 task/backend、只 resolve 一次的 seed、prompt、輸入檔絕對路徑與 SHA-256、capability/config digest、模型檔案 metadata、Comfy `prompt_id`、要求/實際輸出契約與 warning。尺寸、FPS、影格數、時長或音訊不符合要求會 fail；連續性指標目前是 warning-only，仍需人工檢查。`--resume` 只有在 sidecar 的 task/backend/seed/input/config/contract 全部完全相符且影片重新通過契約檢查時才會跳過。

## 產出後自檢

每支影片完成後，先技術驗收，再內容驗收。不要只看 CLI 有印出路徑，也不要把連續性分數當成角色品質分數。

### 技術驗收

1. 確認 MP4 與同名 sidecar 都存在，讀取 `actual_pyav_metadata.validation.status`。
2. `fail` 代表尺寸、FPS、影格數、時長或音訊等契約不符，不能當成功交付。
3. `warning` 代表檔案契約可讀，但連續性指標需要人工確認；它不是自動拒絕，也不是自動通過。
4. `pass` 只代表技術契約通過，不代表角色、動作或美術內容正確。
5. 有抽幀時確認目錄至少有一幀且完整解碼；失敗時保留上一版，不手動把 staging 當正式輸出。

### 內容驗收

- `img2video`：仍可辨識為來源靜幀，且動作符合 prompt，沒有不必要的整體溶解或身份漂移。
- `character_video`：新鏡頭成立，角色的臉、服裝、道具與比例仍可辨識；第一幀不需要等於參考圖。
- `pose_drive`：全程是預期角色與動作，沒有雙人、重影或中後段明顯換臉；先確認輸入姿勢／朝向本來就接近動作片第一幀。
- `camera_move`：運鏡方向符合枚舉，主體沒有被誤解成自己旋轉或表演。
- `transition`：起點與終點分別對得上指定靜幀，中間是內容轉場，不用它驗傳統硬切／疊化。
- `clip_extend`：開頭接得上上一鏡尾幀，角色、服裝、光線與動作方向沒有明顯斷裂。
- `fx_loop`：連續播放多輪，人工檢查接縫停頓、運動方向、慣性、表情與主體位置；首尾像素差只用來找問題候選。
- `video_concat`／`video_composite`：除契約外，實際查看鏡頭順序、縮放／裁切、音訊政策與合成邊緣是否符合本次明確選項。

本技能不自動開系統播放器。需要使用者做主觀驗收時，回報可觀看的檔案路徑與具體待判斷項目；由使用者決定接受、調整或放棄。若正在製作同一角色的一整組遊戲動作，改讀 `skills/comfyui-character-animation-workflow/SKILL.md` 編排分階段驗收。

### 4~6 鏡最小案例（鏡頭表 → 逐鏡 → concat）

例如「角色走進法陣、法陣循環、鏡頭推近、場景變成夜景」可先列：

| 鏡號 | task / 輸入 | 時長 | 接法 |
|---|---|---:|---|
| A01 | `img2video` + `hero_day.png`，角色向前一步 | 2s | 第一鏡 |
| A02 | `clip_extend` + A01 mp4，角色停下 | 2s | 尾幀延續 |
| A03 | `fx_loop` + `magic_circle.png`，法陣循環 | 2s | 獨立元素 |
| A04 | `camera_move` + A02 尾幀，`--camera zoom_in` | 2s | 尾幀延續 |
| A05 | `transition` + A04 尾幀 / `night_scene.png`，傳送門展開 | 2s | 首尾幀 |

每鏡用對應 CLI、帶 `--shot-id A01`…`A05`，確認 mp4 與 sidecar 都通過，再執行 `video_concat --name scene_A --video A01.mp4 ...`。這只是基本順序串接，不包含剪接節奏、字幕、配樂、對白或混音；完整成片仍交給外部剪接工具。

## 執行

```
img2video:
  <python_exe> <generate_script> img2video --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --image <path> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>

fx_loop:
  <python_exe> <generate_script> fx_loop --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --image <path> --prompt "..." [--backend h3|wan] [--duration 2] [--no-extract-frames] [--overwrite] --output-dir <output_dir>

transition:
  <python_exe> <generate_script> transition --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --start <A> --end <B> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>

clip_extend:
  <python_exe> <generate_script> clip_extend --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --video <prev.mp4> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>

video_concat:
  <python_exe> <generate_script> video_concat --video <a.mp4> --video <b.mp4> --name scene_A --output-dir <output_dir> [--resize-mode strict|fit|fill|stretch] [--audio-policy require-consistent|drop|silence-missing] [--resume|--overwrite]

video_composite:
  <python_exe> <generate_script> video_composite --foreground <greenscreen.mp4> --background <bg.mp4|bg.png> [--chroma-color 00FF00] [--tolerance 60] [--softness 40] [--resize-mode fill|strict|fit|stretch] [--overwrite] --output-dir <output_dir>

character_video:
  <python_exe> <generate_script> character_video --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --character-ref <path> [--character-ref <path2>] --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>

camera_move:
  <python_exe> <generate_script> camera_move --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --image <path> --camera zoom_in|zoom_out|pan_left|pan_right|pan_up|pan_down|orbit_cw|orbit_ccw|static [--prompt "..."] [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>

pose_drive:
  <python_exe> <generate_script> pose_drive --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --image <char.png> --motion-ref <motion.mp4> --prompt "..." [--control-type pose|canny|depth] [--backend h3|wan] [--duration 2] [--extract-frames] [--overwrite] --output-dir <output_dir>
```

## 已知限制

- 一次 2~6 秒。長片 = 多鏡頭 + `clip_extend` + `video_concat`
- `character_video` 鎖身份、不鎖構圖;要構圖不動用 `img2video`
- `fx_loop` 首尾幀實測平均像素差可以很低,不保證任意題材都完美閉環
- 沒有「AI 自動判斷主體邊界」的影片去背/合成(沒有語意分割模型)——`video_composite` 是 chroma key,只吃乾淨綠幕素材,對任意實拍影片/雜亂背景不適用；效果好壞取決於前景綠幕乾不乾淨跟 `--tolerance`/`--softness` 調得準不準,不保證任意素材都摳得乾淨
- `video_composite` 只保留前景音軌並丟棄背景音軌；需要背景聲、配樂或混音時交給外部剪接工具
- `camera_move` 的 `--camera` 是枚舉;有 last_frame 的 backend 會再餵幾何終點靜幀(見 `reference/camera-move.md`)。`orbit_*` 只靠 prompt
- `video_concat` 每支都有音軌才接立體聲;有任何一支無聲,整段當無聲(不要半段有聲)
- `pose_drive` 要角色靜幀 + 動作影片,而且**靜幀姿勢要接近動作片第一幀**;對不上會雙人/重影,不要拿兩張不相干的素材硬綁。歷史上 H3 臉比 Wan 穩，實際選擇以 capability config 為準；只要快才在確認 capability 後明確給 `--backend wan`
- 每支影片輸出都會在 CLI 回報 task/backend、尺寸、FPS、幀數、音訊、耗時與輸出路徑；同名輸出預設拒絕覆寫，只有明確給 `--overwrite` 才會更新
- 各 backend 能力表 / machine-specific config 規則,見 `reference/backends.md`
- 每支輸出都會有同名 `.mp4.json` sidecar：包含 task/backend、單次 resolve 的 seed、prompt/negative、輸入絕對路徑與 SHA-256、capability/config digest、模型檔名與 config 中的 hash/size、Comfy `prompt_id`、要求/實際 PyAV 契約、warnings、耗時與輸出路徑。尺寸、FPS、影格數、時長或音訊不符合契約會 fail；連續性指標目前 warning-only。
- `video_concat` 預設 `--resize-mode strict`，尺寸/長寬比不同會 fail；要處理時明確選 `fit`(加黑邊)、`fill`(裁切) 或 `stretch`。預設 `--audio-policy require-consistent`，混合有聲/無聲會 fail；`drop` 丟掉全部音軌，`silence-missing` 為缺音鏡補靜音，並檢查音畫 duration drift。
- `extract_video_frames` 先寫 staging，確認完整解碼且至少一幀後才換入固定輸出目錄；失敗會保留上一版影格。`--shot-id`/`--name` 產生安全、可追溯前綴；`--resume` 只有 sidecar 的 task/backend/seed/input/config/contract 全相符且輸出重新驗證通過時才跳過。
- 連續性指標檢查 `fx_loop` 首尾 seam、`transition` 首/尾對 start/end、`img2video`/`camera_move`/`clip_extend` 來源到輸出首幀；閾值未跨題材校準，不用它判定 character/pose 身份品質。
- timeout 會持久記錄 prompt_id 與精確 queue/running ownership；只有確認仍是該 prompt_id 的 pending queue item 時，才嘗試精確刪除，絕不呼叫全域 `/interrupt`，也不對 running/未知狀態自動重送工作。

細節見 `DESIGN.md`。
