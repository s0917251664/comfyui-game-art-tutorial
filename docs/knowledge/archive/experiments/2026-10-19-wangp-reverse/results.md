# WanGP 逆向研究：第一輪實測結果（E1–E6）

日期：2026-10-19｜平台：windows-cuda（RTX 4080 16 GB），ComfyUI 0.34.0｜設計：[design.md](design.md)｜腳本：[scripts/](scripts/)

輸出都在 `output/experiments/wangp-reverse-20261019/<實驗>/`（不進 git），每個實驗資料夾有 `compare.jpg`（每支 6 張等距關鍵幀）與 `metrics.json`。

**做法**：`ab_run.py` 載入正式 template 後，在記憶體裡改參數或加節點，再交給正式 runner 跑，所以 preflight、上傳、技術檢查、`run.result.json` 都照常產生。改了什麼記在每個 run 的 `experiment_patch.json`。template 檔案沒有改動。

所有輸出都是 candidate。下面的判斷依據指標和關鍵幀，每組只有 2 個 seed，只能當訊號，不能當定論。

## 總表

| # | 實驗 | 結論 | 動作建議 |
|---|---|---|---|
| E1 | H3 取樣器 res_multistep vs euler | 看不出差異 | 維持 res_multistep |
| E2 | Wan 5B：shift 8/20 步 vs shift 5，20/30/50 步 | shift 5 在 seed 3001 壞了兩支；步數加多沒有好處 | 維持 shift 8、20 步 |
| E3 | VACE 1.3B：CFG 6/20 步 vs CFG 5，20/30 步 | 同 seed 下幾乎相同；30 步多花 32% 時間 | 維持 CFG 6、20 步 |
| E4 | VACE 參考圖注入 | **replace 模式效果明顯：錘子回到母版設計** | 提案做成 template |
| E5 | H3「鏡頭靜止」獨立句型 | 基準組本來就沒推近，驗證不了 | 用 3 秒原條件補測 |
| E6 | Animate 蒸餾 6 步：euler vs uni_pc | 差不多；seed 43 兩種都不穩 | 維持 euler |

**總結**：WanGP 的預設參數（E1、E2、E3、E6）是針對它自己的解析度和非蒸餾路線調的，搬到我們的設定沒有帶來改善，E2 甚至變差。有價值的是「做法」，也就是 E4 的參考圖注入。

## E1　H3 取樣器

`video/h3/img2video-last`，首尾都是 `skye_idle_square_1024.png`，768×768、56 幀，prompt 沿用 vfx-research req3 的 idle 錨定攻擊，seed 3002、3003。

| run | 耗時 s | 相鄰幀差 | 首／末幀 vs 原圖 | 前景高度最小／最大比 | 碰邊幀數 |
|---|---|---|---|---|---|
| res_multistep s3002 | 111 | 1.68 | 5.51 / 5.64 | 0.88 / 1.00 | 0 |
| euler s3002 | 104 | 1.66 | 5.23 / 5.23 | 0.82 / 1.00 | 0 |
| res_multistep s3003 | 104 | 2.64 | 5.02 / 4.89 | 0.83 / 1.00 | 0 |
| euler s3003 | 104 | 2.43 | 5.02 / 4.69 | 0.80 / 1.00 | 0 |

兩種取樣器的動作幅度、回到原站姿的程度和耗時都差不多。WanGP 的 3 步第二階段精修沒有測，ComfyUI 版沒有對應的節點設定。

**另外發現**：`video/h3/img2video-last` 的技術檢查要求「沒有音軌」，但 H3 會輸出音訊，所以 6 支都被判 `failed`（`check_video_output(video): 音軌:有,預期沒有`）。影片本身完整。這是 draft template 的 bug，另外修。

## E2　Wan 2.2 5B shift／steps

`video/wan/img2video`，同一張 idle 圖，640×640、49 幀，idle prompt，seed 3001、3004。

| run | 耗時 s | 相鄰幀差 | 末幀 vs 原圖 | 前景高度最小比 | 觀察 |
|---|---|---|---|---|---|
| shift8/20 s3001（基準） | 41 | 0.77 | 7.48 | 0.98 | 正常眨眼 |
| shift5/20 s3001 | 34 | 0.77 | 9.84 | **0.87** | 中段轉身、縮小 |
| shift5/30 s3001 | 46 | 0.39 | 5.89 | 0.99 | 正常 |
| shift5/50 s3001 | 72 | 0.36 | 7.70 | **0.78** | **整隻角色被綠幕染綠** |
| shift8/20 s3004（基準） | 33 | 0.21 | 2.66 | 0.99 | 正常 |
| shift5/20、30、50 s3004 | 34 / 46 / 73 | 0.21–0.22 | 2.6–2.8 | 0.99 | 和基準幾乎相同 |

WanGP 的 50 步、shift 5 是為 1280×720、121 幀調的。在我們「小角色加大片綠幕」的構圖下，低 shift 比較容易把背景色洗進角色裡。

## E3　VACE 1.3B CFG／steps

`video/wan-vace/inpaint` keep 模式，錘子改色案例（素材同 `vfx-video-inpaint-smoke-20261007`），544×560、57 幀，seed 202、203。

- 同一個 seed 下，CFG 6／5、20／30 步的錘子形狀、顏色、光效幾乎相同。差異來自 seed，不是這兩個參數。
- 耗時：20 步約 113–115 秒，30 步約 150 秒。
- `compare.jpg` 最右一格是 runner 補到 4k+1 的第 57 幀，raw 輸出裡是灰糊的；貼回原片時會被丟掉，不影響交付。

## E4　VACE 參考圖注入

做法參考 WanGP 的 `vace_preprocessor.py:254-273`：把冰錘母版 `skye-ice-hammer-game/art-src/weapon/weapon-front-clean.png` 縮到 90%，置中貼在 560×560 白底上。graph 加一個 `LoadImage` 接到 `WanVaceToVideo.reference_image`，`TrimVideoLatent` 原本就會裁掉參考圖那幾幀。prompt 改成描述母版的樣子（深藍錘身、金色端蓋紅寶石、兩端青色冰晶窗、中央冰閃電徽記、棕色皮革握把）。seed 202、203，每支約 114–122 秒，有參考圖只多約 7 秒。

| 模式 | 沒有參考圖 | 有參考圖 |
|---|---|---|
| replace（遮罩內清空重畫） | **錘子設計跑掉**：s202 變成黑框加紅寶石，s203 變成單顆藍晶；只看 prompt 會自己發明 | **回到母版設計**：深藍錘身、兩端青色冰晶窗、中央冰閃電徽記、金色框，兩個 seed 都對 |
| keep（保留原內容當引導） | 原片錘子已經提供形狀，加上新 prompt 就改對顏色 | 和沒有參考圖相近，差異不明顯 |

- **結論**：「把道具換成指定設計」的 replace 情境裡，參考圖是決定性的。只靠文字，VACE 1.3B 畫不出指定的道具。keep 情境本來就有原片當引導，參考圖的幫助有限。
- **限制**：replace_ref 的第 0 幀錘子比較扁、少了冰晶窗（`compare.jpg` 第一欄），之後的幀才穩定。紅寶石在小尺寸下不明顯。要逐幀看才能決定能不能交付。
- **提案**：新增 `video/wan-vace/inpaint-reference`（結構變化，所以是另一份 template），slot 加 `reference_image`，前處理做「白底置中縮放」。照[擴充協議](../../../maintenance/extension-protocol.md)，使用者確認後再做。

## E5　H3「鏡頭靜止」句型

把 prompt 裡的 `static locked camera` 改成獨立一句：「The camera stays completely still in a fixed wide full-body shot and her whole body remains inside the frame.」其他條件同 E1 的 res_multistep 組。

- 兩支的前景高度最大比都是 1.00、0 幀碰邊、首末幀差 4.7–5.6，跟基準組相同。
- **基準組本身就沒發生鏡頭推近**：之前的問題出在 3 秒的 `transition`，這次是 2 秒、56 幀。所以這組驗證不了新句型有沒有效。
- 補測要用原條件：72 幀（3 秒），先確認基準組會重現推近，再比新句型。

## E6　Wan Animate Move 取樣器

`video/wan-animate/move`，安裝測試的素材（reference.png、source.mp4），17 幀、384×384，蒸餾 6 步，seed 42、43。

- seed 42：兩種取樣器都是正常的跑步動作，身份和構圖相近，uni_pc 稍微清楚一點。
- seed 43：兩種都不穩。首幀糊、構圖從全身跳成近景；uni_pc 還在頭上冒出不存在的道具。
- 耗時一樣（約 15 秒；第一支 62 秒含模型載入）。Move 模式的構圖不穩和幻覺是已知問題，換取樣器解決不了。

## 下一步

1. **E4**：使用者確認後做成 `video/wan-vace/inpaint-reference` template。前處理照 WanGP 做白底置中，要不要加去背由使用者決定。
2. **E5**：用 3 秒原條件補測。
3. **H3 template 音軌檢查 bug**：`video/h3/img2video*` 的技術檢查應該允許或要求音軌。
4. **E7（MatAnyone）、E8（N 段滑動視窗）**：等使用者決定節點、權重、授權，以及 runner 迴圈怎麼解釋 R2。
