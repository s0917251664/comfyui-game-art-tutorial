---
name: game-art-edit-brief
description: 專案相容入口，將多參考圖、指定部位編修及角色／結構保留需求映射到既有 ComfyUI 圖片 task；通用 brief 規則由 game-art-workflow 負責。
---

# 遊戲圖片編修需求整理

本技能是專案相容入口，負責 ComfyUI task 輸入映射及專案限制，不執行生成、不選換引擎，也不增加 API、模型、task 或 workflow。通用來源／參考圖職責、修改與保留項、分階段、版本管理及內容驗收規則統一依[遊戲美術共用工作流程](../game-art-workflow/SKILL.md)，避免維護兩份 brief 方法。

當需求涉及多張參考圖、只改指定部位、要維持角色或結構，或使用者希望先整理編修需求時使用。一般從零產圖沿用 ComfyUI 產圖技能；影片需求走 ComfyUI 影片技能。若使用者選擇平台圖片工具，將已整理的需求交給[平台圖片生成技能](../platform-image-gen/SKILL.md)；該技能按當下工具 schema 執行或回傳 brief，不假設本機 task 能力在平台也存在。

## 整理 brief

先依共用工作流程取得必要的來源、參考圖用途、本輪修改、保留項、版本及驗收條件，再把可執行部分映射到下方 ComfyUI task 輸入。只在關鍵來源、目標或範圍無法判斷時詢問；不要為填滿表格而重問已知資訊。

本專案常用圖片參考角色包括來源／編修目標、角色、pose／structure、appearance、背景、mask-preview 與候選。遮罩預覽只表達範圍意圖，不必然符合本機 Alpha mask 契約；參考圖板供人檢視，不能當作生成器理解多圖輸入的證據。

## 對應既有輸入

依 brief 對應既有 task 的輸入概念，不自行創造參數或替換 task：

- `refine`：來源圖、整圖風格／外觀描述及既有 task 支援的 denoise 範圍。
- `guided_inpaint`：來源圖、已確認 Alpha mask、需求所需的既有 control reference/type/strength 與／或 appearance reference/weight。
- `inpaint`：來源圖、符合本機契約且已確認的遮罩、局部修改描述。
- `character_action`：角色參考與 pose reference；身份及姿勢都須人工檢查。
- `flux2_edit`：只有使用者明確指定且既有 preflight 與驗證條件符合時才列入；只接受單一來源圖，不支援多張參考、mask 或 denoise 控制。
- `layer_split`：從完成圖和人工確認的遮罩做既有 ComfyUI Core 裁切，不需要生成底模；仍須透過本專案 ComfyUI task 入口和 gate 執行。它只切出指定單一圖層，不是自動角色拆件。
- 其他需求沿用[ComfyUI 產圖技能](../comfyui-art-gen/SKILL.md)的 task 路由、能力檢查與輸入契約。能力未知或不支援時照實列出，不用提示文字掩蓋限制。

ComfyUI 的輸入和控制能力是本機產線契約，不能直接映射成 GPT Image 或其他平台工具的功能。若選平台執行，交由平台圖片技能重新核對其即時 schema；無可用工具時交付 brief。

參考 OpenAI 圖片指南時，讀[OpenAI 圖片編修指引摘要](references/openai-image-guidance.md)。該文件只借用需求組織方式，不代表 SDXL、IPAdapter 或本機 task 具有 GPT Image API 的行為。素材整理、局部編修、透明素材檢查或其他本機工具情境見[情境與工具路徑](references/scenarios.md)。

## 固定輸入的參數比較

若使用者明確要求固定來源、prompt、seed 與參考圖，並比較事先列明的有限參數組合，轉交[ComfyUI 圖片 sweep](../comfyui-image-sweep/SKILL.md)。一般單次生成仍交由產圖技能；brief 不觸發自動重抽。

### 簡例：只改頭髮短絨

- 需求規格：以使用者指定來源圖為 edit target，只把頭髮表面改成短絨；保留髮型、髮色、臉、服裝和背景。
- 提示：`只改頭髮表面為短而細密的柔軟短絨，保留原髮色、髮型輪廓與瀏海；臉、耳朵、衣服和背景維持原樣。`
- 支援輸入：若選 `guided_inpaint`，依本機流程提供已確認 Alpha mask；appearance reference 或控制參考僅在需求和該 task 支援時使用。

這只是 brief 示意，不是已測提示或參數配方；紅色預覽本身不替代本機 Alpha mask。保留項的實際保護程度依選定 task 及是否有確定性後處理而定。

## 分階段需求與回報

分階段、來源版本選擇和驗收狀態依共用工作流程，不在本技能另定重試次數或接受規則。交付時可呈現「需求 → 本機 task 支援輸入 → 未支援項」；實際生成後回到 ComfyUI 產圖技能執行能力 gate 和技術檢查。指令符合度、可見內容觀察與使用者美術接受決定分開記錄。
