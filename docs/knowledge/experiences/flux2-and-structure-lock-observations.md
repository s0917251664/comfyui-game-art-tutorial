# FLUX.2 與結構鎖定的經驗觀察

此頁整理特定樣本的經驗，供相關 task 預期管理及人工驗收時參考。它不是通用生成規則，也不會自行改動 profile、prompt、模型選擇或 CLI 預設。

## FLUX.2 Klein 4B：文字拼寫仍不可靠

| 欄位 | 證據 |
|---|---|
| 日期／平台 | 2026-09-01；XU-Nano-PC，Windows CUDA，RTX 4080，16,376 MiB VRAM |
| task／模型 | `flux2_concept`：Klein 4B distilled FP8；對照 stock SDXL `concept` |
| 輸入 | 同一藥水 prompt，1024×1024，seed 20260901；完整命令及模型 SHA-256 見 repo 證據檔案：`docs/tested-versions.md` |
| 觀察 | SDXL 標牌缺少 POTION；FLUX.2 組成與材質較好，但把 POTION 拼成 PENTION。FLUX.2 在這一例較快，不代表文字輸出已可靠。 |
| 適用範圍／限制 | 一個固定 prompt 的本機 PoC；不能外推到其他文字、硬體或提示詞，也不能承諾正確字形。含字樣素材須逐字人工檢查。 |
| 狀態 | 歷史觀察；FLUX.2 仍是獨立實驗路線，不取代 SDXL 主線。 |

## FLUX.2 Klein Base 單圖編輯：臉部細節漂移

| 欄位 | 證據 |
|---|---|
| 日期／平台 | 2026-09-01；同一 RTX 4080，16,376 MiB VRAM |
| task／模型 | `flux2_edit`；FLUX.2 Klein Base 4B FP8 |
| 輸入 | 832×1216 角色參考圖，白金科幻盔甲修改 prompt，seed 20260901；輸出 832×1232；詳細命令及版本證據見 repo 證據檔案：`docs/tested-versions.md` |
| 觀察 | 主體、姿勢、步槍、構圖與灰背景保留，材質成功替換；臉部細節有漂移。這個 task 不是 identity lock。 |
| 適用範圍／限制 | 單一輸入圖與單次本機樣本；不得把輪廓保留推論成角色身分必定穩定，也不得承諾跨圖身份鎖定。 |
| 狀態 | 歷史觀察；只供人工驗收時檢查臉部細節，不自動修改 prompt 或模型。 |

## SDXL icon_asset 結構範本：固定大結構會壓制額外裝飾線條

| 欄位 | 證據 |
|---|---|
| 日期／模型 | 2026-08-19；`sdxl_standard`，轉盤 8 等分放射狀圖示 |
| task／控制 | `icon_asset --structure-ref`；img2img 與 Canny 結構鎖定，denoise 在 0.55 至 0.85 間觀察 |
| 輸入／證據 | 範本圖固定分區與顏色；細節見 [結構範本規則](../art/structure-ref.md) 及 [已知 task 限制](../art/known-limitations.md) |
| 觀察 | 分區數量與顏色穩定，質感隨 denoise 增強；額外鑲花雕紋等需要新邊緣線條的細節沒有明顯出現。這是該結構控制案例的取捨，並非只靠繼續調高 denoise 就能保證解決。 |
| 適用範圍／限制 | 已測的放射狀圖示範例，不保證所有範本或模型行為相同。需要大結構準確時仍以範本為準，成品逐項人工驗收；若額外細節重要，須把它列為獨立驗收目標。 |
| 狀態 | 歷史觀察；正式 task 參數見 [結構範本規則](../art/structure-ref.md)，此頁不覆蓋正式契約。 |
