# AGENTS.md

這是一個遊戲美術 AI 產圖產線專案。核心文件:

- `教學.md` —— 完整的環境建置紀錄、功能地圖(哪種需求對應哪種技術)、設備/預算選型建議
- `skills/comfyui-art-gen/SKILL.md` —— **當使用者用自然語言要求產生遊戲美術素材時,讀這份文件並照它的流程操作**
- `skills/comfyui-install/SKILL.md` —— **當要在新機器上設置這條產線、或 `local_config.json` 不存在時,讀這份文件並照它的流程操作**。這是一份目標清單而不是腳本,不同機器的 OS/硬體/既有安裝狀態交給 agent 臨場判斷怎麼達成
- `skills/comfyui-pipeline-review/SKILL.md` —— **只有使用者明確要求「評估/盤點產線有沒有新技術可以升級」時才讀這份文件**,平常不要主動觸發。負責盤點現有模型清單 + 查現況 + 給建議,不負責自己動手換模型
- `skills/comfyui-new-tool-checklist/SKILL.md` —— **要幫這條產線新增任何新工具/新技術/新 task(不管改動看起來多小)時,讀這份文件並照它的檢查清單走完整輪**,涵蓋安裝、程式碼、實測、文件、workflows/ 同步五個面向,不要漏步驟就說做完了
- `local_config.json` —— **這台機器的實際安裝路徑**(ComfyUI 裝在哪、python.exe 在哪),不進版控,每台機器內容都不一樣。不存在的話代表這台機器還沒裝好,照 `skills/comfyui-install/SKILL.md` 的流程走
- `tools_src/generate.py` —— 實際執行產圖的穩定核心腳本(原始碼,版本控管在這裡)。部署到 ComfyUI 機器上的執行副本在 `<ComfyUI 安裝路徑>/tools/generate.py`,由安裝流程複製過去,不要繞過它自己組 ComfyUI API 呼叫
- `tools_src/detect_device.py` —— 設備能力偵測(GPU/VRAM/OS),輸出 `device_config.json` 給 `generate.py` 讀取,決定用哪個 checkpoint/解析度
- `workflows/` —— **不進版控**(見 `.gitignore`)。ComfyUI workflow JSON 檔案,是 `generate.py` 背後鎖死的產圖流程定義,給維護這條產線的人(不是美術)在 ComfyUI 網頁介面手動開、除錯、開發新能力時視覺化參考用,屬於本機個人產物,跟 `教學.md` 第 9 章「自己存一份到 `~/ComfyUI/user/default/workflows/`」是同一件事。不強制每個 `generate.py` 新能力都要補對應檔案——有空、真的會用到再補,不用當成義務性的同步負擔

## 給任何 agent 的原則

- ComfyUI 是產線裡的其中一個生成引擎/工具,不是要求使用者學會拉節點。多數情境下只需要呼叫 `skills/comfyui-art-gen/SKILL.md` 描述的流程
- 產圖流程要穩定、可重複——不要每次臨場亂組 ComfyUI 節點圖,新增能力時比照 `generate.py` 的模式(鎖死大部分參數,只留必要欄位可調)
- 安裝/裝機是相反的情境:硬體排列組合太多,**刻意不寫死成腳本**,交給 agent 臨場判斷,細節見 `skills/comfyui-install/SKILL.md`
- 換一台機器 / 換一顆顯卡時,至少重跑 `detect_device.py` 重新產生 `device_config.json`,不要假設 checkpoint 名稱或解析度跟這台機器一樣
- 目前沒有預算,只用本機免費模型;之後有預算要接外部雲端 API(GPT/BFL/Kling 等),ComfyUI 本身已經有對應的 API 節點,不用重建產線,詳見 `教學.md` 第 0.5 章 C 段
- 如果需要在這個 repo 裡寫 `.ps1` 檔案,要存成**帶 BOM 的 UTF-8**——Windows PowerShell 5.1 沒有 BOM 會照系統 ANSI 編碼讀檔,中文字會把語法解析弄壞(這個專案已經踩過一次這個坑)
