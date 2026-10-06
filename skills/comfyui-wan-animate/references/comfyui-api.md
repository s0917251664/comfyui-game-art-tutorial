# Wan Animate 固定 ComfyUI API 操作契約

本文件說明如何由 agent 直接呼叫本機 ComfyUI API，使用版控中的固定 graph JSON。它不是 Python client、CLI 或 `generate.py` backend。每次執行前讀取 `local_config.json`，使用其中 `comfyui_url` 做 live preflight。

## 固定 templates 與 preflight

使用技能目錄中的 [Mix API graph](../assets/mix-api.json)、[Move API graph](../assets/move-api.json)及[template manifest](../assets/template-manifest.json)。以 `GET {comfyui_url}/object_info` 取得 live schema，核對兩份 graph 的 node class 存在，並確認 loader 對應的 live model selectors 可選到 graph 固定使用的模型。再比對 manifest 中模型路徑與檔案大小。Preflight 必須在任何上傳前完成；node、model selector、資產或 graph input 不匹配就停止，不要用相似名稱推定相容。

可用目前會話的 HTTP 工具直接呼叫 API。若需本機 shell，可在互動式 PowerShell 7 使用系統既有 `Invoke-RestMethod`、`.NET HttpClient` 或 `curl.exe`；不要建立 `.ps1`、Python client 或其他包裝程式。以下是可直接改值使用的 PowerShell 7 範例：

```powershell
$base = 'http://127.0.0.1:8188'
$schema = Invoke-RestMethod -Uri "$base/object_info" -Method Get
```

固定參數為 384×384、16 FPS、6 steps、CFG 1、Euler/simple、CPU text encoder。動態替換欄位只限 prompt、reference、source video、明確 seed、唯一 output prefix、輸出 17／33 幀；Mix 另有 SAM 點位。依模板 node input key 填值：node 21 `text`、node 10 `image`、node 145 `file`、node 300（ImageFromBatch）`length`、node 62 `length`、node 63 `seed`、node 19 `filename_prefix`、node 107 `coordinates_positive`／`coordinates_negative`。以實際模板與 live schema 核對，不可只憑 node ID 虛構 input。

模板占位符包括 `__REFERENCE_IMAGE__`、`__SOURCE_VIDEO__`、`__POSITIVE_PROMPT__`、seed `-1`、`__OUTPUT_PREFIX__`；Mix 另含 `__POSITIVE_POINTS__`、`__NEGATIVE_POINTS__`。seed 必須換為明確整數，prefix 必須唯一。圖片及影片需先 upload 才有 server path；收到兩次 upload response 後，才替換各自 path。queue 前掃描完整 graph，所有占位符都必須已替換，seed 不可是 `-1`。任何 input 不確定就先停止。

## 輸入準備與上傳

來源影片需為 16 FPS CFR，片段長度 17 或 33 幀。所選片段須至少包含本次要求的幀數，最長 33 幀；33 幀 source 可用 node 300 `ImageFromBatch.length` 選取 17 幀，node 62 `length` 設定輸出 17 或 33 幀。不要把長片直接上傳再期待 graph 只解碼所需片段。用 repo 既有媒體工具準備片段，不新增媒體處理程式。reference 圖及來源影片先檢查可解碼、用途、版本及 hash。

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

source video 使用同一路徑再上傳，並各自保存完整 JSON 回應。上傳失敗時記錄錯誤及已成功的 upload path，不重複 queue。Graph 不含音訊輸出；brief 記錄音訊採 `drop`。若需求要求保留來源音訊，停止此 graph 流程並說明能力不支援。

## Mix 點位與 Move

Mix 點位座標使用 384×384 graph 中心裁切座標，不是原圖像素座標；範圍為 `0 <= x,y < 384`。node 107 的值是 JSON 字串，例如 positive `'[{"x":192,"y":192}]'`、negative `'[]'`。Mix 至少要一個 positive point，negative 可以空陣列；點位須根據本次 source／人物確認，不能沿用其他影片的點位。ComfyUI UI 可選用於視覺檢查點位，平常仍由 API 執行。

Move 不傳 SAM points，也不接來源角色遮罩或沿用來源背景要求；背景由 reference 與目標 brief 定義。Prompt 描述實際觀察到的動作和身份錨點，不加入來源沒有的動作或道具。

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

保存到全新輸出目錄，記錄輸入／輸出 hash、`workflow_api.json`、`preflight.json`、`history.json`、`candidate.mp4`、`candidate.mp4.json` 與首／中／末幀。完全解碼並核對尺寸、17／33 幀、16 FPS CFR／PTS、音訊狀態；任何缺項或錯誤都留失敗收據並停止，不推測補造。技術通過仍只代表輸出契約通過，畫面內容需人工驗收。

## 驗證狀態

2026-10-06 以本技能的固定 templates，直接用 PowerShell 7 HTTP 命令完成 live schema／模型檔案大小檢查、兩次素材上傳、Mix17／Move17 提交、依各自 prompt ID 輪詢與下載。沒有開瀏覽器、沒有新增 Python client 或 CLI。兩支均完整解碼通過：384×384、17 幀、16 FPS、1.0625 秒、H.264、無音訊，PTS 為逐幀精確 1/16 秒。

| 模式 | Prompt ID | Server execution time | 證據 |
|---|---|---:|---|
| Move17 | `56566acd-9d48-41b4-abf1-11bdb1cbc0b1` | 59.946 秒 | [validation](../../../output/wan-animate-api-direct/move17-validation.json) |
| Mix17 | `78498f85-514d-418f-b512-7e58cc7b6b86` | 25.608 秒 | [validation](../../../output/wan-animate-api-direct/mix17-validation.json) |

模型快取／前處理條件不同，以上不作兩模式速度優劣比較。完整 [preflight](../../../output/wan-animate-api-direct/preflight.json)、[上傳回應及輸入 hash](../../../output/wan-animate-api-direct/uploads.json)、實際 `*-api.json`、`*-queue.json`、`*-history.json` 與 MP4／首中末幀同存該目錄。無額外顯存抽樣，不沿用安裝期數字冒充本次量測。

使用的正向 prompt 描述機器人攝影機頭、粉紅金屬、白藍針織衫與來源頭手動作；抽幀仍見肩膀、手臂與手部變形，內容維持 candidate，沒有 Steve 的 accepted 決定。不能宣稱 prompt 已解決身份漂移。33 幀僅有先前安裝期 smoke 證據，本技能模板此次只重新實測 17 幀；音訊保留、其他解析度、多角色與 SCAIL-2 未測。不要改既有 profiles 或將此獨立能力登記為 `generate.py` task/backend。
