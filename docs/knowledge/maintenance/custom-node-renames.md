---
type: maintenance
status: current
---
# custom node 改名紀錄

2026-10-08（PR 2.5，[D9](../decisions/2026-10-07-phase2-template-runner.md)）起，repo 自己的 ComfyUI custom node 改用 `GameArt` 前綴、分類 `GameArt/Video`。當時舊名稱留作隱藏別名。2026-10-08（PR 8.2，[退場決定](../decisions/2026-10-08-node-alias-exit.md)）起，別名已從程式刪除。這一頁是 repo 裡唯一還寫出舊 class 名稱的說明；`tests/test_neutral_wording.py` 會擋其他地方出現。

## 名稱對照

| 新 class 名稱 | 舊 class 名稱（已移除） | 套件 | 新顯示名稱 |
|---|---|---|---|
| `GameArtVideoLayers` | `SteveVideoLayers` | `comfyui-video-layers` | GameArt · SAM Video Masks / Ordered Layers |
| `GameArtLoadFaceSwapVideo` | `SteveLoadFaceSwapVideo` | `comfyui-face-swap-video` | GameArt · Read Video and Face Reference |
| `GameArtReActorVideo` | `SteveReActorVideo` | `comfyui-face-swap-video` | GameArt · ReActor Video + Audio Output |

| 項目 | 新 | 舊（已移除） |
|---|---|---|
| 分類 | `GameArt/Video` | `Steve/Video` |
| 換臉 socket 型別 | `GAMEART_FACE_SWAP_SOURCE` | `STEVE_FACE_SWAP_SOURCE` |

## 現在的行為

- `NODE_CLASS_MAPPINGS` 只登記新名稱。舊名稱不再是子類別，也沒有 `DEPRECATED` 別名。
- repo 的 client 本來就只送新名稱：`face_swap.py` 的 API graph 與輸出的 UI workflow、`video_layers.py` 的 graph 都用新名稱。
- preflight 只接受新名稱。live `/object_info` 沒有新名稱時，就是缺少節點（部署或重啟後才會出現），不會再把「只有舊名稱」解讀成要重啟。
- 已存、仍使用舊 class 名稱的 UI workflow，要等下面「部署後要做的事」做完（第 8.4、queue 為空、重啟）之後，開啟時才會顯示缺少節點。在那之前，正在跑的 ComfyUI 仍是舊程式，不會因為 repo 已刪別名就顯示缺少節點。ComfyUI 不會自動換成新節點。要繼續用，請在 UI 裡把節點換成上表的新節點後另存。
- 沒有 `_meta` 的舊 API prompt 只當紀錄，不能直接重送。第 8.4 部署並重啟之後，重送預期得到 HTTP 400（缺少節點），而不是 HTTP 500。

## 這台 Windows 機器上還沒遷移的檔

- `<ComfyUI>/user/default/workflows/Ch8_影片換臉_Server.json`：整份就是換臉的兩個舊節點（讀取 1 個、ReActor 1 個）和一條舊 socket 連線。agent 不改這份檔。請使用者在 UI 換成新節點後另存。
- Video Layers 的已存 UI workflow：這次掃描是 0 份。
- 本機 `output/`（不進版控）有 21 份改名前的 API prompt 仍是舊名稱，而且都沒有 `_meta`：換臉 7 份、Video Layers 14 份。只當紀錄。
- **Mac 還沒掃。** 同一套唯讀掃描要在 Mac 的 `<ComfyUI>/user/**/workflows/**/*.json` 再做一次；有用到舊名稱的 workflow 同樣由使用者在 UI 遷移。

## 部署後要做的事

1. `gameart.py deploy --yes`（會提示 custom_nodes 有變更、要重啟），再跑 `gameart.py verify-install`。部署排在第 8.4 階段，而且要等 queue 為空。
2. 在 queue 為空時重啟 ComfyUI。重啟之後 schema 只剩新名稱，舊名稱從 schema 消失，已存的舊 workflow 開啟時才顯示缺少節點。
3. 依上一節遷移 `Ch8_影片換臉_Server.json`。

## 不受影響的部分

- `templates/` 的固定 graph（Wan Animate、SCAIL-2、SAM3、VACE）和圖片 golden fixtures 都沒有用到這些節點，所以沒有改 graph、版本或 hash。
- 改名前的實測紀錄裡的節點名稱已改寫成新名稱；當時實際送出的是對照表裡的舊名稱。
- 文件裡以 `output/*-kabuto-upper-body/`、`output/*-kabuto-face-swap/`、`output/*-kabuto-wan-animate/` 標註的本機證據，實際資料夾名稱是改名前建立的 `steve-kabuto-upper-body` 等（在 ignored `output/`，不進版控，也沒有改名）。
