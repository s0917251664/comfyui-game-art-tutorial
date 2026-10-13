# 3d/hunyuan3d-2mv/multiview-cutout

**Hunyuan3D-2mv 多視角轉 3D（自動去背）**（v0.1.0，draft）

把物件的前、左、後、右四張視角圖轉成 3D 網格（GLB，只有幾何、沒有貼圖）。每張視角會先用 BiRefNet 去背、補白底，所以可以直接丟設計稿或三視圖裁出來的圖。已經去背乾淨的圖，用 [`3d/hunyuan3d-2mv/multiview`](../multiview/README.md)。

## 用途

- 武器、道具的設計圖轉成粗模，拿去 Load3D 擺角度，當透視或重繪的控制圖。
- 不是最終美術資產：網格沒有貼圖、拓樸未整理。

## 輸入

| slot | 說明 |
|---|---|
| `front_image` | 正面視角（必填） |
| `left_image` | 物件自己的左側。只有一張側面圖就兩邊都給它 |
| `back_image` | 背面。沒有就給正面圖左右鏡像 |
| `right_image` | 物件自己的右側 |
| `steps`／`cfg` | 預設照官方範本 20／7.5 |

- 四張都必填，每張一個物件、置中、四邊留白；比例要一致（三視圖同一張裁切最好）。
- 輸出在 `outputs/mesh/`，post 步驟 `check_model_3d` 只檢查 GLB 格式與頂點數（≥100）。

## 執行

```bash
python tools_src/gameart.py run 3d/hunyuan3d-2mv/multiview-cutout --set front_image=front.png --set left_image=side.png --set back_image=back.png --set right_image=side.png --preflight
```

確認 preflight 通過再拿掉 `--preflight` 實際執行。產出的 GLB 放到 ComfyUI `input/3d/` 就能在 Load3D 開啟。

## 來源與差異

從官方 workflow_templates `3d_hunyuan3d_multiview_to_model` 派生（原檔在 `source/`），模型、取樣參數相同。差異：每張視角前加 core 節點 `RemoveBackground`（BiRefNet）→ `InvertMask` → `ImageCompositeMasked` 貼白底。原因：2026-10-13 錘子三視圖實驗不去背時，灰色背景被建成兩片平板；去背後才得到乾淨模型（實驗紀錄 `output/hammer-3d-proxy/hy3d/`，本機、不進版控）。

2026-10-13 使用者要求把「平面圖轉 3D」做成固定 template，並同意兩份都做。技術通過不等於美術接受（[R1](../../../../docs/knowledge/rules/candidate-review.md)）。
