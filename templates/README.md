# templates/：固定 ComfyUI API graph

每個 template 是一個資料夾 `templates/<id>/`，`<id>` 就是 template id（例如 `video/wan-animate/mix`）：

| 檔案 | 內容 |
|---|---|
| `graph.api.json` | 實測過的 ComfyUI API graph，**位元組不改**（`.gitattributes` 設 `-text`，避免換行被轉換） |
| `template.json` | 可替換的 slot、選用的 option、模型 pin、平台狀態、送出前後的檢查步驟、首尾幀語意、證據文件 |
| `README.md` | 給人看的簡短說明 |

`_schema/template.schema.json` 是 `template.json` 的結構說明（文件用途）；實際驗證在 `tools_src/comfyui_pipeline/runner/template.py`，只用標準庫。以 `_` 開頭的資料夾不是 template。

## 規則（載入時強制）

- `graph.api.json` 的位元組 sha256 與 canonical sha256 都要和 `template.json` 一致。位元組不符但 canonical 相符時，通常是 git 把換行轉換了。
- 每個 slot／option／model 指到的節點與 input 都必須存在；graph 裡每個 `__XXX__` 占位與每個 `seed`／`noise_seed = -1` 都要有 slot 認領；兩個 slot 不能寫同一個目標（`default_from` 例外）。
- patch 後的 graph 和原 graph 只能在「slot 目標＋已啟用 option 的目標」不同，不能新增或刪除節點，也不能改 class_type。
- 任何 model 沒有 sha256 pin 時，template 狀態不能是 `technical_pass`（Wan Animate 的四份因 `dw-ll_ucoco_384.onnx` 尚未 pin 而是 `draft`，TODO 2.2 在 Windows 補上）。

## 使用

```text
python tools_src/gameart.py run list
python tools_src/gameart.py run show video/wan-animate/mix
python tools_src/gameart.py run video/sam3/track-text --dry-run --set track_text=mallet --set source_video=clip.mp4
```

目前（PR 2.1）只有 `--dry-run`：輸出要送出的 graph（上傳欄位顯示為 `<upload:slot>`），不連線、不上傳、不 queue。`--set NAME=@檔案` 從 UTF-8 檔讀值（可帶 BOM，結尾換行會去掉）；`--values FILE.json` 一次給多個值；`--output-dir` 寫出 `workflow_api.dryrun.json` 與 `dryrun.json`。實際送出在 PR 2.3。`run` 只能從 repo 執行，`templates/` 不部署。

## 修改

改 graph 或 template.json 都要升版本（graph 改動升 major），更新兩個 sha256，並重跑 `python tests/golden_template_graphs.py --write` 後檢查 golden diff。舊的 `skills/comfyui-wan-animate/assets/template-manifest.json` 在 PR 2.4 刪除前保留，不再是這些 graph 的權威來源。
