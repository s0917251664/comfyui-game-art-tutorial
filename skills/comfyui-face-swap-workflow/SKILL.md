---
name: comfyui-face-swap-workflow
description: 以 ComfyUI server-side ReActor node 處理影片換臉及本機媒體輸出。
---

# 影片換臉

正式能力由 `tools_src/face_swap.py` client 與 `tools_src/comfyui_face_swap_video/` custom node package 組成。影片解碼、批次、模型推論、音訊編碼、候選輸出與完整驗證全在 ComfyUI server；client 只執行 preflight、送 API queue、下載結果檔。這是獨立工具 gate，不新增 `generate.py` task 或 video backend。

先讀 [CLI、部署與狀態](references/local-tool.md)。preflight 會驗 ReActor pins、custom node package 部署 hash 與 live API schema；任一項失敗都在 queue 前停止。Server-smoke-v1 及 server-full-v2 均完整解碼通過，但因指定處理影格有 unchanged pixels，technical status 為 warning，content status 仍是 candidate。17 個 face/media/node 測試及 17 個 portable install 測試通過；輸出位置與完整 stats 見 [local-tool.md](references/local-tool.md)。

輸入包含來源影片、donor 身份參考圖、clip bounds 與至少一個 edit range。`face-index` 依 ReActor 每幀由大到小排序選臉，**不做跨幀身份追蹤**；使用多人物或臉序可能變化的素材時需仔細看每幀結果。即使技術驗證通過，candidate 仍需人工檢查身份、表情、遮擋、髮際線、連續性和音畫同步，並由 Steve 決定是否接受。

年齡調整與重生成頭部表演不屬於此工具。`references/integration.md` 只記錄原始 Wan Animate 工作流的未接入狀態，不代表 ReActor 換臉不可用。舊 `cf61275` standalone prototype 已 deprecated，僅保留歷史，不使用其處理架構或結果作正式驗證。
