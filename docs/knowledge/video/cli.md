---
type: reference
status: active
---

# 影片 task 與 template 對照

旗標與必要輸入**不在文件裡**：生成 task 查 `generate.py <task> --help`，template 查 `gameart.py run show <id>`。這頁只說 task 背後走哪份 template，以及哪些 task 是本機處理。生成 task 都要明確帶 `--config` 或 `--comfy-url`、`--output-dir`；`--backend` 只有能力設定檔有 `default_backend` 才可省略；一般 timeout 建議 1800 秒。不要為單次需求改 graph 或臆造旗標。

## 生成 task（`generate.py`，由 runner 填 template）

| task | template id | 備註 |
|---|---|---|
| `img2video`、`fx_loop`、`transition`、`clip_extend`、`camera_move`（Wan） | `video/wan/img2video` | 同一份 graph，task 不同在驗收與輸出包裝；Wan 沒有尾幀能力、無聲 |
| 同上（H3，沒有尾幀） | `video/h3/img2video` | |
| 同上（H3，有尾幀） | `video/h3/img2video-last` | `transition` 與 `fx_loop` 鎖首尾；規則見 [R3](../rules/idle-anchoring.md) |
| `pose_drive` | `video/{h3\|wan}/pose-drive-{canny\|pose\|depth}` | 角色靜幀的姿勢與朝向要貼近動作片首幀 |
| `character_video` | `video/h3/character-video-{參考圖張數}` | 一到九張角色參考 |
| `video_inpaint` | `video/wan-vace/inpaint` | 遮罩約定、輸出與限制見 [vfx-tools](vfx-tools.md)；遮罩由 [SAM3 追蹤](sam3-tracking.md) 產生。runner 不寫影片 sidecar，不支援 `--resume`，失敗時看 `run.result.json` 並用新的 `--name` 重跑 |

預設 `img2video` 只留 MP4，`fx_loop` 預設抽 PNG 序列；其他 task 要抽幀須明確要求。

## 本機處理（不連 ComfyUI）

- `video_concat`：至少兩支 24 FPS MP4 與順序。尺寸或長寬比不一致、混合有聲與無聲預設都拒絕；要 `fit`／`fill`／`stretch` 或 `drop`／`silence-missing` 須事先向使用者說明差異並取得選擇，不靜默裁切、拉伸或丟音訊。
- `video_composite`：只適合本產線輸出的乾淨純綠幕前景（chroma key，不是語意分割）；只保留前景音軌。細節與限制見 [README](README.md) 的 task 段。

## 獨立路線

Wan Animate、SCAIL-2、SAM3 追蹤不是 `generate.py` task，用 `gameart.py run`（見 [取捨](wan-animate-choice.md)、[SAM3 追蹤](sam3-tracking.md)）。Video Layers（SAM2 備援與 2D 圖層合成）見 [layers](layers.md)。
