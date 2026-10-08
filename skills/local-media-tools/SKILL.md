---
name: local-media-tools
description: 不用模型、不送 ComfyUI 的本機像素與媒體處理：遮罩合成、純換色、像素比較、參考圖板、Alpha 檢查（image_edit_tools.py），以及特效去背（黑底亮度／綠幕）、sprite sheet／WebM 打包、Idle 首尾量測、影片遮罩工具（gameart.py vfx）。
---

# 本機媒體工具

處理既有的圖片或影片、不需要生成時用這個技能。這些工具用 Pillow／NumPy／PyAV 在本機執行，不需要 GPU，也不讀 `local_config.json`；agent 要能執行程式並讀寫來源檔。

## 依需求選

| 需求 | 入口 | 細節 |
|---|---|---|
| 遮罩合成、純換色、像素比較、參考圖板、Alpha／素材檢查 | `gameart.py edit composite|recolor|compare|reference-board|asset-audit` | [local-image-edit-tools](references/local-image-edit-tools/README.md) |
| 特效去背（黑底亮度、綠幕） | `gameart.py vfx luma-alpha|chroma-alpha` | [vfx-tools](../../docs/knowledge/video/vfx-tools.md) |
| sprite sheet／WebM 打包、Idle 首尾量測 | `gameart.py vfx pack|loop-metrics` | [vfx-tools](../../docs/knowledge/video/vfx-tools.md)；首尾規則見 [R3](../../docs/knowledge/rules/idle-anchoring.md) |
| 物件貼回、遮罩拆包、關鍵幀 | `gameart.py vfx prop-paste|unpack-masks|keyframes` | [vfx-tools](../../docs/knowledge/video/vfx-tools.md) |

## 判斷原則

- 需要模型生成或重畫的需求（換造型、重畫遮罩內內容）不是這裡的工作，交給 [comfyui-run](../comfyui-run/SKILL.md) 或 [platform-image-gen](../platform-image-gen/SKILL.md)。
- 參數比較（sweep）會送既有的圖片 task，屬於 [comfyui-run](../comfyui-run/SKILL.md)。
- 輸出一律是 candidate；像素統計、遮罩外 0 變動這類技術檢查不代表美術接受（[R1](../../docs/knowledge/rules/candidate-review.md)）。
- 不覆寫來源檔；輸出寫到新的資料夾。

舊技能 `local-image-edit-tools` 的完整內容保留在 `references/` 底下，對照表見 [技能收斂對照](../../docs/knowledge/maintenance/skills-6-mapping.md)。
