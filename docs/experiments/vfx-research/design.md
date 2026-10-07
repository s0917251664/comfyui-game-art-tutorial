# VFX 研究：去背輸出、區域標記修改、Idle 起始幀

日期：2026-10-07｜平台：windows-cuda（RTX 4080 16 GB）｜分支：`research/vfx-alpha-mask-idle`｜數據：[results.md](results.md)

主軸是用明確的控制取代文字描述，例如 alpha、遮罩、首尾幀和量測。第一輪沒有下載任何模型、套件或權重；追加實測時經 Steve 同意，只下載了 Wan2.1 VACE 1.3B（4.31 GB，見需求 2）。本研究沒有修改既有 task、graph 或技能，只新增研究用的本機工具 `tools_src/vfx_alpha_tools.py`（附單元測試）。所有產物都是 candidate，是否接受由 Steve 決定。

---

## 需求 1：動效直接輸出去背成品

### 現況

只有 `video_composite` 的綠幕 chroma key（`video_media.py:505`），用每像素和 key 色的最大通道距離做線性 ramp，沒有 despill，也不還原半透明顏色；它的輸出是合成後的 MP4，不是透明序列。`comfyui-video-gen` 明確寫著沒有透明影片、逐幀 AI 去背、APNG 和 sprite sheet。

### 方案比較

| 方案 | 本機可行 | 實測 | 適用 | 主要限制 |
|---|---|---|---|---|
| 1. 黑底生成＋亮度轉 alpha（`luma-alpha`）／直接 additive | ✅ 純 NumPy | ✅ | 發光、火花、光暈、亮色霧 | 黑底取 alpha 無法分辨「顏色暗」和「透明」，暗色或不透明的煙無法表達；需要設定黑點，以壓掉生成背景的雜訊（本片約 7–11/255） |
| 2. 逐幀 AI 去背（BiRefNet，沿用 `benchmark_birefnet`） | ✅ 本機已有權重 | ✅ | 不透明主體（角色、道具） | 逐幀沒有時序模型；不會還原半透明顏色，綠幕片會把綠色留在前景 |
| 3. 綠幕 chroma key（現況） | ✅ | ✅ 基準和 unmix/despill 版 | 不透明主體 | 綠色系、青色系特效最難處理；半透明部分大量殘綠；unmix 會讓軟邊偏暗 |
| 4a. Wan-Alpha（原生 RGBA） | ❌ 缺權重 | 未測 | T2V 生成透明特效 | 只有 T2V，I2V 權重尚未釋出，不能指定起始幀；ComfyUI 官方整合寫「coming soon」，社群版需要額外 custom node |
| 4b. TransPixar／TransPixeler | ❌ | 未測 | T2V RGBA | 基於 CogVideoX-5B，官方說明約需 24 GB VRAM，超過 16 GB |
| 4c. MatAnyone／MatAnyone2（時序 matting） | ❌ 缺權重和節點 | 未測 | 不透明主體、頭髮邊緣 | 需要首幀遮罩（可接 SAM）；授權為 NTU S-Lab License 1.0，商用條件需 Steve 自行確認全文 |
| 4d. `BriaTransparentVideoBackground`（ComfyUI API 節點） | 節點存在，但屬於付費外部 API | 不測 | — | 專案目前無預算，依 AGENTS 須由使用者明確選擇才可使用 |

### 實測重點（詳見 results §1）

- **時序穩定度**：黑底＋亮度法的閃爍值最低（0.0062）；BiRefNet 在黑底片為 0.0108，hr-matting 為 0.0073。綠幕片的方法都在 0.05–0.06，但那支片本身的動態也比較大。
- **獨立對照 C**（特效顏色不飽和，亮度法的假設不成立）：亮度法的 alpha MAE 0.052 和深色背景合成誤差 1.47 仍然最低；淺色背景合成誤差 12.0，略優於綠幕基準的 13.8。綠幕的 IoU 最高（0.83），代表它在「哪裡有東西」比較準，但軟邊的透明度和顏色比較差。
- **殘綠**：綠幕基準的半透明邊緣 100% 殘綠，G 比 max(R,B) 平均高 154；unmix/despill 可以降到 0，但青色特效會變成偏暗的深青。
- **處理時間**：亮度法和 chroma 約 0.013–0.02 秒／幀；BiRefNet general 約 0.10 秒／幀，hr-matting 0.41 秒／幀。
- **輸出格式**：PNG 序列（主檔）、sprite sheet＋JSON、APNG、WebM VP9 alpha 都已在本機做成工具並實測。WebM 回讀的 alpha 誤差是 0.75/255；`sheet.png` 5632×2912，超過常見的 4096 貼圖上限。

### 推薦

1. **發光、火花、光暈、亮霧類特效**：預設用黑底生成，交付兩種形式。PNG 序列以 straight alpha 為主檔（`luma-alpha`，黑點依片調整，本次 16/255）；同時保留黑底原始 RGB，給引擎走 additive／screen 混合。WebM VP9 alpha 當預覽或網頁用，不當主檔。
2. **暗色煙霧、不透明碎片和角色**：維持綠幕，建議 `video_composite` 或新工具改用 unmix＋despill。需要更好的邊緣時，BiRefNet（`general` 或 `hr-matting`）可作為逐幀候選，但要人工檢查閃爍。
3. 生成特效時避免使用和 key 色相近的顏色，例如綠幕上的青色或綠色特效。
4. 原生 RGBA 模型目前不建議下載：Wan-Alpha 只有 T2V，不能鎖起始幀，和本專案「先定靜幀再動起來」的流程不合；等 I2V 權重和官方 ComfyUI 支援出來再評估。

### 缺少的模型或節點（只列出，未下載）

| 名稱 | 來源 | 大小 | 備註 |
|---|---|---|---|
| Wan-Alpha DoRA `epoch-13-1500_changed.safetensors` | [htdong/Wan-Alpha_ComfyUI](https://huggingface.co/htdong/Wan-Alpha_ComfyUI) | 0.31 GB | 另需 RGB／alpha VAE decoder 各 0.25 GB，以及 [WeChatCV/Wan-Alpha](https://github.com/WeChatCV/Wan-Alpha) 的 `RGBA_save_tools.py`（MIT） |
| Wan2.1 T2V 14B（Wan-Alpha 的 base） | [Comfy-Org/Wan_2.1_ComfyUI_repackaged](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged) | fp8 14.29 GB／fp16 28.58 GB | 官方說明另需 lightx2v T2V 蒸餾 LoRA（大小未查） |
| MatAnyone2 `model.safetensors` | [PeiqingYang/MatAnyone2](https://huggingface.co/PeiqingYang/MatAnyone2) | 141 MB | 需要第三方 ComfyUI 節點；授權為 NTU S-Lab 1.0 |

### 後續工作量

- 把 `vfx_alpha_tools` 正式接入（`gameart.py` 對應、`deploy_manifest`、技能和知識頁、smoke）：約 0.5–1 天。
- `video_composite` 加入 unmix/despill 選項和回歸測試：約 0.5 天。
- Wan-Alpha 評估（下載約 15–30 GB、custom node 安全審查、固定 graph）：約 2–3 天，而且仍然只有 T2V。

---

## 需求 2：動效可以標記特定區域修改

### 現況

`video_layers segment` 可以在首幀（和後續修正幀）給提示，用 SAM 2.1 傳播 1–4 個物件遮罩，輸出白色＝選取的 `L` 遮罩。repo 裡沒有「只重畫遮罩內」的影片 task；圖片端有 `image_edit_tools composite/recolor`，但它的遮罩方向相反（alpha 0＝編修）。

### 本機能力查核（看原始碼，不是看名稱）

| 節點／模型 | 本機 | 是否支援空間遮罩 |
|---|---|---|
| `WanVaceToVideo`（`comfy_extras/nodes_wan.py:287`） | 節點有，**VACE 權重沒有** | ✅ 有 `control_masks`：遮罩內的 control_video 被設為 reactive，遮罩外為 inactive，再分開送 VAE 編碼 |
| `WanFunInpaintToVideo`（`nodes_wan.py:256`） | 節點有，Fun InP 權重沒有 | ❌ 實作只轉呼叫 `WanFirstLastFrameToVideo`，是首尾幀補間，不是空間遮罩 |
| `Wan22FunControlToVideo` + `wan2.2_fun_control_5B` | ✅ | ❌ 只有 control video 和 ref image，沒有遮罩，所以會重畫整張 |
| `WanAnimateToVideo`（Mix）＋ Wan2.2 Animate 14B | ✅ | 有角色遮罩，但它是「角色替換並由姿勢驅動」，不是通用局部重繪；本次未測 |

### 串接設計

```
video_layers segment（SAM 2.1，白色=選取）
  → masks/*.png（L）
  → 方向轉換：sam-to-edit-mask（alpha 0=編修，給圖片工具）／VACE 直接吃白色=重畫
  → 影片局部重繪：
       (a) 像素路線：mask-recolor（純色相，非 AI）
       (b) AI 路線：VACE control_video=原片、control_masks=SAM 遮罩（建議羽化或擴張）
  → mask-composite：遮罩外逐 byte 貼回原片（feather 只在擴張後的區域內作用）
  → 量測：outside_changed_pixels 必須為 0；遮罩內相鄰幀差、色相統計；人工看片
  → 交付 PNG 序列（MP4 重新編碼會讓遮罩外產生約 1.1 的差，和原片重新編碼相同）
```

### 實測結果（results §2A、§2B）

- 本機遮罩換色（像素路線）：遮罩外 0 像素變動；遮罩內有飽和度的青色 100% 轉成洋紅。限制是發光最強時接近白色的部分換不到、遮罩外的光點沒有改、尾巴被漏選染色。
- 沒有遮罩條件的 AI 路線（Fun Control 5B canny 整片重畫再貼回）：重畫的原始輸出在遮罩外平均差 63.8；貼回後遮罩外為 0，但槌子設計被破壞，青色仍佔 24.6%。**判定不可用**。
- **VACE 1.3B（2026-10-07 追加，已下載實測）**：576² 裁切工作區、57 幀，每組約 88 秒。裁切區內遮罩外的差異只有約 4.4（Fun Control 是 63.8），角色本體幾乎不動；貼回後遮罩外 0 變動；遮罩內相鄰幀 MAE 14.9–16.9，和原片的 15.1 相近，沒有額外閃爍。
  - template 模式（遮罩內塗黑，官方做法）：洋紅佔比 46–58%，但每個 seed 都重新設計一把不同的槌子，原設計沒有留下。適合「換成新物件」。
  - keep 模式（遮罩內保留原片當引導）：保住槌子結構（金色端框、晶窗、握柄），光效轉成洋紅（36–52%）；但槌身深藍被帶向紫色、金色更飽和、Z 字變淡。適合「同一物件改光效、材質」，但仍需人工選 seed。
- 遮罩品質：SAM 在快速揮動的幀（3–6）相鄰幀 IoU 降到 0.42–0.49，前 5 幀有漏選到尾巴；外圍光點沒有選到，所以所有路線都沒改到光點。

### 推薦（依 VACE 實測更新）

| 需求類型 | 推薦路線 | 理由 |
|---|---|---|
| 只換顏色，造型要完全不變 | SAM 遮罩＋`mask-recolor`＋貼回 | 決定性、遮罩外和非目標色逐 byte 不變；接近白色的高光需要另外處理 |
| 同一物件改光效或材質，可以接受細節微調 | VACE keep 模式＋貼回，跑 3 個 seed 由人選 | 結構保住、光效顏色整體一致；會帶動槌身色調，Z 字這類細節不保證 |
| 換成新物件或新特效 | VACE template 模式＋貼回 | 遮罩內整個重新生成，外部不受影響 |
| 要連外圍光點一起改 | 光點框成 SAM 第二個物件，或擴大遮罩 | 這次光點不在遮罩內，三種路線都沒改到 |

- 1.3B 只支援 480P 級畫布，所以小物件建議用「裁切工作區＋貼回」（這次 576²），不要直接處理整張 1024。
- 品質不夠時再考慮 14B（約 35 GB），需要你另外同意下載。

### 實測計畫的執行紀錄

原計畫（照官方模板固定 graph、同一組遮罩、3 個 seed、量遮罩外 drift 和遮罩內統計、和本機換色並排比較）已全部執行。和原計畫不同的地方：
- 畫布改成 576² 裁切工作區，不用 832×480 或 640×640。
- 多加了 keep 模式。
- shift 和取樣參數改照本機官方模板（shift 5、20 步、cfg 6）。

目前仍是研究 graph；在 `video_capabilities.json` 加入 `vace` capability gate 之前，不接成 task。

### 模型

| 名稱 | 來源 | 大小 | 狀態 |
|---|---|---|---|
| `wan2.1_vace_1.3B_fp16.safetensors` | [Comfy-Org/Wan_2.1_ComfyUI_repackaged](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged) `split_files/diffusion_models` | 4.31 GB | **已下載**（2026-10-07，SHA-256 驗證一致） |
| `wan2.1_vace_14B_fp16.safetensors` | 同上 | 34.68 GB（16 GB VRAM 需要 offload） | 未下載 |
| `wan2.2_fun_vace_{high,low}_noise_14B_fp8_scaled.safetensors` | [Comfy-Org/Wan_2.2_ComfyUI_Repackaged](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged) | 各 17.35 GB（需要兩個） | 未下載 |

[Kijai/WanVideo_comfy_fp8_scaled](https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/tree/main/VACE) 另有約 3.05 GB 的 VACE module 檔；它和核心 `WanVaceToVideo` 的載入方式是否相容沒有查證，不列為首選。

### 後續工作量

- 接成固定 task（裁切／貼回、keep／template 模式、capability gate、sidecar、測試、技能）：約 2–3 天。
- `mask-recolor` 加高光處理選項：約 0.5 天。
- `video_layers` client rename 加重試：約 0.5 天（見下方附帶問題）。

---

## 需求 3：角色動作以 Idle 圖為第一幀，首尾呼應

### 現況與 graph 查核

| task | backend | 首幀 | 尾幀 | 依據 |
|---|---|---|---|---|
| `img2video` | H3 | ✅ | ✗ | `build_img2video_h3` 把 `LoadImage` 接到 `MiniMaxH3ImageToVideo.first_frame` |
| `img2video` | Wan 5B | ✅ | ✗ | `Wan22ImageToVideoLatent.start_image`：第一個 latent 的 `noise_mask=0`（latent 直接鎖住） |
| `fx_loop` | H3 | ✅ | ✅（同一張） | `video.py:183-186` 傳 `last_image_filename=img_fn`。**更正**：任務說明寫 `fx_loop` 只在 prompt 後面加文字，實際上 H3 已經鎖住首尾幀 |
| `fx_loop` | Wan | — | — | `tasks` 要求 `last_frame`，Wan 沒有，會被 gate 擋下 |
| `transition` | H3 | ✅ `--start` | ✅ `--end` | 同上；`--start` 和 `--end` 可以是同一張 Idle |
| `camera_move` | H3 | ✅ | static 時用同一張，pan/zoom 時用幾何終點圖 | `video.py` camera 分支 |
| `pose_drive` | H3 | ❌ | ❌ | 圖片接到 `MiniMaxH3ReferenceToVideo.ref_images.ref_image_0`，只當身份參考 |
| `pose_drive` | Wan | ❌ | ❌ | 圖片接到 `Wan22FunControlToVideo.ref_image`，進的是 `reference_latents`；`start_image` 在 execute 參數裡，但沒有開放在 schema 上 |
| `character_video` | H3 | ❌ | ❌ | 官方說明首幀可以不同 |

H3 鎖首尾的機制（`nodes_minimax_h3.py`、`comfy/ldm/minimax/model.py`）：keyframe 經 VAE 編碼後放進 packed sequence 當條件列（`img_update=False`，不參與去噪，每一步重新注入）。這是強引導，**不是像素直接覆蓋**，所以首幀不會和 Idle 逐 byte 相同。另外首幀是直接拉伸到畫布（`"disabled"`），尾幀是置中裁切（`"center"`）；Idle 圖的比例和畫布不同時，首尾的幾何會有微小差異。

### 實測（results §3）

- 首幀 vs Idle（ROI MAE）：H3 三支約 9.5–10.2；Wan 4.3；編碼誤差下限 3.7。H3 的差異集中在線稿邊緣和背景色調，姿勢和構圖都對齊。
- 尾幀 vs 首幀：fx_loop 3.67、transition 4.44、H3 img2video 4.69；Wan img2video 64.5（變成另一個角色）。
- 在這次 Idle 動作很小的情況下，只鎖首幀的 H3 img2video 首尾差也很低，代表「首尾差低」不足以證明 loop 好；fx_loop 中段有位置晃動和表情改變，仍須人工看片。
- transition 確實演出了「蹲低、出拳、回到 Idle」，但中段鏡頭推近、頭部被裁掉；prompt 中的冰晶火花沒有出現。

### 動作樣板規則（建議）

1. **第一幀一律是已驗收的 Idle 圖**：只用能鎖首幀的 task（H3 的 `img2video`／`fx_loop`／`transition`）。`pose_drive` 和 `character_video` 不能保證第一幀，需求是「從 Idle 開始」時不要用它們，或改用下方的實驗方案。
2. **需要回到 Idle 的動作**（Attack、Win、Fail、Hit 等）：用 `transition --start <Idle> --end <Idle>`，prompt 寫清楚「中段動作＋回到完全相同的站姿和位置＋鏡頭不動」。
3. **Idle 循環**：用 `fx_loop --backend h3 --image <Idle>`（首＝尾＝Idle）。
4. **只出不回的動作**（離場、倒地）：用 `img2video --backend h3`，只鎖首幀。
5. 不建議用 Wan 5B `img2video` 做角色動作；本次 2 秒內身份就跑掉了（只有一個 seed，樣本有限）。
6. Idle 圖先補邊到與生成畫布相同的比例（長邊 768、對齊 32），避免首幀拉伸和尾幀裁切造成的幾何差。
7. **驗收**：每支用 `vfx_alpha_tools loop-metrics --reference <Idle> --key 00FF00` 量首幀 vs Idle、尾幀 vs 首幀、接縫比，只用來找出可疑的片，不能自動判定接受。暫定提醒門檻（ROI MAE）：首幀 vs Idle > 15，或尾幀 vs 首幀 > 2.5 倍編碼下限（約 9）時要人工重點看；門檻需要更多片校準。
8. 循環的最後一幀如果和第一幀相同（H3 鎖尾），引擎播放時要去掉重複的最後一幀，否則接縫會停一拍；交付說明要寫清楚。

### 實驗方案（未測）

`MiniMaxH3AddGuide` 節點可以在任意幀錨定圖片，而 `PackedLayout` 同時處理 keyframes 和 refs。理論上可以讓 `pose_drive`（Ref2VA）也錨定 Idle 為首尾幀，但 Ref2VA 權重是否用 keyframe 訓練過並不清楚。需要先做固定 graph 實驗（約 1 天），通過後才考慮接成 task 參數。

### 需要修改的地方（只是建議，本次沒有修改）

| 檔案 | 建議 |
|---|---|
| `skills/comfyui-character-animation-workflow/SKILL.md` | 加入「Idle 錨定」規則（上面 1–4），並說明哪些 task 不能保證首幀；驗收加入 `loop-metrics`，並註明只是輔助指標 |
| `docs/knowledge/animation/workflow.md` 第 24 行動作表 | Idle 改成 `fx_loop`（H3，首尾鎖 Idle）；新增 Attack／Win／Fail 改用 `transition` Idle→Idle；`pose_drive` 標注不鎖首幀 |
| `skills/comfyui-video-gen/SKILL.md` | task 路由表加一欄「首／尾幀是否鎖住」；更正 `fx_loop` 的說明（H3 會鎖尾幀＝首幀，不只加 prompt）；第 72 行在去背工具接入後改寫 |
| `tools_src/comfyui_pipeline/tasks/video.py` | `fx_loop` 的 help 補上「H3 會把同一張圖當尾幀」；可考慮在 `transition` 加 `--return-to-start`（end＝start）語法糖；`pose_drive`／`character_video` 的 help 註明首幀不鎖 |
| `tools_src/comfyui_pipeline/video_media.py` `video_canvas` | 可選：輸入比例和畫布不同時提示，或提供補邊選項 |

### 後續工作量

- 文件和技能規則：約 0.5 天。
- `--return-to-start` 和 help 文字加測試：約 0.5 天。
- `loop-metrics` 門檻校準（每種動作至少 3–5 支）：約 1 天的 GPU 時間。
- AddGuide 實驗：約 1 天。

---

## 新增工具：`tools_src/vfx_alpha_tools.py`

| 子命令 | 用途 |
|---|---|
| `luma-alpha` | 黑底特效 → straight RGBA PNG 序列（黑點、白點、gamma） |
| `chroma-alpha` | 綠幕 key（和 `video_composite` 相同的 ramp），可加 `--unmix`、`--despill` |
| `birefnet-alpha` | 逐幀 BiRefNet（沿用 `benchmark_birefnet`，只用本機權重和 CUDA） |
| `metrics` | alpha 分佈、相鄰幀 \|Δα\|、二階差閃爍值、邊緣殘留 key 色 |
| `board` | 原片和候選結果疊在 alpha、深色、淺色背景上的對照圖 |
| `pack` | sprite sheet＋JSON、APNG、WebM VP9 alpha（含回讀檢查） |
| `sam-to-edit-mask` | SAM 白色＝選取 → image_edit alpha 0＝編修 |
| `mask-recolor` | SAM 遮罩內色相旋轉，遮罩外逐 byte 不變 |
| `mask-composite` | 編修片只在遮罩內貼回原片，並檢查遮罩外為 0 變動 |
| `loop-metrics` | 首幀 vs 參考圖、尾幀 vs 首幀、接縫比（可用 ROI） |

輸出目錄必須是新的，不覆寫既有檔案。工具只做像素運算，不呼叫 ComfyUI；目前是 repo 內的研究工具，尚未加入 `gameart.py` 對應或部署清單。

## 附帶問題

- `video_layers.py:103` 用 `os.rename(stage, dest)` 沒有重試；本次遇到一次 `WinError 5`，推測是剛寫入的檔案被短暫鎖住。建議加有限次重試。
- `doctor.py:216` 的 `subprocess.run(text=True)` 沒有指定 encoding，在 cp950 環境會出現解碼錯誤（已另開待辦）。

## 驗證

- `tests/test_vfx_alpha_tools.py`：16 項，全部用合成資料。系統 Python 缺 libvpx，WebM 那項會略過；ComfyUI venv 下 16 項全部通過。
- 全套測試 `PYTHONPATH=tools_src python -m unittest discover -s tests`：系統 Python（miniconda 3.13.9）274 項通過、略過 10 項（原本 9 項，加上缺 libvpx 的 WebM 那項）；ComfyUI venv 326 項全部通過、沒有略過。基準（本分支開始前）：258 項通過、略過 9 項。

## 2026-10-07 實作結果（Steve 決定：VACE 接成 task、vfx 工具接入產線、需求 3 規則寫入技能，並要求可人工指定物件）

- `generate.py video_inpaint`（wan `masked_edit`）：自動工作區、keep／replace 模式、無損 FFV1 上傳、貼回並檢查遮罩外為 0。實機 smoke 技術 pass，結果 candidate。
- 人工指定物件：`gameart.py vfx keyframes` → `mask_session.py` 手繪 → `vfx segment-plan` → `video_layers.py run` → `vfx unpack-masks`／`mask-preview`。實測只塗第 0 幀時尾巴會被漏選，需在中段加修正幀。
- `vfx_alpha_tools.py` 已加入部署清單和 `gameart.py vfx`；需求 3 的規則已寫入技能、動作表和 task help。
- 操作契約：[`docs/knowledge/video/vfx-tools.md`](../../knowledge/video/vfx-tools.md)。

## 需要 Steve 決定的事項（研究當時）

1. ~~是否下載 Wan2.1 VACE 1.3B~~：已同意並完成實測（results §2B）。下一步是否把 VACE 接成固定 task，以及是否需要 14B 版（約 35 GB）。
2. 特效交付格式：是否採用「黑底 RGB（additive）＋ straight alpha PNG」為預設，WebM、APNG、sprite sheet 是否需要，以及 sprite sheet 的單張尺寸上限（目前 5632×2912）。
3. 是否把 `vfx_alpha_tools` 正式接入產線（`gameart.py`、部署、技能文件）。
4. 需求 3 的樣板規則和技能修改建議是否照表實施。
5. 原生 RGBA（Wan-Alpha）是否等 I2V 權重出來再評估；MatAnyone 的授權是否可以接受。
6. 本次所有生成片（results §0、§2B）都是 candidate，尚未驗收。
