---
type: evaluation-note
status: research-candidate
last_updated: 2026-10-06
---

# Wan Animate 與 SCAIL-2 評估及可控學習方式

執行方式已更新為[Wan Animate 專用技能](../../../skills/comfyui-run/references/comfyui-wan-animate/README.md)與[固定 template（`gameart.py run`）操作契約及實測](../../../skills/comfyui-run/references/comfyui-wan-animate/references/comfyui-api.md)。**2026-10-06 更新：SCAIL-2 FP8 權重已下載並以固定 API templates 實測，操作與結果改以 [SCAIL-2 reference](../../../skills/comfyui-run/references/comfyui-wan-animate/references/scail2.md) 為準；下方「SCAIL-2 評估」段保留為安裝前的研究紀錄。**2026-10-06 新一輪 Mix17／Move17 API 技術通過，內容仍為 candidate；下方原 UI 候選與安裝期觀察保留作比較，不因新測試而繼承驗收。

## 範圍與現況

本筆記整理 2026-10-06 已有的 Wan2.2 Animate 技術證據，以及 SCAIL-2 是否值得作為下一個研究方向。目標是建立可比較、可回溯的學習方式；本筆記不代表生成內容已驗收，也不授權安裝 SCAIL-2 權重或自動 queue。

目前機器為 RTX 4080（16,376 MiB VRAM）、31.1 GiB RAM。本機已安裝 Wan Animate 14B FP8 scaled。已測設定為 384×384、33 幀、16 FPS、6 steps、CFG 1、Euler/simple、seed 20261005。Mix 與 Move 的 API 技術 smoke 通過，但 Mix/Move 有攝影機頭身份漂移，Move 另憑空出現吉他；結果仍是 candidate，沒有美術審核者的 accepted 決定。此原生 UI workflow 尚未接入 `generate.py` task/backend。完整安裝 pins、執行紀錄及輸出位置見[安裝紀錄](wan-animate-install.md)。

## 優先檢查的可驗證假說

安裝紀錄顯示，API graph 與原生 UI 範本的 positive prompt 都是 `The character is dancing in the room`；來源是女性真人頭部與手部的近景動作，機器人只出現在角色參考圖。這構成 prompt 與來源素材不匹配的可檢驗假說，可能讓動作或身份條件互相牽扯，但目前沒有對照實驗證明它造成了漂移。不得把它寫成已證實原因。

第一輪學習應先保留來源影片、角色參考圖、模型、graph、尺寸、幀數、FPS、步數、CFG、sampler、scheduler 與 seed，只替換成忠實描述參考動作及身份特徵的 prompt。避免加入來源沒有的舞蹈或道具。Mix 模式的 prompt 可要求沿用來源鏡頭與背景；Move 模式的背景應由角色參考／目標 brief 定義，不能照搬 Mix 的背景指示。首、中、末幀都要檢視身份、輪廓、衣著、手部、道具與動作是否保持。若懷疑長度影響，另以 17 幀與 33 幀做成對比較；此時仍固定其餘輸入，並在紀錄中標明唯一改動是幀數。

用至少三個 seed 評估同一 prompt 的穩定性時，應在同一模型與同一設定內比較。不同模型之間的 seed 不保證代表公平或相同的隨機條件；跨模型比較需固定其餘可比輸入，對每個模型使用相同數量的候選並明確記錄限制。這些比較是供人檢視的候選，不是自動挑選或驗收。

## SCAIL-2 評估

[SCAIL-2 官方 repository](https://github.com/zai-org/SCAIL-2)與[ComfyUI 原生整合](https://github.com/Comfy-Org/ComfyUI/pull/14373)可作為研究來源。SCAIL-2 彩色遮罩中，黑色表示該位置的背景不可見，白色表示背景可見，彩色區域表示角色區域並與動作身份對應。一般 SAM 二值遮罩不能直接視為符合需求的 SCAIL-2 彩色遮罩。

官方 `workflow_templates` 的 SCAIL-2 角色替換範本副本（本機證據：`output/animation-evaluation/SCAIL2-official-reference.json`）已下載供 ComfyUI UI 載入檢視，Git blob 為 `1fc5602b9c54b3517ed6af320ff281d5615e9306`，SHA-256 為 `2048278312063ac83b02e705b22bf52c041f53c0387ac3db47366e1bcf7b3f1d`。正式 8188 preflight 沒有缺少範本所需的 node class；依範本原始檔名比對，缺少四個檔名：`Wan2_1_VAE_bf16.safetensors`、`sam3.1_multiplex_fp16.safetensors`、`wan2.1_14B_SCAIL_2_fp16.safetensors`、`wan2.1_SCAIL_2_DPO_lora_bf16.safetensors`。這表示原始檔名未匹配，並不證明每個檔案都必須另外下載；本機另有 `wan_2.1_vae.safetensors`，其與範本所需 VAE 的相容性尚未驗證。權重／相容模型未驗證，graph 未 queue；preflight 僅為結構／節點及檔名檢查，不代表可執行或完成推論。範本使用 FP16 主權重、bf16 VAE、SAM3、UMT5、CLIP Vision、distill LoRA 與 SCAIL-2 DPO LoRA，因此不能只把主權重檔名改成 FP8 就宣稱範本可跑。細節見 template preflight（本機證據：`output/animation-evaluation/scail-template-preflight.json`）。

官方獨立環境標示 Python 3.10–3.12，本機 ComfyUI 使用 Python 3.13.9；因此以原生 ComfyUI 範本研究相依條件，不直接假設官方獨立環境可沿用。

官方 FP8 scaled 權重檔為 17,694,586,857 bytes（約 16.48 GiB），官方固定檔案連結與 SHA-256 可見[模型檔案頁](https://huggingface.co/Comfy-Org/SCAIL-2/blob/3bd725f20edad6967a65792af3017e251a5bd853/diffusion_models/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors)。權重檔大小不是執行時 VRAM 用量，故 RTX 4080 16 GB 的可行性仍未知。FP16 約 32.8 GB，對本機顯存不宜列為優先候選；MXFP8 或 NVFP4 也不能只因檔案較小就推定適合此卡。磁碟可用空間最近記錄為 46.9 GiB，尚須預留其他輔助模型、暫存與輸出空間。這些數字是研究規劃依據，不構成下載或安裝決定。

## 建議的學習次序與紀錄

建議按五階段學習，每階段都留一份可檢視產物：

1. **素材盤點：** 記下來源片段、角色參考、模式與允許變更；產物是完成的 brief。若來源、參考用途或身份錨點不明，先停止，不進入生成比較。
2. **遮罩理解：** 對照官方範本檢視 SCAIL-2 mask 黑／白／彩色語義；產物是標註語義的 mask 預覽。若只有一般二值 SAM mask 或顏色身份映射不清，停止 SCAIL-2 執行規劃。
3. **Prompt 對齊：** 逐句核對 prompt 是否描述角色參考及實際來源動作，並依 Mix／Move 分別寫鏡頭背景要求；產物是鎖定的 prompt 版本。若描述加入來源不存在的動作或道具，先修 brief。
4. **受控比較：** 固定輸入與參數，只改一項，保存實際 graph、manifest 及候選輸出；產物是逐候選測試紀錄。若技術 preflight 缺 node／模型、輸入 hash 改變，或輸出無法解碼，停止本輪並記錄，不將失敗候選混入品質比較。
5. **品質檢視與決定：** 查看首／中／末幀並對照 brief，寫下技術結果、內容缺陷與美術審核者的決定；產物是帶 candidate／accepted／rejected 狀態的驗收紀錄。若身份漂移、幻覺道具或必要錨點不符，保持 candidate 或由美術審核者決定拒絕；不得自動重送或升格。

先完成 Wan Animate 內部受控比較，再評估是否值得加入 SCAIL-2；後者需另確認彩色 mask 製作、環境相容、輔助權重、磁碟及實際 VRAM。官方提供訓練程式碼不表示本機已具備可重現的訓練環境，本機微調能力尚未驗證。

另外已有兩份僅更改 positive prompt 的 Wan Animate UI workflow 候選，供 UI 載入檢視： Mix identity candidate（本機證據：`output/animation-evaluation/WanAnimate-RTX4080-mix-identity-candidate.json`） 與 Move identity candidate（本機證據：`output/animation-evaluation/WanAnimate-RTX4080-move-identity-candidate.json`）。新 prompt 聚焦粉紅金屬、相機形機械頭、白藍針織衫、黃色長褲及來源中的頭手動作；檔案結構檢查通過，但兩份都尚未 queue 或做美術驗收。hash 與變更欄位見 template manifest（本機證據：`output/animation-evaluation/template-manifest.json`）。這些是額外候選檔，不替換已部署 workflow。

可使用[動畫 brief 模板](templates/animation-brief.md)固定需求與身份錨點，並用[動畫測試紀錄模板](templates/animation-test-record.md)逐候選追溯 graph、prompt、模型、技術檢查、內容觀察和美術審核者的決定。候選應保留 candidate 狀態，直到有明確人工驗收；不要因技術 smoke 通過或模型／prompt 看似更合適就自動標成 accepted。

## 來源與限制

- 本機證據：[Wan Animate 安裝與驗證紀錄](wan-animate-install.md)，包括實際機器、graph、節點、seed、輸出與品質缺陷。
- 外部資料：[SCAIL-2 官方 repository](https://github.com/zai-org/SCAIL-2)、[ComfyUI 整合 PR](https://github.com/Comfy-Org/ComfyUI/pull/14373)、[官方 FP8 權重固定版本頁](https://huggingface.co/Comfy-Org/SCAIL-2/blob/3bd725f20edad6967a65792af3017e251a5bd853/diffusion_models/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors)、[官方 FP16 角色替換 workflow template](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan21_scail2_character_replacement.json)。固定來源 Git blob SHA 見下方本地副本追溯資料。
- SCAIL-2 範本已取得，preflight 未發現缺失 node class；權重未下載、graph 未 queue。遮罩製作、執行速度、峰值 VRAM 與內容品質都未驗證。
- 本評估不修改模型 profiles、production task、能力目錄或既有驗收狀態。新證據與明確專案決定出現後，再更新對應文件。
