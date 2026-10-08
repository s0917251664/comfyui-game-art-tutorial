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
- 任何 model 沒有 sha256 pin 時，template 狀態不能是 `technical_pass`。Wan Animate、SAM3 與 `video/wan-vace/inpaint` 的模型都已 pin，狀態都是 `technical_pass`。VACE 的 macos-mps 仍是 `untested`。
- 對齊官方範本的欄位（PR 3.2，見 [ADR 2026-10-08](../docs/knowledge/decisions/2026-10-08-official-comfy-tooling.md)）：
  - `min_comfyui_version`（對應 `minComfyUIVersion`）：目前寫實測通過的版本 0.34.0。要放寬，必須先在較舊的版本實測。
  - `requires_custom_nodes`（對應 `requiresCustomNodes`）：`[{id, source}]`，列出 graph 用到的非 core 節點所屬套件。`source` 是 `registry`（id 用 Comfy registry id，也就是套件 `pyproject.toml` 的 `project.name`）或 `repo`（這個 repo 自己的 custom node）。只用 core 節點時寫 `[]`。
  - `models[].directory`（對應官方的 `directory`）：`path` 在 `models/` 底下時，必須剛好是 `models/<directory>/<filename>`；不在 `models/` 底下（例如 DWPose 放在 custom node 自己的 `ckpts/`）時寫 `null`。
  - `models[].url`（對應官方的 `url`）：必須等於 `https://huggingface.co/<source.repo>/resolve/<source.revision>/<source.file>`。`source.revision` 一定要是 40 位 commit sha，不能用 `main`；沒有 `source` 時寫 `null`。
  - `provenance.upstream`：`{kind, name, blob, comfyui_version, note}`。`kind` 是 `workflow_templates`（`name` 寫範本名稱，不含 `.json`）、`core_blueprint`（`name` 寫 ComfyUI `blueprints/` 裡的檔名，含 `.json`）或 `none`。`blob` 是派生時那份官方檔案的 `git hash-object --no-filters` 結果；`comfyui_version` 是派生或比對時的 ComfyUI 版本。找不到對應的官方來源時寫 `kind: none`，`name`、`blob`、`comfyui_version` 都是 `null`，並在 `note` 說明原因。

## 使用

```text
python tools_src/gameart.py run list
python tools_src/gameart.py run show video/wan-animate/mix
python tools_src/gameart.py run video/sam3/track-text --dry-run --set track_text=mallet --set source_video=clip.mp4
python tools_src/gameart.py run video/wan-animate/mix --preflight [--verify-hashes] [--allow-unverified-platform]
python tools_src/gameart.py run video/sam3/track-mask --set source_video=clip.mp4 --set seed_mask=mask_editor.png [--timeout 1800] [--output-dir DIR]
```

`--dry-run` 輸出要送出的 graph（上傳欄位顯示為 `<upload:slot>`），不連線、不上傳、不 queue。

`--preflight`（PR 2.2）只讀，不上傳、不 queue，結束碼 0＝通過、1＝擋下、2＝參數或設定錯誤：

- 設定：`--config` 相對路徑以 repo 根目錄解析，從 repo 執行時預設用 `<repo>/local_config.json`；URL 優先順序是 `--comfy-url` > `COMFY_URL`/`COMFYUI_URL` > 設定檔。
- 平台（D6）：讀 `<comfyui_path>/tools/device_config.json` 的 `platform_key`（或 `--platform-key`；和快照不同時會提醒，preflight.json／run.result.json 兩個值都記錄）。template 對這個平台不是 `technical_pass`（含沒列出的平台）就擋下，加 `--allow-unverified-platform` 才放行；`unsupported` 一律擋下。
- graph 寫死 `device: "cuda"` 的節點（Mix 的 node 108）在非 CUDA 平台擋下，`--allow-unverified-platform` 時降為警告；graph 不改。
- ComfyUI `/object_info` 要有 graph 用到的每個 node class，模型 input 的選項清單要有 template 寫的檔名。
- ComfyUI 版本（PR 3.2）：讀 `/system_stats` 的 `system.comfyui_version`，比 template 的 `min_comfyui_version` 低就擋下；讀不到或認不出版本時只提醒，不擋。
- 模型檔 `<comfyui_path>/<path>` 存在且大小相符（D5，摘要分開列「存在」與「大小相符」）；`--verify-hashes` 才完整算 sha256，快取在 `<output-dir>/../.hash-cache.json`（沒給 `--output-dir` 時是 `<repo>/output/runs/.hash-cache.json`）。`auto_download: true` 的模型（SAM2 下載器、DWPose 的兩個 onnx）缺檔時節點會自己下載，runner 不允許，所以缺檔一定擋下。
- slot 沒給齊時只檢查環境；給齊時另外寫出 `workflow_api.dryrun.json`。`--output-dir` 會寫 `preflight.json`。
- 已知限制：不讀 ComfyUI 的 `extra_model_paths.yaml`，模型檔只在 `<comfyui_path>/<path>` 找。模型放在其他資料夾時 preflight 會回報找不到（`/object_info` 的選項檢查仍然有效）。

不加 `--dry-run`／`--preflight` 就是實際執行（PR 2.3），結束碼 0＝完成且技術檢查通過、1＝preflight 擋下或執行失敗、2＝參數或設定錯誤：

1. 先跑同樣的 preflight，擋下就停（不上傳）。
2. pre 步驟讀本機輸入（影片用 PyAV、圖片用 Pillow，所以要用 ComfyUI 的 Python，也就是 `local_config.json` 的 `python_exe`）：FPS、CFR、幀數範圍、遮罩尺寸與是否全黑。
3. 上傳到 ComfyUI 的 `input/<run_id>/`（`overwrite=false`），graph 填上傳回傳的 `subfolder/name`。
4. `POST /prompt`（帶 `client_id`），輪詢 history；只有 `status_str == "success"` 且 `completed` 才算完成。逾時（`--timeout`，預設 1800 秒）不重送、不呼叫全域 `/interrupt`，只刪除確認是自己送出、還在 pending 的 prompt；已經在跑的 job 會繼續跑完。按 Ctrl+C 也一樣。
5. 下載 template `outputs` 宣告的 node，再跑 post 步驟：影片輸出核對寬高、幀數、FPS、pts 是否等間隔、音軌，抽 first／middle／last 關鍵幀；PNG 序列核對張數、尺寸、灰階；SAM3 另外產生遮罩疊圖預覽（選用，失敗只提醒）。

輸出資料夾預設是 `<repo>/output/runs/<日期>-<template id>-<run_id 前 8 碼>/`，template id 裡的 `/` 換成 `-`，例如 `20261008-video-sam3-track-mask-1a2b3c4d/`（`--output-dir` 可改，必須不存在或是空的），內含 `preflight.json`、`uploads.json`、`workflow_api.json`（實際送出的 graph）、`queue.json`、`history.json`、`outputs/<output id>/`、`keyframes/`、`run.log`、`run.result.json`。

`run.result.json` 的 kind 是 `template_run_result`：記錄 template 版本與 hash、prompt_id、client_id、run_id、seed、送出 graph 的 sha256、模型、slot 值、輸入檔與上傳位置、輸出檔 sha256 與量測值、平台、ComfyUI 版本、時間（`timing.execution_seconds` 是 ComfyUI history 記錄的執行時間）、每一項檢查結果。影片的 `fps` 是數字（整數幀率記成 `16`，非整數記成小數），分數形式另外記在 `fps_rational`（例如 `"16/1"`、`"30000/1001"`）。任何一步失敗都會寫 `status: failed` 和 `failure`（步驟、prompt_id、錯誤），已下載的檔案保留。技術檢查通過不等於美術接受：`content_review` 一律是 `pending`，接受與否由使用者決定後用 `gameart.py review list|accept|reject` 記錄（failed 的結果不能 accept）。延伸段 template 會提醒「延伸段接縫（第 32/33 幀前後）需要人工檢查」，也寫進 manifest 的 warnings。

### 本機輸入、pre 產生的上傳檔與 VACE 步驟（PR 3.3）

有些 graph 需要先在本機處理輸入，再把處理結果上傳（例如 VACE 局部重繪要先裁工作區、編成無損片段）。`template.json` 用下面的寫法宣告，runner 依序執行，graph 仍然只在宣告的 slot 目標上改值：

- **本機輸入**：`type: path`（檔案或資料夾，例如遮罩 PNG 資料夾或 `layers.zip`），或沒有 `upload` 的 `image`／`video`／`mask_image`。這類 slot 只給 pre／post 步驟讀，不上傳、不寫進 graph，`targets` 一定是 `[]`。`int`／`float`／`string`／`text`／`bool` 也可以寫 `targets: []`，只當步驟參數用。`targets` 是 `[]` 的 slot，一定要被某個步驟引用。
- **pre 產生的上傳檔**：`upload: true` 加 `generated: true`。使用者不能用 `--set` 指定；值由 pre 步驟產生（例如 `vace_work_area` 的 `control`、`mask` 參數），產生它的步驟要排在 `upload` 步驟之前。
- **pre 量到的值**：`from_pre: "{pre.<步驟>.<欄位>}"`（例如 `{pre.vace_work_area.width}`），使用者也不能指定。graph 目標可以是占位；dry-run／preflight 時 graph 顯示 `<pre:vace_work_area.width>`，實際執行時在 pre 步驟跑完、上傳之前填入並驗證。
- 步驟參數也可以引用 pre 步驟的結果，例如 `"frames": "{pre.vace_work_area.length}"`。

VACE 的三個步驟（實作在 `tools_src/comfyui_pipeline/runner/vace_media.py`，和 `generate.py video_inpaint` 共用同一份程式）：

| 步驟 | 階段 | 參數 | 做什麼 |
|---|---|---|---|
| `vace_work_area` | pre | `video`、`masks`、`mask_object`、`grow`、`pad`、`crop`、`mode`、`control`、`mask` | 讀來源與遮罩（白色＝重畫）、擴張遮罩、算工作區、縮到 VACE 像素上限，寫出兩支 FFV1 無損片段到 run 資料夾的 `work/`，並交給 `control`／`mask` 指定的 generated slot 上傳。結果欄位：`frames`、`width`、`height`、`length` |
| `paste_back` | post | `output`、`feather` | 把 VACE 輸出縮回原尺寸，只在擴張＋羽化遮罩內貼回來源，寫 `composited/frames/*.png`（無損母帶）與 `composited/composited.mp4`（H.264，不是無損），記在 `run.result.json` 的 `derived_outputs` |
| `qa_outside_mask_unchanged` | post | （無） | 重新讀貼回的 PNG，逐幀數遮罩外和來源不同的像素，不是 0 就判定失敗 |

清單外的步驟一律拒絕；`paste_back` 需要 pre 有 `vace_work_area`，`qa_outside_mask_unchanged` 需要排在 `paste_back` 之後。

### 清理上傳到 ComfyUI 的輸入

runner 不會刪除上傳的檔案：每次執行的輸入留在 `<comfyui_path>/input/<run_id>/`（`run_id` 記在 `run.result.json` 與 `uploads.json`）。這是目前的預設，是否改成自動清理還沒決定。要手動清理時：

1. 確認這個 run 已經結束：`run.result.json` 存在，而且 ComfyUI 的 `/queue` 裡沒有這個 `prompt_id`（逾時或 Ctrl+C 的 run，job 可能還在跑，要等它結束）。
2. 只刪那個 run 的子資料夾，例如 PowerShell：`Remove-Item -LiteralPath "<comfyui_path>\input\<run_id>" -Recurse`；macOS：`rm -r "<comfyui_path>/input/<run_id>"`。不要清空整個 `input/`，裡面可能有其他工作的檔案。
3. 刪掉之後就不能用同一份 `workflow_api.json` 在 ComfyUI 重跑；要重跑請重新 `gameart.py run`。repo 裡的 run 資料夾（輸出與 manifest）不受影響。

`--set NAME=@檔案` 從 UTF-8 檔讀值（可帶 BOM，結尾換行會去掉）；`--values FILE.json` 一次給多個值；dry-run 的 `--output-dir` 寫出 `workflow_api.dryrun.json` 與 `dryrun.json`。`run` 只能從 repo 執行，`templates/` 不部署。

## 修改

改 graph 或 template.json 都要升版本（graph 改動升 major），更新兩個 sha256，並重跑 `python tests/golden_template_graphs.py --write` 後檢查 golden diff。`template.json` 是這些 graph 唯一的權威來源；舊的 `skills/comfyui-wan-animate/assets/template-manifest.json` 已在 PR 2.4 刪除（見[轉址檔索引](../docs/knowledge/archive/redirect-stubs.md)）。
