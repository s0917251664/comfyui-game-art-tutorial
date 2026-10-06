---
name: game-art-initialize
description: 協助第一次使用本專案的使用者開始遊戲美術工作，盤點需求與可用技能路線，並只在明確選定本機 ComfyUI 時規劃環境安裝。
---

# 遊戲美術專案初始化

適用於使用者要初始化、開始使用或了解本專案能做什麼。這是本 repo 專用入口，依賴 repo 內技能與知識文件；它不是可攜式通用技能。先辨認使用者已有的目標和偏好，避免把「開始使用」直接解讀成安裝 ComfyUI。

## 路由

- 使用者尚未選執行路線：先整理需求、盤點本專案技能；優先提出可直接開始的需求整理方式。清楚告知：「可以先只使用需求整理與平台圖片技能，不必安裝 ComfyUI 或 Python；需要本機功能時再補環境。」不可默認舊的 ComfyUI 路線並觸發安裝。
- 只整理需求／製作規劃：讀 `skills/game-art-workflow/SKILL.md`。平台原生圖片技能可在會話提供相符工具時直接使用，不需要 repo、本機 runtime 或 `local_config.json`。
- 使用者明確選平台圖片工具：讀 `skills/platform-image-gen/SKILL.md`，逐項核對當下工具 schema。工具目前可用、schema 有效且符合本案時才執行；否則交付 brief 與缺口。不得推定免費、付費權限、外部 API 可用或影片支援。
- 使用者明確選 ComfyUI：先按 task 路由到現有 executor，不能一概套用圖片 CLI 或強制要求本機 Python／設定：圖片既有 CLI 讀 `skills/comfyui-art-gen/SKILL.md`；現有影片 CLI 讀 `skills/comfyui-video-gen/SKILL.md`；Wan Animate 固定 API 讀 `skills/comfyui-wan-animate/SKILL.md`；影片換臉和 Video Layers 分別讀 `skills/comfyui-face-swap-workflow/SKILL.md`、`skills/comfyui-video-layers/SKILL.md`。遵照 executor 自己的 CLI／API、profile、loopback、路徑、模型與 task gate。只有 executor 明確支援的 API 方式，才可在明確 server URL 及本次授權下以 HTTP 呼叫；不臨場改用 API，也不因泛稱「ComfyUI」就新造 graph。既有專案已選路線時沿用已配置方式。
- 本機檔案處理與遮罩等 helper 是獨立路線，按任務讀 `skills/local-image-edit-tools/SKILL.md`、`skills/comfyui-object-design/SKILL.md` 或相符工具技能；逐項檢查其自身依賴，不由「使用 ComfyUI」推定需要 server、GPU 或 repo Python。
- 只有使用者明確要求安裝／初始化本機 ComfyUI，或明確選擇需本機安裝的既有 CLI／helper 且其自身依賴缺失時，才讀 `skills/comfyui-install/SKILL.md` 和安裝知識。安裝前遵照安裝流程說明容量與範圍。各工具依自己的契約判斷依賴；不得假設所有 ComfyUI 路線都需要相同 Python 或本機設定。

路線概念速查：需求 brief／平台圖片／支援的直接 ComfyUI API／既有本機 CLI／本機檔案處理，各自是不同執行方式。尚未選路線時採需求整理與盤點、不安裝；已有 ComfyUI 專案則沿用已選 executor，不重問引擎。能力不足時回報實際缺口，不靜默切換平台、外部付費服務或另一種工具。平台圖片能力不代表影片能力。

## 執行邊界

初始化只負責路由及本次需求所需的盤點；不因讀取本技能而生成、安裝、下載模型、建立本機設定或改寫 profile。只有使用者要求相關操作時，才沿用該執行技能的授權及 gate。已存在的 CLI、ComfyUI API 與本機 helper 各依其技能描述使用，不臨場發明新入口。

專案技能的維護與移植另由維護域文件負責；本技能只連結、不改寫該維護流程。`workflows/` 是 git 忽略的本機 UI／除錯參考素材；版本控管的 API templates 是執行契約的一部分，依其技能文件維護，兩者不可混為一談。
