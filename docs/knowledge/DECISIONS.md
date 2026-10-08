---
type: decision-index
status: current
---
# 生效中的產線決策

決策細節與證據寫在日期化 ADR。這一頁只列目前採用的方向；歷史實測仍需按適用 task、模型與平台閱讀，不能憑一個結果自動改設定檔。

| 日期 | 決策 | ADR |
|---|---|---|
| 2026-10-08 | 影片 template 一份 graph，凍結成 `video_config=None` 時 builder 寫入的檔名。模型可記 `platforms.windows-cuda`（必須與頂層 pin 相同）。不為每個平台複製一份 graph，也不編造 macos-mps 的另一組檔名。預檢仍檢查頂層 pin。 | [影片模型 pin 不按平台分 graph](decisions/2026-10-08-video-model-pins.md) |
| 2026-10-08 | 圖片 D13 採方案 A：每種會增刪或更換節點的組合各一份固定 template，runner 只填值。`image/sdxl/*` 對應 `sdxl_standard`，`image/sd15/*` 對應 `sd15_light`；tier 只改呼叫端寬高。`filename_prefix` 維持 builder 前綴。checkpoint 是 slot，LoRA 不 pin。圖片 `time_alignment` 允許 null。 | [圖片 template 的結構組合](decisions/2026-10-08-image-template-variants.md) |
| 2026-10-08 | custom node 舊名稱直接移除，不再保留別名，也不採用 Node Replacement。缺少新名稱就是缺少節點。這一階段不部署、不重啟；部署與重啟留到第 8.4，且 queue 必須為空。 | [custom node 舊名稱直接移除](decisions/2026-10-08-node-alias-exit.md) |
| 2026-10-08 | 不採用、不安裝 comfy-cli／comfy-mcp，也不用 Comfy Cloud；只參考官方 workflow_templates 的範本欄位與 ComfyUI core subgraph blueprints。`template.json` 補 `min_comfyui_version`、`requires_custom_nodes`、模型 `url`／`directory`、`provenance.upstream`。第 8 階段已評估 core 的 Node Replacement API，結論見[退場決定](decisions/2026-10-08-node-alias-exit.md)。 | [不採用官方 CLI／MCP，只對齊範本欄位與 blueprints](decisions/2026-10-08-official-comfy-tooling.md) |
| 2026-10-07 | 第二階段：固定 API JSON 改用頂層 `templates/`＋`gameart.py run` 執行（先接 Wan Animate 6 份、SAM3 2 份）；runner 完成後 R2 改成「固定 API JSON 一律透過 template＋runner」；custom node 改用 `GameArt` 名稱，舊名別名已在 PR 8.2 移除（見[退場決定](decisions/2026-10-08-node-alias-exit.md)）；`output/` 證據寫成純文字標註；有 hash 紀錄的檔案設 `-text`。共 14 項（D1–D14）。 | [第二階段 template 與 runner](decisions/2026-10-07-phase2-template-runner.md) |
| 2026-10-06 | 新使用者初始化先選工作路線，可只需求整理／平台圖片而不安裝 ComfyUI/Python；新增能力先判別平台、支援 API、既有 CLI 或必要程式，不預設全進 `generate.py`，也不自動遷移既有實作或更改 runtime／模型／profiles／驗收。 | [初始化與路線選擇](installation/initialization.md)；[技能庫維護說明](maintenance/skill-library.md) |
| 2026-10-01 | 維持固定 task／能力 gate；`--result-json` 是選用技術追溯資料；素材版本與人工驗收以按需 Markdown 素材頁記錄，不自動回寫生成規則。 | [素材 Markdown 紀錄；撤回先前 SQLite 方案](decisions/2026-10-01-asset-result-records.md) |
| 2026-10-01 | SDXL 是既有穩定基線；FLUX.2 保持獨立實驗路徑，不能由單機 PoC 推論可取代主線。 | [FLUX.2 維持獨立 PoC](decisions/2026-10-01-flux2-remains-poc.md) |
| 2026-10-01 | 沿用既有 Markdown 知識庫和檔案讀寫規範；保留固定版本的上游技能與產品 runtime，並明確記錄其原生 Windows 支援範圍。 | [以標準 Markdown 維護專案知識庫](decisions/2026-10-01-obsidian-integration.md) |
