---
type: tool-guide
status: active
last_updated: 2026-10-07
---

# 特效去背、物件標記局部重繪與 Idle 首尾規則

這頁是 `vfx_alpha_tools.py`（`gameart.py vfx`）與 `generate.py video_inpaint` 的操作契約和證據入口。研究過程與完整數據見 [`docs/experiments/vfx-research/`](../../experiments/vfx-research/design.md)。所有輸出都是 candidate，技術通過不等於美術接受，由 Steve 決定。

## 1. 特效去背輸出

| 特效類型 | 生成方式 | 去背 | 交付 |
|---|---|---|---|
| 發光、火花、光暈、亮色霧 | `fx_loop`／`img2video`，起始靜幀與 prompt 都用純黑背景 | `vfx luma-alpha --black-point <背景雜訊>`（本次 16/255 = 0.063） | straight-alpha PNG 序列（主檔）＋保留黑底原片給引擎走 additive |
| 暗色煙霧、不透明碎片、角色 | 綠幕 | `vfx chroma-alpha --unmix --despill` | 同上；綠幕上不要用綠色或青色特效 |
| 需要更好邊緣的不透明主體 | 綠幕或任意底 | `vfx birefnet-alpha`（只能在 repo 的 `tools_src/` 執行，需要本機 BiRefNet 權重） | 逐幀模型，沒有時序穩定機制，要檢查閃爍 |

- 量測：`vfx metrics --input <RGBA 序列>` 會輸出 alpha 分佈、相鄰幀 |Δα|、閃爍值和殘綠；`vfx board` 會產生原片／alpha／深色背景／淺色背景的對照圖。
- 打包：`vfx pack --input <RGBA 序列> --output-dir <新資料夾> [--columns N] [--apng] [--webm]`，輸出 sprite sheet＋JSON（straight alpha、fps）、APNG，以及 WebM VP9 alpha（要用 libvpx 解碼才保得住 alpha；有損，不當主檔）。sprite sheet 不會自動縮小，超過引擎貼圖上限（常見 4096）時要先減少幀數或尺寸。
- 實測（2026-10-07，704×416×56 幀冰爆）：亮度法閃爍值 0.0062，綠幕現況 0.0589；在獨立對照中亮度法的 alpha MAE 最低（0.052）。黑底取 alpha 無法區分「顏色暗」和「透明」，暗色或不透明的煙霧不要用這個方法。

## 2. 影片物件標記與局部重繪

### 2.1 人工指定物件（美術操作）

```text
gameart.py vfx keyframes --video <src.mp4> --frames 0,<中段幀> --output-dir <dir>/keyframes
mask_session.py create --image <dir>/keyframes/frame_00000.png --output-dir <dir>   # 每張關鍵幀各開一次
    → 把 EDITOR_URL 給美術，用白色塗出要改的物件 → 完成後 mask_session.py fetch
gameart.py vfx segment-plan --video <src.mp4> --mask 0=<mask_editor.png> [--mask <幀>=<mask_editor.png>] --output-dir <dir>/plan
video_layers.py run --config <local_config.json> --plan <dir>/plan/segment_plan.json --output-dir <dir>/segment
gameart.py vfx unpack-masks --segment-dir <dir>/segment --video <src.mp4> --output-dir <dir>/masks
gameart.py vfx mask-preview --video <src.mp4> --masks <dir>/masks --output <dir>/mask_preview.png   # 給美術確認
```

- 一定要有第 0 幀的手繪遮罩；動作幅度大的片要在中段再塗 1–2 張修正幀。實測只塗第 0 幀時，SAM 在第 14 幀之後把尾巴也選進去；加了第 18 幀修正後，第 28 幀以後恢復正常，但第 14 幀仍有漏選。
- 手繪頁輸出的是黑底白色的 RGBA，`segment-plan` 會忽略 alpha，轉成白色＝選取的 L 遮罩，並縮放到 video_layers 的工作尺寸（偶數寬 256–1280）。
- 外圍光點等想一起改的東西要一起塗，或另外標成第二個物件；不在遮罩內的不會被改。
- 遮罩預覽要給美術確認後才進下一步。

### 2.2 只換顏色（不用 AI）

`vfx mask-recolor --input <src.mp4> --masks <dir>/masks --from-hue <度> --to-hue <度> [--hue-range 30] [--min-saturation 0.3] --output-dir <新資料夾>`：遮罩內做 HSV 色相旋轉，遮罩外和不符合色相的像素逐 byte 不變。接近白色的高光（飽和度太低）換不到。

### 2.3 `generate.py video_inpaint`（VACE 局部重繪）

```text
<python_exe> <generate_script> video_inpaint --config <local_config.json> --backend wan --timeout 1800 \
  --video <src.mp4> --masks <dir>/masks|<segment>/layers.zip [--mask-object 1] \
  --mode keep|replace --prompt "..." [--seed N] [--grow 8] [--feather 4] [--pad 48] [--crop x0,y0,x1,y1] \
  [--name <名稱>] --output-dir <output_dir>
```

- Gate：`video_capabilities.json` 的 wan backend 必須有 `masked_edit`，需要 `wan2.1_vace_1.3B_fp16.safetensors`、`wan_2.1_vae.safetensors`、`umt5_xxl_fp8_e4m3fn_scaled.safetensors`，以及核心節點 `WanVaceToVideo`、`TrimVideoLatent`、`LoadVideo`、`ImageToMask` 等。H3 沒有這個能力。
- 輸入：來源片必須是 24 FPS、5–81 幀；遮罩是白色＝重畫的 L PNG（幀數和尺寸要和來源一致），或 video_layers 的 `layers.zip`。圖片 inpaint 的 alpha 遮罩方向相反，會被拒絕。
- 模式：`keep` 會保留遮罩內的原內容當引導，適合改光效、材質或顏色，造型比較保得住；`replace` 會清空遮罩內再重畫（官方模板做法），適合換成新物件，每個 seed 的設計都不同。
- 處理流程：遮罩先擴張 `--grow`，依遮罩自動算工作區（再加 `--pad`，對齊 16），超過 832×480 像素時縮小處理；控制片段和遮罩編成無損 FFV1 mkv 上傳。取樣參數照官方模板 `video_wan_vace_inpainting.json` 的非 turbo 分支（shift 5、20 步、cfg 6、uni_pc/simple）。
- 輸出：
  - `<name>_00001_.mp4`：工作區原始結果，走一般影片契約和 sidecar，`fps`／`frames`（4k+1）都會驗證。
  - `<name>_00001_composited/`：
    - `frames/*.png`：貼回後的無損主檔，遮罩（擴張＋羽化範圍）外逐 byte 等於來源解碼結果，有程式檢查。
    - `composited.mp4`：H.264 重新編碼，不是無損。
    - `result.json`：工作區、處理尺寸、模式、seed、遮罩外變動數。
  - 音軌會丟掉。
- 實測（RTX 4080，Skye 召槌 FINAL 1024²×56 幀）：
  - 研究跑了 6 組（2 模式 × 3 seed），每組約 88 秒；遮罩外貼回前的差異約 4.4（Fun Control 整片重畫是 63.8），貼回後是 0；遮罩內相鄰幀差和原片相近。
  - 2026-10-07 正式 task smoke：工作區自動算出 544×560，耗時 99.7 秒，原始輸出驗證 pass，貼回後遮罩外 0 變動（另外獨立重算也確認）。
  - 證據在 `output/experiments/vfx-research-20261007/req2_vace/` 和 `output/experiments/vfx-video-inpaint-smoke-20261007/`。

| 需求 | 用什麼 |
|---|---|
| 只換顏色，造型完全不能變 | 2.2 `mask-recolor` |
| 同一物件改光效或材質 | `video_inpaint --mode keep`，跑 2–3 個 seed 讓美術挑 |
| 換成新物件或新特效 | `video_inpaint --mode replace` |

## 3. Idle 起始幀與首尾呼應

| task／backend | 首幀 | 尾幀 | 說明 |
|---|---|---|---|
| `img2video` H3 | ✅ | ✗ | 首幀是條件 token，每一步重新注入，不參與去噪；強引導，但不是逐像素相同 |
| `img2video` Wan 5B | ✅ | ✗ | latent 直接鎖住；但實測 2 秒內角色就跑掉，不建議用於角色動作 |
| `fx_loop` H3 | ✅ | ✅（同一張） | 會把 `--image` 同時當首幀和尾幀 |
| `transition` H3 | ✅ `--start` | ✅ `--end` | `--start` 和 `--end` 可以是同一張 Idle |
| `pose_drive`、`character_video` | ✗ | ✗ | 圖片只當身份參考，不保證第一幀 |

動作規則：

1. 所有動作的第一幀都用已驗收的 Idle 圖，所以只用上表能鎖首幀的 H3 task。
2. Idle 循環用 `fx_loop --backend h3 --image <Idle>`。
3. 要回到 Idle 的動作（Attack、Win、Fail、Hit 等）用 `transition --backend h3 --start <Idle> --end <Idle>`，prompt 寫清楚「中段動作＋回到完全相同的站姿與位置＋鏡頭不動」。
4. 只出不回的動作（離場、倒地）用 `img2video --backend h3`。
5. Idle 圖先補邊到和生成畫布相同的比例（長邊 768、對齊 32）。H3 的首幀是拉伸到畫布、尾幀是置中裁切，比例不同時首尾會有幾何差異。
6. 驗收時跑 `vfx loop-metrics --video <mp4> --reference <Idle.png> --key 00FF00 --output-dir <新資料夾>`，看首幀 vs Idle、尾幀 vs 首幀和接縫比（只計角色範圍）。暫定提醒門檻（ROI MAE）：首幀 vs Idle > 15，或尾幀 vs 首幀 > 9 時要重點看片。這只用來找可疑的片，不能自動判定接受。
7. 首尾鎖成同一張時，循環播放要去掉重複的最後一幀，交付說明要寫清楚。

實測（2026-10-07，Skye Idle，編碼誤差下限 3.7）：

| 影片 | 首幀 vs Idle | 尾幀 vs 首幀 |
|---|---|---|
| `fx_loop` | 9.49 | 3.67 |
| `transition`（攻擊後回 Idle） | 10.19 | 4.44 |
| H3 `img2video` | 9.79 | 4.69 |
| Wan `img2video` | 4.31 | 64.47（變成另一個角色） |

- `fx_loop` 中段有位置晃動和表情改變。
- `transition` 中段鏡頭推近、頭部被裁掉。
- 首尾差低不代表動作或 loop 品質好，仍要人工看片。

## 4. 換道具材質／造型：先定母版，再整幀套原片動作

需求是「把影片裡的道具換成另一種材質或造型」（例如魔法槌 → 純木槌）時，**不要用 `video_inpaint` 局部重畫**。改成「先定母版靜幀 → 整幀套用原片動作」。

### 步驟

1. **標記道具**：在第 0 幀用 `mask_session.py` 手繪道具範圍，只塗要換的部分，不要塗到手。
2. **做母版靜幀**：
   - 用 `flux2_edit` 對第 0 幀整張下指令，例如「把槌子換成木槌，角色、姿勢、手、握把、畫風、綠幕保持不變」，跑 2–3 個 seed，選道具最好、又沒改到手和握把的那張。
   - FLUX 會微幅重畫角色（實測角色區平均差 21.6），所以只把新道具貼回原圖：先用 `gameart.py vfx chroma-alpha` 的同一套公式（key 設成 FLUX 圖的綠色，加 `--unmix --despill`）把道具去背，再疊到**原圖的綠色**上。貼回範圍＝手繪遮罩擴張 6 px ∪ 新道具的非綠像素，但排除原圖裡遮罩外的角色像素。直接貼 FLUX 圖的背景會看得出綠色色差。
   - 母版給美術確認。
3. **整幀套動作**：`generate.py pose_drive --backend h3 --control-type canny --image <母版> --motion-ref <原片>`，prompt 要描述新道具和動作。
   - canny 的邊緣會帶入道具的位置，所以道具會跟著原片動。
   - `--control-type pose` 的骨架沒有道具資訊，道具動作會跑掉，不要用。
4. **驗收**：整幀都是重新生成的，角色不是逐像素保留原本的樣子，臉、服裝、尾巴要人工比對；快速動作的幀可能有動態模糊。

### 2026-10-07 實測（Skye 召槌 FINAL → 純木槌，RTX 4080）

| 路線 | 結果 |
|---|---|
| `video_inpaint` replace（只有文字描述，沒有母版） | 遮罩外 0 變動；但快速揮動時糊成一團、槌頭形狀歪扭、沒有描邊、和握把接不起來、遮罩外的光點還留著。**不採用** |
| `video_inpaint` keep | 保留原本的金框和晶窗，只把顏色改成橘金色，不像木頭。**不採用** |
| SDXL `inpaint` 做母版（denoise 1.0，綠幕素材） | 綠色滲進木頭、木頭變成扁平色塊、描邊髒。**不採用** |
| `flux2_edit` 做母版，再去背疊回原圖的綠幕 | 木紋清楚、描邊和角色一致、背景綠色均勻（貼回區平均 (0.5, 253.6, 0.7)，原圖 (0, 254, 0)）。採用為母版 |
| **H3 `pose_drive` canny**（母版＋原片） | 動作和原片幾乎一致，木槌前後穩定，光點自然消失；768² × 56 幀，耗時 294.8 秒，技術 pass。**最佳 candidate** |
| H3 `pose_drive` pose | 道具舉起的時間和位置跑掉 |
| SCAIL-2 動畫模式（固定範本，原片先轉 16 FPS、取 33 幀） | 動作有跟上，但背景變成藍紫色斑塊、無法去背，還把原片光點畫成白色，只有 384². **不適合綠幕素材** |

- 證據：`output/experiments/vfx-manual-mask-trial-20261007/`
  - `master_wood_mallet_v3.png`
  - `fullframe/wood_posedrive_canny_00001_.mp4`
  - `fullframe_compare_board.png`
  - `wood_board.png`
- 輸出都是 candidate，尚未驗收。
- 只測了一支片和一種道具，這個結論不能直接推到所有道具或所有動作。

## 5. 物件追蹤方式比較（2026-10-07，同一支召槌片）

| 提示方式 | 結果 |
|---|---|
| SAM2.1（video_layers），框選或手繪第 0 幀 | 抓得到槌子，但前段會漏選到尾巴，要在中段補修正幀 |
| SAM3 打字 `hammer` | 第 0–1 幀槌子橫放時只抓到握柄 |
| SAM3 打字 `mallet`／`big hammer with gold frame` | 56 幀都抓到整把槌子，尾巴完全沒被誤選，約 9 秒 |
| SAM3 用第 0 幀手繪遮罩（`SAM3_VideoTrack.initial_mask`，不給文字） | 塗多少就追多少，從頭到尾不會自己修正；Steve 實際手繪的遮罩只追到槌頭和槌柄，握把、手、尾巴都沒被選進去，7.4 秒 |
| SAM3 用隨手框的方塊當第 0 幀遮罩 | 前段把背景和整個角色都選進去，不可用 |

SAM3 追蹤是純 ComfyUI graph（`LoadVideo` → `SAM3_VideoTrack` → `SAM3_TrackToMask`），之後若要正式化，應做成固定 API graph 素材，不要再包一層 Python 指令。實驗腳本在 `output/experiments/vfx-sam3-text-20261007/`。
