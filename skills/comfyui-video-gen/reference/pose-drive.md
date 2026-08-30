# `pose_drive`

對應靜態 `character_action`:角色靜幀說「這是誰」,動作參考影片說「這段怎麼動」。不是 `img2video`(那張圖當第一幀自己演),也不是 `character_video`(文字賭新動作)。

哪個 `--backend` 接得上,見 `backends.md`。CLI 不要寫模型檔名。預設 `h3`;只要快、可接受無聲且臉可以漂,才 `--backend wan`。

## 固定輸入

- `--image`:角色靜幀。**姿勢/朝向必須接近 `--motion-ref` 第一幀**,跟靜態 `character_action` 一樣
- `--motion-ref`:動作參考影片(mp4)
- `--control-type`:預設 `pose`(骨架)。肢體表演用 pose;輪廓清楚的剪影/特效用 `canny`;空間前後景用 `depth`
- 時長 2~6 秒。參考影片比較短時,超出的幀控制會變弱

沒有接近的靜幀時:**先抽動作片第一幀當角色圖**,或先走圖片產線 `character_action` 擺成那個起點姿勢。不要拿站姿棚拍去套走路片。

## 已實測(2026-08-27,這台 RTX 4080 16GB,不要自動播成品)

**對的綁法:**動作片第一幀當 `--image`,`character_video_h3_00001_.mp4` 當 `--motion-ref`,`pose`,2 秒,seed 42。同一組輸入,預設 h3 跟 `--backend wan` 對打:

| | 預設 h3(`00004`) | wan(`00003`) |
|---|---|---|
| 牆鐘 | 154.6 秒 | 94.4 秒 |
| 輸出 | 512×768、56 幀、2.33 秒、H.264 + AAC 立體聲 | 512×768、49 幀、2.04 秒、H.264 無聲 |
| 檔案 | `output/pose_drive_00004_.mp4` | `output/pose_drive_00003_.mp4` |
| 首幀 vs 角色靜幀平均像素差 | 4.1 | 4.3 |
| 畫面 | **一個人**在倉庫走向鏡頭,背心/步槍/馬尾對得上 | 同左,也是一個人 |
| 中後段臉 | 還是同一人(末幀走近鏡頭,細節變了但身份認得出) | 中段開始漂、末幀已經換臉,背心/槍套也糊掉 |

抽幀:`pose_drive_00004_frames/`(56 png)、`pose_drive_00003_frames/`(49 png)。沒有自動播放。

**跨角色(同一支走路片、兩個不同人):**先 `character_action --control-type pose` 把各自靜幀擺成走路起點,再 `pose_drive`。動作來源仍是 `character_video_h3_00001_.mp4`。

| | 銀甲騎士 | 紫袍法師 |
|---|---|---|
| 靜幀 | `output/_walk_knight.png` | `output/_walk_witch.png` |
| 牆鐘 | 208.8 秒 | 151.4 秒 |
| 輸出 | `output/pose_drive_00005_.mp4` | `output/pose_drive_00006_.mp4` |
| 規格 | 兩邊都是 512×768、56 幀、2.33 秒、H.264+AAC | |
| 畫面 | 金髮銀甲橘披風,倉庫走向鏡頭,全程一人 | 紫帽紅髮紫袍金杖,倉庫走向鏡頭,全程一人 |

首幀對靜幀像素差會偏高(靜幀是棚拍/插畫,輸出被動作片帶進倉庫),看的是身份不是構圖。抽幀 `pose_drive_00005_frames/`、`pose_drive_00006_frames/`。沒有自動播放。

h3 不是像素鎖臉,也不是真正的 ControlNet Union(ComfyUI 0.34.0 還沒那個節點);身份走角色靜幀參考、動作走預處理後的影片參考。比 wan Fun Control 穩臉,但比靜態 IPAdapter 鬆。

**錯的綁法(不要再當範例):**棚拍站姿持槍 `female_carbine_final.png` 去套同一支走路片 → `pose_drive_00001_.mp4` 雙人、`00002_.mp4`(canny)雖是單人但槍/場景亂。那不是 task 壞掉,是輸入姿勢對不上。

## 什麼時候不該用

- 只要這張過關靜幀原構圖動起來 → `img2video`
- 要新鏡頭、沒有動作影片 → `character_video`
- 主體別動只運鏡 → `camera_move`
- 靜態換姿勢、有一張 pose 圖 → 圖片產線 `character_action`
