# 本機唇形同步 helper

`tools/film_lipsync.py` 是 MuseTalk v1.5 的固定本機 adapter，供已定稿／已核對的單鏡候選配一段台詞音訊。它不是 `generate.py` task，不使用 ComfyUI graph，也不會下載模型、播放成品、循環動作或判定內容接受。helper 依賴同目錄的 `film_audio.py`；部署需將兩檔放在 `<ComfyUI>/tools/`。MuseTalk 原始碼、權重及 Python runtime 必須留在隔離環境，helper 將音訊與來源影片 staging 到 MuseTalk root 下的暫存目錄，官方腳本只收到 ASCII 相對路徑。

## 輸入契約與固定參數

- 來源影片須為 constant frame rate（CFR）24 FPS，偶數寬高，最長 30 秒，長邊不超過 1280；若已有音軌，必須明確使用 `--replace-audio` 才會以指定台詞取代它。
- 台詞音訊須為單一可讀音軌、非靜音、0.5–30 秒，且長度不得超過來源影片。helper 不循環、延伸或改速來源動作；只取影片開頭涵蓋台詞長度的來源影格。
- MuseTalk 適合單一、近正面的清晰臉部特寫；多臉、側臉、遮擋或小臉的結果不保證可用。素材和嘴型自然度仍須人工檢查。
- 模型固定 MuseTalk v1.5，source commit `0a89dec45a0192b824e3cf4daf96c239440c5ed8`。隔離 runtime 固定核對 Python 3.10、Torch `2.0.1+cu118`、NumPy `1.23.5`、Transformers `4.39.2`、MMCV `2.0.1` 及 CUDA 可用；推論固定 batch size 4、24 FPS、float16。版本或 commit 不符即停止。
- 目標影格數為 `ceil(台詞秒數 × 24)`。官方輸出若比目標少一幀，helper 以最後一幀補尾並把音訊 pad 至影格邊界；差異超過一幀則失敗。成品保持來源寬高，輸出 H.264/AAC MP4 與 JSON 技術 manifest。既有輸出、sidecar 或 log 路徑會阻止覆寫。

## CLI

若目標是有表演感的說話影片，先用影片技能的既有 `img2video` 等 task 產出呼吸、眨眼、視線或輕微頭部動作的候選，核對角色與臉部穩定後才做嘴型。MuseTalk 不會替靜止來源補出完整身體表演；把單張圖重複成影片只能驗證嘴型工具，不能當成影片感已達標。先量定稿台詞長度，安排來源影片涵蓋整句，避免補嘴型時必須循環、裁切台詞或改速。接嘴型後仍需重驗臉部貼合、頭部動作與整體自然度。

以專案根目錄為工作目錄。`$taskPython` 取自 `local_config.json` 的 ComfyUI `python_exe`；`$taskTool` 是已部署的 `<ComfyUI>/tools/film_lipsync.py`。`$museRoot` 與 `$musePython` 必須指向本機隔離安裝的 MuseTalk checkout 和 Python 3.10 runtime；不要將其安裝到 ComfyUI Python：

```powershell
$localConfig = Get-Content .\local_config.json -Raw | ConvertFrom-Json
$taskPython = $localConfig.python_exe
$taskTool = Join-Path $localConfig.comfyui_path 'tools\film_lipsync.py'
$museRoot = '.\output\audio_runtime\MuseTalk'
$musePython = '.\output\audio_runtime\muse\Scripts\python.exe'
& $taskPython $taskTool --muse-root $museRoot --muse-python $musePython --video .\output\production\S001-v01.mp4 --audio .\output\production\S001-line-v01.wav --output .\output\production\S001-lipsync-v01.mp4
```

只有確認要捨棄來源原音軌時才追加 `--replace-audio`。每個新版本都用不同且不存在的輸出檔名；保留影片、同名 `.json` manifest 及 `.log`。

## 隔離環境與狀態

本機隔離安裝位於 repo 的 `output/audio_runtime/MuseTalk/`（MuseTalk source root）和 `output/audio_runtime/muse/Scripts/python.exe`（Python runtime）。模型檔案需依 helper 的 `MODEL_FILES` 常數存在，包含 MuseTalk v1.5 UNet/config、SD-VAE、Whisper、DWPose、face-parse-bisent、S3FD 權重及 `scripts/inference.py`；缺任一檔案即停止。source revision 必須精確為 `0a89dec45a0192b824e3cf4daf96c239440c5ed8`。隔離環境套件 freeze 證據見 `muse-environment.txt`（本機證據：`output/film_audio_smoke/muse-environment.txt`），`pip check` 無依賴問題。helper 執行時會核對固定套件版本、CUDA、必要權重和來源 revision，檢查失敗即停止，不會降級到 ComfyUI runtime。

2026-10-03 官方腳本初步 smoke 使用 yongen 插畫角色首幀來源：148 幀、24 FPS、352×608，搭配 Qwen Uncle_Fu 6.16 秒台詞；官方 MuseTalk 產出 147 幀、6.125 秒可解碼影片，contact sheet 可見嘴部變化。

`film_lipsync.py` 第二輪固定 helper 已技術通過：`output/film_audio_smoke/musetalk_v01.mp4` 為 352×608、24 CFR、148 幀（6.1666667 秒）；MuseTalk 原始 147 幀後補最後一幀，48 kHz 音訊 295,680 samples 補 320 samples 靜音，helper elapsed 31.88 秒。相同已部署 helper 重跑 `musetalk_v02.mp4` 也成功，輸出同為 352×608、24 CFR、148 幀（6.1667 秒），elapsed 31.08 秒。4 個 lipsync contract tests 與 portable suite 17 tests pass；最終部署同步的 portable 測試為 25 pass、0 fail。這些結果驗證 adapter 的輸入、影格及音訊契約；影片內容仍是 `candidate`，嘴型同步自然度未驗收，不能宣稱騎士角色可用、插畫角色已適用或劇情素材已接受。

官方來源：[MuseTalk](https://github.com/TMElyralab/MuseTalk)。本 helper 僅封裝固定版本與有限輸入契約，不把 MuseTalk 上游的其他展示流程視為本機已接入能力。
