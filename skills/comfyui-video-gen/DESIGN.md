# 影片產線設計稿（相容索引）

設計稿內容已移至 [canonical 影片設計稿](../../docs/knowledge/video/design.md)。以下保留原有標題與 heading anchors；點擊各段連結可到對應 vault heading。操作以 [影片技能](SKILL.md) 和 [影片知識總覽](../../docs/knowledge/video/README.md) 為準。

# 影片產線設計稿

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#影片產線設計稿)

## 0. 一句話定位

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#0-一句話定位)

## 1. 為什麼不能把影片當成「會動的 concept」

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#1-為什麼不能把影片當成會動的-concept)

## 2. 影視工程師會怎麼用 ComfyUI

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#2-影視工程師會怎麼用-comfyui)

## 3. 三個需求方向,加上漏掉的那些

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#3-三個需求方向加上漏掉的那些)

### 3.1 單純動畫特效

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#31-單純動畫特效)

### 3.2 有劇情的長片

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#32-有劇情的長片)

### 3.3 動態轉場

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#33-動態轉場)

### 3.4 使用者沒點名、但影視工程師會立刻補上的方向

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#34-使用者沒點名但影視工程師會立刻補上的方向)

## 4. 產線原則(沿用圖片,不另發明一套)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#4-產線原則沿用圖片不另發明一套)

## 5. 建議的 task 切法

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#5-建議的-task-切法)

### 5.1 `generate.py` 目前 task 與後續規劃

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#51-generatepy-目前-task-與後續規劃)

### 5.2 編導流程(skill 層,不是 generate.py task)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#52-編導流程skill-層不是-generatepy-task)

## 6. 模型選擇與歷史實測

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#6-模型選擇與歷史實測)

### 為什麼鎖定 2.2、不用已經出的 2.5(以及後面的 2.6/2.7/3.0)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#為什麼鎖定-22不用已經出的-25以及後面的-262730)

### 2026-08-26 本機開源 bake-off(這台 4080 16GB)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#2026-08-26-本機開源-bake-off這台-4080-16gb)

### 2026-08-26 第一次實測(832x480、同一張 `character_action_00026_.png`、同一句 idle prompt、seed 42、20 steps)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#2026-08-26-第一次實測832x480同一張-character_action_00026_png同一句-idle-promptseed-4220-steps)

## 7. 已知限制(目前實作與歷史實測)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#7-已知限制目前實作與歷史實測)

## 8. 分階段落地

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#8-分階段落地)

### 第 0 階段(歷史設計階段,2026-08-26)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#第-0-階段歷史設計階段2026-08-26)

### 第 1 階段:這台機器能跑出第一段影片(雙模型 bake-off,已完成)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#第-1-階段這台機器能跑出第一段影片雙模型-bake-off已完成)

### 第 2 階段:第一個穩定 task = `img2video`(已完成)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#第-2-階段第一個穩定-task-img2video已完成)

### 第 3 階段:`fx_loop` + 抽幀包裝(已完成)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#第-3-階段fx_loop-抽幀包裝已完成)

### 第 4 階段:轉場與運鏡(CLI 已完成，品質持續依 backend 實測)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#第-4-階段轉場與運鏡cli-已完成品質持續依-backend-實測)

### 第 5 階段:長片所需的最小連戲(CLI 已完成)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#第-5-階段長片所需的最小連戲cli-已完成)

### 第 6 階段以後(有明確需求才開)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#第-6-階段以後有明確需求才開)

## 9. 跟現有圖片產線怎麼接

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#9-跟現有圖片產線怎麼接)

## 10. 已拍板的產品決定(2026-08-26)

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#10-已拍板的產品決定2026-08-26)

## 11. 刻意沒做的決定

> Canonical section: [移至 knowledge vault](../../docs/knowledge/video/design.md#11-刻意沒做的決定)
