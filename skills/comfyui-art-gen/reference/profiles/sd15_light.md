# sd15_light 調校筆記（轉址）

內容在 PR 7.3（2026-10-08）搬到 [skills/comfyui-run/references/comfyui-art-gen/reference/profiles/sd15_light.md](../../../comfyui-run/references/comfyui-art-gen/reference/profiles/sd15_light.md)。

這個轉址檔保留的原因：`tools_src/comfyui_pipeline/profiles/sd15_light.json` 的 `notes_ref` 指向這裡，而 `notes_ref` 算在 profile 內容 hash（`profile_content_sha256`）裡；改路徑會讓 hash 和既有 smoke 驗證報告對不上。這個資料夾不是技能（沒有 SKILL.md）。
