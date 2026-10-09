---
type: guide
status: current
---
# 開始使用本專案：需求路線與初始化

初始化不是安裝的同義詞：先確定要完成的工作，再依實際路線確認依賴。除非使用者明確選定本機 ComfyUI，否則不推導出安裝意圖。尚未選工具時可以說：「可以先只用需求整理與平台圖片工具，不必安裝 ComfyUI 或 Python；需要本機功能時再補環境。」已選 ComfyUI 的專案沿用既有選擇，不重複詢問；缺能力時先說明具體缺口與候選路線。

## 路線

| 使用情境 | 入口與依賴 | 可執行範圍 |
|---|---|---|
| 整理圖片或特效需求、參考圖用途、修改與保留、驗收 | [game-art-brief](../../../skills/game-art-brief/SKILL.md)，無需生成 runtime 或 `local_config.json` | 交付可執行的 brief 與分階段規劃，不代表已生成 |
| 平台原生圖片生成或編修 | [platform-image-gen](../../../skills/platform-image-gen/SKILL.md)；依賴本次會話確有且 schema 有效的圖片工具，不依賴 repo、ComfyUI、Python | 只做工具明確支援的靜態圖片能力，不推論免費、付費權限、外部 API 或影片能力 |
| 本機 ComfyUI（task、template、recipe） | [comfyui-run](../../../skills/comfyui-run/SKILL.md)；需要含 PyAV／Pillow 的 Python（通常是 ComfyUI 的 `python_exe`）、可連線的 server、模型與 gate | 當前能力快照、live preflight 與實測允許的範圍；固定 graph 一律走 `gameart.py run`（[R2](../rules/fixed-graphs.md)） |
| 不經 ComfyUI 的本機工具 | [local-media-tools](../../../skills/local-media-tools/SKILL.md)；各工具列明自己的函式庫 | 不預設需要 ComfyUI server 或 GPU；手繪遮罩服務例外，需要 ComfyUI 網頁服務 |
| 安裝本機 ComfyUI 或補缺失依賴 | 使用者明確選定後讀 [comfyui-install](../../../skills/comfyui-install/SKILL.md) 與 [安裝指南](install-guide.md) | 只裝本次所選能力需要的項目 |

## 依賴分層

「使用 ComfyUI」不代表每個元件都要在 agent 端裝相同 runtime：

- 本機工具各依自己的契約，可能需要 Pillow、NumPy、PyAV、OpenCV 或專用依賴；不能因某工具使用 ComfyUI 的 Python 就推論所有路線也需要。
- 跑 template 需要 server 在線、所需節點與模型已裝、live preflight 通過；runner 的輸入輸出檢查需要 repo 與含 PyAV／Pillow 的 Python。
- 用 `generate.py` 時遵照 `local_config.json`、device／image／video 能力快照與 task gate。缺設定不自動猜機器路徑，也不等於立即安裝：先判斷使用者要的是配置既有 server、整理 brief，還是安裝。
- 部分 template（例如 Wan Animate）限定已記錄的本機 loopback server 與機器狀態。
- 平台原生圖片技能獨立於本機路線；平台當下無工具或 schema 不支援時保留 brief 與能力缺口，不悄悄切換路線。

已有本機 ComfyUI 路線時，盤點用 `gameart.py doctor`（唯讀）看三份機器快照是否缺少或過期；換機或環境變動才跑 `doctor --refresh`（只掃描，不下載）。

## 安裝前告知

提出安裝時，明確告知本次選擇的能力、依賴與估計磁碟空間，再依[安裝指南](install-guide.md)核實機器與空間。模型、套件與 custom node 是不同項目，按所選能力分開列；不宣稱安裝後自動可用。使用者只要求需求整理或平台圖片時，不以缺 `local_config.json` 為由要求安裝。

## 相關文件

- [安裝指南](install-guide.md)、[模型清單](models-and-sources.md)
- [Wan Animate 安裝紀錄](../video/wan-animate-install.md)
