# OpenAI 圖片編修指引：需求整理參考

查閱日期：2026-10-01。

這份摘要把官方 GPT 圖片生成／編修資料轉成需求整理方法。它只協助說清目標、參考圖用途與驗收觀察，不代表本機 ComfyUI 模型或 task 具有相同能力，也不證明任何提示方式必然改善結果。

## 官方資料摘要與專案適配

- 官方圖片提示指南建議清楚拆開要改的部分與應保留的部分，並在多張輸入圖時說明每張圖的角色；複雜編修可分步進行。專案適配：brief 分列修改項、保留項與參考圖用途；是否分階段依使用者需求和可驗收性決定。[Image prompting](https://developers.openai.com/api/docs/guides/image-prompting)
- Cookbook 圖片生成指南以明確參考圖職責、alpha 保留需求與提示中的 invariants 作為控制描述。專案適配：將參考用途和不得變項寫進自然語言需求；本機 Alpha mask 仍需符合既有格式與人工確認流程，不能把文字要求當作遮罩。[Image generation prompting guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide)
- 官方 image eval 範例依任務檢查指令符合度、局部性與內容保留。專案適配：產出回報可分項描述提示符合度、指定區域以外的變動及保留項，再獨立記錄人工美術接受決定。這些是觀察維度，不是自動品質分數。[Image evals](https://developers.openai.com/cookbook/examples/multimodal/image_evals)
- Image generation API 文件說明遮罩只引導編修區域，未必精準遵守；API 可用選項亦只適用於文件所述 API。專案適配：不把平台／API 遮罩控制等同本機 Alpha mask，也不把官方 API 選項寫成內建工具或 ComfyUI 已支援的功能。[Image generation guide](https://developers.openai.com/api/docs/guides/image-generation)

## 適用邊界

以上內容是需求表達的參考，不是本機模型驗證或效能結論。SDXL、IPAdapter、遮罩、`flux2_edit` 及其他既有 task 的實際輸入限制，仍以 [ComfyUI 產圖技能](../../comfyui-art-gen/SKILL.md) 和專案 task 文件為準。此參考不表示 GPT Image API 已接入，也不提供固定模型型號、價格或生成參數。
