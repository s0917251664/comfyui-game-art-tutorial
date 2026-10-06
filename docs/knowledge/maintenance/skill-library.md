---
type: architecture-reference
status: current
last_updated: 2026-10-06
---

# 專案技能庫、執行路線與維護規則

本頁是專案技能庫路線盤點與新能力／技能維護規則的 canonical reference。它記錄目前已存在的執行方式和未完成的遷移評估；不是執行入口、移植計畫或讓任何技能自動改用 API 的授權。技能 metadata 的觸發描述、入口 body、references 和各路線自己的 gate 仍是使用者呼叫能力時的操作依據。

## 執行路線

依使用者目標選擇路線。已知能力時沿用其專屬 skill，不從 repo 名稱、ComfyUI server 或已有 Python code 推定必須安裝／執行相同環境。

| 路線 | 用途與必要檢查 | Runtime／程式要求 |
|---|---|---|
| Brief／需求與工作流程 | 釐清來源、reference、修改／保留項、交付及驗收；不執行生成。 | 零 ComfyUI／Python 要求。 |
| 平台原生圖片工具 | 核對本次會話實際提供的工具及即時 schema，使用其明確支援的輸入／輸出。 | 不讀 `local_config.json`，不要求 profile、detector 或本機 Python；不推定影片、外部 API／付費權限可用。 |
| 直接 ComfyUI API＋固定 graph assets | 對已存在的固定 API graph JSON 直接呼叫 server HTTP API。Upload、history 與 outputs 依固定契約。 | 不必新增 Python wrapper、CLI、`generate.py` task/backend 或 capability catalog；仍要依當次 ComfyUI URL 及 live schema/models preflight。 |
| 既有 `generate.py` CLI | 使用已接入的圖片／影片 task，沿用 image profiles、影片 backend/capability 與既有輸入／結果契約。 | 保留現有 Python facade/package；不要因單一 API graph 存在就宣稱其 task 已遷移。 |
| 本機 helper／custom node | 執行需要 local file、批次／長片解碼、state、資料夾管理或 server-side 專用媒體演算法的工作。 | 只有為契約所需的 client/helper、套件或 custom node 才保留／新增；清楚區分 client／server 責任和部署。 |

ComfyUI API 是另一種呼叫既有 graph 的方式，不等於 API client 產品或新 engine。若固定 assets 足以處理 prompt 和有限欄位，agent 可直接呼叫 ComfyUI；若任務還包含受控媒體前處理、批次、輪詢恢復或輸出整理，按實際必要性評估 helper，不以「無 Python」當普遍要求。

## 新技能、能力與 discoverability

新增或改技能時遵循[新增能力檢查清單](new-capability-checklist.md)。每個技能至少交代：

1. **觸發與邊界：** 使用者說什麼會用；支援及不支援的輸入、輸出和工作。
2. **依賴與版本：** 平台實際工具 schema、ComfyUI server／node/model pins、profile/backend、local packages 或 input asset versions；只列路線實際依賴。
3. **執行 gate：** 明確的當前能力查詢、固定資產／參數、何時可 upload／queue／呼叫及失敗處理。API route 檢查 live schema、模型 selectors 和固定 graph；CLI route 用既有 capability/profile；platform route 用 current tool schema。
4. **狀態與最小證據：** 分開記技術 contract、實際輸出、內容 candidate 與使用者接受；失敗、未測、scope 限制保留在 evidence/reference。
5. **操作 references：** 入口只放不可跳過的條件與簡明操作；精確 input keys、request/response、長表和踩坑放 reference；最小 graph/assets 有明確版本／hash。

Repo 內新增、改名或責任變更的技能，應更新 `AGENTS.md` 核心技能清單及 `docs/knowledge/TOOLS.md`、`docs/knowledge/INDEX.md` 實際路由；也更新直接相依 skill 的 handoff。全域 discoverable stub 僅在使用者明確要求跨 repo／全域找到該專案技能時建立；stub 指向唯一 canonical 文件，不複製另一套操作規則。

## 技能庫盤點

盤點基準：本 repository 的 `skills/*/SKILL.md`，共 **33 個技能目錄**。其中包括 17 個專案自有遊戲美術技能、1 個 project-knowledge skill，及 15 個固定來源的 Obsidian 上游技能。下表涵蓋 17 個美術技能；其餘 16 個不屬於本次美術執行路線盤點，並未要求修改它們。

「API 後續適配度」表示日後可研究是否適合，**不是已完成遷移**。只有 Wan Animate 欄明確列出目前直接 API graph；其他技能仍依其現行 implementation 運作。

| 技能 | 目前實作／職責 | API 後續適配度與狀態 |
|---|---|---|
| `game-art-initialize` | 新使用者初始化與依任務路由；本身不生成、不安裝。 | 只做路由；支援把明確選定能力交給 API skill，沒有自身 API 執行器。 |
| `game-art-workflow` | 共用 brief、參考圖責任、分階段和驗收規劃；不呼叫引擎。 | 不適用於 brief 本身；可交接到任何明確選定 executor。 |
| `game-art-edit-brief` | ComfyUI 圖片 task 輸入映射與編修 brief；不生成。 | 目前只映射已存在 CLI task；並非 API 執行，未遷移。 |
| `platform-image-gen` | 呼叫本次平台實際提供的圖片工具，依當下 schema 檢查能力。 | 平台原生路線，不經 ComfyUI API；不要求本機 Python／config。 |
| `comfyui-art-gen` | `generate.py` 圖片 task、profile、能力 snapshot 和本機 ComfyUI CLI。 | 某些固定 graph 可另作直接 API 評估；目前圖片任務仍用現行 CLI/gate，未遷移。 |
| `comfyui-image-sweep` | `image_edit_tools.py sweep` 包裝既有圖片 CLI task 的有限參數比較。 | 依賴既有 task 語意與 sweep orchestration；不適合把 wrapper 當單個 graph API，目前未遷移。 |
| `comfyui-object-design` | Python helper 組合既有 ComfyUI Core graph 和圖片 task，處理 scene／sheet／pattern。 | graph 可否直接 API 呼叫需按各模式另評估；helper 現仍提供現行合成／CLI，未遷移。 |
| `comfyui-video-gen` | `generate.py` 影片 task/backend、`video_capabilities.json`、本機 concat/composite。 | 固定已接入 backend 仍走 CLI；不可由 API node 存在取代 backend gate，目前未遷移。 |
| `comfyui-wan-animate` | 以固定 API-format JSON 直接呼叫 ComfyUI HTTP API；Mix17／Move17 近期直接 HTTP 技術 smoke 通過，內容仍 candidate，未接 `generate.py`。 | 已有 API 路線；33 幀新模板及輸出品質不能由 17 幀測試推定，依專用 skill／evidence 管理。 |
| `comfyui-character-animation-workflow` | 編排既有圖片／影片 task、階段和人工驗收，不另加模型參數。 | 作 workflow orchestrator，可在明確支援後委派 API skill；本身沒有遷移。 |
| `comfyui-film-workflow` | 劇情多鏡規劃與影音 helper；依實際需要用本機音訊／片段工具和既有生成 task。 | 規劃部分可跨路線；時間線、音訊／解碼狀態處理仍依各 helper，未遷移為 API-only。 |
| `comfyui-face-swap-workflow` | 薄 client、共享 media/contracts 與 server-side ReActor custom node；完整影片處理在 ComfyUI server。 | Queue 可由 API 發起，但輸入 gate、chunked media／輸出契約依賴現有 code，非只替換請求 transport；未遷移。 |
| `comfyui-video-layers` | 薄 client 加固定 custom node，server 執行 SAM propagation、逐幀 layer compose、音訊與驗證。 | ComfyUI API 是底層 transport 一部分；media/state 算法靠 server code，非單純固定 graph 替代；未遷移。 |
| `local-image-edit-tools` | Pillow／NumPy 的本機 composite、recolor、compare、reference-board、asset-audit；另有既有 task sweep 轉交。 | 像素檔案操作不適用於生成 API；保留 local helper code。 |
| `comfyui-install` | 維護者／使用者依硬體與安裝狀態安裝、部署 ComfyUI。 | 環境操作路線；不屬於 API 生成 executor。 |
| `comfyui-new-tool-checklist` | 本維護清單的 route-specific 新技能／能力流程。 | 治理文件，不執行 API 或生成。 |
| `comfyui-pipeline-review` | 按範圍做 offline skill/workflow/architecture review；明確要求時另研究當前模型／技術。 | 唯讀治理流程，不呼叫模型 API，也不改現行 executor。 |

## 維護與審視責任

- **技能庫／執行路線 review** 可按明確請求讀當前 skills、TOOL 路由、source、相關案例和驗收證據。預設先 offline；不強制 web 搜尋、不要求完整掃描 model 類別、不下載模型或替換 profiles。單純 review 不自行改檔；同一要求或先前上下文若已明確授權具體技能／文件修訂，則可直接按授權範圍實作，不重問。
- **模型／當前技術 review** 只有使用者明確要求查新、比較或升級候選才進行。此時按限定類別查一手資料，記來源日期、現行證據、候選、限制及建議；不得替換 profile、下載或部署。
- **新增／修改能力** 只有具體建置任務才套新增能力 checklist；先確認授權範圍，再按路線做實測。純 brief、平台原生工具使用與治理 skill 不因位於本 repo 就強制安裝 ComfyUI/Python。
- **驗收規則** 由對應 asset/result record 保持；知識觀察與 review 建議不自動改生成 profile 或 accepted/rejected 決定。
