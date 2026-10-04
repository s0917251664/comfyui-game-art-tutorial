# Server-side ReActor graph 與執行契約

正式 graph 僅有兩個 repo-owned node：`SteveLoadFaceSwapVideo` → `SteveReActorVideo`。第一個 node 在 ComfyUI server 驗證影片與 donor 參考圖都是絕對 local paths，並讀取來源 CFR metadata。第二個 node 在 server 端解碼影片、以最多 8 幀為一批處理 edit ranges，直接呼叫已註冊官方 `ReActorFaceSwap` node 的 `.execute()`。所有臉部偵測、swap 與模型執行都留在 ComfyUI server。

Server 節點保留官方 ReActor NSFW filter；不以自製 fallback 代替。若 ReActor 回傳 partial batch、黑畫面 fallback 或驗證失敗，server 拒絕發布結果。成功後 server 負責 H.264/AAC 編碼、comparison/frames/manifest、完整解碼驗證和 atomic publish。預設輸出位於 `<ComfyUI>/output/face_swap/<uuid>/`，使用新目錄、不覆寫。`workflow_ui.json` 是同一固定 graph 的可視化版本，可直接在 ComfyUI 開啟並 queue。

Client `tools_src/face_swap.py` 僅含標準函式庫、既有 `generate` API facade 與共用 `comfyui_face_swap_video.contracts`；只做 preflight、queue、下載四個正式結果檔及保存 graph/history/receipt。Client 不解碼影片、不切影格、不上傳 PNG、不執行模型、不編碼音訊或組裝影片。

`--face-index` 範圍 0–7，代表 ReActor 每幀大至小排序的人臉索引；不是跨幀 identity tracking。`--batch-size` 範圍 1–8，預設 4。未變更影格依 `--on-unchanged error|preserve` 停止或保留並產生 warning。所有節點、ReActor pins 與 server package 雜湊都由 preflight 檢查。

此路徑是獨立 node/client gate，不是 `generate.py` task，亦不加入 `video_capabilities.json` backend catalog。能力快照重掃即使顯示 H3/Wan 可用，也不能替代 face-swap preflight。舊 `cf61275` client-side standalone prototype 已 deprecated；Wan Animate 原始工作流狀態見 [integration.md](integration.md)。
