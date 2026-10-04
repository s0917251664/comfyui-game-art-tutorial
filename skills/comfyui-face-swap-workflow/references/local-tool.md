# ComfyUI ReActor 換臉 wrapper

狀態（2026-10-04）：ReActor 已安裝至本機 ComfyUI，固定 commit `a12c5b19dcac9ae8b47e592da39c9711c8f8c756`（0.7.1b3）。`tools_src/face_swap.py` 是 `generate` API wrapper；不載入 ONNX、不 import `reactor_core`，所有模型推論只在 ComfyUI。正式 smoke-v2 通過完整解碼契約，但技術狀態為 warning：120 幀、2 秒、1920×1080、60 FPS，含 AAC 音訊；counts 為 `changed=61`、`unchanged=1`、`outside_edit_ranges=58`，有 1 個指定處理影格未變更。9 個 face_swap 測試與 17 個 portable install 測試通過；helper 已部署至 ComfyUI tools，preflight 通過。video capability 重掃列出 H3 與 Wan 可用，`default_backend` 維持 `h3`。全片 `full-v1` 已完成 exit 0：45.2 秒、2712 幀、1920×1080、60 FPS、AAC 1 track、32 個 ComfyUI jobs、完整解碼通過，耗時 260.28 秒。Counts 為 `changed=179`、`unchanged=75`、`outside_edit_ranges=2458`；指定範圍總 254 幀，75 幀只是 pixel-difference 檢查未發現變化，不能推論為偵測失敗。整體 technical status 為 warning，content status 為 candidate，尚未經使用者美術驗收。音訊檢查的同時刻相關係數為 0.990888，數據見 `output/steve-kabuto-face-swap/comfy-full-v1/audio-check.json`。

## 架構與部署

部署 `tools_src/face_swap.py` 至 `<ComfyUI>/tools/face_swap.py`，並沿用已部署的 `<ComfyUI>/tools/generate.py` 及完整 `<ComfyUI>/tools/comfyui_pipeline/` package。這不是可獨立運行的單檔工具；其 PyAV、OpenCV、NumPy、Pillow 與 ComfyUI HTTP/API 操作依賴由既有 ComfyUI Python/runtime 提供。執行路徑與 loopback URL 從 repo `local_config.json` 讀取，不把此台機器絕對路徑寫入通用文件。

ComfyUI-ReActor pinned install 新增 `onnx==1.23.1`、`segment-anything==1.0`、`ultralytics==8.4.172`、`ml_dtypes==0.6.0`；安裝時未替換 PyTorch 或 CUDA。ReActor 使用 ComfyUI 標準模型目錄。所需模型與輔助資源須預先存在；helper 不下載模型。正式部署沿用 ReActor [官方 repository](https://github.com/Gourieff/ComfyUI-ReActor) 與已配置的 ComfyUI Python，不建獨立模型 runtime。

### 可重建的安裝基準

1. 從 `local_config.json` 讀 `comfyui_path` 與 `python_exe`。在 `custom_nodes/ComfyUI-ReActor` 取得[官方 repository](https://github.com/Gourieff/ComfyUI-ReActor)，checkout `a12c5b19dcac9ae8b47e592da39c9711c8f8c756`（0.7.1b3），不要使用浮動的 `main` 作版本依據。此 ComfyUI 環境已使用的新增套件版本為上列四項；重建時用 ComfyUI 的 Python 安裝並核對版本，安裝前後確認 PyTorch/CUDA build 未改變。若 resolver 要替換 Torch/CUDA，先停止並調整依賴安裝方式。
2. 依 [ReActor 官方安裝說明](https://github.com/Gourieff/ComfyUI-ReActor#installation)完成節點安裝；所有重量檔放到 ComfyUI 的標準 models 目錄。swap/detection/recognition 模型來源為 [Gourieff/ReActor Hugging Face dataset](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models)，`inswapper_128.onnx` 與 `buffalo_l.zip` 下載後依本頁 SHA-256 核對；buffalo_l 解壓至 `models/insightface/models/buffalo_l/`。`inswapper_128.onnx` 放在 `models/insightface/`。套用核心三模型 SHA-256 pin；下載來源與 local hash 都要保留在部署紀錄。
3. Preflight 還需要 `models/facerestore_models/` 至少一個 `.onnx`（graph 選 `none`，只為防止 ReActor 自動下載），以及 [AdamCodd NSFW detector](https://huggingface.co/AdamCodd/vit-base-nsfw-detector) 的 `config.json`、`model.safetensors`、`preprocessor_config.json` 放在 `models/nsfw_detector/vit-base-nsfw-detector/`。Face-restorer 的官方檔案見 [ReActor dataset](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models/facerestore_models)。安裝後以 `local_config.json` 跑下方 `preflight`，核對 node schema 及所有必要檔案，再跑 smoke。此重建流程不把任何模型下載放進 wrapper 執行路徑。

ReActor README 說明 `inswapper_128.onnx` 與 `buffalo_l` 預訓練權重依 InsightFace 條款僅限非商業研究用途；若要商業用途，需自行確認可用權重及其授權。以上是來源方聲明，操作前應閱讀[官方授權說明](https://github.com/Gourieff/ComfyUI-ReActor#disclaimer)。

## 前置檢查與命令

`preflight` 使用必要的 `--config <local_config.json>`，解析 `comfyui_path`、`comfyui_url`；只接受 loopback HTTP ComfyUI。upload 前檢查：

- `custom_nodes/ComfyUI-ReActor` 的 HEAD 必須等於 pinned commit，工作樹不得有變更；核對三個 core 檔案 SHA-256。
- 核對 `models/insightface/` 下的固定 swap/detection/recognition 模型及需用的額外 buffalo 模型；檢查標準目錄中的 NSFW detector 資源及至少一個 face restoration ONNX，避免 ReActor schema/執行時自動下載。
- 向 live `/object_info` 取得 schema，檢查 `LoadImage`、`ImageBatch`、`ReActorFaceSwap`、`SaveImage`、`CreateVideo`、`SaveVideo`，所需輸入、`inswapper_128.onnx` 與 `none` restorer 選項；回報 node schema fingerprint。任何檢查失敗均在 image upload 和 queue 前停止。

```powershell
$ConfigPath = (Resolve-Path local_config.json).Path
$Config = Get-Content -Raw $ConfigPath | ConvertFrom-Json
$ComfyPython = $Config.python_exe
$ComfyTool = Join-Path $Config.comfyui_path 'tools/face_swap.py'
& $ComfyPython $ComfyTool preflight --config $ConfigPath
& $ComfyPython $ComfyTool swap --config $ConfigPath `
  --video 'D:\input\shot.mkv' --source-image 'D:\input\donor.png' `
  --start 0 --end 2 --edit-range 0:2 --face-index 0 --batch-size 4 `
  --on-unchanged preserve --audio preserve `
  --output-dir 'D:\output\shot-face-swap-v1'
```

`--config` 必須提供。`swap` 另需 `--video`、單張 `--source-image`、新的 `--output-dir` 及至少一個 `--edit-range START:END`。可選 `--start`（預設 0）、`--end`（預設影片尾）、`--face-index`（0–7，預設 0）、`--batch-size`（1–8，預設 4）、`--timeout`（1–3600 秒，預設 600）、`--on-unchanged error|preserve`（預設 error）和 `--audio preserve|drop`（預設 preserve）。輸出目錄已存在會拒絕，不覆寫來源。

輸入影片限制：單一 video、最多一條 audio stream，已知 1–60 CFR、偶數寬高、最長邊不超過 1920、片長最多 60 秒。參考圖長邊不超過 4096。edit ranges 須在 clip bounds 內且不可重疊。face index 是 ReActor **每一幀** 大至小排序索引，沒有 temporal identity tracking；不得描述成鎖定人物。未變更影格依 `on-unchanged` 停止或保留。

## 媒體輸出與追溯

模型運算只在 ComfyUI 執行。wrapper 先解碼指定片段，將需處理影格 lossless PNG 上傳，按固定 graph 分批 queue；每批輸出由 ComfyUI ReActor node 完成。固定 graph 為 `LoadImage`/`ImageBatch` → `ReActorFaceSwap`（`inswapper_128.onnx`、`retinaface_resnet50`、不做 face restorer）→ `SaveImage` 與 `CreateVideo` → `SaveVideo`。client 下載輸出後核對 batch frame count 和 canvas，再組裝整片候選。Video stream 全片 H.264 重新編碼；若 `--audio preserve` 且來源有聲，使用 timestamp placement 建立 48 kHz stereo timeline、空缺補靜音後 AAC 重編碼。保留的是音訊內容時間線，不是 bitstream copy；`drop` 不輸出音軌。

輸出目錄包含 `candidate.mp4`、`candidate.mp4.json`、`frames.json`、`comparison.jpg`，另有每批 API graph/history 與下載影格的技術追溯資料。manifest 記錄 ReActor/core/model hashes、schema fingerprint、ComfyUI jobs、輸入及輸出 hash、實際媒體規格、逐幀像素變更狀態和 warnings。pixel change 只是差異，不等於臉部偵測或美術品質證明；仍須人工逐鏡檢查。

## 固定來源與 hash

ReActor commit：`a12c5b19dcac9ae8b47e592da39c9711c8f8c756`。Preflight pin 以下 ReActor core bytes：

| 路徑 | SHA-256 |
|---|---|
| `reactor_core/inswap.py` | `9f5457b96ce0863b24cdfd818807c7178b9ca2eebc520872d001e2ca105eabe3` |
| `reactor_core/face_objects.py` | `9604bab5ee9bebaab3cb9923a4b3e55a23021181baa798ea44412c2619590b25` |
| `reactor_core/meanshape_68.py` | `ec26c48ab8ecf44d9bca3bf25f2ba0702be7a0209f0cdc687b49d7e40581436a` |

標準 `models/insightface/` 相對路徑及 SHA-256：

| 路徑 | SHA-256 |
|---|---|
| `inswapper_128.onnx` | `e4a3f08c753cb72d04e10aa0f7dbe3deebbf39567d4ead6dce08e98aa49e16af` |
| `models/buffalo_l/det_10g.onnx` | `5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91` |
| `models/buffalo_l/w600k_r50.onnx` | `4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43` |

此外 preflight 要求 buffalo_l 的 `2d106det.onnx`、`1k3d68.onnx`、`genderage.onnx`，NSFW detector 的 `config.json`、`model.safetensors`、`preprocessor_config.json`，以及 `models/facerestore_models/` 至少一個 ONNX。檢查存在性不代表此 graph 啟用 restoration；graph 明確選 `none`。未來升級 ReActor 或 schema 時不得自行改 pin，需先完成相容性檢查與新 smoke。

## 停用 standalone prototype 歷史

早期 prototype 曾直接載入 ReActor Core 和 ONNX models 做 CPU 推論，違反模型推論須在 ComfyUI 完成的架構要求，已停用。其舊 smoke `output/steve-kabuto-face-swap/smoke-v1/` 僅作視覺參考，warning candidate 不算正式驗證。prototype 沒有 temporal tracking、遮擋推理、hair handling 或 restoration；不可把其 CLI 用法或結果當成目前工具契約。

正式 smoke-v2 存於 `output/steve-kabuto-face-swap/comfy-smoke-v2/`；full-v1 的候選、manifest 和人工檢視圖存於 `output/steve-kabuto-face-swap/comfy-full-v1/`。`face-detail.jpg`、`comparison.jpg` 與 `audio-check.json` 可用於人工審查。這些 technical pass/warning 都不等於內容接受。來源 video timeline 是 45.2 秒，容器約 45.241 秒的音訊尾端依影片長度裁齊；音訊是 AAC 重編碼，非原始音訊位元流複製。`integration.md` 僅記錄原始 Wan Animate 工作流的接入缺口，不代表 ReActor wrapper 不可用。
