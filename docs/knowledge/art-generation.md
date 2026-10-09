---
type: guide
status: current
---
# 圖片 task 選擇與判斷

只維護 ComfyUI 圖片 task 的**選擇與判斷**：該用哪個 task、該先確認什麼、什麼時候停下來問。旗標與預設值不在這裡，查 `generate.py <task> --help`；`generate.py` 依 task 與旗標選出 `templates/image/**` 的 template（用法以 `gameart.py run show <template id>` 為準）。共用的需求整理與驗收見 [brief 與驗收](art/brief-and-acceptance.md)；平台原生生圖走 [platform-image-gen](../../skills/platform-image-gen/SKILL.md)，不讀本頁的設定。

## 環境與能力

- 執行任何 task 前先讀 repo 根目錄的 `local_config.json`（不進版控，每台機器不同）：`python_exe`、`generate_script`、`comfyui_url`、`output_dir`、能力快照路徑。不存在代表這台機器還沒裝好，照 [comfyui-install](../../skills/comfyui-install/SKILL.md) 處理，不假裝能實機產圖。不要把實際路徑寫進進版控的文件。
- ComfyUI 位址要明確傳入（`--comfy-url` 或 `--config`），不猜預設 port。每次帶 `--output-dir <output_dir>`，把成品留在 repo 的 `output/`，並把印出的路徑告訴使用者。
- `--timeout` 只是送達後輪詢的上限，逾時不代表 ComfyUI 停止工作；先查狀態，不重複送同一個任務。
- 換機或換顯卡：重跑偵測（`gameart.py doctor --refresh`）；舊快照的設備指紋對不上時，`generate.py` 會拒絕使用。

**先讀 `image_capabilities.json` 再規劃**（FLUX.2 另論）：

1. `default_profile` 是哪一份。目前只有 `sdxl_standard` 一份設定檔；使用者明確要換時才加 `--profile`。
2. `tasks.<task>.available`：不可用就看 `missing_files`／`missing_nodes`，如實說缺什麼。
3. `tasks.<task>.validation`：`verified` 直接做；`experimental` 先說明是實驗性；`unverified` 先說「這個平台或記憶體級距沒有驗證紀錄，結果可能較差」，使用者同意再做；`verified_other_env` 是曾在別的環境驗證，告知差異即可。驗證升格（`validation approve`）是使用者的決定。
4. `features`：例如 `controlnet.pose` 不可用時，不提議 `--control-type pose`。

FLUX.2（`flux2_concept`／`flux2_edit`）不使用 image profile，改走獨立的 Core node 與模型 preflight；preflight 通過只代表所需 node 與模型存在，不代表這台硬體已驗證。遮罩工具（`mask-session`、`sam`）是獨立工具，不在快照裡，`generate.py` 也不檢查它們。

## 決策順序

1. **有沒有現成 task 覆蓋？** 有就用，不因為「自己組 graph 比較快」就繞過去。真要新的固定 graph 走 [擴充協議](maintenance/extension-protocol.md)，不臨場組（[R2](rules/fixed-graphs.md)）。
2. **這台機器能不能跑、驗證過沒有？** 依上節。task 不可用就不硬送（`generate.py` 在上傳前就會拒絕），如實告知缺什麼，選項是補裝、換一台已裝好的機器、或先不做。**不要為了避開錯誤自行換設定檔或降級。**
3. **沒有現成 task、而且是一次性探索**：目前沒有 ComfyUI MCP 入口，如實說「目前沒有對應工具」，不自己臨場組 graph 頂替。
4. **沒有現成 task、而且會重複用到**：走 [擴充協議](maintenance/extension-protocol.md) 或 [新增能力清單](maintenance/new-capability-checklist.md)。

## 任務判斷

| 使用者說的像… | task | 判斷依據 |
|---|---|---|
| 「畫一個…」「生一張概念圖／場景／道具」，沒有參考圖 | `concept` | 沒有輸入圖 |
| 「用 FLUX.2 試畫」 | `flux2_concept`（實驗） | 明確指定；純文字。沒指定時仍用穩定的 SDXL `concept` |
| 「用 FLUX.2 把這張圖改成…」 | `flux2_edit`（實驗） | 明確指定；一張來源圖＋整圖修改，不是局部修補 |
| 圖示、symbol、按鈕圖案、單一遊戲小物件 | `icon_asset` | 單一、獨立、預期疊到別的畫面上的小元素，不是完整場景或 UI 版面 |
| 照這個姿勢或線稿畫，角色不重要 | `pose_only` | 只有姿勢參考，不需角色一致性 |
| 這個角色或風格套到新場景，姿勢隨意 | `style_lock` | 只有角色參考。要的是影片、首幀不必是那張定稿圖 → 影片 `character_video` |
| 這個角色換個姿勢或動作 | `character_action` | 角色參考**加**姿勢參考，兩者都要 |
| 草稿上色、精緻化、同造型換材質或顏色 | `refine` | 有來源圖，想保留大致構圖 |
| 這裡崩壞了幫我修、只改這個區域 | `inpaint` | 來源圖加確認過的遮罩，且不涉及「結構要保持、外觀要換」 |
| 換武器或道具但握姿要對、換材質但造型不能變 | `guided_inpaint` | 遮罩內「結構鎖住、外觀自由」的衝突需求；純 `inpaint` 對這類需求失敗率高 |
| 放大、解析度不夠、交件或印刷 | `upscale` | 已定稿的成品，不是重新構圖 |
| 定稿合成圖拆出外框、中心鈕等圖層 | `layer_split` | 已有定稿圖，事後切大塊區域；不吃 prompt |
| 去背、透明背景 | `--remove-bg`（`icon_asset` 永遠去背） | 可疊加在 `concept`、`pose_only`、`style_lock`、`character_action`、`refine` |
| 多出幾個版本比較 | `--batch N` | 只有探索型 task 支援；沒概念就建議 3 |
| 手動畫遮罩、自動找物件邊界 | `mask-session`、`sam` | 只產生遮罩，不產圖；完成的遮罩再交給 `inpaint`／`guided_inpaint`／`layer_split` |
| 比較有限幾組參數 | `edit sweep`（comfyui-run） | 見 [edit-tools](art/edit-tools.md) |

## 各 task 要先確認的事

只補問**前文與附件都沒有的資訊**，不重問已知答案。

- **尺寸比例**：`concept`、`pose_only`、`style_lock`、`character_action` 在沒有尺寸答案時才問；`icon_asset` 預設方形畫布，不用問；局部重繪與 `refine`、`upscale`、`flux2_edit` 不開放尺寸（`inpaint` 類跟隨來源圖）。使用者指定了不能用的尺寸就說明限制，不硬加旗標或改走別的 task。
- **`--style`**（只適用 SDXL）：使用者對美術方向有明確偏好才用，不主動問；用 `anime` 時 prompt 開頭一定要加 `score_9, score_8_up, score_7_up`，否則實測會灰階或構圖跑掉（見 [sdxl-standard](art/profiles/sdxl-standard.md)）。FLUX.2 不支援 style、negative、batch、LoRA。
- **`icon_asset`**：
  - 描述偏抽象形容詞（「科技感」「精緻一點」）時，先問有沒有參考圖或具體關鍵字，不要靠反覆生成讓使用者修正方向。
  - 結構或顏色配置**有明確答案、不該讓 AI 猜**（精確等分的放射狀分區，或內容是字母、數字這類有精確筆畫的元素）→ 用 `--structure-ref` 範本圖鎖結構，判斷與取捨見 [結構範本](art/structure-ref.md)。範本是文字時，先問「要工整易讀，還是重視風格連筆」，兩者常有取捨。
  - 使用者有一張想「質感偏向」的現成圖才問 `--appearance-ref`；參考圖若帶文字，權重要從低值（0.3–0.4）開始，否則會帶出一坨假字（見 [已知限制](art/known-limitations.md)）。
  - 整組系列（例如一整套花色）先挑一張把風格與材質配方定案，確認後再套用到其餘，不要邊做邊決定風格。
  - 要匹配現成素材包時先看它實際的解析度；探索階段用預設，最後交付前才統一縮放。
- **`pose_only`／`character_action`**：沒有姿勢參考就請使用者提供（自己擺拍或畫簡單火柴人都行）；`character_action` 另需角色參考。`--control-type` 的選擇看 [控制來源判斷](art/control-type-selection.md)；文字描述的動作要和姿勢參考一致。
- **`style_lock`**：沒有角色或風格參考就沒有一致性，不要憑空生成後假裝有。
- **`refine`**：`--denoise` 控制保留原圖的程度——0.3–0.4 大致保留原色只微調，約 0.6 細節大幅改變，0.9 以上幾乎重畫。變化太小才往上調。顏色指令太強而 denoise 太低時，蓋不過原圖。
- **`inpaint`**：**一定要有使用者確認過的遮罩範圍**，不要自己用文字猜區域。沿用已確認的遮罩，沒有才手繪或採用 SAM 候選；先看實際預覽與 Alpha 契約，範圍改變才重新確認。遮罩格式的陷阱見 [遮罩](art/masking.md)。
- **`guided_inpaint`**：遮罩原則同 `inpaint`，且最好只蓋要換外觀的區域（遮罩越貪心，不想要的東西越容易被重生）。外觀靠文字講不清楚、使用者有現成參考圖時優先用 `--appearance-ref`，並提醒最好是乾淨的材質特寫。鎖結構：手臂或肢體姿勢不能變用 `pose`；輪廓或立體起伏不能變用 `canny`（輪廓）或 `depth`（有凹凸的表面）；兩種需求都有就同時用結構鎖與外觀參考。`--appearance-ref` 抓的是風格與色彩印象，不是逐像素複製圖案。
- **`upscale`**：盡量沿用當初生成的 prompt（二次取樣需要它，風格才一致）；記不得就用畫面內容重新描述。
- **`layer_split`**：來源必須是定稿完成圖；遮罩要使用者確認過（`alpha=0` 為要保留進這一層的區域）；一次一層。適合大塊、邊界明確的區域，不適合細碎或視覺相似的重複元素。

## 複合元件的圖層（例如轉盤的外框、分區隔板、中心鈕）

依構件類型判斷，不要一招用到底（背景理由見 [圖層拆分判斷](art/layered-assets.md)）：

- **結構相異的大塊**（外框、中心鈕、指針）：各自用 `icon_asset` 生成，prompt 重複同一組風格關鍵字；不保證一致，仍需美術微調。
- **高度重複的元素**（每個分區隔板）：不要逐一生成，也不要事後用 `layer_split` 切相鄰的相似色塊。看使用者要「一片樣板自己複製組裝」（`icon_asset` 生一片，交給 Figma 或遊戲引擎旋轉複製）還是「一張結構已對的完整成品」（`--structure-ref` 一次鎖住整個結構，代價是精細裝飾被壓掉）。
- **已有定稿合成圖，想事後切大塊**：`layer_split`。
- 完整角色、尾巴、靴子、耳朵、口袋等邊界明確的部位可先用 `sam` 產候選，必須看過預覽才交給 `layer_split`；眼睛、手指、交疊瀏海可能要手繪。

## 手動遮罩與 SAM 候選

- `mask-session create` 建立工作階段，把 `EDITOR_URL` 給使用者，說「紅色區域會重新生成；沒塗紅的盡量保留，塗完按完成」，不必講節點或 Alpha。`status` 為 `completed` 才 `fetch`，取回 `mask_editor.png`、`mask_comfy.png`、`preview.png`。空遮罩會被拒絕，選取超過 98% 要二次確認。
- 手繪頁不能匯入 SAM 候選；候選不準就對來源圖重新手繪。SAM 候選沒有語意名稱，要看 contact sheet 與預覽判斷，不能只看 score；大輪廓與獨立配件效果較好（[SAM 候選](art/sam-segmentation.md)）。
- 使用者按完成，或已明確接受同一候選，就算確認，不重複詢問。

## 結果與離線檢查

成品是候選；開圖逐項看使用者明確要求的主體、顏色、姿勢、構圖、數量與排除內容，不能只看 CLI 成功。失敗時只可按已知參數語意做**一次有理由的修正**並重驗，沒有明確可調原因就停止，不換 seed 盲目重抽。修改產線或接手新機器時，離線測試（`python -m unittest discover -s tests`）不能代替一次實機 smoke test。

## 深入參考

| 狀況 | 讀這頁 |
|---|---|
| 使用者提出特殊參數要求 | [art-parameters.md](art-parameters.md) |
| 判斷 `--control-type` | [control-type-selection](art/control-type-selection.md) |
| 遮罩沒生效、局部修圖變差 | [masking](art/masking.md) |
| 「這個能不能做到」或看起來像已知限制的失敗 | [known-limitations](art/known-limitations.md) |
| 結構或數量用文字講不清楚 | [structure-ref](art/structure-ref.md) |
| 設定檔調校經驗與驗證紀錄 | [sdxl-standard](art/profiles/sdxl-standard.md) |
| 素材紀錄與驗收 | [result-records](result-records.md) |

## 機器等級不足時

可用記憶體低於 8000 MB（含只有 CPU、讀不到 Apple 記憶體）的機器 tier 是 `null`，圖片 task 會在上傳前停下，不會自動降級到別的底模。如實告知使用者，建議改用 [platform-image-gen](../../skills/platform-image-gen/SKILL.md) 或換一台已裝好的機器（`--comfy-url` 指過去）。圖片 graph 唯一來源是 `templates/image/**`，沒有對應 template 的旗標組合會被拒絕，不會退回別的路徑。
