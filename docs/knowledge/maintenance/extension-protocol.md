---
type: maintenance
status: current
---
# 新增固定 graph 的擴充協議

新的 ComfyUI 固定流程不臨場組 graph，也不再新增 Python graph builder。缺能力時照這份協議做成 `templates/<id>/`，用 `gameart.py run` 執行（[R2](../rules/fixed-graphs.md)）。技術通過不等於美術接受（[R1](../rules/candidate-review.md)）。

## 步驟

1. **提案。** 寫清楚現有 task 或 template 為什麼不夠、輸入、輸出、要守住的像素或時間契約。只整理需求，不送 prompt。
2. **使用者確認**之後才改程式或新增 template。不因「比較快」就換引擎或下載模型。
3. **固定來源。** 模型檔記錄 size 與 sha256。有 Hugging Face 來源時，`source.revision` 用 40 位 commit，`url` 跟它一致。不追浮動 `main`。
4. **優先派生。** 官方 [workflow_templates](https://github.com/Comfy-Org/workflow_templates) 或 ComfyUI core `blueprints/` 已有對應流程時，從那一份派生，把 blob 寫進 `provenance.upstream`。對不上才 `kind: none`，並在 note 寫原因。差異（換了哪顆模型、哪一段改在本機做）寫在 note，不另組一套節點。
5. **做成 template。** `graph.api.json` 加 `template.json` 加 `README.md`。`status` 先是 `draft`，平台先是 `untested`。slot 只放會變的值。結構變化用另一份 template，不在 runner 裡插節點。JSON 用 LF。
6. **測試。** runner 填值後的 graph 與來源逐欄相同；既有 golden 的 hash 不因這次新增而改掉。preflight 在上傳前擋下缺節點、版本太舊、模型 pin 不符。
7. **實機。** queue 為空時跑一次 `gameart.py run <id>`。`run.result.json` 技術檢查通過才算數。`content_review` 維持 `pending`。
8. **狀態變更。** 證據齊了，另一次變更把該平台改成 `technical_pass`，template `status` 一併改。沒跑過的平台維持 `untested`。graph 有改就升 major，只改狀態升 patch。

部署、重啟 ComfyUI、安裝節點或下載模型都不在這份協議的預設步驟裡。要做的時候分開說明影響，並等使用者同意。

## 範例：Wan VACE 局部重繪

第 3 階段就是照這個順序做的。

- 官方範本 `video_wan_vace_inpainting`，blob `4af6c58919482553498d0e9f5bc7b5985030b914`。另有 core blueprint「Video Inpainting (Wan2.1 VACE)」，blob `3eb700cb9478e00a3b8d8a7c415a36609193ac5e`，取樣參數相同，沒有從它派生。
- 差異寫在 template 的 note：主模型用本機已有的 1.3B（範本是 14B）、不接 CausVid LoRA、遮罩與工作區在本機先做成無損片段。
- 先以 `draft` 放進 `templates/video/wan-vace/inpaint`。等價測試對上當時的舊實作輸出。
- 2026-10-08 在 windows-cuda 用 2026-10-07 的素材、同一句 prompt、seed 202 跑過：raw 544×560、57 幀、24 FPS、h264、無音軌，遮罩外變動像素 0，crop 140,206,684,766。規格與舊輸出相同，檔案 sha256 不同。之後把 windows-cuda 改成 `technical_pass`（v0.1.1）。macos-mps 仍是 `untested`。
- `generate.py video_inpaint` 的指令與旗標沒變，graph 改由 runner 填這份 template。

比對上游 blob 可用選用腳本 `tools_src/maintenance/diff_upstream_template.py`。它只讀、要連網，不進 runner，也不改檔。

## 不在這份協議裡的事

- 本機像素工具（Pillow）與平台原生圖片工具不組 ComfyUI graph。
- 研究腳本在 `experiences/*/scripts/`，不是產線入口。
- 美術接受仍用 `gameart.py review`，由使用者決定。
