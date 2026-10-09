---
name: local-media-tools
description: 不經 ComfyUI graph 的本機工具：Pillow／NumPy 像素處理（遮罩合成、純換色、比較、參考圖板、Alpha 檢查、物件展示組裝 scene／sheet／pattern）、特效去背與打包（gameart.py vfx）、配音與 Animatic（film-audio、film-qwen）、對嘴（film-lipsync）、遮罩輔助。要模型生成或重畫內容時不是這裡。
---

# 本機媒體工具

處理既有的圖片或影片、不需要生成時用這個技能。這些是**本機 Python 工具**，不是 template，不要硬套 `gameart.py run`。agent 要能執行程式並讀寫來源檔；多數不需要 GPU、ComfyUI server 或 `local_config.json`（遮罩手繪服務與 sweep 例外，見下）。

## 依需求選

| 需求 | 入口（`gameart.py <tool> --help`） | 判斷依據 |
|---|---|---|
| 遮罩內合成、純換色、像素比較、參考圖板、Alpha／素材檢查 | `edit`（composite、recolor、compare、reference-board、asset-audit） | [edit-tools](../../docs/knowledge/art/edit-tools.md)、[單一物件換色](../../docs/knowledge/art/single-object-color.md) |
| 物件展示背景、檢視表、圖樣重複 | `design`（scene、sheet、pattern，純 Pillow） | [物件組裝](../../docs/knowledge/art/object-design-workflows.md) |
| 特效去背、sprite sheet／WebM 打包、Idle 首尾量測、道具貼回、遮罩拆包 | `vfx` | [vfx-tools](../../docs/knowledge/video/vfx-tools.md)、[R3](../../docs/knowledge/rules/idle-anchoring.md) |
| 接片、綠幕合成、抽幀 | `generate.py video_concat`／`video_composite`（本機 PyAV，不連 ComfyUI） | [影片知識](../../docs/knowledge/video/README.md) |
| 台詞試聽、混音、Animatic、配音、對嘴 | `film-audio`、`film-qwen`、`film-lipsync` | [劇情流程](../../docs/knowledge/video/production-flow.md) |
| 手繪遮罩、邊界貼合、SAM 候選遮罩 | `mask-session`（需 ComfyUI 網頁服務）、`mask-refine`、`sam` | [遮罩](../../docs/knowledge/art/masking.md)、[SAM](../../docs/knowledge/art/sam-segmentation.md) |

## 判斷原則

- 需要模型生成或重畫（換造型、重畫遮罩內內容）不是這裡的工作，交給 [comfyui-run](../comfyui-run/SKILL.md) 或 [platform-image-gen](../platform-image-gen/SKILL.md)。有限參數比較（sweep）會送出圖片 task，也屬 comfyui-run。
- 工具之間的遮罩約定不同（圖片 inpaint 是反向 alpha，影片 SAM 是白選黑不選），不能直接互換；用之前看 [遮罩](../../docs/knowledge/art/masking.md)。
- 輸出都是 candidate；像素統計、遮罩外 0 變動這類技術檢查不代表美術接受（[R1](../../docs/knowledge/rules/candidate-review.md)）。
- 不覆寫來源檔；輸出寫到新資料夾（多數工具會拒絕已存在的資料夾）。
- TTS、對嘴、Pillow 比較都只是機械處理：台詞要聽過、嘴型要看過，才算過。
