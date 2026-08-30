# `character_video`

對應靜態 `style_lock`:丟角色參考圖,文字說這個角色在做什麼,模型組**新鏡頭**。不是 `img2video`(那張圖當第一幀)。

哪個 `--backend` 接得上這個 task,見 `backends.md`。CLI 不要寫模型專用 prompt tag;實作層自己補。也不能接 SDXL 的 IPAdapter / `--style`。

## 鎖死的參數(不要臨場改)

- 時長 2~6 秒,畫布最長邊 768,20 steps
- 參考圖 1~9 張

## 已實測(2026-08-27,這台 RTX 4080 16GB,不要自動播成品)

`output/female_carbine_final.png` 當唯一 `--character-ref`,prompt 寫倉庫行走(不是棚拍 idle),`--duration 2 --seed 42`。

| | |
|---|---|
| 牆鐘 | 69.6 秒 |
| 輸出 | 512×768、56 幀、2.33 秒、24fps、H.264 + AAC 立體聲 |
| 檔案 | `output/character_video_h3_00001_.mp4` |
| 第一幀 vs 來源靜幀平均像素差 | ~89(構圖已換成倉庫,不是 I2V) |
| 身份 | 背心/卡其褲/馬尾/步槍下垂仍認得出是同一人 |

## 什麼時候不該用

- 就要「這張已經過關的靜幀活起來、構圖別動」→ `img2video`
- 還沒有角色靜幀 → 先走圖片產線 `style_lock` / `character_action` 出圖
- 要同一場下一鏡連戲 → `clip_extend`(吃上一鏡尾幀),不是再丟一張參考圖重賭身份
