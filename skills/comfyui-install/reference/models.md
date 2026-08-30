# 模型清單(依 tier 分)

`skills/comfyui-install/SKILL.md` 步驟 8 指向這裡——先確認 `device_config.json` 的 `tier` 落在哪個 family,再往下看對應的段落。

**這件事不是只有底模(checkpoint)要跟著 tier 換,ControlNet/IPAdapter/CLIP Vision 全部都是跟底模綁定的,底模架構變了,這些都要跟著換成對應版本,不能只換 checkpoint、其他照抄。**

> **這張表是安裝流程的模型家族、檔名與來源基準,不是 hash-level 的可重現版本 manifest。** 裝機時只管照表裝,不要因為你知道有更新的模型就自作主張換掉——不同人在不同時間裝出來的美術基準要一致,是這整條產線存在的意義。實際可重現的 ComfyUI/custom node commit、套件版本與模型 SHA-256 以 [`docs/tested-versions.md`](../../../docs/tested-versions.md) 為準；XU-Nano-PC 的 manifest 已完成 verified capture，其他機器若仍是 `pending_on_installed_machine`，表格中的日期、大小與檔名不可單獨被宣稱為已鎖定版本。真的想評估要不要升級,用 `skills/comfyui-pipeline-review/SKILL.md`,那是獨立於安裝流程之外、需要使用者明確觸發跟核准的另一件事。

## `sdxl_high` / `sdxl` / `sdxl_light` tier(SDXL 家族,目前唯一實際驗證過的組合)

下載到 `<ComfyUI 安裝路徑>/models/<子資料夾>/`,已存在的檔案跳過:

| 模型 | 子資料夾 | 檔名 | 下載來源 | 概估大小 | 用途 | 最後確認日期 |
|---|---|---|---|---|---|---|
| SDXL base | `checkpoints` | `sd_xl_base_1.0.safetensors` | `https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors` | ~6.5GB | 第 3~6 章底模 | 2026-07-29 |
| ControlNet Canny (SDXL) | `controlnet` | `controlnet-canny-sdxl-1.0.safetensors` | `https://huggingface.co/lllyasviel/sd_control_collection/resolve/main/diffusers_xl_canny_full.safetensors` | ~2.5GB | 第 7 章,`generate.py --control-type canny`(預設) | 2026-07-29 |
| ControlNet Depth (SDXL) | `controlnet` | `controlnet-depth-sdxl-1.0.safetensors` | `https://huggingface.co/lllyasviel/sd_control_collection/resolve/main/diffusers_xl_depth_full.safetensors` | ~2.5GB | 第 7 章,`generate.py --control-type depth` | 2026-08-17 |
| ControlNet OpenPose (SDXL) | `controlnet` | `controlnet-openpose-sdxl-1.0.safetensors` | `https://huggingface.co/thibaud/controlnet-openpose-sdxl-1.0/resolve/main/OpenPoseXL2.safetensors` | ~4.7GB(fp32,檔案偏大是正常的) | 第 7 章,`generate.py --control-type pose` | 2026-08-17 |
| IPAdapter Plus (SDXL) | `ipadapter` | `ip-adapter-plus_sdxl_vit-h.safetensors` | `https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors` | ~0.85GB | 第 8 章 | 2026-07-29 |
| CLIP Vision (ViT-H) | `clip_vision` | `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | `https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors` | ~2.5GB | 第 8 章。**注意路徑是 `models/image_encoder`,不是 `sdxl_models/image_encoder`——後者是 bigG 版,維度不同,裝錯會在 `IPAdapterAdvanced` 執行期噴 shape mismatch** | 2026-07-29 |
| BiRefNet 去背 | `background_removal` | `birefnet.safetensors` | `https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors` | ~0.9GB | `generate.py --remove-bg` 用,跟底模架構無關,任何 tier 都用這個 | 2026-07-29 |
| 4x-UltraSharp 放大模型 | `upscale_models` | `4x-UltraSharp.pth` | `https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth` | ~67MB | `generate.py upscale` 用,跟底模架構無關,任何 tier 都用這個 | 2026-08-17 |

VRAM 較緊張時(`sdxl_light` tier),Depth/OpenPose 這兩個 ControlNet 檔案較大(共約 7GB),可以先跳過,等使用者真的需要姿勢/深度控制再補裝。

## 選用風格底模(`generate.py` 的 `--style`,選配)

**不是基本配備,只有使用者主動要用 `--style` 切換風格才裝。** 只適用 SDXL 家族 tier(`sdxl_high`/`sdxl`/`sdxl_light`),`sd15` 機器不要提。裝法跟裝表格一的 SDXL 底模一樣,下載到 `<ComfyUI 安裝路徑>/models/checkpoints/`,不用額外裝 ControlNet/IPAdapter/CLIP Vision(這幾個都是綁 SDXL 架構,不是綁特定微調版,現有那份繼續共用)。

| `--style` 值 | 風格方向 | Checkpoint | 概估大小 | 授權注意事項 | 最後確認日期 |
|---|---|---|---|---|---|
| `realistic` | 寫實 | Juggernaut XL Ragnarok(`juggernautXL_ragnarok.safetensors`,實際檔名以下載頁為準) | ~6.4~6.9GB | CreativeML Open RAIL-M,個人/創作免費;**商用(尤其做成付費 API/SaaS)需另外聯繫 RunDiffusion 洽談授權**,單純內部用來產遊戲美術素材通常不算這個限制範圍,但使用者自己要再覆核一次 | 2026-08-19 |
| `illustration` | 插畫/概念藝術 | Illustrious XL v1.1(官方 `OnomaAIResearch/Illustrious-XL-v1.1`,檔名 `Illustrious-XL-v1.1.safetensors`) | ~6.9GB | **2026-08-19 更正**:之前記成 MIT 是查到非官方鏡像倉庫自己標的授權,不是真實條款。官方倉庫標示 `sdxl-license`(沿用 Stability AI 的 SDXL 授權條款),同系列其他版本授權不同(v0 是 Fair AI Public License 1.0-SD,限制跟 Pony 類似;v2.0 是 CreativeML OpenRAIL-M)——**下載前務必自己去官方頁面看一次完整條款,不要沿用這裡的摘要當定論** | 2026-08-19 |
| `anime` | 二次元/動漫 | Pony Diffusion V6 XL(`ponyDiffusionV6XL_v6StartWithThisOne.safetensors`,實際檔名以下載頁為準,另有 VAE `sdxl_vae.safetensors` ~335MB) | ~6.9GB | Fair AI Public License 1.0-SD,**限制「monetized web service/app 的商用推論」**,對外服務化需聯繫 purplesmart.ai;單純內部用來產遊戲美術素材通常不算這個限制範圍,但使用者自己要再覆核一次 | 2026-08-19 |

### 使用眉角(實測發現才記,不是預先猜測;沒列出的部分代表還沒實測過)

- **`anime`(Pony Diffusion V6 XL)**:2026-08-19 實測確認,**prompt 沒帶 `score_9, score_8_up, score_7_up`(至少 3 個 score 標籤)這組 Pony 官方建議的品質標籤時,輸出會不穩定(實測出現灰階、跟描述無關的圓形徽章構圖);補上這組標籤後同一個 prompt 出圖正常,色彩/構圖都符合預期。** 已排除 VAE 是原因——原本懷疑跟 checkpoint 內建 VAE vs 建議搭配的獨立 `sdxl_vae.safetensors`(已下載到 `models/vae/`,`generate.py` 目前沒接這顆,一律用 `CheckpointLoaderSimple` 內建 VAE)有關,但隔離變數測試(只加 score 標籤、不改 VAE)就解決了,不是 VAE 問題,外部 VAE 那顆先留著沒必要接進程式碼
- **`realistic`(Juggernaut XL Ragnarok)**:2026-08-19 實測,不需要特殊 prompt 慣例,預設參數直接出圖正常。官方建議解析度是 832x1216 直式(跟這台機器 `sdxl` tier 預設的 1024x1024 不同),想更貼近官方建議可以另外帶 `--width 832 --height 1216`
- **`illustration`(Illustrious XL v1.1)**:2026-08-19 實測,`--rating safe` 正常出圖,沒有出現 `anime` 那種畫質問題。官方文件說分級標籤幾乎是必填,沒加可能結果不穩定,細節見上面表格 `--rating` 相關說明

下載來源查 Civitai/Hugging Face 官方頁面確認實際檔名跟連結,不要用上面括號裡的檔名當成確定的下載網址去憑空組合。使用者可以只選其中幾個風格,不用三個全裝——**動手下載任何一顆之前,先告知該顆的概估大小,加總這台機器目前已用空間 + 想裝的這幾顆,確認硬碟還有沒有足夠可用空間**,原則同下面「硬碟空間概估」那段。

### 硬碟空間概估(裝機前先跟使用者說清楚)

| 項目 | 概估大小 | 是否必要 |
|---|---|---|
| ComfyUI 原始碼(git clone) | ~0.3GB | 必要 |
| Python 虛擬環境(torch + CUDA + 其他依賴套件) | ~6~8GB | 必要 |
| 上面這張表全部裝齊(SDXL tier) | ~20GB | 必要(VRAM 吃緊的 `sdxl_light` 可先跳過 Depth/OpenPose,省 ~7GB) |
| LoRA 訓練工具(`kohya_ss` + 它自己的 `uv sync` 依賴,選配) | ~5~8GB | 選配,只有使用者明確要練 LoRA 才裝 |
| 選用風格底模(`--style`,見上面「選用風格底模」表格,3 顆全裝) | ~20GB(每顆 ~6.5~7GB) | 選配,只有使用者明確要用 `--style` 切換風格才裝,可以只選其中幾個 |
| **合計(不含 LoRA 訓練工具、不含風格底模)** | **約 26~28GB** | — |
| **合計(含 LoRA 訓練工具、含風格底模 3 顆全裝)** | **約 51~64GB** | — |

**這是概估值,不是精確保證**——實際檔案大小以下載當下來源網站顯示的為準,Python 依賴套件版本更新也會讓虛擬環境大小浮動。裝機前把這個範圍念給使用者聽,提醒**硬碟至少要留 30GB 以上可用空間**比較保險,不要裝到一半才發現空間不夠中斷——那樣通常需要手動清理已下載一半的檔案才能重來,比事前確認空間麻煩很多。

## 選用影片模型(`generate.py img2video` / `character_video`,選配)

**不是每台機器的基本配備,只有使用者明確要產短片才裝。** 跟 SDXL 底模/ControlNet/IPAdapter **完全不相容**,是另一組 UNET/VAE/文字編碼器,不要塞進上面的 SDXL 表格、也不要假設 `CKPT` 能拿來產影片。

以下是 Windows / RTX 4080 的歷史安裝與實測紀錄(路徑相對於 `<ComfyUI 安裝路徑>/models/`)，不是目前 repository 可直接重建的鎖定檔。當時的檔名、大小與日期可作為辨識線索；XU-Nano-PC 的實際版本、hash 與 smoke 已填入 [`docs/tested-versions.md`](../../../docs/tested-versions.md) 的 `verified` manifest，其他已安裝機器仍須自行擷取並從 `pending_on_installed_machine` 完成 smoke 後再改為 `verified`:

| 用途 | 子資料夾 | 檔名 | 下載來源 | 實際大小 | 最後確認日期 |
|---|---|---|---|---|---|
| Wan 2.2 5B UNET | `diffusion_models` | `wan2.2_ti2v_5B_fp16.safetensors` | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` `split_files/diffusion_models/` | 9.31 GiB | 2026-08-26 |
| Wan 2.2 Fun Control 5B UNET(wan 的 control_video 能力) | `diffusion_models` | `wan2.2_fun_control_5B_bf16.safetensors` | 同上 `split_files/diffusion_models/` | 9.32 GiB | 2026-08-27 |
| Wan 2.2 VAE | `vae` | `wan2.2_vae.safetensors` | 同上 `split_files/vae/` | 1.31 GiB | 2026-08-26 |
| Wan / 共用文字編碼器 | `text_encoders` | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `Comfy-Org/Wan_2.1_ComfyUI_repackaged` `split_files/text_encoders/` | 6.27 GiB | 2026-08-26 |
| MiniMax H3 UNET(I2V / 首尾幀) | `diffusion_models` | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `Comfy-Org/MiniMax-H3` `diffusion_models/` | 19.53 GiB | 2026-08-26 |
| MiniMax H3 UNET(h3 的 character_ref / control_video) | `diffusion_models` | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 同上 `diffusion_models/` | 19.53 GiB | 2026-08-27 |
| MiniMax H3 文字編碼器 | `text_encoders` | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 同上 `text_encoders/` | 14.61 GiB | 2026-08-26 |
| MiniMax H3 video VAE | `vae` | `minimax_h3_video_vae_fp16.safetensors` | 同上 `vae/` | 4.85 GiB | 2026-08-26 |
| MiniMax H3 audio VAE | `vae` | `minimax_h3_audio_vae_fp32.safetensors` | 同上 `vae/` | 0.56 GiB | 2026-08-26 |

Wan + H3 FL2VA 約 56.4 GiB;加上 Ref2VA 約 76 GiB。Ref2VA 跟 FL2VA 是不同 UNET,h3 的 `character_ref` / `control_video` 不能拿 FL2VA 頂替。h3 的 `pose_drive` 也用這顆 Ref2VA,不用再下 Fun ControlNet。`camera_move` 不另外下模型(走已有 I2V backend)。對照見 `skills/comfyui-video-gen/reference/backends.md`。torch 需 cu130 才能走 H3 的 `int8_convrot`(這台已是 2.13.0+cu130)。LTX-2.5 本輪不裝(Hugging Face gated)。下載前先講空間,原則同風格底模。

模型安裝完成後，若要開影片能力，執行 `tools_src/detect_video_capabilities.py` 產生 machine-specific `video_capabilities.json`。它會把每個 backend 的模型路徑與可用 capability 寫入設定，但不會計算大型檔案 hash，也不會下載缺檔；可重現的 SHA-256 仍要在 smoke test 收尾時填入 `docs/tested-versions.md`。`generate.py` 每次影片 task 都會重新檢查模型檔案、runtime 與 ComfyUI nodes，避免把「檔案曾經存在」誤當成目前可跑。

## `sd15` tier(VRAM < 8GB,SD1.5 家族)

**這條路線目前這個 repo 完全沒有實機驗證過**。`tools_src/generate.py` 裡 `CONTROLNET_MODELS`/`ip-adapter_file`/`clip_name` 仍指向 SDXL 版本，因此 CLI 目前會對需要 ControlNet/IPAdapter 的 SD1.5 組合先 fail-fast（提早拒絕）；只有繞過 capability gate、直接把 SDXL add-on graph 跟 SD1.5 底模混用時，才會因架構不符發生 shape mismatch。遇到這個 tier 時:

1. 先跟使用者說清楚這是還沒驗證過的路線,不是「裝了就一定動」
2. `checkpoint` 換成 `device_config.json` 裡指定的 SD1.5 系列模型(如 DreamShaper),下載來源跟使用者確認,不要臆測網址
3. ControlNet/IPAdapter/CLIP Vision 路徑目前會被 capability gate 主動拒絕；只下載對應的 **SD1.5 版本**並不會自動開通，不能把「模型已安裝」當成「task 已支援」
4. 真正新增 SD1.5 add-on 支援時，要照 `skills/comfyui-new-tool-checklist/SKILL.md` 完整處理：建立依 tier 選擇的模型映射、更新 capability gate、補 graph/CLI 測試、完成 ComfyUI 實機 smoke test，再同步文件。只修改 `CONTROLNET_MODELS` 常數仍不完整，IPAdapter/CLIP Vision 與 gate 也必須一起處理
