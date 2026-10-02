# Image edit tools：參數與輸出

## `composite`

必要參數：`--source`、`--edited`、`--mask`、`--output-dir`。三張輸入必須是單影格，尺寸一致；source 與 edited 會解碼為 RGBA。mask 必須是同尺寸、含 Alpha 的 PNG。工具以 Alpha byte 選擇／插值 RGBA channels：0 完全取 edited，255 完全取 source，介於兩者按 byte 權重混合。既有輸出資料夾（即使空目錄）也會拒絕。

輸出新目錄中的 `composited.png` 與 `result.json`。manifest 記錄輸入輸出路徑與 SHA-256、尺寸、保留像素數及候選狀態。alpha=255 區域會做逐 byte invariant 檢查；它不評分編修內容。

## `compare`

必要參數：`--source`、`--edited`、`--output-dir`；`--mask` 選填，但提供時仍須是同尺寸 Alpha PNG。尺寸不符就停止，不自動對齊、縮放或旋轉。

輸出 `difference.png`、`comparison.png`、`comparison.json`；提供遮罩且遮罩含非 255 alpha 區域時才輸出 `detail.png`。差異圖將每像素最大 RGBA byte 差映成紅色強度，沒有 perceptual threshold。統計包含 whole；有 mask 時另列 alpha 0 的 edited、0–255 的 transition、255 的 preserved 區域。RGBA 統計包含完全透明像素內的 RGB 值，不能當成可見差異或美術品質分數。

## `sweep` plan JSON

Plan 欄位僅接受 `task`、`base`、`sweep`、選填 `preserve_outside`。`base` 必須含 `prompt`、固定 `seed` 與 task 必要輸入；路徑相對 plan JSON 所在目錄解析。`sweep` 是參數名稱到非空數值陣列的 mapping，產生笛卡兒積；重複值拒絕，總執行數不得超過 16。固定 prompt、seed、來源圖、mask、control／appearance／character／pose references 不可掃描。

| task | 必要輸入 | 可掃描參數 |
|---|---|---|
| `refine` | `image` | `denoise` |
| `inpaint` | `image`, `mask` | `denoise` |
| `guided_inpaint` | `image`, `mask` | `denoise`, `control_strength`, `appearance_weight` |
| `character_action` | `character_ref`, `pose_ref` | `ip_weight`, `pose_strength` |

所有 sweep 權重限制在 0–1。其他 base 參數依現有 task CLI 白名單，包括 `negative`、`style`、`rating`、`control_type`、尺寸等。`guided_inpaint` 的 control 與 appearance references / weights 依需求提供；`character_action` 用角色參考與姿勢參考。多張參考在這裡只是映射既有不同角色輸入，不表示任意多圖理解。

`preserve_outside: true` 只對 `inpaint`、`guided_inpaint` 生效：每張生成輸出仍保留 raw comparison，並額外產生 mask composite 及 final comparison。它不會替 `refine` 或 `character_action` 合成，也不保證 mask 外生成階段未漂移；合成結果在 Alpha=255 的像素保留 source RGBA bytes。

### 執行與停止

```powershell
python <ComfyUI>\tools\image_edit_tools.py sweep --plan <plan.json> --config <runtime.json> --output-dir <new-dir> --dry-run
python <ComfyUI>\tools\image_edit_tools.py sweep --plan <plan.json> --config <runtime.json> --output-dir <new-dir> --profile <id>
```

runtime config 必須包含 `python_exe`、`generate_script`、`comfyui_url`、`comfyui_path`；另需能讀取 `image_config`（未提供時預設 `<comfyui_path>/tools/image_capabilities.json`）。`python_exe` 與 `generate_script` 必須存在。`--timeout` 預設 240 秒，必須是有限正數。

sweep 會依次呼叫既有 `generate.py` task，每次寫入 `generation.json`、stdout/stderr log，並驗證唯一輸出圖、manifest 與 SHA-256。具有 `image` 輸入的 task 會建立 `raw_comparison/`；沒有 `image` 輸入的 `character_action` 不會建立 raw comparison。中途錯誤會將已完成候選與失敗狀態留在 `sweep.json`，停止後續提交；不要直接重跑整組。若 CLI timeout，先檢查 ComfyUI queue 是否仍在工作。

每次候選會更新 `candidates.png` 接觸圖。輸出不是已接受版本；Steve 逐支檢視並作決定後，才可依專案 result-records 規則記錄 accepted/rejected。`--dry-run` 只驗證計畫並產生命令，不檢查 server、模型或生成結果。

## 範例調整

範例中的 `../../../../output/...` 路徑以範例 JSON 檔案所在的 `reference/examples/` 為相對根目錄解析，指向 repository 根目錄下的 `output/`。複製到實際工作目錄後，請改為實際輸入檔路徑，並指定尚未存在的輸出路徑，由工具建立。這些 prompt 只示範既有輸入欄位，未經實測，不是驗證配方。
