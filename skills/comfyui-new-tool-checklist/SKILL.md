---
name: comfyui-new-tool-checklist
description: 新增或擴充圖片、影片與本機工具能力時，依受影響能力類型執行完整安裝、程式、實測及文件檢查。
---

# 新增產線能力

當新增模型、task、backend、本機工具，或替既有 task 增加參數時使用。純文件修正不套用完整能力檢查。

先從[總工具庫](../../docs/knowledge/TOOLS.md)確認相關能力，再讀 [維護知識索引](../../docs/knowledge/maintenance/README.md) 和 [新增能力檢查流程](../../docs/knowledge/maintenance/new-capability-checklist.md)，辨認本次屬於圖片、影片、本機工具中的哪一類，可同時套用多類。只執行適用的項目；跳過時記明原因。圖片沿用既有 profile 與 graph 契約，影片沿用 capability/backend 契約，本機工具檢查自己的依賴、CLI、輸出和部署範圍。不要新增不必要的 workflow 或依賴。

完成適用的程式、部署、文件與實測項目；實機條件不具備時明確留下未驗證狀態。離線檢查、語法檢查或產生檔案都不能代替模型／畫面人工驗收，也不得將設定檔標成已驗證。
