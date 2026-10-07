# 影片產線可靠範圍盤點（2026-10-03）

> 本頁記錄一次本機可靠性盤點的範圍與觀察，供後續建立基準使用。這是工程與內容抽樣紀錄，不是品質認證，也不改變 task、模型設定或素材驗收狀態。

## 環境與盤點邊界

盤點日期：2026-10-03。機器為 Windows 11、NVIDIA RTX 4080 16GB（16,376 MiB）；ComfyUI 影片 runtime 偵測為 Python 3.13.9、PyTorch 2.13.0+cu130、Pillow 12.2.0、PyAV 18.1.0。指定快照 `output/video_reliability_20261003/capabilities.json` 顯示 H3 與 Wan available，ComfyUI node check available。

這是獨立盤點快照，刻意沒有指定 `default_backend`。其中 `null` 只代表初次獨立盤點快照未記錄預設值；當時沒有改動正式預設。修復後重新掃描正式 `video_capabilities.json`，確認 `default_backend` 仍為 H3。正式重掃前快照另存於 `output/video_reliability_20261003/capabilities_before_fix.json`。盤點時 repo 的 `generate.py` 與整個 `comfyui_pipeline/`（排除 cache）和部署版本一致。

`tests/test_generate.py` 初次有 65 項測試全數通過，涵蓋圖片與影片程式，不是 65 支影片測試。初次執行因未設定 `PYTHONPATH` 找不到模組；補上 `tools_src` 後通過。後續為本次發現的 fingerprint 回歸缺口新增一項 regression test，更新後 66 項測試全數通過。

本次盤點沒有變更模型或 profile；官方最新技術升級評估不在範圍內。

## 輸出檔與 sidecar 盤點

`output/video_reliability_20261003/existing_outputs.json` 遞迴掃描 repo 的 `output`，並掃描 ComfyUI `output` 根層，共列出 304 個 MP4 路徑；全部都完成完整影片解碼。這個數字包含副本與測試檔，不代表 304 次獨立生成，也不代表任何一支已獲美術接受。音軌只讀取 metadata，沒有完整解碼或聆聽。

304 支中有 61 支具 sidecar。其中 60 支有非空 `requested_contract`，重新尺寸、FPS、影格數、時長與音軌存在性契約均通過；另 1 支沒有可判定契約，屬 unverifiable。該筆合成測試檔名含 `accepted_clip`，名稱不代表美術審核者曾驗收。其餘 243 支沒有 sidecar，不能據此宣稱可重現。

60 筆具輸出契約的 sidecar，其 task/backend 分布如下：

| Task | Backend | 筆數 |
|---|---:|---:|
| `camera_move` | H3 | 1 |
| `character_video` | H3 | 22 |
| `clip_extend` | H3 | 11 |
| `fx_loop` | H3 | 1 |
| `img2video` | H3 | 15 |
| `video_composite` | local | 3 |
| `video_concat` | local | 7 |

輸入引用共 102 筆，94 筆目前存在且 SHA-256 相符，8 筆路徑已失效，位於封存目錄；失效原因尚未確認。這項盤點沒有把失效自動解讀為輸入內容變更。

[`docs/tested-versions.md`](../../tested-versions.md) 記有 2026-08-31 的歷史 smoke：H3 `transition`、`pose_drive`，以及 Wan `img2video`、`pose_drive`。這些紀錄不在本次 60 筆具輸出契約的 sidecar 集合內；Wan `transition` 不在這些歷史 smoke 範圍內。

## 代表性畫面抽樣

對代表性影片各抽取六個時間點製作 `representative_contact.jpg`。這只是稀疏抽樣，不能代表全片時間品質驗收，也沒有聽音軌：

| 影片 | 抽樣觀察 | 可支持的結論與限制 |
|---|---|---|
| `fx_loop_h3_00001` | 轉盤首尾相近，中段輪面紋理出現變形 | 此例不能支持剛體旋轉或無縫循環承諾 |
| `transition_h3_00001` | 輪盤由平面藍色變成金屬藍 | 沒有逐一比對指定來源端點，不能宣稱端點準確 |
| `camera_move_h3_00002` | 輪盤逐漸放大 | 只觀察到這個例子的 zoom 效果 |
| `pose_drive_00004` | 抽樣中單人走近鏡頭，背心與槍的輪廓可辨 | 只適用這個抽樣案例 |
| `pose_drive_00001` | 抽樣中可見明顯雙人重疊 | 顯示錯誤起姿／控制綁定可能產生失敗結果 |
| `character_video_h3_00001` | 抽樣中單人走近鏡頭 | 只適用這個抽樣案例 |

## Live baseline：H3 `img2video`

本次另完成一支 H3 `img2video` live baseline：[`shot_reliability_20261003_idle_img2video_00001_.mp4`](../../../output/video_reliability_20261003/live_baseline/shot_reliability_20261003_idle_img2video_00001_.mp4)，sidecar 為同名 `.mp4.json`。輸出為 768×768、24 FPS、56 frames、2.333333 秒、H.264 與 AAC stereo（32,000 Hz），耗時 95.053 秒；technical contract pass，沒有 warnings。`--extract-frames` 產生 56 張 PNG，逐張載入解碼成功且數量符合影片影格數；音訊完整解碼為 73 audio frames，但未聆聽，沒有音質驗收。輸入 source hash 與紀錄相符。

基準輸入為 `baseline_source.png`，SHA-256 `AFE83960DCEE3BCB728AAEA70A0AF5E835FF88F8DF27F919EA6075BFF7E08A05`；seed 為 `20260831`。使用既有 `img2video` task 參數，prompt 為 `subtle idle motion, cloth and hair move gently, camera locked`，negative 為 `blurry, low quality, text, watermark`，請求 2 秒、768×768，並使用 `--extract-frames`。輸入是多視圖角色設定板，刻意沿用歷史 smoke，因此這支影片不能當作單角色 idle 製作品質基準。六幀抽樣配置大致保留；動作自然度、音質與美術驗收仍 pending。這支 live baseline 在原 304 路徑盤點完成後生成，不計入該統計。

## 修復的可靠性缺口：動態 upload 清單 fingerprint

盤點中發現一個會影響 `--resume` 的可靠性問題：ComfyUI `LoadImage` 的上傳圖片清單及 `LoadVideo` `COMBO` options 中可變的檔名被納入 node schema fingerprint，當生成流程上傳新素材後，preflight fingerprint 會改變，可能誤擋原本有效的 resume。

已修正共用的 `video_catalog.py` `node_schema_fingerprint`：只對標記為 `image_upload`、`video_upload` 或 `audio_upload` 的 input options 清空動態檔名清單。schema 的型別、flags、輸入輸出，以及其他 enum/options 仍參與 fingerprint。generate facade 與 `detect_video_capabilities.py` 共用此函式。新增 regression test 驗證 fingerprint 運算不改寫 payload、圖片與影片檔案清單變動時 fingerprint 穩定，且真實 interface 或其他 enum 變動仍會改變 fingerprint。這是既有校驗 bugfix，不新增 task 或模型。部署完成後執行 `tools_src/verify_portable_install.py --config local_config.json --require-video`，21 pass、0 fail；檢查涵蓋 facade、整個 package 與 detector 同步、live device match、圖片預設 `sdxl_standard` 及影片 H3/Wan。

修正後已將 `generate.py`、整個 `comfyui_pipeline/` 與 `detect_video_capabilities.py` 部署到 ComfyUI。`capabilities_fixed.json` 的 fingerprint 與 `fingerprint_live.json` 中上傳 `upload_inventory_probe.png` 前、後及 snapshot 值一致（`57b26425…2499058`），證明本次標記為 upload 的動態清單不再造成 fingerprint 漂移。此觀察不代表未標記的所有 schema 欄位都已驗證為穩定。

其後使用相同 source、seed、prompt、negative 與請求參數再次完成 H3 `img2video`，結果為 [`shot_reliability_fixed_20261003_idle_img2video_00001_.mp4`](../../../output/video_reliability_20261003/live_fixed/shot_reliability_fixed_20261003_idle_img2video_00001_.mp4)：768×768、24 FPS、56 frames、2.333333 秒，technical pass 且無 warnings，56 張 PNG 均可解碼。sidecar 耗時記為 1.145 秒，推測受 ComfyUI cache 影響，不能當作效能推論。隨後對該輸出執行 `--resume`，現場成功重新驗證並恢復既有輸出，沒有進入生成送出流程。原始 95.053 秒 baseline 仍保留；新 snapshot 的簽名不能假裝與舊 sidecar 相同，舊 sidecar 未重寫，也未補造 hash。修復造成設定 digest 改變，舊 sidecar 會與新 snapshot digest 不同；原輸出與舊 snapshot 均保留，沒有放寬 resume 簽章條件。

## 目前有證據支持的範圍

本次盤點支持這台機器在當時環境下，既有影片路線可用；列入的 304 個 MP4 均能完整解碼，並且有 60 筆具輸出契約的 sidecar，其輸出通過各自記錄的技術契約。既有生成 task 也有歷史執行紀錄。本次內容檢視仍是少量題材的單例抽樣，不能推算各 task 成功率，也不能把技術 pass 視為內容合格。

修復後執行 `verify_portable_install.py --config local_config.json --require-video`，21 項部署檢查通過、0 項失敗，包含 facade、package、偵測器同步與本機能力快照。正式的 `<ComfyUI>/tools/video_capabilities.json` 已依修正後偵測器刷新，保留原預設 `h3`；原快照另存 `output/video_reliability_20261003/capabilities_before_fix.json`。舊演算法的快照需重新偵測；新的 config digest 與舊 sidecar 不同時，仍維持 resume 嚴格比對，不改寫歷史紀錄來繞過檢查。

已知固定契約為 24 FPS、生成長邊最高 768、請求時長 2 至 6 秒，且 backend 對齊可能令輸出實際時長不同於請求值。現有證據不保證像素級鎖臉、真正環繞運鏡（orbit）或無縫 loop。既有 304 路徑盤點的音訊只核對 metadata；原始 live baseline 另完成音訊解碼。兩者都不能支持音質或內容判斷。

## 下一階段缺口與建議次序

以下是待規劃工作，不代表已完成的能力或新增規則：

- **P0：擴充可重複基準。** 已補一筆 H3 `img2video`、2 秒、方形畫布的 live 技術基準，MP4、sidecar、source hash 與 seed 可對照。仍需按 task/backend 留存基準與人工觀察證據，並測試 2、4、6 秒及直式、橫式、方形比例；這些項目尚待實測。
- **P1：先測低複雜度場景。** 涵蓋 idle、zoom/pan，以及畫面中只有單一循環元素的案例，同時保存失敗例，避免只留下成功樣本。
- **P2：再測角色動作與接續。** 納入角色起始姿勢、多種動作與片段接續，明確檢查身份、重影、服裝道具與時間連續性。
- **P3：按實際需求評估交付包裝。** 透明序列、sprite 打包等若有需要，依新增工具 checklist 另行評估與驗證；本次盤點沒有新增這些能力。

## 證據檔案

- `output/video_reliability_20261003/capabilities.json`：本機能力與 runtime 快照。
- `output/video_reliability_20261003/existing_outputs.json`：影片解碼、sidecar 契約與輸入引用盤點。
- `output/video_reliability_20261003/representative_contact.jpg`：既有代表影片的六點抽樣圖板。
- `output/video_reliability_20261003/live_baseline/shot_reliability_20261003_idle_img2video_00001_.mp4` 與同名 `.mp4.json`：原始 H3 live technical baseline 及其 sidecar。
- `output/video_reliability_20261003/live_fixed/shot_reliability_fixed_20261003_idle_img2video_00001_.mp4` 與同名 `.mp4.json`：fingerprint 修復後的 live 結果與 sidecar。
- `output/video_reliability_20261003/capabilities_fixed.json`、`fingerprint_live.json`：修復後獨立 snapshot 與動態 upload 清單前後 fingerprint 檢查。
- `output/video_reliability_20261003/capabilities_before_fix.json`：正式重掃前保存的舊影片能力快照。
- `tests/test_generate.py`：66 項圖片與影片測試，包含 upload inventory fingerprint regression。
- [`docs/tested-versions.md`](../../tested-versions.md)：包含 2026-08-31 的 H3 `transition`、`pose_drive`，以及 Wan `img2video`、`pose_drive` 歷史 smoke 紀錄。
