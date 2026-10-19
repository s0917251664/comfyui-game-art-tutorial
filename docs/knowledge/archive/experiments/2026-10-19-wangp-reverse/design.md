# WanGP 逆向研究：參數、長片視窗、VACE、MatAnyone、prompt 規則

日期：2026-10-19｜平台：windows-cuda（RTX 4080 16 GB）｜分支：`research/wangp-reverse`｜狀態：靜態閱讀完成，GPU 實測未開始

研究對象是 [deepbeepmeep/WanGP](https://github.com/deepbeepmeep/WanGP) commit `fdc63bdf89358fb13c93cf6b38693fd89a859f00`（v18.19，2026-10-19）。原始碼 clone 在 repo 外的 `C:\Users\XU\tools\_research-src\WanGP`，只讀、未執行、不進 git。本頁的行號都指那個 commit。

## 範圍與授權

- WanGP 是獨立的 Gradio app，不是 ComfyUI 節點包。我們只吸收**參數與做法**，用 ComfyUI 原生／已裝節點或自寫的固定節點重做；**不複製它的程式碼**。
- 授權是自訂的 WanGP Community License 2.0。研究、評估、內部使用屬 Free Use；條款 1.3 寫明不主張抽象的想法、方法、格式本身。複製進來的程式碼仍受該授權約束，所以不複製。內建的 `mmgp` 記憶體引擎同屬此授權，不重做。
- 第三方模型保留各自授權。MatAnyone 的授權（舊紀錄寫 NTU S-Lab License 1.0）要另外確認，WanGP 原始碼裡沒寫。

## R1　預設參數對照

WanGP 的預設值逐層疊加：`models/_settings.json`（30 步、guidance 5）→ `wgp.py:3341-3342`（i2v 類 shift 7、其他 5）→ 各家族 handler 的 `update_default_settings` → `defaults/*.json` 頂層鍵。`"URLs": "t2v"` 這類參照只繼承權重和 LoRA，不繼承取樣參數。加速 LoRA 是使用者在 UI 選的 profile（`profiles/<family>/*.json`），不是預設值。

| 模型 | 參數 | WanGP | 我們 | template |
|---|---|---|---|---|
| Wan2.2 TI2V 5B | steps / shift / cfg | 50 / 5 / 5（`defaults/ti2v_2_2.json:14-16`） | 20 / 8 / 5 | `video/wan/img2video`、`pose-drive-*` |
| Wan2.1 VACE 1.3B | steps / cfg / shift | 30 / 5 / 5（全域預設） | 20 / 6 / 5 | `video/wan-vace/inpaint` |
| Wan Animate | steps / cfg / shift / solver | 30 / 5 / 7 / unipc（不蒸餾） | 6 / 1 / 8 / euler（lightx2v ×1.0） | `video/wan-animate/{mix,move}*` |
| SCAIL-2 | steps / cfg / shift | 40 / 5 / 3（`defaults/scail2_14B.json:16-18`） | 6 / 1 / 5（lightx2v ×0.8＋DPO ×1.0） | `video/wan-animate/scail2*` |
| H3 | steps / shift / solver | 20 / 12 / **euler**；另有 3 步第二階段（switch 0.9035） | 20 / 12 / **res_multistep**；無第二階段 | `video/h3/*` |
| Qwen Edit 2511 | steps / shift | 30 / 動態 mu（`qwen_main.py:190-205`） | 40 / 固定 3.1 | `image/qwen-image-edit/three-reference` |
| Flux2 Klein 4B | steps / guidance | 4 / 1 | 4 / 1 | `image/flux2/concept`（相同） |

WanGP 沒有 Wan2.2 Fun Control 5B。我們的 Animate／SCAIL-2 走蒸餾，與 WanGP 預設的非蒸餾路線本質不同，不能直接比，只能拿來做「蒸餾 vs 非蒸餾」對照。

## R2　長片滑動視窗

- **交接用像素，不用 latent。** Wan 系（i2v、VACE、Animate、SCAIL）都把上一窗尾幀解碼成像素，再重新 encode 當下一窗條件（`wgp.py:8579`）。VACE 用 latent 交接的路徑被作者以「品質較差」停用（`any2video.py:282`）。只有 SVI Pro 用 latent 交接。
- **overlap 是硬切。** overlap 幀只當條件，第 2 窗起直接丟掉開頭 overlap 幀（`wgp.py:8630-8633`），沒有 crossfade。
- **規劃公式。** `總幀數 = (窗數-1) × (window - overlap - discard) + window`。window 和 overlap 對齊 4n+1，discard 取 4 的倍數，所以每窗新增的幀數是 4 的倍數。
- **預設值。** 通用 overlap 5；i2v 類 1；SCAIL-2 是 window 81、overlap 5；InfiniteTalk 是 81、9；H3 是 362、18。discard 和校色預設都是 0；VACE 的 overlap_noise 預設 20（即 0.02）。
- **參考圖每窗重新注入。** `frames_positions` 關鍵幀按全片時間軸定位，跨窗時自動落在正確的視窗。
- **校色。** Lab 色彩空間做 mean/std 匹配後再按強度混合（`multitalk_utils.py:382-480`），預設 0。我們 `scail2-extend` 的 `ColorTransfer reinhard_lab` 強度 1.0 與它等價，但預設值不同；`mix-extend` 沒有校色，兩份 template 不一致。
- **ComfyUI 對應。** `WanAnimateToVideo`（`continue_motion`）和 `WanSCAILToVideo`（`previous_frames`）已內建同樣的像素前綴做法，我們現有的兩段延伸與 WanGP 的 Animate／SCAIL-2 機制相同。差距只在：固定兩段、段長 33（WanGP 是 81）、沒有逐段 prompt、沒有 discard。

**N 段設計草案：** 拆成四個部分，結構都固定，每段只換輸入值。

1. **prep**：只跑一次，產出 pose、mask、背景，存成無損序列。
2. **seg-first**：第一段生成。
3. **seg-next**：接續段，輸入前段尾 5 幀、累積的 `video_frame_offset`、seed、逐段 prompt。
4. **assembler**：runner 本機串接各段。

段間尾幀存 PNG，不存 mp4。**待決：「runner 迴圈呼叫同一份 template N 次」算不算 R2 的結構變化，要使用者決定。**

## R3　VACE

- **遮罩語意相同**：白色是重畫區、黑色是保留區。WanGP 在遮罩內填灰 127.5，我們填 0；兩種都可以，因為 `WanVaceToVideo` 會把遮罩內外分成兩路處理。
- **最大缺口是參考圖。** WanGP 把參考圖等比縮放、置中貼在白底畫布上（`vace_preprocessor.py:254-273`），可先去背（rembg，背景填白）。之後把它的 latent 加在時間軸最前面，生成後裁掉。ComfyUI `WanVaceToVideo` 本來就有 `reference_image` 輸入，我們的 graph（node 55）沒接；`TrimVideoLatent` 已經接好。
- **其他缺口**：關鍵幀注入（`frames_positions`）、keep frames（指定幀整張重生成）、outpainting（上下左右按百分比外擴）、遮罩收縮與橢圓核（`expand_or_shrink_mask`，iterations 3）、SLG（layer 9、10–90%）、加速 LoRA（1.3B 用 CausVid 8 步、cfg 1、shift 2）。
- **我們較強的地方**：只裁遮罩工作區來算、羽化貼回，並逐 byte 驗證遮罩外沒有改動。WanGP 是整張重生成。
- **prompt**：WanGP 要求 VACE prompt 要長、描述整個場景，並明寫被注入的物件（`vace_infos.py:48,111,138`）。

## R4　MatAnyone

- **流程**：首幀遮罩用 SAM v1 vit_h 點選（預設）或 SAM3.1。接著把首幀遮罩先 dilate 再 erode，留出不確定區。MatAnyone 推論前，把第 0 幀重複 10 次當 warmup，這些幀不輸出（`matanyone_wrapper.py:47-74`）。輸出 0–1 浮點軟 alpha。記憶體設定 `mem_every 5`、`max_mem_frames 5`、不開 long term。
- **注意**：選 SAM3 時 WanGP 根本不跑 MatAnyone，只輸出二值遮罩。
- **權重**：v1 和 v2 都有，預設 v1，作者說多數人偏好 v1。檔案是 DeepBeepMeep 轉成 safetensors 的版本（HF `DeepBeepMeep/Wan2.1`，`mask/` 子資料夾），不是官方 `.pth`；大小與 sha 程式裡沒寫。
- **輸出**：真正的 RGBA PNG 序列只有 `alpha` 模式（`rgba_video.py`）；預設輸出是原片 mp4 加有損的 alpha mp4。
- **我們的缺口**：現有 SAM3、SAM2 的遮罩都是二值硬邊；BiRefNet 是逐幀處理，沒有時序穩定。沒有時序穩定的軟 alpha。
- **ComfyUI 版設計**：SAM3 `track-*` 取第 0 幀遮罩 → dilate/erode → MatAnyone（含 warmup）→ `JoinImageWithAlpha` → RGBA PNG（straight alpha，白色＝前景）＋ L 灰階 alpha 序列。
- **未確認**：有沒有現成的 ComfyUI MatAnyone 節點包。若沒有，照 `tools_src/comfyui_video_layers/` 的寫法自寫固定節點。
- **適用範圍**：不透明的角色和道具（頭髮、衣緣）。不適合半透明特效，特效仍走黑底亮度法。

## R5　prompt 規則

**結論**：我們沒有「每個模型怎麼寫 prompt」的規則頁。WanGP 的 enhancer system prompt 是現成的外部規則來源，值得吸收的依序如下。

1. **編修指令**：寫三件事，「改什麼」、「什麼不變」、「引用圖中實際存在的元素」，長度 30–90 字。否定句改成肯定句（「不要改 X」改成「保留 X」），抽象詞換成具體描述（`flux/modules/system_messages.py:13-24`）。
2. **多參考圖**：依序編號，並說明每張的角色（底圖、身份、物件、服裝、風格、背景）。**語法依模型而異**：Qwen 2.1 用 `<image1>`、H3 用 `<Picture N>`、Bernini 用序數自然語言。不可直接套到 Qwen Edit 2511。
3. **影片鏡頭**：鏡頭描述恰好一句；不需要運鏡就明寫「鏡頭靜止」。
4. **首尾幀**：描述可見的動作路徑，維持單一連續鏡頭，不要發明中間場景（H3 `prompt_enhancer.py:268-278`）。
5. **Wan Animate 拆兩段**：`prompt` 寫目標角色與場景，`alt_prompt` 寫來源影片的動作與背景（`models/wan/infos.py:86-88`）。要先確認 ComfyUI 版有沒有對應輸入。
6. **透明背景**：明寫「RGBA、alpha channel、transparent background」，不可用白底代替（Qwen 2.1）。
7. **長度與語言**：Wan／LTX 約 150 字；H3 Ref2VA 約 350–500 字；Flux2 編修 50–80 字。描述用英文，台詞和可見文字保留原語言。

**與我們衝突、吸收時要標適用範圍的：**

- **文字**：「畫面上的字一律給引號」只適用 FLUX、Qwen 這類能畫字的模型，不能覆蓋 SDXL 的實測結論（`art/known-limitations.md:19,22`）。
- **品質標籤**：「丟掉品質標籤」不適用 SDXL／Pony 的 score 標籤。
- **I2V 是否重述外觀**：WanGP 自己就有兩種相反的說法（`prompt_enhance_utils.py:100` 與 `docs/PROMPTS.md:45-51`），要用 A/B 實驗解決。
- **鏡頭靜止**：這只是 prompt 層的要求。我們實測過 transition 的鏡頭仍會被推近（[vfx-research results.md](../2026-10-07-vfx-research/results.md)），驗收仍要看片。

---

## 實驗清單（GPU 由主 session 統一跑）

每項都是 candidate，技術通過不等於美術接受。表中「需同意」指要裝節點、下載模型或改規則。

| # | 實驗 | 變數 | 需同意 |
|---|---|---|---|
| E1 | H3 取樣器 | res_multistep vs euler（同 seed、20 步、shift 12）；再看要不要加第二階段 | 否 |
| E2 | Wan 5B 參數 | 先固定 20 步比 shift 8 vs 5；再比 20 / 30 / 50 步 | 否 |
| E3 | VACE 參數 | cfg 6 vs 5；20 vs 30 步 | 否 |
| E4 | VACE 參考圖注入 | 接上 `reference_image`（白底置中）vs 不接；用 Skye 道具修補案例 | 否（新 graph 先在研究分支做 draft） |
| E5 | prompt A/B | 「鏡頭靜止」句型（H3 transition，沿用 vfx-research 的輸入）；I2V 重述外觀與否 | 否 |
| E6 | Animate 取樣器 | 蒸餾 6 步下 euler vs uni_pc | 否 |
| E7 | MatAnyone 去背 | SAM3 首幀遮罩 → MatAnyone v1／v2，與 `birefnet-alpha` 比閃爍值和邊緣 | **是**：節點包、權重下載、授權 |
| E8 | N 段滑動視窗 | 先用 seg-first + seg-next ×1 重現 `mix-extend` 的 61 幀，再試 N=3、4 的接縫與色彩漂移 | **是**：runner 迴圈是否符合 R2 |

**順序建議**：E1、E2、E3 不用裝任何東西，可以最先跑。E4、E5 做完，結果能直接回饋到知識庫。E7、E8 等使用者決定之後再做。

## 結果

尚未實測。實測數據寫在同目錄的 `results.md`。結果被接受後，照[擴充協議](../../../maintenance/extension-protocol.md)新增 template，並把 prompt 規則整理成正式的規則頁。
