---
type: installation-record
status: installed-technical-pass-content-candidate
last_updated: 2026-10-06
---

# Wan2.2 Animate 本機安裝與驗證

目前狀態：正式 8188 已完成安裝；固定 API templates 的 Mix17／Move17 已直接 HTTP 實測，live node／model preflight、queue、下載與完整解碼均技術通過。輸出有肩膀、手臂與手部變形，仍為 candidate，未獲使用者美術驗收；17 幀結果不證明 33 幀穩定。日常操作、每次執行前的 live gate 及當次證據見[專用技能](../../../skills/comfyui-wan-animate/SKILL.md)與[API reference](../../../skills/comfyui-wan-animate/references/comfyui-api.md)，採直接 HTTP，不要求瀏覽器或新增 client／CLI。本頁以下保留安裝 pins 與安裝期歷史測試。輸出證據位於本機 ignored `output/`，clean clone 不含，連結不代表目前 live gate。


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
- 既有 comfyui_controlnet_aux 保持原狀；DWPose 使用 ONNX。
- 新增 color-matcher 0.6.0、mss 10.2.0、ddt 1.7.2、docutils 0.23；pip check 通過。optional Triton 未安裝，測試 graph 不使用該 optional node。

七個模型的 repository revision、目標路徑、bytes、SHA-256 見[模型來源](../installation/models-and-sources.md)與[下載 manifest](../../../output/wan-animate-install/download-manifest.json)。所有新增檔案完成完整雜湊驗證。重用 UMT5 `umt5_xxl_fp8_e4m3fn_scaled.safetensors`：6,735,906,897 bytes；SHA-256 `c3355d30191f1f066b26d93fba017ae9809dce6c627dda5f6a66eaa651204f68`。

## 安裝期歷史實測與品質限制

使用官方機器人參考圖與官方來源影片 frames 64..96（原片 4.0..6.0625 秒），固定第一段原生 graph。API smoke 25 種 node 全部存在，正式服務的官方 UI 31 種 node 全部存在。UI 範本經結構檢查與部署，未另外透過前端按鈕執行；實際 queue 為明確映射同一原生第一段的安裝專用 API graph。這些安裝專用 smoke 與產物留在本機 ignored `output/wan-animate-install/`；clean clone 不含檔案，舊 preflight 不可作為現在的 live gate。

| 測試 | 輸出 | 整體耗時 | 5 秒抽樣 GPU 使用最大值 | 紀錄 |
|---|---|---:|---:|---|
| Mix 17，首次載入 | 384×384／17 幀／16 FPS，1.0625 秒 | 70.96 秒 | 15,002 MiB | [validation](../../../output/wan-animate-install/mix-validation.json) |
| Mix 33，模型已載入 | 384×384／33 幀／16 FPS，2.0625 秒 | 25.37 秒 | 15,148 MiB | [validation](../../../output/wan-animate-install/mix33-validation.json) |
| Move 33，正式服務重新啟動後 | 384×384／33 幀／16 FPS，2.0625 秒 | 76.06 秒 | 14,815 MiB | [validation](../../../output/wan-animate-install/move33-validation.json) |

全部 MP4 H.264、無音訊，完整解碼核對尺寸、幀數與 CFR／PTS 通過；記憶體為包含其他應用程式的抽樣總量，非模型精確峰值。系統 RAM 抽樣最高約 29.55 GiB，餘裕有限。耗時受模型快取與來源影響。

**安裝期內容檢查有明確瑕疵：** Mix33 結尾機器人攝影機頭變成粉紅人形／精靈頭；Move33 也有同樣身份漂移，且前景憑空出現吉他。Mix17 較接近參考，但手部仍有缺陷。技術通過不等於角色一致性通過；所有輸出保持 candidate，沒有使用者 accepted 決定。不因品質瑕疵自動重送生成。

- [Mix33 影片](../../../output/wan-animate-install/mix33-smoke.mp4)、[末幀](../../../output/wan-animate-install/mix33-frame-32.png)。
- [Move33 影片](../../../output/wan-animate-install/move33-smoke.mp4)、[首幀](../../../output/wan-animate-install/move33-frame-00.png)、[末幀](../../../output/wan-animate-install/move33-frame-32.png)。

## 產線界線與安裝收尾

這項能力未新增 Python client、production CLI、`generate.py` task/backend 或 capability catalog。安裝專用 `prepare_smoke.py`／`run_smoke.py` 留在 ignored output 作歷史追溯，不當成正式產線入口。可重用 API graph templates 已在 2026-10-06 以直接 HTTP 完成 Mix17／Move17 技術驗證；仍須依技能於每次工作執行前做正式 live preflight。即使通過，仍屬本機獨立 API 路徑，不會自動成為 `generate.py` backend。舊 WanVideoWrapper complex workflow 的未接入狀態另見原 integration 文件。

已重跑影片 detector，既有 h3／wan 仍 available，原預設 h3 保留；該 detector 不涵蓋 Animate。安裝後 portable verification：43 passed、0 failed；pip check 無依賴衝突。此回歸檢查不替代上方 Animate smoke。[正式節點 preflight](../../../output/wan-animate-install/production-node-preflight.json)、[portable report](../../../output/wan-animate-install/portable-final.txt)。

## SCAIL-2 追加參考（未安裝）

Steve 追加提出 SCAIL-2「加入參考」方向，未要求安裝。官方 [zai-org/SCAIL-2](https://github.com/zai-org/SCAIL-2) 說明其端到端角色動畫、角色替換與多角色參考能力；遮罩以黑、白及彩色區域表達不同語義，不能直接當成本專案一般二值遮罩理解。官方獨立環境要求 Python 3.10–3.12。

安裝期曾記錄本機可見 `WanSCAILToVideo`／`SCAIL2ColoredMask` 節點名稱，但當時節點與工作流未驗證。後續 2026-10-06 範本 preflight 確認所需 node class 存在，卻發現四個精確模型檔名未匹配；權重／相容模型仍未驗證，graph 未 queue、未推論。詳見[動畫評估筆記](animation-evaluation.md)。RTX 4080 16 GB 是否足以執行未知；節點 preflight 不代表可執行。此項不在 Wan Animate smoke 範圍。

另見[官方權重](https://huggingface.co/zai-org/SCAIL-2)與[ComfyUI 原生整合 PR](https://github.com/Comfy-Org/ComfyUI/pull/14373)。參考項目不構成安裝或 16 GB 可行性驗證。

## 新增能力 checklist 適用性

- 安裝：影片模型／node／runtime 完成，pins 與 hash 留存；圖片與本機新工具安裝項目不適用。
- 程式與部署：未修改 production facade/package、catalog、profile 或新增 task，相關同步／golden fixture 項目不適用；安裝專用 helper 已語法檢查及實際執行。原生 UI workflow 已部署並檢查 node id、pos、link 端點與 last_link_id。
- 實測：Mix17／Mix33／Move33 實際 queue，輸出與解碼契約通過；無音訊，未測音訊保留。抽幀已檢查且記錄品質缺陷，未標記人工接受。
- 文件：安裝、模型來源、video-gen、face-swap integration、AGENTS、知識路由與 tested-versions 已更新；後續已補專用技能與 API templates，不將此路徑宣稱為 `generate.py` 正式 task。
- 收尾：正式 8188 已重啟、31-node preflight pass、detector 保留 h3，portable 43/0，pip check pass；已移除本次完成下載留下的單一 .part 檔。SCAIL-2 只記參考，未安裝。
