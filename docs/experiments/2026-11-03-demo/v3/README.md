---
type: demo-record
status: candidate
date: 2026-11-03
---
# Demo v3：沒動的地方與原圖完全一樣（Windows RTX 4080，騎士圖 A.png，不含 Skye）

主軸：**只有被指定要改的地方會變，其餘像素與原圖逐一相同**。結果是候選，目視判斷（R1）。

## Demo 1 改姿勢（揮手，持劍手不動）與 Demo 2 手掌朝鏡頭
做法：`gameart.py pose-edit run` 出圖 → 把候選整張以仿射對位（ECC）對齊原圖 → 只在「右側手臂＋肩甲上緣＋披風上緣」這塊區域貼回候選（只取候選與原圖有人物內容的像素，區域外擴 15 像素、邊緣羽化 5 像素），顏色用區域外一圈的平均／標準差對齊原圖 → 其餘全部是原圖。
- 圖：`demo1_pose_edit_wave_pick3.jpg`、`demo2_palm_to_camera_pick3.jpg`（上排原圖＋3 個候選，下排與原圖的差異熱圖，黑＝完全相同）。
- 數字（`data/demo12_numbers.json`）：貼回區域約 11–12.6 萬像素（約 11–12%）；其外面 88.6–90.1 萬像素，**變動 0 個**。羽化帶在貼回區域內。
- 張數：Demo 1、Demo 2 各產 24 張候選（seed 5–300，指令見下），依「對位後貼回區域內人物內容差異」排序後，目視檢查前 10 名，挑 3 張；挑出的 3 張都是正確的手、持劍手仍握柄、手套顏色與原圖一致（棕色）。其餘沒有逐張評正確率（Demo 1 前 10 名裡有 1 張手沒舉起來；Demo 2 的 24 張中 v2 已知 2 張兩手都舉）。
- 指令：`pose-edit run --image A.png --custom "the hand on the right side of the image, currently resting on the hip, is raised high with an open palm waving, while the hand on the left side of the image keeps gripping the sword hilt on the shoulder exactly as before" --keep-extra "…" --avoid "a second sword, missing sword hilt, both hands raised" --seeds …`（Demo 2 改為「raised to head height with the open palm facing straight toward the camera, fingers pointing up」）。約 28 秒／張。
- 限制：貼回區域內的肩甲、手臂、披風上緣是候選的版本，與原圖不完全相同（肩甲多一條線、手臂護甲略不同），只是外觀接近；Demo 1 候選 1 的手肘下方多一段護手。pose-edit 重畫全身，身體比例與原圖不同的候選不能用貼回（會看到整個肩部變形），已被排掉。

## Demo 3 局部遮罩（劍刃冰晶→深色鋼）
改善接縫：遮罩只取劍刃本身；外擴 20 像素只在「背景」上取（不碰頭髮、臉等人物像素）；殘留的舊劍刃淡青邊與細線併入遮罩；重畫圖先對位再貼回，背景色調對齊原圖；只在背景側羽化。結果：貼回範圍外 948,065 個像素，變動 **0**。圖：`demo3_blade_material.jpg`、`demo3_seam_zoom.jpg`（v2 與 v3 接縫放大對照）。仍有極淡的一條舊輪廓細線在劍刃上緣。

## Demo 4 影片物件替換
不再用 VACE 逐幀重畫（會抖），改成「第一幀的新劍刃（Demo 3 的結果）依 SAM3 追蹤遮罩估計的每幀仿射變換貼到每一幀」，舊劍刃先用背景修補抹掉，頭髮在劍前方。sam3 約 15 秒，其餘本機運算約 1 分鐘。劍刃外 30 像素以外 49 幀變動像素 **0**；劍刃外觀漂移（扣掉運動後與第 1 幀的平均差）：來源片 26.2、VACE 版 48.0、v3 **14.4**；「相鄰幀平均差」不降（來源 27.3、VACE 30.5、v3 32.5，被劍本身的運動主導，不引用）。檔案：`demo4_before_after.mp4`（H.264，左原片右結果）、`.gif`、`demo4_strip.jpg`、`data/demo4_metrics.json`。第 48 幀劍尖有些糊。

## 通用
單一素材、單一次執行；時間含模型載入。沒有螢幕錄影工具，以對照圖、GIF、mp4 代替。
