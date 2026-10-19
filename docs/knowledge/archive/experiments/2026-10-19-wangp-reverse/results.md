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
| E4 | VACE 參考圖注入 | **replace 模式效果明顯：錘子回到母版設計** | 已做成 `video/wan-vace/inpaint-reference`（windows-cuda technical_pass） |
| E5 | H3「鏡頭靜止」獨立句型 | 2 秒驗證不了；3 秒補測：原寫法 2/3 推近，獨立句型 0/3 | 寫進 [idle 錨定規則](../../../rules/idle-anchoring.md) 第 3 點 |
| E6 | Animate 蒸餾 6 步：euler vs uni_pc | 差不多；seed 43 兩種都不穩 | 維持 euler |
| E7 | MatAnyone2 去背 vs BiRefNet／綠幕／SAM3 | 和 BiRefNet 相當；能修 SAM3 破洞；⚠ 非商業授權 | 不進產線；只在要指定物件的非商業專案考慮 |

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

**另外發現**：H3 的 6 支都被判 `failed`（`check_video_output(video): 音軌:有,預期沒有`），影片本身完整。原因在 runner 的 `check_video_output`：`audio: true` 一律被當成「保留來源音軌」，來源沒有音軌時就把預期改成「沒有」。已修正（commit 61802d9）：只有 `{keep_audio}` 這類 placeholder 才看來源音軌；寫死 `true`（模型自己生成音訊）一律要求有音軌。E5 補測的 6 支 H3 因此都是 exit 0。

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
- **已做成 template**：使用者確認後，照[擴充協議](../../../maintenance/extension-protocol.md)新增 `video/wan-vace/inpaint-reference`。
  - **graph**：在 graph 內處理參考圖：透明處合成白底 → `ResizeAndPadImage` 白邊置中到工作區。研究時是在本機先處理、縮到 90%；template 改成填滿工作區。
  - **實機**：直接用透明 PNG 母版，seed 202／203（`e4_template_live/`）。技術檢查全部 pass，遮罩外 56 幀不變，錘子設計和研究時一致，第 0 幀一樣偏扁。
  - **狀態**：windows-cuda 改為 technical_pass（v0.1.1）。

## E5　H3「鏡頭靜止」句型

把 prompt 裡的 `static locked camera` 改成獨立一句：「The camera stays completely still in a fixed wide full-body shot and her whole body remains inside the frame.」其他條件同 E1 的 res_multistep 組。

- 兩支的前景高度最大比都是 1.00、0 幀碰邊、首末幀差 4.7–5.6，跟基準組相同。
- **基準組本身就沒發生鏡頭推近**：之前的問題出在 3 秒的 `transition`，這次是 2 秒、56 幀。所以這組驗證不了新句型有沒有效。
- 補測要用原條件：73 幀（3 秒），先確認基準組會重現推近，再比新句型。

### E5 補測（73 幀）

條件同原 transition：73 幀、768×768，seed 3002／3003／3004。輸出在 `e5b_camera_73f/`。10/07 原片用同一套指標量出前景高度最大比 1.031。

| run | 前景高度最大比 | 最小比 | 相鄰幀差 | 首／末幀 vs 原圖 |
|---|---|---|---|---|
| 原寫法 s3002 | **1.041** | 0.866 | 1.97 | 5.46 / 5.35 |
| 原寫法 s3003 | 1.000 | 0.887 | 1.89 | 5.40 / 5.15 |
| 原寫法 s3004 | **1.036** | 0.923 | 2.23 | 5.15 / 5.22 |
| 獨立句型 s3002 | 1.000 | 0.887 | 1.66 | 5.48 / 5.29 |
| 獨立句型 s3003 | 1.000 | 0.887 | 1.81 | 5.37 / 5.14 |
| 獨立句型 s3004 | 1.000 | 0.923 | 1.76 | 4.97 / 5.09 |

- 原寫法在 s3002 重現了 10/07 的推近，s3004 也有推近。
- 獨立句型三個 seed 都沒有推近，相鄰幀差也比較小。
- 動作（蹲低、出拳、冰花、回到原站姿）兩組都有。
- 推近幅度只有約 4%，樣本 3 對 3，算是支持「鏡頭獨立寫一句」這條外部規則的第一個實測訊號，不是定論。

## E6　Wan Animate Move 取樣器

`video/wan-animate/move`，安裝測試的素材（reference.png、source.mp4），17 幀、384×384，蒸餾 6 步，seed 42、43。

- seed 42：兩種取樣器都是正常的跑步動作，身份和構圖相近，uni_pc 稍微清楚一點。
- seed 43：兩種都不穩。首幀糊、構圖從全身跳成近景；uni_pc 還在頭上冒出不存在的道具。
- 耗時一樣（約 15 秒；第一支 62 秒含模型載入）。Move 模式的構圖不穩和幻覺是已知問題，換取樣器解決不了。

## E7　MatAnyone2 影片去背（⚠ 非商業授權）

**授權**：MatAnyone 是 NTU S-Lab License 1.0，只限非商業用途。本節是本機評估。

**安裝**（使用者同意後，只裝 v2）：

- 節點包 FuouM/ComfyUI-MatAnyone，commit `87cbce3`。
- 權重 `matanyone2.pth`：141,429,115 bytes，sha256 與官方一致。
- 本機修改：關掉 ImageNet resnet 自動下載。

詳見 [模型與來源](../../../installation/models-and-sources.md#選用-matanyone2-影片去背實驗中非商業授權)。

**流程**：SAM3 `track-text` 取第 0 幀遮罩 → `MatAnyone2`（warmup 10、erode/dilate 0）→ `JoinImageWithAlpha` → RGBA PNG。腳本是 `scripts/run_matanyone.py`，輸出在 `e7_matanyone/`。

### 綠幕片（Skye 召槌 1024²×56 幀，首幀遮罩＝`chibi girl` ∪ `mallet`）

| 方法 | 閃爍值 | 半透明比例 | 邊緣殘綠 >16 | 耗時 |
|---|---|---|---|---|
| 綠幕去背 `chroma-alpha --unmix --despill` | 0.042 | 3.7% | 0% | — |
| BiRefNet HR-matting（逐幀） | **0.0289** | 20.7% | 82% | — |
| MatAnyone2 | 0.0301 | 8.8% | 95% | 10 秒 |

- **綠幕去背**：完整保留冰晶特效，邊緣乾淨。
- **BiRefNet**：只留角色和錘子，特效被乾淨去掉。
- **MatAnyone2**：大致只留角色和錘子，但冰晶位置有淡淡的鬼影，握把和手臂之間殘一塊綠。
- **邊緣殘綠**：MatAnyone2 和 BiRefNet 都只算 alpha、不處理溢色，用在綠幕片要另外做 despill。
- **結論**：綠幕生成的素材，MatAnyone2 沒有優勢。

### 實景片（安裝測試 source.mp4，人物＋灰牆，33 幀，首幀遮罩＝SAM3 `woman`）

| 方法 | 閃爍值 | 半透明比例 | 觀察（第 16 幀） |
|---|---|---|---|
| SAM3 逐幀二值遮罩 | 0.0668 | 1.2% | 袖子破成碎片 |
| BiRefNet HR-matting | **0.0197** | 5.0% | 完整、邊緣乾淨 |
| MatAnyone2 | 0.0201 | 3.5% | 完整，SAM3 的破洞都補回來；辮子左側多一小塊灰影 |

- MatAnyone2 把 SAM3 逐幀遮罩的閃爍值從 0.067 降到 0.020，前後幀傳播確實有用。但單一主體的畫面裡，BiRefNet 一樣穩，而且不需要首幀遮罩。耗時 42 秒（含模型載入）。

### 判斷

- 兩支素材上，MatAnyone2 的品質都和 BiRefNet HR-matting **相當，沒有勝出**。
- 它真正的獨特價值是「**指定要哪個物件**」：首幀用 SAM3 選定，之後跟著傳播。BiRefNet 是抓畫面最顯著的主體，沒辦法指定。這只有在畫面裡有多個主體、只要其中一個時才派得上用場，這次還沒測。
- 加上授權只限非商業，**現階段不做成 template、不進產線**：
  - 單一主體：BiRefNet（`vfx birefnet-alpha`）。
  - 綠幕：`chroma-alpha`。
  - 要指定物件、而且是非商業專案時，才考慮 MatAnyone2，並先補測多主體場景。

## 下一步

1. ~~E4 做成 template~~：已完成（`video/wan-vace/inpaint-reference` v0.1.1）。
2. ~~E5 補測~~：已完成，結果寫進 idle 錨定規則。
3. ~~H3 音軌檢查 bug~~：已修正 runner。
4. ~~E7（MatAnyone）~~：已評估，品質和 BiRefNet 相當，非商業授權，不進產線。要的話補測多主體場景。
6. **E8（N 段滑動視窗）**：等使用者決定 runner 迴圈怎麼解釋 R2。
5. **H3 draft template**：`video/h3/*` 的 template 有了這次的實機證據（img2video-last），可以另外評估是否升 technical_pass。
