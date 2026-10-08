---
type: tool-guide
status: active
last_updated: 2026-10-07
---

# 特效去背、物件標記局部重繪與 Idle 首尾量測

這頁是 `vfx_alpha_tools.py`（`gameart.py vfx`）與 `generate.py video_inpaint` 的操作契約和證據入口。研究過程與完整數據見 [`experiences/2026-10-07-vfx-research/`](../experiences/2026-10-07-vfx-research/design.md)。所有輸出都是 candidate（[R1](../rules/candidate-review.md)）。

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

### 2.1 指定物件並追蹤整支影片

**預設：SAM3 固定 template（`gameart.py run`）**，詳見 [sam3-track reference](../../../skills/comfyui-video-layers/references/sam3-track.md)。

```text
gameart.py vfx keyframes --video <src.mp4> --frames 0 --output-dir <dir>/keyframes      # 抽第 0 幀
mask_session.py create --image <dir>/keyframes/frame_00000.png --output-dir <dir>      # 把 EDITOR_URL 給美術，只塗要改的物件
mask_session.py fetch --session-id <id> --output-dir <dir>                             # 取得 mask_editor.png
gameart.py run video/sam3/track-mask --set source_video=<src.mp4> --set seed_mask=<dir>/mask_editor.png --preflight
gameart.py run video/sam3/track-mask --set source_video=<src.mp4> --set seed_mask=<dir>/mask_editor.png
    # 或 video/sam3/track-text --set track_text=<英文名詞>；遮罩在 <run>/outputs/masks/，預覽在 <run>/keyframes/mask_preview.png
gameart.py vfx mask-preview --video <src.mp4> --masks <run>/outputs/masks --output <dir>/mask_preview.png   # 需要其他取樣幀時
```

- 手繪起手時「塗多少就追多少」：只塗要改的部分，不要塗到手或尾巴。只要塗第 0 幀，不需要補塗中段幀。隨手框一個方塊不可用。
- 文字起手時名詞要具體：實測 `hammer` 在第 0–1 幀只抓到握柄，`mallet` 每一幀都正確。
- runner 輸出的遮罩是 R=G=B 的 RGB 灰階 PNG，`video_inpaint` 和 `gameart.py vfx` 都可以直接讀。
- 外圍光點等想一起改的東西要一起塗，或另外追蹤後再合併；不在遮罩內的不會被改。

**備用：SAM2.1（video_layers）**。只在 SAM3 不可用時使用。需要在中段加修正幀；實測只塗第 0 幀時，第 14 幀以後會把尾巴也選進去。

```text
gameart.py vfx keyframes --video <src.mp4> --frames 0,<中段幀> --output-dir <dir>/keyframes
gameart.py vfx segment-plan --video <src.mp4> --mask 0=<mask_editor.png> [--mask <幀>=<mask_editor.png>] --output-dir <dir>/plan
video_layers.py run --config <local_config.json> --plan <dir>/plan/segment_plan.json --output-dir <dir>/segment
gameart.py vfx unpack-masks --segment-dir <dir>/segment --video <src.mp4> --output-dir <dir>/masks
```

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

哪些 task 會鎖首／尾幀、動作怎麼選 task、補邊與 `loop-metrics` 驗收門檻，都寫在 [R3 Idle 錨定](../rules/idle-anchoring.md)。本節只保留量測數據。

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

### 步驟（只用正式入口）

1. **標記道具**：照 2.1 節用 `mask_session.py` 在第 0 幀手繪，只塗要換的部分，不要塗到手。
2. **做母版靜幀**：
   - `generate.py flux2_edit --image <第 0 幀> --prompt "把〔道具〕換成〔新道具〕；角色、姿勢、手、握把、畫風、綠幕保持不變"`，跑 2–3 個 seed，選道具最好、沒改到手和握把的那張。
   - `gameart.py vfx prop-paste --source <第 0 幀> --edited <選中的 FLUX 圖> --mask <mask_editor.png> --output-dir <新資料夾>`：只把新道具貼回原圖，背景用原圖的綠。FLUX 會微幅重畫角色（實測角色區平均差 21.6），所以不要直接用 FLUX 整張圖。
   - 把 `composited.png` 給美術確認，這張就是母版。
3. **整幀套動作**：`generate.py pose_drive --backend h3 --control-type canny --image <母版> --motion-ref <原片> --prompt "<新道具＋動作描述>"`。不要用 `--control-type pose`：骨架裡沒有道具資訊，道具動作會跑掉。
4. **驗收**：整幀都是重新生成的，角色不是逐像素保留，臉、服裝、尾巴要人工比對；快速動作的幀可能有動態模糊。

`prop-paste` 只適用綠幕素材。選取範圍是：手繪遮罩擴張 `--grow`（預設 6 px），加上新道具在 `--near`（預設 30 px）內的非綠像素，再排除原圖在遮罩外的角色像素。新道具以 unmix＋despill 去背後疊到原圖綠色上；選取外的像素會由程式檢查是否逐 byte 不變。

### 2026-10-07 實測（Skye 召槌 FINAL → 純木槌，RTX 4080）

| 路線 | 結果 |
|---|---|
| `video_inpaint` replace（只有文字描述，沒有母版） | 遮罩外 0 變動；但快速揮動時糊成一團、槌頭形狀歪扭、沒有描邊、和握把接不起來、遮罩外的光點還留著。**不採用** |
| `video_inpaint` keep | 保留原本的金框和晶窗，只把顏色改成橘金色，不像木頭。**不採用** |
| SDXL `inpaint` 做母版（denoise 1.0，綠幕素材） | 綠色滲進木頭、木頭變成扁平色塊、描邊髒。**不採用** |
| `flux2_edit` 做母版＋`vfx prop-paste` 疊回原圖的綠幕 | 木紋清楚、描邊和角色一致、背景綠色均勻（貼回區平均 (0.5, 253.6, 0.7)，原圖 (0, 254, 0)）。正式指令的輸出和實驗時的母版逐像素相同。採用為母版 |
| **H3 `pose_drive` canny**（母版＋原片） | 動作和原片幾乎一致，木槌前後穩定，光點自然消失；768² × 56 幀，耗時 294.8 秒，技術 pass。**最佳 candidate** |
| H3 `pose_drive` pose | 道具舉起的時間和位置跑掉 |
| SCAIL-2 動畫模式（只是比較測試，不是流程步驟；固定範本，原片先轉 16 FPS、取 33 幀） | 動作有跟上，但背景變成藍紫色斑塊、無法去背，還把原片光點畫成白色，只有 384². **不適合綠幕素材** |

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
| SAM3 用第 0 幀手繪遮罩（`SAM3_VideoTrack.initial_mask`，不給文字） | 塗多少就追多少，從頭到尾不會自己修正；使用者實際手繪的遮罩只追到槌頭和槌柄，握把、手、尾巴都沒被選進去，7.4 秒 |
| SAM3 用隨手框的方塊當第 0 幀遮罩 | 前段把背景和整個角色都選進去，不可用 |

SAM3 追蹤已做成固定 template（`templates/video/sam3/track-{mask,text}/`，2026-10-07 前放在 `skills/comfyui-video-layers/assets/`），以 `gameart.py run` 執行。2026-10-07 runner 出現前的直接 HTTP smoke：遮罩版 56 幀，和實驗遮罩平均 IoU 0.998；文字版 `mallet` 56 幀，IoU 1.0（`output/experiments/vfx-sam3-graph-smoke-20261007/smoke.json`）。研究用腳本放在 [`experiences/2026-10-07-vfx-research/scripts/`](../experiences/2026-10-07-vfx-research/scripts/README.md)，不是產線入口。2026-10-08 Windows 以 runner 跑 track-mask（同一支 56 幀）：GPU 7.896 秒、56 張 1024² 遮罩，技術檢查通過。
