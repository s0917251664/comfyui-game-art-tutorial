---
type: demo-record
status: candidate
date: 2026-11-03
---
# Demo 重跑（v2）：騎士圖 A.png，Windows RTX 4080，main 7abe662

取代同層 v1。素材為 2026-10-19 自行生成的騎士圖（不含 Skye 素材）。結果是候選，美術由人驗收（R1）；挑圖與正確與否皆為我目視判斷，非盲評。沒有螢幕錄影工具，用對照圖、GIF 與 mp4 預錄代替。

| Demo | 指令（重點） | seed | 耗時 | 成功張數 |
|---|---|---|---|---|
| 1 改姿勢（持劍手不動、另一手揮手） | `gameart.py pose-edit run --image A.png --custom "the hand on the right side of the image, currently resting on the hip, is raised high with an open palm waving, while the hand on the left side of the image keeps gripping the sword hilt on the shoulder exactly as before" --keep-extra "…sword… held on the shoulder…" --avoid "a second sword, missing sword hilt, both hands raised" --seeds 7,21,99,3,42,123` | 6 個，挑 21、99、3 | 167 秒（6 張，約 28 秒／張） | 6/6 持劍手仍握劍、揮的是另一隻手；其中 3/6 手套顏色與原圖一致（另 3 張手套變灰或黑），挑出的 3 張持劍手都是原本的棕色手套 |
| 2 手掌朝鏡頭 | 同上，`--custom` 改為「右側那隻手舉到頭高、掌心朝鏡頭、手指朝上，左側那隻手繼續握劍」 | 6 個，挑 7、42、123 | 166 秒（6 張） | 4/6 正確（seed 7、99、42、123）；seed 21、3 兩隻手都舉起來，握柄掉了 |
| 3 局部遮罩（劍刃材質：冰晶→深色鋼） | `gameart.py sam`（圈出劍身，沿用 v1 的候選 #02，向外擴 12 像素）→ 整張依提示重畫 → `gameart.py edit composite` 只貼回遮罩內 | 7（另試 21、99，挑 7） | sam 31 秒＋重畫 29 秒 | 遮罩外 953,588 像素：貼回前 953,570 個被改，貼回後 **0** 個；範圍內 58,123／58,124 個像素改變 |
| 4 影片物件替換（劍刃換深色鋼） | `run video/sam3/track-text --set track_text="giant blade"` → `run video/wan-vace/inpaint-reference`（參考圖＝上一個 Demo 裁出的深色鋼劍刃、`grow=16`） | 7（另試 21，挑 7） | sam3 約 15 秒＋VACE 86 秒（49 幀、24fps） | 49 幀都換成深色鋼劍並跟著動作；遮罩外（遮罩外擴 16 像素以外）平均差異 1.39／255，每幀最多約 1.2 萬個像素（約 3.8%）差異超過 8 個色階 |

檔案：`demo1_pose_edit_wave_pick3.jpg`、`demo1_all6.jpg`、`demo2_palm_pick3.jpg`、`demo2_all6.jpg`、`demo3_blade_material.jpg`（圈選、整張重畫、貼回、貼回前後差異圖）、`demo4_strip.jpg`、`demo4_before_after.mp4`（H.264，左原片右結果）、`demo4_before_after.gif`、`demo4_reference.jpg`、`data/`。

## 要標註的地方

- 說「左手／右手」時模型以「畫面左右」理解；第一次用「左手」揮手舉起的是持劍手、握柄消失（6 張全錯），改成「畫面右側那隻手」才對，已在指令裡這樣寫。
- Demo 3 的合成貼回在劍刃邊緣留下一圈很淡的灰暈（新劍比原遮罩略小）。整張重畫的輸出尺寸是 832×1232（原圖 1216），先縮回原尺寸才能比對。
- Demo 4 遮罩外「逐幀完全不變」沒有達到嚴格 0（原因還沒查清，可能是來源 mp4 解碼差異），簡報請寫「大致不變（平均差 1.39/255）」。
- 單一素材、單一次執行；時間含模型載入。
