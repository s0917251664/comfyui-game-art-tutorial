---
type: rule
id: R2
status: current
---
# R2 只用已登記的固定流程，不臨場組 graph

## 規則

1. ComfyUI 生成只走已登記的執行方式：`generate.py` 的固定 task、版控的固定 API-format JSON（只替換對應 reference 明列的占位欄位），以及 repo 內的 server-side custom node。這三種是不同的執行方式，不能把 CLI 假寫成 API。
2. 不為單次需求臨場組、改接或拼接 ComfyUI graph 與節點，也不臨場改用 API、換模型或補不存在的旗標。
3. 缺能力時如實說明目前做不到，不自動換引擎，也不用相似的 graph 或 task 頂替。需要新能力時，照 [新增能力清單](../maintenance/new-capability-checklist.md) 走。
4. 研究用的一次性腳本（例如 `experiences/*/scripts/`）不是產線入口，不可當工具呼叫，也不要從裡面衍生新功能。
5. 發現文件和實作衝突時，先核對實作並修正說明，不要為了符合舊文件而改 graph。

> **預定變更（2026-10-07 已決定，D8）**：template runner（`gameart.py run`）完成後，第 1 點會改為「固定 API JSON 一律透過 template＋runner 執行」，手動 HTTP 只留作除錯。runner 合併前，仍依目前第 1 點執行。見 [ADR](../decisions/2026-10-07-phase2-template-runner.md)。

## 適用範圍

所有 ComfyUI 路線（圖片、影片、Wan Animate／SCAIL-2、SAM3 追蹤、換臉、Video Layers）。平台原生圖片工具與本機像素工具不組 ComfyUI graph，不受第 1、2 點限制，但同樣適用第 3 點。
