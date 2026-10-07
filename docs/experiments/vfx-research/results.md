# VFX 研究實測數據（2026-10-07，windows-cuda／RTX 4080）

所有數字都對應 `output/experiments/vfx-research-20261007/` 下的檔案（`output/` 不進版控，只在這台機器上）。量測腳本與產物放在同一個資料夾：`req1/run_req1.py`、`req1/run_req1_c.py`、`req2/run_req2.py`、`req3/run_req3.py`，工具為 `tools_src/vfx_alpha_tools.py`。以下數字都是技術指標，不代表美術驗收；所有輸出都是 candidate，需 Steve 決定。

## 0. 環境與前置

- ComfyUI 0.34.0 原本就在 8188 執行（不是本次啟動的，所以結束後沒有關閉），開跑前佇列是空的。
- 第一次送出時被 gate 擋下：node input schema fingerprint 不一致（快照 2026-10-06；模型數 106→109）。依 AGENTS 規定執行 `gameart.py doctor --refresh`（只掃描、不下載），舊快照備份在 `capability_snapshot_before_refresh/`。刷新後 H3 和 Wan 的能力和刷新前相同。刷新時 `doctor.py:216` 印出 cp950 `UnicodeDecodeError`，偵測本身有完成；這個問題另開待辦，不在本分支修正。
- 生成紀錄：`run_generation.sh`、`run_generation.log`。每支 MP4 都附同名 `.mp4.json` sidecar，`validation.status` 全部是 `pass`。

| 影片 | task／backend | 尺寸 | 幀數 | 生成秒數 |
|---|---|---|---|---|
| `req1/r1_fx_black_00001_.mp4` | fx_loop／h3 | 704×416 | 56 | 52.6 |
| `req1/r1_fx_green_00001_.mp4` | fx_loop／h3 | 704×416 | 56 | 47.4 |
| `req3/r3_idle_loop_fxloop_00001_.mp4` | fx_loop／h3 | 768×768 | 56 | 104.8 |
| `req3/r3_attack_idle_transition_00001_.mp4` | transition／h3（3 秒） | 768×768 | 73 | 141.3 |
| `req3/r3_idle_img2video_h3_00001_.mp4` | img2video／h3 | 768×768 | 56 | 99.0 |
| `req3/r3_idle_img2video_wan_00001_.mp4` | img2video／wan | 768×768 | 49 | 60.7 |
| `req2/r2_wan_canny_regen_00001_.mp4` | pose_drive／wan canny | 768×768 | 57 | 71.7 |

## 1. 去背輸出

**輸入**：`inputs/fx_ice_burst_black.png`，由 `inputs/concept_00088_.png`（SDXL concept，seed 20261007）裁切而來。`inputs/fx_ice_burst_green.png` 是同一張圖以亮度法（黑點 14/255）取 alpha 後合成到 #00FF00 上，讓兩支影片的起始內容相同。兩支影片使用相同的 prompt 主體和 seed 1001，但生成出來的動態並不相同，所以實片之間的比較會受到內容差異影響。

### 1A. 實片（`req1/analysis/req1_results.json`，`real/*` 為 RGBA PNG 序列）

| 方法 | 每幀秒數 | 平均 α | 可見像素中半透明比例 | 相鄰幀 \|Δα\| | 二階差閃爍值（平均／最大） | 邊緣殘綠（G−max(R,B) 平均；>16 的比例） |
|---|---|---|---|---|---|---|
| luma_on_black（黑點 16/255） | 0.0129 | 0.208 | 0.996 | 0.0149 | 0.0062／0.0155 | — |
| birefnet_general（黑底片）* | 0.5345 | 0.265 | 0.929 | 0.0182 | 0.0108／0.0224 | — |
| birefnet_hr_matting_on_black | 0.4074 | 0.225 | 1.000 | 0.0142 | 0.0073／0.0135 | — |
| chroma_baseline_on_green（現行 `video_composite` 的 ramp） | 0.0131 | 0.202 | 0.304 | 0.0812 | 0.0589／0.0823 | 153.7；100% |
| chroma_unmix_despill_on_green | 0.0205 | 0.202 | 0.304 | 0.0812 | 0.0589／0.0823 | 0.0；0% |
| birefnet_general_on_green | 0.1097 | 0.262 | 0.735 | 0.0739 | 0.0510／0.1127 | 175.3；99.96% |

\* 第一次呼叫包含 CUDA 暖機；同一變體之後的呼叫約 0.10–0.11 秒／幀（見 1B）。綠底片本身的動態較大，閃爍值有一部分來自內容差異。

對照圖：`analysis/board_real_black_clip_mid.png`、`analysis/board_real_green_clip_mid.png`（原片、alpha、深色背景、淺色背景）。

### 1B. 已知 alpha 對照（循環論證：真實值由亮度法產生）

真實 alpha 取自 `real/luma_on_black`，再合成到黑底和綠底：一組無損，一組經 libx264 crf18 yuv420p（`synthetic_*_h264.mp4`）。**亮度法在這組必然接近 0 誤差，只能證明它可以還原且不受 H.264 影響，不能當成優勢。**

| 方法 | 無損 α MAE／軟邊 MAE／IoU | H.264 α MAE／軟邊 MAE／IoU |
|---|---|---|
| luma_on_black | 0／0／1.000 | 0.0040／0.0078／0.982 |
| chroma_baseline_on_green | 0.1118／0.2659／0.700 | 0.1114／0.2649／0.702 |
| chroma_unmix_despill_on_green | 同上（只改顏色，不改 α） | 同上 |
| birefnet_general_on_black | 0.0687／0.1611／0.713 | 0.0666／0.1563／0.722 |
| birefnet_general_on_green | 0.1219／0.2847／0.600 | 0.1144／0.2669／0.611 |

### 1C. 獨立對照（`analysis_c/req1_control_c.json`）

特效顏色乘 0.75（最高通道約 191）、alpha 不變。黑底取 alpha 時無法分辨「顏色變暗」和「變透明」，這組量的是亮度法的系統誤差。合成誤差是把結果疊到淺色或深色背景上，和真實值合成後比較的平均 RGB 差（0–255）。

| 方法 | α MAE | 軟邊 α MAE | IoU@0.5 | 淺色背景合成誤差 | 深色背景合成誤差 |
|---|---|---|---|---|---|
| luma_on_black | **0.0524** | **0.1123** | 0.651 | **12.0** | **1.47** |
| chroma_baseline_on_green | 0.0901 | 0.2135 | **0.832** | 13.8 | 10.1 |
| chroma_unmix_despill_on_green | 0.0901 | 0.2135 | 0.832 | 15.6 | 5.04 |
| birefnet_general_on_black | 0.0649 | 0.1521 | 0.722 | 18.0 | 7.86 |
| birefnet_general_on_green | 0.1478 | 0.3195 | 0.566 | 24.5 | 15.7 |

### 1D. 打包（`req1/pack_luma_on_black/result.json`）

- PNG 序列：`analysis/real/luma_on_black/`，56 張，共 19 MB。
- Sprite sheet：`sheet.png` 5632×2912（8×7）、12.0 MB，另附 `sheet.json`（每格座標、fps 24、straight alpha）。
- APNG：`anim.png` 18.9 MB。
- WebM VP9 alpha：`anim.webm` 1.53 MB，回讀 56 幀，alpha 平均絕對誤差 0.748/255。必須用 `libvpx-vp9` 解碼才保得住 alpha，FFmpeg 內建的 vp9 解碼器會丟掉 alpha。

### 1E. 特效循環接縫（fx_loop H3，`loop_metrics_fx_*/loop_metrics.json`）

| 片 | 首幀 vs 起始圖 | 尾幀 vs 起始圖 | 尾幀 vs 首幀 | 相鄰幀中位數 | 接縫比 |
|---|---|---|---|---|---|
| black | 5.69 | 5.98 | 3.51 | 1.56 | 2.26 |
| green | 5.77 | 5.65 | 2.81 | 2.22 | 1.26 |

## 2. 區域標記修改

**來源**：`inputs/skye_hammer_ready_FINAL_1024.mp4`，從 Skye 正式區複製的 `04_召槌拿穩` FINAL（1024²、56 幀），原檔沒有修改。

- SAM 2.1 small，經 video_layers segment：plan 為 `req2/segment_plan.json`，在第 0、18、40 幀各給框和正負點。第一次 `run` 在最後 `os.rename` 時出現 `WinError 5 存取被拒`（`req2/segment_run.log`），暫存區已被清除；換一個輸出名稱重跑 `segment_hammer_r2/` 就成功：technical pass，server 7.97 秒，56 幀、空白遮罩 0 張。遮罩已解壓到 `masks_hammer/`。相鄰幀 IoU 在快速揮動的第 3–6 幀降到 0.42–0.49。疊圖 `mask_overlay_frames.png` 顯示第 0–4 幀有一部分漏到尾巴，外圍光點粒子沒有被選到。
- 方向轉換的範例：`analysis/frame000_edit_mask_alpha0_edit.png`（SAM 白色＝選取 → image_edit 的 alpha 0＝編修）。

`analysis/req2_results.json`（色相統計只計遮罩內飽和度 >0.3 的像素）：

| 版本 | 遮罩外變動 | 遮罩內青色／洋紅佔比 | 遮罩內相鄰幀 MAE |
|---|---|---|---|
| 原片 | — | 24.5%／1.8% | 15.13 |
| A. 本機遮罩換色 `local_recolor_cyan_to_magenta/`（190°→300°，範圍 ±30°，飽和度 ≥0.3） | PNG 為 0 像素；轉 H.264 crf18 後平均 1.141（原片自己重新編碼也是 1.140） | 0.0%／26.2% | 16.08 |
| B. Wan canny 重繪原始輸出（768→1024 Lanczos、取前 56 幀） | 平均 63.8；99.8% 的像素差 >8 | 24.6%／22.6% | — |
| B'. 重繪結果貼回遮罩內（羽化 4）`analysis/ai_regen_pasted_feather4/` | 0 像素 | 24.6%／22.6% | 16.02 |

對照圖 `analysis/board_req2.png`（第 0／12／18／40 幀）：

- A 在第 12 幀發光最強時，接近白色的晶窗沒有被換到。
- A 的第 0 幀，尾巴因遮罩漏選而染到一點粉紅。
- B 的槌子金框變成米白、Z 字消失，第 40 幀的光又回到青色。
- B' 的洋紅光暈在遮罩邊緣被硬切，外圍光點仍是原本的青色。

### 2B. VACE 1.3B 遮罩局部重繪（2026-10-07 追加，Steve 同意下載）

**模型**：`wan2.1_vace_1.3B_fp16.safetensors`，來源 Comfy-Org/Wan_2.1_ComfyUI_repackaged，4,309,519,800 bytes，SHA-256 `640ccc0577e6a5d4bb15cd91b11b699ef914fc55f126c5a1c544e152130784f2`（和 Hugging Face 公布值一致）。存放在 `ComfyUI/models/diffusion_models/`。text encoder 和 VAE 沿用本機既有的 `umt5_xxl_fp8_e4m3fn_scaled`、`wan_2.1_vae`。下載後執行 `doctor --refresh`（模型數 109→110，H3／Wan 能力不變），舊快照備份在 `capability_snapshot_before_vace_refresh/`。

**Graph**：研究用固定 graph，照官方模板 `video_wan_vace_inpainting.json` 的非 turbo 分支：ModelSamplingSD3 shift 5、KSampler 20 步／cfg 6／uni_pc／simple、`WanVaceToVideo` strength 1、`TrimVideoLatent`，負向詞照抄模板。遮罩用 SAM 遮罩擴張 8 px（模板預設 GrowMask 20，用在 720 畫布）。輸入用 KJNodes `LoadImagesFromFolderKJ` 讀無損 PNG，輸出用 SaveImage 存 PNG。腳本：`req2_vace/run_vace.py`；每組的 graph 在 `raw/<run>/workflow_api.json`，紀錄在 `raw/run_log.json`。這個 graph 沒有接成 task。

**設定**：從 1024 原片的 (160,176) 裁出 576×576 工作區，56 幀送進 length 57（第 57 幀由節點自動補灰並丟棄）。兩種模式：
- **template**：遮罩內 control 填黑，和官方模板相同，等於整個重畫。
- **keep**：遮罩內保留原片，當作引導。

各跑 seed 101／202／303，結果貼回 1024 原片時使用擴張後的遮罩，羽化 4。

`req2_vace/analysis/vace_results.json`（遮罩內統計使用原 SAM 遮罩；「遮罩內 vs 原片」是改變量，不是品質分數）：

| 組別 | 每組秒數 | 裁切區內遮罩外差異（貼回前，平均；>8 的比例） | 貼回後遮罩外變動 | 遮罩內 vs 原片 MAE | 遮罩內相鄰幀 MAE | 青色／洋紅佔比 |
|---|---|---|---|---|---|---|
| template s101 | 98.2* | 4.38；12.4% | 0 | 92.6 | 14.93 | 3.3%／53.3% |
| template s202 | 88.1 | 4.59；12.3% | 0 | 86.8 | 15.29 | 2.0%／58.2% |
| template s303 | 88.0 | 4.37；12.5% | 0 | 89.7 | 16.03 | 2.7%／46.2% |
| keep s101 | 95.1 | 4.51；12.3% | 0 | 65.8 | 16.90 | 3.0%／52.1% |
| keep s202 | 88.0 | 4.50；11.9% | 0 | 61.9 | 16.13 | 7.4%／36.2% |
| keep s303 | 88.0 | 4.27；12.0% | 0 | 71.6 | 16.87 | 2.3%／50.8% |

\* 含模型首次載入。原片遮罩內相鄰幀 MAE 為 15.13，三種路線的比較見 2A（本機換色 16.08、Wan canny 貼回 16.02）。

對照圖 `req2_vace/analysis/board_vace.png`（第 0／12／18／40 幀），貼回後的 PNG 序列在 `analysis/<run>_pasted/`：

- template：每個 seed 都畫出一把不同設計的新槌子（黑框方塊、金框紫面等），同一支片內前後一致，但原設計（金色端框、晶窗、Z 字）沒有留下。
- keep：保住了槌子結構（金色端框、晶窗位置、握柄），晶窗和光暈轉成洋紅；但槌身深藍被帶向紫色，金色更飽和，Z 字變淡或變形。s202 最接近原設計，但晶窗內仍殘留一點青色（7.4%）。
- 兩種模式都沒有改到遮罩外的青色光點；角色本體在裁切區內的差異平均約 4.4，主要來自重新編碼和色調的微小偏移，貼回後歸零。

## 3. Idle 首幀與首尾呼應

**Idle 圖**：`inputs/skye_idle_square_1024.png`，從 Skye 正式區 `09_1024方形綠幕動作/00_生成參考/character_safearea_square_1024.png` 複製；它是已驗收「一般待機」FINAL 影片所用的生成參考。

`req3/analysis/req3_summary.json`。ROI 為 Idle 圖中非綠色像素的外框再加 16 px：`[276,174,493,595]`（768 畫布）。編碼誤差下限是把 Idle 畫布只經過 libx264 yuv420p 的結果：ROI MAE 3.69（`*_codec_floor.mp4`）。

| 影片 | 幀數 | 首幀 vs Idle | 尾幀 vs Idle | 尾幀 vs 首幀 | 相鄰幀 MAE 中位數／p95 | 接縫比 |
|---|---|---|---|---|---|---|
| fx_loop H3（首＝尾＝Idle） | 56 | 9.49 | 9.49 | 3.67 | 1.28／12.92 | 2.86 |
| transition H3（Idle→攻擊→Idle，3 秒） | 73 | 10.19 | 9.61 | 4.44 | 5.80／33.01 | 0.77 |
| img2video H3（只鎖首幀） | 56 | 9.79 | 10.35 | 4.69 | 2.12／7.70 | 2.21 |
| img2video Wan 5B（只鎖首幀） | 49 | **4.31** | 65.00 | **64.47** | 1.05／6.31 | 61.4 |

- 首幀 vs Idle 的熱圖：`analysis/<label>/compare_first_vs_reference/`（`image_edit_tools compare`）。差異集中在線稿邊緣，背景綠也稍微偏暗；構圖和姿勢是對齊的。
- fx_loop 循環：中段第 9–33 幀相鄰差呈現大小交錯（約 10–14／1–3，`loop_metrics.json` 的 `adjacent_mae_roi_series`）。第 8–13 幀有位置晃動，表情從吐舌變成微笑（`metrics_idle_loop_fxloop/strobe_frames_08-13_roi.png`）。
- transition：條圖 `analysis/transition_h3_idle_attack_idle/frames_strip_roi.png` 顯示蹲低、出拳、回到 Idle；但第 3–5 幀鏡頭被推近，頭部被裁掉，prompt 要求的冰晶火花沒有出現。
- Wan img2video：後半段溶接成另一個轉身的角色（`analysis/img2video_wan_first_only/frames_strip_roi.png`）。
- 單元測試：`tests/test_vfx_alpha_tools.py` 16 項；全套測試結果見 design.md 的「驗證」段落。
