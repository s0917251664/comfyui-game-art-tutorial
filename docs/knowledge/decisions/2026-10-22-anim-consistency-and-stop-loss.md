---
type: adr
status: accepted
date: 2026-10-22
---
# ADR：新增 R4 動畫一致性 gate 與 R5 生成方法停損

## 決策

使用者（Steve）2026-10-22 核准把兩項經驗升格為跨路線正式規則：

- [R4 新動畫進遊戲前，配色與比例要對基準動畫量測通過](../rules/animation-consistency.md)
- [R5 生成方法停損：同一問題兩輪沒解，就換方法層級](../rules/method-stop-loss.md)

## 理由與證據

`skye-ice-hammer-game` 持槌拖錘跑一支 20 格循環花了約 3 天、約 25 次退件。主要成本來自：

- 顏色與比例的不一致，到交付後才由使用者試玩抓出；補量才發現其他動畫早已偏色、中途縮放。
- 在同一層級的方法上連續失敗仍繼續；有效的方法是使用者提出的。

逐項時間線、原因與修正做法見[持槌拖錘跑返工檢討](../experiences/armed-drag-run-rework-retro-2026-10.md)。

## 範圍與限制

- R4 的提醒門檻（比例 ±3%、區域 Lab 差約 6）是本次經驗值，只用來找要處理的地方，不能代替 [R1](../rules/candidate-review.md) 的美術驗收。
- 量測工具目前在該遊戲專案的 `tools/`，尚未做成本 repo 的通用工具；要做成通用工具時照[新增能力清單](../maintenance/new-capability-checklist.md)。
- R5 不放寬 [R2](../rules/fixed-graphs.md)：換到新的節點組合仍要先實驗；下載模型、安裝節點仍要先取得同意。
