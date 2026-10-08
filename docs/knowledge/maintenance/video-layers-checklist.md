---
type: change-record
status: current
---
# Video Layers 新增能力檢查紀錄（2026-10-04）

本次屬 ComfyUI server-side 影片工具，適用「影片」及「本機工具」檢查；不是 `generate.py` task/backend。逐類記錄完成項目與略過理由。

| 類別 | 結果 |
|---|---|
| 安裝／runtime／模型 | 正式 8188 runtime 與 SAM cache 已存在，沒有下載模型或安裝套件。官方來源及固定 revision/hash 寫入模型來源頁、tool reference。Pins 作本機 preflight gate，不聲稱跨平台通用或 verified。 |
| Preflight／部署 | `production-current-preflight.json` pass。client、package 雙位置、shared media helper、模型 hashes 與 live schema 核對成功；node loaded-hash gate 在執行時核對。正式 server 在 queue 空時重啟並產出 PID 14020 current results。face-swap gate 獨立，`face-swap-preflight-after.json` pass；ReActor source 未修改。 |
| CLI／schema／部署程式 | 固定單 node `GameArtVideoLayers`、schema v1 `segment`／`compose`。client、tools/shared package 和 custom node 部署均進 portable verifier。Image track initial destination mapping 新增 regression test；track/keyframes 互斥。沒修改 `generate.py` facade/package 或 video graph/backend。 |
| Runtime／出片測試 | 20 個 Video Layers tests 和 17 個 portable tests pass；current portable report 43 passed、0 failed。四個 current clip 嚴格驗 FPS、逐影格 PTS grid、H.264、AAC 48 kHz stereo、full decode；production preflight 和 capability rescan 已完成。 |
| 內容／像素 QA | 三個 zip 的實際 39-frame PNG 獨立檢查完成，head/collar、fingers、jacket matte 區域各自 total changed 0，manifest outside-mask max 均 0。肉眼 QA 仍判 arm armor 定位/遮罩不合、手指接觸和腰帶 3D 接觸未解；content 都是 candidate。詳見 completion audit（本機證據：`output/*-kabuto-upper-body/video-layers/completion-audit.md`）。 |
| Windows ACL 隱性問題 | 已修復並驗證：Python 3.13 `mkdtemp()` private DACL 經 rename 保留，令跨 desktop/tool identity 讀取失敗。新 client/server 用繼承 output parent ACL 的 UUID stage dir，仍 atomic rename／拒絕覆寫；一般及核准程序跨身份均可讀 current results。只改 Video Layers，不動 face-swap media 或 generation source。 |
| `generate.py`／image profile／backend | 略過：這是獨立 ComfyUI node/client，無生成 task/backend/profile 修改。Video capability rescan 僅記錄當前 H3 default、H3/Wan available。 |
| ComfyUI UI workflow JSON | N/A：固定 API graph 單節點，已用 production queue 驗證；沒有手工 UI graph/workflow JSON 需交付，workflows 非義務。 |
| 新機器／跨平台 smoke | 未做、並明確不宣稱：只有此 Windows 本機 runtime 證據。 |
| 美術驗收／完整 Kabuto 影片 | 未完成：armor matte 與定位錯、glow 漏選；prop 是靜態照片重複 39 幀；belt 仍有透視／繞身接觸問題。這些不能推為已接受素材或完成作品。 |

本次有界工具的技術安裝、live preflight、current smoke、output codec/CFR 驗證、source sync 與 PNG pixel QA 均已完成。完整作品仍缺動態目標身體替換、形變／接觸處理和可用的精確特效遮罩；工具不承諾能從 baked effects exact 反演。候選畫面美術品質也尚未通過驗收。
