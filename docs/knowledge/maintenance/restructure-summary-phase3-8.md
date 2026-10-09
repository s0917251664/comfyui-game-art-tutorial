---
type: maintenance
status: current
---
# 第 3–8 階段總結（2026-10-09 收尾）

這一頁是第 3–8 階段的結案摘要：每一階段交了什麼、實機驗證到哪裡、留下哪些待開發與待決。分支 SHA 與操作細節以[進度頁](../archive/restructure-progress-2026-10-08.md)為準，交付脈絡見[交付頁](../archive/restructure-delivery-2026-10-08.md)，原始計畫與規則見[交接頁](../archive/restructure-handoff.md)。

第 3–8 階段已合併進 `develop`（merge commit `2a0fd57`）。技術檢查通過不等於美術接受（[R1](../rules/candidate-review.md)）。

## 各階段

| 階段 | 結果 | 實機 |
|---|---|---|
| 3 VACE 模板化 | template 官方欄位（最低 ComfyUI 版本、custom node、模型 url／directory、upstream）；runner 支援 pre 產生的上傳檔與 VACE 前後處理步驟；`video/wan-vace/inpaint` 為 `technical_pass`（windows-cuda）；`generate.py video_inpaint` 由 runner 執行 | 10-07 素材：遮罩外變動 0，工作區與舊路徑一致 |
| 4 圖片 template | SDXL 系列、`image/layer-split`、FLUX.2 抽成 template（方案 A：每種節點組合一份） | preflight 與 dry run |
| 5 圖片 task 切換 | 12 個圖片 task 改由 runner 填 template | image-core smoke 10/10（8.3 之後再跑一次） |
| 6 影片 template 與 recipe | 7 個影片 task 改走 template；recipe 格式與執行器；`object-mark-inpaint` 實機跑完確認點 | H3／Wan 各實跑一次；recipe 完整跑完，使用者確認遮罩後局部重繪 |
| 6′ 工具整併 | 重複實作合併；`vfx_alpha_tools` 拆成 `vfx_alpha` 套件；物件組裝改純 Pillow | `vfx prop-paste` 輸出比對 |
| 7 catalog 與技能 | `templates/catalog.json` 與能力索引頁；偵測器認得 template 能力；18 個技能收成 6 個；擴充協議 | 路由走查 7 個典型需求 |
| 8 退場 | 舊節點名稱移除（8.1／8.2）；影片 builder、5 個轉址檔與 `VideoPlan.finalize` 刪除（8.3／8.3b）；`templates/` 納入部署、第三方節點版本記錄（8.4） | 部署 → Manager 正常重啟 → `verify-install` 305/305；部署端 smoke pass |

## 使用者已做的決定

- 不開 GitHub PR，改由實作者自行 review；合併由使用者做。
- 低記憶體舊架構底模路線與影片人臉替換功能完全移除（前者不做 template，後者效果太差，改由模型直接產影片）；圖片與影片只走 template。
- `object-mark-inpaint` 的一次實跑結果（握柄局部重繪，手部保留原片）：使用者表示「先這樣，可以用」，已用 `gameart.py review accept` 記錄。

## 待開發

| 項目 | 現況 | 下一步 |
|---|---|---|
| 被握住的物件：手部（遮擋物）保護遮罩 | 第一次局部重繪把握柄上的手一起重畫、變形。這次用 SAM3 文字追蹤「glove」得到手的遮罩，從物件遮罩扣掉（手外留 5 像素）、局部重繪改用 grow 0 才保住手。扣遮罩是一次性腳本（本機證據：`output/verify-20261009-6.4/subtract_hands.py`），不是正式工具 | 照[擴充協議](extension-protocol.md)提案：在 `object-mark-inpaint` 加「保護遮罩」步驟（追蹤 → 確認 → 從物件遮罩扣掉），由 runner 的固定步驟實作，不臨場組 graph |
| review 只能選原始輸出 | `run.result.json` 的 `outputs` 只有 VACE 原始輸出；貼回結果在 `derived_outputs`，`gameart.py review` 選不到 | 讓 `asset_review` 也能列出並記錄 `derived_outputs` |
| recipe 的 local 步驟 | 實際執行器只執行 template 步驟；local 步驟（只有 `_drafts` 的 recipe 用到）會停下 | 草稿 recipe 轉正時一起實作 |

## 待使用者決定

- 合併。
- `object-mark-inpaint` 與三條 `_drafts` recipe 是否轉正。
- 其他產出的美術接受與平台驗證升格（`gameart.py review`、`gameart.py validation approve`）。
- 上傳到 ComfyUI `input/<run_id>/` 的檔案是否自動清理（目前手動）。
