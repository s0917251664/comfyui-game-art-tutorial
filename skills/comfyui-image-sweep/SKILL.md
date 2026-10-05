---
name: comfyui-image-sweep
description: 對 ComfyUI 既有圖片 task 做固定來源與參考、有限且事先指定的參數比較；以 image_edit_tools.py sweep 執行，不是通用重試或平台圖片工具。
---

# ComfyUI 圖片 task 有界比較

本技能只負責使用既有本機 `image_edit_tools.py sweep`，對指定圖片 task 做事先列明的有限參數比較。它不新增生成 task、模型或 workflow，也不改寫共用 brief。需求與驗收依[共用流程](../game-art-workflow/SKILL.md)；task、config、能力 gate 和生成輸入依[ComfyUI 產圖技能](../comfyui-art-gen/SKILL.md)。Plan 欄位及輸出見[plan 格式](reference/plan-format.md)；範例仍保留於[guided inpaint](../local-image-edit-tools/reference/examples/guided-inpaint.json)及[character action](../local-image-edit-tools/reference/examples/character-action.json)。本技能依賴專案執行環境，不是可單獨移植的平台技能。

## 適用範圍

只有使用者明確要固定來源、prompt、seed 和參考圖，並比較有限的已支援參數組合時使用。輸入來源、prompt、seed 和參考保持固定；只改 plan schema 明確允許的參數。允許 task 僅 `refine`、`inpaint`、`guided_inpaint`、`character_action`；笛卡兒積上限 16 個候選。`preserve_outside` 只適用 `inpaint` 和 `guided_inpaint`。

一般單次產圖／編修走既有 ComfyUI 圖片 task；平台圖片生成不使用此工具。不得把 sweep 當盲目重抽、失敗後自動重試或品質最佳化保證。

## 執行前檢查

- 依 ComfyUI 產圖技能取得本機 `python_exe`、`generate_script`、`comfyui_path`、ComfyUI URL、image capability snapshot 和輸出位置；不猜預設路徑或 port。
- 按所選 task 確認 snapshot 的 task availability 與 validation，並滿足 ComfyUI 產圖技能對 `experimental`／`unverified` 的告知與試跑同意 gate。snapshot 缺失、設備指紋過期、task 不可用或模型/node 缺漏時停止。
- 準備符合既有 plan schema 的 JSON，需要時以 `--dry-run` 檢查命令與展開；dry-run 不查 server、模型或生成結果。確認輸出資料夾是新路徑；正式執行與 dry-run 各用不同的新路徑。
- mask、source 與參考圖要符合所選 task 和本機 image_edit_tools 契約。本機圖片編修與 composite 都以 Alpha 0 選編修、255 保留；影片 SAM 的白選黑不選及未知平台遮罩契約不可直接互換。

## 執行與驗收

使用部署後的既有腳本入口（程式碼仍在同一支 `image_edit_tools.py`，未拆成獨立 runtime）：

```text
<python_exe> <ComfyUI>/tools/image_edit_tools.py sweep --plan <plan.json> --config <runtime.json> --output-dir <new-dir> [--profile <id>] [--timeout 240] [--dry-run] [--allow-unverified]
```

正式執行先檢查 ComfyUI queue；running 或 pending 非空即停止，零生成提交，不清除或插隊。validation 非 `verified` 時，依本機工具規則先告知並取得明確試跑同意，再傳 `--allow-unverified`；遇到 task 不可用、生成失敗或逾時即停止，查明當次狀態後再依已有授權與使用者要求處理下一步，不自動重送。

逐張開啟候選與接觸圖，檢查使用者指定的差異、保留項、遮罩外像素和輸出契約。像素統計只是 byte 層比較，不是語意或美術評分。保存 plan、執行記錄和所有候選；候選狀態與使用者接受決定分開記錄。

## 職責界線

此工具依賴 ComfyUI 產線、本機 Python、已部署工具與模型／node；不能移植成只看提示文字即可執行的平台 skill。其他平台若有自己的多候選能力，須按即時 schema 另行使用，不套用此工具的 task、參數、seed 或重試規則。
