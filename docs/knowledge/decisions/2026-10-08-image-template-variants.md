---
type: adr
status: proposed
date: 2026-10-08
---
# ADR 草稿：圖片 template 的結構變化（D13）與 profile／tier 對應

> 狀態是 `proposed`：**需要使用者決定**後才生效。決定之前，第 4.2 階段不開始。

## 背景

第 4 階段要把圖片 task 的 Python builder（`tools_src/comfyui_pipeline/image_graphs.py`）抽成 `templates/image/**`。[第二階段 ADR](2026-10-07-phase2-template-runner.md) 的 D13 把一個問題留到這裡：LoRA、去背、ControlNet 這類**要插入節點**的變化，怎麼放進 template。另外還要決定 profile／tier（sd15、sdxl、sdxl_high、sdxl_light）怎麼對應到 template。

現有 runner 的限制（`runner/template.py`）：
- slot 只能改既有 input 的值；
- option 只有 `set_link`（新增一條連線）和 `set_value` 兩種，而且是布林；
- `check_patched` 禁止新增或刪除節點，也禁止改 class_type。

所以目前的 runner 只能表達「同一張 graph 換值」。圖片 builder 的結構變化有三種：
- 插入節點：LoRA 插入 `LoraLoader`；去背在尾端接 5 個節點；Union 後端插入 `SetUnionControlNetType`；
- 換節點類型：`control_type` 會把前處理節點換成 `Canny`／`OpenposePreprocessor`／`DepthAnythingV2Preprocessor`；
- 改輸出：去背的輸出改成透明圖那個 `SaveImage`。

## 兩個方案

- **方案 A：variant template。** 每種結構組合各一份固定 graph，例如 `image/sdxl/concept`、`image/sdxl/concept-lora`、`image/sdxl/concept-transparent`、`image/sdxl/concept-lora-transparent`。runner 完全不用改。呼叫端（第 5 階段的薄轉接）依 CLI 旗標選出 template id。
- **方案 B：擴充 option 操作。** 每個 task 一份 base graph，option 可以插入或替換節點。option 改成多選一（`choices`），新增三種 op：`add_node`、`replace_node`、`relink`。每個 choice 可以宣告自己的 slot、models、requires_custom_nodes、outputs。

## 原型與等價結果

原型放在 [`templates/_drafts/image-variants/`](../../../templates/_drafts/image-variants/README.md)。這個資料夾以底線開頭，runner 的 `discover` 不會收錄。這次沒有改 `tools_src/`，也沒有新增正式 template。

| | 方案 A | 方案 B |
|---|---|---|
| 原型範圍 | concept：sdxl、sd15 各 4 份（LoRA × 去背）；pose_only：sdxl 12 份（control_type 3 × 後端 2 × LoRA 2）。共 **20 份** template，JSON 7,670 行 | concept：sdxl、sd15 各 1 份 base；pose_only：sdxl 1 份 base。每份加一個 `variants.json`。共 **3 份** template，JSON 1,726 行 |
| runner | 現有 runner：`load_template`、`resolve`、`patch` 原樣使用 | base 用現有 runner 載入並填 slot，結構變化交給獨立 helper [`option_ops.py`](../../../templates/_drafts/image-variants/option_ops.py) |
| graph 來源 | 產生器 [`build_drafts.py`](../../../templates/_drafts/image-variants/build_drafts.py) 用代表值呼叫 builder（只讀）一次，必填文字換成占位、seed 換成 -1，之後就固定 | base graph 和方案 A 的無變化版本位元組相同；choice 的 ops 由同一支產生器比較 variant 和 base 的差異產生 |

等價判準：測試 [`tests/test_image_variant_drafts.py`](../../../tests/test_image_variant_drafts.py) 拿 99 組圖片 golden 的相關子集，逐欄位比對（含 int／float 型別，以及輸出節點）。

| 檢查 | 案例數 | 方案 A | 方案 B |
|---|---|---|---|
| golden 子集：concept、concept_lora_style_size、concept_remove_bg（4 個 tier），pose_only_canny／pose／depth／union_depth（3 個 SDXL tier） | 24／99 | 24 相同 | 24 相同 |
| 全部組合直接和 builder 比（含 golden 沒有的 LoRA＋去背、Union＋LoRA） | 52 | 52 相同 | 52 相同（模型清單也和方案 A 一致） |
| Q2 另一案：sd15 用 sdxl template 加 checkpoint、解析度的值 | 3 | graph 相同，但模型 pin 仍是 SDXL 底模 | — |
| 方案 B 的防呆：未知 choice、沒選到時不需要的 slot、兩個 option 改到同一個 input、`replace_node` 和別的 option 改同一個節點（不論書寫順序）、`set_value` 的連線指向別的 option 插入的節點、兩個 option 都改 outputs、片段占位沒人認領、沒宣告的節點 | 8 | — | 都會拒絕 |

（本機證據：`output/verify-20261008-4.1/`，內含測試前後的完整測試紀錄與案例數報告。）

結論：**兩個方案都能做到和 builder 逐欄位相同**。golden 等價不能用來二選一，差別在維護成本與規則。

## 兩案比較

全面推行時的 graph 數量，依現在各 task 的旗標推算：
- 方案 A 的軸：LoRA、`--remove-bg`、`--control-type`、`--control-backend`、icon_asset 的兩種參考圖、guided_inpaint 的 control／appearance。
- 方案 B：每個 task 一份 base；用到底模的 task 依家族分開（sd15 不支援的 task 沒有 sd15 版），layer_split 與 FLUX.2 不分家族。

| task | 方案 A（sdxl） | 方案 A（sd15） | 方案 B base |
|---|---|---|---|
| concept | 4 | 4 | 2 |
| icon_asset（一律去背） | 8 | 2 | 2 |
| refine | 2 | 2 | 2 |
| inpaint | 1 | 1 | 2 |
| guided_inpaint | 8 | 1 | 2 |
| character_action | 12 | — | 1 |
| pose_only | 24（不含 Union 是 12） | — | 1 |
| style_lock | 4 | — | 1 |
| upscale | 1 | 1 | 2 |
| layer_split（不用模型，不分家族） | 1 | | 1 |
| FLUX.2 concept／edit | 2 | | 2 |
| **合計** | **約 78 份**（不含 Union 約 66） | | **18 份 base**＋10 份 option 定義 |

| 面向 | 方案 A：variant template | 方案 B：擴充 option 操作 |
|---|---|---|
| graph 數量 | 約 78 份，LoRA 節點這類共用片段在數十份 graph 裡重複 | 18 份 base；變化寫在 option 定義裡 |
| hash 維護 | 每份 graph 都有兩個 sha256。改一個共用片段（例如預設負向提示詞）要重新產生所有相關 variant，各自升 major，golden diff 很大。需要一支產生器才維護得動 | base 的 hash 照舊。插入的片段在 option 定義裡，不受 graph hash 保護：要嘛搬進 `template.json`（靠 `template_json_sha256` 記錄），要嘛另外記一個 hash |
| R2「不臨場組 graph」 | **完全符合**。送出的 graph 等於登記的 graph 加上 slot 值，`check_patched` 一行不改 | 部分符合。所有可能的 graph 都由 template 事先宣告、可以列舉，但送出的那張 graph 的結構在 repo 裡不存在，是 runner 執行時組出來的。白名單要從「改了哪些 input」擴大成「加了哪些節點、換了哪些 class」 |
| 證據與平台狀態 | 每個組合有自己的 `status` 與平台證據。例如 Union 後端是實驗性質，它的 variant 可以單獨留在 `draft`，其他升 `technical_pass` | base 的 `technical_pass` 不代表每種 choice 組合都實測過，平台狀態要細到 choice 層級，schema 會變複雜 |
| preflight | 不用改：`requires_custom_nodes`、models、nodes 都是這份 graph 的 | 要依選擇結果決定：選 pose／depth 才需要 `comfyui_controlnet_aux`；controlnet 模型 pin 跟著 choice 換；去背會改 outputs |
| option 之間互相影響 | 不會發生，組合已經展開 | 會發生。Union 的 `type` 值取決於 control_type，原型只能把兩軸攤平成 6 個 choice（`canny`…`union_depth`）。軸再多就會在 JSON 裡重寫一套 builder |
| runner 改動 | 不用改。只有共同缺口（見下方「兩案都要處理」） | `runner/template.py` 的驗證、`resolve`、`patch`、`check_patched`、`declared_targets`；`preflight.py` 的 models 與 nodes；`run.py` 的 outputs；`cli.py` 的 `--option` 語法（從布林改成 `NAME=CHOICE`）；schema、README 與測試。估計要先插入一個 runner PR，才能做 4.2 |
| 第 5 階段切換 | 薄轉接依旗標算出 template id（原型的 `build_drafts.a_id`），再填 slot。golden 和 `graph_sha256` 已證明能做到切換前後相同 | 薄轉接算出 base id 和 choices，再填 slot，graph_sha256 一樣能相同。但要等 runner 擴充合併後才能開始 |
| 第 7、8 階段 | catalog 會有約 78 列，要用家族與 task 分組。第 8.3 階段刪 builder 之後，產生器不能再呼叫 builder，要改成從片段檔組（只在離線產生 template 時用，不進 runner） | catalog 18 列。第 8.3 階段刪 builder 不受影響 |

### 兩案都要處理的共同缺口

這些不影響二選一，但 4.2 開始前要先定：
1. **可替換的底模。** `--style` 會換成同家族的社群底模，golden `concept_lora_style_size` 也換了 checkpoint，所以 checkpoint 必須是 slot。現在 models pin 只核對 graph 裡的預設檔名。換成別的檔名時，preflight 仍然檢查 pin 的那個檔案；`run.result.json` 的 models 列 `filename` 還是 pin，只有同一列的 `graph_value` 是實際送出的檔名。runner 要能分辨：slot 值等於 pin 的檔名時照常檢查大小與 sha256；不同時只用 `/object_info` 確認檔案存在，並在 manifest 標成「未 pin」。LoRA 檔是使用者自己準備的，一律算未 pin。
2. **輸出檔名前綴。** 原型保留 builder 的 `filename_prefix`（例如 `concept`、`transparent`），因為第 5 階段的驗收要求送出的 graph sha256 和切換前相同。如果改用 runner 的 `output_prefix` slot（`gameart/<id>/<run_id>`），sha256 就會不同。
3. **圖片的 `frame_anchoring`。** schema 的 `time_alignment` 只有影片的兩個值，原型暫時寫 `per_source_frame`。圖片 template 應該允許 `null`，或新增一個值。
4. **tier 的預設解析度。** runner 不知道 tier，所以 slot 預設值沒辦法隨 tier 變。原型由呼叫端明確傳入 width／height（sdxl_light 傳 768）；slot 預設值只寫設定檔的原生尺寸。各 task 的規則不同，薄轉接要照 builder 的現況傳值，見下一節的 Q2 摘要；icon_asset 一律用原生尺寸，不能套用 sdxl_light 的 768。

## Q2：profile／tier 怎麼對應到 template

golden 顯示：
- sdxl_high 和 sdxl 產生的 graph 完全相同；
- sdxl_light 只在「用 tier 預設解析度」的 task 不同：concept、character_action、pose_only、style_lock 走 `_default_size()`，sdxl_light 是 768。icon_asset 用設定檔的原生尺寸，不看記憶體檔位，sdxl_light 仍是 1024（golden `sdxl_light.json` 的 `icon_asset`）。inpaint、guided_inpaint、refine、upscale、layer_split 沒有預設寬高；FLUX.2 固定 1024，四個 tier 的 graph 相同；
- sd15 只有底模檔名和寬高不同；
- 兩個設定檔的取樣參數相同。

| 方案 | 做法 | 評估 |
|---|---|---|
| **每個家族（設定檔）一份**（建議） | `image/sdxl/*` 對應 `sdxl_standard`，`image/sd15/*` 對應 `sd15_light`。底模 pin、add-on 模型、`requires_custom_nodes` 都屬於該家族。同一家族內的 tier 差異只有解析度：用 tier 預設解析度的 task，由呼叫端依設定檔明確傳入（和 builder 的 `_default_size()` 相同：沒選設定檔時是 `device_config.json` 的預設寬高，選了 `--profile` 時是設定檔的 `resolution.by_memory`）；icon_asset 傳原生尺寸；其他 task 不傳 | 模型 pin 正確，preflight 檢查的是這台機器真的會用的檔案。sd15 沒有 ControlNet／IPAdapter，所以根本沒有 `image/sd15/pose-only`，「不支援」直接由「沒有 template」表達，不用在執行時另外擋。代價是 sd15 有 11 份（方案 A），共用部分和 sdxl 重複 |
| 一份 template，用 slot 預設值 | 只有 sdxl template；sd15 傳 `checkpoint=dreamshaper_8.safetensors`，再加寬高 | graph 能做到相同（原型 3 組相同），但 template 的模型 pin 仍是 SDXL 底模（測試有斷言這點），preflight 會檢查錯的檔案。sd15 不支援的 task 也要靠額外的 gate。不建議 |
| 每個 tier 一份 | sdxl_high、sdxl、sdxl_light、sd15 各一份 | sdxl_high 和 sdxl 的 graph 完全一樣，只是複製。不建議 |

## 建議

1. **D13 採方案 A（variant template）**，搭配**離線產生器**：
   - runner 維持「只換值、不改結構」，R2 和現有的 hash 白名單不用動；
   - 每個組合可以有自己的狀態與實機證據。
   - 數量多的問題交給產生器處理：產生器只在新增或修改 template 時執行，負責寫出 graph、兩個 sha256 和 template.json；golden 測試確認它的輸出和 builder 相同。它不是 runner 的一部分，執行時不會用到。
   - 方案 B 的好處（檔案少）主要在作者端；它要付出的代價是 runner 的結構白名單和證據粒度，而這些正是第二階段建立的保證。
2. **Q2 採「每個家族（設定檔）一份」**，tier 只影響呼叫端傳入的解析度。
3. 4.2 開工前先補上「兩案都要處理的共同缺口」的第 1 點（runner 支援可替換的底模），可以單獨開一個小 PR。

## 需要使用者決定

1. **D13：方案 A 或方案 B？**（建議 A）
2. **Q2：每個家族一份，或一份 template 加 slot 預設值？**（建議每個家族一份）
3. **要不要減少組合數？** 方案 A 約 78 份，其中三項可以考慮刪減：
   - pose_only 的 Union 後端（實驗性質，12 份）：刪掉，或保留但維持 `draft`；
   - character_action、pose_only、style_lock 的 `--remove-bg`（共 20 份）：保留，或之後改成「先生成、再用獨立的去背 template 處理」。後者送出的 graph 會和現在不同，第 5 階段的 graph_sha256 驗收要另外說明；
   - 上面兩項有 6 份重疊（pose_only 的 Union × 去背），兩項都刪是減少 26 份，剩約 52 份；
   - icon_asset 兩種參考圖的組合（sdxl 8 份）。
4. **產生器：** 要不要把 `build_drafts.py` 的做法收進 repo 當正式工具（例如 `tools_src/` 外的維護腳本）？第 8.3 階段刪 builder 之後，產生器要改成從片段檔組 graph。
5. **輸出檔名前綴：** 圖片 template 保留 builder 的 `filename_prefix`（第 5 階段 graph_sha256 才能相同），或改用 runner 的 `output_prefix`（輸出路徑和影片 template 一致，但切換時 sha256 會不同，驗收要改寫）？
6. **可替換的底模與 LoRA：** 不在 pin 清單裡的 checkpoint／LoRA，preflight 只確認檔案存在、manifest 標成「未 pin」，這樣是否可以接受？

## 範圍與界線

- 這份 ADR 不改 [R1](../rules/candidate-review.md)：template 的輸出一律是 candidate，美術驗收由使用者決定。
- 原型都是 `draft`，模型沒有 sha256 pin，只放在 `templates/_drafts/`。決定之後，4.2 會依結論重做正式 template，原型屆時刪除或改寫。
- 方案 B 的 `option_ops.py` 只是原型；選 B 的話，要在 runner 裡重寫並補完整的 schema 與測試。
