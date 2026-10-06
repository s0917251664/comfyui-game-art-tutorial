# 模型清單（依選定設定檔與獨立能力分）

`skills/comfyui-install/SKILL.md` 步驟 8 指向這裡——先依安裝流程確認選定的 image profile，再看對應 family；tier 只提供預設建議，大機器選 `sd15_light` 時也應使用 SD1.5 清單。影片與 FLUX.2 另看各自段落。

**這件事不是只有底模(checkpoint)要跟著 tier 換,ControlNet/IPAdapter/CLIP Vision 全部都是跟底模綁定的,底模架構變了,這些都要跟著換成對應版本,不能只換 checkpoint、其他照抄。**

> **這張表是安裝流程的模型家族、檔名與來源基準,不是 hash-level 的可重現版本 manifest。** 裝機時只管照表裝,不要因為你知道有更新的模型就自作主張換掉——不同人在不同時間裝出來的美術基準要一致,是這整條產線存在的意義。實際可重現的 ComfyUI/custom node commit、套件版本與模型 SHA-256 以 `docs/tested-versions.md` 為準；XU-Nano-PC 的 manifest 已完成 verified capture，其他機器若仍是 `pending_on_installed_machine`，表格中的日期、大小與檔名不可單獨被宣稱為已鎖定版本。真的想評估要不要升級,用 `skills/comfyui-pipeline-review/SKILL.md`,那是獨立於安裝流程之外、需要使用者明確觸發跟核准的另一件事。

## `sdxl_high` / `sdxl` / `sdxl_light` tier(SDXL 家族,目前唯一實際驗證過的組合)

下載到 `<ComfyUI 安裝路徑>/models/<子資料夾>/`,已存在的檔案跳過:

| 模型 | 子資料夾 | 檔名 | 下載來源 | 概估大小 | 用途 | 最後確認日期 |
|---|---|---|---|---|---|---|
| SDXL base | `checkpoints` | `sd_xl_base_1.0.safetensors` | `https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors` | ~6.5GB | 第 3~6 章底模 | 2026-07-29 |
| ControlNet Canny (SDXL) | `controlnet` | `controlnet-canny-sdxl-1.0.safetensors` | `https://huggingface.co/lllyasviel/sd_control_collection/resolve/main/diffusers_xl_canny_full.safetensors` | ~2.5GB | 第 7 章,`generate.py --control-type canny`(預設) | 2026-07-29 |
| ControlNet Depth (SDXL) | `controlnet` | `controlnet-depth-sdxl-1.0.safetensors` | `https://huggingface.co/lllyasviel/sd_control_collection/resolve/main/diffusers_xl_depth_full.safetensors` | ~2.5GB | 第 7 章,`generate.py --control-type depth` | 2026-08-17 |
| ControlNet OpenPose (SDXL) | `controlnet` | `controlnet-openpose-sdxl-1.0.safetensors` | `https://huggingface.co/thibaud/controlnet-openpose-sdxl-1.0/resolve/main/OpenPoseXL2.safetensors` | ~4.7GB(fp32,檔案偏大是正常的) | 第 7 章,`generate.py --control-type pose` | 2026-08-17 |
| ControlNet Union SDXL ProMax（實驗） | `controlnet` | `xinsir-controlnet-union-sdxl-1.0-promax.safetensors` | `https://huggingface.co/xinsir/controlnet-union-sdxl-1.0/resolve/main/diffusion_pytorch_model_promax.safetensors` | 2,513,342,408 bytes | 只供 `pose_only --control-backend union` A/B；需 ComfyUI Core `SetUnionControlNetType` | 2026-09-01 |
| IPAdapter Plus (SDXL) | `ipadapter` | `ip-adapter-plus_sdxl_vit-h.safetensors` | `https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors` | ~0.85GB | 第 8 章 | 2026-07-29 |
| CLIP Vision (ViT-H) | `clip_vision` | `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | `https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors` | ~2.5GB | 第 8 章。**注意路徑是 `models/image_encoder`,不是 `sdxl_models/image_encoder`——後者是 bigG 版,維度不同,裝錯會在 `IPAdapterAdvanced` 執行期噴 shape mismatch** | 2026-07-29 |
| BiRefNet 去背 | `background_removal` | `birefnet.safetensors` | `https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors` | ~0.9GB | `generate.py --remove-bg` 用,跟底模架構無關,任何 tier 都用這個 | 2026-07-29 |
| 4x-UltraSharp 放大模型 | `upscale_models` | `4x-UltraSharp.pth` | `https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth` | ~67MB | `generate.py upscale` 用,跟底模架構無關,任何 tier 都用這個 | 2026-08-17 |

VRAM 較緊張時(`sdxl_light` tier),Depth/OpenPose 這兩個 ControlNet 檔案較大(共約 7GB),可以先跳過,等使用者真的需要姿勢/深度控制再補裝。

Union 是額外的實驗權重，**不會取代**上面三顆正式模型。ProMax 權重的官方 SHA-256 為 `9fae2e50cb431bfcbe05822b59ec2228df545ef27f711dea8949e9f4ed9f7cdc`；安裝或更新後，必須先在 `/object_info` 確認 `ControlNetLoader` 看得到檔名與 `SetUnionControlNetType` 節點，再允許上傳參考圖。若要擴大到 `character_action`、`guided_inpaint` 或 `icon_asset`，需另做各 task 的實機回歸，不能只因 `pose_only` smoke 成功而開通。

### 選用 BiRefNet A/B benchmark 權重

只有明確要重新評估去背模型時才裝，不是正式產線必需品。四個 Hugging Face repository 各自下載完整 snapshot 到 `<ComfyUI>/models/background_removal_variants/<repo 名>/`；每顆 `model.safetensors` 都是 444,473,596 bytes。它們與 SDXL／FLUX 架構無關，但官方 Transformers 路徑需要 `timm`。2026-09-01 的已驗證環境鎖定 `timm==1.0.29`；官方 requirements 同時列出 `numpy<2`，現行 ComfyUI 是 NumPy 2.4.4，雖然本輪推論成功，正式接線前仍需視為相容性風險。

| 變體 | Repository | 原生 benchmark 尺寸 | 用途 | 最後確認日期 |
|---|---|---:|---|---|
| general baseline | `ZhengPeng7/BiRefNet` | 1024 | 與現行 general 比較 | 2026-09-01 |
| HR | `ZhengPeng7/BiRefNet_HR` | 2048 | 高解析一般前景分割 | 2026-09-01 |
| HR-matting | `ZhengPeng7/BiRefNet_HR-matting` | 2048 | 高解析柔邊／半透明 matting | 2026-09-01 |
| dynamic | `ZhengPeng7/BiRefNet_dynamic` | 不固定；本 benchmark 上限 2304 | 多解析度輸入 | 2026-09-01 |

目前 ComfyUI v0.34.0 的 Core `LoadBackgroundRemovalModel` 會把所有背景移除權重固定前處理成 1024×1024，因此不能只把 HR 檔案丟進 `background_removal/` 就宣稱完成 2048 推論。本專案以 `tools_src/benchmark_birefnet.py` 走官方本機 Transformers 載入做 A/B；benchmark 通過前不修改正式 `--remove-bg`。

## 選用風格底模(`generate.py` 的 `--style`,選配)

**不是基本配備,只有使用者主動要用 `--style` 切換風格才裝。** 只適用 SDXL 家族 tier(`sdxl_high`/`sdxl`/`sdxl_light`),`sd15` 機器不要提。裝法跟裝表格一的 SDXL 底模一樣,下載到 `<ComfyUI 安裝路徑>/models/checkpoints/`,不用額外裝 ControlNet/IPAdapter/CLIP Vision(這幾個都是綁 SDXL 架構,不是綁特定微調版,現有那份繼續共用)。

| `--style` 值 | 風格方向 | Checkpoint | 概估大小 | 授權注意事項 | 最後確認日期 |
|---|---|---|---|---|---|
| `realistic` | 寫實 | Juggernaut XL Ragnarok(`juggernautXL_ragnarok.safetensors`,實際檔名以下載頁為準) | ~6.4~6.9GB | CreativeML Open RAIL-M,個人/創作免費;**商用(尤其做成付費 API/SaaS)需另外聯繫 RunDiffusion 洽談授權**,單純內部用來產遊戲美術素材通常不算這個限制範圍,但使用者自己要再覆核一次 | 2026-08-19 |
| `illustration` | 插畫/概念藝術 | Illustrious XL v1.1(官方 `OnomaAIResearch/Illustrious-XL-v1.1`,檔名 `Illustrious-XL-v1.1.safetensors`) | ~6.9GB | **2026-08-19 更正**:之前記成 MIT 是查到非官方鏡像倉庫自己標的授權,不是真實條款。官方倉庫標示 `sdxl-license`(沿用 Stability AI 的 SDXL 授權條款),同系列其他版本授權不同(v0 是 Fair AI Public License 1.0-SD,限制跟 Pony 類似;v2.0 是 CreativeML OpenRAIL-M)——**下載前務必自己去官方頁面看一次完整條款,不要沿用這裡的摘要當定論** | 2026-08-19 |
| `anime` | 二次元/動漫 | Pony Diffusion V6 XL(`ponyDiffusionV6XL_v6StartWithThisOne.safetensors`,實際檔名以下載頁為準,另有 VAE `sdxl_vae.safetensors` ~335MB) | ~6.9GB | Fair AI Public License 1.0-SD,**限制「monetized web service/app 的商用推論」**,對外服務化需聯繫 purplesmart.ai;單純內部用來產遊戲美術素材通常不算這個限制範圍,但使用者自己要再覆核一次 | 2026-08-19 |

### 使用眉角

已搬到 [art/profiles/sdxl-standard.md](../art/profiles/sdxl-standard.md)「風格變體」：調校經驗綁在模型設定檔上，不跟安裝清單放在一起。重點仍是 **`--style anime` 的 prompt 開頭一定要加 `score_9, score_8_up, score_7_up`**。

下載來源查 Civitai/Hugging Face 官方頁面確認實際檔名跟連結,不要用上面括號裡的檔名當成確定的下載網址去憑空組合。使用者可以只選其中幾個風格,不用三個全裝——**動手下載任何一顆之前,先告知該顆的概估大小,加總這台機器目前已用空間 + 想裝的這幾顆,確認硬碟還有沒有足夠可用空間**,原則同下面「硬碟空間概估」那段。

### 硬碟空間概估(裝機前先跟使用者說清楚)

| 項目 | 概估大小 | 是否必要 |
|---|---|---|
| ComfyUI 原始碼(git clone) | ~0.3GB | 必要 |
| Python 虛擬環境(torch + CUDA + 其他依賴套件) | ~6~8GB | 必要 |
| SDXL 正式模型全套（不含 Union） | ~20GB | 底模必要，其餘依選定 task 安裝；所有 tier 均可省略不用的選配模型 |
| LoRA 訓練工具(`kohya_ss` + 它自己的 `uv sync` 依賴,選配) | ~5~8GB | 選配,只有使用者明確要練 LoRA 才裝 |
| 選用風格底模(`--style`,見上面「選用風格底模」表格,3 顆全裝) | ~20GB(每顆 ~6.5~7GB) | 選配,只有使用者明確要用 `--style` 切換風格才裝,可以只選其中幾個 |
| **合計(不含 LoRA 訓練工具、不含風格底模)** | **約 26~28GB** | — |
| **合計(含 LoRA 訓練工具、含風格底模 3 顆全裝)** | **約 51~64GB** | — |

**這是概估值,不是精確保證**——實際檔案大小以下載當下來源網站顯示的為準,Python 依賴套件版本更新也會讓虛擬環境大小浮動。裝機前把這個範圍念給使用者聽,提醒**硬碟至少要留 30GB 以上可用空間**比較保險,不要裝到一半才發現空間不夠中斷——那樣通常需要手動清理已下載一半的檔案才能重來,比事前確認空間麻煩很多。

## 選用 FLUX.2 Klein 4B PoC（`flux2_concept` / `flux2_edit`）

**這是跟 SDXL 平行的實驗性圖片 backend，不是 checkpoint 替換。** 只有使用者明確核准 FLUX.2 PoC 才安裝；它不受 `device_config.json` 的 SDXL tier 自動選擇，也不能共用 SDXL ControlNet、IPAdapter、LoRA、`--style` checkpoint 或 negative prompt 契約。本機路線以 12GB+ VRAM 為實驗門檻，仍須逐台實測峰值 VRAM；未通過 smoke 前不可宣稱可用。

| 用途 | 子資料夾 | 檔名 | 官方下載來源 | 實際大小（2026-09-01 HEAD） | 授權／用途 | 最後確認日期 |
|---|---|---|---|---:|---|---|
| FLUX.2 Klein 4B distilled FP8 | `diffusion_models` | `flux-2-klein-4b-fp8.safetensors` | `https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors` | 4,070,624,520 bytes | Apache 2.0；`flux2_concept` 固定 4 steps | 2026-09-01 |
| FLUX.2 Klein 4B base FP8 | `diffusion_models` | `flux-2-klein-base-4b-fp8.safetensors` | `https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4b-fp8/resolve/main/flux-2-klein-base-4b-fp8.safetensors` | 4,089,498,488 bytes | Apache 2.0；`flux2_edit` 固定 20 steps | 2026-09-01 |
| Qwen3 4B text encoder | `text_encoders` | `qwen_3_4b.safetensors` | `https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors` | 8,044,982,048 bytes | 兩個 FLUX.2 task 共用；`CLIPLoader type=flux2` | 2026-09-01 |
| FLUX.2 VAE | `vae` | `flux2-vae.safetensors` | `https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors` | 336,213,556 bytes | 兩個 FLUX.2 task 共用 | 2026-09-01 |

四個檔案合計 16,541,318,612 bytes（約 15.4 GiB）。下載前先確認剩餘空間；下載到暫存 `.part`，檔案大小與 SHA-256 驗證後才改成正式檔名。需要 ComfyUI Core 提供 `EmptyFlux2LatentImage`、`Flux2Scheduler` 與 `ReferenceLatent`；不需額外 custom node。精確 ComfyUI commit、模型 SHA-256 與 smoke 證據以 `docs/tested-versions.md` 為準。

## 選用影片模型(`generate.py img2video` / `character_video`,選配)

**不是每台機器的基本配備,只有使用者明確要產短片才裝。** 跟 SDXL 底模/ControlNet/IPAdapter **完全不相容**,是另一組 UNET/VAE/文字編碼器,不要塞進上面的 SDXL 表格、也不要假設 `CKPT` 能拿來產影片。

### ComfyUI Video Layers 使用的 SAM 2.1 small（不是影片生成 backend）

Video Layers 使用的 `facebook/sam2.1-hiera-small` 為短影片遮罩傳播模型，來源為 [Meta 官方 Hugging Face model repository](https://huggingface.co/facebook/sam2.1-hiera-small)，模型程式／文件見 [facebookresearch/sam2](https://github.com/facebookresearch/sam2)。本工具固定 revision `ee5bba1d82bb8749febdf90f45e84b687142ba03`，只讀取既有 Hugging Face cache 並核對 `config.json`、`model.safetensors`、`preprocessor_config.json` 的 hash；不自動下載，也不加入 `video_capabilities.json` 的生成 backend/task。本機實際 runtime pins 見 [Video Layers reference](../../../skills/comfyui-video-layers/references/local-tool.md) 和 [tested-versions](../../tested-versions.md)；它們是此機 preflight gate，未宣稱其他平台相容。新機若沒有快取，按需回到安裝技能及使用者授權流程，勿由日常 preflight 觸發下載。

以下是 Windows / RTX 4080 的歷史安裝與實測紀錄(路徑相對於 `<ComfyUI 安裝路徑>/models/`)，不是目前 repository 可直接重建的鎖定檔。當時的檔名、大小與日期可作為辨識線索；XU-Nano-PC 的實際版本、hash 與 smoke 已填入 `docs/tested-versions.md` 的 `verified` manifest，其他已安裝機器仍須自行擷取並從 `pending_on_installed_machine` 完成 smoke 後再改為 `verified`:

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

Wan I2V + H3 FL2VA 約 56.4 GiB；加上 Ref2VA 約 76 GiB；若再安裝表內 Wan Fun Control 5B，另加 9.32 GiB，全表約 85.3 GiB。Ref2VA 跟 FL2VA 是不同 UNET,h3 的 `character_ref` / `control_video` 不能拿 FL2VA 頂替。h3 的 `pose_drive` 也用這顆 Ref2VA,不用再下 Fun ControlNet。`camera_move` 不另外下模型(走已有 I2V backend)。對照見 `skills/comfyui-video-gen/reference/backends.md`。torch 需 cu130 才能走 H3 的 `int8_convrot`(這台已是 2.13.0+cu130)。LTX-2.5 本輪不裝(Hugging Face gated)。下載前先講空間,原則同風格底模。

模型安裝完成後，若要開影片能力，執行 `tools_src/detect_video_capabilities.py` 產生 machine-specific `video_capabilities.json`。它會把每個 backend 的模型路徑與可用 capability 寫入設定，預設只記 size；明確帶 `--hash-models` 才計算 SHA-256，也不會下載缺檔；可重現的 SHA-256 仍要在 smoke test 收尾時填入 `docs/tested-versions.md`。`generate.py` 每次影片 task 都會重新檢查模型檔案、runtime 與 ComfyUI nodes，避免把「檔案曾經存在」誤當成目前可跑。

## `sd15` tier(VRAM < 8GB,SD1.5 家族)

**這條路線目前這個 repo 完全沒有實機驗證過**。`tools_src/comfyui_pipeline/profiles/sd15_light.json` 模型設定檔目前只有 SD1.5 底模、BiRefNet 與放大模型，沒有任何 ControlNet/IPAdapter/CLIP Vision，因此 CLI 目前會對需要 ControlNet/IPAdapter 的 SD1.5 組合先 fail-fast（提早拒絕）；只有繞過 capability gate、直接把 SDXL add-on graph 跟 SD1.5 底模混用時，才會因架構不符發生 shape mismatch。遇到這個 tier 時:

1. 先跟使用者說清楚這是還沒驗證過的路線,不是「裝了就一定動」
2. 依選定的 `sd15_light.json` 安裝 `dreamshaper_8.safetensors`；不要從較大機器的 `device_config.json` 沿用 SDXL checkpoint。下載來源須確認，不能臆測網址
3. ControlNet/IPAdapter/CLIP Vision 路徑目前會被 capability gate 主動拒絕；只下載對應的 **SD1.5 版本**並不會自動開通，不能把「模型已安裝」當成「task 已支援」
4. 真正新增 SD1.5 add-on 支援時，要照 `skills/comfyui-new-tool-checklist/SKILL.md` 完整處理：在 `sd15_light.json` 補上 SD1.5 版 ControlNet/IPAdapter/CLIP Vision 與對應 `tasks`、更新 capability gate、補 graph/CLI 測試、完成 ComfyUI 實機 smoke test，再同步文件與設定檔的 `validation`。只補 ControlNet 仍不完整，IPAdapter/CLIP Vision 與 gate 也必須一起處理

### `sd15_light` 設定檔的模型與空間

步驟 4b 報空間時用這張表；`sd15_light` 不需要 ControlNet/IPAdapter/CLIP Vision。

| 模型 | 子資料夾 | 檔名 | 概估大小 | 是否必要 |
|---|---|---|---|---|
| SD1.5 底模（DreamShaper 8） | `checkpoints` | `dreamshaper_8.safetensors` | **待確認**：這個 repo 還沒實際下載過，下載前以來源頁面顯示的大小告知使用者，不要自行估算 | 必要 |
| BiRefNet 去背 | `background_removal` | `birefnet.safetensors` | ~0.9GB（同 SDXL 表格，架構無關共用） | 選配；`icon_asset` 與 `--remove-bg` 需要 |
| 4x-UltraSharp 放大模型 | `upscale_models` | `4x-UltraSharp.pth` | ~67MB（同 SDXL 表格） | 選配；`upscale` 需要 |

合計 = DreamShaper 8 實際大小 + 最多約 1GB。實際下載後把確認的大小與日期補回這張表。

## Wan2.2 Animate 原生 workflow（本機已安裝）

此模型組只供 ComfyUI 官方 Wan2.2 Animate UI workflow，不加入 `generate.py` model profile/backend。模型下載由 `output/wan-animate-install/download_models.py` 固定 Hugging Face revision、檔案大小及 SHA-256；2026-10-06 七個新增檔案皆完成 size／SHA-256 驗證，合計 22,634,628,209 bytes（21.08 GiB）。Mix／Move 短片技術 smoke 已通過，內容有身份漂移，仍待人工驗收。已安裝的 UMT5 encoder 依官方 workflow 重用，未由本次腳本下載。

| 用途 | Repository @ 固定 revision | 上游檔案 → ComfyUI 路徑 | Bytes | SHA-256 |
|---|---|---|---:|---|
| Animate 14B FP8 主模型 | `Kijai/WanVideo_comfy_fp8_scaled` @ `033a4e487f60220b3d6e469599a6aebc46e13cee` | `Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors` → `models/diffusion_models/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors` | 18,401,760,586 | `2936b31473a967e7a429a6646bba60e7862d0938e178b58b2a140f391dd5b8e6` |
| Wan2.1 VAE | `Comfy-Org/Wan_2.1_ComfyUI_repackaged` @ `123acf1cc74bccbb9bfff8ac1ee72edc08c2341d` | `split_files/vae/wan_2.1_vae.safetensors` → `models/vae/wan_2.1_vae.safetensors` | 253,815,318 | `2fc39d31359a4b0a64f55876d8ff7fa8d780956ae2cb13463b0223e15148976b` |
| LightX2V 加速 LoRA | `Kijai/WanVideo_comfy` @ `8260d429d19fd7a72304cad059160b95d843913f` | `Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` → `models/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | 738,005,744 | `85c4a61c30e0497aa44b91d93a893b624708461a56fe5485183b28fa07e2dfb3` |
| DWPose 使用之 YOLOX | `yzd-v/DWPose` @ `1a7144101628d69ee7a3768d1ee3a094070dc388` | `yolox_l.onnx` → `custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx` | 216,746,733 | `7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411` |
| Relight LoRA | `Kijai/WanVideo_comfy` @ `8260d429d19fd7a72304cad059160b95d843913f` | `LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors` → `models/loras/WanAnimate_relight_lora_fp16.safetensors` | 1,436,672,440 | `fc646c74c73f4b251f5fd9bc440ef21b03b27305f499966c68b2b3aa31498561` |
| SAM 2 base-plus | `Kijai/sam2-safetensors` @ `f885607d88bb3f9145efa49c3e3c50a9e5bf13eb` | `sam2_hiera_base_plus.safetensors` → `models/sam2/sam2_hiera_base_plus.safetensors` | 323,407,992 | `fa02d9028dcc4859c191f1d3f1ca1f7eefdb85f3b5e746c9ad738f322f3e89e2` |
| CLIP Vision H (FP16) | `Comfy-Org/Wan_2.1_ComfyUI_repackaged` @ `123acf1cc74bccbb9bfff8ac1ee72edc08c2341d` | `split_files/clip_vision/clip_vision_h.safetensors` → `models/clip_vision/clip_vision_h.safetensors` | 1,264,219,396 | `64a7ef761bfccbadbaa3da77366aac4185a6c58fa5de5f589b42a65bcc21f161` |

UMT5 依官方 workflow 使用現有 text encoder；實際檔案由環境檢查確認，並非上述下載腳本的固定 hash 清單。ComfyUI 固定為 `12d5279438bfefc058a269eae805ceab6047777f`；新增 KJNodes `d3cfe21625e5170126ce06fbfcfe1d88108688c3` 與 `ComfyUI-segment-anything-2` `0c35fff5f382803e2310103357b5e985f5437f32`。既有 `comfyui_controlnet_aux` 不變。Python 3.13.9、PyTorch 2.13.0+cu130、RTX 4080 16,376 MiB VRAM／31.1 GiB RAM。詳細安裝與驗證狀態見 [Wan2.2 Animate 安裝紀錄](../video/wan-animate-install.md)。

## SCAIL-2（本機已安裝，2026-10-06）

供 [comfyui-wan-animate 技能](../../../skills/comfyui-wan-animate/SKILL.md)的 SCAIL-2 固定 API templates 使用，不加入 `generate.py` profile/backend。三個檔案皆完成 size／SHA-256 驗證；其餘依賴重用上方 Wan Animate 檔案（VAE 以 `wan_2.1_vae.safetensors` 替代官方範本的 `Wan2_1_VAE_bf16`）。

| 用途 | Repository @ 固定 revision | 上游檔案 → ComfyUI 路徑 | Bytes | SHA-256 |
|---|---|---|---:|---|
| SCAIL-2 14B FP8 主模型 | `Comfy-Org/SCAIL-2` @ `fe3c728bc793ba21ca674688f822afb709ad44fb` | `diffusion_models/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors` → `models/diffusion_models/` 同名 | 17,694,586,857 | `11513b4697ecf566de0cb74660c478f301fb6699a62b10369e91a6ed0fd6b083` |
| SCAIL-2 DPO LoRA | `Comfy-Org/SCAIL-2` @ `fe3c728bc793ba21ca674688f822afb709ad44fb` | `loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors` → `models/loras/` 同名 | 1,226,936,552 | `b106522036f64e50f5f8ae3b808973515ff442cc2fac27b65d875eafb95b89e2` |
| SAM3.1 multiplex | `Comfy-Org/sam3.1` @ `7bb8374780a725b4353ed31f3a9395c9742b5621` | `checkpoints/sam3.1_multiplex_fp16.safetensors` → `models/checkpoints/` 同名 | 1,745,546,848 | `9ba99c92703c2e8b4f47de2d34a539bb8e18923049e238b780d70dbe6368eb03` |
