# LoRA 訓練工具(進階選配)

`skills/comfyui-install/SKILL.md` 指向這裡——**只有使用者明確要準備訓練角色/風格 LoRA 時才裝,不是每台機器的基本配備。** 跟 ComfyUI 完全獨立的另一套工具:

- 裝 `kohya_ss`:`git clone --recursive https://github.com/bmaltais/kohya_ss.git`(注意 `--recursive`,`sd-scripts` 是它的 git submodule,漏了要補 `git submodule update --init --recursive`)
- 建環境:進 `kohya_ss` 資料夾跑 `uv sync`(沒有 `uv` 就先按官方指引裝,見它自己的 `README.md`)。這一步依賴解析比較久(CUDA 相關套件多),耐心等,不要當成卡住
- 實際訓練是呼叫 `sd-scripts/sdxl_train_network.py`(不要透過它的 Gradio GUI,跟這條產線一貫「CLI/API 驅動、不要求人點介面」的原則一致),用 `accelerate launch` 執行,細節跟已驗證過的參數見 `教學.md` 第 8 章
- Windows 主控台印 `--help` 可能因為內建的日文說明文字編碼問題直接噴 `UnicodeEncodeError`(cp950 codec 的問題,不是腳本壞掉),不影響實際訓練執行,不用因為這個就以為裝壞了
- 訓練完的 `.safetensors` 檔案複製進 `<ComfyUI 安裝路徑>/models/loras/`,`generate.py` 就能透過 `--lora <檔名>` 使用
