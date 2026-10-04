---
name: comfyui-face-swap-workflow
description: 使用 ComfyUI ReActor 節點換臉並由本機 wrapper 整理影片與音訊。
---

# 影片換臉

正式路線是 `tools_src/face_swap.py` ComfyUI API wrapper。所有模型推論都在 ComfyUI ReActor 節點；wrapper 只檢查安裝與 live schema、準備無損 PNG 影格、送固定 graph queue、取回結果並處理媒體。它是獨立工具 gate，不是 `generate.py` task，也不登記成既有影片 backend。

先讀 [CLI、部署與狀態](references/local-tool.md)。執行前從 `local_config.json` 取得 ComfyUI 路徑、Python 與 URL；執行 `preflight`，確認 ReActor pinned commit、core/model files 與即時 `/object_info` graph schema 都符合。gate 失敗時不可上傳或 queue。正式 smoke-v2 與 full-v1 技術流程已完成並通過完整解碼，但皆有 unchanged frame 的 warning；結果仍是 candidate，尚未經使用者美術驗收。

處理前確認來源影片、donor 身份圖、edit range、每幀 face index、missing/unchanged 策略、音訊政策與新的 output directory。`face-index` 是 ReActor 每一幀依大至小排列的臉部索引，**不是身份追蹤**；多人物或臉部排序變化須特別檢查。換臉候選及 manifest 仍需人工逐鏡驗收身份、表情、遮擋、髮際線、連續性與音畫同步。

年齡調整、重新生成頭部表演或多鏡故事仍須分別規劃。Wan Animate 路線不由本 helper 執行，狀態見 [integration.md](references/integration.md)。停用的 standalone Core prototype 歷史見 [local-tool.md](references/local-tool.md)。
