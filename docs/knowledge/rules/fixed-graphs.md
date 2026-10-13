---
type: rule
id: R2
status: current
---
# R2 交付走已登記的固定流程；新的節點組合先實驗再進產線

## 規則

1. ComfyUI 生成只走已登記的執行方式：`generate.py` 的固定 task、`templates/` 的固定 API graph，以及 repo 內的 server-side custom node。這三種是不同的執行方式，不能把 CLI 假寫成 API。
   - 固定 API graph 一律透過 template＋runner 執行：`gameart.py run <template> --preflight` 檢查，再用 `gameart.py run <template>` 實際執行。只填 `template.json` 宣告的 slot 與 option；runner 會核對 graph hash、占位欄位與差異白名單，並寫出 `run.result.json`。
   - 手動呼叫 ComfyUI HTTP（自己上傳、`POST /prompt`）只用來除錯 runner 本身，不是產線執行方式，結果也不能代替 `run.result.json` 當證據。
   - 新的固定 graph 要先做成 template（見 [templates/README](../../../templates/README.md) 的「修改」），不要在技能文件裡另寫一套送出步驟。
2. 交付用的生成（要進成品、要當證據的輸出）不臨場組、改接或拼接 graph，也不臨場改用 API、換模型或補不存在的旗標。理由是可重現：同一份 template、同樣的 slot 值，要得到同樣的 graph。
3. 這不表示節點組合不能變。現有 template 做不好時，要主動想：在什麼狀況下，既有節點重新排列組合可以變成新的做法。例：多視角轉 3D 前面接 BiRefNet 去背（[`3d/hunyuan3d-2mv/multiview-cutout`](../../../templates/3d/hunyuan3d-2mv/multiview-cutout/README.md)）；3D 灰模搭配物件設計圖重新上色。做法：
   - 先說清楚遇到的狀況、要解的問題、打算怎麼組，標明是實驗。
   - 在 ComfyUI 實驗（UI 或一次性 graph 都可以）。輸出放本機 `output/`，記下節點組合、參數、結果與失敗點。實驗輸出是候選，不當交付證據。
   - 實驗成功、使用者確認要納入後，照 [擴充協議](../maintenance/extension-protocol.md) 做成 template，才算進入產線。
4. 缺能力時如實說明目前做不到，不自動換引擎，也不拿相似的 graph 或 task 頂替後當成已完成；可以提出第 3 點的實驗方案，由使用者決定。下載模型、安裝節點仍要先取得同意。其他新能力照 [新增能力清單](../maintenance/new-capability-checklist.md)。
5. 研究用的一次性腳本（例如 `experiences/*/scripts/`）不是產線入口，不可當工具呼叫。裡面驗證過的做法要進產線，照擴充協議重新做成 template，不直接搬腳本。
6. 發現文件和實作衝突時，先核對實作並修正說明，不要為了符合舊文件而改 graph。

第 1 點的 template＋runner 規定自 2026-10-08 起生效（D8，見 [ADR](../decisions/2026-10-07-phase2-template-runner.md)）。之前「用 HTTP 工具直接送固定 JSON」的做法已停用。

## 適用範圍

所有 ComfyUI 路線（圖片、影片、Wan Animate／SCAIL-2、SAM3 追蹤、Video Layers）。平台原生圖片工具與本機像素工具不組 ComfyUI graph，不受第 1、2 點限制，但同樣適用第 3 點。
