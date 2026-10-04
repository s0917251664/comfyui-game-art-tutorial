# ComfyUI ReActor graph 與執行契約

`face_swap.py` 會透過既有 `generate` facade 呼叫本機 ComfyUI API。換臉、偵測與模型運算只由 server 上的 `ReActorFaceSwap` node 執行；client 不 import ReActor core 或 ONNX runtime，也不載入模型。wrapper 的 preflight 是本工具獨立 gate，不會新增 `generate.py` task 或改動 `video_capabilities.json` backend catalog。

## 固定 graph

每批最多 8 張影格：`LoadImage` 載入 donor 與逐幀輸入、`ImageBatch` 組成 batch、`ReActorFaceSwap` 使用 `inswapper_128.onnx` 與 `retinaface_resnet50`、face restoration 固定為 none；輸出分別經 `SaveImage` 與 `CreateVideo`/`SaveVideo`。上傳前 `preflight` 會讀即時 `/object_info`，核對所有節點與所需輸入，並驗證 swap model 和 no-restorer 選項仍存在；不符合即停止。

wrapper 將來源片段解碼並以 lossless PNG 準備影格，上傳至 ComfyUI；ComfyUI 回傳影格及每批影片。client 核對輸出批次影格數與尺寸，再組裝整段候選影片及音訊。這裡的「本機媒體處理」只含解碼、PNG 準備、結果檢查、H.264/AAC 編碼與組裝，不含模型推論。

`--face-index` 範圍 0–7，表示 ReActor 每幀按大至小排序的人臉索引；它不維持跨幀身份追蹤。索引排序變化可能令不同幀選到不同人，需人工檢查。`--batch-size` 範圍 1–8，預設 4。

## 接入隔離

影片來源能力快照不宣告此 wrapper backend。使用者明確要求換臉時，按本技能獨立執行 preflight；ComfyUI 節點缺失、模型缺失、pin 不符或 graph schema 改變，都必須在 upload/queue 前停止。不得由 H3/Wan available 推論 ReActor 可用。

停用 standalone ReActor Core prototype 及其歷史 pin/smoke 見 [local-tool.md](local-tool.md)；Wan Animate 另見 [integration.md](integration.md)。
