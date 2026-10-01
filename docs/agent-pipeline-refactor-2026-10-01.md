# 產線技能與知識庫重構紀錄（2026-10-01）

## 範圍

本次把六份技能入口改為漸進揭露路由，並將可重用的 task、參數、安裝、維護、影片、角色動畫、決策與經驗資料集中到 `docs/knowledge/`，作為可由 Obsidian 開啟的 vault。入口保留原有 skill name/description 與重要路由、能力 gate、平台限制、設定／URL／部署／輸出目錄契約、人工驗收和一次有理由修正。舊 art reference 頁保留標題與相容連結。知識頁按需載入；經驗不會自動改寫 profile 或生成規則。

圖片結果 manifest 維持 opt-in：`--result-json` 記錄技術資訊，不改變既有 task 選擇或輸出策略，也不等同美術驗收。素材頁與人工驗收狀態以 `docs/knowledge/assets/*.md` 的標準 Markdown 記錄；技術測試候選必須維持 `candidate`，不得由技術檢查或遷移動作推定為 `accepted`。本次 `smoke-potion` 已由舊測試資料遷移到 [Markdown 素材頁](knowledge/assets/smoke-potion.md)，圖檔與 JSON manifest 留在 repo `output/` 內；遷移 hash 完整核對，沒有記錄 Steve 的 accepted 決定。舊 SQLite smoke database 已移除，原 PNG／JSON 證據保留。

## 主要文件

- Vault 導覽與工具路由：[`INDEX.md`](knowledge/INDEX.md)、[`TOOLS.md`](knowledge/TOOLS.md)、[`DECISIONS.md`](knowledge/DECISIONS.md)。
- 美術產圖 task 與參數：[`art-generation.md`](knowledge/art-generation.md)、[`art-parameters.md`](knowledge/art-parameters.md)、[`art/`](knowledge/art/)。
- 結果 manifest 與 Markdown 素材紀錄：[`result-records.md`](knowledge/result-records.md)、[`assets/smoke-potion.md`](knowledge/assets/smoke-potion.md)。
- 模型經驗及日期化決策：[`experiences/`](knowledge/experiences/)、[`decisions/`](knowledge/decisions/)。
- 安裝、維護、影片、動畫知識分別置於 [`installation/`](knowledge/installation/)、[`maintenance/`](knowledge/maintenance/)、[`video/`](knowledge/video/)、[`animation/`](knowledge/animation/)。
- 根目錄 [`AGENTS.md`](../AGENTS.md) 和 [`教學.md`](../教學.md) 提供技能與 vault 路由及資產紀錄的使用入口。

在 Obsidian 中用 **Open folder as vault** 開啟 `docs/knowledge/`。本次提供最小 `.obsidian` 設定；沒有安裝 Obsidian 或社群外掛，也未做 GUI 開啟驗證。repo 的相對 Markdown 連結可由一般 Markdown 閱讀器使用；vault 內導覽連結指向 vault 內頁面。

## 新增能力檢查適用項目

依 repo 的新增工具檢查規則，純文件整理本身不套用完整新增能力 checklist。這次只記錄現存 opt-in `--result-json` manifest 契約與 Markdown 素材頁驗收界線；沒有新增 workflow、MCP、模型、續作服務或透明影片能力。模型內容品質仍須人工驗收。

## 驗證

- 現行驗證（撤回 asset-library 功能後）：146 tests 通過、0 skip；portable verifier 為 18 pass / 0 fail。這是目前保留的程式／部署驗證結果。
- 撤回前歷史紀錄：當時曾報告 157 tests、0 skip，portable verifier 為 19 pass / 0 fail，另有 11 個 source/deployed `.py` 與 `.json` 檔案 hash 相符。這些數字包含後來撤回的 SQLite 資產庫工具與部署檔，不代表目前版本；僅 `asset_library` 部署副本及其 hash 檢查已移除，其餘 portable 部署核對保留。
- 五個實機結果（SDXL concept、去背透明輸出、layer split、FLUX.2 concept、FLUX.2 edit）經最後 validator 重讀，對應 PNG hash、尺寸與 alpha 相符；技術驗證通過不代表內容已接受。
- 同環境、同 seed 73101 的 concept legacy 呼叫與加上 `--result-json` 的呼叫，PNG bytes 與 pixels 相同。ComfyUI 允許同 graph 命中快取，因此這只驗證新旗標未改 graph／輸出，不是獨立重抽或跨 GPU 一致性證明。
- `smoke-potion` 候選由 SQLite 歷史資料遷移至 Markdown 素材頁，所有保留檔案 hash 核對一致；狀態仍是 `candidate`，尚無 Steve accepted/rejected 決定。舊 smoke database 已移除，PNG 與 JSON manifest 證據保留。輸出仍可見多個瓶子與大面積灰底／陰影。
- 撤回前歷史連結掃描曾記錄 287 個相對連結、0 個失效，並假設 vault 內連結不出 vault；此結果不代表目前連結拓撲。現況 root 重查 `docs/knowledge/` 有 72 個 vault 相對連結、0 個 broken。另有素材頁兩個 artifact link 指向 vault 外的 repo `output/`，以及一條 ADR link 指回本報告；這些連結是否有效以目標檔案實際存在為準。舊標題相容性已檢查；Obsidian UI 未安裝，未做 GUI 驗證。

## 入口檔 UTF-8 byte 數

下表是原重構完成時量測的原始入口與當時入口 UTF-8 byte 數，非本次文件更新後的現值；後續小幅修改尚未更新此表。它不是 token 精確估值，也不代表完成任務只需讀入口；完整上下文依任務再讀對應 canonical 知識頁。

| Skill | 原始 bytes | 目前 bytes |
|---|---:|---:|
| `comfyui-art-gen` | 42,316 | 9,546 |
| `comfyui-character-animation-workflow` | 8,367 | 2,475 |
| `comfyui-install` | 26,749 | 1,403 |
| `comfyui-new-tool-checklist` | 10,263 | 1,171 |
| `comfyui-pipeline-review` | 4,606 | 1,148 |
| `comfyui-video-gen` | 18,852 | 5,982 |

## 尚未宣稱的事項

已驗證現存 CLI 技術路徑和文件路由；圖像內容品質需依每項使用者需求人工驗收。`--result-json` 的 manifest 記錄模型檔名而非權重 hash，graph digest 不是完整 graph；要重跑需具備相符模型、runtime、ComfyUI/nodes 與版本條件，仍不承諾逐像素一致。歷史觀察保留其日期、模型、證據與適用範圍，只有證據足夠並經人工核准才提升為正式決策或 profile 規則。
