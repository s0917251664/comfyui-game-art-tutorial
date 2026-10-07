---
type: workflow
status: active
---

# 單角色遊戲動畫工作流程

本頁維護單角色動作組的 ComfyUI task 映射、技術 gate、抽幀與本機交付；repo 入口技能為 `skills/comfyui-character-animation-workflow/SKILL.md`（由 [TOOLS.md](../TOOLS.md) 路由）。角色母圖、代表動作、逐支選版與內容驗收方法統一由[共用製作流程](../../../skills/game-art-workflow/references/production.md#同一角色的動作集合)維護，不增加生成能力，也不把平台圖片工具當成影片工具。

## 決策前確認

先看本機 `image_capabilities.json`（所需 `style_lock`、`character_action` 等）及 `video_capabilities.json` 的 backend/task capabilities。不可用就不排入動作表；整條路線缺關鍵能力（例如沒有任何 `pose_drive` backend）先停下告知；`unverified` 要先告知使用者，再決定是否繼續。不要重問已從附件、前文得知的角色圖、偏好、尺寸、FPS、授權或驗收決定。

確認並記下：主參考角色靜幀是否定稿；各動作用途、是否循環、期望時長；交付尺寸/FPS/是否要 PNG frames；是否需轉身／背面；是否要求透明素材；可用 task 與 backend。現有影片固定 24 FPS，生成畫布長邊最多 768、尺寸依 backend 向下對齊 32；透明序列由 `gameart.py vfx` 後處理產生（見 [vfx-tools](../video/vfx-tools.md)），不是模型原生 RGBA。若需轉背面但參考素材不足，先停下補足素材，不把單張正面圖說成可靠三視圖。外部付費 provider 未接入時，不列為執行方案。

## 角色靜幀與動作表

角色、服裝、道具、比例與構圖先於圖片階段定稿；需要特定起始姿勢時，用 `character_action` 製作與動作參考影片首幀姿勢／方向接近的靜幀，並由使用者先驗收。task 不適用時說明取捨，讓使用者決定，不自動以別種 task 硬做。

動作表只列本案需要欄位，建議如下：

| 動作 | 遊戲用途 | 是否循環 | 期望時長 | 起始靜幀 | task | backend | 交付格式 |
|---|---|---|---:|---|---|---|---|
| Idle | 等待狀態 | 是 | 使用者指定 | 已驗收 Idle 圖 | `fx_loop`（H3，首＝尾＝Idle） | `h3` | MP4；需要時 PNG frames |
| Attack／Win／Fail 等回到 Idle 的動作 | 依用途 | 否 | 使用者指定 | 已驗收 Idle 圖（首尾） | `transition --start <Idle> --end <Idle>` | `h3` | MP4；需要時 PNG frames |

所有動作第一幀用已驗收 Idle 圖；哪些 task 會鎖首／尾幀、補邊與驗收量測依 [R3 Idle 錨定](../rules/idle-anchoring.md)。`img2video` 適用原構圖 idle/展示與只出不回的動作，`fx_loop` 用於明確需要無縫循環的元素，`character_video` 適用換場景/新表演且首幀可變，`pose_drive` 使用動作參考片，`camera_move` 主體不動只運鏡。不要為整組一致而把所有動作塞進同一 task。需要更貼近動作影片的表情與手勢、或把影片中人物換成角色時，可改走獨立的 [Wan Animate／SCAIL-2 技能](../../../skills/comfyui-wan-animate/SKILL.md)（固定 API graph，另有自己的 gate，不在 video_capabilities.json）。

## 製作與驗收

代表動作與其餘動作的順序依共用製作流程；本機每支需保留原始 MP4 與同名 `.mp4.json` sidecar：

- `fail`：技術契約不符，不進人工驗收或後製，先排查。
- `warning`：保留影片，按 warning 人工檢查；不把它自行當成功或失敗。
- `pass`：只代表尺寸/FPS/frame count/duration/audio 等技術契約通過，不代表角色或美術內容通過。

之後依影片技能的 task 驗收項目逐支看片：身份、服裝、道具、動作自然度、loop 接縫/方向/慣性/表情、音畫及鏡頭連續性。首尾像素差不等於身份或 loop 品質。記錄實際 MP4/sidecar 路徑、technical status、人工檢查點、使用者接受／調整／放棄決定與後續安排。未接受的原片保留供比較，不自動重送或覆寫。

### 逐支驗收紀錄

| 動作 | MP4／sidecar | 技術狀態 | 人工檢查重點 | 使用者決定 | 後續 |
|---|---|---|---|---|---|
| Idle | 實際路徑 | `pass`／`warning`／`fail` | 身份、動作、loop、腳底與接縫 | 接受／調整／放棄 | 接受後交付已準備的 frames 或從既有 MP4 抽幀 |

## Frames 與後製

支援 `--extract-frames` 的 task 可在生成時準備候選影格；`fx_loop` 預設抽幀。影格未隨 MP4 人工驗收之前，仍是候選，不作正式交付或合成來源。已接受 MP4 若尚未抽幀，從該 MP4 呼叫既有 `extract_video_frames(video_path, output_dir)`，不得為抽幀重生成。helper 會在 `<output_dir>/<stem>_frames/` 寫 staging，完整解碼且至少一幀才替換舊目錄；失敗保留舊影格。核對幀數與已驗收 sidecar 的實際 frame count。它不建新 CLI task、不重建 sidecar，也不接受 `--resume` / `--overwrite`。

依 `local_config.json` 的 `python_exe`、`generate_script` 所在資料夾、已接受 MP4 與輸出根目錄執行：

```text
<python_exe> -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path(sys.argv[1]))); from generate import extract_video_frames; extract_video_frames(sys.argv[2], sys.argv[3])" "<generate_script 資料夾>" "<accepted.mp4>" "<output_dir>"
```

依 shell 正確引用路徑；PowerShell 對帶引號的執行檔使用 `&`。抽幀或 `video_composite` 後，仍要再核對尺寸、FPS、影格數、音訊政策與畫面。綠幕合成是背景合成，不是透明序列；透明 PNG 序列、APNG、sprite sheet 用 `gameart.py vfx chroma-alpha`／`pack` 從已接受 MP4 產生。後製不能修復角色變形、重心錯誤或動作理解錯誤。

## 交付

| 動作 | 原始 MP4 | sidecar | frames／合成檔 | 技術狀態 | 已知限制 |
|---|---|---|---|---|---|

列已接受的動作與 MP4/frames 路徑、sidecar `pass`/`warning`、待確認或放棄項、已知限制及未執行後製。不要刪供應商/backend 原始輸出，不只交修剪／合成結果而失去來源追溯。不自動開系統播放器；回報路徑及待使用者判斷項。

## 付費與第三方輸出

目前未接入外部 provider backend。未來接入後，每次付費生成前先列 provider/backend、輸入素材、時長、輸出數量及估價，取得使用者確認後才送出；失敗不自動付費重試。第三方素材若無本機 sidecar，須如實記錄 provider、請求參數、原始檔及可取得的識別資訊，不假裝有同等追溯性。
