---
type: adr
status: accepted
date: 2026-10-08
---
# ADR：物件組裝改本機 Pillow，BiRefNet 去背留在 repo

## 背景

`comfyui_design.py` 的 scene、sheet、pattern 原本組 ComfyUI Core graph，上傳圖片再排隊。`vfx birefnet-alpha` 則呼叫 repo 內的 `benchmark_birefnet`；那個腳本不在部署清單。

## 決定

1. **scene、sheet、pattern 改為純 Pillow 合成。** 不組 ComfyUI graph，不 upload，不 queue。CLI 仍是 `gameart.py design` 的這三個子命令。`--comfy-url`、`--config`、`--timeout` 仍接受，但不使用。幾何沿用原本的規則：物件依 alpha 外框裁切，等比縮放（RGB 用 LANCZOS，alpha 用 BILINEAR）後置中；畫布縮放沿用中心裁切。合成權重是來源 alpha。輸出不透明 RGB 與 manifest（`model_generation` 為 false）。不透明物件仍拒絕，而且不會去碰 ComfyUI。標題仍只接受可列印 ASCII。
2. **`vfx birefnet-alpha` 維持現狀。** 只能從 repo 的 tools_src 執行，不會被 deploy 帶出去。它繼續透過 `benchmark_birefnet` 跑，不部署那個 benchmark，也不改成 ComfyUI graph。不改權重或演算法。

## 後果

技能、教學、工具總表與相關頁已改成純 Pillow 現況：不組 graph、不 upload、不 queue。`vfx birefnet-alpha` 仍只在 repo 執行，benchmark 不進部署。`gameart.py vfx` 的子命令不變。2026-10-03 的 Core graph 實測留在流程評估頁，只當當時紀錄。
