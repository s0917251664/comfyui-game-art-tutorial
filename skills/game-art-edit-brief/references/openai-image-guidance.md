# OpenAI 圖片編修指引：需求整理參考

查閱日期：2026-10-02。

本文件把 OpenAI 官方圖片生成與評估範例轉成需求整理方法。官方資料協助說清楚修改目標、參考圖用途與驗收觀察；本機可做什麼仍以既有 task、工具契約、機器能力快照與實測紀錄為準。GPT Image API 的參數、遮罩行為或保真能力不會因此成為本機 ComfyUI 能力。

需要按情境選工具時，讀[圖片編修情境與工具路徑](scenarios.md)。本機 brief 只整理需求和既有 task 支援情況，不執行生成、不新增 API 能力。

## 官方資料與專案適配

- [Image prompting guide](https://developers.openai.com/api/docs/guides/image-prompting)：角色特徵 anchor、清楚說明需修改與需保留內容，以及逐輪集中描述變更。專案適配：brief 寫出不變項、本輪改動及來源版本；這種編排不保證本機模型結果更好。
- [Image generation models prompting guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide)：參考圖的明確職責、風格轉換、換裝、多圖合成與角色一致性情境。專案適配：先標示參考用途，再映射到既有 task 支援的輸入欄位；官方多圖工作流不代表本機 task 可接收相同數量或角色的圖片。
- [Image evals](https://developers.openai.com/cookbook/examples/multimodal/image_evals)：正確性、指定區域以外的變動、需保留內容及空間關係等觀察面向。專案適配：作為產後人工檢查項，搭配 `compare` 的像素差異及 `asset-audit` 的 Alpha／尺寸檢查；不輸出自動美術分數。
- [Transparent image assets](https://developers.openai.com/cookbook/examples/multimodal/transparent-image-assets-for-campaigns-and-presentations)：透明素材生成與交付範例。專案適配：把 Alpha 通道、邊緣及畫布內完整度列入檢查；本機去背仍走既有 task。
- [High input fidelity example](https://developers.openai.com/cookbook/examples/generate_images_with_high_input_fidelity)：示範特定 Image API 的輸入保真選項。專案適配：只借用列出關鍵細節並檢查是否保留的方式；API 專屬參數不移植到本機 ComfyUI。

## 工具入口

`asset-audit` 與 `reference-board` 已整合於既有 `tools_src/image_edit_tools.py`，沒有額外依賴或部署檔。操作格式及限制見[圖片編修情境與工具路徑](scenarios.md)，輸出只供技術檢視和人工判斷。

已在 Windows／RTX 4080 專案環境完成兩工具與既有 image edit tools 的 33 項測試；部署驗證 18 項通過，拒絕覆寫既有輸出目錄的案例也已實測。Alpha、參考板的輸出證據及案例限制見[情境文件](scenarios.md)和 `output/scenario_tools_20261002/`。這些測試不代表驗收任何生成結果或美術品質。

## 本機輸入依據

本機 task 欄位查[遊戲圖片編修需求整理技能](../SKILL.md)、[圖片完整參數規格 art-parameters.md](../../../docs/knowledge/art-parameters.md) 及 task 文件；工具契約和證據見 [edit-tools.md](../../../docs/knowledge/art/edit-tools.md)。`guided_inpaint` 需要已確認 Alpha mask，`character_action` 是角色與姿勢參考欄位，`flux2_edit` 僅支援單張來源圖且沒有 mask 或 denoise 控制。其他輸入不能從官方 API 文件推定。
