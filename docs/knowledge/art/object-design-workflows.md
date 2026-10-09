# 物件與平面素材工作流評估

**日期：** 2026-10-03（組裝實測）；組裝程式於 2026-10-08 改為 Pillow。  
**適用範圍：** 素材生成仍是本機 Windows / CUDA / RTX 4080 的既有 SDXL 圖片 task。`scene`／`sheet`／`pattern` 現在不經過 ComfyUI。  
**狀態：** 現行組裝是本機 Pillow。下面的 Core graph 路徑是 2026-10-03 的實測紀錄，不是現行程式的產物。各項輸出均待美術審核者驗收。這不是 `generate.py` 新 task 或模型驗證。

## 結論

素材仍用既有生成 task（`icon_asset`、`concept`、`guided_inpaint`）。組裝不再走 ComfyUI。現行 `tools_src/comfyui_design.py` 的 `scene`、`sheet`、`pattern` 是純 Pillow：不組 graph、不預檢 Core 節點、不 upload、不 queue，輸出不透明 RGB 與 `manifest.json`（`kind` 為 `pillow_design`）。它不呼叫 diffusion 模型，不會重新生成物件，亦不會覆寫來源檔案。`--comfy-url`、`--config`、`--timeout` 仍接受但不使用。同目錄需要 `image_edit_tools.py`，不需要 `generate.py` 或 `comfyui_pipeline/`。決定見 [ADR](../decisions/2026-10-08-local-design-and-birefnet.md)。

實測顯示單一玻璃藥水瓶候選可作為物件素材起點，三張候選可組成 proof sheet，單一圖樣可重複排格，透明物件亦可放入概念背景。不過瓷器／古銅材質編修案例沒有證明材質可控；場景合成也不會補上接觸陰影或替物件重打光。中文字排版、完整海報系統及 3D 渲染流程仍未建立。

## 六個方向的可行性

| 方向 | ComfyUI 內可做的部分 | 本次證據與限制 | 判斷 |
|---|---|---|---|
| 道具／物件系列 | 用 `icon_asset` 個別產透明物件，再用 `sheet` 排成檢視表；需要已有輪廓時可試 `--structure-ref`。 | 一張玻璃瓶候選可用於組裝，但不符合提示中的琥珀色與短瓶比例。扁平模板大致保留瓶型，陶瓷候選仍扁平、古銅候選偏金色。`sheet` 可正規化可見範圍和留白，候選風格差異仍清楚可見。 | **部分可行**：產單件與排檢視圖可用；材質命中與系列一致性仍屬實驗。 |
| 商品／物件主視覺 | `concept` 產背景，再以 `scene` 將一個透明物件放進不透明背景，可指定畫布和物件框。 | 已實測 square 1024×1024、portrait 1024×1280、banner 1536×768 三種圖形合成。合成只貼入物件，不重算光線／透視，沒有接觸陰影或反射。 | **平面展示可行，擬真商品攝影未證明**。 |
| 海報／社群圖 | `concept` 產底圖，`scene` 定位主物件；可加固定位置的簡短 ASCII 標題。 | helper 不支援中文字；只有頂端／底端可列印 ASCII，沒有可編輯多欄版面、文字框、字體或多尺寸自動重排。2026-10-03 的紀錄用過 Core `TextOverlay`；現行是 Pillow 繪字，限制相同。 | **主視覺底圖可行，完整平面排版不可用**；中文文案需外部排版。 |
| 圖樣／裝飾系統 | 先準備單一透明母圖樣，再由 `pattern` 排成規則格子。 | 3×3 重複輸出 768×768 並產 manifest；只有規律重複，沒有 seamless tile 生成或接縫分析。 | **貼紙／素材排列可行，無縫紋理未證明**。 |
| UI 圖示／元件系列 | `icon_asset` 產單件，`sheet` 對照多件；本機 `asset-audit` 查看 Alpha／大小／碰邊。 | 可排不同輸入，但可統一格子與可見範圍留白，但不保證共享光源、風格或物件本身比例，也不輸出透明排版；每個圖示仍須逐件驗收。 | **候選整理流程可行，系列規格鎖定仍需人工**。 |
| 簡單 3D 物件輔助 | 可進一步評估目前 ComfyUI 安裝中可見的 3D Core 節點。 | `/object_info` 可見 `Load3D`、`Preview3D`、`RenderMesh` 等節點，但本次沒有完成可用的模型建置／渲染實驗；本機未找到 Blender CLI，Python 環境也未找到 `bpy`。不能據此判定 ComfyUI 3D 整體不可行，也不能列為本產線已可用流程。 | **待獨立 PoC**，不納入本次已實測入口。 |

## 物件生成與材質嘗試

所有輸出都在 `output/design_workflows_20261003/`。原始生成追溯見各子資料夾 `generation.json`、`history.json`。當時的 ComfyUI Core graph 合成追溯見 `core-*/manifest.json`、`request.json`、`graph.json` 與 `history.json`；現行 Pillow 不再寫這些 graph 檔，只寫 `design_<mode>.png` 與 `manifest.json`。

- 單一青綠玻璃藥水瓶：`object/transparent_00159_.png`，`icon_asset` seed `202610031`，768×768 RGBA。形成一個可用於後續平面組裝的玻璃瓶候選；**candidate，不代表已接受**。
- 象牙陶瓷材質：`ceramic/transparent_00160_.png`，用相同 `bottle-template.png` 結構參考，seed `202610033`。瓶型大致保留，但瓶身仍是扁平米色填色，記為**材質失敗、輪廓參考部分有效**。
- 古銅材質：`bronze/transparent_00161_.png`，用 `bottle-template.png` 作 `--structure-ref`，seed `202610033`。瓶型大致保留，但呈現黃金色而非要求的古銅色，記為**材質失敗、輪廓參考部分有效**；不足以證明系列材質控制可靠。
- 局部材質：`material-guided/guided_inpaint_00017_.png`，`guided_inpaint`、Canny strength 0.6、denoise 0.85、seed `202610033`。瓶身呈現米色陶瓷外觀，但仍有玻璃般的反光與底部特徵；未證明遮罩外完全不變或材質命中穩定，維持**experimental candidate**。

這些結果不授權更改既有 task 的 profile、預設參數或驗證狀態。

## 2026-10-03 的 Core graph 組裝紀錄

以下表格與路徑是改 Pillow 之前、用 ComfyUI Core graph 跑出的紀錄。幾何（alpha 外框、置中、中心裁切）現行 Pillow 沿用；那些資料夾裡的 `graph.json` 不是現行程式的產物。

背景候選 `background/concept_00071_.png` 在要求空場景時仍生出瓶子；移除商品攝影語意並強調空的建築靜物後，一次有理由的 prompt 修正產生 `background-corrected/concept_00072_.png`。它可作為版面底圖候選，但不是版面排版成品。

| 當時的 Core graph | 實際結果 | 證明的範圍 |
|---|---|---|
| `scene` | `core-scene/design_scene_00001_.png`，1024×1024 | 單一透明物件置入背景；遮罩 alpha、位置與尺寸組裝成功。非光照匹配或商品攝影。 |
| `scene` 對齊畫布 | `core-portrait-aligned`、`core-banner-aligned` | 來源背景經縮放後可輸出指定畫布；這是幾何裁切／縮放與貼入測試，不等於多尺寸自動排版。 |
| `sheet` | `core-sheet/design_sheet_00001_.png`，768×256 | 三個已存在候選並排檢視，輸入本身沒有被模型改動。 |
| `pattern` | `core-pattern/design_pattern_00001_.png`，768×768 | 單一透明圖樣重複 3×3；不含 seamless 接縫處理。 |

當時三種 helper graph 的 manifest 都標記 `model_generation: false`、`acceptance: pending human review`。輸出是 RGB，不是透明素材；要交付透明資產仍使用原本 RGBA 輸入或既有去背流程。Core Alpha proof 以 50% 紅色覆在藍底測得 `[128, 0, 126]`（容差 1），遮罩外像素完全不變。原始與部署端 `sheet`、`pattern` 解碼像素相同；三種部署 CLI 模式均實際執行。這些數字屬於 Core graph 版本，現行 Pillow 沒有重跑這一批實機。

## 可重現證據與執行界線

- 實際執行證據：`review.json`（本機證據：`output/design_workflows_20261003/review.json`） 摘要記錄 2026-10-03、Windows CUDA RTX 4080、6 次 fresh generation、26 項測試及部署 19 項通過；各 task 均有 sampler/decode 證據，完整參數與來源 hash 見對應 `generation.json`、`execution-proof.json`（本機證據：`output/design_workflows_20261003/execution-proof.json`）。
- 當時的 Core 合成輸出和 graph：`core-scene`（本機證據：`output/design_workflows_20261003/core-scene/manifest.json`）、`core-sheet`（本機證據：`output/design_workflows_20261003/core-sheet/manifest.json`）、`core-pattern`（本機證據：`output/design_workflows_20261003/core-pattern/manifest.json`）。
- 實機部署輸出：`deployed-scene`（本機證據：`output/design_workflows_20261003/deployed-scene/manifest.json`）、`deployed-sheet`（本機證據：`output/design_workflows_20261003/deployed-sheet/manifest.json`）、`deployed-pattern`（本機證據：`output/design_workflows_20261003/deployed-pattern/manifest.json`）。實際尺寸為 square 1024×1024、portrait 1024×1280、banner 1536×768；scene 仍無接觸陰影。
- Alpha 技術統計：`object-audit`（本機證據：`output/design_workflows_20261003/object-audit/audit.json`）；只作透明通道統計，不能判定去背邊緣的美術品質。
- Core node schema 與當前安裝資源：`node-evidence.json`（本機證據：`output/design_workflows_20261003/node-evidence.json`）。`Load3D`／`RenderMesh` 節點雖存在，`Load3D` 檔案選單目前只有 `none`；沒有固定 3D 生成／渲染 task，檢查目錄也未找到 Blender／`bpy`、Hunyuan3D 或 Trellis 模型。本次僅做 preflight，沒有 mesh 渲染實驗；這不代表 ComfyUI 3D 整體不可行。
- 現行 helper 部署後與 `image_edit_tools.py` 同目錄即可（Pillow／NumPy）；不依賴 `generate.py`、`comfyui_pipeline/` 或 ComfyUI server。不檢查 Core 節點，也不上傳、不排程。ComfyUI 路徑與 Python 從當機 `local_config.json` 解析，不寫死其他機器路徑。新輸出資料夾避免覆蓋舊結果。2026-10-03 的 Alpha 單元測試與已部署 CLI 實測通過數仍以 `review.json` 為準，那是 Core graph 版本的技術通過數，並非圖片美術通過數。
- ComfyUI 內建節點存在只證明當前 `/object_info` 列出節點，不等於該 3D 功能已跑通。新的節點、生成 task、模型/profile 或 custom node 都要另按新增能力清單評估。
