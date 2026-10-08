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
- 任何 model 沒有 sha256 pin 時，template 狀態不能是 `technical_pass`。目前 8 份的模型都已 pin（`dw-ll_ucoco_384.onnx` 在 PR 2.2 補上），都是 `technical_pass`。

## 使用

```text
python tools_src/gameart.py run list
python tools_src/gameart.py run show video/wan-animate/mix
python tools_src/gameart.py run video/sam3/track-text --dry-run --set track_text=mallet --set source_video=clip.mp4
python tools_src/gameart.py run video/wan-animate/mix --preflight [--verify-hashes] [--allow-unverified-platform]
```

`--dry-run` 輸出要送出的 graph（上傳欄位顯示為 `<upload:slot>`），不連線、不上傳、不 queue。

`--preflight`（PR 2.2）只讀，不上傳、不 queue，結束碼 0＝通過、1＝擋下、2＝參數或設定錯誤：

- 設定：`--config` 相對路徑以 repo 根目錄解析，從 repo 執行時預設用 `<repo>/local_config.json`；URL 優先順序是 `--comfy-url` > `COMFY_URL`/`COMFYUI_URL` > 設定檔。
- 平台（D6）：讀 `<comfyui_path>/tools/device_config.json` 的 `platform_key`（或 `--platform-key`）。template 對這個平台不是 `technical_pass`（含沒列出的平台）就擋下，加 `--allow-unverified-platform` 才放行；`unsupported` 一律擋下。
- graph 寫死 `device: "cuda"` 的節點（Mix 的 node 108）在非 CUDA 平台擋下，`--allow-unverified-platform` 時降為警告；graph 不改。
- ComfyUI `/object_info` 要有 graph 用到的每個 node class，模型 input 的選項清單要有 template 寫的檔名。
- 模型檔 `<comfyui_path>/<path>` 存在且大小相符（D5）；`--verify-hashes` 才完整算 sha256，快取在 `<output-dir>/../.hash-cache.json`（沒給 `--output-dir` 時是 `<repo>/output/runs/.hash-cache.json`）。`auto_download: true` 的模型（SAM2 下載器、DWPose 的兩個 onnx）缺檔時節點會自己下載，runner 不允許，所以缺檔一定擋下。
- slot 沒給齊時只檢查環境；給齊時另外寫出 `workflow_api.dryrun.json`。`--output-dir` 會寫 `preflight.json`。

不加 `--dry-run`／`--preflight`（實際執行）時會先跑同樣的 preflight；上傳與 queue 在 PR 2.3 加入，目前 preflight 通過後以結束碼 2 停止。`--set NAME=@檔案` 從 UTF-8 檔讀值（可帶 BOM，結尾換行會去掉）；`--values FILE.json` 一次給多個值；`--output-dir` 寫出 `workflow_api.dryrun.json` 與 `dryrun.json`。`run` 只能從 repo 執行，`templates/` 不部署。

## 修改

改 graph 或 template.json 都要升版本（graph 改動升 major），更新兩個 sha256，並重跑 `python tests/golden_template_graphs.py --write` 後檢查 golden diff。舊的 `skills/comfyui-wan-animate/assets/template-manifest.json` 在 PR 2.4 刪除前保留，不再是這些 graph 的權威來源。
