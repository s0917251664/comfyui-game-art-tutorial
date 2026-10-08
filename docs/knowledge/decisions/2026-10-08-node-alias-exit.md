---
type: adr
status: accepted
date: 2026-10-08
---
# ADR：custom node 舊名稱直接移除（PR 8.1／8.2）

## 背景

PR 2.5（[D9](2026-10-07-phase2-template-runner.md)）把 repo 自己的 custom node 改成 `GameArt*`，舊 class 名稱和換臉的舊 socket 型別先留成隱藏別名。對照與拼法只寫在[改名紀錄](../maintenance/custom-node-renames.md)。[官方工具 ADR](2026-10-08-official-comfy-tooling.md) 第 5 點要求第 8 階段評估 ComfyUI core 的 Node Replacement API。使用者要求把第 8 階段做完，並授權決定退場方式。

環境：Windows、ComfyUI v0.34.0。Mac 尚未掃描。

## 決定

**採用直接移除（方案二），不採用 Node Replacement，也不再保留別名。** PR 8.2 已刪掉別名類別與舊名稱常數。preflight 只檢查新名稱；缺少新名稱就是缺少節點。

同時接受這些條件，不把它們當成阻擋：

1. 本機有 1 份 UI workflow 仍用舊名稱：`<ComfyUI>/user/default/workflows/Ch8_影片換臉_Server.json`（2 個節點、1 條連線）。agent 不改這份檔。使用者在 UI 換成新節點後另存。
2. Mac 的 `<ComfyUI>/user/**/workflows/` 還沒掃。有用到舊名稱時，同樣由使用者在 UI 遷移。
3. 本機 `output/` 有 21 份改名前的 API prompt（都沒有 `_meta`）。它們只當紀錄，不能直接重送。重送預期是 HTTP 400（缺少節點）。
4. 隔離實例上的 L6（確認 400 而不是 500）尚未執行。離線讀過程式：別名移除後，缺節點走 `validate_prompt` 的 missing node，不會進到會對缺 `_meta` 丟 `KeyError` 的 replacement。部署與重啟留到第 8.4，且 queue 必須為空。

## 為什麼不採用 Node Replacement

1. 別名還在 `NODE_CLASS_MAPPINGS` 時，前後端都不會替換。要換就得先刪別名，省不下遷移。
2. 本機那 21 份舊 API prompt 都沒有 `_meta`。replacement 會對這種節點 `KeyError`，`/prompt` 沒有接住，預期變成 HTTP 500。直接移除則是清楚的 400。
3. UI 端本來就要使用者按替換，而且前端不會改 link 上記錄的型別字串。這份 workflow 只有 2 個節點，手動換掉即可。
4. replacement 的 `old_node_id` 仍要把舊名稱寫進程式，無法清掉用詞掃描的例外，還依賴標成不穩定的 `comfy_api.latest`。

## 範圍

- 不改 `templates/` 與圖片 golden。那些 graph 沒用這些節點。
- 不在這一階段部署或重啟使用者的 ComfyUI。
- 不把舊 prompt 的 `class_type` 自動改寫。若以後要重送，在 client 端改寫，而不是加回別名。

## 來源

- 本機唯讀掃描與離線 replacement 檢查（本機證據：`output/verify-20261008-8.1/`）。
- ComfyUI v0.34.0：`app/node_replace_manager.py`、`server.py` 的 `/prompt`、`execution.py` 的 `validate_prompt`。
- https://docs.comfy.org/custom-nodes/backend/node-replacement.md
