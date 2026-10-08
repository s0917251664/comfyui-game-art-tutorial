---
name: comfyui-wan-animate
description: 使用已安裝的 Wan2.2 Animate 或 SCAIL-2，透過固定 template 與 `gameart.py run` 做 Mix 原影片角色替換、Move 參考角色動作驅動、兩段延伸的較長片段、保留來源音訊、改輸出寬高，或用 SCAIL-2 做角色替換／動畫時使用；也用於查詢本機能力與驗收候選。獨立原生能力，技術 smoke 通過但內容仍 candidate，未接入 generate.py backend/task。
---

# Wan Animate

Wan Animate 是已安裝的獨立 ComfyUI 原生能力：Mix 將參考角色置入來源影片；Move 以來源動作驅動參考角色。固定 templates 涵蓋單段 17／33 幀、兩段延伸 61 幀、選用的來源音訊保留與可調寬高。SCAIL-2 是同一路線下的另一個模型（以 SAM3 彩色遮罩綁定角色），有自己的 templates 與[操作契約](references/scail2.md)。

所有執行都透過 template＋runner：`gameart.py run <template> --preflight` 檢查，`gameart.py run <template>` 實際執行（[R2](../../docs/knowledge/rules/fixed-graphs.md)）。runner 負責上傳、送出、輪詢、下載、輸出檢查與 `run.result.json`，agent 不要自己呼叫 ComfyUI HTTP 送 graph。不需要瀏覽器或 UI 操作；必要時可以在 ComfyUI UI 檢視／除錯 SAM 點位，但正式結果一律用 runner 產生。這條路線沒有 `generate.py` task/backend，也不能由 H3/Wan 5B 的 `video_capabilities.json` 推定可用。

安裝期 Mix／Move smoke 通過但曾出現身份漂移及 Move 幻覺吉他。2026-10-06 的 Mix17／Move17、Mix61（含音訊）、Move61 與直式 384×640 Move17 都已技術通過，2026-10-08 也用 runner 跑過 Move17；畫面仍有肩膀、手臂和手部變形，尚未美術驗收。不可宣稱 prompt 已解決身份漂移，也不可由已測尺寸推論其他尺寸穩定。先讀[安裝紀錄](../../docs/knowledge/video/wan-animate-install.md)與[操作契約及實測](references/comfyui-api.md)。

## 選 template

template 在 repo 頂層 `templates/video/wan-animate/<名稱>/`，下面以 id（例如 `video/wan-animate/mix`）稱呼。`python tools_src/gameart.py run show <id>` 會列出可填的 slot、option、模型 pin 與平台狀態。

- 一般角色替換／動作驅動，片長 ≤ 33 幀：`video/wan-animate/mix`／`video/wan-animate/move`。
- 需要 61 幀（約 3.8 秒）：`video/wan-animate/mix-extend`／`video/wan-animate/move-extend`。更長的片段沒有 template，停止並告知，不要臨場複製延伸節點。
- 要保留來源音訊：加 `--option keep_audio`。要改寬高：填 `width`／`height` slot（只實測過 384×384 與 384×640）。
- 使用者指定 SCAIL-2，或需要多角色／依顏色綁定身份的替換：讀 [scail2.md](references/scail2.md)，用 `video/wan-animate/scail2`／`scail2-extend`。不要因 Wan Animate 結果不佳就自動改跑 SCAIL-2，反之亦然。

## 每次工作流程

以下 `<py>` 是 `local_config.json` 的 `python_exe`（runner 要用它，因為輸入／輸出檢查需要 ComfyUI 環境裡的 PyAV 與 Pillow），在 repo 根目錄執行。

1. 讀本機 `local_config.json`，確認 `python_exe`、`comfyui_path`、`comfyui_url`，不要猜位置或換用其他服務。
2. 完成 brief：來源影片、角色 reference、Mix／Move 模式、mask 語義、身份錨點、prompt 及驗收條件。來源影片必須是 16 FPS CFR 的有界片段（單段 17／33 幀、延伸 61 幀），先用既有媒體工具切好。Mix 使用來源背景，要至少一個 positive point（以輸出寬高中心裁切後的座標表示）；Move 不給 points，背景依 reference／目標 brief 定義。預設不輸出音訊，在 brief 記錄 audio drop。
3. 把 slot 值寫進一份 UTF-8 的 `values.json`（例子見[操作契約](references/comfyui-api.md#執行步驟)），路徑用絕對路徑。
4. preflight：`<py> tools_src/gameart.py run <id> --values values.json --preflight`。結束碼 0 才繼續；1 表示被擋下（缺節點、模型、檔案大小不符、平台未驗證等），照訊息回報，不要自行下載模型或加 `--allow-unverified-platform`（後者要使用者確認）。每次都要重跑 live preflight，不要拿舊的 preflight 輸出或 video snapshot 代替。
5. 實際執行：`<py> tools_src/gameart.py run <id> --values values.json [--option keep_audio]`。runner 會先重跑 preflight、檢查輸入（FPS、CFR、幀數），再上傳、送出、等待完成、下載並檢查輸出（寬高、幀數、FPS、pts、音軌），抽 first／middle／last 關鍵幀，寫 `run.result.json`。
   - 結束碼 0：完成且技術檢查通過。
   - 結束碼 1：看 `run.result.json` 的 `failure.step` 與 `failure.error` 回報；有 `prompt_id` 就一起回報。逾時或中斷時 job 可能還在 ComfyUI 跑，runner 不會重送、不會全域 interrupt。不要自動重跑。
   - 結束碼 2：參數或設定錯誤，修正後再跑。
6. 人工檢視：打開 `keyframes/` 的三張圖與 `outputs/video/` 的影片，依 brief 逐項檢查；延伸段一定要看第 32／33 幀前後的接縫（runner 也會在 warnings 提醒）。依[測試紀錄模板](../../docs/knowledge/video/templates/animation-test-record.md)記錄結果。
7. 交給美術審核者：用 `<py> tools_src/gameart.py review list <run 資料夾>` 列出候選。只有使用者確認後才執行 `review accept|reject <輸出檔> --by <決定的人>`；agent 不可自行 accept。審核前一律是 candidate。

不得臨場另組或改接節點圖、繞過 runner 直接送 JSON、改模型 profiles 或假裝能力已接入 `generate.py`（[R2](../../docs/knowledge/rules/fixed-graphs.md)）。不覆寫舊候選（每次 run 都是新資料夾）、不因瑕疵自動重送。brief 與受控比較方式見[動畫 brief 模板](../../docs/knowledge/video/templates/animation-brief.md)及[評估筆記](../../docs/knowledge/video/animation-evaluation.md)。
