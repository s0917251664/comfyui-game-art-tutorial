---
name: local-image-edit-tools
description: 使用 Pillow/NumPy 做既有圖片的遮罩合成、純換色、像素比較、參考圖板與 Alpha 檢查；不需要 ComfyUI、不執行模型生成，sweep 轉交 comfyui-image-sweep。
---

# 本機圖片編修工具

當使用者要把既有編修結果合成回原圖、檢查像素差異、整理帶用途標籤的參考圖板、檢查 Alpha／畫布邊界，或在既有遮罩內做純色相調整時使用。輸入可來自本機模型、平台生成或手工製作；必須先取得可讀取的原始圖片檔，不能以截圖替代 Alpha 原檔。共用需求、版本與內容驗收由[遊戲美術工作流程](../../../game-art-brief/references/game-art-workflow/README.md)維護。

開始前確認 `image_edit_tools.py` 及可匯入 Pillow／NumPy 的 Python。可用 repo `tools_src/image_edit_tools.py`、既有部署副本或交付到工作目錄的同一檔案；五個操作不需要 GPU、ComfyUI server、`local_config.json` 或圖片 capability snapshot，不因缺 config 要求裝機。只有能執行程式、讀寫圖片的 Agent 才能使用工具；純聊天平台可使用共用方法，但不能宣稱已完成檔案檢查。

## 職責邊界與舊入口相容

`sweep` 實作與 CLI 仍在同一支 `image_edit_tools.py`，但其 ComfyUI task／queue／manifest 規則已交由[ComfyUI 有限參數比較](../../../comfyui-run/references/comfyui-image-sweep/README.md)維護；收到這類需求就交接，不套用本技能的免 ComfyUI 前提。本次拆分技能責任，不搬動程式或新增 graph。

本技能不建立遮罩。手繪工具使用 ComfyUI web service；`mask_refine` 需 OpenCV，SAM 另需模型／runtime，都不能因本技能免 ComfyUI 而推定可用。

## 使用順序

1. 整理參考用 `reference-board`；檢查 Alpha／範圍／碰邊用 `asset-audit`；純換色用 `recolor`；將編修結果合回來源用 `composite`；看修改差異用 `compare`。本技能不呼叫生成模型；需要生成時，沿用使用者選定的引擎交接其執行技能。
2. `composite`／`compare` 的 source、edited 與選用 mask 必須是同尺寸單影格圖片；不會自動對齊或縮放。mask 必須是帶 Alpha channel 的 PNG：alpha 0 選編修圖，255 保留來源圖，中間值對 RGBA byte 逐通道插值。這是遮罩選擇合成，不是前景 alpha-over 或線性光混合。平台編修圖若改變尺寸或構圖，不得直接合回或偷偷縮放；先說明不符合輸入契約。
   `composite --keep-source-alpha` 會令輸出沿用 source Alpha；只在需要保留來源透明度時加此旗標。省略時仍依原有遮罩方向對完整 RGBA byte 插值。這不影響 `recolor`，後者本來就保留來源 Alpha。
   `recolor` 的 mask 同樣須為同尺寸、帶 Alpha 的單影格 PNG；Alpha 小於 255 表示可編輯選區，255 排除。只改可見、符合色相範圍及最低飽和度條件的像素，並保留 HSV saturation/value 到 RGB 量化前；不呼叫生成模型、不新增紋理、不保證精確 RGB、不換材質或重打光，也沒有語意分割／畫遮罩功能。來源 Alpha 與未匹配 RGBA 精確保留，選區品質仍須人工確認。
3. 每次指定全新的 output directory；工具會拒絕已存在的路徑，避免混合或覆寫既有結果。
4. 開啟輸出檢視圖及候選，依共用工作流程檢查內容。像素統計只描述 RGBA bytes，包含透明像素的隱藏 RGB，不判斷美術品質或接受狀態；候選由美術審核者明確驗收。

## 命令入口

```powershell
<python> <image_edit_tools.py> composite --source <source.png> --edited <edited.png> --mask <mask.png> --output-dir <new-dir>
<python> <image_edit_tools.py> composite --source <source.png> --edited <edited.png> --mask <mask.png> --keep-source-alpha --output-dir <new-dir>
<python> <image_edit_tools.py> recolor --source <source.png> --mask <alpha-mask.png> --from-hue 180 --to-hue 0 --hue-range 45 --min-saturation 0.12 --output-dir <new-dir>
<python> <image_edit_tools.py> compare --source <source.png> --edited <edited.png> [--mask <mask.png>] --output-dir <new-dir>
<python> <image_edit_tools.py> reference-board --plan <plan.json> --output-dir <new-dir>
<python> <image_edit_tools.py> asset-audit --image <image.png> --output-dir <new-dir>
```

參數、輸出與錯誤處理見 [reference](reference/plan-format.md)；單件換色實測見[單一物件換色](../../../../docs/knowledge/art/single-object-color.md)。sweep 範例與參數由 ComfyUI sweep 技能按需讀取。CLI 模板須替換為實際路徑；PowerShell 對帶引號的 Python 路徑使用 `&`。

`reference-board` 的 plan 僅含 1–12 筆 `items`，每筆 `path`、`label`、`role`，只供人工整理參考圖，不會把 board 圖當生成輸入。`asset-audit` 只檢查 Alpha／尺寸／可見邊緣，不評估角色、文字、姿勢或美術品質；輸出預覽及限制見[情境手冊](../../../game-art-brief/references/game-art-edit-brief/references/scenarios.md)。

## 驗證狀態

2026-10-01 本機 smoke 已覆蓋 standalone composite/compare、dry-run，以及 `guided_inpaint`、`refine`、`inpaint`、`character_action` 共六張 832×1232 候選。guided preserve_outside 的原始生成在 mask 外有 815,312/846,943 個變動像素；composite 後 mask 外為 0，保留區 902,053 像素另經 NumPy 比對。部署 verifier 17 項通過，單元與部署測試 30 項通過。生成候選仍待美術審核者驗收；畫面觀察與限制見 [知識手冊](../../../../docs/knowledge/art/edit-tools.md)。這些結果不會自動更新 image profile/task validation。

2026-10-03 增補 `recolor` 與 `composite --keep-source-alpha` 實測；43 項單元測試及 19 項部署 verifier 通過。玻璃瓶案例仍是待美術審核者驗收的 candidate，生成未命中紅色的兩次試跑及色相旋轉限制見[單一物件換色紀錄](../../../../docs/knowledge/art/single-object-color.md)。日期化觀察不會改寫 image profile 或 task validation。
