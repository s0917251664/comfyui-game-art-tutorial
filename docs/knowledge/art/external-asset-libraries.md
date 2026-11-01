---
type: reference
status: draft
---
# 外部免費素材庫（臉、服裝、姿勢）

來源：Block 客（blocktempo）2026-11-01 報導〈佛心 AI 素材庫〉，日本創作者あぎ（Agi）公開的三個素材庫。這是新聞轉述，**條款細節以三個站的原始頁面為準**；「在本專案怎麼用」一節已於 2026-11-02 做過一輪小規模實測（見「實測紀錄」），結論只在該範圍內成立。

## 三個素材庫

| 庫 | 內容 | 授權（依報導） | 連結 |
|---|---|---|---|
| 人臉 | 1,499 張（893 正面臉、606 造型照），Midjourney 生成；正面臉為脖子以上構圖 | CC0，商用與修改可，不必標註；請求勿轉載圖片本身；禁止冒充真人 | https://ai-portrait-gallery.pages.dev/ |
| 服裝 | 1,407 張純服裝圖（無人物），文字生成 | 非 CC0；禁止再散布、轉售圖片（含加工後）與批次下載；用它當參考做出的作品可商用；不保證不侵權；禁止用於真人或未成年 | https://ai-costume-gallery.pages.dev/ |
| 姿勢 | 288 種姿勢 × 5 角度（1,439 張深度圖，無臉灰色人偶）；另有人偶線稿版 | 同服裝庫 | 深度圖 https://ai-pose-depth-gallery.pages.dev/ ；線稿 https://ai-pose-gallery.pages.dev/ |

已知瑕疵（站方或報導自述）：服裝圖有細節錯誤（如釦子兩側都有）；姿勢圖的手指與交疊腿邊界較弱。

## 在本專案怎麼用（2026-11-02 實測觀察；範圍見下節）

- **姿勢深度圖 → `--control-type depth`**：深度圖可直接當 `--pose-ref`，不必另外抽取；兩個姿勢（雙手扠腰、側身展臂）都被遵守，不論帶不帶角色參考。限制：深度圖是無衣裸色人偶，輸出容易照人偶體型生出內衣／緊身衣，且 prompt 寫了衣服也會被壓過，要自己控制 prompt 與負面詞並逐張看。
- **線稿版 → `canny`**：姿勢被遵守，但人偶線條與關節球會被當成真實邊緣畫進成品（成品像畫了線的假人），不能直接當乾淨姿勢控制；深度圖餵 `canny` 同樣不乾淨（頭髮亂散）。
- **`pose`（OpenPose）**：線稿人偶與深度圖人偶都**抽不到有效骨架**——成品退回 prompt／角色參考本身，變成與姿勢無關的臉部特寫。無臉人偶不能用 `pose`。
- **人臉 → 角色一致性參考**：人臉庫圖是脖子以上的特寫，當 `character_action` 的 `--character-ref` 時，該路線偏向照參考構圖與髮型，臉不穩定：同 seed 換姿勢，臉部相似度與髮型（短髮／過長髮／髮片失真）都不一致，不能說「換姿勢不換臉」成立。降低 `--ip-weight` 到 0.4 也沒有改善（出現髮簾狀失真）。
- **服裝 → 外觀參考**：未測。
- 這些庫的臉、衣服、姿勢風格偏寫實 AI 美女與成人市場（報導稱姿勢庫約三分之二偏成人向）；實際看到的 `全身1人・標準系` 分類也以坐、跪、躺的擺拍為主，找不到行走／揮擊類動作。遊戲動作用途能用的很少，使用前要先挑。

## 實測紀錄

- 日期：2026-11-02；環境：本機 Windows、ComfyUI 0.34.0、profile `sdxl_standard`（`image_capabilities.json` 顯示 `controlnet.canny/pose/depth`、`ipadapter` 皆可用；`character_action` 與 `pose_only` 為 legacy 已驗證）。`generate.py` 圖片 task 沒有 `--preflight`，用能力快照與 profile 檢查代替；快照為 11 天前，指紋一致。
- 參考圖（本機、不進 repo）：人臉 1 張 `f71f980dde3`；姿勢深度圖與線稿各 `full_single_P018_front`（雙手扠腰）、`full_single_P077_front`（側身展臂），共 6 張，放 `output/pose-face-test/refs/`。
- 指令骨架：`python tools_src/generate.py character_action --character-ref <face> --pose-ref <pose> --control-type <depth|canny|pose> --seed 42 --width 768 --height 1024 --prompt "a young woman, full body standing, ..."`；另跑 `pose_only --control-type depth`。固定 seed 42，每組 1 張；單張約 8–16 秒（第一張含載入 32 秒）。
- 結果對照圖：`output/pose-face-test/sheet0.png`、`sheet1.png`、`sheet2.png`；各組輸出在 `output/pose-face-test/out/`（A=depth、B=depth 換姿勢、C/D=canny 線稿、E/G=pose 線稿、F=pose 深度圖、H=canny 深度圖、I=pose_only depth、J=ip-weight 0.4）。
- 限制：只測 1 張臉、2 個姿勢、1 張／組、單 seed，沒有做行走／揮擊類，也沒測服裝庫；臉部一致性只做目視判斷。**技術結果，非美術接受**，未 accept／reject。
- 暫時結論：姿勢庫深度圖可當姿勢來源；要「換姿勢不換臉」不能靠人臉庫特寫配 `character_action`，須另找一致性方法（先實驗，標明實驗，再依擴充協議）。

## 使用規則

1. **不進 repo**：服裝庫與姿勢庫禁止再散布，人臉庫作者請求勿轉載。repo 與對外簡報只放連結，不放圖片本身，也不批次下載。
2. 使用者自己下載、當參考圖餵進流程可以；產出的作品可商用，但要在素材紀錄寫明參考來源與庫名（[result-records](../result-records.md)）。
3. 禁止用於表現真人或未成年；人臉庫圖不可冒充真人。遊戲角色用途以外的情境先問使用者。
4. 商用前請使用者自己確認三個站的最新條款；agent 不做法律判斷。
5. 要把它做成固定 template，依[擴充協議](../maintenance/extension-protocol.md)：先標實驗、實測、使用者確認後才進產線。
