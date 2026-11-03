# FLUX.2 三參考圖編修

`image/flux2/edit-three-reference` 是獨立實驗模板，保持 draft／untested；輸出為待美術驗收的 candidate。

三張圖片依序是封面修改目標、角色外觀參考、物件參考。各自載入、等比例縮放與 VAE 編碼，再經 ReferenceLatent 追加至正負兩條 conditioning。不是把圖片拼成一張，也沒有用程式修補像素。文字提示須以 image 1、image 2、image 3 說明各圖用途；參考順序不等於硬性身分、透視或像素鎖定。

派生來源是隨附的官方 [Image Edit (Flux.2 Klein 4B) blueprint](source/official-blueprint.json)，固定版本與差異見 template.json 的 provenance。保留官方 base 模型、取樣方法和參數；擴充兩組獨立參考分支並按順序串接。原單圖模板不變，沒有下載新模型或修改 runner。

使用 `python tools_src/gameart.py run show image/flux2/edit-three-reference` 查實際輸入契約，再依 comfyui-run 技能 dry-run、preflight、執行。這個入口尚未接入 generate.py 的圖片 task。

輸出比例由第一張目標圖決定。這是全圖重新生成式編修，沒有遮罩與逐像素保留承諾；增加參考圖亦增加記憶體和計算量。技術成功不代表美術驗收通過。

2026-10-12 經使用者授權新增實驗模板並執行三圖封面編修。這份授權不代表其他素材的美術接受或模板狀態升級。

這個模板不是改姿勢的首選，也沒有解決雙手握短柄；選路見[物件局部修正的取捨](../../../../docs/knowledge/art/local-object-repair-decisions.md)。

## 實機紀錄

2026-10-12 在 windows-cuda／RTX 4080 完成兩輪：第一輪 68.967 秒，第二輪 76.881 秒。預檢確認 17 種必要節點可用、三個模型 SHA-256 符合 pin，三張圖片各自上傳；兩輪 runner 技術檢查通過，content_review 仍 pending。

第一輪槌頭端面與厚度較明確，但接合仍不理想，圖樣和角色細節有漂移。第二輪沿用第一輪輸出及相同角色／武器參考，槌柄改為皮革握柄，下方手部握持反而不清楚，不能視為修復成功。保留第一輪供比較，不自動美術接受。

模板／runner／preflight 回歸測試共 147 項，144 項通過、3 項略過；文件測試另 5 項通過。來源與三圖接線另經只讀審核。此實驗結果不自動升級模板或平台狀態。

本機完整證據：`output/hammer-three-reference-comfy-template/`（`experiment.json`、`round1/`、`round2/`）。output 是本機產物，另機未必存在。

2026-10-12～14 本機共 68 次 run 都是 `completed`，其餘多為封面實驗（`output/cover-redo/`）。這只是技術完成，平台狀態未升級；封面結論見[封面握錘失敗紀錄](../../../../docs/knowledge/experiences/cover-hammer-grip-2026-10.md)。
