---
name: comfyui-video-gen
description: 將短片、循環特效與鏡頭需求路由到已接入的影片 task，檢查機器能力、生成並逐支驗收；不處理靜態圖片。
---

# 影片產線

## 職責與交接

短動態特效的需求、時間階段、交付與內容驗收方法由[共用製作流程](../game-art-workflow/references/production.md)維護。本技能負責 ComfyUI 七個影片生成 task 的 backend/capability gate、執行及影片技術契約；本機 `video_concat`、`video_composite` 與抽幀亦沿用既有入口。

上述本機處理不需 ComfyUI server，但仍依賴 `generate.py` facade、整個 `comfyui_pipeline/` 及相關 PyAV/Pillow/NumPy runtime，不是任意平台可執行的獨立單檔。平台圖片工具只能生成靜態素材；目前沒有平台影片執行技能或已接入 provider，不能把共用 VFX 計畫當成影片執行能力。

先查[工具範圍總表](../../docs/knowledge/TOOLS.md)，了解當前可用能力；本技能只用既有 CLI，不臨場組 ComfyUI graph。Backend、模型/runtime、影格、驗收細節與實測經驗見[影片知識庫](../../docs/knowledge/video/README.md)。歷史設計（包含未實作項目）見[影片設計稿](../../docs/knowledge/video/design.md)，不可把規劃當作可用 task。

## 何時使用

影片、過場、循環特效、讓靜幀動起來或單支多鏡短片使用本技能。單張靜態圖走 `comfyui-art-gen`。需要同一角色一整組遊戲動作與分階段人工驗收，改走[單角色動畫 workflow](../comfyui-character-animation-workflow/SKILL.md)。

劇情多鏡製作、長影片規劃與分鏡，先走 [劇情影片流程](../comfyui-film-workflow/SKILL.md) 建立鏡頭表與連續性紀錄，再回本技能逐鏡執行。單支影片仍直接使用本技能。

不以 `transition` 做傳統硬切／疊化／擦除；Logo 或中文字效果不可靠，直接說明限制。成品不自動以系統播放器開啟，只回報檔案路徑。

## 開始前

沿用前文的素材、尺寸、時長與授權，不重問。讀 `local_config.json` 及 `video_capabilities.json`；快照缺少或依賴變更時重跑 `detect_video_capabilities.py`（只盤點、不下載）。ComfyUI task 明確帶 `--config` 或 `--comfy-url`，按需加 `--video-config`。本機 concat/composite 不需 URL/backend，但需 PyAV/Pillow，合成另需 numpy。

規劃前檢查 backend/task capabilities。缺關鍵能力先告知並停下；`unverified` 先說明。只有 config 有 `default_backend` 才可省略 `--backend`。不因缺依賴而換 task 或自動切 H3/Wan；要產靜幀另查圖片快照。

## task 路由

| 需求 | task |
|---|---|
| 原構圖靜幀動起來、idle | `img2video` |
| 主體靜止，只推拉搖鏡 | `camera_move` |
| 角色參考圖演新動作／換場景，首幀可改 | `character_video` |
| 角色靜幀由動作影片驅動 | `pose_drive` |
| 循環特效、火焰、法陣、旗幟 | `fx_loop` |
| A 畫面變成 B | `transition`，要兩張靜幀 |
| 同場接續前鏡 | `clip_extend` |
| 接片／乾淨綠幕合成 | `video_concat`／`video_composite`（本機）|
| 有劇情的短片 | 先逐鏡建表，再呼叫現有 task、最後 concat；不可一條超長 prompt |

生成影片沒指定時長預設 2 秒，可指定 2–6 秒；更長拆鏡。影片固定 24 FPS，沒有 `--fps`。`--width` 和 `--height` 成對；生成畫布縮至長邊 768 內並向下對齊 32，不能保證任意交付尺寸。Backend 對齊影格後的實際時長未必正好等於要求；有其他規格要求時先說明差距，不虛構旗標。

## 每支影片必要輸入

- `img2video`、`fx_loop`、`camera_move`：靜幀和英文 prompt；camera 再給 `--camera` 枚舉。`img2video` 預設只留 MP4，`fx_loop` 預設抽幀（不需時用 `--no-extract-frames`）。
- `transition`：`--start`、`--end` 及中間變化；`clip_extend`：前段 `--video` 或尾幀 `--image` 二選一及續接描述。
- `character_video`：至少一張 `--character-ref` 及新鏡頭 prompt；首幀可異於參考圖。`pose_drive`：角色 `--image`、`--motion-ref` 及英文描述；姿勢／方向貼近參考片首幀。否則先抽首幀，以目標角色圖做 `character_action` 起姿並驗收。控制預設 pose，可選 canny/depth。
- `video_concat`：至少兩支影片、順序、名稱及明確的音訊／尺寸政策；預設混合有聲無聲即拒絕、尺寸不同亦拒絕。`drop` 丟全部音軌、`silence-missing` 補靜音；尺寸可選 `fit`（黑邊）、`fill`（裁切）、`stretch`，不默默調整。
- `video_composite`：產線輸出的乾淨純綠幕 `--foreground`，及影片／圖片 `--background`。只做 chroma key，非語意分割；只留前景音軌。

## 執行 CLI

使用本機 `python_exe` 與 `generate_script`。生成 task 都明確帶 `--config` 或 `--comfy-url`、按需 `--video-config`、一般 timeout `--timeout 1800` 及 `--output-dir`；backend 不從模型名猜。例：

```text
<python_exe> <generate_script> img2video --config <local_config.json> [--video-config <video_capabilities.json>] --timeout 1800 --image <path> --prompt "..." [--backend h3|wan] [--duration 2] [--extract-frames] --output-dir <output_dir>
```

其他 task 的原始 CLI（含純本機 concat/composite）見[影片 CLI 參考](../../docs/knowledge/video/cli.md)，只讀本次會用到的 task。

## 驗收與交付

每個生成 MP4 都讀同名 `.mp4.json` sidecar 與 `actual_pyav_metadata.validation.status`。`fail` 不交付；`warning` 按 warning 人工確認；`pass` 僅技術通過。核對要求/實際尺寸、FPS、幀數、duration、音訊與輸入 seed/路徑/hash。抽幀目錄須至少一幀並完整解碼；實際幀數需符合 sidecar，抽幀失敗要保留上一版。只用已驗收 MP4 呼叫既有 `extract_video_frames(video_path, output_dir)`，不為抽幀重新生成；它寫 staging、完整解碼後才替換目錄，不重建 sidecar。完整 helper argv 用法見[單角色動畫 workflow](../comfyui-character-animation-workflow/SKILL.md)。

人工核對角色身份、prompt 動作、構圖/運鏡方向、起訖幀或多輪 loop 接縫，以及 concat/composite 的順序、縮放、音訊和綠幕邊緣。連續性指標只找候選問題，未跨題材校準，不判定角色品質。由使用者決定接受、調整或放棄；未接受仍保留供比較。報告檔案路徑與待判斷點，不自動開播放器、不自動重送或覆寫。

目前未接入第三方付費 provider、透明影片、逐幀 AI 去背、APNG 或 sprite-sheet 打包。若將來接入付費 provider，每次付費前先列 provider/backend、輸入素材、時長、輸出數量與估價，取得使用者確認後才送出；失敗不自動付費重試。外部輸出若沒有本機 sidecar，不能宣稱有相同追溯性。
