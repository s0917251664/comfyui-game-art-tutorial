---
type: rule
id: R2
status: current
---
# R2 只用已登記的固定流程，不臨場組 graph

## 規則

1. ComfyUI 生成只走已登記的執行方式：`generate.py` 的固定 task、`templates/` 的固定 API graph，以及 repo 內的 server-side custom node。這三種是不同的執行方式，不能把 CLI 假寫成 API。
   - 固定 API graph 一律透過 template＋runner 執行：`gameart.py run <template> --preflight` 檢查，再用 `gameart.py run <template>` 實際執行。只填 `template.json` 宣告的 slot 與 option；runner 會核對 graph hash、占位欄位與差異白名單，並寫出 `run.result.json`。
   - 手動呼叫 ComfyUI HTTP（自己上傳、`POST /prompt`）只用來除錯 runner 本身，不是產線執行方式，結果也不能代替 `run.result.json` 當證據。
   - 新的固定 graph 要先做成 template（見 [templates/README](../../../templates/README.md) 的「修改」），不要在技能文件裡另寫一套送出步驟。
2. 不為單次需求臨場組、改接或拼接 ComfyUI graph 與節點，也不臨場改用 API、換模型或補不存在的旗標。
3. 缺能力時如實說明目前做不到，不自動換引擎，也不用相似的 graph 或 task 頂替。需要新能力時，照 [新增能力清單](../maintenance/new-capability-checklist.md) 走。
4. 研究用的一次性腳本（例如 `experiences/*/scripts/`）不是產線入口，不可當工具呼叫，也不要從裡面衍生新功能。
5. 發現文件和實作衝突時，先核對實作並修正說明，不要為了符合舊文件而改 graph。

第 1 點的 template＋runner 規定自 2026-10-08 起生效（D8，見 [ADR](../decisions/2026-10-07-phase2-template-runner.md)）。之前「用 HTTP 工具直接送固定 JSON」的做法已停用。

## 適用範圍

所有 ComfyUI 路線（圖片、影片、Wan Animate／SCAIL-2、SAM3 追蹤、換臉、Video Layers）。平台原生圖片工具與本機像素工具不組 ComfyUI graph，不受第 1、2 點限制，但同樣適用第 3 點。
