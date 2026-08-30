# 已驗證版本清單（tested-version manifest）

這份文件記錄「曾在同一台已安裝機器上實際跑通」的工具、custom node（自訂節點）、Python 套件與模型版本。它不是目前最新版推薦，也不應把可變的 `main`/`master` 分支當成版本。安裝流程先依這份清單的已驗證版本重現；要升級時，另做一次完整 smoke test（冒煙測試）並更新紀錄。

目前狀態：**待在已安裝機器擷取（pending capture on installed machine）**。

本 repository 沒有 `local_config.json`、ComfyUI 安裝目錄或模型檔，因此目前沒有可誠實填入的 ComfyUI/custom node commit、套件版本或模型 SHA-256。下列欄位刻意保留 `null`；不要用猜測的 commit 或雜湊值填補，也不要把下載頁面的檔名當作內容版本。

## 擷取規則

在已安裝且已完成一次端到端產圖驗證的機器上，從該機器的實際路徑擷取資料，再把結果填入本文件的 manifest 範本：

```bash
COMFYUI_PATH="<ComfyUI 安裝路徑>"
PYTHON_EXE="<ComfyUI>/.venv/bin/python"

git -C "$COMFYUI_PATH" rev-parse HEAD
git -C "$COMFYUI_PATH/custom_nodes/ComfyUI-Manager" rev-parse HEAD
git -C "$COMFYUI_PATH/custom_nodes/ComfyUI_IPAdapter_plus" rev-parse HEAD
git -C "$COMFYUI_PATH/custom_nodes/comfyui_controlnet_aux" rev-parse HEAD
# NVIDIA 機器才執行；Mac MPS/CPU 機器以 device_config.json 的 backend 與 unified_memory_mb 為準。
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
fi

"$PYTHON_EXE" --version
"$PYTHON_EXE" -c 'import sys; print(sys.version); import torch; print("torch", torch.__version__); import PIL; print("Pillow", PIL.__version__)'

# Linux 使用 sha256sum；macOS 將 sha256sum 換成 shasum -a 256。
sha256sum "$COMFYUI_PATH/models/checkpoints/<檔名>"
sha256sum "$COMFYUI_PATH/models/controlnet/<檔名>"
sha256sum "$COMFYUI_PATH/models/ipadapter/<檔名>"
sha256sum "$COMFYUI_PATH/models/clip_vision/<檔名>"
sha256sum "$COMFYUI_PATH/models/background_removal/<檔名>"
sha256sum "$COMFYUI_PATH/models/upscale_models/<檔名>"
```

Windows PowerShell 可用同等指令：

```powershell
$ComfyUiPath = "<ComfyUI 安裝路徑>"
$PythonExe = "<ComfyUI>\.venv\Scripts\python.exe"

git -C $ComfyUiPath rev-parse HEAD
git -C "$ComfyUiPath\custom_nodes\ComfyUI-Manager" rev-parse HEAD
git -C "$ComfyUiPath\custom_nodes\ComfyUI_IPAdapter_plus" rev-parse HEAD
git -C "$ComfyUiPath\custom_nodes\comfyui_controlnet_aux" rev-parse HEAD
# NVIDIA 機器才執行；沒有此命令時保留 null，並記錄 device_config.json。
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
}

& $PythonExe --version
& $PythonExe -c "import torch, PIL; print('torch', torch.__version__); print('Pillow', PIL.__version__)"
Get-FileHash "$ComfyUiPath\models\checkpoints\<檔名>" -Algorithm SHA256
Get-FileHash "$ComfyUiPath\models\controlnet\<檔名>" -Algorithm SHA256
Get-FileHash "$ComfyUiPath\models\ipadapter\<檔名>" -Algorithm SHA256
Get-FileHash "$ComfyUiPath\models\clip_vision\<檔名>" -Algorithm SHA256
Get-FileHash "$ComfyUiPath\models\background_removal\<檔名>" -Algorithm SHA256
Get-FileHash "$ComfyUiPath\models\upscale_models\<檔名>" -Algorithm SHA256
```

每個 hash 都要對應實際檔案、模型家族與來源 URL；若模型由 `extra_model_paths.yaml` 指向共享模型庫，請記錄共享模型庫的真實檔案路徑。完成後填上 `captured_at`、`machine`、`smoke_test`，並保留 `device_config.json` 的 tier/backend/解析度結果作為同一筆驗證的上下文。

## Manifest 範本

以下是可直接複製到 issue 或未來專用 JSON/YAML 檔的結構。`null` 代表尚未擷取，不代表任何預設版本或已驗證通過：

```yaml
manifest_version: 1
capture_status: pending_on_installed_machine
captured_at: null
machine: null
device_config:
  tier: null
  backend: null
  gpu_name: null
  driver_version: null
  vram_mb: null
  unified_memory_mb: null
  default_width: null
  default_height: null
comfyui:
  commit: null
  source: https://github.com/comfyanonymous/ComfyUI.git
custom_nodes:
  ComfyUI-Manager:
    commit: null
    source: https://github.com/Comfy-Org/ComfyUI-Manager.git
  ComfyUI_IPAdapter_plus:
    commit: null
    source: https://github.com/cubiq/ComfyUI_IPAdapter_plus.git
  comfyui_controlnet_aux:
    commit: null
    source: https://github.com/Fannovel16/comfyui_controlnet_aux.git
runtime:
  python: null
  torch: null
  pillow: null
models:
  - file: null
    family: null
    sha256: null
    source: null
    captured_from: null
smoke_test:
  status: not_run
  date: null
  command: null
  output: null
```

### 版本更新門檻

只有在同一個 manifest 內的 ComfyUI commit、custom node commits、Python/PyTorch/Pillow 版本與使用到的模型 SHA-256 都已擷取，並且至少完成一次最小產圖與輸出檔驗收後，才把 `capture_status` 改成 `verified`。只更新其中一項時，保留 `pending_on_installed_machine`，避免把未驗證的混合環境誤當成可重現版本。

本文件不會替目前尚未查證的版本填入假的 SHA；拿不到已安裝機器的檔案，就維持 `null` 並在交付回報中說明尚未完成實機驗證。
