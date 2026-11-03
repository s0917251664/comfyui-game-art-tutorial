---
type: reference
status: experimental
---
# 外部免費素材庫（臉、服裝、姿勢）

來源：Block 客（blocktempo）2026-11-01 報導〈佛心 AI 素材庫〉，日本創作者あぎ（Agi）公開的三個素材庫。這是新聞轉述，**條款細節以三個站的原始頁面為準**；「在本專案怎麼用」一節已於 2026-11-02 做過一輪小規模實測（見「實測紀錄」），結論只在該範圍內成立。

## 可用結論（先讀這裡）

2026-11-02 在本機 Windows 實測五輪（下方「實測紀錄」有細節與證據路徑）。全是小樣本的目視技術結果，不是美術接受；輸出仍走 [R1](../rules/candidate-review.md) 逐張驗收。

**可以用**

- **已有角色圖，只想改姿勢或手掌方向 → `generate.py flux2_edit`（`image/flux2/edit`）**，約 30 秒／張，臉、髮、衣服最能保住，也最符合「改圖不重算」。遊戲風 34／36（94%）、動漫 4 風格 79／96（82%）、寫實 17／23（74%，要挑圖）。條件：來源圖全身、單人、背景單純；一次只改一個動作；提示寫具體肢體（肘彎曲、掌心朝向；掌心朝鏡頭沿用「stop gesture」說法）；每個動作至少出 3 個 seed 挑；逐張看手、持物、髮型、服裝有無被重畫。提示格式：`Change only the pose: …  Keep the face, hairstyle, clothes, art style and the plain background unchanged.`
- **要用姿勢庫的姿勢（不在乎臉）→ `pose_only --control-backend union --control-type depth`**，搭明確服裝 prompt、負面詞排除裸色、`--pose-strength 0.6`；姿勢遵守 16／16。姿勢庫的深度圖可直接當 `--pose-ref`。

**動作選單（`gameart.py pose-edit`）**

不會寫提示的人用這個：`python gameart.py pose-edit list` 看選單，`python gameart.py pose-edit run --action <id> --image <角色圖>` 執行（先加 `--preflight` 或 `--dry-run` 檢查）。內建 8 個動作與已實測的提示句型、固定尾句「Keep the face, hairstyle, accessories, clothes, art style and the plain background unchanged.」，預設 seed 7／21／99 各跑一次，輸出 `contact_sheet.png`（原圖＋各 seed）與 `pose_edit.result.json`（提示、seed、每張檢查提醒：手、持物數量、髮型與服裝是否被重畫），內容審查一律 `pending`，不自動 accept。

| 動作 id | 動作 | 已知失敗（見實測紀錄） |
|---|---|---|
| `raise_hand` | 舉手 | 另一隻手也跟著舉 |
| `walk` | 走路 | 厚塗風服裝被重畫 |
| `cross_arms` | 抱胸 | 少見 |
| `look_back_wave` | 回頭揮手 | 臉被擋，身分無法判斷 |
| `hold_staff` | 雙手持杖（持物） | 原道具留著造成兩根、只一手握 |
| `point` | 單手指向 | 少見 |
| `look_down` | 低頭 | 少見 |
| `palm_to_camera` | 掌心朝鏡頭 | 變成雙手合十或橫伸（沿用 stop gesture 句型） |

2026-11-03 在 windows-cuda 實機跑 `raise_hand`、`cross_arms`、`palm_to_camera` 各 3 seed（動漫風來源圖），9／9 完成且姿勢目視達成，單張約 29 秒；證據 `output/pose-face-test/pose_edit_live/`、對照圖 `show/k_pose_edit_live.png`。底層 template `image/flux2/edit` 平台狀態仍是 `untested`（要不要升 `technical_pass` 由使用者決定），所以實跑要加 `--allow-unverified-platform`，結果只當技術試驗。

**自訂與組裝（不限這 8 個動作）**

- **自訂一句**：`pose-edit run --image <圖> --custom "the character waves with the left hand and looks to the right."`。工具自動加固定前綴與保留尾句；描述寫一句英文、一次一個大動作。
- **零件組裝**：`--part 右手=舉高 --part 頭=朝左 --part 視線=往左看`（零件：left_hand、right_hand、palm、head、gaze、feet、legs、body，也可寫中文 左手、右手、手掌、頭、視線、腳步、腿、身體）；內容寫英文，或常見中文（舉高、放下、叉腰、朝鏡頭、朝下、朝左、朝右、往下看、向前跨步…會換成英文句型）。
- **連續編修**：`--action raise_hand --part 頭=朝左`（也可 `--action a,b`，用 `--then` 分步）：上一步挑出的圖當下一步來源；每步各出 seed 與對照圖，`--pick 21` 指定上一步用哪個 seed，沒給就自動用第一張成功的（只是接續用，不是接受）。最多 4 步，建議不超過 2～3 步，偏移會累積。
- **微調**：`--seeds 7,21` 或 `--count 4`（seed 池前 N 個）；`--keep-extra "the blue scarf"` 額外保留；`--avoid "a second staff"` 不要出現。
- **看提示再執行**：先加 `--dry-run`，會印出每一步組好的完整英文提示，可以微調再跑。
- **存成自己的選單**：`pose-edit save --id wave_left --label 左手揮手 --custom "..."`，寫進 repo 根目錄的 `pose_edit_actions.local.json`（不進版控），之後 `pose-edit list` 會列出，也能 `--action wave_left` 使用。
- 2026-11-03 實機：自訂「左手揮手並看右邊」3 seed、`舉手` 後接 `頭=朝左、視線=往左看` 兩步連續編修（`--pick 21`），都 completed；證據 `output/pose-face-test/pe_custom/`、`pe_chain/`，對照圖 `show/l_pose_edit_custom_chain.png`。目視：揮手與頭部轉向多數達成；**左右手要小心**——模型多半把「左手」畫成畫面左側那隻手（角色自己的右手），要指定左右時看一眼結果，必要時改寫成 "the hand on the left side of the image"；自訂「看右邊」3 張都沒有真的轉向（臉仍朝前）。技術結果，沒有驗收。

**不建議**

- `pose`（OpenPose）抓無臉人偶（抽不到骨架；DWPose 只 1／4）、線稿人偶配 `canny`（線條畫進成品）、人臉庫特寫當 `--character-ref`（臉與髮型不穩）、Qwen-Image-Edit 2511 做姿態（442 秒、臉糊、複製人偶體型）。
- 兩段式重畫臉（先生圖再 `guided_inpaint` 重畫頭部）只有正面頭勉強成立，側臉失敗。

**還沒解決或沒驗證**

- 保臉：轉側面或背面時身分無法判斷，沒有量化比對。
- 手指數量與細節：沒有逐指檢查；MeshGraphormer 手部深度偵測 11／16，但局部重繪沒做。
- 姿勢庫沒有走、跑、揮擊類動作；服裝庫沒測；連續多格動畫一致性沒測。

## 三個素材庫

| 庫 | 內容 | 授權（依報導） | 連結 |
|---|---|---|---|
| 人臉 | 1,499 張（893 正面臉、606 造型照），Midjourney 生成；正面臉為脖子以上構圖 | CC0，商用與修改可，不必標註；請求勿轉載圖片本身；禁止冒充真人 | https://ai-portrait-gallery.pages.dev/ |
| 服裝 | 1,407 張純服裝圖（無人物），文字生成 | 非 CC0；禁止再散布、轉售圖片（含加工後）與批次下載；用它當參考做出的作品可商用；不保證不侵權；禁止用於真人或未成年 | https://ai-costume-gallery.pages.dev/ |
| 姿勢 | 288 種姿勢 × 5 角度（1,439 張深度圖，無臉灰色人偶）；另有人偶線稿版 | 同服裝庫 | 深度圖 https://ai-pose-depth-gallery.pages.dev/ ；線稿 https://ai-pose-gallery.pages.dev/ |

已知瑕疵（站方或報導自述）：服裝圖有細節錯誤（如釦子兩側都有）；姿勢圖的手指與交疊腿邊界較弱。

## 在本專案怎麼用（2026-11-02 實測觀察；範圍見下節）

- **姿勢深度圖 → `--control-type depth`**：深度圖可直接當 `--pose-ref`，不必另外抽取；兩個姿勢（雙手扠腰、側身展臂）都被遵守，不論帶不帶角色參考。限制：深度圖是無衣裸色人偶，輸出容易照人偶體型生出內衣／緊身衣，且 prompt 寫了衣服也會被壓過，要自己控制 prompt 與負面詞並逐張看。
- **線稿版 → `canny`**：姿勢被遵守，但人偶線條與關節球會被當成真實邊緣畫進成品（成品像畫了線的假人），不能直接當乾淨姿勢控制；深度圖餵 `canny` 同樣不乾淨（頭髮亂散）。
- **`pose`（OpenPose）**：線稿人偶與深度圖人偶都**抽不到有效骨架**——成品退回 prompt／角色參考本身，變成與姿勢無關的臉部特寫。無臉人偶不能用 `pose`。
- **人臉 → 角色一致性參考**：人臉庫圖是脖子以上的特寫，當 `character_action` 的 `--character-ref` 時，該路線偏向照參考構圖與髮型，臉不穩定：同 seed 換姿勢，臉部相似度與髮型（短髮／過長髮／髮片失真）都不一致，不能說「換姿勢但臉不變」成立。降低 `--ip-weight` 到 0.4 也沒有改善（出現髮簾狀失真）。
- **服裝 → 外觀參考**：未測。
- 這些庫的臉、衣服、姿勢風格偏寫實 AI 美女與成人市場（報導稱姿勢庫約三分之二偏成人向）；實際看到的 `全身1人・標準系` 分類也以坐、跪、躺的擺拍為主，找不到行走／揮擊類動作。遊戲動作用途能用的很少，使用前要先挑。

## 實測紀錄

- 日期：2026-11-02；環境：本機 Windows、ComfyUI 0.34.0、profile `sdxl_standard`（`image_capabilities.json` 顯示 `controlnet.canny/pose/depth`、`ipadapter` 皆可用；`character_action` 與 `pose_only` 為 legacy 已驗證）。`generate.py` 圖片 task 沒有 `--preflight`，用能力快照與 profile 檢查代替；快照為 11 天前，指紋一致。
- 參考圖（本機、不進 repo）：人臉 1 張 `f71f980dde3`；姿勢深度圖與線稿各 `full_single_P018_front`（雙手扠腰）、`full_single_P077_front`（側身展臂），共 6 張，放 `output/pose-face-test/refs/`。
- 指令骨架：`python tools_src/generate.py character_action --character-ref <face> --pose-ref <pose> --control-type <depth|canny|pose> --seed 42 --width 768 --height 1024 --prompt "a young woman, full body standing, ..."`；另跑 `pose_only --control-type depth`。固定 seed 42，每組 1 張；單張約 8–16 秒（第一張含載入 32 秒）。
- 結果對照圖：`output/pose-face-test/sheet0.png`、`sheet1.png`、`sheet2.png`；各組輸出在 `output/pose-face-test/out/`（A=depth、B=depth 換姿勢、C/D=canny 線稿、E/G=pose 線稿、F=pose 深度圖、H=canny 深度圖、I=pose_only depth、J=ip-weight 0.4）。
- 限制：只測 1 張臉、2 個姿勢、1 張／組、單 seed，沒有做行走／揮擊類，也沒測服裝庫；臉部一致性只做目視判斷。**技術結果，非美術接受**，未 accept／reject。
- 補測（同日）：`pose_only --control-backend union`（本機已有 xinsir union promax，experimental），同 seed 42、prompt 改寫為白 T 恤牛仔褲、無臉參考，2 姿勢 × depth／canny／pose，證據 `output/pose-face-test/sheet3.png`、`out/K_union_*`。union depth：姿勢遵守且穿得上衣服（比標準 depth controlnet 乾淨，不再退成內衣），但人偶體型與褲管破洞偏卡通；union canny：仍把人偶線條畫進成品；union pose：骨架一樣抽不到，姿勢被忽略（雙手插口袋的通用站姿）。→ 問題在 OpenPose 抽取器認不得無臉人偶，換 controlnet 模型不能解。每組單張，僅此範圍。
- 手掌方向（同日補看，目視放大 `output/pose-face-test/hands.png`）：depth 路線（標準與 union）會跟著深度圖的手形，張開手掌的朝向與五指張開大致遵守、扠腰的手貼腰也正確；但手指細節與數量不保證，姿勢庫自己也自述手指較弱。pose 路線沒有骨架所以手方向無從談起。僅 2 個姿勢各 1 張，手部細節要逐張驗收。
- 第二輪實驗（2026-11-02，只用本機已裝的節點與模型，**沒有下載或安裝任何東西**）：
  - DWPose（`DWPreprocessor`，`dw-ll_ucoco_384.onnx` + `yolox_l.onnx`，本機原本就有）：對 4 張人偶（深度圖、線稿各 2）只有 1 張（線稿 P077 側身展臂）抽出骨架與手指點，其餘 3 張全黑＝抽不到；對一張真人照片可抽出。證據 `output/pose-face-test/dwpose/`、`sheet4.png`。結論：DWPose 比 OpenPose 稍好但對無臉人偶不穩，不能當穩定做法。
  - Qwen-Image-Edit 2511 三參考（`image/qwen-image-edit/three-reference`，加 `--allow-unverified-platform`，442 秒／張）：圖1放深度圖 P077、圖2/3放兩張臉。姿勢與張開手掌朝向遵守，但輸出照抄人偶的肌肉與體型、衣服只剩白色連身，臉糊成無五官，臉庫的身分沒帶過來。證據 `output/pose-face-test/qwen_P077/`、`sheet5.png`。單張，僅此範圍。
  - MeshGraphormer 手部深度（2026-11-02，使用者同意後下載）：節點首次執行自動下載 2 個權重，來源 Hugging Face `hr16/ControlNet-HandRefiner-pruned`，合計約 1.3GB：`graphormer_hand_state_dict.bin` 855,658,184 bytes、`hrnetv2_w64_imagenet_pretrained.pth` 513,111,608 bytes，位置 `C:\Users\XU\ComfyUI\custom_nodes\comfyui_controlnet_aux\ckpts\hr16\`（要移除就刪這個資料夾）。對 3 張 SDXL 生成圖（含兩張 union depth 站姿）執行：3 張只有 1 張抓到一隻手（側身展臂的右手，深度圖與遮罩可用），另 1 張只有碎片，其餘全黑＝偵測不到手。證據 `output/pose-face-test/mesh/`、`sheet6.png`。結論：偵測率低，單靠它不能保證補到手；後續「深度圖＋depth ControlNet 局部重繪」未做，因為多數圖沒有可用的手部深度。
  - **第三輪（2026-11-02，皆為實驗，沒改固定 template）**
    - 穩定性＋服裝：`pose_only --control-backend union --control-type depth`，prompt 明寫白 T 恤、牛仔褲、白球鞋，負面詞排除裸色與緊身衣；2 姿勢（P018 扠腰、P077 側身展臂）× seed 1–4 × `--pose-strength` 1.0／0.6，共 16 張，每張約 8–17 秒。目視：16／16 姿勢遵守（含手臂方向與張開手掌）；強度 0.6 的 8 張全部穿成牛仔褲與上衣，強度 1.0 有 3 張腿或上衣變半透明／發亮的人偶質感。**服裝要靠 prompt 加負面詞加 `--pose-strength 0.6`**，手指細節仍需逐張看。證據 `output/pose-face-test/s2/`、`sheet7_0.png`、`sheet7_1.png`。
    - 手部偵測統計：上述 16 張丟 MeshGraphormer，11／16 抓到手（強度 0.6 為 7／8，強度 1.0 為 4／8）；P077 展臂 7／8，P018 扠腰 4／8。證據 `output/pose-face-test/mesh2/`。比第二輪的 1／3 高，但後續「深度圖＋depth ControlNet 局部重繪手」仍沒做。
    - 兩段式重畫臉（先 depth 生全身圖，再 `guided_inpaint` 只重畫頭部橢圓，`--appearance-ref` 臉庫特寫，denoise 0.85，seed 7）：正面頭的 P018，權重 0.6 得到有劉海短髮與微笑、與臉參考大致像，權重 1.0 臉被頭髮蓋住；側轉頭的 P077 權重 0.6 變灰色圓盤、1.0 臉被頭髮擋住。→ 只對正面頭有機會，側臉不行，身分相似度只做目視且單張。證據 `output/pose-face-test/s3/`、`sheet8.png`。
    - **FLUX.2 單圖編修（`image/flux2/edit`，加 `--allow-unverified-platform`，32 秒）：以 P018 成品為來源，prompt 要求「雙臂向兩側伸直、掌心朝前，臉髮衣服不變」，結果姿勢改對、掌心朝前，臉、髮型、上衣、牛仔褲幾乎不變。證據 `output/pose-face-test/flux2_edit/`、`sheet9.png`。單張單 seed，是目前「換姿勢但臉不變」最有希望的路。**
    - 姿勢多樣性：姿勢庫 `ポーズ名` 找不到走、跑、揮擊類（只有「振り向く」回頭類），列為限制。
    - 未做：Yedp-Action-Director 骨架輸出（需在 ComfyUI 介面擺 3D 人偶，無法 API 自動化）。
  - **第四輪：FLUX.2 單圖編修改姿勢穩定性（2026-11-02，`image/flux2/edit`，`--allow-unverified-platform`，單張約 28–32 秒，全為目視判斷、不是量測）**
    - 來源角色 5 個：寫實 3 個（SDXL 生成，白 T＋牛仔褲）、遊戲風 2 個（`generate.py concept --style illustration` 無臉扁平風 G1；`--style anime` 動漫風 G2，銀髮藍圍巾棕外套）。提示固定格式：「Change only the pose: …  Keep the face, hairstyle, clothes, art style and the plain background unchanged.」一次只改一個動作。
    - 遊戲風 2 角色 × 6 動作 × 3 seed（7／21／99）＝36 張：右手高舉 6／6、走路 6／6、抱胸 6／6、回頭揮手 6／6、雙手持杖舉過頭 5／6（1 張出現兩根杖）、「雙手前推」原提示 0／6（手臂被畫成向兩側展開）。改寫提示為「兩手肘彎曲、掌心朝鏡頭、不要向兩側」後 5／6（1 張兩掌併攏）。含改寫共 34／36。臉、髮型、服裝、畫風、背景在這些圖都保持，只有圍巾形狀與背景色偶爾微變（1 張背景變米色）。
    - 寫實 3 角色（seed 42 為主，再補 2 組 seed）共 23 張：右手高舉 3／5（2 張變成雙手或雙臂都舉）、走路 5／5、雙手前推原提示 2／5（其餘兩臂向兩側）、抱胸 3／3、回頭揮手 4／5（1 張雙手合十；另 1 張髮型多出髮髻）；合計 17／23。頭轉向側面時臉被擋，身分是否一致無法判斷。
    - 失敗樣態：(a)「雙手前推」被解讀為雙臂橫伸；(b) 指定單手時另一手跟著動；(c) 持物時物件數量重複；(d) 髮型偶爾被改（寫實角色）；(e) 回頭動作會讓臉轉開，保臉無從驗證；(f) 手指數量與細節沒有逐指檢查，只確認大致掌心朝向（舉手、前推、揮手的掌心朝向多數正確）。
    - 證據：`output/pose-face-test/flux_stab/`、`flux_stab2/`、`flux_stab3/`，對照圖 `show/f_flux_batch1.png`、`g_flux_G1.png`、`g_flux_G2.png`、`h_push_prompt.png`、`i_realistic_seeds.png`；耗時記錄在各資料夾 `log.txt`。
    - **結論（可用 or 不可用）**：對「遊戲風單張角色圖、一次只改一個大動作」可用：36 張中 34 張達標（94%）。對寫實角色有條件可用但穩定度較差（17／23，74%），要挑圖。還沒驗證：連續多格動畫的一致性、身分的量化比對、武器細節、背面／大幅度轉身、手指正確性。不要拿它直接產出交付素材，所有輸出仍走 R1 逐張驗收。
    - **可用條件**：來源圖清楚、全身、單人、背景單純；一次一個動作；提示寫清楚「肘彎曲、掌心朝向」等具體肢體；每個動作至少出 3 個 seed 挑；結果逐張看手、持物與髮型。**不可用情境**：需要精準指定每根手指或武器握法；需要保證臉部身分不變又要大幅轉頭；需要一次完成連續動畫格；寫實角色當批量素材。
  - **第五輪：動漫角色專測（2026-11-02，`image/flux2/edit`，`--allow-unverified-platform`，單張約 28 秒，全為目視判斷）**
    - 4 個動漫風格角色（`generate.py concept` 產生，一般向、全身）：N1 日系 RPG 立繪（`--style illustration`，紅髮雙辮騎士）、N2 Q 版二頭身（`--style anime`，紫雙馬尾法師）、N3 厚塗動漫（`--style illustration`，綠髮遊俠）、N4 線稿上色（`--style anime`，黑髮少年；原圖有兩人，裁切左側一人當來源）。8 動作 × 3 seed（7／21／99）× 4 角色＝96 張，96 張全部執行成功。
    - 總成功率（姿勢達成且角色大致不變）79／96＝82%。依動作：走路 12／12、抱胸 12／12、單手指向 12／12、低頭 12／12、回頭揮手 11／12、舉手 9／12（3 張變成雙手舉）、雙手持杖 8／12、**掌心朝鏡頭 3／12**。依角色：N1 19／24、N2 18／24、N3 22／24、N4 20／24。
    - 與第四輪動漫風（G2）比對：舉手、走路、抱胸、回頭揮手、持杖在 G2 皆 3／3，這輪多角色後降到 8–11／12；「掌心朝鏡頭」第四輪用「推出、停止手勢」寫法得 5／6，這輪改用「手肘彎曲、手掌貼平朝鏡頭」寫法只有 3／12，多數變成兩手合在胸前或交疊。→ 提示寫法影響大，朝鏡頭掌心要沿用「stop gesture」那種說法。
    - 失敗樣態：(a) 舉手時另一隻手也跟著舉（N1、N2、N3 各 1 張）；(b) 雙手持杖時原本的道具（N2 紅寶石法杖）留在畫面，造成兩根杖，或杖只由一手握住（N4）；(c) 掌心朝鏡頭變成雙手合十或心形手勢；(d) N3 厚塗角色走路時披風與護甲被重畫成不同款式，原本背後的盾或弓有時消失；(e) 背景色偶爾偏米色。
    - 專測項目：**臉部身分**——正面、低頭時臉型、髮色、眼色、配件（髮飾、帽子）保持；回頭揮手有 8／12 轉成側面或背面，臉被擋住，轉側面時的身分無法判斷。**手指數量**——大圖的舉手、指向、持物多數是 5 指，但這輪沒有逐指檢查，小圖看不清的不下結論。**髮型與配件**——N1 雙辮、N2 雙馬尾與帽子、N4 圍巾基本保留，圍巾形狀會變。**畫風漂移**——N1、N2、N4 沒有明顯漂移；N3 厚塗最明顯（服裝款式與光影變動）。
    - 證據：`output/pose-face-test/anime_src/`（來源）、`anime_flux/`（96 張與 log.txt）；對照圖 `show/j_anime_N1.png`～`j_anime_N4.png`。
    - 結論：動漫角色可用於「單張角色、一次改一個動作」，舉手、走路、抱胸、指向、低頭都穩；雙手持物與掌心朝鏡頭不穩，要多出 seed 挑或改寫提示；厚塗風格要檢查服裝是否被重畫。
  - **哪種需求走哪條路（以上有限樣本）**
    | 需求 | 路線 | 備註 |
    |---|---|---|
    | 要姿勢庫的姿勢、不在乎臉 | union depth ＋ 明確服裝 prompt ＋ `--pose-strength 0.6` | 姿勢遵守 16／16；手需驗收 |
    | 已有一張角色圖，只想改姿勢或手掌方向 | FLUX.2 `image/flux2/edit` | 保臉保衣最好，一次一個動作，逐張驗收 |
    | 想用臉庫重畫臉 | 先生圖，再 `guided_inpaint` 重畫頭部（正面頭、權重 0.6） | 側臉失敗；相似度未量化 |
    | 用 pose／OpenPose 抓無臉人偶 | 不建議 | 抽不到骨架；DWPose 也只 1／4 |
    | 線稿人偶 canny | 不建議 | 線條畫進成品 |
    | 手部修補 | MeshGraphormer 偵測 11／16，可當手部深度來源 | 局部重繪未測 |
  - 這輪結論：姿勢遵守靠 depth 類控制（union depth 最乾淨）；「保臉」在這些方法都沒解決，不能靠臉庫特寫。
- 結論見頁首「可用結論」：姿勢庫深度圖可當姿勢來源；「換姿勢但臉不變」改走 `flux2_edit`，不靠人臉庫特寫。

## 使用規則

1. **不進 repo**：服裝庫與姿勢庫禁止再散布，人臉庫作者請求勿轉載。repo 與對外簡報只放連結，不放圖片本身，也不批次下載。
2. 使用者自己下載、當參考圖餵進流程可以；產出的作品可商用，但要在素材紀錄寫明參考來源與庫名（[result-records](../result-records.md)）。
3. 禁止用於表現真人或未成年；人臉庫圖不可冒充真人。遊戲角色用途以外的情境先問使用者。
4. 商用前請使用者自己確認三個站的最新條款；agent 不做法律判斷。
5. 要把它做成固定 template，依[擴充協議](../maintenance/extension-protocol.md)：先標實驗、實測、使用者確認後才進產線。
