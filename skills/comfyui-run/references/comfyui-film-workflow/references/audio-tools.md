# 本機旁白與 Animatic 工具

`tools/film_audio.py` 是劇情影片製作流程的本機音訊與預視 helper，不是 `generate.py` task，也不使用 ComfyUI graph、server 或 custom node。部署時將 `tools_src/film_audio.py`、`tools_src/film_qwen.py`、`tools_src/film_sapi.ps1` 三檔同步到 `<ComfyUI>/tools/`；入口可用 ComfyUI Python 3.13 執行。它使用該環境既有 PyAV、NumPy、Pillow。更新 helper 後三檔要一起部署。`verify_portable_install.py` 的 `SYNC_SOURCE_FILES` 已列入這三檔。

## 能力與限制

- `voices` 列出 Windows 已安裝 SAPI 聲線；`probe` 檢查媒體技術資訊；`tts` 將單段文字轉 WAV；`mix` 依 JSON 時間線疊混最多 32 軌；`animatic` 依靜幀和秒數或旁白實測長度輸出時間預視；`dub` 將一條音訊配到既有 24 FPS 影片。
- 成品音訊統一為 48 kHz、雙聲道、PCM 16-bit WAV；Animatic/Dub 輸出 H.264、24 FPS MP4，可帶 AAC。單次片段最長 10 分鐘；單次 TTS 文字上限 5,000 字，Qwen3 單段上限 500 字；Animatic 每份最多 200 鏡。較長作品分段製作。
- 輸出路徑必須是新檔名；同名檔案或 sidecar 已存在時會停止。每個輸出旁寫 `.json` 技術 manifest，技術 pass 的內容狀態仍為 `candidate`。
- 不提供字幕燒錄、ducking、time stretch、音樂生成或自動播放。唇形同步是另一個選配 helper，狀態見[本機唇形同步 helper](lipsync-tools.md)。配音長短不符需調整計畫，或對 `dub` 明確選擇補靜音／裁切；`mix` 超峰值預設報錯，需明確指定正規化政策。
- TTS 先作聲線草稿與台詞量時；聽取並調整台詞、停頓與鏡頭時間後，才把實測秒數寫回計畫。所有音訊、靜幀、Animatic 與影片先列 `candidate`，由美術審核者決定是否接受。

## CLI 範例

以下以 repository 根目錄作為工作目錄。先從 `local_config.json` 取得已部署 ComfyUI Python 路徑，helper 路徑依 ComfyUI 安裝目錄組成；不要假設 portable Python 位置：

```powershell
$localConfig = Get-Content .\local_config.json -Raw | ConvertFrom-Json
$taskPython = $localConfig.python_exe
$taskTool = Join-Path $localConfig.comfyui_path 'tools\film_audio.py'
& $taskPython $taskTool voices
& $taskPython $taskTool probe .\output\film_audio_plan\scratch\line.wav
& $taskPython $taskTool tts --engine sapi --voice "<voices 命令列出的完整聲線名稱>" --text-file .\output\film_audio_plan\S001.txt --output .\output\film_audio_smoke\S001-sapi-v01.wav
& $taskPython $taskTool tts --engine piper --piper-python .\output\audio_runtime\piper\Scripts\python.exe --model .\output\audio_runtime\models\zh_CN-huayan-medium.onnx --text-file .\output\film_audio_plan\S001.txt --output .\output\film_audio_smoke\S001-piper-v01.wav
& $taskPython $taskTool tts --engine qwen3 --qwen-python .\output\audio_runtime\qwen\Scripts\python.exe --model .\output\audio_runtime\models\qwen17 --speaker Serena --instruction "用堅定而平靜的語氣說，語速稍慢，停頓自然。" --text-file .\output\film_audio_plan\S001.txt --output .\output\film_audio_smoke\S001-qwen-v01.wav
& $taskPython $taskTool mix --plan .\output\film_audio_plan\mix.json --output .\output\film_audio_smoke\mix-v01.wav
& $taskPython $taskTool animatic --plan .\output\film_audio_plan\animatic.json --output .\output\film_audio_smoke\animatic-v01.mp4
& $taskPython $taskTool dub --video .\output\film_audio_smoke\cut-v01.mp4 --audio .\output\film_audio_smoke\mix-v01.wav --audio-policy exact --output .\output\film_audio_smoke\dub-v01.mp4
```

三個 TTS 引擎均須明確指定，不會自動下載模型或換聲線。SAPI 的 `--voice` 名稱應先由 `voices` 查得。Qwen3 使用已下載的本機模型資料夾。

`mix.json` 範例（位於 `output/film_audio_plan/`），音訊路徑相對於 JSON 檔。`start` 是在混音時間線上的絕對起點，依台詞／鏡頭時序紀錄填入；`gain_db` 為該軌增益：

```json
{
  "duration": 5.5,
  "peak_policy": "error",
  "tracks": [
    {"audio": "../film_audio_smoke/S001.wav", "start": 0, "gain_db": 0},
    {"audio": "../film_audio_smoke/ambience.wav", "start": 0.4, "gain_db": -12}
  ]
}
```

`animatic.json` 範例（位於 `output/film_audio_plan/`）。每鏡擇一使用固定 `duration` 或以旁白實際長度計時的 `timing_audio`，可加 `tail_pause` 秒。`timing_audio` 只供量時，不會自動加入輸出聲音；要製作有聲 Animatic，另設 `audio` 指向 mix WAV，並指定 `audio_policy`：

```json
{
  "width": 768,
  "height": 432,
  "audio": "../film_audio_smoke/mix-v01.wav",
  "audio_policy": "exact",
  "shots": [
    {"id": "S001", "image": "../film_audio_smoke/S001.png", "timing_audio": "../film_audio_smoke/S001.wav", "tail_pause": 0.25},
    {"id": "S002", "image": "../film_audio_smoke/S002.png", "duration": 2.75}
  ]
}
```

已測 Qwen 台詞長 6.72 秒，長於既有影片生成 task 的 2–6 秒單鏡時長；不能直接當成一個生成鏡頭。應規劃為跨剪接的旁白，或依語意拆成多句、分配到多鏡，並在 mix 時按時間線放置。

## 隔離環境與實測狀態

主 helper 使用 ComfyUI Python 3.13 中既有 PyAV、NumPy、Pillow。Piper 1.8.0 與 Qwen TTS 安裝在 `output/audio_runtime/` 獨立環境，避免更動 ComfyUI 套件；Piper 模型在 `output/audio_runtime/models/`。Qwen 環境使用官方 `qwen-tts` 0.1.1、Transformers 4.57.3，不更動 ComfyUI 5.15.0；可唯讀借用既有 torch 安裝。不得為此流程直接升降 ComfyUI Python 的 torch／Transformers。

截至 2026-10-03：Windows SAPI `zh-TW` Hanhan Desktop 已產生 5.772 秒 WAV；Piper 1.8.0 `zh_CN-huayan-medium` 已產生 3.970625 秒 WAV。Qwen3-TTS 1.7B CustomVoice `qwen17` 已成功完成兩個聲線的技術 smoke：Serena 中文單句 native 24 kHz mono、161,280 samples（6.72 秒），推理 11.88 秒；Uncle_Fu 6.16 秒，推理 10.71 秒。兩者均在 RTX 4080、Torch 2.13 cu130、Transformers 4.57.3、bf16/SDPA 執行，聲音轉為 48 kHz stereo。輸出與 JSON manifest 為技術 pass、內容 candidate；尚未聽取，不代表自然度、台灣腔或情緒達標。Qwen 環境唯讀借用既有 Comfy torch，未覆寫其安裝。

8 個有意義的 helper tests 與 portable suite 17 tests pass。有聲 Animatic 技術 smoke 有兩次：10.291666 秒、247 幀，以及 15 秒、360 幀；兩者均為 24 FPS、768×432。15 秒預視與其 dub 均技術 pass。測試重複使用同一張既有、尚未接受的角色圖及純測試聲音，只驗證時間線、編碼與配音技術契約，不能當成真實分鏡作品或劇情成片，也不代表畫面或聲音已接受。

MuseTalk 使用獨立原始碼、模型與隔離 Python 3.10 runtime；固定 helper 的技術 smoke 已通過，但自然度與角色內容尚未接受。模型、runtime 與測試邊界見[本機唇形同步 helper](lipsync-tools.md)。官方來源：[MuseTalk](https://github.com/TMElyralab/MuseTalk)。

官方來源：[Qwen3-TTS 專案](https://github.com/QwenLM/Qwen3-TTS)、[Qwen3-TTS 模型](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice)、[Piper（Open Home Foundation）](https://github.com/OHF-Voice/piper1-gpl)、[System.Speech.Synthesis API](https://learn.microsoft.com/dotnet/api/system.speech.synthesis.speechsynthesizer)、[PyAV 文件](https://pyav.org/docs/stable/)。實測安裝的 Piper Python 套件版本為 1.8.0。
