# 已知限制

`skills/comfyui-art-gen/SKILL.md` 指向這裡——如實告知使用者,不要假裝能做到。

- 只有本機 SDXL 一條路線,Logo/中文字排版品質不會好
- **只在 SDXL 家族機器(`sdxl_high`/`sdxl`/`sdxl_light` tier)上驗證過。** 如果 `device_config.json` 的 `tier` 是 `sd15`(低 VRAM 機器,底模會自動換成 SD1.5 系列),`character_action`/`style_lock`/`pose_only` 這些用到 ControlNet 或 IPAdapter 的 task **目前會壞掉**——`generate.py` 裡這幾個模型檔名是寫死指向 SDXL 版本,沒有跟著 tier 換,直接跑會 shape mismatch。遇到 `sd15` tier 的機器,如實告知使用者這條路線還沒補上,不要假裝能動
- 需要角色/姿勢一致性的 task,沒有對應參考圖就不要硬做,結果不會有一致性
- `refine` 的顏色/材質改變幅度受 `--denoise` 影響很大,denoise 太低時強烈的顏色指令可能蓋不過原圖(這是參數特性,不是 bug,提醒使用者可以調高再試)
- **`guided_inpaint` 的 `pose` 結構鎖定只到手腕/關節等級,不包含手指細節。** 目前用的 OpenPose ControlNet 抓的是身體骨架關鍵點,沒有手部細節模型,所以能大幅降低「武器整個浮空/變形」這類大結構崩壞,但沒辦法保證每根手指都精確——實測手套/手指邊緣偶爾還是會有點模糊,這是目前這條路線的已知上限,不是遮罩或 prompt 沒調好
- **`guided_inpaint` 的 `--appearance-ref` 抓的是參考圖的風格/色彩印象,不是逐像素複製圖案。** 實測丟一張像素化數位迷彩紋理當參考,結果變成同色系的條紋質感,不是精確複製那個像素圖案——不要跟使用者保證「會做出一模一樣的紋理」。另外遮罩邊界外側偶爾會被外觀參考圖的顏色牽動一起變化(實測緊鄰遮罩的衣領被牽動變色),遮罩要盡量貼合實際要換的區域
- **`guided_inpaint` 遮罩只要碰到肩章/臂章這類小圖案的位置,即使該處已經是空白布料,還是有機會被重新腦補出一個圖案。** 這不是 `guided_inpaint` 特有的問題,是 denoise=1.0 全自由生成的通病(見 `reference/masking.md`)——真的踩到就用小範圍 `inpaint` 單獨修那一小塊,不要擴大 `guided_inpaint` 的遮罩去將就它
- **`icon_asset` 的 `--appearance-ref` 如果參考圖本身帶有文字(例如成品截圖上印的按鈕文字),IPAdapter 有機會把文字的視覺印象一起帶進來,變成畫面裡一坨讀不出來的假字。** 2026-08-19 實測:拿一張中心按鈕寫著「SPIN NOW」的參考圖,`--appearance-weight` 用預設 0.8 時,產出的中心鈕上冒出「SPINE」這種殘留假字;把權重壓到 0.35 才穩定消失。原理跟 `--structure-ref` 鎖太緊會壓掉裝飾細節是相反方向的坑,但同樣建議:參考圖如果帶文字,`--appearance-weight` 從低值(0.3~0.4)開始試,不要直接用預設 0.8,而且负向詞的 `text`/`words`/`writing` 這幾個權重也要拉高(`(text:1.5)` 以上)才夠力壓下去
- **`icon_asset` 的 `--structure-ref` 能鎖住結構/顏色配置,但鎖不住精細裝飾細節(鑲花雕紋這類需要額外邊緣線條的裝飾)。** 2026-08-19 實測(轉盤放射狀等分圖示):denoise 從 0.55 調到 0.85,結構/顏色始終穩定,質感也持續提升(從平面到有光澤球面感),但雕花/雕紋這類細節不管怎麼調都沒有明顯出現——推測是 Canny ControlNet 鎖邊緣的同時也壓抑了「多畫額外線條」,是這個做法的結構性限制,不是 denoise 沒調好,不要跟使用者保證「結構鎖住又能有精細雕花」兩者都要,細節見 `reference/structure-ref.md`
- **沒有自動語意分割模型,`layer_split` 的圖層邊界一定要使用者手動畫遮罩,不支援「AI 自己判斷邊界」。** 沒有裝 SAM 這類分割模型,`layer_split` 純粹依賴 `--mask` 指定的遮罩檔案裁切透明度,不會自己找出畫面裡的物件邊界。高度重複的元素(例如轉盤的每個分區隔板)也不建議靠這個 task 逐一切割,原因跟怎麼處理見 `reference/layered-assets.md`
- **`--style` 只在 SDXL 家族機器(`sdxl_high`/`sdxl`/`sdxl_light` tier)生效,`sd15` 機器會直接報錯拒絕執行。** 三個風格候選(Juggernaut XL/Illustrious XL/Pony Diffusion V6 XL)都是 SDXL 架構,跟 `sd15` 的 ControlNet/IPAdapter 對不上,不像預設 `CKPT` 那樣有 sd15 對應版本
- **`--rating` 只在 `--style anime`/`illustration` 時有效,`--style realistic` 或沒給 `--style` 會直接報錯拒絕執行。** Juggernaut XL(`realistic`)跟預設底模沒有分級標籤訓練慣例,給了 `--rating` 也不會有任何效果,所以直接擋下來,不要讓它靜默沒作用
- **`--style` + `--lora` 同時使用時,LoRA 觸發效果沒有實測驗證過會不會打折。** 這個專案訓練 LoRA 用的底模是裝機時鎖定的預設 checkpoint(見 `教學.md` 第 8 章),`--lora` 的權重是針對那顆底模的權重空間練的——換成 `--style` 指定的其他 SDXL 微調版後,LoRA 觸發詞/特徵還原效果可能跟著變化,如實告知使用者這個組合還沒驗證過,不要假設兩者疊加一定跟平常一樣穩
- **`--lora` 的觸發詞可靠度取決於訓練方式,不要假設「打觸發詞就一定觸發」。** 這個專案的訓練流程用 SDXL 官方建議的 `--network_train_unet_only`(只練 U-Net),實測發現單獨丟觸發詞、不搭配任何特徵描述詞時,效果不穩定;請使用者生圖時觸發詞旁邊還是搭配幾個關鍵特徵詞一起下,不要只丟一個詞賭它記得(細節見 `教學.md` 第 8 章)
