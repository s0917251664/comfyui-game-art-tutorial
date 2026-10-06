---
type: guide
status: current
---
# 開始使用本專案：需求路線與環境初始化

本頁說明第一次使用者如何選擇工作方式。初始化不是安裝同義詞：先確定要完成的工作，再依實際路線確認依賴。除非使用者明確選定本機 ComfyUI，否則不從舊專案預設推導出安裝意圖。

## 路線

| 使用情境 | 入口與依賴 | 可執行範圍 |
|---|---|---|
| 整理圖片／特效需求、參考圖用途、修改與保留範圍、驗收方式 | `skills/game-art-workflow/SKILL.md`；不需生成 runtime 或 `local_config.json` | 交付可執行 brief／分階段規劃，不代表已生成 |
| 使用平台原生圖片生成或編修 | `skills/platform-image-gen/SKILL.md`；依賴本次會話實際提供且 schema 有效的圖片工具，不依賴此 repo、ComfyUI、Python 或本機設定 | 只做當下工具明確支援的靜態圖片能力；schema 不符時交付 brief。不得由此推論免費、付費權限、外部 API 或影片能力 |
| 使用本機既有 ComfyUI CLI | 圖片讀 `skills/comfyui-art-gen/SKILL.md`，影片讀 `skills/comfyui-video-gen/SKILL.md` 與 task 技能；需要各自 CLI 契約所列的 client/runtime、可連線 ComfyUI server、模型與 task gate。repo CLI 通常讀 `local_config.json`，先查既有配置 | 僅執行當前 capability、live preflight 與實測允許的 task |
| 透過明確 URL 使用既有 ComfyUI API | 需要使用者提供／指定的 server URL、該次連線授權，以及路線所需 server node、模型和 live schema；呼叫 agent 可透過 HTTP，不必因此安裝本機 Python。特定技能仍可要求更嚴格的 loopback／機器 gate | 僅限 API template 或既有 API client 支援的操作；不得推廣成所有機器工具都可遠端使用 |
| 安裝本機 ComfyUI 或缺失的特定本機工具 | 使用者明確選定該路線後讀 `skills/comfyui-install/SKILL.md` 和本頁的安裝文件；各工具按自身依賴核查 | 僅安裝本次所選能力所需項目；不把所有 helper、影片模型或選配模型當基本配備 |

尚未選工具時可告知：「可以先只使用需求整理與平台圖片技能，不必安裝 ComfyUI 或 Python；需要本機功能時再補環境。」若使用者已明確選 ComfyUI，沿用既有選擇，不重複詢問；若缺能力，先說明具體缺口及候選路線。

| 路線 | 典型依賴 | 下一步 |
|---|---|---|
| 需求 brief | 無生成 runtime | 整理需求和驗收條件 |
| 平台原生圖片 | 本次會話可用工具及有效 schema | 按平台技能執行或交付 brief |
| 直接 ComfyUI API | 僅限 executor 明確支援的 URL／連線方式、server 節點模型及 gate | 讀對應 API 技能並遵守 loopback／路徑限制 |
| 既有 ComfyUI CLI | 該 CLI 指定的 Python、設定、server 與 task 能力 | 讀圖片或影片 CLI 技能與 capability gate |
| 本機檔案處理 | 各 helper 個別列明的程式與函式庫 | 讀相符本機工具技能；不預設需要 ComfyUI server |

## ComfyUI 依賴分層

「使用 ComfyUI」不代表每個元件都要在 agent 端安裝相同 runtime：

- repo 內既有 CLI／helper 依各自契約可能需要 ComfyUI Python、Pillow、NumPy、PyAV、OpenCV 或其他專用依賴；查對應技能和安裝文件。不能因某 helper 使用 ComfyUI Python 就推論所有路線也需要。
- ComfyUI server API 操作需要 server 在線、所需節點／模型已裝，以及 live schema／模型 preflight 通過。若有明確 URL 且使用者授權該次連線，HTTP 呼叫端不必安裝本機 Python；server 端仍須滿足能力要求。
- 使用 repo `generate.py` 等既有 CLI 時，遵照 `local_config.json`、device/image/video capability 與 task gate。缺設定不自動猜測機器路徑，也不等同立即安裝；先判斷使用者要的是配置既有 server、整理 brief，還是安裝。
- Wan Animate 等技能可能限定已記錄的本機 loopback server、固定模板和機器狀態。提供一般 API URL 的規則不解除該技能自己的限制。
- 平台原生圖片技能獨立於本機路線；平台當下無工具或 schema 不支援時保留 brief 與能力缺口，不悄悄切換路線。

## 安裝前告知語

需要提出 ComfyUI 安裝時，明確告知本次選擇的能力、依賴與估計磁碟空間，再依 `install-guide.md` 核實機器與可用空間。模型、套件與 custom node 是不同項目，按選定能力列出，不宣稱安裝後自動可用；安裝與下載遵循使用者對該次工作的授權。使用者只要求需求整理或平台圖片時，不以缺 `local_config.json` 為由要求安裝。

## 技能庫邊界

本初始化入口及引用專案執行契約的技能依賴本 repo，不等於可獨立搬移的通用技能。共用需求與平台原生圖片技能依各自移植契約可攜；本初始化入口則引用本專案的技能、CLI 和知識頁。需要全域技能庫初始化時，產出獨立 stub 草稿，並清楚指回本 repo 的 canonical absolute path；全域安裝流程由使用者指定的全域 skill maintainer 處理。

`workflows/` 被 git 忽略，供本機 ComfyUI UI 檢視、除錯和維護；版本控管的 API templates 是程式／技能明確使用的執行契約，兩者用途不同。初始化不可假設乾淨 clone 已包含這些被忽略的 UI 檔；明確取得且符合執行契約的匯出檔仍可按對應技能使用。不能要求所有新 task 必須附 UI workflow JSON。

## 相關文件

- [ComfyUI 安裝目標與檢查流程](install-guide.md)
- [模型家族、來源與容量](models-and-sources.md)
- [Wan Animate 本機執行紀錄](../video/wan-animate-install.md)
