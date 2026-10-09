---
type: maintenance
status: current
---
# 重構交接：第 3–8 階段

2026-10-08 的實作中斷點在[重構進度 2026-10-08](restructure-progress-2026-10-08.md)。給人讀的交付說明在[重構交付脈絡 2026-10-08](restructure-delivery-2026-10-08.md)。下一個 agent 先讀進度頁。這一頁保留規則、流程和原始計畫。進度頁和這一頁衝突時，規則以這一頁為準，做到哪裡以進度頁為準。兩者都讓路給已經生效的[決策](../DECISIONS.md)。

從 2026-10-08 起，第 3–8 階段由 **Windows 本機 agent**（CUDA 機器，已經知道 repo 和 ComfyUI 安裝的位置）自己實作，並做到端到端驗證。分工如下：
- 審核端：只依這份計畫審 PR。
- 使用者：在審核後合併。

## 1. 現況（develop `2dbdeeb`）

| PR | 合併（台北） | 內容 |
|---|---|---|
| #1 | 10-07 21:12 | 第 1 階段文件整理：刪 stub、抽出 R1／R2／R3、文件改用中性稱呼、SAM3 為預設、實驗紀錄併入經驗區、上游技能移到 `third_party/` |
| #2 | 10-07 23:22 | 1.5-A：`.gitattributes` 對有 hash 紀錄的檔案設 `-text`；`output/` 連結改純文字；新增 `test_doc_links` |
| #3 | 10-07 23:44 | 1.5-B：相對 `--config` 以 repo 根目錄解析；smoke 用語修正 |
| #4 | 10-08 01:46 | 2.1：頂層 `templates/`（8 份）、`template.json` 與 schema、`run list|show|--dry-run`、golden 20 案例 |
| #5 | 10-08 10:24 | 2.2：`--preflight`、平台 gate、模型大小與 `--verify-hashes`、DWPose pin |
| #6 | 10-08 11:16 | 2.3：實際執行（上傳、queue、輪詢、下載、post 步驟）、`run.result.json`；`review` 接受 `template_run_result` |
| #7 | 10-08 12:46 | 2.4：技能改用 `gameart.py run`；R2 第 1 點改寫；刪舊 `template-manifest.json` |
| #8 | 10-08 13:20 | 2.5：custom node 改用 `GameArt*` 名稱，舊名稱保留為隱藏別名（見[改名與別名](../maintenance/custom-node-renames.md)） |

第 2 階段交付的東西：
- 8 份固定 API graph（Wan Animate 6、SAM3 2），都是 `technical_pass`（windows-cuda）。
- `gameart.py run`：list／show／dry-run／preflight／實際執行。用法見 [templates/README](../../../templates/README.md)。
- 決策 D1–D14 見[第二階段 ADR](../decisions/2026-10-07-phase2-template-runner.md)。
- 官方工具的取捨見 [ADR 2026-10-08](../decisions/2026-10-08-official-comfy-tooling.md)：不裝 comfy-cli／comfy-mcp，只對齊官方範本欄位與 core blueprints。

基準數字（新 PR 拿來比對）：
- 完整測試：Ran 505、OK、skipped 0。
- `verify-install`：91/91。
- 使用者的 ComfyUI：v0.34.0。

## 2. 必守規則

1. **R2／D8：固定 graph 一律走 runner。** 新的固定 graph 先做成 template，再用 `gameart.py run` 執行（[R2](../rules/fixed-graphs.md)）。手動打 HTTP 只能用來除錯 runner，結果不能當證據。
2. **技術通過不等於美術接受。** `content_review` 永遠是 `pending`，由使用者用 `review accept|reject` 決定（[R1](../rules/candidate-review.md)）。agent 不 accept、不 reject，也不 approve validation。
3. **不寫特定人名。** 審核者寫「美術審核者」，使用者的決定寫「使用者確認」。[`test_neutral_wording`](../../../tests/test_neutral_wording.py) 會擋。舊 class 名稱的拼法只留在[改名紀錄](../maintenance/custom-node-renames.md)。PR 8.2 已刪掉 `contracts.py` 的 `LEGACY_*` 常數，其他檔案不要再寫那些拼法。
4. **位元組與 hash：**
   - 有 hash 紀錄的檔案（`templates/**`、validation、smoke suites 等）在 [`.gitattributes`](../../../.gitattributes) 設 `-text`。新增這類檔案時，要同一個 PR 補上規則，並用 `git check-attr text <檔案>` 確認。
   - `graph.api.json` 的位元組 sha256 和 canonical sha256 都要和 `template.json` 一致。
   - 不准用編輯器重存 graph。改 graph 就是升 major（見下一點）。
5. **template 版本與狀態**（[templates/README](../../../templates/README.md)「規則」「修改」）：
   - 版本用 semver：只改說明升 patch；slot 驗證或預設值改變升 minor；graph 或 slot 目標改變升 major。
   - 改 graph 或 `template.json` 一定要升版本、更新兩個 sha256，並重跑 `python tests/golden_template_graphs.py --write`，檢查 golden diff。
   - `status` 只有 `draft`／`technical_pass`／`retired`，只描述技術狀態。
   - 任何模型沒有 sha256 pin，就不能是 `technical_pass`。
   - 平台狀態只能透過 PR、附實機證據修改，runner 不會自動升級。`untested` 的平台預設拒跑。
6. **重構完成前不加新功能。** 新能力、新模型、新 graph 都先記成待辦。真的要加，必須使用者明確同意，而且一律用 `templates/` 格式提交，不再新增 Python graph builder。
7. **不動使用者的 ComfyUI 和模型：**
   - 安裝或更新 ComfyUI、custom node、Python 套件，或下載、搬移、刪除模型，都要先說明容量與影響，取得使用者同意。
   - 下載用固定 revision，逐檔驗 sha256。
   - 不硬砍 ComfyUI：不用 `Stop-Process`／`taskkill`，不呼叫 `/interrupt`，不清 queue。
8. **runner 只用標準庫。** 讀媒體的部分（PyAV、Pillow）在 ComfyUI 的 Python 裡跑，缺套件時要有清楚的錯誤訊息。不引入 comfy-cli、comfy-mcp 或其他第三方依賴。

## 3. 每個 PR 的流程

1. `git fetch`，從**最新的 `origin/develop`** 切分支，命名 `feat|fix|refactor|docs|test/phase<N.M>-<簡述>`。一個 PR 只做下面計畫的一項。如果發現範圍太大，就再拆，並在 PR 裡說明。
2. **改之前**跑完整測試，記下 Ran／OK／skipped：
   ```text
   $env:PYTHONPATH = 'tools_src;tests;.'
   <python_exe> -m unittest discover -s tests
   ```
3. 實作。測試和文件放在同一個 PR。
4. **改之後**再跑一次完整測試；文件 PR 至少另外跑 `python tests/test_doc_links.py` 和 `python tests/test_neutral_wording.py`。
5. **Windows 實機驗證：**
   - 證據放在 `output/verify-<YYYYMMDD>-<PR 編號>/`（ignored，不進版控）。
   - 文件裡只能寫成純文字標註，例如「（本機證據：`output/verify-...`）」，不能寫成連結（[文件連結規則](../maintenance/doc-links.md)）。
   - 要部署 custom node 或工具時：先 `deploy` dry run，確認後 `deploy --yes`，再**另外**跑 `verify-install` 取得通過數。
6. commit 身分自己選，但同一個 PR 裡要一致。push 分支，開 PR 到 `develop`，描述用繁體中文（格式見第 7 節）。
7. **不要自己 merge。** 等審核端回覆；要修改就在同一個分支加 commit。已經 push 的 commit，不經使用者同意不 force-push、不 rebase。

## 4. 第 3–8 階段計畫

- 順序：3 → 4 → 5 → 6 → 7 → 8。6′（工具整併）可以和 3–6 平行，但不能和進行中的 PR 改到同一批檔案。
- 每一階段的最後一個 PR 合併後，在 PR 回報裡附上該階段的總結。

### 第 3 階段：VACE 模板化（第一個帶前後處理的 template）

| PR | 範圍 | 驗收 | 實機驗證 |
|---|---|---|---|
| **3.1** `fix/phase3.1-device-config-warning` | ① `face_swap.py`、`video_layers.py` 從 repo 執行時，會因為 import 連帶載入 `image_graphs`，印出誤導的「找不到 device_config」提醒（runner 已經避開，見 `runner/media.py` 的註解）。改成不載入、或只在真的需要時才載入。② `gameart.py` TOOLS 表裡 `run` 的說明還寫「實際送出在 2.3」，改成現況 | 新測試：兩支工具的 `--help`、`preflight` 在沒有 `tools_src/device_config.json` 時不印這個提醒；完整測試全過 | 兩支工具各跑一次 preflight，輸出用 `Select-String -Pattern '找不到.*device_config'` 搜尋，結果為 0；圖片 task 在真的缺快照時仍會提醒 |
| **3.2** `feat/phase3.2-template-official-fields` | `template.json` 對齊官方欄位（[ADR 2026-10-08](../decisions/2026-10-08-official-comfy-tooling.md)）：`min_comfyui_version`、`requires_custom_nodes`（`[{id, source: registry｜repo}]`）、`models[].directory` 與 `models[].url`（用固定 revision 的下載網址）、`provenance.upstream`（`{kind: workflow_templates｜core_blueprint｜none, name, blob, comfyui_version}`）。validator 要檢查：`directory` 和 `path` 一致；`url` 和 `source` 一致。preflight 讀 `/system_stats` 的 ComfyUI 版本，低於 `min_comfyui_version` 就擋下，讀不到只提醒。8 份 template 補欄位，各升 patch | 8 份 graph 的 hash 不變；golden 不變；新增欄位的正反測試；schema 文件更新 | 8 份 preflight 都通過；用假的高版本需求（測試或 `--dry-run`）確認會擋下。官方範本 blob 用 `git hash-object` 對 workflow_templates 的檔案計算；找不到對應範本就寫 `kind: none` 並說明 |
| **3.3** `refactor/phase3.3-runner-generated-inputs` | runner 支援「pre 步驟產生的檔案」當上傳輸入，以及新的 post 步驟。把 `video_edit_media.py` 的工作區處理（grow／crop／size／FFV1 work clips）、`paste_back`、遮罩外逐 byte 不變的 QA，包成 `STEPS` 清單內的固定步驟（例如 `vace_work_area`、`paste_back`、`qa_outside_mask_unchanged`）。原模組保留為薄轉接，行為不變 | `test_video_inpaint.py` 一字不改全過；新步驟用假 media 做單元測試；清單外的步驟仍然拒絕 | 不需要 GPU：用 2026-10-07 素材跑新步驟，和舊路徑的中間檔逐 byte 比對 |
| **3.4** `feat/phase3.4-wan-vace-template` | 新增 `templates/video/wan-vace/inpaint/`：graph 由 `build_video_inpaint_wan` 產出，對照官方 `video_wan_vace_inpainting` 範本與 core blueprint「Video Inpainting (Wan2.1 VACE)」，在 `provenance.upstream` 記錄 blob。pre／post 用 3.3 的步驟，模型 pin 補齊 sha256。新增時先標 `draft` | 等價測試：多組參數下，runner patch 後的 graph 和 builder 逐欄位相同；golden 加入這份；占位與差異白名單通過 | 用 2026-10-07 素材執行 `gameart.py run video/wan-vace/inpaint`：遮罩外變動像素 0，輸出規格與舊 `generate.py video_inpaint` 一致。證據齊全後，同一個 PR 把 windows-cuda 改成 `technical_pass`，macos-mps 維持 `untested` |
| **3.5** `refactor/phase3.5-video-inpaint-adapter` | `generate.py video_inpaint` 的名稱和旗標不變，內部改成呼叫 runner（`video/wan-vace/inpaint`）。同步更新 `video/cli.md`、`vfx-tools.md`、相關技能。`VideoPlan.finalize` 先保留，第 8 階段才刪 | 舊 CLI 測試全過；同樣的 seed 產生同一份送出 graph（sha256 相同）；result 欄位相容 | 舊 CLI 指令實跑一次，和 3.4 的輸出比對技術規格；遮罩外變動 0 |

### 第 4 階段：圖片 template 抽出（還不切換）

| PR | 範圍 | 驗收 | 實機驗證 |
|---|---|---|---|
| **4.1** `docs/phase4.1-image-variant-design` | 決定 ADR D13：LoRA、去背、ControlNet 這類插入節點的變化，用「variant template」還是「擴充 option 操作」。也要決定 profile／tier（sd15／sdxl／sdxl_high）怎麼對應到 template（每個 profile 一份，或用 slot 預設值）。用 2 個 task 做原型，用 golden 等價測試當判準。寫成 ADR 草稿，**需要使用者決定** | 原型在 99 組 golden 的子集上逐欄位等價；ADR 列出兩案的比較 | 不需要 |
| **4.2** `feat/phase4.2-sdxl-templates` | 依 4.1 的決定，把 SDXL 系列 task（concept、icon_asset、refine、inpaint、guided_inpaint、character_action、pose_only、style_lock、upscale、layer_split）抽成 `templates/image/**`，加上 patch。狀態一律 `draft`，生成路徑還不使用它們 | 99 組 golden 中屬於這批的案例，runner 產生的 graph 和 builder 逐欄位相同；hash 規則通過 | Windows：每個 template 跑 preflight 與 dry run，不生成 |
| **4.3** `feat/phase4.3-sd15-flux2-templates` | SD1.5、FLUX.2（concept、edit）。官方有對應範本時，在 `provenance.upstream` 記錄 | 同 4.2 | 同 4.2 |

### 第 5 階段：圖片切換

| PR | 範圍 | 驗收 | 實機驗證 |
|---|---|---|---|
| **5.1** `refactor/phase5.1-image-tasks-runner-a` | concept、icon_asset、refine、character_action、pose_only、style_lock 改成 runner 的薄轉接，CLI 名稱和旗標不變 | golden 不變；`image_generation_result` 欄位與 `graph_sha256` 和切換前相同 | `smoke run` 結果和基準相同（不加 `--record`）；同 seed 新舊 graph sha256 相同 |
| **5.2** `refactor/phase5.2-image-tasks-runner-b` | inpaint、guided_inpaint、upscale、layer_split、flux2_*；文件與技能同步 | 同 5.1 | 同 5.1。Mac 有空時跑 smoke 補證據，沒跑就維持 `untested` |

### 第 6 階段：影片 template 與 recipe

| PR | 範圍 | 驗收 | 實機驗證 |
|---|---|---|---|
| **6.1** `test/phase6.1-video-golden` | 先替 5 個 Python 影片 graph（`build_img2video_wan`、`build_pose_drive_wan`、`build_img2video_h3`、`build_character_video_h3`、`build_pose_drive_h3`）補 golden，不改程式 | golden 測試涵蓋 7 個影片 task 的主要參數組合 | 不需要 |
| **6.2** `feat/phase6.2-video-templates` | 5 個 graph 轉成 template。抽尾幀、運鏡終點圖改成 pre 步驟。模型目前由偵測器設定檔決定，要改成 template pin：機器之間檔名不同時，在 PR 提出方案（依平台的 pin 或 variant），不要自己定案。官方有對應範本或 blueprint（例如 Wan 2.2 Image to Video）時，記錄 upstream | 和 6.1 golden 逐欄位等價 | preflight 與 dry run |
| **6.3** `refactor/phase6.3-video-tasks-runner` | 7 個影片 task 改成薄轉接 | golden 不變；result 欄位相容 | H3、Wan 各實跑一次 smoke，技術規格與基準一致 |
| **6.4** `feat/phase6.4-recipes-format` | `templates/recipes/` 與 `recipe.schema.json`：多個步驟，中間有人工確認點；在確認點停下來，可以續跑；每一步都留證據。`_drafts/` 下的東西不能被一般流程引用。第一條 recipe 是 `object-mark-inpaint`（SAM3 track-mask → 遮罩預覽 →〔使用者確認〕→ wan-vace inpaint），標 draft | schema 與續跑的測試；確認點沒有確認就不往下走 | 用 2026-10-07 素材跑一次，確認點停下來，由使用者確認後續跑 |
| **6.5** `feat/phase6.5-recipes-rest` | `prop-swap`、`idle-anchored-action`（依 `frame_anchoring` 選 template；[R3](../rules/idle-anchoring.md)）、`fx-alpha-export`，都放 `_drafts/`。轉正要另開 PR，並且要使用者核准 | 每條 recipe 的 dry run 測試 | 每條 recipe 用 2026-10-07 素材做一次 dry run |

### 第 6′ 階段：工具整併（可以和 3–6 平行）

| PR | 範圍 | 驗收 | 實機驗證 |
|---|---|---|---|
| **6′.1** `refactor/phase6p.1-dedupe` | 重複實作各留一份：色相旋轉（`vfx_alpha_tools.masked_hue_rotate` 和 `image_edit_tools.recolor`）、`read_masks`（vfx 和 `runner/vace_media`，PR 3.3 前在 `video_edit_media`）、遮罩貼回、影片讀寫 | `test_vfx_alpha_tools`、`test_image_edit_tools`、`test_video_inpaint` 全過；`prop-paste` 輸出和研究 master 逐 byte 相同 | 實跑一次 `vfx prop-paste`，和舊輸出比對 hash |
| **6′.2** `refactor/phase6p.2-split-vfx` | `vfx_alpha_tools.py`（1,020 行）拆成 pixel／mask／media／qa 模組，`gameart.py vfx` 的介面不變；`deploy_manifest` 同步 | 同上；部署 dry run 清單正確 | `deploy --yes` 後另外跑 `verify-install`，回報通過數 |
| **6′.3** | `comfyui_design.py` 已改純 Pillow；`vfx birefnet-alpha` 維持 repo 內 `benchmark_birefnet`，不進部署 | 見 [ADR](../decisions/2026-10-08-local-design-and-birefnet.md) | 不部署 |

### 第 7 階段：catalog、技能收斂、擴充協議

| PR | 範圍 | 驗收 | 實機驗證 |
|---|---|---|---|
| **7.1** `feat/phase7.1-catalog` | 從 `template.json` 自動產生 `templates/catalog.json` 與能力索引頁（檔頭寫「自動產生，勿手改」）。欄位參考官方範本索引：用途、媒體類型、模型、`min_comfyui_version`、`requires_custom_nodes`、狀態、平台、`frame_anchoring` | 測試確認產生的檔案是最新的；手寫的能力列改成連到 catalog | 不需要 |
| **7.2** `feat/phase7.2-capability-detect` | `detect_video_capabilities` 認得 template 宣告的能力（`object_track`、`wan_animate_*`、`masked_edit`）；`doctor` 一併顯示 | 偵測器測試 | Windows 跑偵測與 `doctor`，結果和實際模型一致 |
| **7.3** `docs/phase7.3-skills-6` | 18 個技能收斂成 6 個：`game-art-brief`、`platform-image-gen`、`comfyui-run`、`local-media-tools`、`comfyui-extend`、`comfyui-install`。技能只寫怎麼選、怎麼判斷，細節交給 catalog 與 reference。AGENTS 路由同步。量大就拆兩個 PR：先新增並轉址，再刪舊的 | 連結測試與中性用語測試；舊技能的每條規則都對應到新位置（附對照表） | 用典型需求走一次路由（圖示、局部重繪、物件遮罩加 VACE、換道具、Idle 動作、特效去背、新 node 提案），記錄每個需求選到哪個技能與 template |
| **7.4** `docs/phase7.4-extension-protocol` | `comfyui-extend` 的擴充協議：提案 → 使用者確認 → 固定 revision、sha256 pin → 優先從官方範本或 core blueprint 派生 → template 標 `draft` → 測試 → 實機證據 → 狀態 PR。技能與文件裡剩下的「不可臨場組 graph」禁令改成引用協議。附一個唯讀、需連網的上游比對腳本（選用，不進 runner） | 連結測試；協議範例用第 3 階段 VACE 的實際過程 | 不需要 |

### 第 8 階段：退場

| PR | 範圍 | 驗收 | 實機驗證 |
|---|---|---|---|
| **8.1** `docs/phase8.1-node-alias-exit` | 唯讀掃描各機器 `user/default/workflows/` 裡的舊節點名稱。評估三個方案：ComfyUI core 的 Node Replacement API、直接移除別名、繼續保留。要回答四件事：① 套件是 V1 寫法（有 `NODE_CLASS_MAPPINGS` 時，core 不會用 `comfy_entrypoint`），要怎麼註冊；② face-swap 舊 socket 型別能不能用 input/output mapping 表達；③ 舊名稱還在 `NODE_CLASS_MAPPINGS` 時，replacement 不會觸發；④ 沒有 `_meta` 的 API prompt 會不會出錯。寫成 ADR 草稿，**需要使用者決定** | 評估附上實測（Windows，用暫存的測試 workflow，不改使用者的檔案） | 掃描結果與測試紀錄 |
| **8.2** `refactor/phase8.2-remove-aliases` | 依 8.1 的決定處理舊名稱：刪 `LEGACY_*`；同步 `test_neutral_wording` 的例外清單和改名頁 | 完整測試。本階段不部署、不重啟 | 部署與重啟留到 8.4，且 queue 必須為空。舊名稱 workflow 的行為見[退場決定](../decisions/2026-10-08-node-alias-exit.md) |
| **8.3** `refactor/phase8.3-remove-builders` | 刪掉已被 template 取代的 builder、`VideoPlan.finalize` 專用路徑，以及還被程式引用的 5 個 stub（先改引用處） | 完整測試；golden 改由 template 維護 | smoke 一輪 |
| **8.4** `feat/phase8.4-deploy-templates` | `deploy_manifest`、`verify_portable_install` 納入 `templates/`；決定 `run` 是否仍然只能從 repo 執行；把第三方 custom node 的 commit 記錄到 `docs/tested-versions.md` | 部署測試；verify-install 數字更新 | 部署 dry run → `deploy --yes` → 另外跑 `verify-install` |

## 5. 已知待辦與待決

| 項目 | 狀態 |
|---|---|
| `face_swap.py`、`video_layers.py` 印出誤導的 device_config 提醒 | PR 3.1 修正：兩支工具改從 `comfyui_pipeline.client` 取 HTTP client，不再載入 `image_graphs` |
| `comfyui_design.py` 改寫成純 Pillow | 已落地（6′.3）；BiRefNet benchmark 仍不部署 |
| Mix node 108 寫死 `device=cuda` | 非 CUDA 平台由 preflight 擋下；等 Mac 實測後才決定要不要宣告平台覆寫（D6） |
| `extra_model_paths.yaml` | 不支援，模型只在 `<comfyui_path>/<path>` 找。要支援必須另外提案 |
| 上傳到 `input/<run_id>/` 的檔案不會自動清理 | 目前要手動清理（[templates/README](../../../templates/README.md)）；要不要自動清理，**等使用者決定** |
| macos-mps | 所有 template 都還沒實測，維持 `untested` |
| 被握住的物件：手部（遮擋物）保護遮罩 | **待開發**（2026-10-09）：局部重繪會把握住物件的手一起重畫。一次性做法與提案方向見[第 3–8 階段總結](../maintenance/restructure-summary-phase3-8.md) |
| review 只能選原始輸出，選不到 `derived_outputs` | **待開發**（2026-10-09），見[第 3–8 階段總結](../maintenance/restructure-summary-phase3-8.md) |
| SD1.5 template | **暫不做**（使用者 2026-10-09 決定）；圖片 builder 保留為 SD1.5 退路 |

## 6. Windows／PowerShell 5.1 經驗

- **不要用 `python -c "..."`**，巢狀引號在 PowerShell 5.1 會壞。小工具寫成 .py 檔：
  ```text
  @'
  print("hello")
  '@ | Set-Content -Encoding UTF8 "$V\helper.py"
  ```
- **verify-install 的通過數**要另外跑 `gameart.py verify-install` 取得，不要從 `deploy` 的輸出推算。
- **重啟 ComfyUI：**
  1. 先讀 `/queue`，確認沒有工作在跑或排隊。
  2. 請使用者關閉 ComfyUI；或者在使用者同意後，用開啟它的同一方式正常關閉。
  3. 用 `local_config.json` 的 `start_script`（`start_comfyui.ps1`）啟動。
  4. 每 5 秒讀一次 `/system_stats`，最多等 3 分鐘。不硬砍。
- **`tests` 套件被遮蔽：** ComfyUI venv 的 site-packages 有套件裝了頂層 `tests`，所以不要寫 `python -m unittest tests.test_x`。完整測試用 `-m unittest discover -s tests`，單檔用 `python tests/test_x.py`。
- **找 device_config 提醒**用樣式 `找不到.*device_config`，不要只搜 `device_config`（會誤中正常輸出）。
- 輸出導到檔案用 `*> file.txt`。所有指令都用 `local_config.json` 的 `python_exe`。

## 7. 回報給審核端

PR 描述（繁體中文）用這個格式：

```text
## 摘要（一到三句）
## 範圍（對應本頁哪個 PR；和計畫不同的地方與原因）
## 變更（依檔案或模組）
## 測試（改前、改後的 Ran／OK／skipped；新增的測試）
## 實機驗證證據
- 環境：Windows、GPU、ComfyUI 版本、HEAD commit
- 每一步：指令、結果、證據路徑（output/verify-...）、時間（台北）
- 異常與沒有做的步驟（原因）
## 待使用者決定
## 風險與回退方式
```

PR 開好後，在對話中回報：PR 網址、head commit、測試數字、實機結果一句話、待決事項。審核端看完會回「可以合併」或修改清單；**合併由使用者做**。
