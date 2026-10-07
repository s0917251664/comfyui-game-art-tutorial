# 圖片編修情境與工具路徑

這份情境手冊保留 ComfyUI 與本機圖片工具的輸入映射、日期化實測及限制，不是跨平台通用執行規格。共用需求與內容驗收由[共用工作流程](../../game-art-workflow/SKILL.md)維護；平台生成依[平台圖片技能](../../platform-image-gen/SKILL.md)的當下工具能力，不照搬本表 task／參數。參考板協助人查看素材，不是生成輸入，也不會增加模型可用的參考圖數量。

只讀本次情境那一列及必要的實測／契約小節，不整份載入提示資料或全部案例。表中的 `sweep` 交由[ComfyUI 有限參數比較](../../comfyui-image-sweep/SKILL.md)執行；其餘五個圖片檔案工具不需 ComfyUI。

| 情境 | 準備 brief 時要說明 | 本機流程與可用工具 | 必須人工確認 |
|---|---|---|---|
| **1. 角色一致性與換姿勢** | 哪張是角色來源；臉、髮型、服裝、裝備、比例與配色哪些固定；哪張只提供姿勢；背景是否可改 | 用 `reference-board` 列出 `source`／`character`／`pose` 用途；依 `character_action` 既有角色與 pose reference 欄位生成。動作優先時可評估 `pose`，但 Q 版可能偵測不到骨架；`canny` 可能連衣服、帽子輪廓一起帶入。沒有可用骨架時不自動 fallback。輸出可用 `asset-audit` 檢查 Alpha、尺寸與邊界 | 角色外觀和姿勢是否都符合。IPAdapter 可能把參考中的造型帶入結果；asset-audit 不認識角色特徵。 |
| **2. 換裝、配件或盔甲改版** | 指定要換的衣物／配件、要保留的角色特徵；外觀參考只供造型、材質或配色中的哪部分；是否需要分階段 | `reference-board` 區分角色來源、服裝 appearance reference、範圍預覽；有已確認 Alpha mask 時，檢查 `guided_inpaint` 的 appearance 欄位是否符合需求；沿用使用者選定的角色版本處理下一階段 | 服裝輪廓、配件位置與角色身份是否保留；參考圖中的模特、姿勢或背景有無被帶入。工具不自動評估裝備設定。 |
| **3. 只改表面材質或顏色** | edit target；只改哪個表面及材質／顏色；保留輪廓、鄰近部位和其他顏色；appearance reference 只借用什麼 | 手動畫並人工確認 Simple Mask Tool 的 Alpha mask；可選 `/refine` 邊界預覽；依需求用 `guided_inpaint` 的來源圖、mask 與適用的 appearance/control reference；`composite` 做 Alpha 選擇合成，`compare` 查看像素差異 | 生成結果可能超出遮罩語意邊界；確認 mask 和合成方向正確、暈邊可接受。沒有 before/after 專用 UI 能力時，需自行明確保留對照輸入與輸出檔案。 |
| **4. 依風格參考改整體質感** | 來源圖與風格參考；只借用筆觸、明暗、材質或色調中的哪些；不得改動的角色、道具與構圖 | 以 `reference-board` 對照來源與外觀參考；整體修改可評估既有 `refine`；圖示則依欄位評估 `icon_asset` 的 appearance reference。固定輸入及 seed、比較允許的既有參數時可用 `sweep` | `refine` 是整圖編修，未以 mask 指定局部時不能假設其他內容不變；外觀參考可能帶入原圖中不想要的內容。 |
| **5. 多張圖各有不同職責** | 每張標記為 `source`、`character`、`pose`、`appearance`、`mask-preview` 或 `candidate`；指出衝突時的優先順序 | 用 `reference-board` 一次並列最多 12 張原圖與用途標籤；依 task 分別接既有欄位，例如 `character_action` 的角色＋pose、`guided_inpaint` 的來源＋mask＋適用 control／appearance | reference board 只供人檢視；生成時傳原始圖片到 task 支援的欄位。不能把板面當成一張多圖生成輸入；`flux2_edit` 僅支援一張來源圖。 |
| **6. 透明角色、道具或圖示交付** | 需要透明背景；物件完整輪廓與安全邊距；陰影、髮絲或半透明材料是否需要保留 | 依既有 task 支援使用 `--remove-bg`；`icon_asset` 固定去背。產出後以 `asset-audit` 檢查 Alpha 統計、visible bbox、碰邊與尺寸，並看白／黑／棋盤預覽 | 棋盤預覽中邊緣是否有光暈、洞或裁切。Alpha 通道存在不等於去背美術品質通過。 |
| **7. 鎖定道具／圖示的結構** | 數量、輪廓、方向、顏色區塊哪些不可變；要改的是表面還是結構；準備清楚的範本圖 | `reference-board` 標出結構範本與外觀參考；依 `icon_asset` 既有 `--structure-ref`／appearance 欄位處理。設定支援限制參考 [structure-ref 文件](../../../docs/knowledge/art/structure-ref.md) | 人工核對數量、排列和細節；`asset-audit` 不辨識形狀或結構，structure-ref 的細節能力仍受已知限制。 |
| **8. 分階段完成複合改動** | 把可分開驗收的部分排成階段，例如剪影→姿勢→服裝→表面材質；每階段標明採用的來源版本和不得變項 | 對每階段整理 reference board；每次只在需求允許下處理對應的既有 task；記錄 prompt、seed、輸入版本與產物。只有美術審核者明確選定的版本才可作下一階段來源 | 不把未驗收的 candidate 自動當母版。若使用者要一次完成多項改動，照需求交付並逐項檢查，不強制拆成多次生成。 |
| **9. 有界比較與結果回顧** | 固定來源、prompt、seed 與所有參考，只列可掃描的一兩個已支援參數及每一版觀察重點 | `sweep` 只包裝 `refine`、`inpaint`、`guided_inpaint`、`character_action`，最多 16 個候選；用 `compare` 看 byte-level 差異；`asset-audit` 可確認透明與邊界等基本條件 | 固定輸入不可 sweep；差異像素或區域統計不是語意判斷或美術分數。分開記錄技術結果、人工 brief 觀察和美術審核者的接受決定。 |

## 新增的本機輔助工具

`asset-audit` 與 `reference-board` 整合於既有 `tools_src/image_edit_tools.py`；不新增依賴或部署檔。指令會拒絕既有輸出目錄，請每次使用新的輸出路徑。

### 整理參考圖板

```powershell
python tools_src/image_edit_tools.py reference-board --plan <plan.json> --output-dir <new-dir>
```

Plan JSON 只能有 `items` 鍵，含 1–12 筆；每筆只能有 `path`、`label`、`role`。相對路徑以 plan JSON 所在資料夾解析。role 只接受 `source`、`character`、`pose`、`appearance`、`mask-preview`、`candidate`；label 必須是非空文字且最多 120 字元。

```json
{
  "items": [
    {
      "path": "inputs/character.png",
      "label": "角色來源：保留臉型、髮型與衣服形狀",
      "role": "source"
    },
    {
      "path": "inputs/material.png",
      "label": "材質參考：只參考短絨質感",
      "role": "appearance"
    },
    {
      "path": "inputs/mask-preview.png",
      "label": "範圍預覽，不是生成遮罩",
      "role": "mask-preview"
    }
  ]
}
```

輸出 `reference_board.png` 及含原檔路徑、SHA-256、尺寸和 role 的 `references.json`。縮圖保持比例，最長邊不超過格子範圍；JSON 仍記原圖尺寸和路徑。原圖才是 task 輸入，board 只供人工檢視。repo 範例：plan（本機證據：`output/scenario_tools_20261002/references-plan.json`）、board（本機證據：`output/scenario_tools_20261002/board/reference_board.png`）。

### 稽核 Alpha 與基本素材狀態

```powershell
python tools_src/image_edit_tools.py asset-audit --image <image.png> --output-dir <new-dir>
```

輸出 `audit.json`、白／黑／棋盤背景預覽。只報告原始尺寸、Alpha 通道、完全透明／半透明／不透明像素數、可見像素框和可見像素是否碰畫布邊界；預覽長邊最多 1200 px，統計使用完整解析度。工具不修改來源、不修邊、不檢查文字、姿勢、角色特徵、形狀或美術接受度。audit 的 `findings` 只表示列明的機械檢查，不是整體素材合格判斷。

## 產後人工觀察

借用 OpenAI image eval 的維度作為檢查問題，不轉成自動評分：

- **需求符合度**：本輪指定的修改是否出現，呈現方式是否符合 brief？
- **局部性**：是否集中在預期區域？區分生成變動與後續遮罩合成結果。
- **保留項**：臉、輪廓、姿勢、裝備、文字或背景等固定內容有無漂移？
- **空間關係**：物件、肢體、配件的位置與方向是否正確？
- **交付條件**：尺寸、格式、透明通道等可機械檢查條件是否符合？

`compare` 顯示像素差異，不理解語意；`asset-audit` 只檢查 Alpha／尺寸／碰邊，不懂圖像內容。最後將工具數據、brief 的人工觀察與美術審核者的 candidate／accepted／rejected 決定分開記錄。

## 官方方法與本機界線

- [Image prompting guide](https://developers.openai.com/api/docs/guides/image-prompting)：角色特徵 anchor、保留項與逐輪說明改動。適配為簡潔列出不變項與本輪目標，不保證本機生成效果。
- [Image generation models prompting guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide)：參考圖職責、風格、換裝、多圖合成與角色一致性情境。適配為先分清素材用途，再按 task 契約映射欄位；本機 task 不因此支援任意多圖輸入。
- [Image evals](https://developers.openai.com/cookbook/examples/multimodal/image_evals)：指令正確性、局部性、保留項和空間關係。適配為人工觀察項目，不是本機自動評分器。
- [Transparent image assets](https://developers.openai.com/cookbook/examples/multimodal/transparent-image-assets-for-campaigns-and-presentations)：透明素材的準備與交付參考。本機生成與去背仍依既有 task。
- [High input fidelity example](https://developers.openai.com/cookbook/examples/generate_images_with_high_input_fidelity)：只借用關鍵細節保留檢查；API 專屬參數不移植到 ComfyUI。

## 實測證據與限制

2026-10-02 Windows／RTX 4080 專案環境：兩新工具及既有 image edit tools 共 33 項測試通過；部署驗證 18 項通過，拒絕覆寫既有輸出目錄的錯誤案例也已實測。

- 三張來源、appearance、mask-preview 參考圖產生 1080×420 board；中文標籤完整，縮圖保留比例且未裁切。root 目視檢查版面：board 圖（本機證據：`output/scenario_tools_20261002/board/reference_board.png`）、references.json（本機證據：`output/scenario_tools_20261002/board/references.json`）。工具仍只作人工參考整理。
- 2048×2048 RGBA cutout 記錄 2,708,657 個透明像素、192,410 個半透明像素、1,293,237 個不透明像素，visible bbox `[134, 59, 1910, 2003]`，沒有列出的 Alpha／碰邊 finding：audit.json（本機證據：`output/scenario_tools_20261002/alpha/audit.json`）。
- 832×1232 RGB 角色圖正確報告 `no_alpha_channel`、`no_fully_transparent_pixels`、`visible_pixels_touch_canvas_edge`：audit.json（本機證據：`output/scenario_tools_20261002/opaque/audit.json`）。這只表示該圖不含 Alpha 且內容貼邊，不代表它不適合其他用途。
- 部署輸出：deployed-board（本機證據：`output/scenario_tools_20261002/deployed-board/`）、deployed-alpha（本機證據：`output/scenario_tools_20261002/deployed-alpha/`）。實際部署位置仍遵循 `image_edit_tools.py` 的既有部署契約。

上述證據只確認工具整理與基本 Alpha 檢查行為，不驗收生成結果、去背邊緣或美術品質。reference board 的狀態為 `candidate`；asset audit 的狀態為 `observed`，都保留人工判斷。

## 三個代表案例實跑觀察

2026-10-02 以 `sdxl_standard`、seed `20261002` 跑了三個代表 task，共四張生成圖（圖示含一次有理由修正）。以下是 root 對輸出畫面的觀察與技術記錄；**所有輸出仍是待美術審核者檢視的 candidate，只代表這三個情境，不代表其餘情境已驗證，也沒有更動 profile 或 task validation。**完整 argv／prompt 在 `execution.json`（本機證據：`output/scenario_generation_20261002/execution.json`），task manifest 各在案例資料夾的 `generation.json`，人工觀察在 `review.json`（本機證據：`output/scenario_generation_20261002/review.json`）。

- **局部材質，`guided_inpaint`（21.08 秒）**：832×1232 藍髮呈現密集細纖維、部分纖維偏長，髮型輪廓大致保留，但沒有精準呈現短絨參考材質。raw comparison 在 926,576 個保留區像素中有 870,763 個 byte 改動；按已確認 mask 合成後保留區改動為 0。手繪 mask 中未選到的小洞仍保留。輸出見 `material`（本機證據：`output/scenario_generation_20261002/material/`） 與 `material-final-diff`（本機證據：`output/scenario_generation_20261002/material-final-diff/`）。
- **角色姿勢，`character_action`（11.05 秒）**：832×1232 輸出大致跟上斜向跳躍、雙手持槌的姿勢；帽緣、捲髮與衣服形狀受 pose reference 污染，原角色的藍色馬耳、bob 髮型及水手服身份沒有保住，因此角色身份要求未達成。輸出見 `action`（本機證據：`output/scenario_generation_20261002/action/`）。
- **`character_action` 控制方式比較（2026-10-02，Windows CUDA）**：以 `sdxl_standard`、相同 prompt 與 seed `20261002` 重跑，生成條件唯一變更為 `--control-type canny`→`pose`。pose 輸出較接近藍髮、動物耳朵與深藍短褲，但成了站姿且沒有槌子，動作要求未達成；輸出仍是待美術審核者檢視的 candidate。ComfyUI history 的 node 8 `openpose_json` 為 `people=[]`、512×512 畫布，顯示這次沒有偵測骨架，因此不能稱為成功的 pose 控制；資料見 `pose-keypoints.json`（本機證據：`output/scenario_generation_20261002/action-pose/pose-keypoints.json`）。原角色與姿勢參考分別是 `character-master.png`（本機證據：`output/platform_retest_20261001/inputs/character-master.png`） 與 `reports/skye-ai-art-pipeline-v9/assets/images/pose-reference-isolated.png`（`reports/` 不進版控，只在原實驗機器上），pose 輸出見 `character_action_00038_.png`（本機證據：`output/scenario_generation_20261002/action-pose/character_action_00038_.png`）。task 的 `verified` 只表示執行能力／輸出契約有驗證，不保證角色身份、姿勢或美術品質。
- **透明道具圖示，`icon_asset`（7.50 秒，另有一次有理由修正）**：1024×1024 RGBA 初版是青藍冰槌搭金色細節。原始 RGB 可見的徽記區域 Alpha 全為 0，所以黑底預覽中不顯示。固定 seed 後以 negative prompt 排除文字／標記／徽記等再生成，槌頭輪廓也改變；單一修正不足以證明品質改善。見 `icon`（本機證據：`output/scenario_generation_20261002/icon/`）、`icon-correction`（本機證據：`output/scenario_generation_20261002/icon-correction/`） 與 `icon-audit`（本機證據：`output/scenario_generation_20261002/icon-audit/`）。

三例展示的是 brief、既有 task 與本機工具可如何串接，以及需要如何記錄失配；不能據此宣稱 task 已保證達成需求，亦不把 tool audit、像素統計或 root 觀察當作美術審核者的驗收。

## task 輸入依據

需求入口見[遊戲圖片編修 brief 技能](../SKILL.md)，task 欄位見[完整參數規格 art-parameters.md](../../../docs/knowledge/art-parameters.md)。工具契約見 [local-image-edit-tools 技能](../../local-image-edit-tools/SKILL.md)及[ edit-tools 知識頁](../../../docs/knowledge/art/edit-tools.md)。`guided_inpaint` 需已確認 Alpha mask；`character_action` 是角色與 pose reference；`flux2_edit` 僅單張來源、不支援多參考、mask 或自訂 denoise。不能從 OpenAI API 文件推定本機 task 支援其他輸入。
