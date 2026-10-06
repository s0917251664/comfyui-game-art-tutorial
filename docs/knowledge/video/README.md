---
type: tool-guide
status: active
---

# 影片產線知識

這頁是影片 task 的工具範圍、backend 選擇、技術契約與歷史驗收紀錄。repo 入口技能為 `skills/comfyui-video-gen/SKILL.md`（由 [TOOLS.md](../TOOLS.md) 路由）；ComfyUI server-side SAM 遮罩與 ordered layer 合成是獨立工具，規格與狀態見 [`layers.md`](layers.md) 及 `skills/comfyui-video-layers/SKILL.md`。要規劃單一角色多動作則改讀 [`animation/workflow.md`](../animation/workflow.md)。設計稿保留在 [`design.md`](design.md)，其中尚未接入的能力仍是規劃，不是可呼叫 task。

## 狀態與工具範圍

CLI 對外契約是 task 名與可選 `--backend`，不是模型名。已存在 task：`img2video`、`fx_loop`、`transition`、`clip_extend`、`video_concat`、`video_composite`、`character_video`、`camera_move`、`pose_drive`。細部旗標與必要輸入見技能入口。模型節點、prompt tag、圖形只由程式鎖定，不得為單次要求臨場組 ComfyUI graph。

生成 task 走已安裝的 ComfyUI；`video_concat`、`video_composite` 與 `extract_video_frames` 是本機處理，不需要 server/backend。`detect_video_capabilities.py` 僅盤點既有模型、runtime、nodes，缺依賴時在 upload/queue 前停止，不下載或靜默切換 backend。

| 能力 | 已接 backend | 使用 task |
|---|---|---|
| `i2v`：靜幀作首幀 | `h3`, `wan` | `img2video`, `clip_extend`, `camera_move` |
| `last_frame`：餵尾幀 | `h3` | `fx_loop`, `transition`；有此能力時 `camera_move` 可餵幾何終點 |
| `character_ref`：圖參考角色，首幀可改場景 | `h3` | `character_video` |
| `control_video`：角色圖 + 動作影片 | `h3`, `wan` | `pose_drive` |
| `audio` | `h3` | H3 支援音訊；Wan I2V/Fun Control 輸出無聲 |

實際可用性仍以本機 `video_capabilities.json` 的 backend/task 能力及 `default_backend` 為準。config 的預設為 null 時必須明確提供 `--backend`。不能因某 task 缺少 node、模型或 backend 而改 task，也不能假設 H3/Wan 自動替代。

## Backend、模型與 runtime

以下檔名是目前實作映射的機器模型，供裝機／除錯人員識別，不是 CLI 輸入，不表示每台機器已安裝：

| Backend task | 模型檔 | 注意事項 |
|---|---|---|
| H3 I2V / 首尾幀 | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 不可與角色參考模型混用 |
| H3 角色參考 / 動作驅動 | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | backend 內處理私有 `<Picture i>` / `<Video k>` tags；不是 Fun ControlNet Union |
| Wan I2V | `wan2.2_ti2v_5B_fp16.safetensors` | 較快、無聲、沒有尾幀能力 |
| Wan 動作驅動 | `wan2.2_fun_control_5B_bf16.safetensors` | 只供 Wan `pose_drive`，不可與 I2V 權重混用 |

`detect_video_capabilities.py` 只檢查指定 ComfyUI `.venv`、現有模型與（有 URL 時）`/object_info`；`generate.py` 送 input 前會再檢查 backend、模型 metadata、Python/PyTorch/Pillow/PyAV/CUDA/GPU 與 graph nodes。`device_config.json` 的圖片 tier 不決定影片 backend。使用 `pose`/`depth` 前需確認 `comfyui_controlnet_aux` 前處理模型已存在；不要讓第一次 smoke test 未經同意觸發下載。

H3 曾以 4080 16GB 實測較能保留身份且可有聲，Wan 跑得快但無聲、身份較易漂；這是 2026-08-26 的單機 bake-off，不能取代當前 capability config 或當成品質保證。完整歷史設計、比較及限制見 [`design.md`](design.md)。

## task 選擇與主要判斷

- 原構圖靜幀動起來：`img2video`。角色換場景或新表演、第一幀不必同靜幀：`character_video`。
- 只有運鏡：`camera_move`；角色動作影片驅動：`pose_drive`，且角色靜幀姿勢／朝向要接近動作片第一幀。
- 循環元素：`fx_loop`；A 到 B 內容變化：`transition`；同場景延續：`clip_extend`。
- 本機接片：`video_concat`；乾淨綠幕前景合背景：`video_composite`。傳統硬切、疊化等交剪輯軟體。
- 有劇情的多鏡需求先建鏡頭表，逐鏡呼叫既有 task，再串接；不要用一個超長 prompt 冒充分鏡。

`camera_move --camera` 為 `static`, `pan_up`, `pan_down`, `pan_left`, `pan_right`, `zoom_in`, `zoom_out`, `orbit_cw`, `orbit_ccw`。有 `last_frame` 的 backend 會用來源首幀與幾何終點靜幀；`orbit_*` 只是 prompt，平面裁切不能做真正繞拍。沒有 `--speed`；目前 zoom 倍率 1.35、pan 終點 crop 0.82，畫布限制見技能。Fun Camera 14B 約需兩顆 fp8 UNET 共 30GB 且需不同 VAE；PAI 5B 格式與 Comfy-Org loader 不相容，需另裝 custom node，故這兩條目前不在產線。

## 共通輸出契約

影片生成預設 2 秒，可指定 2–6 秒；長片拆鏡。所有生成及本機影片處理固定 24 FPS，沒有 `--fps`。生成 `--width`/`--height` 成對給定，畫布長邊縮到 768 內並向下對齊 32；不保證任意交付尺寸。Backend 對齊可能令實際時長與 2 秒不完全相同。影格數依 backend 契約。

生成產出 MP4 及同名 `.mp4.json` sidecar，記錄 task/backend、單次 resolve 的 seed、prompt/negative、輸入絕對路徑與 SHA-256、capability/config digest、模型 metadata、Comfy `prompt_id`、要求與實際 PyAV 契約、warning、耗時與輸出路徑。除非使用者明確要求，絕不自動用系統播放器開影片，只回報路徑與待判斷事項。

`--shot-id`／`--name` 用於安全、可追溯的輸出前綴；同一多鏡任務逐鏡命名後，sidecar 與素材可互相追查。

尺寸、FPS、幀數、duration、audio 不符合契約是 `fail`，不可交付；`warning` 保留原片並按訊息人工檢查；`pass` 只代表技術契約通過，不代表美術內容合格。連續性指標目前 warning-only，跨題材閾值未校準，不能代替身份、動作或 loop 品質判斷。`--resume` 僅當 sidecar 的 task/backend/seed/input/config/contract 全相符且影片重驗通過才跳過。同名輸出預設拒絕覆寫，除非明確 `--overwrite`。

timeout 會保存 `prompt_id` 及精確 queue/running ownership；只有確認該 prompt 仍在 pending queue 才精確移除。不可全域 `/interrupt`，也不可對 running/未知狀態自動重送。

## task 特有細節

### `pose_drive`

角色靜幀說明「是誰」，動作影片說明「怎麼動」。輸入角色圖需接近參考影片第一幀姿勢／朝向；站姿角色套走路片會造成雙人或重影。找不到起始 pose 時先從動作片抽首幀；若不是目標角色，先用目標角色靜幀加該姿勢走 `character_action`，驗收後再驅動。只有動作片本來就是目標角色且該幀已接受才直接當角色圖。`--control-type` 預設 `pose`，可用 `canny`、`depth`；參考影片短於輸出時，超出段的控制變弱。

2026-08-27 RTX 4080 16GB 實測：同一走路參考片、角色圖取動作首幀，H3 2.33 秒/56 幀/154.6 秒、H.264+AAC，首幀差 4.1，中後段臉可辨認；Wan 2.04 秒/49 幀/94.4 秒、H.264 無聲，中段起漂移至末幀換臉。另兩個跨角色的預備起姿案例（金甲騎士、紫袍法師）都輸出單人走路片。反例：棚拍持槍站姿去套走路片造成雙人；換 canny 雖單人但武器/場景亂。這是已記錄的單機案例，不是品質承諾。H3 不是像素級鎖臉，也不是真正 ControlNet Union；身份由靜幀角色參考、動作由預處理影片承擔。

正確綁法的完整比較（輸入為 `character_video_h3_00001_.mp4`，同 `pose`、2 秒、seed 42）：

| | H3 (`pose_drive_00004`) | Wan (`pose_drive_00003`) |
|---|---|---|
| 時間、輸出 | 154.6 秒；512×768、56 幀、2.33 秒、24 FPS、H.264+AAC 立體聲 | 94.4 秒；512×768、49 幀、2.04 秒、24 FPS、H.264 無聲 |
| 首幀差與畫面 | 4.1；一人走向鏡頭，背心、步槍、馬尾符合，末段仍可辨識 | 4.3；中段起漂、末段換臉，背心和槍套糊掉 |
| frames | `pose_drive_00004_frames/`（56 PNG） | `pose_drive_00003_frames/`（49 PNG） |

同一走路片驅動兩個不同目標角色的預備起姿案例：

| 目標 | 預備靜幀 | 時間與輸出 | 人工觀察 |
|---|---|---|---|
| 銀甲騎士 | `output/_walk_knight.png` | 208.8 秒；`output/pose_drive_00005_.mp4`，512×768、56 幀、2.33 秒、H.264+AAC | 金髮銀甲橘披風，在倉庫走向鏡頭，全片一人；frames `pose_drive_00005_frames/` |
| 紫袍法師 | `output/_walk_witch.png` | 151.4 秒；`output/pose_drive_00006_.mp4`，512×768、56 幀、2.33 秒、H.264+AAC | 紫帽紅髮紫袍金杖，在倉庫走向鏡頭，全片一人；frames `pose_drive_00006_frames/` |

上述棚拍／插畫靜幀與倉庫影片的首幀像素差可能偏高，應看角色身份，不要求場景構圖相同。錯誤綁法的舊輸出是 `output/pose_drive_00001_.mp4`（持槍棚拍站姿套走路影片，雙人）及 `output/pose_drive_00002_.mp4`（canny 單人但槍與場景亂）。歷史影片不自動播放。

### `character_video`

對應靜態 `style_lock`：參考 1–9 張角色圖，文字描述新鏡頭；第一幀可以不是參考圖。需角色參考圖，第一張決定預設畫布比例。不要用 SDXL IPAdapter/`--style` 或把 backend prompt tag 暴露給 CLI。已實測限制：2026-08-27 RTX 4080 16GB，單張角色圖生成倉庫行走 69.6 秒，512×768、56 幀、2.33 秒、24 FPS、H.264+AAC；第一幀差約 89，背景構圖改變但服裝、馬尾、步槍及角色身份仍可辨識。只要原構圖動起來就走 `img2video`；同場接續走 `clip_extend`。

### `camera_move`

`--prompt` 選填，只描述場景；枚舉決定運鏡，省略 prompt 即主體靜止。Ken Burns 沒有畫面外像素，不能揭露原圖外內容。2026-08-27 RTX 4080 測 zoom-in、seed 42：純 prompt 96.5 秒、首尾平均像素差 16.0；餵幾何終點圖 106.8 秒、差 41.8，末幀對幾何終點差 3.9，轉盤變大且沒有自己旋轉，輸出 768×768、56 幀、H.264+AAC。`orbit_*` 幾何終點尚未實測。

### `video_composite`

純本機 PyAV+numpy chroma key，不是語意分割，只適合本產線輸出的乾淨純 `#00FF00` 前景；輸入必須是綠幕素材，不保證任意實拍或主體含綠畫面能乾淨去背。支援前景 mp4、影片或靜態圖背景；背景短則循環、長則截斷，圖片重複使用。影音逐幀串流。只保留前景音軌，背景音丟棄，前景無聲則輸出無聲。輸出先寫暫存再原子替換，預設拒絕覆寫。預設 `--resize-mode fill`：等比放大裁切；`fit` 補黑邊、`stretch` 拉伸、`strict` 尺寸不同即拒絕。`--chroma-color` 須與素材一致；`--tolerance` 提高會移除更多近綠色、可能吃到主體；`--softness` 控邊緣羽化。RGB 最大通道距離對純綠生成片最佳；H.264 色偏、半透明煙霧、抗鋸齒綠邊、主體含綠仍須人工微調。沒有自動取樣、spill suppression 或 AI 分割。

### `video_concat`

輸入至少兩支 24 FPS MP4 與順序。預設 `--resize-mode strict`，尺寸/長寬比不一致即 fail；可明確選 `fit`、`fill` 或 `stretch`。預設 `--audio-policy require-consistent`，輸入混合有聲與無聲即拒絕。使用者選 `drop` 才全部移除音軌；`silence-missing` 才替缺音鏡補靜音。必須事先說明差異並取得選擇，不靜默裁切、拉伸或丟音訊；檢查音畫 duration drift。無 `extract-frames` 旗標，需要時對結果呼叫既有抽幀 helper。

## 抽幀與人工驗收

需要 PNG sequence 時，生成 task 明確加 `--extract-frames`；`img2video` 預設只留 MP4，`fx_loop` 預設抽幀、可加 `--no-extract-frames`。其他生成 task 只在明確要求時抽幀。`video_concat`/`video_composite` 後使用既有抽幀 helper。Helper 對 staging 完整解碼且至少一幀後才取代固定輸出目錄；失敗保留上一版。抽幀不重建 sidecar，不重新產生影片；核對 frames 數量與 sidecar 實際 frame count。

技術驗收後仍要逐支人眼檢查：I2V 保來源角色與動作；character video 核對臉、服裝、道具比例；pose drive 查是否雙人、重影、換臉；camera move 查運鏡方向且主體未表演；transition 核對起訖靜幀；clip extend 查接續；fx loop 至少連看多輪，檢查接縫、方向、慣性、表情與位置；concat/composite 查順序、縮放/裁切、音訊政策及合成邊緣。首尾像素差只可協助找候選問題。

需要主觀驗收時，回報可觀看路徑與具體項目，由使用者接受、調整或放棄。不要自動重送、覆寫或將 technical `pass` 推成使用者接受。透明影片、逐幀 AI 去背、APNG、sprite sheet 打包、外部 provider backend 尚未接入；本機綠幕合成不能宣稱透明序列能力。

## 已知限制及待辦界線

角色身份/動作自然度無法由目前自動分數保證；loop/transition 等連續性分數閾值尚未跨題材校準。輸入姿勢與動作首幀不符仍可能得到壞結果，即使 task 技術檢查 pass。背景音訊混音、字幕、配樂、對白與精剪交外部剪輯工具。雲端/API、Fun Camera、透明影片及包裝工具只出現在 [`design.md`](design.md) 的歷史/規劃討論，不代表已接入。

## 可靠範圍盤點

- [2026-10-03 本機影片可靠範圍盤點](reliability-audit-2026-10-03.md)：環境快照、MP4/sidecar 追溯、有限內容抽樣與下一階段基準缺口。

Wan Animate 為獨立固定 API 路徑，未接入 `generate.py` task/backend；使用／查詢依[專用技能](../../../skills/comfyui-wan-animate/SKILL.md)，安裝及歷史測試見[安裝紀錄](wan-animate-install.md)。本頁不取代執行前 live preflight。
