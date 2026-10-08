---
type: installation-record
status: installed-technical-pass-content-candidate
scail2: installed-technical-pass-content-candidate
last_updated: 2026-10-06
---

# Wan2.2 Animate 本機安裝與驗證

目前狀態：正式 8188 已完成安裝；固定 API templates 的 Mix17／Move17、兩段延伸 Mix61（含音訊）／Move61 與直式 384×640 Move17 已於 2026-10-06 直接 HTTP 實測（runner 出現前），live node／model preflight、queue、下載與完整解碼均技術通過。輸出有肩膀、手臂與手部變形，仍為 candidate，未獲使用者美術驗收。SCAIL-2 已於同日下載 FP8 權重並完成技術實測，見下方 SCAIL-2 段。日常操作、每次執行前的 live gate 及當次證據見[專用技能](../../../skills/comfyui-wan-animate/SKILL.md)與[操作契約](../../../skills/comfyui-wan-animate/references/comfyui-api.md)；2026-10-08 起一律用 `gameart.py run` 執行固定 template（[R2](../rules/fixed-graphs.md)），不要求瀏覽器。本頁以下保留安裝 pins 與安裝期歷史測試。輸出證據位於本機 ignored `output/`，clean clone 不含，連結不代表目前 live gate。


## 本機設定與使用入口

RTX 4080（16,376 MiB VRAM）、31.1 GiB RAM；ComfyUI 位於 `C:/Users/XU/ComfyUI`，Python 3.13.9、torch 2.13.0+cu130。使用 Animate 14B FP8 scaled 原版檔案（非 KJ v2），UMT5 FP8 text encoder 放 CPU，ComfyUI 動態顯存管理與卸載。新增模型佔 21.08 GiB；既有 UMT5 重用。

正式服務為 `http://127.0.0.1:8188`，測試用 8189 已關閉。UI workflow 已放進 `C:/Users/XU/ComfyUI/user/default/workflows/`：

- `WanAnimate-RTX4080-mix.json`：影片角色替換，含 SAM2 遮罩／背景與 relight。
- `WanAnimate-RTX4080-move.json`：參考角色動作驅動，不接來源背景／角色遮罩，停用 relight。

已部署的 UI workflow 可用於檢視和點位除錯；日常執行路由為依固定 JSON 的直接 ComfyUI API，不要求瀏覽器。Mix 需依來源重新設定 PointsEditor 點位，不能沿用官方人物點位。既有 workflow smoke 起始設定皆為 384×384、33 幀、16 FPS、6 steps、CFG 1、Euler/simple、seed 20261005，停用後續延伸段。只驗證這個小範圍，不推定較高解析度、長片、多人物、延伸段或音訊成功。

## 來源與固定版本

依 [ComfyUI 官方 Animate 指南](https://docs.comfy.org/tutorials/video/wan/wan2-2-animate)及 [官方 workflow templates](https://github.com/Comfy-Org/workflow_templates)安裝；原 UI JSON 的 Git blob 為 `ee96a29cbac97c89d961ba7a95f219b2326c2063`。

- ComfyUI 保持 `12d5279438bfefc058a269eae805ceab6047777f`。
- ComfyUI-KJNodes：`d3cfe21625e5170126ce06fbfcfe1d88108688c3`。
- ComfyUI-segment-anything-2：`0c35fff5f382803e2310103357b5e985f5437f32`。
- 既有 comfyui_controlnet_aux 保持原狀；DWPose 使用 ONNX。`yolox_l.onnx` 已 pin（見 `templates/video/wan-animate/*/template.json`）；pose estimator `dw-ll_ucoco_384.onnx` 在 2026-10-08 於 Windows 確認：`custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/dw-ll_ucoco_384.onnx`，134,399,116 bytes，sha256 `724f4ff2439ed61afb86fb8a1951ec39c6220682803b4a8bd4f598cd913b1843`（和 Hugging Face `yzd-v/DWPose` revision `1a714410…` 的 LFS sha256 一致），PR 2.2 已補 pin。DWPose 與 SAM2 下載器缺檔會自動下載，`gameart.py run <id> --preflight` 會先確認檔案在本機。
- 新增 color-matcher 0.6.0、mss 10.2.0、ddt 1.7.2、docutils 0.23；pip check 通過。optional Triton 未安裝，測試 graph 不使用該 optional node。

七個模型的 repository revision、目標路徑、bytes、SHA-256 見[模型來源](../installation/models-and-sources.md)與下載 manifest（本機證據：`output/wan-animate-install/download-manifest.json`）。所有新增檔案完成完整雜湊驗證。重用 UMT5 `umt5_xxl_fp8_e4m3fn_scaled.safetensors`：6,735,906,897 bytes；SHA-256 `c3355d30191f1f066b26d93fba017ae9809dce6c627dda5f6a66eaa651204f68`。

## 安裝期歷史實測與品質限制

使用官方機器人參考圖與官方來源影片 frames 64..96（原片 4.0..6.0625 秒），固定第一段原生 graph。API smoke 25 種 node 全部存在，正式服務的官方 UI 31 種 node 全部存在。UI 範本經結構檢查與部署，未另外透過前端按鈕執行；實際 queue 為明確映射同一原生第一段的安裝專用 API graph。這些安裝專用 smoke 與產物留在本機 ignored `output/wan-animate-install/`；clean clone 不含檔案，舊 preflight 不可作為現在的 live gate。

| 測試 | 輸出 | 整體耗時 | 5 秒抽樣 GPU 使用最大值 | 紀錄 |
|---|---|---:|---:|---|
| Mix 17，首次載入 | 384×384／17 幀／16 FPS，1.0625 秒 | 70.96 秒 | 15,002 MiB | validation（本機證據：`output/wan-animate-install/mix-validation.json`） |
| Mix 33，模型已載入 | 384×384／33 幀／16 FPS，2.0625 秒 | 25.37 秒 | 15,148 MiB | validation（本機證據：`output/wan-animate-install/mix33-validation.json`） |
| Move 33，正式服務重新啟動後 | 384×384／33 幀／16 FPS，2.0625 秒 | 76.06 秒 | 14,815 MiB | validation（本機證據：`output/wan-animate-install/move33-validation.json`） |

全部 MP4 H.264、無音訊，完整解碼核對尺寸、幀數與 CFR／PTS 通過；記憶體為包含其他應用程式的抽樣總量，非模型精確峰值。系統 RAM 抽樣最高約 29.55 GiB，餘裕有限。耗時受模型快取與來源影響。

**安裝期內容檢查有明確瑕疵：** Mix33 結尾機器人攝影機頭變成粉紅人形／精靈頭；Move33 也有同樣身份漂移，且前景憑空出現吉他。Mix17 較接近參考，但手部仍有缺陷。技術通過不等於角色一致性通過；所有輸出保持 candidate，沒有使用者 accepted 決定。不因品質瑕疵自動重送生成。

- Mix33 影片（本機證據：`output/wan-animate-install/mix33-smoke.mp4`）、末幀（本機證據：`output/wan-animate-install/mix33-frame-32.png`）。
- Move33 影片（本機證據：`output/wan-animate-install/move33-smoke.mp4`）、首幀（本機證據：`output/wan-animate-install/move33-frame-00.png`）、末幀（本機證據：`output/wan-animate-install/move33-frame-32.png`）。

## 產線界線與安裝收尾

這項能力未新增 Python client、production CLI、`generate.py` task/backend 或 capability catalog。安裝專用 `prepare_smoke.py`／`run_smoke.py` 留在 ignored output 作歷史追溯，不當成正式產線入口。可重用 API graph templates 已在 2026-10-06 以直接 HTTP 完成 Mix17／Move17 技術驗證；仍須依技能於每次工作執行前做正式 live preflight。即使通過，仍屬獨立的 template＋runner 路徑（2026-10-08 起取代直接 HTTP），不會自動成為 `generate.py` backend。舊 WanVideoWrapper complex workflow 的未接入狀態另見原 integration 文件。

已重跑影片 detector，既有 h3／wan 仍 available，原預設 h3 保留；該 detector 不涵蓋 Animate。安裝後 portable verification：43 passed、0 failed；pip check 無依賴衝突。此回歸檢查不替代上方 Animate smoke。正式節點 preflight（本機證據：`output/wan-animate-install/production-node-preflight.json`）、portable report（本機證據：`output/wan-animate-install/portable-final.txt`）。

## SCAIL-2 安裝與實測（2026-10-06）

使用者於 2026-10-06 同意下載並實測。以固定 revision 下載三個檔案並逐一核對 SHA-256，合計 20,667,070,257 bytes（19.25 GiB）：SCAIL-2 14B FP8 scaled 主模型與 DPO LoRA（`Comfy-Org/SCAIL-2` @ `fe3c728bc793ba21ca674688f822afb709ad44fb`）、SAM3.1 multiplex（`Comfy-Org/sam3.1` @ `7bb8374780a725b4353ed31f3a9395c9742b5621`）。UMT5、CLIP Vision H、LightX2V LoRA 與 VAE 重用 Wan Animate 既有檔案；官方範本寫的 `Wan2_1_VAE_bf16` 改用本機 `wan_2.1_vae.safetensors`，實測可解碼。ComfyUI 版本不變（`WanSCAILToVideo` 等節點為 core 內建），未新增 custom node 或 Python 套件。下載腳本與記錄在 ignored `output/scail2-install/`。

替換 33 幀、替換 61 幀（兩段延伸）、動畫 33 幀三次 queue 全部技術通過，RTX 4080 16 GB 可執行 384×384。身份一致性比 Wan Animate 好，但兩種模式都變成全身構圖、未貼合來源近景鏡頭，內容仍為 candidate。檔案清單、模式、動態欄位與實測細節見 [SCAIL-2 reference](../../../skills/comfyui-wan-animate/references/scail2.md)；官方研究來源仍見[動畫評估筆記](animation-evaluation.md)。

## 新增能力 checklist 適用性

- 安裝：影片模型／node／runtime 完成，pins 與 hash 留存；圖片與本機新工具安裝項目不適用。
- 程式與部署：未修改 production facade/package、catalog、profile 或新增 task，相關同步／golden fixture 項目不適用；安裝專用 helper 已語法檢查及實際執行。原生 UI workflow 已部署並檢查 node id、pos、link 端點與 last_link_id。
- 實測：Mix17／Mix33／Move33 實際 queue，輸出與解碼契約通過；無音訊，未測音訊保留。抽幀已檢查且記錄品質缺陷，未標記人工接受。
- 文件：安裝、模型來源、video-gen、face-swap integration、AGENTS、知識路由與 tested-versions 已更新；後續已補專用技能與 API templates，不將此路徑宣稱為 `generate.py` 正式 task。
- 收尾：正式 8188 已重啟、31-node preflight pass、detector 保留 h3，portable 43/0，pip check pass；已移除本次完成下載留下的單一 .part 檔。
- 2026-10-06 追加：延伸段／SCAIL-2 templates 加入專用技能，live schema preflight、實際 queue 與完整解碼通過；未改 production package、profile 或 capability catalog。
