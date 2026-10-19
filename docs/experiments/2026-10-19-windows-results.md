---
type: experiment-results
status: ours-side-complete-platform-side-pending
date: 2026-10-19
---
# Windows 實測結果（我方側）

主機：Windows 11、RTX 4080 16GB、ComfyUI 0.34.0，預設 SDXL 設定（`--style illustration`）。操作依 `2026-10-18-windows-checklist.md`，驅動腳本 `scripts/run_windows_experiments.py`，證據 `2026-10-19-evidence/`。
素材為本次自行生成（A.png：持劍騎士，seed 7；M.png／M2.png：多邊形手畫遮罩，未經美術確認）。所有結果只代表本機、當日、單一素材；美術好壞由人判定（R1）。「平台側」需要 Steve 的 Codex／Gemini 帳號，尚未跑。

| 實驗 | 我方側結果 | 樣本 | 結論 |
|---|---|---|---|
| E1 可重現 | 固定 seed：與第 1 張逐像素差異 0%（4 組皆 0）；換 seed：100% 像素不同 | 5＋5，同機 | 可寫（我方）；平台側待測 |
| E2 範圍外不變 | `guided_inpaint` 後不合成：範圍外 99.4% 像素被改動；`edit composite` 貼回後 0 像素。換槍需求：只部分達成，畫面有殘留劍身碎片，自評約 2/5（非盲評） | 1 | 可寫（技術面）；品質為單例 |
| E3 角色一致 | 我方側已跑：`character_action`（pose），以 A.png 為角色參考，姿勢圖取自 `output/cover-redo` 既有骨架圖 5 張。5/5 張髮色由銀灰變金／淡黃、瞳色由黃變紅、服裝與配色都有改動，身份沒保住（我目視，非盲評，未打分）。單張約 11 秒 | 5 | 我方漂移屬實；盲評分數與平台側待測 |
| E4 透明背景 | `icon_asset` 輸出 RGBA，`has_alpha=true`，findings 為空；白底預覽邊緣乾淨（audit 自己註明不代表去背品質） | 1 | 我方可；平台側待測 |
| E5 圖上文字 | POTION 0/5、START 0/5、「開始遊戲」0/5、「藥水」0/5、1234 0/5，合計 0/25（嚴格：整組字完全正確才算；我個人目視，非盲評）。英文常多一個 T 或重複字；中文為假字 | 25 | 可寫：本機 SDXL 路線不能靠它出字，要後製加字 |
| E6 選區精度 | 小目標（頸部扣飾，1,781 像素）`inpaint` 不合成：範圍外 99.4% 被改動 | 1 | 同 E2，需合成 |
| E7 影片與 3D | `run list` 有 3D 2、影片 27（含 h3 14、wan-animate 6、wan 4、sam3 2、wan-vace 1）。`video/wan/img2video --preflight`：節點 11/11、模型 3/3 齊全，但因 template 標為 untested 被擋，需加 `--allow-unverified-platform` | — | 有（實驗中） |
| E8 時間 | 單張 SDXL 概念圖約 7.0 秒（42 次平均，含啟動與取圖）；首次載入模型約 12 秒；`inpaint`／`guided_inpaint` 約 7 秒。成本：本機免費，不含電費與設備 | 42 | 可寫；平台側待測 |

## 補充發現

- **「inpaint 調低 denoise 會變灰」已實測證實**（PR #11 原為機制推論）。`inpaint` 同圖同遮罩：denoise 1.0 可生成內容；0.6 與 0.3 遮罩內變成均勻灰色色塊（遮罩內平均飽和度 50→23→8→3）。證據 `2026-10-19-evidence/denoise_compare.jpg`。單一素材、單一 seed。
- **ComfyUI 對完全相同的請求直接回傳快取，不重算**：連跑同 seed 同提示詞，第 2 次起只花約 1 秒且檔名不變。測可重現性時必須穿插別的請求（本實驗已如此做）。此點應寫進知識庫。
- 機器快照過期時 `generate.py` 會拒絕執行；`doctor --refresh` 後還需讓 `tools_src` 旁有 device_config 等檔（本次手動複製，已加入 .gitignore 類檔案，不入版控）。

## E3 補充：用專案內已驗收的角色圖重跑（2026-10-19）

改用 Skye 遊戲專案已驗收的角色圖當參考，姿勢同樣是 5 張骨架圖，`character_action`（pose）各生 1 張。此角色圖屬遊戲專案素材，圖片只留在本機，不放入 repo，以下為文字描述（我目視，非盲評，未打分）：
- 保住的：藍髮色系、馬耳形狀、青色眼睛、深藍短褲與黑手套、橘色領巾（5 張中約 3 張有）。
- 漂移的：5/5 髮型變長變蓬、體型比原圖不 Q、上衣變白色外套加藍色徽章、靴子樣式不一致；領巾在 2 張消失或變成領帶。
- 結論：用已驗收的卡通角色，髮色與五官保住較多，但服裝與比例仍每張不同。與騎士圖（髮色眼色全變）合起來看，「我方會漂移」成立，程度依角色而異。
- 對照：遊戲專案後續改用「修改既有影格」（Flux2 遮罩編修）來保一致，不重新生成整張，這是比 `character_action` 更穩的做法，但尚未在本實驗中量測。
