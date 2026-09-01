# 產線技術升級評估（2026-09-01）

> 狀態：優先度 1 的 FLUX.2 Klein 4B PoC、優先度 2 的 BiRefNet 變體 A/B，以及優先度 3 的 ControlNet Union 完整 `pose_only` 回歸，均已完成。stock SDXL、general BiRefNet 與三顆專用 ControlNet 均未被替換。Union 已定版為可重複的**選用實驗路徑**，不升格為預設；優先度 4 尚未開始。

## 結論摘要

| 項目 | 建議 | 優先度 | 結論 |
|---|---|---:|---|
| SDXL 底模 | 維持現狀 | — | stock SDXL 繼續當可重現 baseline；Juggernaut、Illustrious、Pony 已是選用風格底模，不需再做架構性替換。 |
| FLUX.2 Klein 4B | **PoC 已完成，保留為選用實驗軌** | 1 | RTX 4080 上 1024² 文字生圖 7.57 秒／13,642 MiB，單圖編輯 27.83 秒／15,594 MiB；能力有價值，但文字與臉部一致性仍有缺口，不取代 SDXL。 |
| BiRefNet HR-matting / dynamic | **A/B 已完成，維持 general 預設** | 2 | 6 個 2048² 案例沒有證明新變體穩定勝出；general 整體指標最佳、約快 2.1 倍且 CUDA 配置記憶體約為三分之一。HR-matting 只在部分柔邊案例局部較好。 |
| SDXL ControlNet Union | **選用實驗路徑定版，不升格預設** | 3 | 3 類控制 × 10 seeds × 兩後端共 60/60 成功；Union 平均耗時不高於 verified 且平均峰值 VRAM 較低。品質樣本沒有系統性退步，但只有一張來源圖與 `pose_only` scope，三顆專用模型繼續是正式路徑。 |
| InstantID / PuLID v1.1 | **新增臉部 ID 專用 task 的候選實驗** | 4 | 目標是人臉身分相似度，不是一般風格與外觀參考；不應取代 IP-Adapter。會引入 InsightFace/臉部偵測依賴與新 custom node，整合成本較高。 |

## 現有產線基準

- 本機：NVIDIA GeForce RTX 4080，16,376 MiB VRAM，`sdxl` tier，預設 1024×1024。
- ComfyUI：本機 checkout 為 `12d52794` / v0.34.0（2026-08-25）。
- 底模：`sd_xl_base_1.0.safetensors`，文件最後確認日 2026-07-29。
- 選用風格底模：Juggernaut XL Ragnarok、Illustrious XL v1.1、Pony Diffusion V6 XL，都已安裝，文件最後確認日 2026-08-19。
- ControlNet：獨立 SDXL Canny（2.33 GiB）、Depth（2.33 GiB）、OpenPose（4.66 GiB）；程式以 `CONTROLNET_MODELS` 分別寫死檔名。最後確認日為 2026-07-29 / 2026-08-17。
- 圖片條件：IP-Adapter Plus SDXL ViT-H（0.79 GiB）與 CLIP Vision ViT-H（2.35 GiB），文件最後確認日 2026-07-29。
- 去背：`birefnet.safetensors`（本機 0.41 GiB），程式直接以 `LoadBackgroundRemovalModel` 載入，文件最後確認日 2026-07-29。
- 相關 custom nodes：已安裝 `comfyui_controlnet_aux` 與 `ComfyUI_IPAdapter_plus`；未發現 InstantID 或 PuLID custom node。

## 逐項評估

### 1. SDXL 底模：不值得替換 baseline

現有設計已把「可重現基準」與「風格品質」分開：stock SDXL 當 baseline，三顆微調 checkpoint 透過 `--style` 選用。這比把默認 checkpoint 直接改成社群模型更適合這條強調回溯性的產線。

**建議：**不變更 `detect_device.py` 的預設 checkpoint，也不更名現有 style 值。若未來要檢查新版 Juggernaut / Illustrious / Pony，應當作同風格底模的版本更新，用固定 seed/prompt 獨立做 regression（回歸）比較，不與這次架構升級混在一起。

### 2. SDXL ControlNet Union：值得實驗，但價值主要在維運

Diffusers 已正式提供 `ControlNetUnionModel` 與 SDXL pipeline，文件範例直接載入 `xinsir/controlnet-union-sdxl-1.0`。ComfyUI Core 也有 `SetUnionControlNetType`，可指定 `openpose`、`depth`、`canny` 等類型。

潛在收益：

- 把三顆模型的檔名、來源、hash 與佈署管理收旂成一顆。
- 未來新增 lineart / softedge / segmentation 等控制類型時，可能不用繼續擴張獨立模型對映。
- Union 架構支援多條件輸入，對精細編輯有後續潛力。

不確定與風險：

- 「一顆取代三顆」不等於 canny/depth/pose 的結果一定更好；現有三顆是已驗證的異質組合，Union 必須逐類對打。
- 現有 graph 只有 `ControlNetLoader` + `ApplyControlNet`類邏輯；Union 需增加類型設定節點，不是單純換檔名。
- 若只是省硬碟，不足以解釋改動已穩定 task 的回歸風險。

**建議門檻：**使用相同 seed、prompt、preprocessor 輸出與強度，每類至少 10 張；只有當 canny/depth/pose 都不出現明顯品質退步，且載入時間、峰值 VRAM 與單圖時間可接受，才考慮讓 Union 成為默認。在此之前保留三顆舊模型與舊 graph。

**初步實測（2026-09-01）：**使用同一張 832×1216 全身角色參考圖、相同提示詞／negative／seed `20260901`／strength `1.0`，於 RTX 4080（16,376 MiB）以 `pose_only` 比較。Union ProMax（2,513,342,408 bytes，SHA-256 `9fae…7cdc`）與 ComfyUI `SetUnionControlNetType` 均可正常運作。冷啟動 wall time／峰值 VRAM：Canny verified `16.56 s / 15,471 MiB`，Union `10.90 s / 13,231 MiB`；Pose verified `15.56 s / 11,343 MiB`，Union `14.89 s / 10,994 MiB`；Depth verified `14.56 s / 12,657 MiB`，Union `9.94 s / 13,233 MiB`。六張皆保留大致的全身站姿與電台姿勢，但各後端都改寫了服裝與部分道具，不能把這個單例視為品質等價。程式提供隔離的 `pose_only --control-backend union`，預設仍為 `verified`，並在 upload/queue 前檢查 Union 模型與節點。產出與原始量測：`output/controlnet_union_ab_20260901/`。

**完整回歸與定版判定（2026-09-02）：**在同一來源圖、提示詞、negative、832×1216、strength `1.0` 下，Canny／Pose／Depth 各使用 10 個固定 seed（`20260901`–`20260910`），verified 與 Union 各產一張，共 **60/60 成功**。全部 PNG 可讀、尺寸正確且 SHA-256 各不相同；沒有 OOM、節點錯誤、逾時或缺檔。平均耗時／平均峰值 VRAM：Canny verified `9.93 s / 12,991 MiB`、Union `9.91 s / 12,245 MiB`；Pose verified `12.73 s / 12,804 MiB`、Union `11.10 s / 12,495 MiB`；Depth verified `10.20 s / 13,165 MiB`、Union `9.86 s / 12,351 MiB`。抽看每類 seed 1、5、10：兩者皆保留全身構圖；Canny 與 Pose 沒有觀察到 Union 的系統性品質退步；Depth 兩邊都會有個別腿部／背景偽影，Union 的背景在抽樣中較乾淨但不足以宣稱全面勝出。**定版決策：**將 Union 固定為已驗證的 opt-in（選用）`pose_only --control-backend union`；正式預設維持 `verified`，且不開放到 `character_action`、`guided_inpaint`、`icon_asset`。完整結果及可機讀統計：`output/controlnet_union_regression_20260901/`。

### 3. IP-Adapter / InstantID / PuLID v1.1：應新增任務，不應全面替換

InstantID 的官方定位是用單張圖、免訓練（tuning-free）達成 identity-preserving generation（身分保真生成）；PuLID v1.1 的官方說明則指出，相對 v1 改善相容性、可編輯性、臉部自然度與相似度。兩者的問題定義都比現有 IP-Adapter Plus 更專注於「臉」。

這不是 IP-Adapter 的替代關係：現有 `style_lock`、`appearance-ref` 還需要一般風格、配色、材質與整體外觀條件，臉部 ID 模型不是為這些用途設計。

整合風險高於 Union / BiRefNet：

- 需要額外臉部偵測與 embedding 依賴（常見為 InsightFace / antelopev2），在 Windows Python 環境上要特別驗證安裝與啟動。
- 本機目前未安裝 InstantID / PuLID custom node；導入新 node 會增加版本鎖定與安全審查面。
- 需用不同臉型、角度、表情、遮擋、寫實/插畫輸入測試；只拿一張理想大頭照無法代表遊戲角色產線。
- 必須建立人臉圖像的授權、同意、保存與輸出政策；這類資料的隱私風險高於一般風格參考圖。

**建議：**先定義獨立的 `face_id` 任務與驗收資料集，再用 InstantID 與 PuLID v1.1 同場對打。不先預選勝者，也不改現有 `style_lock` 語意。核心指標應包含：人工辨識相似度、臉部自然度、prompt 可編輯性、非寫實風格適配、單圖時間與峰值 VRAM。

### 4. BiRefNet：不換架構，值得更精準地選權重

BiRefNet 官方在現有一般模型之外，已釋出：

- `BiRefNet_HR`：以 2048×2048 訓練，對高解析一般去背。
- `BiRefNet_HR-matting`：以 2048×2048 訓練，目標是高解析 matting（前景透明度摳圖）。
- `BiRefNet_dynamic`：訓練解析範圍 256×256 到 2304×2304，官方定位是對不同解析度提供穩健表現。

這是相對低風險、高可測性的升級候選。現有 `attach_bg_removal()` 的 mask 語意與 alpha 反轉已實機驗證，因此 PoC 應只替換模型變數，不同時改 graph，才能清楚歸因。

**A/B 資料集建議：**20–30 張現有 icon，覆蓋硬邊金屬、發光/半透明、毛髮、細線、淺色主體+淺色背景、深色+深色、低解析與 2K 輸入。保留原圖尺寸與人工 ground-truth mask，比較 alpha MAE / IoU、邊緣 halo、細節斷裂、處理時間與峰值 VRAM。

**建議門檻：**不先假設 HR-matting 必勝；若產線同時吃 512/768/1024/2048 多種尺寸，`dynamic` 也可能是更適合的默認。只有 benchmark 證明整體邊緣品質提升且時間/VRAM 可接受，才更換預設權重。

**A/B 實測結果（2026-09-01）：**三張既有 RGBA 遊戲素材各合成深／淺背景，形成 6 個 2048×2048 案例；general／HR／HR-matting／dynamic 全部使用官方本機 Transformers 路徑實際推論。general 的平均 alpha MAE 0.008689、IoU 0.818162、邊界 MAE 0.240432，平均 0.1486 秒、峰值 CUDA allocated 1,612 MiB，整體優於三顆候選。HR-matting 在部分人物與鏤空柔邊案例局部較好，但整體 IoU 0.682185，且三顆 2048 候選約 0.31–0.32 秒、5,117 MiB。資料集 alpha 源自舊 general 產線而非人工精修真值，因此數值對 general 有偏差；即使如此，候選也沒有呈現足以支持全面替換的穩定收益。決策是維持現狀；若未來有大量毛髮／煙霧／玻璃需求，再用獨立人工 matte 資料集重測 HR-matting。

### 5. FLUX.2 Klein 4B：最值得 PoC，但是新 backend 而不是 SDXL checkpoint

ComfyUI 官方已提供 FLUX.2 Klein 4B 的 text-to-image 與 image-edit workflow。4B 分為 base（未蒸餾，適合 fine-tuning）與 distilled（4 steps，速度優先）。官方列出風格轉換、語意編輯、物件替換/移除、多參考圖組合與疊代編輯。BFL 模型卡並明確指出 4B 權重為 Apache 2.0，可用於商業產品。

VRAM 需求的官方資料有不同口徑：

- ComfyUI FP8 workflow：distilled 約 8.4GB，base 約 9.2GB（官方測試速度為 RTX 5090，不可直接外推 4080 耗時）。
- BFL 原始模型卡：約 13GB VRAM，並建議 consumer GPU 如 RTX 3090/4070 以上。

差異很可能來自權重精度、workflow 與計量範圍；本報告不在未實測前選擇其中一個數字當保證。RTX 4080 16GB 有足夠理由進入 PoC，但最後是否穩定，應看 ComfyUI 實際峰值，尤其是多參考圖編輯。

導入邊界：

- 不能只把 `CKPT` 改成 FLUX 檔名；FLUX.2 使用 diffusion model、Qwen 文字編碼器與 FLUX.2 VAE，graph 與 SDXL 不同。
- 現有 SDXL ControlNet、IP-Adapter、LoRA 與三顆風格 checkpoint 不能直接沿用。
- FLUX.2 的「多參考圖編輯」可能滿足一部分現有 IP-Adapter / inpaint 需求，但不能未實測就稱為 canny/depth/pose 的等價替代。

**建議的第一個 PoC：**新增獨立、明確實驗性的 FLUX.2 backend，不動現有 CLI 默認。先測 distilled text-to-image 與 base image-edit，不先同時做 LoRA/ControlNet。用相同美術目標比較 stock SDXL 與對應 style checkpoint，量測：prompt 跟隨、文字準確度、手部/裝備細節、多參考保留、單圖時間、峰值 VRAM 與模型總磁碟量。

**PoC 實測結果（2026-09-01）：**新增 `flux2_concept` 與 `flux2_edit`，模型總磁碟量 16,541,318,612 bytes。相同藥水提示詞、1024×1024、seed 20260901 下，stock SDXL 為 10.73 秒／15,016 MiB，FLUX.2 distilled 為 7.57 秒／13,642 MiB；FLUX 構圖、材質與標牌完整度較好，但仍把 `POTION` 拼成 `PENTION`。base 單圖編輯為 27.83 秒／15,594 MiB，能保留人物、姿勢、槍械與背景並替換白金盔甲，但臉部細節漂移。結論是保留獨立 task 繼續累積案例，不升格為 SDXL 替代品，也不把它視為 Face ID 或 ControlNet 等價能力。

## 建議的實驗順序與停損點

1. **FLUX.2 Klein 4B PoC**：新能力差異最大，也最可能影響後續架構方向。若 16GB 上編輯容易 OOM、或品質收益不足以抵銷雙產線成本，停在 PoC，不產品化。
2. **BiRefNet A/B**：可用小型、固定資料集快速得到可量化結果。若 alpha / 邊緣品質沒有穩定提升，維持現有權重。
3. **ControlNet Union A/B**：`pose_only` 每類 10 張已通過並定版為選用開關；只有延伸到核心 task 的回歸也過關，才考慮變成默認。
4. **Face ID bake-off**：先確定產品真的需要真人/寫實臉部 ID，並完成資料治理規則，再比 InstantID / PuLID v1.1。若主要是全身、裝備或非人角色一致性，這項優先度應繼續低於 IP-Adapter + LoRA。

## 建議的最終決策

**值得升級的不是「整條產線換代」，而是「新增獨立實驗軌，通過固定 benchmark 後才晉級」。**

- 已完成：FLUX.2 Klein 4B PoC 保留為選用實驗軌；BiRefNet A/B 維持 general 正式預設；ControlNet Union 在 `pose_only` 的 60 張回歸後定版為隔離選用開關。
- 值得但不急：將 ControlNet Union 擴大到其他核心 task 的回歸；Face ID 專用 task 評估。
- 需先有明確產品需求：InstantID / PuLID v1.1 臉部 ID task。
- 不建議：移除 stock SDXL baseline、拿 Union 直接覆蓋三顆已驗證 ControlNet、拿臉部 ID 模型覆蓋通用 IP-Adapter、把 FLUX.2 當普通 SDXL checkpoint 換入。

## 主要資料來源

- [Hugging Face Diffusers: ControlNetUnionModel](https://huggingface.co/docs/diffusers/api/models/controlnet_union)
- [ComfyUI Core: SetUnionControlNetType](https://docs.comfy.org/built-in-nodes/SetUnionControlNetType)
- [InstantID 官方專案](https://github.com/instantX-research/InstantID)
- [PuLID 官方專案](https://github.com/ToTheBeginning/PuLID)
- [BiRefNet 官方專案與 model zoo](https://github.com/ZhengPeng7/BiRefNet)
- [ComfyUI: FLUX.2 Klein 4B 官方指南](https://docs.comfy.org/tutorials/flux/flux-2-klein)
- [Black Forest Labs: FLUX.2 Klein 4B 模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
