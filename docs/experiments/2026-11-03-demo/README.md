---
type: demo-record
status: candidate
date: 2026-11-03
---
# 新簡報四個 Demo 實拍紀錄（Windows，RTX 4080，main 7abe662＋PR #12 分支）

素材：2026-10-19 的騎士圖 A.png（自行生成，不含 Skye 素材）。結果都是候選，美術由人驗收（R1）。沒有螢幕錄影工具，所以用「前後對照 GIF／對照圖」加原始 log 代替螢幕錄影。評分皆為目視。

| Demo | 指令 | 耗時 | 結果 |
|---|---|---|---|
| 1 內建動作 | `gameart.py pose-edit run --image A.png --action raise_hand`（seed 7／21／99） | 85 秒（3 張） | 3 張都舉起右手、臉髮盔甲披風大致保住；原本扛在肩上的大劍只剩水晶劍身浮在背後，握柄消失。圖 `demo1_pose_edit_raise_hand.jpg` |
| 2 只改手掌 | `pose-edit run --image A.png --part 手掌=朝鏡頭 --part 右手=舉高` | 84 秒（3 張） | seed 21、99 掌心朝鏡頭、手舉高；seed 7 舉的是另一隻手。圖 `demo2_pose_edit_part_palm.jpg` |
| 3 局部遮罩重畫 | `gameart.py sam` 圈出劍身（候選 #02，3.7% 面積）→ `generate.py flux2_edit`（整圖改成「紅色火焰劍身＋金色雕紋」）→ `gameart.py edit composite` 只貼回遮罩內（遮罩向外擴 12 像素） | sam 31 秒、FLUX.2 32 秒 | 遮罩外 974k 像素比對：貼回前幾乎全被改（953,562 個）、貼回後 0 個；劍身變成紅色火焰雕紋。FLUX.2 輸出高度 1232，與原圖 1216 不同，先縮回 832×1216 才能比對。圖 `demo3_mask_redraw.jpg`、`data/demo3_*.json` |
| 4 影片物件替換 | `run video/sam3/track-text`（`giant blade`）→ `run video/wan-vace/inpaint-reference`（參考圖＝紅金火焰劍身，`grow=16`） | sam3 15 秒、VACE 約 84 秒（49 幀、24fps） | 劍身在 49 幀都被換成金色／紅紋劍身並跟著動作；對照 `demo4_before_after.gif`／`.jpg` |

## 要誠實標註的地方

- **Demo 3 先失敗過**：SDXL `inpaint`／`guided_inpaint` 在這個劍身遮罩上只把劍身塗成接近背景色的灰影，畫不出火焰劍；改用 FLUX.2 整圖編修加合成才成功。
- **Demo 4 追蹤與換圖要調**：`track-text` 用 `sword` 會同時選到劍鞘且第 12 幀丟失劍身，改 `giant blade` 才穩定追到劍身 49 幀；第一次 VACE（參考圖是兩把劍的整張圖、`grow=8`）只把劍身抹成背景，沒畫出新劍，換成只含劍身的參考圖、旋轉到斜向、`grow=16`、seed 21 才成功。
- **Demo 4 遮罩外「逐幀不變」沒有達到嚴格 0**：我把合成後的逐幀 PNG 與來源 mp4 解碼結果比較，遮罩向外 16 像素以外，每幀仍有約 1 萬個像素（約 3%）差異超過 8 個色階，平均差異約 1.6／255，且離遮罩很遠的區域也有。原因還沒查清（可能是來源影片解碼方式與 pipeline 不同），所以簡報不要寫「逐幀完全不變」，可以寫「遮罩外大致不變（平均差 1.6/255）」。數據在 `data/demo4_outside_check.json`。
- 單一素材、單一次執行；時間含模型載入。
