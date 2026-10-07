---
type: index
status: current
---
# 執行規則（canonical）

每條跨路線的規則只在這裡完整寫一次。AGENTS.md、技能與其他知識頁只用一句話加連結引用，不重寫規則內容；要改規則時只改這裡，並在 [決策紀錄](../decisions/) 留下理由。

| 編號 | 規則 | 一句話 |
|---|---|---|
| R1 | [候選與美術驗收](candidate-review.md) | 所有輸出從 `candidate` 開始；技術通過不等於美術接受；只有美術審核者能決定 `accepted`／`rejected`。 |
| R2 | [只用已登記的固定流程](fixed-graphs.md) | 不為單次需求臨場組或改 ComfyUI graph；缺能力如實說明，新能力走新增能力清單。 |
| R3 | [角色動作的 Idle 錨定](idle-anchoring.md) | 角色動作第一幀用已驗收的 Idle 圖，只選會鎖首（尾）幀的 task。 |

各路線自己的操作契約（旗標、輸入、輸出格式）仍留在對應技能與 reference；這裡只放跨路線、需要一致遵守的原則。
