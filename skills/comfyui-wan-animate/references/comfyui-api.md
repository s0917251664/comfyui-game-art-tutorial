# Wan Animate 固定 template 操作契約（gameart.py run）

本文件說明如何用 `gameart.py run` 執行 Wan Animate 的固定 templates。graph 本身、可填的 slot 與模型 pin 都在 `templates/video/wan-animate/<名稱>/template.json`，runner 負責核對與送出；agent 只準備輸入與 slot 值，不自己改 graph、不自己呼叫 ComfyUI HTTP 送出（[R2](../../../docs/knowledge/rules/fixed-graphs.md)）。這條路線沒有 `generate.py` backend。runner 的完整行為見 [templates/README](../../../templates/README.md)。

## 固定 templates

| Template id | 用途 | 輸出幀數 |
|---|---|---|
| [video/wan-animate/mix](../../../templates/video/wan-animate/mix/template.json)／[move](../../../templates/video/wan-animate/move/template.json) | 單段 Mix／Move | 17 或 33（`frames` slot） |
| [video/wan-animate/mix-extend](../../../templates/video/wan-animate/mix-extend/template.json)／[move-extend](../../../templates/video/wan-animate/move-extend/template.json) | 兩段串接的較長 Mix／Move（見下方「延伸段」） | 固定 61 |
| [video/wan-animate/scail2](../../../templates/video/wan-animate/scail2/template.json)／[scail2-extend](../../../templates/video/wan-animate/scail2-extend/template.json) | SCAIL-2，契約另見 [scail2.md](scail2.md) | 33／61 |

固定參數為 16 FPS、6 steps、CFG 1、Euler/simple、CPU text encoder，預設 384×384。`run show <id>` 會列出全部 slot（型別、預設值、規則、實測過的值）、option、模型 pin 與平台狀態；以它和 `template.json` 為準，本文不重複列 node 編號。

## 執行步驟

以下 `<py>` 是 `local_config.json` 的 `python_exe`，在 repo 根目錄執行；沒給 `--config` 時 runner 會用 `<repo>/local_config.json` 並印出路徑。

1. 查 template：`<py> tools_src/gameart.py run show video/wan-animate/mix`。
2. 準備輸入（見下方「輸入準備」），把 slot 值寫成 UTF-8 的 `values.json`。路徑建議用絕對路徑；相對路徑以執行時的目前資料夾解析。Mix 例子：

   ```json
   {
     "reference_image": "D:/work/wan/reference.png",
     "source_video": "D:/work/wan/source_33f.mp4",
     "prompt": "a pink metallic robot with a camera head, white and blue knit sweater, waves both hands",
     "frames": 17,
     "seed": "auto",
     "positive_points": [{"x": 192, "y": 192}],
     "negative_points": []
   }
   ```

   Move 不給 points；延伸段不給 `frames`，可另給 `seed_segment2`。單一值也可以用 `--set NAME=VALUE`（`--set prompt=@prompt.txt` 從 UTF-8 檔讀），`--set` 優先於 `--values`。
3. 先不連線檢查填值：`<py> tools_src/gameart.py run video/wan-animate/mix --values values.json --dry-run`。會列出改到的欄位，slot 值不合規則（幀數、寬高倍數、點位超出範圍等）在這一步就會擋下。
4. live preflight：同一行改成 `--preflight`。檢查平台狀態、ComfyUI 節點、模型檔大小（加 `--verify-hashes` 完整核對 sha256，有快取）。結束碼 1 就停，照訊息回報；不要自行下載模型、換相似名稱的模型，或加 `--allow-unverified-platform`（要使用者確認，結果只能當技術試驗）。
5. 實際執行：拿掉 `--preflight`，需要時加 `--option keep_audio`。runner 依序：重跑 preflight → 檢查輸入（FPS、CFR、幀數範圍）→ 上傳到 ComfyUI 的 `input/<run_id>/` → 送出 → 只以該 prompt 的 history `success` 且 `completed` 判定完成 → 下載 → 檢查輸出（寬高、幀數、16 FPS、pts 等間隔、音軌是否符合 option）→ 抽 first／middle／last 關鍵幀 → 寫 `run.result.json`。`--timeout` 預設 1800 秒。
6. 看結果：輸出資料夾預設 `output/runs/<日期>-<template id>-<run_id 前 8 碼>/`（template id 的 `/` 換成 `-`，例如 `20261008-video-wan-animate-move-1a2b3c4d/`），影片在 `outputs/video/`，關鍵幀在 `keyframes/`，`run.result.json` 記錄 prompt_id、seed、slot 值、輸入／輸出 sha256、量測值與每一項檢查。
7. 人工檢視與審核：見下方「驗收」。

### 結束碼與失敗

- 0：完成且技術檢查通過（不代表美術接受）。
- 1：preflight 擋下或執行失敗。`run.result.json` 有 `status: failed` 與 `failure`（`step`、`prompt_id`、`error`），已下載的檔案保留。回報 failure 內容，不要自動重跑、不要降尺寸重送。
- 2：參數或設定錯誤（slot 名稱、值格式、設定檔）；修正後重跑。

逾時或 Ctrl+C 時，runner 只刪除確認是自己送出、還在 pending 的 prompt，不呼叫全域 `/interrupt`；已經在跑的 job 會繼續跑完。回報 `prompt_id`，等使用者決定。上傳的輸入不會自動清除，手動清理方式見 [templates/README](../../../templates/README.md#清理上傳到-comfyui-的輸入)。

## 輸入準備

來源影片需為 16 FPS CFR。單段 template 的片段至少要有 `frames` 幀、最多 33 幀；延伸段的片段剛好 61 幀。用 repo 既有媒體工具先切好片段，不要上傳長片期待 graph 只解碼一部分，也不新增媒體處理程式。reference 圖與來源影片先確認用途、版本與 hash。runner 會在上傳前檢查 FPS、CFR 與幀數，不合就停在 pre 步驟。

## Mix 點位與 Move

Mix 點位座標使用輸出寬高（預設 384×384）中心裁切後的座標，不是原圖像素座標；範圍 `0 <= x < width`、`0 <= y < height`，runner 會檢查。`positive_points` 至少一個點，`negative_points` 可以是空陣列。點位要依本次來源的人物確認，不能沿用其他影片的點位；需要時可在 ComfyUI UI 視覺檢查點位，但正式結果仍用 runner 產生。

Move 不給 SAM points，也不接來源角色遮罩或沿用來源背景要求；背景由 reference 與目標 brief 定義。Prompt 描述實際觀察到的動作和身份錨點，不加入來源沒有的動作或道具。

## 延伸段（較長影片）

延伸段 templates 對應官方 UI workflow 的 `Video Extend` subgraph：第二段 `WanAnimateToVideo` 以 `continue_motion` 接第一段輸出，取前段最後 5 幀作動作延續，解碼後去掉重疊幀再接到第一段後面。每段 33 幀，總長固定 33 + 28 = 61 幀（3.8125 秒）。

- seed：`seed_segment2` 預設等於 `seed`；沒有特別理由時不要分開。兩個 seed 都會寫進 manifest。
- Mix 的點位、遮罩、背景對整段 61 幀共用，點位以第一幀判定，仍要抽查後段人物沒有離開遮罩。
- 只有兩段的固定 templates。需要更長的片段時停止並告知，不要臨場複製延伸節點；可以分多次兩段輸出各自驗收，或由維護者照[擴充協議](../../../docs/knowledge/maintenance/extension-protocol.md)另做並實測新的 template。
- 接縫幀（第 32、33 幀前後）是必要的人工檢查點，runner 會寫進 warnings。

## 音訊保留

templates 預設不輸出音訊（brief 記 `drop`）。brief 明確要求保留來源音訊時加 `--option keep_audio`，這是唯一允許的結構性選項。存檔時音訊會截到影片長度；輸出幀與來源第 0 幀起逐幀對齊，所以來源片段的起點就是音訊起點。來源本身沒有音軌時，輸出仍無音軌；runner 的 post 檢查會核對音軌是否符合 option。

## 解析度

`width`／`height` 必須是 16 的倍數（256–1280），runner 會把同一組值填進 graph 裡所有相關節點。輸入以中心裁切縮放，來源長寬比和目標不同時會裁切，要先確認人物仍在裁切範圍內；Mix 點位改用新寬高的座標。

已實測 384×384 與直式 384×640（Move17）。其他尺寸可以用，但視為未實測：先跑 17 幀確認顯存與輸出，再跑較長片段。16 GB 顯卡上較大尺寸可能 OOM，失敗時保留證據並回報，不自動降尺寸重送。

## 驗收

技術檢查通過只代表輸出契約通過。人工逐項檢視 `keyframes/` 與影片：身份錨點、肢體與手部、背景、延伸段接縫、音訊是否符合 brief，依[測試紀錄模板](../../../docs/knowledge/video/templates/animation-test-record.md)記錄。`run.result.json` 的 `content_review` 一律是 `pending`；`gameart.py review list <run 資料夾>` 列出候選，只有使用者明確決定後才用 `review accept|reject <run.result.json 或輸出檔> --by <決定的人> [--note ...]` 記錄。failed 的結果不能 accept。

## 驗證狀態

下表的 2026-10-06 紀錄是 runner 出現前，以同一批固定 graph 直接呼叫 HTTP 完成的；graph 之後搬到 `templates/`，位元組不變。全部完整解碼通過：H.264、16 FPS、PTS 逐幀 1/16 秒。

| 測試 | 輸出 | Prompt ID | Server execution time | 證據 |
|---|---|---|---:|---|
| Move17 | 384×384／17 幀，無音軌 | `56566acd-9d48-41b4-abf1-11bdb1cbc0b1` | 59.946 秒 | validation（本機證據：`output/wan-animate-api-direct/move17-validation.json`） |
| Mix17 | 384×384／17 幀，無音軌 | `78498f85-514d-418f-b512-7e58cc7b6b86` | 25.608 秒 | validation（本機證據：`output/wan-animate-api-direct/mix17-validation.json`） |
| Mix61＋音訊 | 384×384／61 幀，AAC 3.82 秒 | `f15941e6-27a9-4a80-a073-ee2aaaf98c1c` | 95.5 秒 | validation（本機證據：`output/wan-animate-extend/mix61-audio/validation.json`） |
| Move61（無音訊） | 384×384／61 幀，無音軌 | `aa2550ec-1135-4213-8188-8f04d2145ec8` | 42.0 秒 | validation（本機證據：`output/wan-animate-extend/move61/validation.json`） |
| Move17 直式 | 384×640／17 幀 | `db670069-2278-495c-8961-9977a577311b` | 18.0 秒 | validation（本機證據：`output/wan-animate-extend/move17-384x640/validation.json`） |

延伸段與音訊測試用官方來源片段 frames 64..124（61 幀，混入 440 Hz 測試音軌驗證音訊連線），seed 20261006，Mix 點位 positive `[{"x":192,"y":192}]`、negative `[{"x":30,"y":30}]`（依此來源第一幀確認）。模型快取與前處理條件不同，以上時間不作模式間速度比較。

2026-10-08 Windows 驗證時用 `gameart.py run video/wan-animate/move` 跑過一次 Move17（GPU 執行 64.5 秒），runner 的上傳、輪詢、下載、輸出檢查與 `run.result.json` 都正常；證據在該機器的 `output/runs/`。

抽幀觀察（候選，未驗收）：肩膀、手臂與手部仍有變形；61 幀在第 32→33 幀接縫連續，第二段維持相機頭機器人與針織衫；Move61 沒有出現安裝期的幻覺吉他，但手指與手掌仍變形。直式 384×640 輸出變成全身構圖，角色更接近 reference，但來源是頭手近景，動作對應是否合格要人工判斷。音訊輸入是合成測試音，不代表真實對白的嘴型同步。沒有美術審核者的 accepted 決定，不能宣稱 prompt 已解決身份漂移。三段以上、其他解析度與多角色未測。

## 附錄：手動 HTTP（只用於除錯 runner）

正式執行一律用 runner。只有在排查 runner 本身的問題（例如懷疑上傳或輪詢行為）時，才參考下面的 ComfyUI 端點；這樣得到的結果不是產線證據，也不能代替 `run.result.json`。要看 runner 實際送出的內容，先看 run 資料夾的 `workflow_api.json`、`uploads.json`、`queue.json`、`history.json` 與 `run.log`，或用 `--dry-run --output-dir` 產生 `workflow_api.dryrun.json`。

- `GET /object_info`：live node schema 與模型 selector（preflight 用的資料來源）。
- `POST /upload/image`：multipart，欄位 `image`、`type=input`、`overwrite=false`、`subfolder`；回應的 `subfolder/name` 才是 graph 要填的路徑。
- `POST /prompt`：body `{"prompt": <API graph>, "client_id": "<UUID>"}`，回應有 `prompt_id`。
- `GET /history/{prompt_id}`：只有 `status.status_str == "success"` 且 `status.completed == true` 才算完成；空 history 不代表完成，`GET /queue` 只供診斷。
- `GET /view?filename=&subfolder=&type=`：下載輸出（值要 URL-encode）。

除錯時同樣不重送、不呼叫全域 `/interrupt`、不改 graph 結構。
