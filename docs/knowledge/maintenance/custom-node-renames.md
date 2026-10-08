---
type: maintenance
status: current
---
# custom node 改名與舊名稱別名

2026-10-08（PR 2.5，[D9](../decisions/2026-10-07-phase2-template-runner.md)）起，repo 自己的 ComfyUI custom node 改用 `GameArt` 前綴、分類 `GameArt/Video`。舊名稱只留作隱藏別名，讓已存的 workflow 和舊的 API graph 還能載入、執行。這一頁是 repo 裡唯一記錄舊名稱的說明文件；程式裡只有 `comfyui_*/contracts.py` 的 `LEGACY_*` 常數保留舊名稱，`tests/test_neutral_wording.py` 會擋其他地方出現。

## 名稱對照

| 新 class 名稱 | 舊 class 名稱（隱藏別名） | 套件 | 新顯示名稱 |
|---|---|---|---|
| `GameArtVideoLayers` | `SteveVideoLayers` | `comfyui-video-layers` | GameArt · SAM Video Masks / Ordered Layers |
| `GameArtLoadFaceSwapVideo` | `SteveLoadFaceSwapVideo` | `comfyui-face-swap-video` | GameArt · Read Video and Face Reference |
| `GameArtReActorVideo` | `SteveReActorVideo` | `comfyui-face-swap-video` | GameArt · ReActor Video + Audio Output |

| 項目 | 新 | 舊 |
|---|---|---|
| 分類 | `GameArt/Video` | `Steve/Video`（別名也改用新分類） |
| 換臉 socket 型別 | `GAMEART_FACE_SWAP_SOURCE` | `STEVE_FACE_SWAP_SOURCE`（只給舊名稱那一對用） |

## 別名怎麼運作

- 舊名稱仍登記在 `NODE_CLASS_MAPPINGS`，對應到新類別的子類別，行為完全相同（同一個 `execute`／`load`、同樣的輸入檢查）。
- 子類別設 `DEPRECATED = True`。ComfyUI v0.34.0 的 `/object_info` 會對它回報 `"deprecated": true`，前端預設把 deprecated 節點從搜尋與節點庫隱藏（設定「Show deprecated nodes in search」，`Comfy.Node.ShowDeprecated`，預設關閉），但已存 workflow 裡的這些節點照常載入、執行。
- 別名的顯示名稱是原名稱加上「(legacy node name)」，不含舊前綴。
- 換臉的舊名稱那一對保留舊 socket 型別：舊讀取節點輸出 `STEVE_FACE_SWAP_SOURCE`，舊 ReActor 節點也只接受這個型別，所以舊 workflow 的連線不會斷。新、舊節點不能混接（型別不同），要整組換。
- repo 的 client 一律送新名稱：`face_swap.py` 的 API graph 與輸出的 UI workflow、`video_layers.py` 的 graph 都用新名稱。
- preflight 只接受新名稱。live `/object_info` 只有舊名稱時，代表 custom node 已部署（preflight 先核對過檔案 hash）但 ComfyUI 還沒重啟、仍在跑部署前載入的程式，preflight 會直接要求重啟，不會退回舊名稱。Video Layers 的 server node 本來就會拒絕「載入的程式和磁碟上的不同」，退回舊名稱也跑不起來。

## 部署後要做的事

1. `gameart.py deploy --yes`（會提示 custom_nodes 有變更、要重啟），再跑 `gameart.py verify-install`。
2. 在 queue 為空時重啟 ComfyUI，新名稱才會出現在 `/object_info`。
3. 已存的 workflow 不用改，開啟時會用舊名稱別名。想換成新名稱時，在 UI 裡把節點換成新的 GameArt 節點後另存。

## 不受影響的部分

- `templates/` 的 8 份固定 graph（Wan Animate、SCAIL-2、SAM3）和圖片 golden fixtures 都沒有用到這些節點，所以沒有改 graph、版本或 hash。
- 改名前的實測紀錄裡的節點名稱已改寫成新名稱；當時實際送出的是對照表裡的舊名稱，存在本機 `output/` 的 API graph 也還是舊名稱，靠別名仍然可以重送。
- 文件裡以 `output/*-kabuto-upper-body/`、`output/*-kabuto-face-swap/`、`output/*-kabuto-wan-animate/` 標註的本機證據，實際資料夾名稱是改名前建立的 `steve-kabuto-upper-body` 等（在 ignored `output/`，不進版控，也沒有改名）。

## 移除舊名稱（第 8 階段）

退場方式的評估與待決事項見 [ADR 草稿（PR 8.1）](../decisions/2026-10-08-node-alias-exit.md)。

移除前要先在 Windows 與 Mac 唯讀掃描 `<ComfyUI>/user/default/workflows/**/*.json`，確認沒有 workflow 還在用舊 class 名稱；有的話先在 UI 開啟、換成新節點後另存。確認後刪掉 `LEGACY_*` 常數與別名登記，並從 `tests/test_neutral_wording.py` 的允許清單移除。
