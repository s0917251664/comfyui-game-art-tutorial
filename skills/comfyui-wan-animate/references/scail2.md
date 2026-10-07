# SCAIL-2 固定 ComfyUI API 操作契約

SCAIL-2（Wan2.1 14B 架構）是另一個角色動畫模型：用參考圖驅動角色跟著來源影片動，或把來源影片裡的人換成參考角色。和 Wan Animate 不同，它不用 DWPose 骨架，而是把來源影片本身當 pose 輸入，再用 SAM3 依文字追蹤人物，產生**彩色身份遮罩**把參考圖的角色和影片裡的人一一綁定。上傳、queue、輪詢、下載與證據保存都沿用 [Wan Animate API 契約](comfyui-api.md)，本頁只寫 SCAIL-2 不同的地方。

## Templates 與來源

| Template | 用途 | 輸出 |
|---|---|---|
| [scail2-api.json](../assets/scail2-api.json) | 單段 | 33 幀 |
| [scail2-extend-api.json](../assets/scail2-extend-api.json) | 兩段串接 | 33 + 28 = 61 幀 |

兩份都是依官方 [`video_wan21_scail2_character_replacement.json`](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan21_scail2_character_replacement.json)（Git blob `1fc5602b9c54b3517ed6af320ff281d5615e9306`）逐節點對應的 API graph，並做了三項明確調整：

1. 主模型用 FP8 scaled（官方範本寫 FP16，32.8 GB 不適合 16 GB 顯卡）。
2. VAE 用本機既有 `wan_2.1_vae.safetensors`（官方寫 `Wan2_1_VAE_bf16`），實測可正常解碼。
3. 延伸段改用目前 ComfyUI `WanSCAILToVideo` 的 `video_frame_offset` 輸出串接，整段只跑一次 SAM3 追蹤；官方範本則是每段各自切 pose 影片、各跑一次 SAM3。

固定參數：16 FPS、384×384、每段 33 幀、DPO LoRA 1.0 + LightX2V 蒸餾 LoRA 0.8、shift 5、6 steps、CFG 1、Euler/simple、SamplerCustom 解碼 `denoised_output`、text encoder 放 CPU、negative prompt 空字串。延伸段第二段去掉前 5 幀重疊，再以第一段最後一幀為準做 `reinhard_lab` 色彩校正後接上。

## 模型 preflight

除 Wan Animate 共用的 UMT5、CLIP Vision H、Wan2.1 VAE、LightX2V LoRA 外，另需三個檔案（[template manifest](../assets/template-manifest.json) 的 `scail2_models` 有 revision、bytes、SHA-256）：

- `models/diffusion_models/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors`（17,694,586,857 bytes）
- `models/loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors`（1,226,936,552 bytes）
- `models/checkpoints/sam3.1_multiplex_fp16.safetensors`（1,745,546,848 bytes；SAM3 用 `CheckpointLoaderSimple` 載入）

Live `object_info` 必須有 `WanSCAILToVideo`、`SCAIL2ColoredMask`、`SAM3_VideoTrack`、`ColorTransfer`、`BatchImagesNode`，且上述檔名出現在對應 loader 的 selector。缺任何一項就停止，不下載、不換相似檔名。

## 動態欄位

只可改以下欄位，其餘照 template：

| 欄位 | Node | 說明 |
|---|---|---|
| `__REFERENCE_IMAGE__`／`__SOURCE_VIDEO__` | 1 `image`／2 `file` | 上傳後的 server path |
| `__POSITIVE_PROMPT__` | 20 `text` | 描述**最終畫面**：角色外觀、動作、鏡頭與背景 |
| `__SAM3_VIDEO_OBJECT__` | 31 `text` | SAM3 在來源影片要追蹤的對象，英文名詞，例如 `person` |
| `__SAM3_IMAGE_OBJECT__` | 32 `text` | SAM3 在參考圖要追蹤的對象，例如 `robot`、`person` |
| `noise_seed` | 43（延伸段另有 53） | 明確整數，不可留 -1；兩段沒有理由時用同一個 |
| `__OUTPUT_PREFIX__` | 61 `filename_prefix` | 唯一前綴 |
| `replacement_mode` | 35、40（延伸段另有 50） | 三處必須一致，見下方模式 |
| 寬高 | 5 `width`／`height`、40（及 50）`width`／`height` | 必須是 32 的倍數且一致；只實測過 384×384 |
| `object_indices` | 35 | 多人時只取部分人物，例如 `"0,2"`；空字串代表全部 |

來源影片：16 FPS CFR，單段需剛好 33 幀，延伸段需剛好 61 幀（node 4 `length` 依 template 固定）。音訊與 Wan Animate 相同：預設不輸出，需要時在 node 60 加 `"audio": ["3", 1]`。

## 兩種模式

| `replacement_mode` | 模式 | 結果 | 對應 Wan Animate |
|---|---|---|---|
| `true`（template 預設） | 角色替換 | 保留來源影片背景，把追蹤到的人換成參考角色 | Mix |
| `false` | 角色動畫 | 背景來自參考圖，參考角色做來源影片的動作 | Move |

SCAIL2ColoredMask 會依模式自動決定遮罩背景色（替換：來源遮罩背景白、參考遮罩背景黑；動畫則相反），不要自己準備或改黑白二值遮罩。彩色區域代表各個身份；多角色時依 `sort_by=left_to_right`（第一次出現位置由左到右）分配顏色，參考圖和來源影片的人物順序要一致，否則身份會配錯。

## Prompt 與 SAM3 文字

- 主 prompt 寫最終輸出長什麼樣，不是寫來源影片；只描述來源實際有的動作，不加道具。
- SAM3 文字只決定「追蹤誰」，不影響外觀。主體相同時兩個欄位可用同一詞；參考圖不是人時（機器人、怪物）改寫成對應名詞。
- 來源畫面多人時要寫得更具體，或用 `object_indices` 篩人。追蹤失敗（沒偵測到人）時輸出仍會產生，但動作不會跟隨，所以抽幀時要特別確認動作對應。
- SAM3 文字太籠統時會把非主角也當成追蹤對象：2026-10-07 實測「man」在有人形怪人的鏡頭同時追蹤主角與怪人，替換後怪人消失、畫面重畫；改成較具體的「man with black hair」後只追蹤主角，怪人與飛過的道具保留。queue 前可先用 SAM3 遮罩確認只框到目標。
- 參考圖構圖會主導輸出比例：參考圖是胸口以上的大頭照時，遠景或背影來源會被畫成大頭特寫。把參考圖縮小並擺在來源人物頭部的位置與大小（灰底畫布、同輸出寬高）後，遠景鏡頭恢復原片的全身構圖。近景來源配近景參考圖本來就能跟上。

## 實測（2026-10-06，RTX 4080 16 GB）

輸入與 Wan Animate 延伸段測試相同：官方機器人參考圖、官方來源片段 frames 64..124（`source61-tone.mp4`，SHA-256 `1d05e47f…`），seed 20261006，SAM3 文字 `person`／`robot`。全部完整解碼通過：384×384、16 FPS、PTS 逐幀 1/16 秒、H.264、無音軌。

| 測試 | Template | 輸出 | Prompt ID | Server execution time | 證據 |
|---|---|---|---|---:|---|
| 替換 33（首次載入模型） | `scail2-api.json` | 33 幀／2.0625 秒 | `624c9e12-4227-44e6-8cad-4dbb7cb1f1ec` | 68.1 秒 | validation（本機證據：`output/scail2-test/replace33/validation.json`） |
| 替換 61 | `scail2-extend-api.json` | 61 幀／3.8125 秒 | `1da41c66-4300-4a9d-8c34-32fc835acd96` | 39.8 秒 | validation（本機證據：`output/scail2-test/replace61/validation.json`） |
| 動畫 33 | `scail2-api.json`，`replacement_mode=false` | 33 幀 | `b7e59189-d2be-4cc5-8b62-47512797bd0a` | 39.0 秒 | validation（本機證據：`output/scail2-test/animate33/validation.json`） |

這表示 FP8 版本可在 16 GB 顯卡以 384×384／33 幀分段執行；本次沒有成功抽樣顯存，峰值未知。耗時受模型快取影響，不作與 Wan Animate 的速度比較。

抽幀觀察（候選，未驗收）：

- 身份還原明顯比 Wan Animate 穩：相機頭、粉紅金屬、白藍針織衫、黃褲、粉紅鞋從頭到尾一致，延伸段第 32→33 幀接縫連續。
- **兩種模式都輸出全身構圖**（2026-10-06 執行的測試結果）：原因是參考圖構圖主導輸出比例（已於 2026-10-07 驗證：參考圖是大頭照時遠景被畫成大頭特寫；改用縮放對齊的參考圖後恢復全身構圖），替換模式雖保留了灰色背景，但人物比例和鏡頭不像來源。需要貼合來源鏡頭的工作，先用相同取景的參考圖或素材做測試。
- 動畫模式背景為參考圖的淺藍色，符合模式定義。
- 整個畫面重畫時，道具與特效也會被重畫而非保留原片（例：變身腰帶變成一般皮帶、鎧甲細節變少）；需要原片道具完全不變時，SCAIL-2 不適合整畫面重畫。

未測：81 幀官方段長、三段以上、多角色、音訊連線、未用蒸餾 LoRA 的 40 steps／CFG 5 品質模式。其他解析度：832×448 於 2026-10-07 測試（33 與 61 幀，RTX 4080 16 GB，抽樣顯存尖峰 15,088 MiB 含其他程式）、640×352 亦有執行。

## 界線

SCAIL-2 與 Wan Animate 是兩個模型，不能互相推定能力或品質；一方結果不佳時不自動改跑另一方，由使用者決定。這仍是獨立 API 路線，未接 `generate.py`，也不登記為 video backend。所有輸出維持 candidate，等使用者明確驗收。
