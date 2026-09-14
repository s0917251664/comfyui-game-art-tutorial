---
name: comfyui-character-animation-workflow
description: 規劃並執行單一角色的一組遊戲動畫素材流程，從定稿靜幀、動作規格、逐支生成與人工驗收到抽幀交付；不取代既有產圖／產影片 task，也不假裝支援尚未接入的第三方 backend 或透明影片能力。
---

# ComfyUI 單角色動畫工作流程

當使用者要的不是單支影片，而是同一角色的一組遊戲動作（例如 Idle、Win、Expect、Fail、Attack），或要求從角色圖一路做到可交付的動畫素材時使用。

單支「讓這張圖動起來」仍直接走 `skills/comfyui-video-gen/SKILL.md`；有劇情的多鏡過場仍走該技能的鏡頭表流程。這份技能負責的是單角色、多動作、需要分階段驗收的製作編排。

## 責任邊界

- 產圖方式、必要輸入與圖片產後驗收：`skills/comfyui-art-gen/SKILL.md`
- 影片 task、backend、輸出契約、sidecar 與影片產後驗收：`skills/comfyui-video-gen/SKILL.md`
- 新 provider、新 task 或新後製能力：先走 `skills/comfyui-new-tool-checklist/SKILL.md`，不能在本流程臨場補 graph 或假裝已支援
- 模型升級比較：只有使用者明確要求時才走 `skills/comfyui-pipeline-review/SKILL.md`

本技能只安排順序、保存決策與設置人工驗收點，不重複定義底層 task 參數，也不改寫 `generate.py` 的 `pass`／`warning`／`fail` 契約。

## 開始前必要確認

**先確認這台機器能跑哪些 task，再補問缺少的需求。** 先使用附件與前文已提供的角色圖、偏好、尺寸、FPS、授權及驗收決定；不要重複詢問已有答案。讀 `image_capabilities.json`（靜幀要用的 `character_action`、`style_lock` 等，看 `available` 與 `validation`）與 `video_capabilities.json`（各 backend 的 `capabilities`），列出本流程可能用到的 task 哪些可用、驗證狀態為何。規則同 `skills/comfyui-art-gen/SKILL.md`「這台機器能跑什麼」與影片技能的同名段落：

- 不可用的 task 不列入動作表的方案，並告訴使用者缺什麼。
- 整條路線缺關鍵能力（例如沒有任何影片 backend，或有動作參考影片卻沒有可用的 `pose_drive`）時，**在排動作表之前就停下告知**，不要先做完靜幀才發現影片做不了。
- 需要的 task 是 `unverified` 時，先讓使用者知道，再決定是否繼續。

1. 角色主參考圖是否已定稿；若沒有，先走圖片產線，通過圖片產後驗收再繼續。
2. 動作清單，以及每個動作的用途、是否循環、期望時長。
3. 交付尺寸、FPS、是否需要 PNG frames；使用者沒指定時，不自行套用網站案例的 12 FPS。
4. 是否需要轉身或背面。現有參考資料不足時先停下補素材，不把單張正面圖假裝成可靠三視圖。
5. 是否要求透明素材。現有影片產線沒有透明影片／逐幀 AI 去背的一等公民 task；只能交付現有能力實際支援的 MP4、抽幀 PNG，或以乾淨綠幕走 `video_composite` 做背景合成。
6. 要使用哪個已接入 backend。若 capability config 沒有 default，依影片技能要求明確選擇；外部付費 provider 尚未接成 backend 時不得列為可執行方案。

把確認結果整理成動作表。欄位與範例見 `reference/templates.md`，但只填本案需要的資訊，不為了填表增加無關要求。

## 工作流程

### 1. 鎖定角色靜幀

角色、服裝、道具、比例與基本構圖先在圖片階段定稿。需要特定動作起點時，用 `character_action` 準備與動作參考第一幀姿勢／朝向接近的靜幀；不要拿不相干站姿直接餵 `pose_drive`。

產圖後依 `comfyui-art-gen` 的產後驗收打開檢查。角色靜幀未接受前，不進影片生成。

### 2. 逐動作選 task

只從「開始前必要確認」確認可用的 task 裡選；某個動作最適合的 task 在這台機器不可用時，說明取捨讓使用者決定，不自動換成另一個 task 硬做。

- 原構圖內做 Idle／展示動作：`img2video`
- 明確需要無縫循環的元素：`fx_loop`
- 角色換場景或做新表演、第一幀不必等於定稿圖：`character_video`
- 有動作參考影片：`pose_drive`
- 主體不動、只運鏡：`camera_move`

不要為了整組一致性而把所有動作硬塞進同一個 task。task 判斷與 backend 能力仍以影片技能為準。

### 3. 先做代表動作

若是一整組動畫，先選一個最能暴露身份、動作與 Loop 問題的代表動作完成生成與驗收。代表動作未定案前，不批次展開其餘動作，避免相同方向錯誤乘上整組數量。

### 4. 保留原始輸出並執行技術自檢

每支生成保留 MP4 與同名 `.mp4.json` sidecar。先看輸出契約：

- `fail`：不能進人工驗收或後製，先處理契約錯誤。
- `warning`：保留原始輸出，依警告內容人工檢查；不能自行當成失敗或成功。
- `pass`：只代表檔案契約通過，仍須做內容驗收。

不要只靠首尾像素差判斷角色身份、動作自然度或 Loop 可用性。

### 5. 動作人工驗收

依 `comfyui-video-gen` 的產後驗收逐支檢查。循環動作至少要連續觀看多輪，確認接縫、方向、慣性與表情；這是人工觀看要求，不新增跨題材的自動門檻。

把結果與原因回報使用者，由使用者決定接受、調整或放棄。未接受的原始影片仍保留供比較；不自動重送，也不在未確認狀態時覆寫。

### 6. 準備並交付抽幀或合成

需要影格時，支援該旗標的 task 在生成時帶 `--extract-frames`；`fx_loop` 預設抽幀，不使用此旗標。工具會在 MP4 通過契約檢查並寫入 sidecar 後準備 frames；這些影格仍屬候選輸出。只有動作內容經使用者接受後，才把準備好的 frames 或 `fx_loop` 的影格視為正式交付，或進行 `video_composite`。若生成時未準備 frames，接受後可直接對既有 MP4 重新執行既有 helper `extract_video_frames(video_path, output_dir)`，不必新增 CLI task，也不得為了抽幀重新生成影片。使用 `local_config.json` 的 `python_exe`（已安裝 PyAV 與 Pillow），將 `generate_script` 的所在資料夾及已驗收 MP4、輸出根目錄作為 argv 傳入：

```text
<python_exe> -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path(sys.argv[1]))); from generate import extract_video_frames; extract_video_frames(sys.argv[2], sys.argv[3])" "<generate_script 所在資料夾>" "<accepted.mp4>" "<output_dir>"
```

helper 會在 `<output_dir>/<影片檔名移除副檔名與尾端底線>_frames/` 建立影格，完整解碼且至少一幀後才替換舊影格集；失敗會保留舊影格。它不重跑生成，也不重建 sidecar；執行後核對影格數與已驗收 sidecar 的實際幀數一致。路徑依所在 shell 正確引用；PowerShell 使用帶引號的執行檔路徑時加 `&`。後製不能修復角色變形、重心錯誤或動作理解錯誤。

抽幀與合成完成後，再依影片技能檢查輸出尺寸、FPS、影格數、音訊政策與實際畫面。不要把綠幕合成稱為透明序列，也不要宣稱支援目前沒有的 APNG／sprite sheet 包裝。

### 7. 交付

交付時列出：

- 已接受的動作與各自 MP4／frames 路徑
- 對應 sidecar 路徑與 `pass`／`warning` 狀態
- 尚待人工確認或放棄的動作
- 已知限制，以及未執行的後製項目

不要刪除供應商／backend 原始輸出，不要只交修剪或合成後檔案而失去來源追溯。

## 付費或第三方生成

目前 repository 尚未接入第三方 provider backend。未來接入後仍沿用相同 task 名與上述驗收流程；每次付費生成前列出 provider/backend、輸入素材、時長、輸出數量與估計費用，取得使用者確認後才送出。失敗後不自動付費重試。

第三方輸出若沒有本產線 sidecar，不能假裝具備相同可追溯性；要把 provider、請求參數、原始檔與可取得的識別資訊另外保留，直到正式 backend 補齊同等契約。
