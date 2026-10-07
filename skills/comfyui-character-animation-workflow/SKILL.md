---
name: comfyui-character-animation-workflow
description: 在選定 ComfyUI 執行路線時，編排角色動作組的既有圖片／影片 task、技術 gate 與 frames 交付；只有需求與驗收規劃時走 game-art-workflow。
---

# 單角色動畫 workflow

角色母圖、代表動作、動作表、逐支選版與內容驗收的共用方法由[共用製作流程](../game-art-workflow/references/production.md)維護。本技能保留已接入 ComfyUI 圖片／影片的編排、能力 gate、抽幀與交付技術步驟；不代表平台影片已整合。

先查[工具範圍總表](../../docs/knowledge/TOOLS.md)，再按需求讀[單角色動畫製作與交付規範](../../docs/knowledge/animation/workflow.md)。它保存動作表、分階段驗收、既有抽幀 helper、付費界線及交付記錄。

## 何時使用

已選定 ComfyUI 執行同一角色的動作組（如 Idle、Win、Expect、Fail、Attack），或從角色圖做到逐支驗收與交付時使用。只整理動作需求／驗收表時走共用工作流程，不讀本機生成 gate。單支「讓這張靜幀動起來」走 [`comfyui-video-gen`](../comfyui-video-gen/SKILL.md)；有劇情的多鏡過場走 [劇情影片流程](../comfyui-film-workflow/SKILL.md)。當動作來源是既有影片且使用者選擇 Wan Animate 或 SCAIL-2（影片驅動參考角色／影片中人物替換）時，改走獨立的 [`comfyui-wan-animate`](../comfyui-wan-animate/SKILL.md)；其 gate 是該技能的 live preflight，不在 video_capabilities.json；已接受輸出仍經本技能的逐動作驗收與 frames 交付。

## 執行邊界

- 本技能只編排流程與記錄使用者決定，不定義底層參數。角色靜幀、圖片 task 與圖片驗收走 `comfyui-art-gen`；影片 task、backend、sidecar 與影片驗收走 `comfyui-video-gen`。
- 開始排動作前檢查本機 `image_capabilities.json` 與 `video_capabilities.json`。依知識頁處理不可用／`unverified` task；整條路線缺關鍵能力時先停下說明。不要猜 backend、改用不合需求的 task 或臨場組 ComfyUI graph。
- **Idle 錨定**：所有動作第一幀用已驗收 Idle 圖。Idle 循環用 H3 `fx_loop`（首＝尾＝Idle）；要回 Idle 的動作（Attack／Win／Fail 等）用 H3 `transition --start <Idle> --end <Idle>`；只出不回用 H3 `img2video`。`pose_drive`／`character_video` 不鎖首幀，Wan `img2video` 實測身份漂移，都不用於「從 Idle 開始」的動作。Idle 先補邊到生成畫布比例；驗收加跑 `gameart.py vfx loop-metrics`（只是輔助，不自動判定）。細節見 [Idle 規則](../../docs/knowledge/video/vfx-tools.md#3-idle-起始幀與首尾呼應)。
- **換道具**：已驗收的動作片要換道具材質或造型時，先做道具母版（`flux2_edit`＋`gameart.py vfx prop-paste`），再用 H3 `pose_drive --control-type canny` 套原片動作，見 [vfx-tools §4](../../docs/knowledge/video/vfx-tools.md#4-換道具材質造型先定母版再整幀套原片動作)；整幀重新生成，角色要重新驗收。
- 母圖定稿與代表動作的順序依共用製作流程；本機 `pose_drive` 另須準備與動作片首幀姿勢／方向接近且已驗收的目標角色靜幀。
- 保留原始 MP4 和同名 sidecar。`fail` 不交付；`warning` 要人工查明；`pass` 只表示技術契約通過。每支內容仍由使用者決定接受、調整或放棄，不能由指標自動推定。
- 只有內容接受後，已準備的影格才是正式交付或合成來源。尚未抽幀可用知識頁列出的既有 `extract_video_frames(video_path, output_dir)` 從已接受 MP4 抽取，不重新生成，也不新增 CLI task。
- 透明序列、APNG、sprite sheet 由已接受 MP4 經 `gameart.py vfx`（`chroma-alpha --unmix --despill` 或黑底 `luma-alpha`，再 `pack`）後處理產生，不是模型原生 RGBA；`video_composite` 綠幕合成仍不是透明序列。沒有第三方 provider。未來付費 provider 每次需先列明費用與範圍，取得使用者確認後才送出；失敗不自動付費重試。

## 交付

回報已接受動作的 MP4／frames 路徑、sidecar 路徑與 technical status、待確認或放棄動作、已知限制及未執行後製。保留原始來源，不自動開播放器、不自動重送或覆寫。
