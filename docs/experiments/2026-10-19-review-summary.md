# 2026-10-19 簡報與實驗成果：review 摘要

給 reviewer 的入口。分支 `claude/project-thread-s1ejng`（PR #12），已合併最新 main（bb28d9a）。

## 做了什麼
1. 平台 agent 對照實驗（Grok、Codex）與我方流程，共 8 項：E1 可重現、E2/E6 改圖與選區、E3 角色一致、E3b 其他保一致流程、E4 透明、E5 圖上文字、E7 影片與 3D、E8 時間。
2. 推廣簡報（Slides 類型 Artifact，只讀連結見下），32 頁：主線 18 頁，附錄 14 頁。
3. 平台側由 Gemini 改為 Grok 與 Codex，已全面移除 Gemini。

## 結論（單一素材、目視自評、非盲評）
- 固定流程贏在：可重現（同 seed 重跑 0% 差異）、可驗證（局部改圖貼回後範圍外 0 像素）、速度（約 7 秒／張）、本機免費、影片與 3D 一條指令。
- 平台贏在：圖上文字（Grok 24/25、Codex 15/15、我方 0/25）、換武器等大幅改圖品質、Codex 原生透明。
- 角色一致：舊 `character_action` 最弱；Qwen 三參考（約 7 分鐘／張，技術試驗）特徵保住最多；FLUX.2 編修（約 30 秒）快但會換武器；外觀鎖定姿勢跟不上。此騎士沒有 LoRA，LoRA 路線沒測。
- 建議用法：要穩定交付走固定流程；要文字或快速好看走平台；可搭配（平台出圖、固定流程局部修改再貼回）。

## 請 review 的檔案
- `docs/experiments/2026-10-19-windows-results.md`：全部實測數據與表格（含 E3b）。
- `docs/experiments/2026-10-19-evidence/`：證據圖（含 `E3b_all_flows.jpg`）。
- `docs/experiments/2026-10-18-platform-agent-vs-pipeline.md`：實驗設計。
- `docs/experiments/scripts/`：實驗腳本。

## 簡報
- 連結：https://claude.ai/artifact/YBp2gG8WM9EGZ8MXfXZxwG（私人，需 Steve 的帳號；分享要在頁面 Share 選單設定）。
- 目前第 22 版。

## 已知限制與待辦
- 樣本少、無盲評；結果只代表 2026-10-19 當日與當時版本。
- Qwen、FLUX.2 流程在 windows-cuda 為 untested，結果只算技術試驗。
- 待確認：repo 是否公開（影響簡報「怎麼拉專案」頁的私有 repo 提示）。
- 本機主資料夾另有未提交舊工作（FLUX.2 三個模板、局部物件修補指南等），未納入本次成果；FLUX.2 三參考模板未測。
- Skye 遊戲素材只留本機，未進 repo。
