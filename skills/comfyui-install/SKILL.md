# ComfyUI 產線安裝

給任何操作這個 repo 的 agent(Claude Code、Codex、Gemini CLI 等)使用的技能說明。

## 何時使用

當使用者要在一台新機器上設置這條產線(不管是自己的電腦、還是要幫美術同事的電腦裝),或 `local_config.json` 不存在時使用。

## 核心原則

**這不是一支腳本,是一份目標清單。** 不同機器的 OS、硬體、既有安裝狀態都不一樣,不要照抄任何範例指令硬套——每個步驟看「這件事現在是不是已經成立」,不成立就用你判斷這台機器上最合適的方式做到。遇到這台機器特有的狀況(公司網路擋 huggingface、殘留安裝、CUDA 版本卡住、權限問題),照實跟使用者說清楚、想辦法繞過去,不要靜默失敗或編造結果。

之所以不寫死成 `.ps1`/`.sh` 腳本:硬體排列組合太多,腳本只會不斷長出新的特例分支,長期比讓 agent 臨場判斷更難維護。這跟 `generate.py`(必須鎖死參數以保證產圖可重複)是相反的情境——安裝是一次性任務,值得用判斷力換取彈性。

## 開始裝之前:先告知硬碟空間需求

**動手下載任何東西之前,先跟使用者說清楚這台機器大概要花多少硬碟空間**,概估數字跟拆解見 `reference/models.md`「硬碟空間概估」那段(不含 LoRA 訓練工具約 26~28GB,含的話約 31~36GB)。念完概估數字、確認使用者這台機器有足夠可用空間,再開始走下面的步驟——不要裝到一半才發現空間不夠中斷,那樣通常要使用者自己回頭清理下載到一半的檔案才能重來,比事前講清楚麻煩很多。

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
8. **模型**:先確認 `device_config.json` 的 `tier` 落在哪個 family,再決定要裝哪一組。**這件事不是只有底模(checkpoint)要跟著 tier 換,ControlNet/IPAdapter/CLIP Vision 全部都是跟底模綁定的,底模架構變了,這些都要跟著換成對應版本,不能只換 checkpoint、其他照抄。** 完整清單(SDXL 家族的檔名/下載來源表,以及 sd15 tier 的處理方式)見 `reference/models.md`——**那張表是刻意鎖定的版本清單,不是「目前最好的選擇」清單,只管照表裝,不要自作主張換掉更新的模型**(真的想評估升級用 `skills/comfyui-pipeline-review/SKILL.md`,不是安裝流程該做的事)。
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

## 進階(選配):LoRA 訓練工具

**只有使用者明確要準備訓練角色/風格 LoRA 時才裝,不是每台機器的基本配備。** 跟 ComfyUI 完全獨立的另一套工具(`kohya_ss`),裝法跟已知的編碼/踩坑細節見 `reference/lora-training.md`。

## 執行原則

- **冪等**:每一步先檢查是否已經成立,成立就跳過,不要盲目重跑或覆蓋使用者已經調整過的東西(`generate.py` 除外——它永遠要跟 repo 同步)
- **換機器/換顯卡**:至少重跑步驟 4(設備偵測)跟步驟 11(重寫 `local_config.json`),不要假設 checkpoint 或路徑沒變
- **下載失敗/網路受限**:如實回報,不要用假路徑頂替或假裝下載成功
- **收尾**:全部完成後,把最終的 `local_config.json` 內容念給使用者確認一次,並提醒他下一步可以直接用自然語言要求產圖(見 `skills/comfyui-art-gen/SKILL.md`)
