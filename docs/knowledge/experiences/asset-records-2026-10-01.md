---
type: experience
date: 2026-10-01
status: historical
withdrawn: true
---
# 圖片結果 manifest 與已撤回資產庫 smoke test（歷史）

## 適用範圍

XU-Nano-PC；ComfyUI v0.34.0，既有本機安裝環境。這是 2026-10-01 Steve 撤回 SQLite 資產庫方案之前的歷史測試紀錄。它描述當時的 opt-in manifest 與短暫 SQLite 試作，不代表目前支援此工具或該版本數字仍適用；圖片內容也未通過 Steve 驗收。

## 執行與證據

- 撤回前程式版本：157 tests 全通過、無 skip；包含 PyAV 18.1 的環境。當時 portable verifier 19 pass / 0 fail。這些是撤回前歷史數字，不是目前結果。五個實機 manifest 對應 PNG 當時經 validator 重讀，hash、尺寸與 alpha 均相符。
- 部署：11 個 `.py`/`.json` 部署檔案 SHA-256 完全一致。
- 向後相容：concept seed 73101、512×512，未提供新旗標的舊命令與提供 `--result-json` 的新命令，PNG bytes 與 decoded pixels 完全相同。兩次在同一環境送出相同 graph，可命中 ComfyUI 快取（第二次少於 2 秒）；此結果證明新旗標沒有改變 graph／輸出，不是獨立重採樣確定性或跨 GPU 保證。
- 其他 task：concept + remove-bg 產 RGBA 且含透明像素；layer_split 輸出 PNG/alpha、輸入角色與 hash 都通過。
- 撤回前資產紀錄試作：曾寫入一筆 `smoke-potion/v1` candidate，從未 accepted；其圖片、manifest hash、seed、profile、時間與待驗收理由已遷移至 [smoke-potion 素材頁](../assets/smoke-potion.md)。
- 其他整合檢查：manifest 路徑 no-clobber 以 exit 1 拒絕覆寫；送出前後 ComfyUI history 都是 5 筆，沒有額外排程。layer_split RGBA alpha 範圍為 [0,255]，保留區 RGB 與原圖一致。
- FLUX.2 hook：`flux2_concept` 512×512、seed 73101，manifest 中 backend 是 `flux2`、profile 欄位皆為 null、graph seed 是 `noise_seed`，technical pass 且 content pending。repo 證據：`output/agent_refactor_smoke_20261001/flux2.json`。這個 prompt 比 SDXL smoke prompt 短，畫面單瓶綠液；不同 prompt 不是公平模型比較，也不改變 FLUX.2 維持 PoC 的決策。
- FLUX.2 edit hook：`flux2_edit` 從 512×512 輸入產生 1024×1024；manifest 記錄 input role `image`／hash、base UNET，technical pass 且 content pending。repo 證據：`output/agent_refactor_smoke_20261001/flux2_edit.json`。這驗證新旗標能記錄 FLUX.2 edit graph，沒有改動原有輸出尺寸策略，也不構成品質驗收。
- 本機實測資料：repo `output/agent_refactor_smoke_20261001/{concept.json,transparent.json,layer.json}`。撤回前曾使用的 SQLite smoke 檔案僅為歷史來源，素材候選已轉記至 Markdown。

## 人工內容驗收觀察

雖然 PNG technical validation 通過，concept 提示 single bottle 卻生成多瓶排列；去背結果仍有大片灰底／陰影。這個結果證明技術 manifest 不可替代逐項看圖；對使用者要求的數量及真實透明背景仍須人工驗收。此樣本不支持對其他 prompt、模型或平台的泛化結論。

## 限制

第一次執行使用預設 output 位置，sandbox 不允許寫 workspace 外路徑；改用既有 `--output-dir` 後成功。這是環境寫入邊界，不是 CLI defect。
