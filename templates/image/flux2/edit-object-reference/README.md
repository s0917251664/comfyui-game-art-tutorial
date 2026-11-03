# FLUX.2 雙圖物件編修

`image/flux2/edit-object-reference` 輸入待編修圖片與第二張參考。由三參考模板移除角色分支而來。目標圖與參考圖各自 VAE 編碼，依序加入正負參考條件，不拼圖、不用程式產生修復像素。

模型 pins、官方來源與取樣設定沿用三參考模板。原模板不變；此模板維持 draft／untested。用途分工仍須由 prompt 說明，不提供身分或像素硬鎖。

輸入契約請查 `python tools_src/gameart.py run show image/flux2/edit-object-reference`，依 comfyui-run 技能先 dry-run、preflight 再執行。輸出比例由目標圖決定。技術執行成功不代表修復成功，候選仍需美術驗收。

裁切與縮放只是參考準備；局部結果回貼須使用確認過的範圍，並獨立檢查接縫與保留區。

## 用過的方式

- 局部物件修復：最初用來比較去掉站立角色參考的效果，沒有形成結論（本機證據：`output/hammer-method-tests/`）。
- 同角色第二參考：2026-10-29 Skye 衝刺批次把角色圖放在 `image`、待機圖放在 `object_ref`，再用提示詞指定新姿勢（本機證據：`output/skye-design/dash/`）。

單純改單張角色姿勢先用 `gameart.py pose-edit`；選路見[物件局部修正的取捨](../../../../docs/knowledge/art/local-object-repair-decisions.md)。

2026-10-13～29 本機共 14 次 run 都是 `completed`。這只是技術完成，平台狀態未升級。
