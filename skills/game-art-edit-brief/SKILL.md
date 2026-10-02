---
name: game-art-edit-brief
description: 整理遊戲圖片編修前需求，將來源圖、參考圖用途、修改與保留項映射到專案既有圖片 task。用於多參考圖、指定局部修改、維持角色／結構或先整理編修需求；一般從零產圖與影片不適用。
---

# 遊戲圖片編修需求整理

此技能只準備可交給既有產圖流程的編修 brief，不執行生成、不選換引擎，也不新增付費服務、API、模型、task 或 workflow。需要產出時，依使用者選擇交回 [ComfyUI 產圖技能](../comfyui-art-gen/SKILL.md)；若使用者明確選擇平台 image_gen，依該平台當下可用功能處理，不假設本機 task 能力也存在於平台，反之亦然。

當需求涉及多張參考圖、只改指定部位、要維持角色或結構，或使用者希望先整理需求再生成時使用。一般從零產圖沿用產圖技能；影片需求走影片技能。

## 整理 brief

依需要整理下列資訊，不要求每案填完整表格；缺少但不妨礙需求表達的欄位可省略。只在關鍵來源或修改範圍無法判斷時，詢問必要問題。

- 來源圖與版本：引用使用者提供的圖或既有素材紀錄。未有 Steve 明確驗收紀錄時，不稱為已接受母版。
- 這次要改的內容，以及不得變動的角色、姿勢、服裝、構圖、色彩或其他結構。
- 每張參考圖的用途與範圍：哪張是 edit target，哪張只提供 appearance、pose／structure 或 mask preview。風格參考中的其他角色與場景不得當成要引入的內容。
- 預計 task、其支援輸入，以及使用者提出但 task 不支援的要求。不要用座標臨時猜局部範圍；紅色遮罩預覽只表達範圍意圖，不能代替本機需要的 Alpha mask。
- 一段精簡、自然的正向提示，清楚說明要改什麼和要保留什麼。保留使用者指定的精確詞句；不要宣稱提示更長必然更好。風格 token（如 Pony tags）依現有 profile/task 文件。
- 產出後要檢查哪些可見項目，並分開記錄提示遵循情況、實際輸出觀察及 Steve 的美術接受決定。

## 對應既有輸入

依 brief 對應既有 task 的輸入概念，不自行創造參數或替換 task：

- `refine`：來源圖、整圖風格／外觀描述及既有 task 的 denoise 範圍。
- `guided_inpaint`：來源圖、已確認 Alpha mask、需求所需的 `[control_ref/type/strength]` 與／或 `[appearance_ref/weight]`。
- `character_action`：角色參考與 pose reference。
- `flux2_edit`：只有使用者明確指定且既有 preflight 與驗證條件符合時才列入；此 task 使用單一來源圖，不支援多張參考、mask 或 denoise 控制。
- 其他需求沿用 [ComfyUI 產圖技能](../comfyui-art-gen/SKILL.md) 的 task 路由與能力檢查。能力未知或不支援時照實列出，不用提示文字掩蓋限制。

參考 OpenAI 圖片指南時，讀 [OpenAI 圖片編修指引摘要](references/openai-image-guidance.md)。該文件只借用需求組織方式，不代表 SDXL、IPAdapter 或本機 task 具有 GPT Image API 的行為。

brief 完成後，若 Steve 明確要求固定來源、seed 與參考並比較事前指定的有限參數組合，可依需求交接至[本機圖片編修工具](../local-image-edit-tools/SKILL.md) 的 sweep；一般單次生成仍交由產圖技能，不把 brief 流程變成自動多次重抽。

### 簡例：只改頭髮短絨

- 需求規格：以使用者指定來源圖為 edit target，只把頭髮表面改成短絨；保留髮型、髮色、臉、服裝和背景。
- 提示：`只改頭髮表面為短而細密的柔軟短絨，保留原髮色、髮型輪廓與瀏海；臉、耳朵、衣服和背景維持原樣。`
- 支援輸入：若選 `guided_inpaint`，依既有流程提供已確認 Alpha mask；appearance reference 或控制參考僅在需求和該 task 支援時使用。

這是 brief 示意，不是已測提示或參數配方；紅色預覽本身不替代本機 Alpha mask。

## 分階段需求與回報

若一項請求包含多個可分開驗收的改動，可依使用者用途拆成階段；不強制每次只能改一項。後續階段沿用使用者明確選定的版本，不把上次產生的漂移 candidate 自動當作母版。生成與修正仍受既有產圖技能的一次有理由修正界線限制。

交付 brief 時，讓使用者看得出「需求規格 → 提示 → task 支援的輸入」。生成後記錄實際輸入、提示和參數、產物及具體觀察；指令符合度與 Steve 的美術接受狀態分開記，未知狀態照實保留，不作引擎排名。
