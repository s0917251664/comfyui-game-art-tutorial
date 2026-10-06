---
name: comfyui-wan-animate
description: 使用已安裝的 Wan Animate／Wan2.2 Animate，透過固定 ComfyUI API graph 做 Mix 原影片角色替換或 Move 參考角色動作驅動、查詢本機能力與驗收候選時使用。獨立原生能力，技術 smoke 通過但內容仍 candidate，未接入 generate.py backend/task。
---

# Wan Animate

Wan Animate 是已安裝的獨立 ComfyUI 原生能力：Mix 將參考角色置入來源影片；Move 以來源動作驅動參考角色。本技能直接使用 ComfyUI HTTP API 與固定 graph JSON，不要求瀏覽器或 UI 操作；必要時可用 ComfyUI UI 檢視／除錯 SAM 點位。它沒有 `generate.py` task/backend，也不能由 H3/Wan 5B 的 `video_capabilities.json` 推定可用。

安裝期 Mix／Move smoke 通過但曾出現身份漂移及 Move 幻覺吉他。2026-10-06 已使用可重用 Mix17／Move17 API templates 做新一輪技術通過，畫面仍有肩膀、手臂和手部變形，尚未美術驗收；不可宣稱 prompt 已解決身份漂移，也不可由 17 幀結果推論 33 幀穩定。先讀[安裝紀錄](../../docs/knowledge/video/wan-animate-install.md)與[ComfyUI API 操作契約及實測](references/comfyui-api.md)；SCAIL-2 僅供[評估筆記](../../docs/knowledge/video/animation-evaluation.md)研究，不是可直接選用的已驗證模型。

## 每次工作流程

1. 讀本機 `local_config.json`，使用其中 `comfyui_path`、`python_exe`、`comfyui_url`，不要猜位置或換用其他服務。
2. 完成 brief，確認來源影片、角色 reference、Mix／Move 模式、mask 語義、身份錨點、prompt 及驗收條件。輸入影片須符合契約要求的有界 16 FPS CFR 片段。Mix 使用來源背景，SAM 點位以 384×384 中心裁切後座標表示且至少一個 positive point；Move 不傳 points，背景依 reference／目標 brief 定義。Graph 不輸出音訊，在 brief 記錄 audio drop；若需求要求保留來源音訊，停止此路徑並說明限制。
3. 依 API 操作契約對目前 ComfyUI `GET /object_info`，核對固定 graph 所需 node classes、模型 selectors 與本機 manifest assets，並驗證輸入檔。缺 node／selector／model 或 graph 欄位不匹配時停止；不先上傳、不 queue。不要以舊 preflight 輸出或 video snapshot 代替 live check。
4. 先依契約上傳 reference 和 source video，收到 server path 後才填入[固定 API graph template](references/comfyui-api.md)；設定 prompt、明確 seed、唯一 prefix、幀數及 Mix 點位。queue 前驗證所有占位符已替換且 inputs 符合 schema，再提交 prompt、輪詢該 `prompt_id` 並下載輸出。只以 `/history/{prompt_id}` 顯示 success 且 `completed=true` 判定完成。逾時保存 prompt ID 與狀態，不重送、不全域 interrupt，也不自動 queue retry。
5. 將完整輸入／輸出、manifest 與首／中／末幀抽取至全新輸出目錄。技術檢查通過後仍須逐幀依 brief 人工檢視；依[測試紀錄模板](../../docs/knowledge/video/templates/animation-test-record.md)記錄結果，Steve 未明確驗收前保持 candidate。

不得臨場另組節點圖、增加 Python client／CLI、改模型 profiles 或假裝能力已接入 `generate.py`。不覆寫舊候選、不因瑕疵自動重送。brief 與受控比較方式見[動畫 brief 模板](../../docs/knowledge/video/templates/animation-brief.md)及[評估筆記](../../docs/knowledge/video/animation-evaluation.md)。
