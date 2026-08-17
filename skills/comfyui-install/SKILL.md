# ComfyUI 產線安裝

給任何操作這個 repo 的 agent(Claude Code、Codex、Gemini CLI 等)使用的技能說明。

## 何時使用

當使用者要在一台新機器上設置這條產線(不管是自己的電腦、還是要幫美術同事的電腦裝),或 `local_config.json` 不存在時使用。

## 核心原則

**這不是一支腳本,是一份目標清單。** 不同機器的 OS、硬體、既有安裝狀態都不一樣,不要照抄任何範例指令硬套——每個步驟看「這件事現在是不是已經成立」,不成立就用你判斷這台機器上最合適的方式做到。遇到這台機器特有的狀況(公司網路擋 huggingface、殘留安裝、CUDA 版本卡住、權限問題),照實跟使用者說清楚、想辦法繞過去,不要靜默失敗或編造結果。

之所以不寫死成 `.ps1`/`.sh` 腳本:硬體排列組合太多,腳本只會不斷長出新的特例分支,長期比讓 agent 臨場判斷更難維護。這跟 `generate.py`(必須鎖死參數以保證產圖可重複)是相反的情境——安裝是一次性任務,值得用判斷力換取彈性。

## 目標(裝完之後,以下都要成立)

1. **前置工具**:`git`、`python`(3.11+)在 PATH 上。缺的話請使用者先手動安裝,不要代為安裝系統層級工具。
2. **ComfyUI 原始碼**:clone `https://github.com/comfyanonymous/ComfyUI.git` 到 `<ComfyUI 安裝路徑>`(沒有特殊需求的話,Windows 用 `%USERPROFILE%\ComfyUI`,Mac/Linux 用 `~/ComfyUI`)。已存在(`main.py` 在裡面)就跳過 clone。
3. **Python 虛擬環境**:`<ComfyUI 安裝路徑>/.venv`。已存在就跳過建立,但確認裡面的 python 可以正常執行。
4. **設備偵測**:把這個 repo 的 `tools_src/detect_device.py` 複製到 `<ComfyUI 安裝路徑>/tools/detect_device.py`,執行它產生 `<ComfyUI 安裝路徑>/tools/device_config.json`。這支腳本本身是固定邏輯,不要修改它。
5. **PyTorch**:依 `device_config.json` 裡的 `backend`(`cuda`/`mps`/`cpu`)跟 `torch_index_url` 裝對應版本進 `.venv`。已裝的話檢查版本合理即可,不用強制重裝。
6. **ComfyUI 依賴**:`.venv` 裡 `pip install -r requirements.txt`(在 `<ComfyUI 安裝路徑>` 底下)。
7. **Custom nodes**(clone 進 `<ComfyUI 安裝路徑>/custom_nodes/`,已存在就跳過):
   - `ComfyUI-Manager`:`https://github.com/Comfy-Org/ComfyUI-Manager.git`
   - `ComfyUI_IPAdapter_plus`:`https://github.com/cubiq/ComfyUI_IPAdapter_plus.git`
   - `comfyui_controlnet_aux`:`https://github.com/Fannovel16/comfyui_controlnet_aux.git`(提供 `OpenposePreprocessor`、`DepthAnythingV2Preprocessor` 等前處理節點,第 7 章 pose/depth 控制類型要用)
   裝完後確認各自的 `requirements.txt`(如果有)也裝了。`comfyui_controlnet_aux` 的前處理器模型(DWPose、Depth Anything 權重)會在第一次真的執行到的時候自己下載到它自己的 `ckpts/` 資料夾,不用手動預先下載。
8. **模型**:先確認 `device_config.json` 的 `tier` 落在哪個family,再決定要裝哪一組。**這件事不是只有底模(checkpoint)要跟著 tier 換,ControlNet/IPAdapter/CLIP Vision 全部都是跟底模綁定的,底模架構變了,這些都要跟著換成對應版本,不能只換 checkpoint、其他照抄。**

   > **這張表是刻意鎖定的版本清單,不是「目前最好的選擇」清單。** 裝機時只管照表裝,不要因為你知道有更新的模型就自作主張換掉——不同人在不同時間裝出來的美術基準要一致,是這整條產線存在的意義。真的想評估要不要升級,用 `skills/comfyui-pipeline-review/SKILL.md`,那是獨立於安裝流程之外、需要使用者明確觸發跟核准的另一件事。

   **`sdxl_high` / `sdxl` / `sdxl_light` tier(SDXL 家族,目前唯一實際驗證過的組合)**:下載到 `<ComfyUI 安裝路徑>/models/<子資料夾>/`,已存在的檔案跳過:

   | 模型 | 子資料夾 | 檔名 | 下載來源 | 用途 | 最後確認日期 |
   |---|---|---|---|---|---|
   | SDXL base | `checkpoints` | `sd_xl_base_1.0.safetensors` | `https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors` | 第 3~6 章底模 | 2026-07-29 |
   | ControlNet Canny (SDXL) | `controlnet` | `controlnet-canny-sdxl-1.0.safetensors` | `https://huggingface.co/lllyasviel/sd_control_collection/resolve/main/diffusers_xl_canny_full.safetensors` | 第 7 章,`generate.py --control-type canny`(預設) | 2026-07-29 |
   | ControlNet Depth (SDXL) | `controlnet` | `controlnet-depth-sdxl-1.0.safetensors` | `https://huggingface.co/lllyasviel/sd_control_collection/resolve/main/diffusers_xl_depth_full.safetensors` | 第 7 章,`generate.py --control-type depth`,約 2.5GB | 2026-08-17 |
   | ControlNet OpenPose (SDXL) | `controlnet` | `controlnet-openpose-sdxl-1.0.safetensors` | `https://huggingface.co/thibaud/controlnet-openpose-sdxl-1.0/resolve/main/OpenPoseXL2.safetensors` | 第 7 章,`generate.py --control-type pose`,約 4.7GB(fp32,檔案偏大是正常的) | 2026-08-17 |
   | IPAdapter Plus (SDXL) | `ipadapter` | `ip-adapter-plus_sdxl_vit-h.safetensors` | `https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors` | 第 8 章 | 2026-07-29 |
   | CLIP Vision (ViT-H) | `clip_vision` | `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | `https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors` | 第 8 章。**注意路徑是 `models/image_encoder`,不是 `sdxl_models/image_encoder`——後者是 bigG 版,維度不同,裝錯會在 `IPAdapterAdvanced` 執行期噴 shape mismatch** | 2026-07-29 |
   | BiRefNet 去背 | `background_removal` | `birefnet.safetensors` | `https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors` | `generate.py --remove-bg` 用,跟底模架構無關,任何 tier 都用這個 | 2026-07-29 |
   | 4x-UltraSharp 放大模型 | `upscale_models` | `4x-UltraSharp.pth` | `https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth` | `generate.py upscale` 用,跟底模架構無關,任何 tier 都用這個,約 67MB | 2026-08-17 |

   VRAM 較緊張時(`sdxl_light` tier),Depth/OpenPose 這兩個 ControlNet 檔案較大(共約 7GB),可以先跳過,等使用者真的需要姿勢/深度控制再補裝。

   **`sd15` tier(VRAM < 8GB,SD1.5 家族)**:**這條路線目前這個 repo 完全沒有實機驗證過**,`tools_src/generate.py` 裡 `CONTROLNET_MODELS`/`ip-adapter_file`/`clip_name` 這幾個模型檔名目前是寫死指向 SDXL 版本,直接在 sd15 tier 上跑會炸(底模跟 ControlNet/IPAdapter 架構對不上)。遇到這個 tier 時:
   1. 先跟使用者說清楚這是還沒驗證過的路線,不是「裝了就一定動」
   2. `checkpoint` 換成 `device_config.json` 裡指定的 SD1.5 系列模型(如 DreamShaper),下載來源跟使用者確認,不要臆測網址
   3. ControlNet/IPAdapter/CLIP Vision 要找對應的 **SD1.5 版本**(不是 SDXL 版本,檔名/來源都不同,自己去 Hugging Face/Civitai 找對應版本,不要套用上面 SDXL 那張表的網址)
   4. 裝完之後**回頭修改 `tools_src/generate.py` 的 `CONTROLNET_MODELS` 等常數**,讓它們也依 tier 選擇對應檔名(現在是寫死的,這是已知要補的技術債,見程式碼裡的註解)
9. **產圖腳本**:把 `tools_src/generate.py` 複製(覆蓋)到 `<ComfyUI 安裝路徑>/tools/generate.py`——**這支永遠以 repo 裡的原始碼為準**,不要在部署副本上直接改邏輯。
10. **啟動用的小捷徑**(方便使用者之後自己開伺服器,不一定要是腳本,一行指令也行):在 `<ComfyUI 安裝路徑>` 附近留一個能一鍵/一行啟動 `main.py --listen 127.0.0.1 --port <port>` 的方式。**先確認 port 8188 沒被佔用**(例如這台機器如果已經裝了 ComfyUI 桌面版且常駐執行,要換別的 port,如 8189)。
11. **寫入 repo 根目錄的 `local_config.json`**(不進版控,每台機器內容不同):
    ```json
    {
      "comfyui_path": "<ComfyUI 安裝路徑>",
      "python_exe": "<.venv 裡 python 執行檔的完整路徑>",
      "generate_script": "<ComfyUI 安裝路徑>/tools/generate.py",
      "comfyui_url": "http://127.0.0.1:<實際用的 port>",
      "start_script": "<步驟 10 的啟動方式,路徑或指令>",
      "output_dir": "<這個 repo 根目錄>/output"
    }
    ```

## 執行原則

- **冪等**:每一步先檢查是否已經成立,成立就跳過,不要盲目重跑或覆蓋使用者已經調整過的東西(`generate.py` 除外——它永遠要跟 repo 同步)
- **換機器/換顯卡**:至少重跑步驟 4(設備偵測)跟步驟 11(重寫 `local_config.json`),不要假設 checkpoint 或路徑沒變
- **下載失敗/網路受限**:如實回報,不要用假路徑頂替或假裝下載成功
- **收尾**:全部完成後,把最終的 `local_config.json` 內容念給使用者確認一次,並提醒他下一步可以直接用自然語言要求產圖(見 `skills/comfyui-art-gen/SKILL.md`)
