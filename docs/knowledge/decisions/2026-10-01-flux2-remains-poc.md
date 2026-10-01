---
type: adr
status: accepted
date: 2026-10-01
---
# ADR：FLUX.2 維持獨立實驗路線

## 決策

保留 `flux2_concept` 和 `flux2_edit` 作為明確選用的 FLUX.2 Klein PoC，不取代 SDXL 基線，也不併入 SDXL/SD1.5 image profile 或其他 SDXL add-on。

## 證據與範圍

2026-09-01 XU-Nano-PC、RTX 4080 16,376 MiB VRAM 的單次比較中，FLUX.2 distilled 純文字概念圖耗時 7.57 秒，材質較乾淨但 `POTION` 拼成 `PENTION`；FLUX.2 base 編輯耗時 27.83 秒，主體／姿勢／構圖保留但臉部細節漂移。比較指令、模型 hash 與原始輸出見 repo evidence path: `docs/tested-versions.md`，按 task 整理的觀察見 [FLUX.2 經驗](../experiences/flux2-and-structure-lock-observations.md)。

## 後續升級條件

單次測試不構成全平台品質或穩定性證據。若要討論晉升主線，須先有固定 prompt／輸入的品質比較、速度與 VRAM、多提示詞、多參考圖、長時間連續執行與 OOM 壓力證據，再依新增能力流程決定；此 ADR 不授權自動換模型或改生成預設。
