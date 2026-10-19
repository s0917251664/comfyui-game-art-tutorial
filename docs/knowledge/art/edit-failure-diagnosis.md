---
type: guide
status: current
---
# 修圖失敗診斷：症狀 → 原因 → 只改一個變數

局部修改結果不對時，先對症狀，再改**一個**變數重跑，不要整組參數一起動或直接換 seed。流程與停損見 [修圖手冊](edit-playbook.md)。下表的原因有三種來源，標在最後一欄：**實測**＝本 repo 有紀錄；**機制**＝來自 ComfyUI 節點行為，本 repo 的 template 以此為依據；**經驗**＝一般社群做法，套用前以小範圍實測確認。

| 症狀 | 最可能原因 | 先改這一個 | 依據 |
|---|---|---|---|
| 結果幾乎和原圖一樣，像沒有吃到遮罩 | 遮罩沒有 alpha 通道，或方向相反（要改的區域必須 alpha=0） | 檢查遮罩語意：存成 RGBA、要改的區域透明。Simple Mask 的 `mask_editor.png` 不能直接送 | 實測，見 [遮罩](masking.md) |
| 遮罩外的區域也變了（顏色、細節） | 生成端本來就會重畫全圖，遮罩外只是「大致」保留 | 不改參數，用 `edit composite` 把遮罩外合回原圖 | 實測：九成以上保留區像素有變動，合成後為 0（[編修情境](edit-scenarios.md)） |
| 遮罩內變成灰色／平塗色塊，沒有材質細節 | 遮罩貼太緊、羽化太窄，而且 `--denoise` 沒拉滿，模型收到互相矛盾的訊號 | `--denoise` 設 1.0，或放寬遮罩羽化；三者一起看 | 實測，見 [遮罩](masking.md) |
| `inpaint`／`guided_inpaint` 把 `--denoise` 調低反而變灰或畫不出東西 | 這兩個 template 用 `VAEEncodeForInpaint`，遮罩內像素先被填成中性灰再編碼，低 denoise 無法還原原內容 | 局部重繪維持 `--denoise 1.0`；想「保留原內容只微調」改走 `refine`（整圖），或在 ComfyUI 實驗 `SetLatentNoiseMask`（[節點入門](comfyui-nodes-primer.md)） | 機制 |
| 修補處和周圍有明顯接縫、光暈、色差 | 遮罩邊界太硬；遮罩貼著物件邊緣沒有留過渡 | 遮罩往外多留幾像素並羽化；模板內建 `grow_mask_by` 為 6，不夠再放寬手繪範圍 | 機制＋經驗 |
| 修完後該處的光線方向、色溫和周圍不合 | prompt 沒提光源；模型只看到遮罩周邊的一圈 | 在 prompt 加上「與周圍同一光源方向、同色溫」等脈絡 | 經驗 |
| 想移除物件，結果又畫出同一個物件 | 正向 prompt 寫了該物件名稱 | prompt 改寫成遮罩內該有的背景 | 經驗 |
| 手、手指、握姿崩壞 | 純 `inpaint` 沒有結構錨點；手指細節超出 OpenPose 能力 | 肢體／握姿改 `guided_inpaint`＋`pose`；手指細節只蓋壞的那一小塊再修 | 實測，見 [已知限制](known-limitations.md) |
| 小圖案（肩章、臂章、標誌）處即使本來是空白也被畫出圖案 | `denoise=1.0` 的自由生成通病 | 小範圍 `inpaint` 單獨修，不要擴大 `guided_inpaint` 遮罩去將就 | 實測 |
| 外觀參考圖的顏色牽動遮罩外鄰近區域 | `--appearance-ref` 影響整體色彩印象 | 遮罩貼合實際要換的區域；`--appearance-weight` 往下調 | 實測 |
| 參考圖上的文字變成一坨假字 | IPAdapter 把文字視覺印象一起帶入 | `--appearance-weight` 從 0.3–0.4 開始，negative 加強 `text`、`words` | 實測 |
| 改顏色／材質但完全沒命中目標 | 以生成改顏色本來就不穩定；`refine` denoise 太低蓋不過原圖 | 純顏色改走 `edit recolor`；真要改材質才調高 denoise 或改 `guided_inpaint` | 實測，見 [單一物件換色](single-object-color.md) |
| `recolor` 後邊緣還有殘色 | 邊緣像素的色相／飽和度落在範圍外 | 加大 `--hue-range`，或調低 `--min-saturation`；遮罩收緊以避免誤傷鄰近部位 | 實測 |
| 姿勢控制沒作用，角色站得直挺挺 | 骨架沒偵測到（`people=[]`），Q 版或簡筆畫常見 | 不稱為成功的 pose；改換 `canny`／`depth`，或請使用者提供更完整的參考圖 | 實測，見 [控制來源判斷](control-type-selection.md) |
| 簡筆火柴人當 canny 參考，人形扭曲 | 稀疏線條被當作真實邊緣照抄 | 改用 `pose` | 實測 |
| 文字描述的動作和姿勢參考打架，構圖矛盾 | prompt 與控制圖衝突 | 先看參考圖實際動作，prompt 改成一致 | 實測 |
| 去背後有光暈、洞、裁切 | Alpha 存在不代表去背品質；半透明材質、髮絲難處理 | `edit asset-audit` 看白／黑／棋盤預覽，問題區域人工處理 | 實測 |
| 整張圖被塞滿電路／紋理（prompt 有 circuit） | 關鍵字觸發滿版紋理 | 換成 armor plating、wire tufts、mechanical parts 等詞 | 實測 |
| 結構鎖定（structure-ref）後精細雕紋出不來 | Canny 鎖邊緣同時壓抑額外線條 | 不跟使用者保證兩者兼得；細節事後疊加或另補 | 實測，見 [結構範本](structure-ref.md) |
| 同一位置每次都出現相同缺陷（換 seed 沒用） | 底模對該題材的傾向 | 不換 seed；只蓋缺陷處用 `inpaint` 補 | 實測 |
| 重跑一次耗很久、中途失敗 | 大圖或 Mac MPS 限制；逾時 | 先查狀態，不重送；大尺寸 `upscale` 在 Mac 上先告知風險 | 實測 |

## 診斷順序（不確定是哪一種時）

1. **輸入有沒有被吃到**：遮罩格式、尺寸一致、來源圖是否正確（最便宜，先排除）。
2. **範圍對不對**：用半透明預覽看遮罩，而不是看灰階檔。
3. **task 選對沒**：結構要鎖卻用純 `inpaint`，或純顏色卻用生成。
4. **denoise／羽化／遮罩貼合度**：當成一組看。
5. **prompt 內容**：只描述遮罩內；有沒有寫到不想要的東西。
6. **最後才是 seed**，而且只在以上都合理、只是需要多看幾個版本時才換。

## 記錄新發現的規則

新症狀請按 [INDEX](../INDEX.md)「記錄與提升規則」記到 [已知限制](known-limitations.md) 或 [experiences/](../experiences/asset-records-2026-10-01.md)，註明日期、task、環境與證據；單一案例不寫成通則。
