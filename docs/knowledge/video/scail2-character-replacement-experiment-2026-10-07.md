---
type: experiment-record
status: technical-pass-content-candidate
last_updated: 2026-10-07
---

# SCAIL-2 角色替換實驗紀錄 2026-10-07

## 範圍

使用者提供的特攝變身片段（45 秒、1920×1080、60 FPS）把真人鏡頭主角換成使用者本人。只處理前 12 秒的四個真人鏡頭，鎧甲出現後保留原片。所有輸出放在 ignored `output/*-kabuto-wan-animate/`，為 candidate 狀態，使用者未做最終驗收。不收錄任何影片截圖進 repo。

## 試過的四種做法與觀察

| 做法 | 技術堆疊 | 觀察 |
|---|---|---|
| **Wan Animate Mix 整畫面** | 640×352 | 照原片鏡頭與動作執行，但臉不夠像 |
| **SCAIL-2 整畫面 第一輪** | 640×352，SAM3「man」，大頭照參考圖 | 臉最像，但遠景/背影鏡頭被畫成大頭特寫、怪人消失 |
| **SCAIL-2 只換頭 + 逐幀對齊貼回 + ReActor 換臉** | 頭部裁切 512×512，SAM3「head」，依頭部遮罩逐幀縮放對齊，ReActor | 道具與特效完全保留原片，但 SCAIL-2 頭的位置/大小偏移、手擋臉鏡頭無法貼頭、側臉有原演員髮尾疊影；臉的相似度需靠換臉補 |
| **SCAIL-2 整畫面 v3** | 832×448，SAM3「man with black hair」，構圖對齊的縮放參考圖 | 遠景恢復全身構圖、怪人與飛過的道具保留、臉像；但道具特效是重畫的（腰帶變普通皮帶、鎧甲細節少），背影鏡頭開頭幾幀方向不一致 |

## 其他要點

- 用 insightface buffalo_l 的 SCRFD 逐幀偵測人臉來決定只重算有臉的幀。
- FLUX.2 edit 換外套時臉有漂移（與既有觀察一致）。
- 顯存抽樣：832×448 最高 15,088 MiB；640×352 Wan Mix 17 幀最高 14,911 MiB（皆含其他程式）。

## 限制

單一素材、單一 seed、單次觀察，不是受控比較。這些是本機 output 內的一次性實驗腳本，不是產線工具。

## 連結

- [SCAIL-2 reference](../../../skills/comfyui-run/references/comfyui-wan-animate/references/scail2.md)
- [2026-10-06 實驗紀錄](wan-animate-scail2-experiments-2026-10-06.md)
- [換臉技能](../../../skills/comfyui-run/references/comfyui-face-swap-workflow/README.md)
