---
name: comfyui-install
description: 在新機器上依硬體與既有狀態安裝、部署 ComfyUI 遊戲美術產線；遇到模型和版本時沿用核准基準，不自行升級。
---

# ComfyUI 產線安裝

當使用者明確要求在新機器設置 ComfyUI 產線，或已選定需本機 CLI 的 ComfyUI 路線且其依賴缺失時使用。單純缺少 `local_config.json` 不構成安裝意圖；尚未選路線先用 `skills/game-art-initialize/SKILL.md` 整理需求與盤點。明確 server URL 的直接 API 方式只由支援該方式的 executor 按自身 gate 使用，不可一概導向安裝，也不因此略過既有 loopback、profile、路徑或模型限制。共用需求整理、平台原生圖片工具及各自獨立的本機圖片檔案操作不因缺此檔而觸發安裝。這是一份目標清單，不是固定腳本：先判斷各項在這台機器是否已成立，再選合適方法補足，保留使用者既有版本與設定意圖。

開始操作前，從[總工具庫](../../docs/knowledge/TOOLS.md)確認涵蓋的能力，再讀[安裝知識索引](../../docs/knowledge/installation/README.md)，並依本次範圍讀取：

- [完整安裝目標與檢查流程](../../docs/knowledge/installation/install-guide.md)
- [模型家族、來源與容量](../../docs/knowledge/installation/models-and-sources.md)
- [LoRA 訓練工具（僅使用者要訓練時）](../../docs/knowledge/installation/lora-training.md)
- [`docs/tested-versions.md`](../../docs/tested-versions.md) 的實際版本／hash 捕捉狀態
- 本機圖片合成／診斷／參數 sweep 的部署契約：按需讀取[edit-tools.md](../../docs/knowledge/art/edit-tools.md)
- 物件／平面素材 Pillow 組裝 helper 的部署契約：按需讀取[object-design-workflows.md](../../docs/knowledge/art/object-design-workflows.md)
- ComfyUI server-side ReActor face-swap nodes/client package 的 pins、依賴、部署與 live schema preflight：按需讀取[local-tool.md](../../skills/comfyui-face-swap-workflow/references/local-tool.md)；部署 shared package 至 `tools/` 及 `custom_nodes/comfyui-face-swap-video/`，client 沿用 `generate.py` facade/package；路徑讀 `local_config.json`，不建新的影片 backend/task。Smoke-v1/full-v2 技術候選完整解碼但含 warning，內容仍待人工驗收。
- ComfyUI server-side Video Layers SAM／layer 工具的可重建檔案、固定 revision、runtime pins 與 preflight：只有使用者要在另一台機器部署／修復時，按需讀取[技能 reference](../../skills/comfyui-video-layers/references/local-tool.md)；先檢查既有 ComfyUI runtime 和 SAM cache，再依 client/package 雙部署契約同步檔案。這次本機已有 cache，無套件或模型下載；不要把本機 gate pins 當成所有平台安裝要求，也不要自動安裝套件。缺 cache 時須先說明容量／平台條件，依使用者授權的安裝範圍處理。

部署 repo 工具到 ComfyUI 一律用 `python tools_src/gameart.py deploy`（先看 dry run 計畫，確認後 `--yes`），不要手動複製檔案；細節見 install-guide 步驟 10。

在任何模型或套件下載前，先說明所選能力需要的磁碟空間並確認可用空間足夠。模型選擇以已核准設定檔和 tested-version manifest 為準；安裝時看到較新模型，不代表要評估或替換它。不同平台的 smoke test 必須在該機器實際完成，離線部署檢查不等於生成驗證。

Wan Animate 安裝與歷史測試紀錄見[知識庫頁面](../../docs/knowledge/video/wan-animate-install.md)；日常操作改依[專用技能](../comfyui-wan-animate/SKILL.md)。它是獨立的固定 template 路線（`gameart.py run`），未接入 `generate.py` task/backend，也不由 H3/Wan 5B detector 判定。
