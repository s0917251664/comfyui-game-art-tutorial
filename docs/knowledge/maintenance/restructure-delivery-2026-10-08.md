---
type: maintenance
status: current
---
# 第 3–8 階段工作交付脈絡（2026-10-08）

這一份給人讀：這次重構從哪裡接、每一階段交了什麼、分支怎麼疊、哪些已經可以看、哪些還沒交。

三頁分工：

| 頁 | 用途 |
|---|---|
| [重構交接](restructure-handoff.md) | 原始計畫與必守規則 |
| [重構進度 2026-10-08](restructure-progress-2026-10-08.md) | 下一個 agent 的操作清單：SHA、禁做事項、整合順序 |
| 本頁 | 交付脈絡 |

規則仍以交接頁為準。做到哪裡仍以進度頁的 SHA 為準。已經生效的方向在[決策索引](../DECISIONS.md)。本頁不取代那兩頁。

日期是台北時間 2026-10-08。沒有開 GitHub PR，沒有 merge 到 `develop`。

## 一句話

第 3 到第 8 階段裡，能在不上部署、不下載缺檔模型的範圍內做完的項目，都已經做成審查結論為「可以合併」的分支，並 push 到 `origin`。這些分支還沒收成一條線，所以現在不能當成一整包部署。7.3（技能收成 6 個）、8.3（刪 builder）、8.4（部署 template）還沒開始。實機跑過的項目只做了技術檢查，美術接受仍是 pending。

## 任務從哪來

交接頁寫的是：第 1、2 階段已經進 `develop`（當時基準 `2dbdeeb`，完整測試 Ran 505，`verify-install` 91/91，ComfyUI v0.34.0）。第 3–8 階段由 Windows 本機 agent 做到端到端，使用者在審核後自己合併。

前一個 agent 讀了交接頁、開了分支，沒做完。這次接手的範圍是交接頁第 4 節的全部項目：3.1–3.5、4.1–4.3、5.1–5.2、6.1–6.5、6′.1–6′.3、7.1–7.4、8.1–8.4。交接頁寫「需要使用者決定」的設計題，這次依授權直接定案，並寫成 ADR。

接手之後，流程改成：一個項目一條分支，本地用 grok plan mode 審查，結論是「可以合併」才 push。不開 PR，不自己 merge，不 force-push，不 rebase 已經 push 的 commit。token 快用完時先把中斷點寫進進度頁；5.2 的審查隨後結束，5.1、5.2、7.2 也已 push。

`origin/develop` 現在是 `5f1d31e`（Merge pull request #9，交接文件進 develop）。交接頁第 1 節的 `2dbdeeb` 是計畫開寫時的基準。

## 和原計畫不同的地方

1. **沒有開 PR。** 原流程是 push 後開 PR 到 `develop`。這次只 push 分支。合併仍等使用者。
2. **不是每個分支都從當時的 `develop` 切開。** 後做的項目疊在先做完的 commit 上，或從同一個父 commit 分成並列分支。所以單看一條分支，看不到全部改動。
3. **4.3 的 SD1.5 沒寫。** 磁碟上沒有 `dreamshaper_8.safetensors`。沒有發明 hash，也沒有下載。FLUX.2 有寫。SDXL 有寫。
4. **6.2 落地的影片 template 是 18 份，不是計畫表上的 5 個 graph 名稱。** 多出來的是同一批影片 task 的結構組合（有無尾幀、不同姿態條件、不同張數）。狀態仍是 draft。
5. **6′.3 原表寫等使用者決定。** 這次定成：`scene`／`sheet`／`pattern` 改純 Pillow；`birefnet-alpha` 留在 repo，不部署。ADR 在 6′ 那條分支，還沒出現在 `132201f` 的決策索引裡。
6. **兩次審查先退回再通過。** 6.4 的內嵌參考不會展開；5.1 省略 `--seed` 時會抽兩次亂數。都是在原分支加新 commit 修好，沒有 rebase。
7. **8.2 只改了 repo。** 本機已部署的節點仍是舊名稱。要等 8.4，而且 queue 必須是空的，才能部署並重啟。8188 已由使用者停止，沒有另外要求就不要重開。
8. **技術通過不等於美術接受。** 3.4、3.5、6.3 的實機都留著 `content_review: pending`。沒有人執行 accept 或 validation approve。

## 現在實際上有兩層東西

**第一層：已經 push、審查可以合併的分支。** 每一條都可以單獨看 diff。遠端 SHA 在 2026-10-08 用 `git ls-remote` 對過。

**第二層：還沒有的整合線。** `origin/feat/phase6.4-recipes-on-stack` = `132201f` 是目前最長的那條堆疊。它包含第 3 階段、第 4 階段的圖片 template、6.1–6.2、6.4–6.5、7.1、7.4、8.2。它不包含 5.1、5.2、6.3、6′、7.2。

若現在只把 `132201f` 合併進 `develop`，圖片 task 和七個影片 task 仍走舊的 Python builder，物件組裝也還沒改成 Pillow，能力偵測也還沒列出 template 能力。那五條並列分支要先 cherry-pick 成新 commit，才是一整包。

中斷點說明頁自己在 `docs/restructure-progress-2026-10-08`（`76b4ffe`、`076eb39`，本頁是後續 commit）。它疊在 `132201f` 上，只加文件。

## 分支怎麼疊

`132201f` 由下往上（舊到新）是：

```text
5f1d31e  develop（PR #9 交接文件）
537469f  3.1  device_config 提醒
78b28f5  3.2  template 官方欄位
9119b1d  3.3  runner 的 VACE 前後處理
6f7b926  3.4  VACE template，當時為 draft
fc99095  3.5  video_inpaint 改填這份 template
efa284a  8.2  移除舊節點名稱
0b68763  8.2  決策索引改成舊名稱已移除
dc1fd5c  8.2  舊名稱缺少節點的說明改到 8.4 重啟之後
777d75a  3.4  windows-cuda 改成 technical_pass
b35e7e1  7.4  擴充協議
5984301  7.4  禁令改引用協議
37e156d  7.1  catalog 產生器
896f03b  4.2  SDXL 與 layer_split template
c1c9208  4.3  FLUX.2 template
ab6189c  7.1  重產 catalog，納入圖片
e7b0a02  6.1  影片 graph golden
d841d2f  6.2  影片 template
b240e74  7.1  重產 catalog，納入影片
1c47d82  6.4／6.5  recipe
dbf95fd  6.4／6.5  草稿 recipe 的 slot 對到已落地的 template
132201f  6.4  內嵌參考在執行時展開
```

從 `dbf95fd` 另長出三條，它們沒有 `132201f` 那個修復：

```text
dbf95fd
├─ f6b3c75   6.3  七個影片 task
├─ 39f669e   6′   ef70dfe → e7d8ea4 → cab2f3a → 39f669e
└─ 00039a7   7.2  template 能力偵測
```

從 `b240e74` 另長出圖片切換，它們沒有 recipe 那三個 commit：

```text
b240e74
└─ b35d3e3   5.1  前六個圖片 task
   ├─ 1dd86fa  5.1  seed 只抽一次
   └─ 2d1e173  5.2  其餘圖片 task（自己也寫了 seed 只抽一次，但不是 1dd86fa 的子 commit）
```

整合時從 `132201f` 開新分支，用新 commit cherry-pick，順序建議：

1. `f6b3c75`
2. `ef70dfe`、`e7d8ea4`、`cab2f3a`、`39f669e`
3. `00039a7`
4. `b35d3e3`、`1dd86fa`、`2d1e173`

已知會碰到的檔：

- `templates/README.md`：`132201f` 和 6.3、6′、7.2 都改過。
- `tools_src/comfyui_pipeline/image_from_template.py` 的 seed：5.2 疊上 `1dd86fa` 時會衝突。留下的行為是「省略 `--seed` 只抽一次，用 builder 的 48-bit；傳入的 0 保持 0」。slot 預設的 `"auto"` 會再抽一次 32-bit，不能留著。

另外兩條 origin 分支不在這條堆疊上，內容已被堆疊裡的 ADR 取代，不要再拿來當底：

- `docs/phase4.1-image-variant-design` = `be2a27a`（方案比較的草稿線）
- `docs/phase8.1-node-alias-exit` = `7f8be0c`（退場 ADR 的草稿線，commit 訊息仍寫 proposed）

## 各階段交了什麼

審查欄的「可以合併」是本地 grok plan mode 的結論（`stopReason=end_turn`，最後一行 `VERDICT: 可以合併`）。它不是 GitHub review，也不是美術接受。

### 第 3 階段：VACE 成為第一個帶前後處理的 template

| 項目 | 交了什麼 | 分支與 tip | 審查 |
|---|---|---|---|
| 3.1 | `face_swap.py`、`video_layers.py` 不再連帶載入 `image_graphs`，缺 `device_config.json` 時不再印那句誤導提醒。`gameart.py run` 的說明改成現況 | `fix/phase3.1-device-config-warning` `537469f` | 可以合併 |
| 3.2 | `template.json` 補官方欄位：最低 ComfyUI 版本、需要的 custom node、模型 directory／url、upstream 出處。preflight 讀得到版本且低於最低版就擋下 | `feat/phase3.2-template-official-fields` `78b28f5` | 可以合併 |
| 3.3 | runner 能上傳 pre 步驟產生的檔，並執行 VACE 的工作區、貼回、遮罩外逐 byte 檢查。舊模組留成薄轉接 | `refactor/phase3.3-runner-generated-inputs` `9119b1d` | 可以合併 |
| 3.4 離線 | 新增 `templates/video/wan-vace/inpaint/`。當時為 draft | `feat/phase3.4-wan-vace-template` `6f7b926` | 可以合併 |
| 3.4 實機 | 同一份 template 在 windows-cuda 改為 `technical_pass`，版本 0.1.1。macos-mps 仍是 untested | `feat/phase3.4-windows-cuda-pass` `777d75a` | 可以合併。內容審查 pending |
| 3.5 | `generate.py video_inpaint` 的名稱與旗標不變，graph 改由 runner 填這份 template。缺 template 檔會 SystemExit，所以部署必須含 `templates/`，這件事留在 8.4 | `refactor/phase3.5-video-inpaint-adapter` `fc99095` | 可以合併。內容審查 pending |

VACE 現況（本頁所在的 `132201f` 上讀到的檔）：

- id `video/wan-vace/inpaint`，版本 `0.1.1`，`status` 是 `technical_pass`
- graph sha256 `fd9a75dac3b3742316d06be169d7925707dca84256882b561c0fe646df773f75`
- canonical sha256 `eca4a6b9cb0f446c4d6e4bf4535434559d9453e34db42c7d4b493d8aee236649`
- upstream 是官方 `video_wan_vace_inpainting`，blob `4af6c58919482553498d0e9f5bc7b5985030b914`
- 和範本的差異記在 template 裡：主模型用 1.3B，不接 CausVid LoRA，遮罩與工作區在本機先做成無損片段

3.5 的實機比較在本機（本機證據：`output/verify-20261008-3.5/live-compare.txt`）。規格對得上較早的輸出，檔案 hash 不同。不要重跑，不要 accept。

### 第 4 階段：圖片 template 抽出

4.1 定案為方案 A：每一種會增刪或更換節點的組合，各一份凍結 graph。runner 只填值。`image/sdxl/*` 對應 `sdxl_standard`，`image/sd15/*` 對應 `sd15_light`。tier 只改寬高。`filename_prefix` 是字串 slot。checkpoint 是 slot。LoRA 不寫進模型 pin。ADR：[圖片 template 的結構組合](../decisions/2026-10-08-image-template-variants.md)。

| 項目 | 交了什麼 | 在哪 |
|---|---|---|
| 4.2 | SDXL 系列與 `image/layer-split`。狀態在「還沒被 5.x 切換、也還沒實機升格」的意義上保持 draft 規則：catalog 測試要求圖片 template 仍是 draft | `896f03b`，含在 `ab6189c` |
| 4.3 | `image/flux2/concept`、`image/flux2/edit`。SD1.5 目錄不存在 | `c1c9208`，含在 `ab6189c` |
| catalog | 產生器把這 75 份納入索引 | `feat/phase4-image-on-stack` `ab6189c` |

75 份 = 72 份 SDXL + `image/layer-split` + 2 份 FLUX.2。審查可以合併。這階段按計畫還不切換呼叫路徑，切換在第 5 階段。

`doctor --refresh` 確認 `sd15_light` 底模未安裝。checkpoints 裡有 Illustrious-XL、juggernautXL、ponyDiffusion、sam3.1_multiplex、`sd_xl_base_1.0`。沒有 `dreamshaper_8.safetensors`。

### 第 5 階段：圖片 task 改填 template

CLI 名稱和旗標不變。task 自己上傳之後，載入 template、填 slot、patch。沒有呼叫會 queue 的 `runner.run()`。builder 還留著，等 8.3 再刪。

| 項目 | task | 分支與 tip | 審查 |
|---|---|---|---|
| 5.1 | concept、icon_asset、refine、character_action、pose_only、style_lock | `refactor/phase5.1-image-tasks-runner-a` `1dd86fa` | 第一次需要修改，修復後可以合併（9 輪） |
| 5.2 | inpaint、guided_inpaint、upscale、layer_split、flux2_concept、flux2_edit | `refactor/phase5.2-image-tasks-runner-b` `2d1e173` | 可以合併（25 輪） |

5.1 被擋下的原因：省略 `--seed` 時 slot 留著 `"auto"`，`resolve` 再用 32-bit 抽一次，和 builder 的一次 48-bit 對不上。`1dd86fa` 在填 slot 前呼叫一次 `image_graphs.seed_or_random`。傳入的 0 保持 0。

缺檔時的行為：

- SDXL、三個 control task、layer_split、FLUX.2：template 不在就 SystemExit。
- sd15 的 concept、icon_asset、refine、inpaint、guided_inpaint、upscale：目錄不在就退回 builder。

5.1 在 `b35d3e3` 上回報 discover 573 OK。`1dd86fa` 之後只跑了 `tests/test_image_task_template.py`（7 OK），沒有再跑完整 discover。5.2 實作者回報 discover 580 OK，以及 `test_image_task_template.py` 13、`test_generate.py` 67、`test_image_template_equivalence.py` 4、`test_templates.py` 58、`test_neutral_wording.py` 3、`test_doc_links.py` 5。5.2 的審查本身沒有執行測試。

主 repo 的本地 `refactor/phase5.1-image-tasks-runner-a` 已快轉到 `1dd86fa`，與 origin 相同。

### 第 6 階段：影片 template、task 切換、recipe

影片模型 pin 的決定：一份 graph，凍結成 `video_config=None` 時 builder 寫入的檔名。`platforms.windows-cuda` 必須和頂層 pin 相同。不為 macos-mps 另寫一套檔名。ADR：[影片模型 pin 不按平台分 graph](../decisions/2026-10-08-video-model-pins.md)。官方 upstream 只記了兩份：`video/wan/img2video` 對 `video_wan2_2_5B_ti2v`，`video/wan/pose-drive-canny` 對 `video_wan2_2_5B_fun_control`。其餘 `kind` 是 none。18 份都還是 draft。

| 項目 | 交了什麼 | 分支與 tip | 審查 |
|---|---|---|---|
| 6.1 | 影片 graph golden | 含在 `e7b0a02`，tip 見 6.2 | 可以合併 |
| 6.2 | 18 份影片 template，加上 catalog | `feat/phase6.2-video-on-stack` `b240e74` | 可以合併 |
| 6.3 | img2video、fx_loop、transition、clip_extend、camera_move、character_video、pose_drive 改填 template。golden json 沒改 | `refactor/phase6.3-video-tasks-runner` `f6b3c75` | 可以合併。內容審查 pending |
| 6.4／6.5 | recipe：多步驟、確認點、可續跑。`_drafts/` 不會被一般流程撿到 | `feat/phase6.4-recipes-on-stack` `132201f` | 第一次需要修改，修復後可以合併 |

6.3 的對應：Wan 的 img2video、fx_loop、transition、clip_extend、camera_move 都用 `video/wan/img2video`（尾幀不寫進 graph）。H3 沒有尾幀用 `video/h3/img2video`，有尾幀用 `video/h3/img2video-last`。pose_drive 用 `video/{backend}/pose-drive-{canny|pose|depth}`。character_video 用 `video/h3/character-video-{張數}`。

6.3 實機各跑一次。圖是 `C:\Users\XU\ComfyUI\input\0af67d78401a4df6b3ed576c91fdc80f-000.png`。prompt 是 `a small stone token slowly rotates, plain background`。duration 2，seed 202。跑之前 queue 是空的。

| 後端 | 檔 | 技術結果 |
|---|---|---|
| Wan | `output/verify-20261008-6.3/live-wan/smoke63wan_00001_.mp4` | 768×416，49 幀，24 FPS，h264，無音訊，yuv420p，135147 bytes，validation pass，約 32 秒，exit 0 |
| H3 | `output/verify-20261008-6.3/live-h3/smoke63h3_00001_.mp4` | 768×416，56 幀，24 FPS，h264，AAC stereo 32 kHz，188666 bytes，validation pass，約 53 秒，exit 0 |

跑完 queue 是 running=0、pending=0。不要重跑，不要 accept，不要用系統播放器開這兩支 mp4。

那次 `doctor --refresh` 把本機快照對上當時還在跑、尚未套用 8.2 的伺服器。8.4 部署並重啟之後要再 refresh。

Recipe 現況：

| recipe | 狀態 |
|---|---|
| `object-mark-inpaint` | 唯一不在 `_drafts/` 的 recipe，仍是 draft。實機會停在確認點，這次沒有跑完確認 |
| `idle-anchored-action` | `_drafts/`，`executable: false`。走 `video/h3/img2video-last` |
| `prop-swap` | `_drafts/`，`executable: false`。走 `video/h3/pose-drive-canny` |
| `fx-alpha-export` | 本機 vfx，不經 ComfyUI。dry-run 仍顯示來源字串 `{inputs.method}`，執行時才展開 |

6.4 被擋下的原因：整段剛好是一個 `{...}` 參考時要保留原型別（seed 仍是整數），前後還有文字時才把參考代成字串。第一版的正則兩頭都錨死，嵌在路徑或指令裡的參考不會被代換，也不會報錯。`132201f` 修好。dry-run 仍印來源字串，這是審查接受的行為。`tests/test_recipes.py` 19 OK。

### 第 6′ 階段：工具整併

分支 `refactor/phase6p-tools-on-stack`，tip `39f669e`。審查可以合併。只做過 deploy dry-run，沒有 `deploy --yes`。

| commit | 內容 |
|---|---|
| `ef70dfe` | 色相、遮罩、影片讀寫改呼叫同一份實作 |
| `e7d8ea4` | `vfx_alpha_tools.py` 拆成 `vfx_alpha` 套件。`gameart.py vfx` 的子指令不變。套件會部署，`benchmark_birefnet` 不部署 |
| `cab2f3a` | 物件組裝改 Pillow，BiRefNet 留在 repo |
| `39f669e` | 物件組裝頁面改成純 Pillow 現況 |

`scene`／`sheet`／`pattern` 不再需要 ComfyUI。`--comfy-url`、`--config`、`--timeout` 仍接受，但不使用。ADR 在該分支的 `docs/knowledge/decisions/2026-10-08-local-design-and-birefnet.md`。

### 第 7 階段：catalog、能力偵測、擴充協議

| 項目 | 交了什麼 | 分支與 tip | 審查 |
|---|---|---|---|
| 7.1 | 從 `template.json` 產生 `templates/catalog.json` 與能力索引頁。檔頭標自動產生、勿手改。圖片與影片 template 落地後各重產一次 | `feat/phase7.1-catalog` `37e156d`，並含在 `ab6189c`、`b240e74` | 可以合併 |
| 7.2 | `detect_video_capabilities` 增加頂層 `template_capabilities`。`schema_version` 仍是 1。doctor 讀得到舊報告（沒有這個欄位也不報錯） | `feat/phase7.2-capability-detect` `00039a7` | 可以合併（20 輪）。審查沒有執行測試，也沒有連 ComfyUI |
| 7.3 | 18 個技能收成 6 個 | 未開始 | — |
| 7.4 | 擴充協議：使用者確認後，優先從官方範本派生，再標 draft、測試、實機、技術通過。文件裡的「不可臨場組 graph」改成引用這份協議 | `docs/phase7.4-extension-protocol` `5984301` | 可以合併 |

7.2 的判斷：一個能力只要有一份宣告它的 template 沒問題，`available` 就是 true。單一 template 的問題進 `reasons.by_template`。沒連上 `/object_info` 時不因此判不可用，註記是「節點未檢查」。sha256 只在 `--hash-models`。不要用這條分支覆寫使用者現有的 `video_capabilities.json`。這次 session 的 `doctor --refresh` 用的是 7.2 之前的偵測器，快照裡沒有 `template_capabilities`。

7.3 若開始，底要用 `39f669e`，技能頁才含 Pillow 的現況。收斂對照：

| 新技能 | 從哪些來 | 備註 |
|---|---|---|
| `game-art-brief` | game-art-workflow、game-art-edit-brief、game-art-initialize、project-knowledge | 新目錄 |
| `platform-image-gen` | 原頁留下 | |
| `comfyui-run` | art-gen、object-design、video-gen、character-animation、film、face-swap、video-layers、wan-animate、image-sweep | 新目錄 |
| `local-media-tools` | local-image-edit-tools | 新目錄 |
| `comfyui-extend` | new-tool-checklist、pipeline-review | 目錄現在不存在。7.4 的協議已經單獨交過 |
| `comfyui-install` | 原頁留下 | |

目錄維持扁平的 `skills/<name>/SKILL.md`。細節進 catalog 或 references。`AGENTS.md` 路由要改。走一遍的請求：icon、本機 inpaint、物件遮罩加 VACE、prop swap、Idle action、FX alpha、新節點提案。舊規則要有對照表。範圍大就拆成「先加新頁並轉址」和「再刪舊頁」。

### 第 8 階段：舊名稱退場，builder 與部署還沒做

定案是方案 2：直接移除別名，不用 Node Replacement。缺少新名稱就是缺少節點，錯誤文字是缺少節點，不是叫人重啟。ADR：[custom node 舊名稱直接移除](../decisions/2026-10-08-node-alias-exit.md)。8199 的對照實機沒有跑，也不必補。

| 項目 | 狀態 | 分支與 tip |
|---|---|---|
| 8.1 決定 | 已寫進堆疊上的 ADR。另有一條較早的草稿分支不要當底 | 決定在 `132201f` 裡；草稿分支 `7f8be0c` |
| 8.2 刪別名 | repo 裡已刪。未部署，未重啟。審查可以合併 | `refactor/phase8.2-remove-aliases` `dc1fd5c` |
| 8.3 刪 builder | 未開始。要等 5.1、5.2、6.3 都在即將部署的那條線上。先改還在呼叫 stub 的地方。golden 改由 template 維護 | — |
| 8.4 部署 | 未開始。queue 空了才做：deploy dry-run、`deploy --yes`、另外跑 `gameart.py verify-install`。範圍含 `templates/`。第三方 node 版本寫進 `docs/tested-versions.md`。重啟後再 `doctor --refresh` | — |

ComfyUI v0.34.0 曾在 `127.0.0.1:8188` 跑過實機。實機期間沒有硬砍、沒有呼叫 `/interrupt`、沒有清 queue。其後 8188 已由使用者停止，沒有另外要求就不要重開。舊的 UI workflow 要等 8.4 部署並重啟之後，才會變成缺少新節點。在那之前，已部署的那一份仍認舊名稱。`output/` 裡有 21 份舊的 API prompt，它們是紀錄，沒有 `_meta`。重啟之後若原樣再送，預期是 HTTP 400。使用者的 `Ch8_影片換臉_Server.json` 沒有改。

## 測試數字

這些數字各屬於一個 tip，不要寫成每一條分支都跑過同一輪。

| 數字 | tip |
|---|---|
| 交接頁基準：Ran 505、OK、skipped 0；verify-install 91/91 | 當時的 develop |
| discover 573 OK | `b35d3e3`（5.1 seed 修復之前） |
| `test_image_task_template.py` 7 OK | `1dd86fa`（沒有完整 discover） |
| discover 580 OK，以及 5.2 小節列出的單檔 | `2d1e173`（實作者回報） |
| `test_recipes.py` 19 OK，`test_doc_links.py` 5，`test_neutral_wording.py` 3 | `132201f` |
| 更早的一輪 567 | `b240e74` 那條 stack，不是各孤立 tip |

Python 是 `C:\Users\XU\ComfyUI\.venv\Scripts\python.exe`。完整測試先設 `$env:PYTHONPATH='tools_src;tests;.'`，再 `-m unittest discover -s tests`。單檔用 `python tests/test_x.py`。

## 還沒交的，以及建議順序

1. ~~整合分支~~：已完成。**整合線已完成（2026-10-08 17:20 台北）：** `integrate/phase3-8`。從 `132201f` 切出，依序 cherry-pick 6.3、6′、7.2、5.1、5.2（`-x`，新 commit，沒有 rebase），再收進本頁所在的文件 commit。8 個 commit 的 `git patch-id` 和原 commit 相同；5.2 只有 `image_from_template.py` 的 seed 衝突，另加 `1d65de7`：有 seed slot 才抽、省略時只抽一次 48-bit、明確的 0 保持 0。整合後完整測試 Ran 612、OK、skipped 0（本機證據：`output/verify-20261008-integrate/`）。
2. **7.3 技能收斂。** 用 6′ 當底，或等整合線含有 `39f669e` 再做。
3. **8.3 刪 builder。** 等整合線含有 5.1、5.2、6.3。
4. **8.4 部署與 verify-install。** queue 確認是空的之後。部署後重啟，再 `doctor --refresh`。
5. **SD1.5 template。** 要等 `dreamshaper_8.safetensors` 在磁碟上，並且 hash 是實測的。
6. **recipe 實機確認。** `object-mark-inpaint` 會停在確認點，等使用者看遮罩預覽。三條草稿維持 draft，等使用者同意才轉正。
7. **美術接受與平台驗證升格。** 維持 pending，等使用者自己下 `review accept|reject` 或 `validation approve`。

## 使用者現在可以做的決定

整合線 `integrate/phase3-8` 已經出現，要合併進 `develop` 就合併這一條。若先合併 `132201f`，得到的是 VACE、圖片與影片 template、recipe、catalog、擴充協議、以及 repo 裡已刪掉的舊節點別名；圖片 task、影片 task、Pillow 物件組裝、template 能力偵測都不在裡面。

不需要為了這份交付去做美術 accept，也不需要為了 8.1 再開一個 8199。8188 保持停止，直到使用者要求再啟動。下次要 queue 或 deploy 之前，先確認行程與 queue。

本機若還看得到、但沒有進 commit 的說明稿：`output/verify-20261008-4/pr-body.md`、`output/verify-20261008-6.2/pr-body.md`、`output/verify-20261008-6.3/pr-body.md`、`output/verify-20261008-6.4/pr-body.md`、`output/verify-20261008-6p/pr-body.md`。它們是當時準備的 PR 正文，PR 沒有開。
