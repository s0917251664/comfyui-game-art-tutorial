# 3d/hunyuan3d-2mv/multiview

**Hunyuan3D-2mv 多視角轉 3D**（v0.1.0，draft）

把物件的前、左、後、右四張視角圖轉成 3D 網格（GLB，只有幾何、沒有貼圖）。適合簡單的武器、道具或幾何物體；角色與動態姿勢不適合。graph 照官方範本，**不做去背**：輸入必須已經去背、背景乾淨（白或淺色）。直接用設計稿或有灰底的圖，請用 [`3d/hunyuan3d-2mv/multiview-cutout`](../multiview-cutout/README.md)。

## 輸入

| slot | 說明 |
|---|---|
| `front_image` | 正面視角（必填） |
| `left_image` | 物件自己的左側。只有一張側面圖就兩邊都給它 |
| `back_image` | 背面。沒有就給正面圖左右鏡像 |
| `right_image` | 物件自己的右側 |
| `steps`／`cfg` | 預設照官方範本 20／7.5 |

- 背景有雜色或灰底時，背景會被當成物體建出平板（2026-10-13 錘子實驗）。
- 輸出在 `outputs/mesh/`，post 步驟 `check_model_3d` 只檢查 GLB 格式與頂點數（≥100）。

## 來源與差異

從官方 workflow_templates `3d_hunyuan3d_multiview_to_model` 派生（原檔在 `source/`）。UI workflow 展開成 API 節點、沿用官方 node id，模型與取樣參數相同；只把 SaveGLB 前綴改成 `3d/...`，步數與 CFG 開成 slot。

2026-10-13 使用者要求把「平面圖轉 3D」做成固定 template，並同意兩份都做。技術通過不等於美術接受（[R1](../../../../docs/knowledge/rules/candidate-review.md)）。
