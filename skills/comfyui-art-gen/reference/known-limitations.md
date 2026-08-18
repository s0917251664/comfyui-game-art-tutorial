# 已知限制

`skills/comfyui-art-gen/SKILL.md` 指向這裡——如實告知使用者,不要假裝能做到。

- 只有本機 SDXL 一條路線,Logo/中文字排版品質不會好
- **只在 SDXL 家族機器(`sdxl_high`/`sdxl`/`sdxl_light` tier)上驗證過。** 如果 `device_config.json` 的 `tier` 是 `sd15`(低 VRAM 機器,底模會自動換成 SD1.5 系列),`character_action`/`style_lock`/`pose_only` 這些用到 ControlNet 或 IPAdapter 的 task **目前會壞掉**——`generate.py` 裡這幾個模型檔名是寫死指向 SDXL 版本,沒有跟著 tier 換,直接跑會 shape mismatch。遇到 `sd15` tier 的機器,如實告知使用者這條路線還沒補上,不要假裝能動
- 需要角色/姿勢一致性的 task,沒有對應參考圖就不要硬做,結果不會有一致性
- `refine` 的顏色/材質改變幅度受 `--denoise` 影響很大,denoise 太低時強烈的顏色指令可能蓋不過原圖(這是參數特性,不是 bug,提醒使用者可以調高再試)
- **`--lora` 的觸發詞可靠度取決於訓練方式,不要假設「打觸發詞就一定觸發」。** 這個專案的訓練流程用 SDXL 官方建議的 `--network_train_unet_only`(只練 U-Net),實測發現單獨丟觸發詞、不搭配任何特徵描述詞時,效果不穩定;請使用者生圖時觸發詞旁邊還是搭配幾個關鍵特徵詞一起下,不要只丟一個詞賭它記得(細節見 `教學.md` 第 8 章)
