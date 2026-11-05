---
type: guide
status: active
last_updated: 2026-11-05
---
# 去背：先看素材，再選方法

這頁回答一個問題：**手上這張圖或這段影片，要用哪一種方法去背？** 本專案有四種去背方法，各自擅長的素材不同。選錯方法不會報錯，但會得到「看起來有透明，其實邊緣壞掉」的結果，所以先判斷素材類型再動手。

所有去背結果都是 candidate，要在深色底和淺色底上放大看過才交付（[R1](../rules/candidate-review.md)）。完整旗標以各工具 `--help` 與 `gameart.py run show <id>` 為準，這頁只寫判斷和最常用的寫法。

## 一句話版

- **角色、道具、圖示這類「有實體輪廓」的靜圖**：在 ComfyUI 裡用 AI 去背（`--remove-bg`），約 1 秒。
- **發光、火花、光暈、亮色煙這類「半透明」特效**：不要用 AI 去背（會被切掉）。改成黑底生成，再用亮度轉透明；要最乾淨的顏色用本機 `vfx luma-alpha`。
- **暗色煙霧、不透明碎片、角色影片**：綠幕生成，再用本機 `vfx chroma-alpha`。綠幕會留綠邊、吃掉深藍與暗部，交付前一定要放大檢查。

## 選方法

| 素材 | 背景 | 方法 | 在哪裡跑 | 為什麼 |
|---|---|---|---|---|
| 角色、道具、圖示靜圖 | 任意 | AI 去背（BiRefNet）：`generate.py <task> --remove-bg`；`icon_asset` 永遠去背 | ComfyUI（核心節點） | 實體輪廓切得乾淨，披風等少量半透明也保得住 |
| 3D 粗模前的物件圖 | 任意 | `gameart.py run 3d/hunyuan3d-2mv/multiview-cutout`（內建去背） | ComfyUI | 同上，流程已串好 |
| 發光、火花、光暈、亮色霧（靜圖或影片） | **純黑** | `gameart.py vfx luma-alpha`（建議） | 本機 Python，不需要 ComfyUI 或顯卡 | 拿亮度當透明度，柔邊與漸層保留；會把顏色除回透明度，疊到任何背景顏色都對 |
| 同上，只有一張靜圖、想留在 ComfyUI 裡 | **純黑** | `gameart.py run image/core/luma-alpha`（**草稿**） | ComfyUI（核心節點，不用模型） | 柔邊保留，但顏色沒除回透明度，一般疊法會偏暗；遊戲引擎用加亮（additive）或預乘疊法時接近正確 |
| 暗色煙霧、不透明碎片、角色影片 | 綠幕 `#00FF00` | `gameart.py vfx chroma-alpha --unmix --despill` | 本機 Python | 黑底分不出「顏色暗」和「透明」，暗的東西只能靠綠幕；綠幕上不要用綠色或青色特效 |
| 不透明主體，綠幕邊緣不夠好 | 綠幕或任意 | `gameart.py vfx birefnet-alpha`（只能在 repo 執行，要本機權重） | 本機 Python＋CUDA | 逐幀 AI 去背，邊緣較細，但前後幀沒有穩定機制，要檢查閃爍 |

**判斷口訣**：會發光的用黑底；暗的、實心的用綠幕；有清楚輪廓的靜圖直接 AI 去背。

## 為什麼半透明特效不能用 AI 去背

AI 去背模型（BiRefNet）學的是「找出前景物體的輪廓」，它會把畫面分成「是東西」和「是背景」。光暈、火花、煙沒有清楚輪廓，模型會把它們當背景切掉。2026-11-05 實測，一張合成的黑底特效經 AI 去背後，平均透明度只剩 0.015：只留下最亮的一條光軌，光暈和火星全被切掉。

黑底亮度轉透明的道理很簡單：越亮越不透明，純黑完全透明。這樣光暈從亮到暗的漸層自然保留下來。缺點是它分不出「本來就是暗色的東西」和「透明」，所以暗色煙霧、黑色碎片不能用，要改綠幕。

## 為什麼精確版仍要用本機程式

亮度轉透明之後，顏色還要「除回透明度」（反預乘），否則半透明的地方顏色會被黑底拉暗，疊到其他背景時周圍出現一圈暗暈。ComfyUI 核心節點沒有「影像除以影像」，也不能設定黑點、白點或 gamma，所以 ComfyUI 版做不到這一步；本機 `vfx luma-alpha` 做得到，而且：

- 純計算，同一段影片每次結果完全相同，幾百幀一次跑完。
- 不需要顯卡、不需要開 ComfyUI。
- 背景有雜訊時用 `--black-point` 把雜訊壓成全透明（2026-10-07 冰爆影片用 16/255 ≈ 0.063）。

## 指令範例

```text
# 角色或道具靜圖：生成時直接去背（概念圖、姿勢、風格鎖、角色動作、精修都可加）
python tools_src/generate.py concept --prompt "..." --remove-bg --output-dir <output_dir>

# 黑底特效：本機亮度轉透明（輸入可為 MP4 或 PNG 資料夾；輸出資料夾必須是新的）
python tools_src/gameart.py vfx luma-alpha --input <黑底特效.mp4> --output-dir <新資料夾> [--black-point 0.063]

# 黑底特效靜圖，留在 ComfyUI（草稿，先 preflight）
python tools_src/gameart.py run image/core/luma-alpha --set image=<黑底特效.png> --preflight --allow-unverified-platform
python tools_src/gameart.py run image/core/luma-alpha --set image=<黑底特效.png> --allow-unverified-platform

# 綠幕：本機去綠
python tools_src/gameart.py vfx chroma-alpha --input <綠幕.mp4> --output-dir <新資料夾> --unmix --despill

# 交付前檢查：原片／alpha／深色底／淺色底對照圖，以及閃爍與殘綠數字
python tools_src/gameart.py vfx board --original <原片> --candidate 亮度=<RGBA 序列資料夾> --output <對照圖.png>
python tools_src/gameart.py vfx metrics --input <RGBA 序列>
python tools_src/gameart.py edit asset-audit --image <單張 RGBA.png> --output-dir <新資料夾>
```

去背後要打包成 sprite sheet、APNG 或 WebM，見 [vfx-tools 第 1 節](../video/vfx-tools.md#1-特效去背輸出)。

## 交付前一定要看的地方

1. **深色底放大看邊緣**：綠幕的綠邊、黑底的暗暈，在淺色底上看不出來。
2. **深藍、暗紫、陰影**：綠幕去背常把這些吃成半透明（[橫向卷軸角色動畫](../experiences/side-scroller-character-anim-2026-10.md)踩過：深藍短褲變半透明，要補實輪廓內部）。
3. **光暈有沒有被切掉**：把結果疊到深色底，和原圖並排比，光暈範圍應該差不多大。
4. **影片要看閃爍**：`vfx metrics` 的相鄰幀變化；AI 逐幀去背沒有前後幀穩定機制。

## 實測依據

**2026-11-05，Windows／RTX 4080**（[實驗紀錄](../../experiments/2026-11-05-bg-removal/README.md)）

- 靜圖 `--remove-bg`：核心節點 `LoadBackgroundRemovalModel`（`birefnet.safetensors`）→ `RemoveBackground` → `InvertMask` → `JoinImageWithAlpha`，1024² 約 1 秒，邊緣乾淨，披風半透明保留，沒有缺節點或模型。
- 半透明特效：用一張合成黑底特效（軟光暈、火星、一條光軌）當標準答案，疊到深藍紫背景比誤差（越小越好）：

| 做法 | 平均誤差 MAE |
|---|---|
| ComfyUI AI 去背（BiRefNet） | 0.088 |
| ComfyUI 亮度轉透明（`image/core/luma-alpha`），一般疊法 | 0.074 |
| 同上，預乘疊法 | 0.046 |
| 本機 `vfx luma-alpha` | **0.029** |

**2026-10-07，冰爆影片 704×416×56 幀**（[vfx-tools](../video/vfx-tools.md)）：亮度法閃爍值 0.0062，綠幕 0.0589；獨立對照中亮度法的 alpha 誤差最低。

**2026-09-01，去背模型 A/B**（[模型清單](../installation/models-and-sources.md#選用-birefnet-ab-benchmark-權重)）：現行 general 版在實體素材上誤差最低；名稱有「matting」的 HR-matting 版沒有比較好，不要因為名字就換。

## 還沒驗證的

- 半透明特效只測了**一張合成特效、一次**，真實特效沒有逐張驗證。
- 影片走 ComfyUI 的亮度轉透明**沒有測**；影片目前一律用本機 `vfx luma-alpha`。
- `image/core/luma-alpha` 是草稿：graph 本身在 Windows 跑過一次（直接送 ComfyUI，約 0.5 秒），還沒用 runner 跑過，所以兩個平台都標 `untested`，執行要加 `--allow-unverified-platform`。
- MatAnyone2 影片去背是實驗、**只限非商業用途**，見 [vfx-tools](../video/vfx-tools.md#1-特效去背輸出)。
