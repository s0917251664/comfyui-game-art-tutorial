# Face Swap 接入紀錄

**本頁範圍只限原始 Wan Animate workflow 的接入評估與缺口。** 本頁所稱「本次交付不能列為可執行換臉工具」僅指該 Wan Animate workflow；不適用於已另行完成部署和 smoke 的 ComfyUI ReActor server-side wrapper。ReActor 狀態與驗證見 [local-tool.md](local-tool.md)。

目前另有已安裝的 Wan2.2 Animate 固定 template（Mix／Move）；2026-10-06 Mix17／Move17 與兩段延伸 61 幀直接 HTTP 技術通過，內容仍 candidate，也未接入 `generate.py` task/backend。這不是本頁所述舊 WanVideoWrapper graph 的升級或驗收。目前一律用 `gameart.py run` 執行這些固定 template，讀 [comfyui-wan-animate 技能](../../comfyui-wan-animate/README.md)及其[操作契約](../../comfyui-wan-animate/references/comfyui-api.md)。

確認日期：2026-10-04。狀態：blocked dependencies / unverified generation。

來源：[介紹頁](https://comfy.org/workflows/93f286fbc2c8-93f286fbc2c8/) 與 [下載 JSON](https://comfy.org/workflows/download/93f286fbc2c8.json?filename=93f286fbc2c8)。本機原始下載存放 `output/face-swap-reference/upstream.json`，為忽略版控的參考產物；不是已部署的產線 graph。下載版本的 SHA256 與節點缺口見同目錄 `audit.json`。

## 實際依賴

原圖包含 WanVideoWrapper、KJNodes、VideoHelperSuite 的節點，另有 Florence2、SAM2、ONNX detection、AILab_QwenVL。JSON 的 node_versions 不涵蓋所有套件，因此安裝前仍須依節點 properties / 官方 repo 核對 provider，不猜來源。

主要載入名稱（必須核對相容家族，不能以同類檔名替換）：

- `Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors`
- `WanAnimate_relight_lora_fp16.safetensors`
- `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors`
- `Wan2_1_VAE_fp32.safetensors`
- `umt5-xxl-enc-bf16.safetensors`
- `clip_vision_h.safetensors`
- `vitpose-l-wholebody.onnx`、`yolov10m.onnx`
- Florence-2-large、SAM2 base-plus、Qwen3-VL-2B-Instruct。

原圖含自動下載 loader；匯入不代表已安裝，不能未核對下載行為就 queue。自動描述是否可移除、模型量化與編譯選項是否可改，需另做固定 graph 版本與實測，這次未變更。

## 本機檢查與限制

2026-10-03 的 capability snapshot 只涵蓋 H3 與 Wan 5B。2026-10-04 檢查 custom_nodes 目錄，沒有上述 WanVideoWrapper、KJNodes、VideoHelperSuite；模型檔案掃描亦未找到上述 Animate、LoRA、VAE、ONNX 等指定檔名。快照節點差集記錄為參考，執行前仍需查 live `/object_info`。

原圖是 UI format，含 Set/Get 虛擬連線及 widgets，非可直接送出的 API format。不可硬套 generic widgets-to-input converter。影片寬高、幀數與 FPS 有連線覆蓋 widget 值，不能從單一 widget 宣稱輸出規格。

## 新能力檢查結果

- 已完成：來源頁與完整 JSON 讀取、模型／節點盤點、專用技能與人工驗收流程、原檔結構檢查及 hash 留存。
- 未完成：官方套件與模型下載來源／license 核對、安裝、VRAM／runtime 可行性實測、固定 API graph、CLI task、capability 擴充、部署、生成 smoke test、音訊／sidecar 與畫面驗收。
- 未修改：既有 backend、profile、模型與機器 capability 驗證狀態。

本頁僅記錄原始 Wan Animate 工作流的接入缺口；該流程尚不能列為已可執行能力。已完成的 ComfyUI ReActor 換臉工具、實測證據與限制見 [local-tool.md](local-tool.md)。
