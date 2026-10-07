# CLI、部署與 plan 契約

## 架構與部署

`tools_src/video_layers.py` 是薄 client；固定 API graph 只有 `SteveVideoLayers` 一個節點。`tools_src/comfyui_video_layers/` 是共用 client/server package。部署 client 至 `<ComfyUI>/tools/video_layers.py`，package 同步部署到 `<ComfyUI>/tools/comfyui_video_layers/` 與 `<ComfyUI>/custom_nodes/comfyui-video-layers/`，三處 package bytes 必須一致。Client 依賴既有 `generate.py` facade 與整個 `comfyui_pipeline/`，以及部署於 tools 的 `comfyui_face_swap_video/media.py` 和 `contracts.py`；後兩者提供既有影片 inspect、音訊時間軸等共用 helper，本工具不呼叫 ReActor 推論。

`local_config.json` 提供 `comfyui_path`、`comfyui_url`、`python_exe`。Live URL 必須是 loopback HTTP。Client `preflight` 比對 client、兩份 server package、shared helper SHA-256，並檢查 `/object_info` 的 `SteveVideoLayers` 三個 STRING 欄位。Segment 另要求本機快取 SAM 模型檔案與固定 SHA-256；使用 `local_files_only=True`，不下載。此次安裝重用既有 SAM cache，沒有下載模型或套件。以下 runtime pins 是本次本機 gate，不代表所有平台通用安裝組合；版本或模型 pin 不符就停止：`av==18.1.0`、`opencv-python==5.0.0.93`、`torch==2.13.0+cu130`、`transformers==5.15.0`。若另一平台不符，先按 [comfyui-install](../../comfyui-install/SKILL.md) 評估既有環境與該平台支援，不要因此自動安裝或升降級套件。

Server 啟動時載入 package hash；節點開始執行時比對 client preflight 傳入的 package hashes、磁碟 package bytes 與該 server process 已載入的 hashes，任一不符就拒絕執行。這不是 client queue 前的 loaded-hash gate；client queue 前能檢查磁碟部署一致性和 live node schema。2026-10-04 生產 ComfyUI 8188 已在 queue 空時依原參數重啟，fresh `production-current-preflight.json` 通過。若再更新 server package，仍需重新載入 server 並重做 fresh preflight。

## CLI

在 repo 根目錄解析本機 Python 與工具路徑：

```powershell
$ConfigPath = (Resolve-Path local_config.json).Path
$Config = Get-Content -Raw $ConfigPath | ConvertFrom-Json
$Python = $Config.python_exe
$Tool = Join-Path $Config.comfyui_path 'tools/video_layers.py'
& $Python $Tool preflight --config $ConfigPath --plan 'D:\input\plan.json'
& $Python $Tool run --config $ConfigPath --plan 'D:\input\plan.json' `
  --output-dir 'D:\output\video-layers-v1' --timeout 600
```

`--config` 與 `--plan` 必填。`--output-dir` 僅 `run` 使用，目錄必須不存在；不覆寫。`--timeout` 為 1–3600 秒，預設 600。輸入影片、背景、圖片、遮罩及 segmentation manifest 均須為現存絕對路徑；不經 client 上傳，server 需能讀取相同路徑。

## Plan schema v1

所有 plan 含 `"schema_version": 1`、`"operation": "segment" | "compose"`、`"video"`（絕對路徑）、`"start"`、`"end"`。來源影片沿用 `inspect_video`：單一 CFR 影片條件、1–60 FPS、偶數尺寸、最長邊不超過 1920、片長至多 60 秒。處理片段最長 5 秒、至多 300 幀；工作畫面寬度預設 960，可指定偶數 256–1280，工作畫面最長邊不超過 1280、總處理像素至多 150,000,000。輸出維持來源 FPS，音訊預設 drop；`"audio":"preserve"` 時會裁出片段音訊並編成 AAC。

### Segment

Plan 另含 `"objects"` 陣列，必須有 1–4 個不同整數 `id`（1–999）。每個 object 的 `prompts` 至少含 frame 0，提示影格需唯一且位於片段內。可用 box（工作畫面座標 `[x1,y1,x2,y2]`）、points 搭配同數量 0/1 labels，或工作尺寸的 selected-white `L` PNG `mask`；同一提示不可混用 mask 與 box/points。後續提示影格可修正傳播。範例：

```json
{
  "schema_version": 1, "operation": "segment",
  "video": "D:/input/shot.mp4", "start": 8.2, "end": 8.85,
  "width": 960, "audio": "preserve",
  "objects": [{"id": 1, "prompts": [
    {"frame": 0, "box": [410, 120, 620, 420], "points": [[510, 230], [420, 390]], "labels": [1, 0]},
    {"frame": 18, "points": [[505, 240]], "labels": [1]}
  ]}]
}
```

### Compose

Plan 另含靜態 `background` 圖片與 1–8 個依陣列順序繪製的 `layers`。背景轉 RGB，需偶數寬高、最長邊不超過 1280，總輸出像素不超過 150,000,000。Layer `kind` 為 `source` 或 `image`：

- `source` 指 `segmentation` manifest 及其中的 `object` id。Manifest 必須是 segment 輸出，source SHA-256、片段起點、幀數與工作畫布均須和本 plan 完全相符；遮罩逐檔 hash 亦會重驗。`track` 是來源影片第 0 幀的三個 moving anchors，`destination` 是靜態背景上的三個目標點。
- `image` 指最長邊不超過 4096 的 RGBA 圖。`image_points` 是該圖片上的三個固定錨點；來源影片的 `track` 三點或 `keyframes` 位置會驅動其移動。
- `track` 與 `keyframes` 必須擇一。`track` 使用影片第 0 幀的三個點，由 Lucas–Kanade 光流逐影格追蹤，forward/backward 誤差須不超過 2 px，任何追蹤失敗或離開畫布即停止，不會靜止沿用最後位置。image layer 的 `track` 可選 `destination` 三點作初始 target placement：將來源軌跡映射到 target space，再帶動固定 `image_points`。Source layer 的 `destination` 仍代表固定 target anchors。若用 `keyframes`，首尾 frame 必填、中間 keyframe 可選；image layer keyframe points 直接定義於 target space，不使用 `destination` 映射。各 keyframe 間線性插值。Synthetic known-translation 通過，但 Kabuto 原片 LK 在 frame 1 失敗（Comfy prompt `844711e3-44ad-48ce-89ba-4bbd963ecd9a`，無 candidate 發佈）；真實素材需人工 keys，且不宣稱追蹤通用可靠。
- `opacity` 為 0–1，`blend` 為 `over`（預設）或 `screen`。可選 `occlusion_mask` 是與 target background 同尺寸的 `L` PNG，白色表示遮住該 layer、保留底圖，黑色表示顯示 layer。

範例只示意 source layer 的排列；實際座標須對應工作畫布：

```json
{
  "schema_version": 1, "operation": "compose",
  "video": "D:/input/shot.mp4", "start": 8.2, "end": 8.85,
  "background": "D:/input/accepted-still.png", "audio": "preserve",
  "layers": [{"kind": "source", "segmentation": "D:/output/segment/manifest.json", "object": 1,
    "track": [[420, 180], [520, 170], [610, 310]],
    "destination": [[430, 190], [530, 180], [620, 320]],
    "blend": "over", "opacity": 1,
    "occlusion_mask": "D:/input/occlusion.png"}]
}
```

對 source，原片錨點逐影格追蹤、destination 固定；對 image，`image_points` 固定於圖片、影片錨點驅動圖片變換。所有 affine 三點三角形需非退化。Source layer 從原片 RGB 取用所選遮罩區域，可搬移該來源內容；仿射重採樣、混色與 MP4 編碼會改變像素值，這不是無損複製，也無法把烘焙進背景／材質／光照的特效精確拆成獨立層。

## 輸出與狀態

Server 原子建立新輸出目錄，包含 `candidate.mp4`、`manifest.json`、`layers.zip`、`source.jpg`、`comparison.jpg`；segment 的 candidate 是彩色遮罩預覽，zip 含每幀遮罩；compose zip 含逐幀合成 PNG。Client 目錄另記錄 `workflow_api.json`、`history.json`、`receipt.json` 及下載成果。Manifest 留 server PID、runtime、package/model/input/plan hash、音訊資訊、完整解碼結果、SAM 面積／相鄰影格 temporal IoU，或 affine matrix／每層遮罩外變動像素等資訊。

2026-10-04 生產 ComfyUI 8188 fresh preflight 記錄於 `production-current-preflight.json`。最新結果固定使用 `*-current` 名稱；舊 `*-v1` 和 `*-final` 輸出只供歷史追溯。`production-segment-current`（server PID 14020，10.615 秒）處理 8.2–8.85 秒：39 幀、960×540、60 FPS、0.65 秒、H.264 + AAC、31,744 decoded samples，逐幀 PTS grid 和 full decode pass；兩 objects 共 78 masks、empty 0，content candidate。`production-compose-current`（同 PID，8.389 秒）為 39 幀、1024×1024、60 FPS、H.264 + AAC、31,744 samples，PTS/CFR 與 full decode pass，technical warning、candidate。

`arm-segment-v1` 只在下方甲片有效；`arm-segment-v2/v3` 的後續提示未生效，因 Transformers 5.15 在 frame-0 `obj_with_new_inputs` 會消耗多影格提示。修正為逐影格 just-in-time prompt 注入並聚合多物件 IDs 後，`arm-segment-v4`（plan-v3）於 frame 22 面積 25,229→39,261、frame 38 面積 15,064→36,642；新增區域仍粗糙、甲片輪廓不準且中間漏選。Production current 雙物件 mask 可運作，但仍需逐幀人工修邊；technical pass 不代表準確 matte。

肉眼 current QA 顯示甲片貼在靜態人物的畫面左側衣袖，後段位置、比例和裁切仍錯；armor mask 到 frame 22 含部分背景，外溢 glow 漏選。`independent-png-qa.json` 直接讀實際 39 張輸出 PNG：production compose protected head/collar 區每幀 666,624 pixels，total changed 0；`prop-occlusion-current` fingers white matte 每幀 14,785 pixels；`belt-occlusion-current` jacket matte 每幀 958,351 pixels；後兩者遮擋區 total changed 都為 0。三者 manifest outside-mask changed max 均為 0。這些數值代表 PNG matte 區域像素驗證，不等於 MP4 無損或美術接受。

`prop-occlusion-current`（8.338 秒）與 `belt-occlusion-current`（7.903 秒）都為 39 幀、1024 square、60 FPS、H.264/AAC、31,744 samples、full decode pass、technical warning/candidate。Props 由使用者照片去背／旋轉而來，沒有生成道具；靜態照片重複 39 幀，拇指離物、指緣不自然。腰帶 matte 遮擋有效，但照片透視、3D 繞腰接觸與動態尚未解決，手勢和腰帶素材均未 accepted。

20 個 Video Layers tests（新增 image track-to-destination mapping regression）和 17 個 portable tests 通過；portable report 43 passed、0 failed。嚴格輸出 gate 檢查 FPS、每幀 PTS grid、H.264 video、AAC 48 kHz stereo 及完整 decode；四個 current MP4 均 pass。`detect_video_capabilities.py` 重掃正式 8188 後 default H3、H3/Wan available；這些是既有生成能力，不是 Video Layers backend。`face-swap-preflight-after.json` 的獨立 ReActor gate pass，commit `a12c5b19dcac9ae8b47e592da39c9711c8f8c756`，換臉仍沿自己的契約。測試 server 8189 已關閉。

**跨工具 ACL 修正：** Python 3.13 Windows `tempfile.mkdtemp()` 私有 mode-0700 DACL 在 rename 後會阻止不同 desktop/tool identity 讀取成品。新 client 與 server 改成在 output parent 下建立隨機 UUID stage directory（一般 `mkdir()` 繼承 parent ACL），保留拒絕覆寫及 atomic rename。已在一般與核准程序跨身份讀取測試；current 輸出能由預設 tools 跨呼叫讀取。這只改 Video Layers client/server，不改 face-swap media 或 generation source。Manifest `output.path` 指向最終 server 輸出，而非暫存 stage。Strict technical pass 不等於內容 accepted；source matte 仍不是 baked VFX exact extraction，2D affine 也不解 3D／接觸／動畫身體問題。
