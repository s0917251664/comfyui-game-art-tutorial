# Wan Animate 固定 ComfyUI API 操作契約

本文件說明如何由 agent 直接呼叫本機 ComfyUI API，使用版控中的固定 graph JSON。它不是 Python client、CLI 或 `generate.py` backend。每次執行前讀取 `local_config.json`，使用其中 `comfyui_url` 做 live preflight。

## 固定 templates 與 preflight

使用技能目錄中的固定 templates 及[template manifest](../assets/template-manifest.json)：

| Template | 用途 | 輸出幀數 |
|---|---|---|
| [mix-api.json](../assets/mix-api.json)／[move-api.json](../assets/move-api.json) | 單段 Mix／Move | 17 或 33 |
| [mix-extend-api.json](../assets/mix-extend-api.json)／[move-extend-api.json](../assets/move-extend-api.json) | 兩段串接的較長 Mix／Move（見下方「延伸段」） | 固定 61 |
| [scail2-api.json](../assets/scail2-api.json)／[scail2-extend-api.json](../assets/scail2-extend-api.json) | SCAIL-2，契約另見 [scail2.md](scail2.md) | 33／61 |

以 `GET {comfyui_url}/object_info` 取得 live schema，核對兩份 graph 的 node class 存在，並確認 loader 對應的 live model selectors 可選到 graph 固定使用的模型。再比對 manifest 中模型路徑與檔案大小。Preflight 必須在任何上傳前完成；node、model selector、資產或 graph input 不匹配就停止，不要用相似名稱推定相容。

可用目前會話的 HTTP 工具直接呼叫 API。若需本機 shell，可在互動式 PowerShell 7 使用系統既有 `Invoke-RestMethod`、`.NET HttpClient` 或 `curl.exe`；不要建立 `.ps1`、Python client 或其他包裝程式。以下是可直接改值使用的 PowerShell 7 範例：

```powershell
$base = 'http://127.0.0.1:8188'
$schema = Invoke-RestMethod -Uri "$base/object_info" -Method Get
```

固定參數為 16 FPS、6 steps、CFG 1、Euler/simple、CPU text encoder，預設 384×384。動態替換欄位只限 prompt、reference、source video、明確 seed、唯一 output prefix、單段 template 的輸出 17／33 幀、下方「解析度」列出的寬高欄位，以及下方「音訊保留」的唯一一條選用連線；Mix 另有 SAM 點位。依模板 node input key 填值：node 21 `text`、node 10 `image`、node 145 `file`、node 300（ImageFromBatch）`length`、node 62 `length`、node 63 `seed`、node 19 `filename_prefix`、node 107 `coordinates_positive`／`coordinates_negative`。以實際模板與 live schema 核對，不可只憑 node ID 虛構 input。

模板占位符包括 `__REFERENCE_IMAGE__`、`__SOURCE_VIDEO__`、`__POSITIVE_PROMPT__`、seed `-1`、`__OUTPUT_PREFIX__`；Mix 另含 `__POSITIVE_POINTS__`、`__NEGATIVE_POINTS__`。seed 必須換為明確整數，prefix 必須唯一。圖片及影片需先 upload 才有 server path；收到兩次 upload response 後，才替換各自 path。queue 前掃描完整 graph，所有占位符都必須已替換，seed 不可是 `-1`。任何 input 不確定就先停止。

## 輸入準備與上傳

來源影片需為 16 FPS CFR。單段 template 的片段長度 17 或 33 幀，所選片段須至少包含本次要求的幀數，最長 33 幀；延伸段 template 的片段須剛好 61 幀。33 幀 source 可用 node 300 `ImageFromBatch.length` 選取 17 幀，node 62 `length` 設定輸出 17 或 33 幀。不要把長片直接上傳再期待 graph 只解碼所需片段。用 repo 既有媒體工具準備片段，不新增媒體處理程式。reference 圖及來源影片先檢查可解碼、用途、版本及 hash。

用 multipart `POST /upload/image` 上傳 image/video 檔案，form 欄位包含 `image`、`type=input`、`overwrite=false`；可用唯一 UUID subfolder 與唯一 UUID basename 避免檔案衝突。回應 `{name, subfolder, type}` 中的 `subfolder/name` 用於替換正確 LoadImage／LoadVideo input path；不得假設 subfolder 必為空。PS7 範例：

```powershell
$uploadFolder = [guid]::NewGuid().ToString()
$referenceUpload = Invoke-RestMethod -Uri "$base/upload/image" -Method Post -Form @{
    image = Get-Item -LiteralPath $referencePath
    type = 'input'
    overwrite = 'false'
    subfolder = $uploadFolder
}
```

source video 使用同一路徑再上傳，並各自保存完整 JSON 回應。上傳失敗時記錄錯誤及已成功的 upload path，不重複 queue。Templates 預設不輸出音訊（brief 記 `drop`）；brief 要求保留來源音訊時，依下方「音訊保留」接上唯一一條選用連線。

## Mix 點位與 Move

Mix 點位座標使用 graph 輸出寬高（預設 384×384）的中心裁切座標，不是原圖像素座標；預設範圍為 `0 <= x,y < 384`。node 107 的值是 JSON 字串，例如 positive `'[{"x":192,"y":192}]'`、negative `'[]'`。Mix 至少要一個 positive point，negative 可以空陣列；點位須根據本次 source／人物確認，不能沿用其他影片的點位。ComfyUI UI 可選用於視覺檢查點位，平常仍由 API 執行。

Move 不傳 SAM points，也不接來源角色遮罩或沿用來源背景要求；背景由 reference 與目標 brief 定義。Prompt 描述實際觀察到的動作和身份錨點，不加入來源沒有的動作或道具。

## 延伸段（較長影片）

延伸段 templates 對應官方 UI workflow 的 `Video Extend` subgraph：第二段 `WanAnimateToVideo`（node 400）以 `continue_motion` 接第一段輸出（node 230），以 `video_frame_offset` 接第一段 node 62 第 5 個輸出。節點內部會取前段最後 5 幀作動作延續，第二段解碼後依 node 400 的 `trim_image` 去掉重疊幀，再由 node 405 `ImageBatch` 接到第一段後面。每段 33 幀，總長固定 33 + 28 = 61 幀（3.8125 秒）；node 300 `length` 固定 61。

- seed：node 63 和 node 401 都必須換成明確整數；沒有特別理由時兩段用同一個 seed。
- Mix 的 SAM 點位、mask、背景對整段 61 幀共用，點位以第一幀判定，仍須抽查後段人物沒有離開遮罩。
- 只提供兩段的固定 templates。需要更長的片段時停止並告知，不要臨場複製延伸節點；先以多次兩段輸出各自驗收，或由維護者另做並實測新的固定 template。
- 不同段之間的接縫幀（第 32、33 幀前後）是必要人工檢查點。

## 音訊保留

四個 Wan Animate templates 的 node 15 `CreateVideo` 預設沒有 `audio` 輸入，輸出無音軌。Brief 明確要求保留來源音訊時，queue 前在 node 15 inputs 加入 `"audio": ["23", 1]`（`GetVideoComponents` 的音訊輸出）。這是唯一允許的結構性選項。存檔時音訊會截到影片長度；輸出幀與來源第 0 幀起逐幀對齊，所以來源片段的起點就是音訊起點。來源本身沒有音軌時，接上連線也只會輸出無音軌影片，下載後仍需核對 audio stream 是否存在。

## 解析度

寬高可改，但必須是 16 的倍數，且同一張 graph 內要一致：node 212 `width`／`height`、node 62 `width`／`height`；延伸段 templates 另含 node 400 `width`／`height`。Node 212 以 center crop 縮放，來源長寬比與目標不同時會裁切，須先確認人物仍在裁切範圍內。Mix 點位座標改用新寬高的 crop 座標（`0 <= x < width`、`0 <= y < height`）。DWPose node 100／101 的 `resolution` 保持 384 即可。

已實測 384×384 與直式 384×640（Move17）。其他尺寸（例如 480×832）可以使用，但視為未實測：先跑 17 幀確認顯存與輸出，再跑較長片段。16 GB 顯卡上較大尺寸可能 OOM，失敗時保留證據並回報，不自動降尺寸重送。

## Queue、輪詢與下載

完成 preflight、輸入檢查及 upload 後，以 `POST /prompt` 提交 API graph：JSON body 是 `{"prompt": <API graph>, "client_id": "<UUID>"}`。保存回應中的 `prompt_id`。PS7 UTF-8 範例：

```powershell
$payload = @{ prompt = $workflow; client_id = [guid]::NewGuid().ToString() } |
    ConvertTo-Json -Depth 40
$body = [System.Text.Encoding]::UTF8.GetBytes($payload)
$queued = Invoke-RestMethod -Uri "$base/prompt" -Method Post `
    -ContentType 'application/json; charset=utf-8' -Body $body
$promptId = $queued.prompt_id
```

只輪詢 `GET /history/{prompt_id}` 判斷此工作；空 history 或未出現項目不表示完成。僅在該 job `status.status_str == "success"` 且 `status.completed == true` 時下載 outputs。`GET /queue` 只供診斷，不能作為個別 job 完成證據。逾時時保存 prompt ID、最後 history 和狀態，不重送、不全域 interrupt、不自動 retry。若取消自己的 pending job，先確認 ownership；可選用 queue-prompt 刪除操作，但一般流程不需要取消。

依該 job outputs 的 node 19 video 或 image descriptors 下載成品。每個 descriptor 用 `GET /view`，query 含 URL-encoded `filename`、`subfolder`、`type`。範例：

```powershell
$query = 'filename=' + [uri]::EscapeDataString($descriptor.filename) +
    '&subfolder=' + [uri]::EscapeDataString($descriptor.subfolder) +
    '&type=' + [uri]::EscapeDataString($descriptor.type)
$viewUrl = "$base/view?$query"
```

保存到全新輸出目錄，記錄輸入／輸出 hash、`workflow_api.json`、`preflight.json`、`history.json`、`candidate.mp4`、`candidate.mp4.json` 與首／中／末幀。完全解碼並核對尺寸、幀數（17／33／61）、16 FPS CFR／PTS、音訊狀態是否符合 brief；任何缺項或錯誤都留失敗收據並停止，不推測補造。技術通過仍只代表輸出契約通過，畫面內容需人工驗收。

## 驗證狀態

2026-10-06 以本技能的固定 templates，直接用 PowerShell 7 HTTP 命令完成 live schema／模型檔案大小檢查、兩次素材上傳、Mix17／Move17 提交、依各自 prompt ID 輪詢與下載。沒有開瀏覽器、沒有新增 Python client 或 CLI。兩支均完整解碼通過：384×384、17 幀、16 FPS、1.0625 秒、H.264、無音訊，PTS 為逐幀精確 1/16 秒。

| 模式 | Prompt ID | Server execution time | 證據 |
|---|---|---:|---|
| Move17 | `56566acd-9d48-41b4-abf1-11bdb1cbc0b1` | 59.946 秒 | [validation](../../../output/wan-animate-api-direct/move17-validation.json) |
| Mix17 | `78498f85-514d-418f-b512-7e58cc7b6b86` | 25.608 秒 | [validation](../../../output/wan-animate-api-direct/mix17-validation.json) |

模型快取／前處理條件不同，以上不作兩模式速度優劣比較。完整 [preflight](../../../output/wan-animate-api-direct/preflight.json)、[上傳回應及輸入 hash](../../../output/wan-animate-api-direct/uploads.json)、實際 `*-api.json`、`*-queue.json`、`*-history.json` 與 MP4／首中末幀同存該目錄。無額外顯存抽樣，不沿用安裝期數字冒充本次量測。

使用的正向 prompt 描述機器人攝影機頭、粉紅金屬、白藍針織衫與來源頭手動作；抽幀仍見肩膀、手臂與手部變形，內容維持 candidate，沒有 Steve 的 accepted 決定。不能宣稱 prompt 已解決身份漂移。33 幀單段僅有先前安裝期 smoke 證據；61 幀延伸段、音訊連線與 384×640 已如上實測；三段以上、其他解析度與多角色未測。不要改既有 profiles 或將此獨立能力登記為 `generate.py` task/backend。

### 延伸段、音訊與解析度實測（2026-10-06）

使用同一 reference 與官方來源片段 frames 64..124（61 幀，另混入 440 Hz 測試音軌以驗證音訊連線），seed 20261006，Mix 點位 positive `[{"x":192,"y":192}]`、negative `[{"x":30,"y":30}]`（依此來源第一幀確認）。三次 queue 全部完整解碼通過，PTS 逐幀 1/16 秒、H.264：

| 測試 | Template | 輸出 | Prompt ID | Server execution time | 證據 |
|---|---|---|---|---:|---|
| Mix61＋音訊 | `mix-extend-api.json` | 384×384／61 幀／3.8125 秒，AAC 3.82 秒 | `f15941e6-27a9-4a80-a073-ee2aaaf98c1c` | 95.5 秒 | [validation](../../../output/wan-animate-extend/mix61-audio/validation.json) |
| Move61（音訊未接） | `move-extend-api.json` | 384×384／61 幀，無音軌 | `aa2550ec-1135-4213-8188-8f04d2145ec8` | 42.0 秒 | [validation](../../../output/wan-animate-extend/move61/validation.json) |
| Move17 直式 | `move-api.json`，寬高改 384×640 | 384×640／17 幀 | `db670069-2278-495c-8961-9977a577311b` | 18.0 秒 | [validation](../../../output/wan-animate-extend/move17-384x640/validation.json) |

抽幀觀察（候選，未驗收）：兩支 61 幀在第 32→33 幀接縫連續，第二段仍維持相機頭機器人與針織衫；Move61 這次沒有出現安裝期的幻覺吉他，但手指與手掌仍有變形。直式 384×640 輸出變成全身構圖，角色比正方形結果更接近 reference，但來源是頭手近景，動作對應是否合格需人工判斷。這次驗證由維護用 harness 執行與本文相同的 HTTP 步驟（放在 ignored `output/`，不是產線 client）。音訊輸入是合成測試音，不代表真實對白的嘴型同步。
