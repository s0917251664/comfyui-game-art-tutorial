---
name: local-image-edit-tools
description: 使用本機 image_edit_tools.py 做 RGBA 遮罩合成、像素差異檢查、參考圖板、透明素材 Alpha 檢查、遮罩內局部色相調整，或對既有圖片 task 執行固定輸入的有限參數 sweep。
---

# 本機圖片編修工具

當使用者要把既有生成結果合成回原圖、檢查像素差異、把多張來源／參考圖整理成帶用途標籤的檢視板、檢查素材的 Alpha 通道與畫布邊界、在既有 Alpha PNG 遮罩內對符合色相／飽和度條件的可見像素做純色相調整，或明確要求對固定來源與參考做多組參數比較時使用。這些是同一個本機工具的輔助功能，不會新增生成模型或 graph；生成 sweep 只呼叫 `generate.py` 已有的 `refine`、`inpaint`、`guided_inpaint`、`character_action`。參考用途與情境選擇見[圖片編修情境與工具路徑](../game-art-edit-brief/references/scenarios.md)。

開始前確認部署端 `<ComfyUI>/tools/image_edit_tools.py` 存在，並確認選用的 Python 可匯入 Pillow 與 NumPy。`reference-board`、`asset-audit`、`composite`、`compare`、`recolor` 是本機圖片操作，不需要 ComfyUI server、runtime config 或圖片 capability snapshot；只有 `sweep` 需要取得 `python_exe`、`generate_script`、`comfyui_path`、`comfyui_url`、`image_config`，並檢查所選圖片 task 的 capability 與 validation。此工具不在 `image_capabilities.json` 內提供獨立生成能力。

## 使用順序

1. 先依情境選擇：整理多張來源／參考素材時用 `reference-board`；檢查透明素材 Alpha、可見範圍與碰邊時用 `asset-audit`；單件純換色且已有適當遮罩時用 `recolor`；既有合成、差異檢查或固定輸入參數比較照下方流程。這些本機操作只需本機腳本、Pillow／NumPy 與檔案路徑，不讀 ComfyUI runtime 或 capability。一般生成仍走 [ComfyUI 產圖技能](../comfyui-art-gen/SKILL.md)；不可用 sweep 盲目重抽。brief 需求整理仍由 [遊戲圖片編修需求整理](../game-art-edit-brief/SKILL.md) 負責。
2. `composite`／`compare` 的 source、edited 與選用 mask 必須是同尺寸單影格圖片；不會自動對齊或縮放。mask 必須是帶 Alpha channel 的 PNG：alpha 0 選編修圖，255 保留來源圖，中間值對 RGBA byte 逐通道插值。這是遮罩選擇合成，不是前景 alpha-over 或線性光混合。sweep 的角色、姿勢、材質等 task reference 可有不同尺寸，按各既有 task 的輸入契約處理。
   `recolor` 的 mask 同樣須為同尺寸、帶 Alpha 的單影格 PNG；Alpha 小於 255 表示可編輯選區，255 排除。只改可見、符合色相範圍及最低飽和度條件的像素，並保留 HSV saturation/value 到 RGB 量化前；不呼叫生成模型、不新增紋理、不保證精確 RGB、不換材質或重打光，也沒有語意分割／畫遮罩功能。來源 Alpha 與未匹配 RGBA 精確保留，選區品質仍須人工確認。
3. 每次指定全新的 output directory；工具會拒絕已存在的路徑，避免混合或覆寫既有結果。
4. sweep 前先準備 plan JSON 和 runtime config。prompt、seed 與來源／參考圖固定；僅能掃描 task 白名單內參數，笛卡兒積最多 16 次。`preserve_outside` 只適用 `inpaint` 與 `guided_inpaint`。可先用 `--dry-run` 檢查計畫與命令。
5. sweep 會先檢查 task 在 image capability snapshot 可用、validation 狀態為 `verified`、`experimental` 或 `unverified`，且 ComfyUI queue 空閒，再逐個提交。`unsupported` 或不可用 task 一律停止。validation 不是 `verified` 時，須先告知使用者並取得明確試跑同意後加 `--allow-unverified`。逾時或生成失敗即停止；先查 queue 與該次 log，再決定後續，不自動重送。
6. 開啟輸出接觸圖及候選逐張人工檢查。像素統計只描述 RGBA bytes，包含透明像素的隱藏 RGB，不判斷美術品質或接受狀態；所有輸出都維持 `candidate`，由 Steve 明確驗收。

## 命令入口

```powershell
python <ComfyUI>\tools\image_edit_tools.py composite --source <source.png> --edited <edited.png> --mask <mask.png> --output-dir <new-dir>
python <ComfyUI>\tools\image_edit_tools.py composite --source <source.png> --edited <edited.png> --mask <mask.png> --keep-source-alpha --output-dir <new-dir>
python <ComfyUI>\tools\image_edit_tools.py recolor --source <source.png> --mask <alpha-mask.png> --from-hue 180 --to-hue 0 --hue-range 45 --min-saturation 0.12 --output-dir <new-dir>
python <ComfyUI>\tools\image_edit_tools.py compare --source <source.png> --edited <edited.png> [--mask <mask.png>] --output-dir <new-dir>
python <ComfyUI>\tools\image_edit_tools.py sweep --plan <plan.json> --config <runtime.json> --output-dir <new-dir> [--profile <id>] [--timeout 240] [--dry-run] [--allow-unverified]
python <ComfyUI>\tools\image_edit_tools.py reference-board --plan <plan.json> --output-dir <new-dir>
python <ComfyUI>\tools\image_edit_tools.py asset-audit --image <image.png> --output-dir <new-dir>
```

參數、計畫格式、輸出檔案與錯誤處理見 [reference](reference/plan-format.md)；單件換色適用範圍與實測限制見[單一物件換色](../../docs/knowledge/art/single-object-color.md)。可改路徑的完整範例見 [guided inpaint](reference/examples/guided-inpaint.json) 與 [character action](reference/examples/character-action.json)。

`reference-board` 的 plan 僅含 1–12 筆 `items`，每筆 `path`、`label`、`role`，只供人工整理參考圖，不會把 board 圖當生成輸入。`asset-audit` 只檢查 Alpha／尺寸／可見邊緣，不評估角色、文字、姿勢或美術品質；輸出預覽及限制見[情境手冊](../game-art-edit-brief/references/scenarios.md)。

## 驗證狀態

2026-10-01 本機 smoke 已覆蓋 standalone composite/compare、dry-run，以及 `guided_inpaint`、`refine`、`inpaint`、`character_action` 共六張 832×1232 候選。guided preserve_outside 的原始生成在 mask 外有 815,312/846,943 個變動像素；composite 後 mask 外為 0，保留區 902,053 像素另經 NumPy 比對。部署 verifier 17 項通過，單元與部署測試 30 項通過。生成候選仍待 Steve 驗收；畫面觀察與限制見 [知識手冊](../../docs/knowledge/art/edit-tools.md)。這些結果不會自動更新 image profile/task validation。
