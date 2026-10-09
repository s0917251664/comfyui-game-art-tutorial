# 2026-10-07 VFX 研究用量測腳本（不是產線入口）

這些是研究時臨時寫的一次性腳本，用來產生 [results.md](../results.md) 和 [vfx-tools.md](../../../../video/vfx-tools.md) 裡的數據與對照圖。保留在這裡只為了可以追溯和重現。

- 路徑都寫死在當時的 `output/experiments/...`，`REPO = Path(__file__).parents[...]` 也是依照原本在 `output/` 的位置計算。要重跑時，先把腳本放回原位置，或手動修改路徑。
- 部分腳本裡直接組了 ComfyUI graph（`run_vace.py`、`run_sam3*.py`），那是研究當下的做法。**正式入口**是：
  - SAM3 追蹤：`skills/comfyui-video-layers/assets/sam3-track-*.json`（固定 API graph；PR 2.1 起搬到 `templates/video/sam3/track-{mask,text}/graph.api.json`，位元組不變。本資料夾的腳本保留當時的路徑，重跑前要改成新位置）
  - 遮罩局部重繪：`generate.py video_inpaint`
  - 道具母版貼回：`gameart.py vfx prop-paste`
  - 其他去背、打包、量測：`gameart.py vfx ...`
- 不要把這些腳本當工具呼叫，也不要從這裡衍生新功能；新能力請照 `docs/knowledge/maintenance/new-capability-checklist.md` 的流程做。

| 腳本 | 用途 |
|---|---|
| `run_generation.sh` | 需求 1／3 的 H3／Wan 生成批次（呼叫既有 `generate.py` task） |
| `run_req1.py`、`run_req1_c.py` | 去背方法量測與兩組已知 alpha 對照 |
| `run_req2.py` | 本機遮罩換色 vs Wan canny 重畫的量測 |
| `run_vace.py` | VACE 1.3B keep／replace × 3 seed 研究 graph |
| `run_req3.py` | Idle 首幀、尾幀、接縫量測 |
| `run_sam3.py`、`run_sam3_mask.py` | SAM3 文字／遮罩起手追蹤比較 |
| `run_scail2_animate.py` | SCAIL-2 動畫模式比較（套用固定範本） |
