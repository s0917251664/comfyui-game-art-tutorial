---
type: adr
status: accepted
date: 2026-10-08
---
# ADR：影片 template 一份 graph，不按平台複製

## 背景

第 6.2 階段把五個影片 builder（`build_img2video_wan`、`build_img2video_h3`、`build_pose_drive_wan`、`build_pose_drive_h3`、`build_character_video_h3`）的結構變體收成 `templates/video/**`。

graph 裡的模型檔名不是執行當下才猜的。`video_config=None` 時，builder 經由 catalog 寫進 `UNETLoader`／`CLIPLoader`／`VAELoader` 的檔名，和第 6.1 階段 golden 凍結的檔名相同。平台差異若只是「同一份檔在某一台機器上的 pin」，不需要另一份 graph。

## 決定

1. **一份 template，一份 graph。** 不為 `windows-cuda`、`macos-mps` 各複製一份 variant graph。graph 凍結成 `video_config=None` 時 builder 寫入的檔名。
2. **模型物件可以多一個選用的 `platforms`。** 有寫就必須是非空 object，而且必須含 `windows-cuda`。該項目剛好有 `filename`、`sha256`、`size_bytes`，三者都要等於頂層 pin。頂層 `filename` 仍然是 graph 裡那個檔名。
3. **不編造 `macos-mps` 的另一組檔名。** 目前沒有另一套已核對的檔，`platforms` 只記 `windows-cuda`（內容與頂層相同）。`capability_gate.platforms.macos-mps` 維持 `untested`，那是平台閘門，不是模型檔名。
4. **預檢仍只檢查頂層 pin**（`path`、`filename`、`sha256`、`size_bytes`）。`platforms` 是同一份檔的紀錄，不取代頂層，也不讓預檢改去讀平台項目。
5. **沒有 `platforms` 的既有 template 仍然合法。** 額外鍵會被 validator 拒絕，所以 schema 與 `MODEL_KEYS` 要明確允許這個欄位。

## 不採用「每平台一份 graph」的理由

- 節點結構、取樣參數、slot 目標都一樣。平台副本只會把同一個檔名再寫一次，第 6.1 階段的一份 golden 就對不上兩份 graph，hash 與回歸也要維護兩次。
- 真正換檔名會改 graph 的 loader 欄位。那是另一份 template，不是同一份 graph 的平台變體。
- 同一檔的 sha256 與大小已經釘在頂層。`platforms.windows-cuda` 只是把「這個平台用的就是頂層那一筆」寫清楚，避免以後有人為了平台各存一份 graph。

## 後果

- 第 6.2 階段的影片 template 都是 `draft`，`windows-cuda` 與 `macos-mps` 都是 `untested`。實機執行仍待補證據。
- `extract_last_frame` 與 `camera_end_still` 是 runner 的 pre 步驟（只呼叫既有的抽尾幀與運鏡終點靜幀），不是平台 graph，也還沒接上 `tasks/video.py`。執行路徑留到第 6.3 階段。
- 模型 `source`／`url` 只在有固定 git revision 時填。官方範本網址若是 `resolve/main`，不算固定版本，維持 null。`umt5_xxl_fp8_e4m3fn_scaled.safetensors` 的 sha256 與既有 Wan template 的 pin 相同，沿用那一筆 revision。
