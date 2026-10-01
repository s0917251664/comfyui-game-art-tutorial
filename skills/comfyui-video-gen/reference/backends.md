# 影片 backend(實作層,不是 task 契約)

此舊 reference 保留相容索引；目前 canonical 文件是[影片知識庫](../../../docs/knowledge/video/README.md)。

## 現在誰接得上什麼

backend 能力表與映射：[查 canonical 能力矩陣](../../../docs/knowledge/video/README.md#backend模型與-runtime)。可用性仍依本機 `video_capabilities.json`。

## Capability config 與 fail-fast

偵測器範圍、執行前 preflight 及缺模型/node 時的 fail-fast：[查 runtime 契約](../../../docs/knowledge/video/README.md#backend模型與-runtime)。

## 這台機器對應的檔(裝機用,不要寫進 CLI)

模型檔名映射、歷史 bake-off 與機器限制：[查 backend/model runtime](../../../docs/knowledge/video/README.md#backend模型與-runtime)。這些名稱供維護使用，不是 CLI 選項或安裝狀態保證。
