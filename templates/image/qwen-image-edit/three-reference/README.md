# Qwen-Image-Edit 2511 三參考圖編修（進階模型，實驗）

`image/qwen-image-edit/three-reference` 是**比 FLUX.2 Klein 4B 更大的進階模型**的實驗模板，保持 draft／untested；輸出為待美術驗收的 candidate。

## 定位

- 模型：Qwen-Image-Edit 2511（約 20B 級，Apache 2.0 可商用），文字編碼器 Qwen2.5-VL 7B。
- 強項（2026-10-15 封面實驗觀察）：手指會真的包住握柄、照抄版面裡的物件設計與透視、保留原圖背景與臉。
- 弱點：同一個 FLUX 也做不到的「兩隻 Q 版短手同時握在短握把上」仍然只畫出一隻手；服裝會走樣，要放角色母版當參考。
- 成本：RTX 4080 16 GB 一張 1024px 約 7.5 分鐘（主模型 20.5 GB，部分放到系統記憶體）。FLUX.2 Klein 4B 約 20–70 秒。
- **先用 FLUX.2 模板**；只有 FLUX 做不出、而且值得多等幾分鐘時才試這個。它不是 FLUX 的升級版保證。

## 輸入

三張圖各自進 `TextEncodeQwenImageEditPlus` 的 image1／image2／image3，正負兩條 conditioning 都接。提示詞要用 Picture 1、Picture 2、Picture 3 說明每張的用途。

| slot | 用途建議 |
|---|---|
| `image` | Picture 1：主圖或版面（例：骨架＋照設計上色的 3D 武器）。輸出尺寸跟這張。 |
| `identity_ref` | Picture 2：原圖（背景、臉、畫風），或遮掉要改的部位後的原圖。 |
| `object_ref` | Picture 3：角色母版或物件設計。 |

只能放三張。角色母版和物件設計拼成同一張會讓兩者都變模糊（封面實驗 q3），不建議。

## 來源

從 ComfyUI core blueprint「Image Edit (Qwen 2511)」派生，原檔在 [source/official-blueprint.json](source/official-blueprint.json)，固定版本與差異見 template.json 的 provenance。主模型換成 fp8mixed（blueprint 寫 bf16，16 GB 放不下），其餘節點與取樣參數照 blueprint。沒有接 lightning LoRA。

## 使用

先 `python tools_src/gameart.py run show image/qwen-image-edit/three-reference`，再 dry-run、preflight、執行。尚未接入 generate.py。

2026-10-17：使用者要求把這次新增的模型整理成基礎 graph 並寫入技能，標明為進階模型實驗。這不代表美術接受或平台狀態升級。

## 實機紀錄

2026-10-15 在 windows-cuda／RTX 4080 用臨場實驗 graph 跑了 q1–q4 共 7 張封面，每張約 7.5 分鐘；技術上可執行，美術上未通過（見[封面失敗紀錄](../../../../docs/knowledge/experiences/cover-hammer-grip-2026-10.md)）。那個實驗 graph 和本模板不同：沒有 `FluxKontextMultiReferenceLatentMethod`，latent 用空白 `EmptySD3LatentImage` 而非 image1 的 VAE 編碼。本模板照官方 blueprint，**尚未實機執行**（使用者要讓出 GPU，留待之後依協議第 7 步補跑）。
