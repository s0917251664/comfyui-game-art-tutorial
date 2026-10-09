---
type: tool-guide
status: active
---
# ComfyUI server-side Video Layers

Video Layers 是固定 `GameArtVideoLayers` ComfyUI server node + 薄 client 的獨立工具；不是 `generate.py` task 或影片 backend。Server 執行解碼、SAM mask propagation、2D affine、合成、音訊與嚴格輸出驗證，client 做 preflight、queue 和 download。技能入口：[comfyui-video-layers](../../../skills/comfyui-run/references/comfyui-video-layers/README.md)；plan、CLI、部署契約與實測：[local-tool.md](../../../skills/comfyui-run/references/comfyui-video-layers/references/local-tool.md)。

## 契約與安裝界線

Client/package 部署位置、shared helper 與 pinned runtime 見 reference。SAM 使用官方 [Hugging Face SAM 2.1 small](https://huggingface.co/facebook/sam2.1-hiera-small) 與 [Meta SAM 2 repository](https://github.com/facebookresearch/sam2)，固定 revision `ee5bba1d82bb8749febdf90f45e84b687142ba03`；本機只用已快取模型並核對 SHA-256。沒有下載模型或套件。Runtime pins 是本機 preflight gate，沒有宣稱跨平台 verified。生產 ComfyUI 8188 fresh preflight pass；Server node 執行時另核對已載入 package hash。

Plan schema v1 含 `segment`、`compose`。影片最多 5 秒／300 幀，來源 1–60 CFR、最長 60 秒和 1920 px；工作畫面最多 1280 px longest side／150 MP。Segment 支援 1–4 個物件，frame-0 prompt 必須提供，後續影格可加 prompts；遮罩白選黑不選，和 image edit 反向 alpha 不同。Compose 使用靜態 RGB 背景及 ordered 1–8 source/RGBA image layers，能提供白色遮擋 `L` matte。`track` 和 `keyframes` 擇一；LK 追蹤失敗就停止。Image layer 的 `track` 可選 `destination` 作初始 target placement；keyframes 直接用 target-space。Source layer `destination` 仍是固定 target anchors。LK 真實 Kabuto 片段於 frame 1 失敗；尚未證明實片追蹤穩定。

## Current 技術輸出（2026-10-04）

最新 current 輸出全部來自正式 ComfyUI 8188、server PID 14020；舊 `v1` 和 `final` 目錄是歷史結果。以下 technical gate 已完成：fresh `production-current-preflight.json` pass；4 個 current MP4 皆檢查 FPS、逐幀 PTS CFR grid、H.264、AAC 48 kHz stereo 和 full decode pass。

| 候選 | 技術結果 | 肉眼／像素 QA |
|---|---|---|
| `production-segment-current`（本機證據：`output/*-kabuto-upper-body/video-layers/production-segment-current/manifest.json`） | 39 幀、960×540、60 FPS、0.65 秒，H.264/AAC、31,744 samples；2 objects、78 masks、empty=0，10.615 秒，technical pass/content candidate。 | 雙物件 mask 是候選遮罩，仍需人工修邊；不能視為獨立 VFX RGBA matte。 |
| `production-compose-current`（本機證據：`output/*-kabuto-upper-body/video-layers/production-compose-current/manifest.json`） | 39 幀、1024 square、60 FPS，H.264/AAC、31,744 samples，8.389 秒，technical warning/content candidate。 | Armor frame 22/30/38 位置與裁切不符，frame 38 出現小綠三角。PNG QA 的保護 head/collar matte 每幀 666,624 px、改變 0；不代表合成內容正確。 |
| `prop-occlusion-current`（本機證據：`output/*-kabuto-upper-body/video-layers/prop-occlusion-current/manifest.json`） | 39 幀、1024 square、60 FPS，H.264/AAC、31,744 samples，8.338 秒，technical warning/content candidate。 | 手指遮擋 matte 每幀 14,785 px、PNG 改變 0；影片是同一張照片重複 39 幀，拇指離物、指緣不自然。不是動態持物鏡頭。 |
| `belt-occlusion-current`（本機證據：`output/*-kabuto-upper-body/video-layers/belt-occlusion-current/manifest.json`） | 39 幀、1024 square、60 FPS，H.264/AAC、31,744 samples，7.903 秒，technical warning/content candidate。 | 外套遮擋 matte 每幀 958,351 px、PNG 改變 0；仍未解照片透視、3D 繞腰接觸或動態。 |

Independent PNG QA（本機證據：`output/*-kabuto-upper-body/video-layers/independent-png-qa.json`） 是 root 從三份 current zip 中各自讀取 39 張 PNG 後測得；3 個 manifest 的 outside-mask changed pixel max 皆為 0。PNG 數值檢查不等於 MP4 無損，也不代表視覺內容或美術驗收合格。輸入 prop 是既有使用者照片去背／旋轉素材，未生成新道具；prop/belt current 都是靜態照片測試，arm source 音訊僅用來驗證影音輸出契約。

20 個 Video Layers tests 及 17 個 portable tests 通過。最終 `portable-verification-current.txt` 43 passed、0 failed；`video-capability-rescan-current.json` 記錄 H3 default、H3/Wan 可用，這些 backend 不屬 Video Layers。`face-swap-preflight-after.json` 的 ReActor pinned gate 亦通過，仍獨立於此工具。測試 server 8189 已關閉。

## Windows ACL 修正與限制

Python 3.13 Windows `tempfile.mkdtemp()` 建立的 private DACL 會在 rename 後保留，導致不同 desktop/tool identity 無法讀取結果。新 Video Layers client/server 改用 output parent 下隨機 UUID stage path 與一般 `mkdir()` 繼承父目錄 ACL，仍拒絕覆寫並用 atomic rename 發佈。已在一般與核准程序跨身份測試，current results 可由預設 tools 跨呼叫讀取。這次修正只屬 Video Layers，不修改 face-swap media 或既有 generation source。Manifest `output.path` 指向最終 server 檔案，不是暫存目錄。

## Kabuto 變身目標完成度

可用能力包括人工可檢視的短片 SAM 遮罩候選、source RGB layer 搬移、2D affine scale/position、ordered layers 和 explicit front/behind matte。無法證明 baked VFX 可 exact 分離為獨立 RGBA；scene mask 含入背景、材質和光照時無法還原。Armor 遮罩與定位仍錯，人物靜態。手部接觸、自然持物、腰帶繞身與動畫身體接觸尚未解決。完整 Kabuto 變身影片未完成。這台本機技術 gate 通過，不代表跨平台 verified 或美術 accepted。最新使用者需求稽核見completion-audit.md（本機證據：`output/*-kabuto-upper-body/video-layers/completion-audit.md`）。
