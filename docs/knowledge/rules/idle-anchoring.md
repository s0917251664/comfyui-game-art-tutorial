---
type: rule
id: R3
status: current
evidence: ../experiences/2026-10-07-vfx-research/design.md
---
# R3 角色動作的 Idle 錨定

同一角色的一組遊戲動作（Idle、Attack、Win、Fail、Hit…）要能從同一張已驗收的 Idle 圖開始、需要時回到 Idle。

## 哪些 task 會鎖首／尾幀

| task／backend | 首幀 | 尾幀 | 說明 |
|---|---|---|---|
| `img2video` H3 | ✅ | ✗ | 首幀是條件 token，每一步重新注入，不參與去噪；強引導，但不是逐像素相同 |
| `img2video` Wan 5B | ✅ | ✗ | latent 直接鎖住；但實測 2 秒內角色就跑掉，不建議用於角色動作 |
| `fx_loop` H3 | ✅ | ✅（同一張） | 會把 `--image` 同時當首幀和尾幀 |
| `transition` H3 | ✅ `--start` | ✅ `--end` | `--start` 和 `--end` 可以是同一張 Idle |
| `pose_drive`、`character_video` | ✗ | ✗ | 圖片只當身份參考，不保證第一幀 |

## 規則

1. 所有動作的第一幀都用已驗收的 Idle 圖，所以只用上表能鎖首幀的 H3 task。
2. Idle 循環用 `fx_loop --backend h3 --image <Idle>`。
3. 要回到 Idle 的動作（Attack、Win、Fail、Hit 等）用 `transition --backend h3 --start <Idle> --end <Idle>`，prompt 寫清楚「中段動作＋回到完全相同的站姿與位置＋鏡頭不動」。
4. 只出不回的動作（離場、倒地）用 `img2video --backend h3`。
5. Idle 圖先補邊到和生成畫布相同的比例（長邊 768、對齊 32）。H3 的首幀是拉伸到畫布、尾幀是置中裁切，比例不同時首尾會有幾何差異。
6. 驗收時跑 `gameart.py vfx loop-metrics --video <mp4> --reference <Idle.png> --key 00FF00 --output-dir <新資料夾>`，看首幀 vs Idle、尾幀 vs 首幀和接縫比（只計角色範圍）。暫定提醒門檻（ROI MAE）：首幀 vs Idle > 15，或尾幀 vs 首幀 > 9 時要重點看片。這只用來找可疑的片，不能自動判定接受（見 [R1](candidate-review.md)）。
7. 首尾鎖成同一張時，循環播放要去掉重複的最後一幀，交付說明要寫清楚。

## 證據

2026-10-07 實測數字見 [vfx-tools §3](../video/vfx-tools.md#3-idle-起始幀與首尾呼應)，研究過程見 [VFX 研究](../experiences/2026-10-07-vfx-research/design.md)。動作表與交付流程見 [animation/workflow.md](../animation/workflow.md)。
