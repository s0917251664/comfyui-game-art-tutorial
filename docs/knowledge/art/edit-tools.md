---
type: reference
status: current
---
# 本機圖片編修工具

`tools_src/image_edit_tools.py` 提供六種本機操作：Alpha 遮罩合成、遮罩內純色相調整、RGBA byte 差異檢視、固定輸入的有限參數 sweep、參考圖板與素材 Alpha 稽核。它不含生成模型、ComfyUI graph 或新的 `generate.py` task。操作入口是 [`skills/local-media-tools/references/local-image-edit-tools/README.md`](../../../skills/local-media-tools/references/local-image-edit-tools/README.md)，情境選擇見[圖片編修情境手冊](../../../skills/game-art-brief/references/game-art-edit-brief/references/scenarios.md)。

## 能力與契約

### 遮罩合成

`composite --source <png> --edited <png> --mask <png> --output-dir <new-dir>` 將編修結果合成回來源。source 與 edited 尺寸必須一致；mask 必須是帶 Alpha 的同尺寸 PNG。Alpha 0 選 edited，255 選 source，中間值對 RGBA byte 逐通道插值。這是 mask 選擇合成，不是 foreground alpha-over，也不是在線性光空間混合。輸出 `composited.png`、`result.json`；alpha 255 區域有逐 byte 保留檢查。`--keep-source-alpha` 為選配，使用來源圖的 Alpha 作為輸出 Alpha；省略時仍依原契約對完整 RGBA byte 插值。不可覆寫既有目錄。

### 遮罩內純換色

`recolor --source <png> --mask <alpha-mask.png> --from-hue <0-360> --to-hue <0-360> --hue-range <0-180> --min-saturation <0-1> --output-dir <new-dir>` 對同尺寸、單影格且帶 Alpha 的遮罩所界定區域，僅修改可見、符合來源色相範圍與最低飽和度條件的像素。遮罩 Alpha 小於 255 表示可編輯，255 排除；未匹配及遮罩外 RGBA、來源 Alpha 均保留。這是 HSV hue rotation（HSV 色相旋轉），不呼叫生成模型、不保證精確 RGB、不新增紋理或改變材質，也不做物理光照重算。工具不提供語意分割或繪製遮罩；選區需人工檢查。輸出 `recolored.png`、`comparison.png`、`result.json`，須使用新目錄，manifest 的接受狀態留待人工確認。單案例限制與逐像素證據見[單一物件換色](single-object-color.md)。

### 差異檢視

`compare --source <png> --edited <png> [--mask <png>] --output-dir <new-dir>` 產生差異 heatmap、接觸圖與 `comparison.json`；有 mask 時提供 mask 內、過渡帶、mask 外的統計，且 mask 含非 255 alpha 區域時另產生局部 detail sheet。差異以解碼後 RGBA byte 計算，包含 alpha 為 0 的像素隱藏 RGB，不作影像配準、縮放、感知閾值或美術評分。

### 固定輸入參數 sweep

`sweep --plan <plan.json> --config <runtime.json> --output-dir <new-dir> [--profile <id>] [--timeout 240] [--dry-run] [--allow-unverified]` 只包裝既有 `refine`、`inpaint`、`guided_inpaint`、`character_action`。參數 whitelist、plan schema、範例及中斷處理見 [`plan-format.md`](../../../skills/local-media-tools/references/local-image-edit-tools/reference/plan-format.md)。

seed、prompt、來源與參考固定；只能在現有 task 白名單的 0–1 權重參數中建立笛卡兒積，最多 16 次，禁止重複值。空 `sweep` 代表固定輸入下單次執行。這用於使用者明確提出、事前界定的多組參數比較，不能取代一般任務的產後驗收或作為盲目重抽工具。`preserve_outside` 僅支援 `inpaint`、`guided_inpaint`，每次生成後另外用同一遮罩合成並產生 raw/final comparison。

每次 run 透過 `generate.py` 寫入原生 `generation.json` manifest；總目錄含 `sweep.json`、逐 run log、比較資料夾與 `candidates.png`。Queue 需在開始前為空。未完成或失敗時停止後續提交並保存狀態，不自動重送。timeout 後先查 queue。所有輸出都是待美術審核者逐張檢視的 candidate，不會由程式自動評定 accepted/rejected。

### 參考圖板與 Alpha 稽核

`reference-board --plan <plan.json> --output-dir <new-dir>` 將 1–12 張原圖做成供人工檢視的用途標籤版面，並輸出 `reference_board.png` 和帶路徑／hash／尺寸資訊的 `references.json`。Plan 只能含 `items`；每筆只能有 `path`、`label`、`role`，路徑相對 plan JSON 所在資料夾，role 限 `source`、`character`、`pose`、`appearance`、`mask-preview`、`candidate`，label 最多 120 字元。Board 不是生成輸入，task 必須使用原始圖片與其既有參數欄位。

`asset-audit --image <image.png> --output-dir <new-dir>` 輸出 `audit.json` 及白／黑／棋盤預覽。它只報告原始尺寸、Alpha 通道、完全透明／半透明／不透明像素數、可見像素框及可見像素是否碰邊；預覽最長邊 1200 px，統計使用原始解析度。工具不修改素材、不修邊、不判斷文字、姿勢、角色、物件結構或美術接受度。兩者都只需要 Pillow／NumPy 和檔案路徑，不需要 ComfyUI server、runtime config 或 image capability；每次輸出需使用新目錄。

## 安裝與部署

本機依賴為 Pillow 與 NumPy，沿用現有 ComfyUI Python 環境；無需新增模型或 custom node。單一 source 檔部署到 `<ComfyUI 安裝路徑>/tools/image_edit_tools.py`。repository 的 `verify_portable_install.py` 具有對應同步條目；部署驗證範圍及安裝步驟見 [`skills/comfyui-install/SKILL.md`](../../../skills/comfyui-install/SKILL.md) 與 [`installation/install-guide.md`](../installation/install-guide.md)。

## 驗證狀態與觀察

2026-10-01 在 Windows / `windows-cuda`、NVIDIA GeForce RTX 4080（16,376 MiB VRAM）、`sdxl` tier 環境完成 standalone composite、standalone compare 與 sweep dry-run；四個既有圖片 task 共產生六張 832×1232 候選，所選 profile 均為 `sdxl_standard`。`guided_inpaint`、`inpaint`、`character_action` 使用 `sd_xl_base_1.0.safetensors`；`refine` anime 使用 `ponyDiffusionV6XL_v6StartWithThisOne.safetensors`。guided 與 character action 使用既有 IPAdapter、CLIP Vision 與 Canny。`guided_inpaint` 固定 seed `180806271566581`、source/mask/material reference/Canny control，分別以 denoise 0.8 與 1.0 產圖；raw comparison 在 alpha=255 保留區分別量到 815,312 與 846,943 個改動像素。composite 後 mask 外改動為 0，保留區共 902,053 像素，並由獨立 NumPy 比對確認。

畫面觀察：guided 0.8 結果是低飽和淺藍細絲，1.0 是鮮亮藍細絲，且 mask 內輪廓外仍可見淡色暈邊；不能據此宣稱「短絨」要求達標。`inpaint` 的單張候選把頭髮改成灰褐色且髮型大幅改變。`refine` anime seed `278787708121530` 的 denoise 0.4、0.6 各一張，0.6 對髮型、衣服和腰帶的改動更明顯。`character_action` 使用角色來源與 `reports/.../pose-reference-isolated.png` 姿勢 Canny reference，產生一張；姿勢與槌方向接近姿勢圖，但帶入毛邊帽造型，臉與服裝也不是原角色。所有候選均是待美術審核者驗收的輸出，這些單案例觀察不構成引擎排名或 task quality validation。

部署 verifier `verify_portable_install.py --require-image` 回報 17 pass、0 fail；單元與部署測試共 30 項通過，Python syntax 檢查通過。重現命令與耗時在 `output/local_edit_tools_20261001/execution.json`，獨立尺寸、通道、秒數與保留區核對在 `independent-validation.json`；完整腳本為 `run_smoke.py`。原始輸出在同目錄下的 guided、refine、inpaint、character 子目錄，以及 standalone-composite、standalone-compare。耗時受首張模型載入快取影響，不可用來比較 task 效率。ComfyUI server 曾出現既有 `comfyui.db` 權限警告，但六張生成完成；本次未更動資料庫。離線驗證、CLI smoke 與單案例畫面觀察不會自動改寫 image profile 或 task 的 validation 狀態。

2026-10-02 新增的參考圖板與 Alpha 稽核在 Windows／RTX 4080 環境實跑：33 項工具測試通過，部署 verifier 18 項通過，並確認拒絕既有 output 目錄。三張參考圖輸出 1080×420 board，中文職責完整、縮圖未裁切；2048×2048 RGBA cutout 記錄 2,708,657 透明、192,410 半透明、1,293,237 不透明像素，bbox `[134, 59, 1910, 2003]`；832×1232 RGB 圖則正確標出無 Alpha、無透明像素與內容碰邊。輸出證據與預覽在 `output/scenario_tools_20261002/`（本機證據）；此驗證只證明板面整理與機械 Alpha 檢查，不驗收生成圖或去背美術品質。

2026-10-03 單件青綠玻璃瓶測試中，既有 `refine` denoise 0.5 與 0.75 兩次均未得到紅色，且 0.75 對瓶塞／形狀改動較多；停止抽樣後以本機 `recolor` 產生紅色 candidate。單元測試 43 項通過，部署 verifier 19 項通過；candidate 尚待美術審核者驗收。具體遮罩、像素數、Alpha／區域比對及本機 trace 連結見[單一物件換色紀錄](single-object-color.md)；其 `output/` 證據只在原實驗工作樹保存，乾淨 clone 不一定含有。這項紀錄不改變 profile 或 task validation。

## 官方參考與本機適配

- OpenAI [Image prompting](https://developers.openai.com/api/docs/guides/image-prompting)：官方建議需要像素完全一致的保留區域時，將確認過的編修結果合成回原圖。本機 `composite` 將此方法實作為明確的 Alpha 選擇與保留區逐 byte 檢查；它不會自行核准候選，也不代表 SDXL 具有 OpenAI 圖片 API 的語意編修能力。
- OpenAI Cookbook [Image evals](https://developers.openai.com/cookbook/examples/multimodal/image_evals)：以固定案例和評估維度比較輸出，並觀察局部修改對其他內容的影響。本機 sweep 將此思路適配為固定 seed／輸入、少量預先指定參數，以及 mask 內外的 exact RGBA byte 統計；這是本機工程設計，不是該 Cookbook 提供的 ComfyUI 功能，也不會自動判定美術品質。
- Pillow [`Image.composite`](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.composite)：以 mask 合成兩張圖片。本工具另以程式契約明確固定 Alpha 方向與 RGBA byte 語意。
- NumPy [array indexing](https://numpy.org/doc/stable/user/basics.indexing.html)：布林索引與陣列取樣統計的官方參考。

官方來源支援需求表達、比較方法與底層函式庫使用方式，不是本機實機生成品質或美術驗收的證據。
