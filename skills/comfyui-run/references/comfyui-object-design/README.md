---
name: comfyui-object-design
description: 在選定 ComfyUI 路線時，以既有圖片 task 和本機 Pillow helper 執行物件系列、展示場景、檢視表與母圖樣重複；純規劃走 game-art-workflow，平台圖片執行另有技能。
---

# ComfyUI 物件與平面素材流程

物件系列、展示場景、檢視表與母圖樣重複的共用製作／驗收方法由[共用製作流程](../../../game-art-brief/references/game-art-workflow/references/production.md)維護。本技能負責將已確認的需求接到現有 ComfyUI task 與 helper，不處理平台圖片執行。`scene`／`sheet`／`pattern` 是本機 Pillow 確定性合成，不組 ComfyUI graph，也不需要 ComfyUI server；產生新素材的 task 仍要 ComfyUI。

先讀[工具總表](../../../../docs/knowledge/TOOLS.md)和[流程評估與實測](../../../../docs/knowledge/art/object-design-workflows.md)。這份技能編排本機 ComfyUI 既有圖片 task、單件換色工具與 `comfyui_design.py` 的 Pillow 合成。產生前仍依[產圖技能](../comfyui-art-gen/README.md)做路由、能力檢查與人工驗收。決定見[ADR](../../../../docs/knowledge/decisions/2026-10-08-local-design-and-birefnet.md)。

單一物件需求先分流：新素材走 `comfyui-art-gen` 的 `icon_asset`；既有素材只改顏色並保留細節與外形，走本機 `image_edit_tools.py recolor`；要改紋理或材質則依需求評估既有生成 task，產出仍須人工驗收。換色工具的遮罩契約與實測限制見[單一物件換色](../../../../docs/knowledge/art/single-object-color.md)。

## 工作流

1. 先拆需求：要生成新物件，走既有 `icon_asset`（單一透明遊戲素材）或 `concept`（概念／背景）；有明確來源圖要局部改材質，才走 `guided_inpaint` 或 `inpaint`。檢查所需 task 在本機 `image_capabilities.json` 可用且驗證狀態允許試跑。
2. 單件先檢查、再展開系列的方法依共用製作流程；本機需保留候選與 prompt，並檢查 Alpha 與輪廓。若送入組裝 helper，輸入物件／圖樣必須真的有透明區域。
3. 需要放置時，用 `comfyui_design.py`（repo 入口是 `gameart.py design`，部署副本在 `<comfyui_path>\tools\comfyui_design.py`）做 Pillow 合成：`scene` 把一張透明物件放進一張不透明背景；`sheet` 把 1–16 張透明素材排成檢視表；`pattern` 將同一張透明素材按格重複。這些是確定性合成，不會生成或修補輸入內容，也不組 ComfyUI graph。
4. 合成不連 ComfyUI。同目錄需要 `image_edit_tools.py`（Pillow、NumPy）；不需要 `generate.py` 或 `comfyui_pipeline/`。`--comfy-url`、`--config`、`--timeout` 仍接受但不使用。`--output-dir` 必須是尚未存在的新資料夾。遇錯不自動重試，也不會去碰 ComfyUI。輸出是 `design_<mode>.png` 與 `manifest.json`，沒有 `graph.json`、`request.json` 或 `history.json`。
5. 中文標題、品牌字、長文案和精細版面交給外部文字／向量排版工具；目前 helper 標題僅支援可列印 ASCII，且只有固定頂端／底端位置。Pillow 合成輸出為不透明 RGB，不能當作透明資產交付。
6. 開啟實際輸出檢查物件完整性、位置、縮放、接縫、背景關係及尺寸；manifest 的 `candidate` 和技術成功都不代表美術驗收（[R1](../../../../docs/knowledge/rules/candidate-review.md)）。保存 manifest 及輸出路徑，等待使用者決定接受與否。


## 已知能力界線

- `scene` 只用遮罩 Alpha 將物件置入背景，沒有光線重算、接觸陰影、反射或透視配準；適合平面展示合成原型，不可稱為商品攝影重打光。
- `sheet` 是排版檢視圖，可統一格子與可見範圍留白，不會讓生成的多個物件自動共享風格或相同物件比例。
- `pattern` 重複一個母圖樣，不做 seamless（無縫）接縫生成或檢查。
- 標題與說明只接受可列印 ASCII，不支援中文字型與一般海報排版。沒有 ComfyUI `TextOverlay` 節點。
- 不得臨場組 graph（[R2](../../../../docs/knowledge/rules/fixed-graphs.md)；新的固定 graph 走[擴充協議](../../../../docs/knowledge/maintenance/extension-protocol.md)），也不新增 `generate.py` task、模型或 profile。需要新生成能力時先走[新能力清單](../../../comfyui-extend/references/comfyui-new-tool-checklist/README.md)。


## 固定 CLI 範例

下列是參數模板；執行時由 `local_config.json` 解析 Python、部署工具與服務網址，再換入真實輸入和全新的輸出資料夾。

```text
<python_exe> <comfyui_path>/tools/comfyui_design.py scene --images object.png --background background.png --x 260 --y 190 --width 504 --height 536 --canvas-width 1024 --canvas-height 1024 --title "POTION STUDY" --comfy-url <comfyui_url> --output-dir <new-output-dir>
<python_exe> <comfyui_path>/tools/comfyui_design.py sheet --images object-a.png object-b.png object-c.png --cell 256 --columns 3 --padding 32 --comfy-url <comfyui_url> --output-dir <new-output-dir>
<python_exe> <comfyui_path>/tools/comfyui_design.py pattern --images motif.png --cell 256 --columns 3 --rows 3 --padding 64 --color "#f5f0e5" --comfy-url <comfyui_url> --output-dir <new-output-dir>
```

`scene` 的 width/height 是物件配置框，保留物件長寬比；x/y 是配置框左上角，整個框必須落在畫布內。背景可按指定畫布縮放並置中裁切；canvas-width/height 必須成對提供，範圍 64–4096。`sheet`/`pattern` 的 cell 範圍 64–512，columns 1–8，pattern rows 1–8，padding 不超過 cell 的三分之一。pattern 僅接受一張母圖樣。title/caption 是固定頂端／底端的 ASCII 文字，最長 200 字元；不提供字型選擇。範例裡的 `--comfy-url` 可以留著，程式接受但不使用，也沒有排程或逾時重送。
