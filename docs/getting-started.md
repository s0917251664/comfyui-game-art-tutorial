# 新手上手：任何電腦、任何 AI 代理都適用

這份是給不寫程式的同事看的。你只需要做兩件事：**把專案資料夾交給你的 AI 代理，然後用中文說你想做什麼。** 指令、路徑與環境判斷由代理負責。

## 1. 先確認你要走哪條路

| 你想做的事 | 需要準備什麼 |
|---|---|
| 整理需求、寫 brief、決定驗收條件 | 什麼都不用裝 |
| 用 AI 平台內建的生圖／改圖功能 | 只要該平台有圖片工具 |
| 用本機 ComfyUI 生成圖片或影片 | 本機要有 ComfyUI、模型、Python；代理會先檢查，缺什麼再告訴你 |
| 裁切、去背、合成等圖片後製 | 本機要有 Python 與 Pillow 等套件 |

不確定時，先什麼都不裝，直接跟代理說需求。**沒有 `local_config.json` 不代表要安裝**，代理不該因此逼你安裝。

## 2. 讓代理讀到專案規則

所有代理都從同一份規則出發：[`AGENTS.md`](../AGENTS.md)。各工具的入口檔只是指到它，不另寫一套：

| 代理／工具 | 自動讀取的檔案 | 你要做的事 |
|---|---|---|
| Claude Code | `CLAUDE.md` → `AGENTS.md` | 在專案資料夾啟動即可 |
| Codex、其他支援 AGENTS.md 的工具 | `AGENTS.md` | 在專案資料夾啟動即可 |
| Gemini CLI | `GEMINI.md` → `AGENTS.md` | 在專案資料夾啟動即可 |
| GitHub Copilot | `.github/copilot-instructions.md` | 開啟專案資料夾 |
| Cursor | `.cursor/rules/game-art.mdc` | 開啟專案資料夾 |
| 其他／網頁版聊天 | 不會自動讀 | 第一句話貼上：「請先讀 `AGENTS.md`，再依我的需求選技能」 |

技能放在 [`skills/`](../skills/README.md)，每個技能是 `skills/<名稱>/SKILL.md`。工具不會自動載入技能時，`AGENTS.md` 的路由表會告訴代理該讀哪一個檔。

## 3. 作業系統差異（代理會處理，這裡只說明原因）

| | Windows | macOS | Linux |
|---|---|---|---|
| Python 指令 | `python`（或 `py`） | `python3` | `python3` |
| 路徑 | `C:\Users\...`，文件裡的 `/` 也可用 | `/Users/...` | `/home/...` |
| 圖片生成加速 | 多為 NVIDIA（CUDA） | Apple 晶片（MPS） | 視顯卡而定 |
| 新增 `.ps1` 腳本 | 須帶 BOM 的 UTF-8 | 不適用 | 不適用 |

- 文件裡寫 `python tools_src/gameart.py ...` 時，macOS／Linux 請讀成 `python3`；要跑 ComfyUI 路線時，通常用 ComfyUI 自己那份 Python（`local_config.json` 的 `python_exe`）。
- 路徑與機器設定都記在本機的 `local_config.json` 與三份能力快照，**不要從別台電腦複製**，換機就重新偵測。這些檔案不進版控，細節見[已驗證版本](tested-versions.md)的「跨設備重建」。
- 檔案換行一律保持 repo 原樣（見 `.gitattributes`），Windows 不要讓 Git 自動轉換 template 與驗證檔。

## 4. 第一次使用的檢查流程

請代理依序做，每一步只回報結果：

1. 讀 `AGENTS.md`，說明它理解的路線分工。
2. 問你想做什麼，並說明這次會走哪條路線、需要什麼。
3. 只有走本機路線時才跑 `python tools_src/gameart.py doctor`（唯讀）檢查環境；缺項目先告訴你，**不自動下載或安裝**。
4. 生成前先預檢；生成後由你決定結果能不能用。

## 5. 常見問題

- **代理說找不到 `local_config.json`**：只有本機路線才需要。想走平台工具或只整理需求，直接說「不要安裝」。
- **代理想自己下載模型或裝節點**：應先問你；沒有問就請它停下，改走[安裝指南](knowledge/installation/install-guide.md)的確認流程。
- **換了電腦或顯卡**：請代理重新跑 `doctor --refresh`，不要沿用舊快照。
- **不知道該查哪裡**：[知識庫入口](knowledge/INDEX.md)、[工具能力索引](knowledge/TOOLS.md)。
