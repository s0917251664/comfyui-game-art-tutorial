# 模型清單(依 tier 分)

`skills/comfyui-install/SKILL.md` 步驟 8 指向這裡——先確認 `device_config.json` 的 `tier` 落在哪個 family,再往下看對應的段落。

**這件事不是只有底模(checkpoint)要跟著 tier 換,ControlNet/IPAdapter/CLIP Vision 全部都是跟底模綁定的,底模架構變了,這些都要跟著換成對應版本,不能只換 checkpoint、其他照抄。**

> **這張表是刻意鎖定的版本清單,不是「目前最好的選擇」清單。** 裝機時只管照表裝,不要因為你知道有更新的模型就自作主張換掉——不同人在不同時間裝出來的美術基準要一致,是這整條產線存在的意義。真的想評估要不要升級,用 `skills/comfyui-pipeline-review/SKILL.md`,那是獨立於安裝流程之外、需要使用者明確觸發跟核准的另一件事。

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

### 硬碟空間概估(裝機前先跟使用者說清楚)

| 項目 | 概估大小 | 是否必要 |
|---|---|---|
| ComfyUI 原始碼(git clone) | ~0.3GB | 必要 |
| Python 虛擬環境(torch + CUDA + 其他依賴套件) | ~6~8GB | 必要 |
| 上面這張表全部裝齊(SDXL tier) | ~20GB | 必要(VRAM 吃緊的 `sdxl_light` 可先跳過 Depth/OpenPose,省 ~7GB) |
| LoRA 訓練工具(`kohya_ss` + 它自己的 `uv sync` 依賴,選配) | ~5~8GB | 選配,只有使用者明確要練 LoRA 才裝 |
| **合計(不含 LoRA 訓練工具)** | **約 26~28GB** | — |
| **合計(含 LoRA 訓練工具)** | **約 31~36GB** | — |

**這是概估值,不是精確保證**——實際檔案大小以下載當下來源網站顯示的為準,Python 依賴套件版本更新也會讓虛擬環境大小浮動。裝機前把這個範圍念給使用者聽,提醒**硬碟至少要留 30GB 以上可用空間**比較保險,不要裝到一半才發現空間不夠中斷——那樣通常需要手動清理已下載一半的檔案才能重來,比事前確認空間麻煩很多。

## `sd15` tier(VRAM < 8GB,SD1.5 家族)

**這條路線目前這個 repo 完全沒有實機驗證過**,`tools_src/generate.py` 裡 `CONTROLNET_MODELS`/`ip-adapter_file`/`clip_name` 這幾個模型檔名目前是寫死指向 SDXL 版本,直接在 sd15 tier 上跑會炸(底模跟 ControlNet/IPAdapter 架構對不上)。遇到這個 tier 時:

1. 先跟使用者說清楚這是還沒驗證過的路線,不是「裝了就一定動」
2. `checkpoint` 換成 `device_config.json` 裡指定的 SD1.5 系列模型(如 DreamShaper),下載來源跟使用者確認,不要臆測網址
3. ControlNet/IPAdapter/CLIP Vision 要找對應的 **SD1.5 版本**(不是 SDXL 版本,檔名/來源都不同,自己去 Hugging Face/Civitai 找對應版本,不要套用上面 SDXL 那張表的網址)
4. 裝完之後**回頭修改 `tools_src/generate.py` 的 `CONTROLNET_MODELS` 等常數**,讓它們也依 tier 選擇對應檔名(現在是寫死的,這是已知要補的技術債,見程式碼裡的註解)
