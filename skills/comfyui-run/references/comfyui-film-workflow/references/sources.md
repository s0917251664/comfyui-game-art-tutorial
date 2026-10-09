# 研究來源與本地化取捨

查閱日期：2026-10-03。GitHub stars 為當日頁面的約數，用於研究排序，不是可靠性證據。下表只記分鏡／長片製作方法的研究參考；其來源程式碼或技能全文沒有下載、安裝或移植。配音及唇形同步候選的獨立 runtime／模型下載狀態另列於下方，不屬於分鏡研究表，也不代表能力驗收通過。

| 官方來源 | 關注度 | 參考部分 | 轉成我們的流程 |
|---|---|---|---|
| [OpenMontage](https://github.com/calesthio/OpenMontage) | 約 62.5k stars | 研究、劇本、場景計畫、素材、編輯與合成的階段區分 | 劇情節拍、鏡頭計畫、逐鏡產出與可續作記錄；沿用本機 task，沒有接入它的雲端 provider 或渲染器 |
| [Storyboarder](https://github.com/wonderunit/storyboarder) | 約 3.9k stars | 快速粗分鏡、構圖輔助與鏡頭時間預視 | 先辨識站位和事件，再精修；文字表／視覺分鏡／實際 animatic 分開記錄 |
| [SkyReels-V2](https://github.com/SkyworkAI/SkyReels-V2) | 約 7.6k stars | 長影片延伸、歷史影格重疊及起訖畫面控制 | 研究對照：生成較長連續畫面不等於完整多鏡敘事。未接入本技能，不承諾本機可跑 |
| [LongLive](https://github.com/NVlabs/LongLive) | 約 2.6k stars | 長影片生成基礎設施 | 研究候選，沒有採用其模型或執行器；不能從專案示範推定現有產線能力 |

OpenMontage 同時列本機與付費雲端 provider；開源專案不代表每種示範製作都免費。本專案目前只用本機免費模型。本技能自行撰寫製作欄位與執行路由，不沿用外部專案的特殊 schema 或把它們宣稱為本地相容。

代表鏡頭先行、既有技術契約、人工內容接受、固定 task 及重做邊界是本專案的本地化決策。新增模型、工具或 provider 必須另走 `comfyui-new-tool-checklist`；本次只有編排文件，不增加生成能力。

## 配音與唇形同步工具來源

以下是 `film_audio.py` 周邊獨立本機工具所用來源及安裝／驗證界線；它們不是上表的分鏡流程依據：

| 官方來源 | 本機使用與狀態 |
|---|---|
| [Qwen3-TTS 原始碼](https://github.com/QwenLM/Qwen3-TTS) 與 [1.7B CustomVoice 模型](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice) | `qwen-tts` runtime 與模型在隔離環境下載；Serena、Uncle_Fu TTS 及有聲 Animatic/dub 已有技術 smoke pass。輸出仍是 candidate，尚未聽驗聲音品質。 |
| [Piper（Open Home Foundation）](https://github.com/OHF-Voice/piper1-gpl) | Piper 1.8.0 runtime 與 `zh_CN-huayan-medium` 模型隔離安裝；產生 3.970625 秒 WAV 的技術 smoke pass。聲音內容仍待人工聽驗。 |
| [MuseTalk](https://github.com/TMElyralab/MuseTalk) | 官方原始碼與模型已隔離下載。`film_lipsync.py` 固定 helper 已通過第二輪技術契約 smoke；嘴型自然度未驗收，不能推論騎士或劇情素材可接受。限制與技術記錄見 [lipsync-tools.md](lipsync-tools.md)。 |

這些隔離 runtime 和素材支援已列出的有限 helper；技術 pass 不能擴大解讀為聲音或嘴型自然度通過、作品完成，或對遠景／多臉／任意角色普遍適用。
