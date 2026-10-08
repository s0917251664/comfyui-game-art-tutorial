# ComfyUI server-side face-swap package

狀態（2026-10-04）：完整換臉與媒體管線已在 ComfyUI server custom node package 實作。`tools_src/comfyui_face_swap_video/` 是 server node 與 media processing；`tools_src/face_swap.py` 是薄 client。所有 video decode、分批、ReActor 推論、audio encode、final video assembly、完整解碼驗證與 atomic publish 都在 ComfyUI server。Client 不解碼、不抽影格、不編碼音訊、不組裝影片。

## 架構、部署與輸出

將下列兩份共用 package 部署到指定位置，並保留內容一致：

| 來源 | ComfyUI 目的地 | 用途 |
|---|---|---|
| `tools_src/face_swap.py` | `<ComfyUI>/tools/face_swap.py` | CLI client：preflight、queue、download |
| `tools_src/comfyui_face_swap_video/` | `<ComfyUI>/tools/comfyui_face_swap_video/` | client 只載入 `contracts.py` pins/provenance；同份 package 的媒體模組只供 server 執行 |
| `tools_src/comfyui_face_swap_video/` | `<ComfyUI>/custom_nodes/comfyui-face-swap-video/` | server nodes、media pipeline、contracts |

`face_swap.py` 依賴既有 `<ComfyUI>/tools/generate.py` facade 與整個 `comfyui_pipeline/`，不要把 facade 當單檔部署。由 repo 的 `local_config.json` 讀 `comfyui_path`、`python_exe` 與 `comfyui_url`；不同機器不可複製本機絕對路徑。新 custom node 使用 ComfyUI 已有 Python/Torch/NumPy/Pillow/PyAV 環境；本次 package 接入沒有新增模型或套件。

固定 API graph 只有兩個 server nodes：

`GameArtLoadFaceSwapVideo` → `GameArtReActorVideo`

前者要求影片與 donor 參考圖為 server 可讀的絕對 local path，驗證影片 metadata 和參考圖。後者在 ComfyUI server stream-decode 來源、依 edit ranges 分批（最多 8 幀），直接呼叫官方註冊 `ReActorFaceSwap` node 的 `.execute()`。保留官方 NSFW filter；若 ReActor 回傳 partial batch、黑畫面 fallback 或畫布/幀數不符，拒絕輸出。server 完成 H.264/AAC、comparison、frames/manifest、完整解碼檢查與 atomic publish。UI 對應工作流 `workflow_ui.json` 一併輸出；本機可直接開啟版本已存至 `<ComfyUI>/user/default/workflows/Ch8_影片換臉_Server.json`（改名前存的，仍是舊 class 名稱。agent 不改這份檔。PR 8.2 已從 repo 移除別名，但部署與重啟留到第 8.4，而且 queue 必須為空。重啟之後 schema 只剩新名稱，那時開啟才會顯示缺少節點；請使用者在 UI 換成 `GameArtLoadFaceSwapVideo` 與 `GameArtReActorVideo` 後另存，見[改名紀錄](../../../docs/knowledge/maintenance/custom-node-renames.md)），另存 repo `workflows/`（依專案規則忽略版控）。兩個節點在 `GameArt/Video` 分類；output prefix 指向新目錄，不覆寫舊結果，重跑前換成新的 prefix。原生預覽只把 MP4 列為 animated image；比較圖與 JSON 以 files sidecars 傳回，client 只下載。

server 最終輸出位於 `<ComfyUI>/output/face_swap/<uuid>/`。Client queue 後只下載四個結果：`candidate.mp4`、`candidate.mp4.json`、`frames.json`、`comparison.jpg`；並在 client 新 output directory 保存 API graph、UI graph、Comfy history、receipt。`receipt.json` 記錄 prompt id、preflight provenance、client source hash 及輸出位置。server manifest 追溯 `server_pid`、processing location、ReActor/core/model/package hashes、幀狀態與實際媒體資訊。

## Preflight 與 CLI

`preflight` 必須先於任何 queue。Client 從 `local_config.json` 取得 loopback ComfyUI URL，再檢查 pinned ReActor commit、乾淨 git tree、core/model 檔案 SHA-256、兩份 server package 中 `__init__.py`/`contracts.py`/`media.py`/`nodes.py` 的 bytes 一致，以及 live `/object_info` 內三個必要節點與固定 graph 欄位。Server node 執行時也自行驗 ReActor pins；server 保有完整 gate。任何檢查失敗都在上傳／queue 前停止。

PowerShell 範例會從設定檔解析實際執行檔與 client path：

```powershell
$ConfigPath = (Resolve-Path local_config.json).Path
$Config = Get-Content -Raw $ConfigPath | ConvertFrom-Json
$ComfyPython = $Config.python_exe
$ComfyTool = Join-Path $Config.comfyui_path 'tools/face_swap.py'
& $ComfyPython $ComfyTool preflight --config $ConfigPath
& $ComfyPython $ComfyTool swap --config $ConfigPath `
  --video 'D:\input\shot.mkv' --source-image 'D:\input\donor.png' `
  --start 0 --end 6.5 --edit-range 0:1.017 --edit-range 3.3:6.5 `
  --face-index 0 --batch-size 4 --on-unchanged preserve --audio preserve `
  --output-dir 'D:\output\shot-face-swap-v1'
```

`--config` 必填；swap 另需來源影片、`--source-image`、至少一個 `--edit-range START:END` 和新 `--output-dir`。可選 `--start` 預設 0、`--end` 預設片尾、`--face-index` 0–7 預設 0、`--batch-size` 1–8 預設 4、`--timeout` 1–3600 秒預設 600、`--on-unchanged error|preserve` 預設 error、`--audio preserve|drop` 預設 preserve。輸出目錄必須不存在。

限制為單一 video stream、至多一條 audio stream、已知 1–60 CFR、偶數寬高、長邊不超過 1920、片長不超過 60 秒；donor 圖長邊不超過 4096。Clip bounds 和 edit ranges 必須落在來源時間範圍內，ranges 不可重疊。`face-index` 是 ReActor 每一幀由大到小排序的索引，不維持身份追蹤。`unchanged` 只表示 pixel-difference 檢查沒有發現足夠變化，不能推論為臉部偵測失敗。

## 實測狀態

17 個 face/media/node 測試與 17 個 portable install 測試通過。Preflight 通過，server package 已部署；video capability 重掃有 H3 和 Wan，`default_backend=h3`。此獨立 wrapper 不新增 `generate.py` task 或 video backend。

`server-smoke-v1` 已完成：120 幀、2 秒、1920×1080、60 FPS、AAC 音訊；counts `changed=61`、`unchanged=1`、`outside_edit_ranges=58`。Manifest 標記 `processing_location: ComfyUI server` 並記錄 server PID；技術狀態 warning，因一個指定影格輸出未變更。

`server-full-v2`（原生影片預覽與 sidecar 契約修正版）已完成 exit 0：45.2 秒、2712 幀、1920×1080、60 FPS、AAC；一個 ComfyUI queue job，內含 32 個 ReActor batch（每批最多 8 幀），server PID 37080，耗時 175.58 秒。Counts 為 `changed=179`、`unchanged=75`、`outside_edit_ranges=2458`；75 個 unchanged 表示像素差異檢查沒有發現變化，不代表 ReActor 偵測失敗。完整解碼通過，technical warning，content candidate，尚未由使用者美術驗收。Server 與先前 client-side media wrapper 的 `comfy-full-v1` 候選 MP4 SHA-256 相同（`05c05be2a9e4059065be8141dc0f8be3d9fc183bb0e3ac24715766df54a654a1`），`comparison.jpg` 亦相同，確認搬移處理架構後這次輸出畫面與音訊一致。

Server 影片位於 `C:/Users/XU/ComfyUI/output/face_swap/30624cd513c9471599a31b4c2f8073d5/candidate.mp4`；此次 repo/client 交付目錄為 `output/*-kabuto-face-swap/server-full-v2/`，含 `candidate.mp4`、manifest、frames、comparison、API/UI graphs、history、receipt。Smokes 與 full candidate 都不是內容接受狀態；人工驗收完成前不可標記 accepted。

## 固定來源、pins 與可重建安裝

ReActor 官方 repository：[Gourieff/ComfyUI-ReActor](https://github.com/Gourieff/ComfyUI-ReActor)，此機 pinned commit `a12c5b19dcac9ae8b47e592da39c9711c8f8c756`（0.7.1b3）。安裝依官方 [installation instructions](https://github.com/Gourieff/ComfyUI-ReActor#installation)，再 checkout 固定 commit；不要用浮動 main 取代 pin。這台機器既有 ReActor 依賴含 `onnx==1.23.1`、`segment-anything==1.0`、`ultralytics==8.4.172`、`ml_dtypes==0.6.0`；未替換 PyTorch/CUDA。ReActor 核心來源和主要模型的固定 bytes 由共用 `contracts.py` 定義，client/server 共同引用：

| ReActor core path | SHA-256 |
|---|---|
| `reactor_core/inswap.py` | `9f5457b96ce0863b24cdfd818807c7178b9ca2eebc520872d001e2ca105eabe3` |
| `reactor_core/face_objects.py` | `9604bab5ee9bebaab3cb9923a4b3e55a23021181baa798ea44412c2619590b25` |
| `reactor_core/meanshape_68.py` | `ec26c48ab8ecf44d9bca3bf25f2ba0702be7a0209f0cdc687b49d7e40581436a` |

模型在 ComfyUI 標準 `models/insightface/` 路徑。官方來源為 [Gourieff/ReActor Hugging Face dataset](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models)；下載 `inswapper_128.onnx` 與 `buffalo_l.zip` 後依下表 SHA-256 核對。解壓 buffalo archive 至 `models/insightface/models/buffalo_l/`。主要模型 pin：

| `models/insightface/` 相對路徑 | SHA-256 |
|---|---|
| `inswapper_128.onnx` | `e4a3f08c753cb72d04e10aa0f7dbe3deebbf39567d4ead6dce08e98aa49e16af` |
| `models/buffalo_l/det_10g.onnx` | `5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91` |
| `models/buffalo_l/w600k_r50.onnx` | `4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43` |

此外 preflight 要求 buffalo_l 的 `2d106det.onnx`、`1k3d68.onnx`、`genderage.onnx`，AdamCodd [NSFW detector](https://huggingface.co/AdamCodd/vit-base-nsfw-detector) 的三個標準檔案，以及 [ReActor dataset face restoration model](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models/facerestore_models) 內至少一個 ONNX。這些額外資產在 gate 內做存在檢查；graph 固定關閉 face restoration（`none`），但保留官方 NSFW filter。重建時按固定來源下載、保存實際來源 revision 和檔案 hash，再用 `--config` 執行 preflight；不得讓 runtime 自動下載模型。

ReActor 官方說明 InsightFace 的 `buffalo_l` 和 `inswapper_128.onnx` 預訓練權重限非商業研究用途；使用前閱讀[官方 license notice](https://github.com/Gourieff/ComfyUI-ReActor#disclaimer)並遵守權重來源授權。

## Deprecated standalone prototype

舊 `cf61275` 外層 media wrapper 仍在 ComfyUI 執行模型推論，但把媒體處理和組裝留在 client；它已 deprecated，不符合完整功能在 ComfyUI server 的要求。更早的 standalone Core prototype 曾在 client 直接執行模型推論，亦已停用。兩者都只作歷史參考，不是目前架構或驗證證據。本文 [integration.md](integration.md) 只描述原始 Wan Animate workflow 缺口，不能用它判定目前 ReActor wrapper 不可用。
