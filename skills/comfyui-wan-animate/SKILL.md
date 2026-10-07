---
name: comfyui-wan-animate
description: 使用已安裝的 Wan2.2 Animate 或 SCAIL-2，透過固定 ComfyUI API graph 做 Mix 原影片角色替換、Move 參考角色動作驅動、兩段延伸的較長片段、保留來源音訊、改輸出寬高，或用 SCAIL-2 做角色替換／動畫時使用；也用於查詢本機能力與驗收候選。獨立原生能力，技術 smoke 通過但內容仍 candidate，未接入 generate.py backend/task。
---

# Wan Animate

Wan Animate 是已安裝的獨立 ComfyUI 原生能力：Mix 將參考角色置入來源影片；Move 以來源動作驅動參考角色。固定 templates 涵蓋單段 17／33 幀、兩段延伸 61 幀、選用的來源音訊保留與可調寬高。SCAIL-2 是同一路線下的另一個模型（以 SAM3 彩色遮罩綁定角色），有自己的 templates 與[操作契約](references/scail2.md)。本技能直接使用 ComfyUI HTTP API 與固定 graph JSON，不要求瀏覽器或 UI 操作；必要時可用 ComfyUI UI 檢視／除錯 SAM 點位。它沒有 `generate.py` task/backend，也不能由 H3/Wan 5B 的 `video_capabilities.json` 推定可用。

安裝期 Mix／Move smoke 通過但曾出現身份漂移及 Move 幻覺吉他。2026-10-06 的 Mix17／Move17、Mix61（含音訊）、Move61 與直式 384×640 Move17 都已技術通過，畫面仍有肩膀、手臂和手部變形，尚未美術驗收；不可宣稱 prompt 已解決身份漂移，也不可由已測尺寸推論其他尺寸穩定。先讀[安裝紀錄](../../docs/knowledge/video/wan-animate-install.md)與[ComfyUI API 操作契約及實測](references/comfyui-api.md)。

## 選 template

- 一般角色替換／動作驅動，片長 ≤ 33 幀：`mix-api.json`／`move-api.json`。
- 需要 61 幀（約 3.8 秒）：`mix-extend-api.json`／`move-extend-api.json`。更長的片段沒有固定 template，停止並告知，不要臨場複製延伸節點。
- 要保留來源音訊、改寬高：仍用上面的 template，依 API reference 的「音訊保留」「解析度」只改允許的欄位。
- 使用者指定 SCAIL-2，或需要多角色／依顏色綁定身份的替換：讀 [scail2.md](references/scail2.md)，用 `scail2-api.json`／`scail2-extend-api.json`。不要因 Wan Animate 結果不佳就自動改跑 SCAIL-2，反之亦然。

## 每次工作流程

1. 讀本機 `local_config.json`，使用其中 `comfyui_path`、`python_exe`、`comfyui_url`，不要猜位置或換用其他服務。
2. 完成 brief，確認來源影片、角色 reference、Mix／Move 模式、mask 語義、身份錨點、prompt 及驗收條件。輸入影片須符合契約要求的有界 16 FPS CFR 片段（單段 17／33 幀、延伸 61 幀）。Mix 使用來源背景，SAM 點位以輸出寬高（預設 384×384）中心裁切後座標表示且至少一個 positive point；Move 不傳 points，背景依 reference／目標 brief 定義。預設不輸出音訊，在 brief 記錄 audio drop；brief 要求保留來源音訊時，只依 API reference 接上唯一的選用音訊連線。
3. 依 API 操作契約對目前 ComfyUI `GET /object_info`，核對固定 graph 所需 node classes、模型 selectors 與本機 manifest assets，並驗證輸入檔。缺 node／selector／model 或 graph 欄位不匹配時停止；不先上傳、不 queue。不要以舊 preflight 輸出或 video snapshot 代替 live check。
4. 先依契約上傳 reference 和 source video，收到 server path 後才填入[固定 API graph template](references/comfyui-api.md)；設定 prompt、所有 seed 欄位、唯一 prefix、幀數、需要時的寬高與音訊連線，及 Mix 點位（SCAIL-2 則是 SAM3 物件文字與模式）。queue 前驗證所有占位符已替換且 inputs 符合 schema，再提交 prompt、輪詢該 `prompt_id` 並下載輸出。只以 `/history/{prompt_id}` 顯示 success 且 `completed=true` 判定完成。逾時保存 prompt ID 與狀態，不重送、不全域 interrupt，也不自動 queue retry。
5. 將完整輸入／輸出、manifest 與首／中／末幀抽取至全新輸出目錄。技術檢查通過後仍須逐幀依 brief 人工檢視；依[測試紀錄模板](../../docs/knowledge/video/templates/animation-test-record.md)記錄結果，美術審核者未明確驗收前保持 candidate。

除 API reference 明列的欄位與音訊連線外，不得臨場另組或改接節點圖、增加 Python client／CLI、改模型 profiles 或假裝能力已接入 `generate.py`。不覆寫舊候選、不因瑕疵自動重送。brief 與受控比較方式見[動畫 brief 模板](../../docs/knowledge/video/templates/animation-brief.md)及[評估筆記](../../docs/knowledge/video/animation-evaluation.md)。
