---
type: animation-brief-template
status: template
last_updated: 2026-10-06
---

# 角色動畫測試 brief

複製本模板建立一次有界的動畫測試 brief。只填已知事實；未確定的項目標為「待確認」，不要把推測寫成製作要求。模板用於規劃與比較，不表示已提交生成或完成美術驗收。

## 任務

- 測試名稱／日期：
- 目的與要回答的單一問題：
- 執行路線：原生 ComfyUI UI workflow／其他（說明）：
- 參考證據或前次紀錄：

## 輸入與參考

- 來源影片或影格（路徑、片段起訖、版本／雜湊）：
- 角色參考圖（路徑、版本／雜湊）：
- 參考圖用途：身份／外觀／服裝／其他：
- 動作來源與要保留的動作：
- 參考方式：Mix／Move／其他（實際 graph 名稱）：
- 遮罩檔案與語義：例如一般二值選區，或依指定 workflow 定義的彩色身份遮罩；說明黑、白、各顏色分別表示什麼：
- 遮罩人工檢視結果或待處理事項：

## 角色錨點與變更界線

- 必須保留的身份特徵（形狀、材質、顏色、服裝等）：
- 允許改變的內容：
- 禁止新增／改變的物件或特徵：
- 鏡頭、背景與構圖要求：
- 動作幅度及接觸／遮擋注意事項：

## Prompt

- Positive prompt（記錄完整實際文字）：
- Negative prompt（如 workflow 有使用，記錄完整實際文字）：
- Prompt 是否忠實對應來源動作？理由：
- 是否有來源未呈現的場景、動作或道具字詞？逐項列出或填「無」：

英文 prompt 填空示例：

> `A [specific character identity and visible anchors] follows the observed [head, hand, and body motion] in the reference clip. Preserve [identity, silhouette, materials, clothing, and colors]. Keep the camera and background consistent with the source. Do not introduce unobserved props or actions.`

機器人示例（只在與實際參考相符時使用）：

> `A small robot with a camera-shaped head, pink metal body, white-and-blue knitted sweater, and yellow pants follows the observed head and hand motion in the reference clip. Preserve the camera-shaped head, robot silhouette, pink metal, sweater pattern, and yellow pants. Keep the camera and background consistent with the source. Do not introduce unobserved props or actions.`

## 固定設定與比較範圍

- 模型檔名、版本、精度及來源：
- 實際 workflow／graph 版本：
- 解析度、幀數、FPS：
- Steps、CFG、sampler、scheduler：
- Seed：
- 其他會影響結果的設定：
- 本輪唯一預定變因：
- 比較候選數及成對方式：
- 不納入本輪的問題：

## 內容驗收條件

- 首幀檢查項：
- 中間幀檢查項：
- 末幀檢查項：
- 身份與外觀判定條件：
- 動作與時間連續性條件：
- 禁止項（漂移、幻覺道具、衣著／材質改變等）：
- 何種問題須停止比較並修訂 brief：

## 狀態

- Brief 狀態：draft／ready-for-review／closed
- 使用者決定及日期：
- 備註：
