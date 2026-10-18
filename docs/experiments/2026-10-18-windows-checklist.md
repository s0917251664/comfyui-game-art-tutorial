---
type: experiment-checklist
status: draft
date: 2026-10-18
---
# Windows 主機實測清單（照著做就好）

這是 `2026-10-18-platform-agent-vs-pipeline.md` 的操作版。每個實驗都寫了：準備什麼、怎麼做、記什麼、填到哪一格。不需要懂程式，指令整段複製貼上即可。

「我方」指本專案的固定流程，「平台」指 Codex 或 Gemini 等內建生圖。

## 開始前（約 30 分鐘，只做一次）

1. **確認 ComfyUI 已開啟**：瀏覽器開得到 ComfyUI 的頁面（網址看 `local_config.json` 的 `comfyui_url`）。
2. **開 PowerShell，切到專案資料夾**，再貼上這三行。第一行的引號內，換成 `local_config.json` 裡 `python_exe` 的值：

   ```powershell
   $py = "C:\請換成 python_exe 的值\python.exe"
   $out = "output\experiments\platform-vs-pipeline-20261018"
   New-Item -ItemType Directory -Force $out | Out-Null
   ```
3. **檢查機器狀態**：`& $py tools_src\gameart.py doctor`。若提示快照過期，再跑 `& $py tools_src\gameart.py doctor --refresh`（只掃描，不會下載任何東西）。
4. **準備素材**，放在 `$out\inputs\`：
   - `A.png`：一張已經驗收過的角色圖（有手持武器的最好）。
   - `M.png`：只蓋住「手上武器」的遮罩。畫法照 `docs/knowledge/art/masking.md`：要改的地方是透明、其餘不透明。
   - `pose1.png` 到 `pose5.png`：五張不同姿勢的線稿或骨架圖（E3 用）。
5. **準備平台帳號**：能登入 Codex 或 Gemini，並確認可以生圖。記下平台名、模型名、方案。
6. **建立結果檔**：把本文最後的「結果登錄表」複製到 `$out\RESULTS.md`。
7. **若指令說找不到 ComfyUI 位址**：在 `generate.py` 指令最後加上 `--comfy-url http://127.0.0.1:8188`（埠號以你的 ComfyUI 為準）。
8. **兩條規則**：每次都換一個新的輸出資料夾名（舊資料夾會被拒絕寫入）；平台那邊每次開新對話，並把提示詞原文存下來。

> 看圖檔名：我方每次輸出的圖片在資料夾裡，名稱像 `concept_00001_.png`，同資料夾還有一份 `.json` 記錄。下面的 `<圖片路徑>` 請換成實際檔案路徑。

## 怎麼做「像素比較」（E1、E2、E6 都會用到）

```powershell
& $py tools_src\gameart.py edit compare --source <原圖> --edited <結果圖> --mask <遮罩，可省略> --output-dir "$out\<新資料夾名>"
```

跑完打開那個資料夾的 `comparison.json`：

- `regions.whole.changed_fraction`：整張圖有多少比例的像素不一樣（0 代表完全相同）。
- `regions.preserved.changed_fraction`：有給遮罩時，「不該動的範圍」被改的比例。這個要是 0 才算範圍外沒動。
- 同資料夾的 `comparison.png`、`detail.png` 可以直接用眼睛看。

兩張圖尺寸不同時，工具會報錯。這本身就是一個發現，請在表上寫「尺寸不同，無法逐像素比」。

---

## E2 局部改圖，範圍外有沒有動（最重要，先做）

對應簡報欄位 **D2**。

**準備**：`A.png`、`M.png`。需求固定一句話：「只把手上的武器換成長槍，其他不要動」。

**我方**

```powershell
& $py tools_src\generate.py guided_inpaint --prompt "a long spear" --image "$out\inputs\A.png" --mask "$out\inputs\M.png" --output-dir "$out\E2\ours-raw"
& $py tools_src\gameart.py edit compare --source "$out\inputs\A.png" --edited <ours-raw 裡的圖片路徑> --mask "$out\inputs\M.png" --output-dir "$out\E2\cmp-ours-raw"
& $py tools_src\gameart.py edit composite --source "$out\inputs\A.png" --edited <ours-raw 裡的圖片路徑> --mask "$out\inputs\M.png" --output-dir "$out\E2\ours-composite"
& $py tools_src\gameart.py edit compare --source "$out\inputs\A.png" --edited <ours-composite 裡的圖片路徑> --mask "$out\inputs\M.png" --output-dir "$out\E2\cmp-ours-composite"
```

**平台**：開新對話，上傳 `A.png`，貼上需求。把回傳的圖存成 `$out\E2\platform-1.png`。若平台有「選取區域」功能，再做第二輪，存成 `platform-2.png`。然後各跑一次 compare（`--edited` 換成平台的圖，`--mask` 照樣給 `M.png`），輸出資料夾分別叫 `cmp-platform-1`、`cmp-platform-2`。

**要記**
- 我方：合成前、合成後的 `preserved.changed_fraction`。
- 平台：每一輪的 `preserved.changed_fraction`，或「尺寸不同」。
- 請另一個人看 `detail.png`，給「有沒有達成需求」1 到 5 分（不要告訴他哪張是哪邊）。
- 耗時：我方用秒錶或 `Measure-Command`，平台用秒錶。

**填到**：`RESULTS.md` 的 E2 列。

## E5 圖上文字

對應簡報欄位 **D5**。

**準備**：想好 5 組字樣，例如 POTION、START、「開始遊戲」、「藥水」、1234。

**我方**：每組字樣跑 5 次，種子分別是 1 到 5。把下面的 `POTION` 換成該組字樣，資料夾名也跟著換。

```powershell
1..5 | ForEach-Object { & $py tools_src\generate.py concept --prompt 'a wooden sign that says "POTION"' --seed $_ --output-dir "$out\E5\ours-POTION-$_" }
```

**平台**：同樣的句子，每組字樣生 5 張。

**要記**：逐張看，整組字完全正確才算對。填「正確張數 / 總張數」，例如 `3/5`。平台若一次給好幾張，也要記總張數。

**填到**：E5 列，每邊 5 組字樣的合計，例如 `12/25`。

## E4 透明背景

對應簡報欄位 **D4**。

**我方**

```powershell
& $py tools_src\generate.py icon_asset --prompt "a golden coin game icon" --output-dir "$out\E4\ours"
& $py tools_src\gameart.py edit asset-audit --image <ours 裡的圖片路徑> --output-dir "$out\E4\audit-ours"
```

**平台**：要求「透明背景的金幣遊戲圖示」，存成 `$out\E4\platform.png`，再跑：

```powershell
& $py tools_src\gameart.py edit asset-audit --image "$out\E4\platform.png" --output-dir "$out\E4\audit-platform"
```

**要記**（打開 `audit.json`）：
- `has_alpha` 是 `true` 還是 `false`。
- `findings` 裡有哪些字。
- 打開 `preview_white.png`、`preview_black.png`、`preview_checker.png`：邊緣有沒有白邊、黑邊、破洞（有或無）。
- 若 `has_alpha` 是 `false`，另外記「需另外去背」。

**填到**：E4 列。

## E1 可重現性

對應簡報欄位 **D1**。

**準備**：同一段提示詞，例如 `a red potion bottle on a table`。

**我方，固定種子（5 次）與不固定種子（5 次）**

```powershell
1..5 | ForEach-Object { & $py tools_src\generate.py concept --prompt "a red potion bottle on a table" --seed 12345 --output-dir "$out\E1\fixed-$_" }
1..5 | ForEach-Object { & $py tools_src\generate.py concept --prompt "a red potion bottle on a table" --seed $_ --output-dir "$out\E1\varied-$_" }
```

**平台**：同一句話，每次開新對話，生 5 次，存成 `platform-1.png` 到 `platform-5.png`。同時記：平台有沒有地方可以指定種子（有或無）。

**比較**：第 1 張分別和第 2、3、4、5 張做 compare，不用遮罩。共三組（固定種子、不固定、平台），每組 4 個數字。

**要記**：每組 4 個 `whole.changed_fraction` 的平均。固定種子預期接近 0。

**填到**：E1 列。這項只比同一台主機。

## E3 角色一致性

對應簡報欄位 **D3**。

**我方**：五張姿勢各跑一次。

```powershell
1..5 | ForEach-Object { & $py tools_src\generate.py character_action --prompt "same character, game art" --character-ref "$out\inputs\A.png" --pose-ref "$out\inputs\pose$_.png" --output-dir "$out\E3\ours-$_" }
```

**平台**：上傳 `A.png`，依序要求五個姿勢（用文字描述 `pose1.png` 到 `pose5.png` 的姿勢，或同時上傳姿勢圖），存成 `platform-1.png` 到 `platform-5.png`。

**評分（盲評）**：請另一個人處理。把 10 張圖隨機改名成 `01.png` 到 `10.png`，對照表只留給你。評分人對每張圖打四項，各 1 到 5 分：臉、髮型、服裝、配色。

**要記**：每邊四項的平均分，以及有沒有被姿勢參考污染（例如帽子、衣服形狀被帶偏）。

**填到**：E3 列。

## E6 選區精度

對應簡報欄位 **D6**。

**準備**：選 `A.png` 上一個小目標，例如肩章。用手繪遮罩畫出來，存成 `$out\inputs\M2.png`（做法同 `M.png`）。需求：「把肩章改成紅色」。

**我方**

```powershell
& $py tools_src\generate.py inpaint --prompt "red shoulder badge" --image "$out\inputs\A.png" --mask "$out\inputs\M2.png" --output-dir "$out\E6\ours"
& $py tools_src\gameart.py edit compare --source "$out\inputs\A.png" --edited <ours 裡的圖片路徑> --mask "$out\inputs\M2.png" --output-dir "$out\E6\cmp-ours"
```

**平台**：用「選取區域」或純文字，指定同一個肩章與同一句需求，存成 `platform.png`，同樣 compare。

**要記**：`preserved.changed_fraction`；另外打開 `detail.png`，目視記「肩章旁邊的衣領等鄰近區域有沒有被牽動」（有或無）。

**填到**：E6 列。

## E7 影片與 3D（只查有沒有）

對應簡報欄位 **D7**。

**平台**：在你用的平台介面或說明裡找，有沒有「靜圖轉影片」「動作驅動」「平面圖轉 3D」。有就記入口名稱，沒有就記「未找到」。不需要真的跑長任務。

**我方**

```powershell
& $py tools_src\gameart.py run list
& $py tools_src\gameart.py run video/wan/img2video --preflight
```

**要記**：`run list` 是否列出影片與 3D 的流程；`--preflight` 的結果是通過還是被擋下（被擋會說缺什麼）。

**填到**：E7 列。只寫「有、沒有、實驗中」，不比品質。

## E8 時間與成本

對應簡報欄位 **D8**。不用另外跑，邊做邊記。

- **我方耗時**：在任一指令前面加上 `Measure-Command { ... } | Select-Object TotalSeconds`，例如：

  ```powershell
  Measure-Command { & $py tools_src\generate.py concept --prompt "a red potion bottle" --output-dir "$out\E8\ours" } | Select-Object TotalSeconds
  ```
- **平台耗時**：從按下送出到圖出現，用手機秒錶。
- **平台成本**：實驗前後各看一次用量畫面（額度、點數或金額），記下差額；用 API 的記帳單。
- **我方成本**：寫「本機免費，不含電費與設備」。

**填到**：E8 列。我方耗時取 E2 至 E5 各次的平均。

---

## 最後一步：整理與回報

1. 確認 `RESULTS.md` 每一列都有填，樣本不足的寫「樣本不足」。
2. 把 `RESULTS.md` 和 `output\experiments\platform-vs-pipeline-20261018\` 底下的 `comparison.json`、`audit.json` 打包（圖檔太大可只留 `detail.png`），交回這個專案討論串。
3. 回報後，簡報「待補的數據」頁的 D1 到 D8 會依登錄表更新。

遇到錯誤訊息時：不要重試超過一次，把完整訊息貼回來；不要手動停止 ComfyUI 或清佇列；逾時也不要重送。

## 結果登錄表（複製到 RESULTS.md）

| 實驗（簡報欄位） | 平台側結果 | 我方側結果 | 樣本數 | 結論（可寫／樣本不足／無差異） | 證據資料夾 |
|---|---|---|---|---|---|
| E1（D1）可重現 | | | | | `E1\` |
| E2（D2）範圍外不變 | | | | | `E2\` |
| E3（D3）角色一致 | | | | | `E3\` |
| E4（D4）透明背景 | | | | | `E4\` |
| E5（D5）圖上文字 | | | | | `E5\` |
| E6（D6）選區精度 | | | | | `E6\` |
| E7（D7）影片與 3D | | | | | — |
| E8（D8）時間與成本 | | | | | — |

測試資訊：日期＿＿＿　主機＿＿＿　顯卡＿＿＿　平台與模型＿＿＿　方案＿＿＿
