---
type: maintenance
status: current
---
# custom node 改名紀錄

2026-10-08（PR 2.5，[D9](../decisions/2026-10-07-phase2-template-runner.md)）起，repo 自己的 ComfyUI custom node 改用 `GameArt` 前綴、分類 `GameArt/Video`；PR 8.2（[退場決定](../decisions/2026-10-08-node-alias-exit.md)）把舊名稱的隱藏別名從程式刪除。這一頁是 repo 裡唯一還寫出舊 class 名稱的說明；`tests/test_neutral_wording.py` 會擋其他地方出現。

| 新 class 名稱 | 舊 class 名稱（已移除） | 套件 | 新顯示名稱 |
|---|---|---|---|
| `GameArtVideoLayers` | `SteveVideoLayers` | `comfyui-video-layers` | GameArt · SAM Video Masks / Ordered Layers |

分類：新 `GameArt/Video`，舊 `Steve/Video`（已移除）。

## 現在的行為

- `NODE_CLASS_MAPPINGS` 只登記新名稱，沒有 `DEPRECATED` 別名；`video_layers.py` 的 graph 與 preflight 只認新名稱。live `/object_info` 沒有新名稱就是缺少節點（需要部署與重啟），不會再把「只有舊名稱」解讀成要重啟。
- 已存、仍用舊 class 名稱的 UI workflow，在部署並重啟 ComfyUI 之後開啟會顯示缺少節點；ComfyUI 不會自動換成新節點，要在 UI 裡換成新節點後另存。agent 不改使用者的 workflow 檔。
- 沒有 `_meta` 的舊 API prompt 只當紀錄，不能重送；部署並重啟後重送預期得到 HTTP 400（缺少節點）。

## 部署後要做的事

1. `gameart.py deploy --yes`（會提示 custom_nodes 有變更、要重啟），再跑 `gameart.py verify-install`。
2. queue 為空時重啟 ComfyUI；重啟之後 schema 只剩新名稱。
3. Mac 上若有使用舊名稱的已存 workflow，同樣由使用者在 UI 遷移（尚未掃描）。

## 不受影響的部分

- `templates/` 的固定 graph 與圖片 golden fixtures 沒有用到這些節點，沒有改 graph、版本或 hash。
- 文件中以 `output/*-kabuto-upper-body/` 標註的本機證據，實際資料夾名稱是改名前建立的 `steve-kabuto-upper-body`（在 ignored `output/`，不進版控，也沒有改名）。
