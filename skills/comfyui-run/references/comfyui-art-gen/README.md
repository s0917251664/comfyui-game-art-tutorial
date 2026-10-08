---
name: comfyui-art-gen
description: 執行 ComfyUI 遊戲圖片既有 task，負責本機能力檢查、模型與輸入契約、生成及技術驗證；平台生圖另走 platform-image-gen。
---

# ComfyUI 遊戲美術產圖

## 職責與交接

需求、來源／參考用途、版本與內容驗收的共用規則由[遊戲美術工作流程](../../../game-art-brief/references/game-art-workflow/README.md)維護；本技能負責 ComfyUI 的 task 路由、輸入契約、本機能力 gate、執行與技術檢查。已有完整需求時直接沿用，不重做 brief。

12 個圖片 task 中，`layer_split` 是 ComfyUI Core 遮罩裁切，不需生成底模，但仍依現有 task/gate/ComfyUI 執行。平台圖片生成由[平台圖片技能](../../../platform-image-gen/SKILL.md)負責，不讀本機 config、不套用本機參數。缺本機能力時不得自行切到平台；依使用者已選定的引擎交接。

每次先看[工具範圍總表](../../../../docs/knowledge/TOOLS.md)，再按任務只查本技能與 vault 的相關頁面；不要讀入整個知識庫。把自然語言需求轉成 `generate.py` 的固定 task 與必要參數；目標是可重複產圖，不臨場組 graph（[R2](../../../../docs/knowledge/rules/fixed-graphs.md)；新的固定 graph 走[擴充協議](../../../../docs/knowledge/maintenance/extension-protocol.md)）。適用於概念圖、角色／姿勢圖、構圖控制、局部修改、材質變體、圖示與去背。

不適用於整張 UI 版面、Logo／中文字排版、影片或尚未接入的能力。單一 UI 圖示可用 `icon_asset`。影片需求改讀 [comfyui-video-gen](../comfyui-video-gen/README.md)。未有 task 覆蓋的重複生產需求，新的固定 graph 走[擴充協議](../../../../docs/knowledge/maintenance/extension-protocol.md)，其他新能力依 [新能力清單](../../../comfyui-extend/references/comfyui-new-tool-checklist/README.md) 評估；不可把圖片 task 假裝成影片或自行接線替代。

物件展示合成、物件候選檢視表或單圖樣重複，可按需讀[物件與平面素材流程](../comfyui-object-design/README.md)；其中 Pillow 合成只組合既有輸入，不新增生成 task，也不組 ComfyUI graph。中文排版仍交給外部排版工具。

使用者要先整理多參考圖、局部編修、角色／結構保留需求時，可按需讀[遊戲圖片編修需求整理](../../../game-art-brief/references/game-art-edit-brief/README.md)；該技能只整理 brief，task 選擇與能力 gate 仍依本技能。

使用者要做 RGBA 遮罩合成、純換色、差異診斷或透明素材檢查，另讀[本機圖片編修工具](../../../local-media-tools/references/local-image-edit-tools/README.md)；其五個檔案操作不需 ComfyUI。明確要求固定來源／參考的有限參數比較時，讀[ComfyUI 圖片 sweep](../comfyui-image-sweep/README.md)，仍只呼叫既有 task，不代替一般單次產圖流程。

## 每次任務的固定順序

1. 先讀 repo 根目錄 `local_config.json`，取得本機路徑、`python_exe`、`generate_script`、`image_config`、`comfyui_url`、啟動方式與 `output_dir`；若 config 未指定 `image_config`，讀 `<ComfyUI>/tools/image_capabilities.json`。檔案不存在時依 [安裝技能](../../../comfyui-install/SKILL.md) 處理，不得假裝能實機產圖。不可將機器專屬路徑寫進版控文件。
2. 先用下方精簡路由選 task，只補問未提供且確實必要的輸入；不要重問已知答案。分類不明時才讀[完整 task 指南](../../../../docs/knowledge/art-generation.md)相關小節。task 沒有覆蓋時停止並如實說明。
3. **先做能力 gate，再呼叫 CLI。** SDXL／SD1.5 先讀 `image_capabilities.json`，核對可用 task、缺少模型/node 及 validation：`experimental` 或 `unverified` 要先告知，未驗證須取得使用者同意試跑；`verified_other_env` 代表曾在別的環境驗證、目前環境（ComfyUI 版本／模型庫／node）不同，告知差異即可，不阻擋；`validation_basis: legacy` 是舊式手寫驗證（無環境紀錄），視同 verified。驗證升格（`validation approve`）是使用者的決定，agent 不得自行執行。不得自行換 profile 或降級。FLUX.2 不使用 image profile：確認獨立 Core node／模型 preflight 與本機實測證據；仍屬實驗路線，未有本機硬體證據須告知並取得同意。preflight／模型存在不等於品質或硬體已驗證。影片查 `video_capabilities.json` 並改走影片技能。
4. ComfyUI server 必須在設定的 URL 運行；必要時依 `start_script` 啟動。部署副本不會自動找到 repo config；每次呼叫明確帶 `--comfy-url <comfyui_url>`（或明確 `--config <local_config.json>`）。不可猜預設 port。每次圖片生成帶 `--output-dir <output_dir>`，除非使用者指定其他位置；回報程式印出的成品路徑。
5. 只用所選 task 已開放的參數。普通需求只看[art-generation.md](../../../../docs/knowledge/art-generation.md)該 task 範例；使用者指定特殊參數時才查[art-parameters.md](../../../../docs/knowledge/art-parameters.md)相關列。逾時不會停止 ComfyUI 背景工作；先查狀態再考慮重送。
6. 產出後開啟圖片人工驗收：先核對檔案、尺寸與透明契約，再逐項看使用者明確要求的主體、顏色、姿勢、構圖、數量及排除內容，最後依 task 控制目的檢查。不可只看 CLI 成功。失敗時只可按已知參數語意做**一次有理由的修正**並重驗；沒有明確可調原因就停止，不換 seed 盲目重抽、不新增 graph 或隱性 fallback。限制見 [已知限制](../../../../docs/knowledge/art/known-limitations.md)。

## 能力與設備規則

- SDXL／SD1.5 task 依 `image_capabilities.json` 的 `default_profile`、task availability、validation 與 features 決策。快照缺失時退回讀 `device_config.json` tier 並建議補跑偵測；快照設備指紋過期、task 不可用或 preflight 缺模型/node 時停止。
- FLUX.2 `flux2_concept`／`flux2_edit` 是獨立路線，不套用 `--profile`、SDXL tier 或風格旗標；node／模型存在只證明 preflight 通過，不代表能在這台設備成功生成。
- 換機或換 GPU，重跑 `detect_device.py` 與 `detect_image_capabilities.py`；改模型、ComfyUI/custom node 時重新掃描相關能力。不能把其他平台 validation 當成本機驗證。
- `mask_session.py`、`sam_segment.py` 是獨立遮罩工具，不在 image capability snapshot 中。遮罩送入 `inpaint`、`guided_inpaint` 或 `layer_split` 前，必須檢查預覽與 Alpha 契約；SAM 候選需人工查看並確認範圍。操作細節依 task 指南的遮罩參考連結。
- `image_edit_tools.py` 是本機合成／比較／有限 sweep 工具，不在 image capability snapshot 中新增 task。sweep 使用既有 task 時仍要依該 task 的 snapshot validation gate；細節依[本機圖片編修工具](../../../local-media-tools/references/local-image-edit-tools/README.md)。

## 快速 task 路由

| 需求 | task | 必要輸入／判斷 |
|---|---|---|
| 新概念、場景、道具，沒有參考圖 | `concept` | 內容；只在未提供時問尺寸比例 |
| 明確要求試 FLUX.2 純文字生圖 | `flux2_concept`（實驗性） | 內容；純文字；未驗證先告知並取得試跑同意 |
| 明確要求用 FLUX.2 語意修改整張圖 | `flux2_edit`（實驗性） | 一張來源圖 + 整圖修改描述；不是局部修補 |
| 單一遊戲圖示／symbol／道具素材 | `icon_asset` | 內容；透明背景與正方形畫布是預設 |
| 照姿勢圖或線稿畫新角色／不要求身份 | `pose_only` | 姿勢／線稿參考圖 + 內容描述 |
| 角色套新場景，姿勢可變 | `style_lock` | 角色參考圖 + 場景描述 |
| 指定角色照另一張姿勢圖動作 | `character_action` | 角色參考圖 + 姿勢／線稿參考圖 + 動作描述 |
| 保留大致構圖，精緻化或換材質／顏色 | `refine` | 來源圖 + 修改描述 |
| 只修來源圖一塊區域 | `inpaint` | 來源圖 + 已人工確認的遮罩 + 修改描述 |
| 局部換外觀且要鎖住輪廓／姿勢 | `guided_inpaint` | 來源圖 + 已確認遮罩 + 外觀描述或參考圖；只在需求要求結構鎖定時用 |
| 放大已定稿圖 | `upscale` | 成品圖；盡量沿用原 prompt |
| 從定稿合成圖切出單一透明圖層 | `layer_split` | 完成圖 + 已確認遮罩 + layer name |

不要把「換角色動作」誤判為靜態角色一致性；要影片就轉影片技能。需要 mask editor 或 SAM 時，那些工具只產生／整理遮罩，不是生成 task。一般情境的參數及分支只讀[art-generation.md](../../../../docs/knowledge/art-generation.md)相關小節。

## 決策、模型與經驗

只在 task 選擇、模型能力或驗收問題相關時，讀 [生效中決策](../../../../docs/knowledge/DECISIONS.md) 或依模型/task 查 [經驗索引](../../../../docs/knowledge/INDEX.md)；不要把歷史觀察當成預設生成規則。SDXL/SD1.5 validation 依本機能力快照；FLUX.2 依獨立 preflight 與適用平台證據。經驗只有累積可重現證據並人工核准後才能提升為正式規則。

## 按需參考

- [task 選擇、必要輸入與 CLI 範例](../../../../docs/knowledge/art-generation.md)：快速路由無法判斷，或需要特定 task 的遮罩／複合圖層分支時，只讀該小節。
- [參數與呼叫規格](../../../../docs/knowledge/art-parameters.md)：只有使用者提出特殊參數要求時查相關列；包含預設、邊界、profile 選擇與刻意不開放項目。
- [控制來源判斷](../../../../docs/knowledge/art/control-type-selection.md)：姿勢參考圖、線稿與 canny／pose／depth 選擇。
- [遮罩格式與驗收](../../../../docs/knowledge/art/masking.md)、[SAM 候選限制](../../../../docs/knowledge/art/sam-segmentation.md)：局部重繪或拆層前使用。
- [結構範本](../../../../docs/knowledge/art/structure-ref.md)：精確數量、幾何或文字字形需要固定結構時使用。
- [已知限制](../../../../docs/knowledge/art/known-limitations.md)：回答可行性或遇到相關失敗時查閱。
- [SDXL profile 經驗](../../../../docs/knowledge/art/profiles/sdxl-standard.md)、[SD1.5 profile](../../../../docs/knowledge/art/profiles/sd15-light.md)：只讀所選 profile 的平台驗證與觀察。
- 資產驗收與決策見 [知識索引](../../../../docs/knowledge/INDEX.md)；manifest 與 Markdown 素材紀錄方式見 [結果紀錄參考](../../../../docs/knowledge/result-records.md)。只有使用者要求沿用已接受版本時，才按該頁「使用者要求沿用已接受版本」操作。歷史觀察只供預期管理與判斷，不會自動更改模型 profile、CLI 預設或生成規則。

修改產線或接手新機器時，離線檢查與實機 smoke test 的命令見 [art-generation.md](../../../../docs/knowledge/art-generation.md)；離線測試不代表實機產圖通過。
