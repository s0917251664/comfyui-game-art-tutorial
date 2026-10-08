---
type: maintenance
status: current
---
# 重構進度中斷點（2026-10-08）

下一個 agent **先讀這一頁**，再讀 [重構交接](restructure-handoff.md) 的規則和原始計畫。給人讀的完整交付脈絡在[重構交付脈絡 2026-10-08](restructure-delivery-2026-10-08.md)。規則以交接頁為準；做到哪裡以這一頁為準。兩者都讓路給已經生效的[決策](../DECISIONS.md)。

5.1、5.2、7.2 的審查都是可以合併，而且三條分支都已 push。沒有開 PR，沒有 merge 到 `develop`。

## 接手時從這裡開始

**整合線已完成（2026-10-08 17:20 台北）：** `integrate/phase3-8`。從 `132201f` 切出，依序 cherry-pick 6.3、6′、7.2、5.1、5.2（`-x`，新 commit，沒有 rebase），再收進本頁所在的文件 commit。8 個 commit 的 `git patch-id` 和原 commit 相同；5.2 只有 `image_from_template.py` 的 seed 衝突，另加 `1d65de7`：有 seed slot 才抽、省略時只抽一次 48-bit、明確的 0 保持 0。整合後完整測試 Ran 612、OK、skipped 0（本機證據：`output/verify-20261008-integrate/`）。

下一手是 7.3，底用 `integrate/phase3-8`。8.3、8.4 還沒開始。

審查方式改了：使用者在 2026-10-08 要求不再用 grok 審核，改由實作的 agent 自己 review（範圍、正確性、測試、第 2 節規則），結果寫進 commit 或證據資料夾。

## 不要做

- 不開 GitHub PR，不 merge 到 `develop`，不 force-push，不 rebase 已經 push 的 SHA。要改就加新 commit。
- 不 commit 未追蹤的 `HANDOFF-phase3-8.md`。不 commit `third_party/claude-obsidian/WIKI.md` 的刪除。那是工作區裡多餘的變動。
- 不 `review accept|reject`，不 `validation approve`。`content_review` 維持 pending。
- 不下載 `dreamshaper_8.safetensors`，不發明 SD1.5 的 hash，不寫 `templates/image/sd15/`。
- 不重跑已經通過的實機（3.4、3.5、6.3）。不把 draft recipe 升成 `technical_pass`。
- 不硬砍 ComfyUI，不呼叫 `/interrupt`，不清 queue。8188 已由使用者停止（背景任務 `01a11a78-a3b6-73e2-9286-b2f7fefc0c54`）。沒有另外要求就不要重開。停掉之前那一輪實機結束時 queue 是空的；下次要 queue 或 deploy 前再確認行程與 queue。
- 5.1 與 7.2 的工作區仍有未追蹤的 `HANDOFF-phase3-8.md` 和 `WIKI.md` 刪除。不要把這兩項加進任何 commit。
- 不 `deploy --yes`。8.2 只改了 repo，本機已部署的節點仍是舊名稱。8188 目前沒有在跑。
- 文件引用本機證據只用純文字路徑，不寫成連結。

## 線怎麼疊

`origin/develop` 現在是 `5f1d31e`（Merge pull request #9，交接文件進 develop）。交接頁第 1 節寫的 `2dbdeeb` 是計畫開寫時的基準。

功能還沒收成一條線。`origin/feat/phase6.4-recipes-on-stack` = `132201f` 這條上面已經有：3.1–3.5、3.4 實機、4 的圖片 template、6.1–6.2、6.4–6.5、7.1、7.4、8.2。

下面這些 **不在** `132201f` 裡面，之後用新 commit cherry-pick，不要 rebase：

| 分支 | tip | 分岔點 | 遠端 |
|---|---|---|---|
| `refactor/phase6.3-video-tasks-runner` | `f6b3c75` | 父 commit `dbf95fd` | 已 push |
| `refactor/phase6p-tools-on-stack` | `39f669e`（`ef70dfe`、`e7d8ea4`、`cab2f3a`、`39f669e`） | 父 commit `dbf95fd` | 已 push |
| `feat/phase7.2-capability-detect` | `00039a7` | 父 commit `dbf95fd` | 已 push |
| `refactor/phase5.1-image-tasks-runner-a` | `1dd86fa`，父 commit `b35d3e3` | `b35d3e3` 的父 commit 是 `b240e74` | 已 push |
| `refactor/phase5.2-image-tasks-runner-b` | `2d1e173`，父 commit 也是 `b35d3e3` | 同上 | 已 push |

`132201f` 比 `dbf95fd` 多一個 commit：`132201f` 本身（recipe 內嵌參考）。6.3、6′、7.2 都是從 `dbf95fd` 長出去的。5.1 和 5.2 是從 `b240e74` 長出去的，recipe 那三個 commit 它們都沒有。

預期衝突：

- `templates/README.md`：`132201f` 和 6.3／6′／7.2 都會碰到。
- `tools_src/comfyui_pipeline/image_from_template.py` 的 seed：5.2 疊上 `1dd86fa` 時會衝突。兩邊都要留下「省略 `--seed` 只抽一次，而且用 builder 的 48-bit；明確傳入的 0 保持 0」。不要把 seed 留成 template 的 `"auto"`，否則 `resolve` 會再抽一次 32-bit。

主 repo 的本地 `refactor/phase5.1-image-tasks-runner-a` 已快轉到 `1dd86fa`，與 origin 相同。

## 已 push 的 origin 分支

2026-10-08 用 `git ls-remote` 對過。SHA 是短碼。

| 階段 | 分支 | tip | 審查 |
|---|---|---|---|
| 3.1 | `fix/phase3.1-device-config-warning` | `537469f` | 可以合併 |
| 3.2 | `feat/phase3.2-template-official-fields` | `78b28f5` | 可以合併 |
| 3.3 | `refactor/phase3.3-runner-generated-inputs` | `9119b1d` | 可以合併 |
| 3.4 離線 | `feat/phase3.4-wan-vace-template` | `6f7b926` | 可以合併 |
| 3.4 實機 | `feat/phase3.4-windows-cuda-pass` | `777d75a` | 可以合併。`content_review` pending。不要重跑 |
| 3.5 | `refactor/phase3.5-video-inpaint-adapter` | `fc99095` | 可以合併。`content_review` pending |
| 4.1–4.3 與 catalog | `feat/phase4-image-on-stack` | `ab6189c` | 可以合併。沒有 SD1.5 |
| 6.1–6.2 與 catalog | `feat/phase6.2-video-on-stack` | `b240e74` | 可以合併。18 份影片 template 仍是 draft |
| 6.3 | `refactor/phase6.3-video-tasks-runner` | `f6b3c75` | 可以合併。實機見下方。`content_review` pending |
| 6.4–6.5 | `feat/phase6.4-recipes-on-stack` | `132201f` | 第一次需要修改，修復後可以合併 |
| 6′.1–6′.3 | `refactor/phase6p-tools-on-stack` | `39f669e` | 可以合併。只做過 deploy dry-run |
| 7.1 | `feat/phase7.1-catalog` | `37e156d` | 可以合併。後續 tip 也含這份產生器 |
| 7.4 | `docs/phase7.4-extension-protocol` | `5984301` | 可以合併 |
| 8.1 | `docs/phase8.1-node-alias-exit` | `7f8be0c` | 決定是直接移除別名。8199 對照沒有跑，也不必補 |
| 8.2 | `refactor/phase8.2-remove-aliases` | `dc1fd5c` | 可以合併。未 deploy |

4.1 採用方案 A：一種結構組合一份凍結 graph。ADR 在 `docs/knowledge/decisions/2026-10-08-image-template-variants.md`。72 份 SDXL，加 `image/layer-split`，加 FLUX.2 concept／edit，共 75。`video/wan-vace/inpaint` 已是 `technical_pass`（windows-cuda）；`macos-mps` 仍是 untested。

## 5.1、5.2、7.2 已 push

`git ls-remote` 對過：`1dd86fa`、`2d1e173`、`00039a7`。主 repo 若本地的 `refactor/phase5.1-image-tasks-runner-a` 仍停在 `b35d3e3`，以 `origin` 的 `1dd86fa` 為準，先 `git fetch origin`。

### 5.1 種子修復：可以合併，已 push

- 分支 `refactor/phase5.1-image-tasks-runner-a`
- tip `1dd86fa`（訊息：省略圖片 seed 時只抽一次，沿用 builder 的範圍）
- 工作區：`C:\Users\XU\.grok\worktrees\tools-comfyui-game-art-tutorial\subagent-01a11a9c-81a6-7ec1-92b0-e3cf56b62788`
- 這個工作區是髒的：`D third_party/claude-obsidian/WIKI.md`、`?? HANDOFF-phase3-8.md`。不要加進 commit。
- 審查 JSON（本機證據：`output/verify-20261008-5.1/grok-rereview.json`，在上面那個工作區裡）
- `stopReason=end_turn`，9 輪。結論：可以合併。
- 第一次審 `b35d3e3` 是需要修改，只擋省略 `--seed`。`1dd86fa` 修的是那一件。
- 該工作區在 `b35d3e3` 上回報 discover 573 OK。`1dd86fa` 之後只跑了 `tests/test_image_task_template.py`（7 OK），沒有再跑完整 discover。
- 六個 task：concept、icon_asset、refine、character_action、pose_only、style_lock。SDXL 與三個 control task 缺 template 就 SystemExit。sd15 的 concept／icon_asset／refine 在目錄不存在時回 `None`，task 仍走 builder。

### 7.2 能力偵測：可以合併，已 push

- 分支 `feat/phase7.2-capability-detect`
- tip `00039a7`，父 commit `dbf95fd`
- 工作區：`C:\Users\XU\.grok\worktrees\tools-comfyui-game-art-tutorial\subagent-01a11aa6-ad8d-7f70-b8e7-1baa2a3cf023`
- 同樣不要 commit WIKI 刪除和 `HANDOFF-phase3-8.md`。
- 審查 JSON（本機證據：`output/verify-20261008-7.2/grok-review.json`）
- `stopReason=end_turn`，20 輪。結論：可以合併。審查沒有執行測試，也沒有連 ComfyUI。
- 行為：`schema_version` 仍是 1；新增頂層 `template_capabilities`。略過 `image_generation` 和底線開頭的路徑段。`available` 為真的條件是至少一份宣告該能力的 template 沒問題。沒連上 `/object_info` 時不因此判不可用，`reasons.note` 是「節點未檢查」。sha256 只在 `--hash-models`。doctor 要容忍舊報告沒有這個欄位。
- 不要用這條分支寫使用者的 `video_capabilities.json`。寫檔仍要原本的 `--out`，既有檔要 `--overwrite`。
- 這次 session 在主 repo 跑過的 `doctor --refresh` 用的是 7.2 之前的偵測器，快照裡沒有 `template_capabilities`。

### 5.2：可以合併，已 push

- 分支 `refactor/phase5.2-image-tasks-runner-b`
- tip `2d1e173`，父 commit `b35d3e3`（不含 `1dd86fa`，但 seed 只抽一次已經在這個 commit 裡自己寫過）
- 工作區：`C:\Users\XU\.grok\worktrees\phase5.2`（主 repo 的 linked worktree）
- 審查 JSON（本機證據：`output/verify-20261008-5.2/grok-review.json`）
- `stopReason=end_turn`，25 輪。結論：可以合併。審查沒有執行測試。
- 實作者回報：`test_image_task_template.py` 13 OK、`test_generate.py` 67 OK、`test_image_template_equivalence.py` 4 OK、`test_templates.py` 58 OK、`test_neutral_wording.py` 3 OK、`test_doc_links.py` 5 OK、discover 580 OK。這是 5.2 工作區的回報，不是這頁重跑的。
- 六個 task：inpaint、guided_inpaint、upscale、layer_split、flux2_concept、flux2_edit。SD1.5 目錄不存在就退回 builder。SDXL、layer_split、FLUX.2 缺檔是 SystemExit。不要呼叫 `runner.run()`。不要改 golden json。
- 疊上 `1dd86fa` 時，`image_from_template.py` 的 seed 寫法會衝突。兩邊都要留下「只抽一次、0 仍是 0」。

## 實機證據（不要重跑，不要 accept）

3.5 比較已在磁碟上（本機證據：`output/verify-20261008-3.5/live-compare.txt`）。規格對得上較早的輸出，檔案 hash 不同。

6.3 這次 session 各跑一次。先確認 queue 空，再 `doctor --refresh`。那次 refresh 把本機快照對上 **當時還在跑、尚未套用 8.2 的** 伺服器。8.4 部署並重啟之後要再 refresh。

指令從 6.3 工作區跑，`--config` 指主 repo 的 `local_config.json`。圖是 `C:\Users\XU\ComfyUI\input\0af67d78401a4df6b3ed576c91fdc80f-000.png`。prompt 是 `a small stone token slowly rotates, plain background`。duration 2，seed 202。

| 後端 | 檔 | 技術結果 |
|---|---|---|
| Wan | `output/verify-20261008-6.3/live-wan/smoke63wan_00001_.mp4` | 768×416，49 幀，24 FPS，h264，無音訊，yuv420p，135147 bytes，validation pass，約 32 秒，exit 0 |
| H3 | `output/verify-20261008-6.3/live-h3/smoke63h3_00001_.mp4` | 768×416，56 幀，24 FPS，h264，AAC stereo 32 kHz，188666 bytes，validation pass，約 53 秒，exit 0 |

跑完 queue 是 running=0、pending=0。工作區會印既有的「找不到 `tools_src/device_config.json`」警告，生成仍用 `--config`。

`doctor --refresh` 同時確認 `sd15_light` 底模未安裝。checkpoints 裡有 Illustrious-XL、juggernautXL、ponyDiffusion、sam3.1_multiplex、`sd_xl_base_1.0`。沒有 `dreamshaper_8.safetensors`。

## 還沒開始

依這個順序。每一項仍要：實作、測試、grok plan-mode 審查、結論是可以合併才 push。不開 PR。使用者自己 merge。

1. ~~整合分支~~：已完成，見「接手時從這裡開始」。
2. **7.3 技能收斂**。底要用已含 Pillow 說明的 6′（`39f669e`），否則技能頁會和 6′ 衝突。18 個技能收成 6 個，目錄維持扁平 `skills/<name>/SKILL.md`：
   - `game-art-brief` ← game-art-workflow、game-art-edit-brief、game-art-initialize、project-knowledge
   - `platform-image-gen` 留著
   - `comfyui-run` ← art-gen、object-design、video-gen、character-animation、film、face-swap、video-layers、wan-animate、image-sweep
   - `local-media-tools` ← local-image-edit-tools
   - `comfyui-extend` ← new-tool-checklist、pipeline-review（這個目錄現在還不存在；7.4 協議已經單獨 push，不要重寫）
   - `comfyui-install` 留著
   細節放到 catalog 或 references。更新 `AGENTS.md` 路由。用這些請求走一遍，記下打到哪個 skill、哪份 template：icon、本機 inpaint、物件遮罩加 VACE、prop swap、Idle action、FX alpha、新節點提案。舊規則要有對照表。跑連結測試和中性用語測試。範圍大就拆兩段：先加新頁並把舊頁改成轉址，再刪舊頁。
3. **8.3** 刪已被 template 取代的 builder。前提是 5.1、5.2、6.3 都在即將部署的那條整合線上。先修還在呼叫剩餘 stub 的地方。golden 改由 template 維護。
4. **8.4** queue 確認是空的之後：`deploy` dry-run，再 `deploy --yes`，再另外跑 `gameart.py verify-install`，數字用實測的。部署範圍含 `templates/`。第三方 node 版本寫進 `docs/tested-versions.md`。重啟後再 `doctor --refresh`。3.5 的部署副本若找不到 `templates/` 會 SystemExit。不要為了 8.1 去佔 8188，也不要另開 8199，除非使用者另外要求。

草稿 recipe 維持 draft，等使用者同意才升狀態。`object-mark-inpaint` 的實機確認點沒跑（流程會停在 confirm）。idle-anchored-action 和 prop-swap 仍是 `executable: false`。fx-alpha-export 是本機 vfx，不經 ComfyUI。

## 測試數字不要混用

| 何時 | 數字 | 在哪個 tip |
|---|---|---|
| 交接頁基準 | Ran 505、OK、skipped 0；verify-install 91/91 | 當時的 develop |
| 5.1 實作者 | discover 573 OK | `b35d3e3`，seed 修復之前 |
| 5.1 修復後 | `test_image_task_template.py` 7 OK | `1dd86fa`，沒有完整 discover |
| 5.2 實作者 | discover 580 OK，以及上一節列出的單檔 | `2d1e173` |
| 6.4 修復後 | `test_recipes.py` 19 OK，`test_doc_links.py` 5 OK，`test_neutral_wording.py` 3 OK | `132201f` |

有一份更早的 567 是 `b240e74` 那條 stack 上的，不要寫成各孤立 tip 都跑過。

Python：`C:\Users\XU\ComfyUI\.venv\Scripts\python.exe`。完整測試先設 `$env:PYTHONPATH='tools_src;tests;.'`，再 `-m unittest discover -s tests`。單檔用 `python tests/test_x.py`。不要寫成 `python -m unittest tests.test_x`（venv 裡另有一個頂層 `tests` 套件）。不要用 `python -c`。

## 審查怎麼跑

只讀、plan mode。不要讓 grok 跑 shell，也不要讓它讀 repo 以外的檔。

```text
cmd /c "chcp 65001 >nul & C:\Users\XU\.grok\bin\grok.exe --permission-mode plan --max-turns 300 --output-format json --prompt-file <prompt.md> > <out.json>"
```

不要用 PowerShell 的 `>` 或 `Set-Content` 接 grok 的 stdout（會變成 UTF-16）。`stopReason=end_turn` 才算跑完。最後一行必須是 `VERDICT: 可以合併` 或 `VERDICT: 需要修改`。程序還在跑時 JSON 可能是 0 byte，不要解析。程序結束後用 `C:\Users\XU\ComfyUI\.venv\Scripts\python.exe output\grok_result.py <json>` 讀結論（檔案有 BOM 會失敗）。

先前寫過、沒有開 PR 的說明稿若還在本機：`output/verify-20261008-4/pr-body.md`、`output/verify-20261008-6.2/pr-body.md`、`output/verify-20261008-6.3/pr-body.md`、`output/verify-20261008-6.4/pr-body.md`、`output/verify-20261008-6p/pr-body.md`。
