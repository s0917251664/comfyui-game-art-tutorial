# icon_asset 的 --structure-ref:結構/顏色配置已有明確答案時怎麼辦

`skills/comfyui-art-gen/SKILL.md` 的 `icon_asset` 固定問題第 5 點指向這裡——平常不用讀,只有「結構描述用文字講不清楚」或「AI 一直畫不準確定的數量/配置」時才查。

## 這是什麼

`icon_asset` 平常純靠文字 prompt 決定畫面內容,但有些圖示的結構/顏色配置**在下筆前就已經有確定答案**(不是要 AI 自己想像的),例如「一個放射狀圖示要精準分成 N 塊」——這種**精確計數幾何**任務,SDXL 靠文字描述不可靠。

`--structure-ref <範本圖路徑>` 提供另一條路:先準備一張已經畫好目標結構/顏色的範本圖,`icon_asset` 用它同時當:
1. **img2img 的底圖**(denoise 鎖死 0.85,不開放調整):結構/色塊配置直接繼承範本像素,不用 SDXL 自己決定
2. **Canny ControlNet 的邊緣來源**(strength 鎖死 0.85):邊緣位置再鎖一層,防止 img2img 的 denoise 沒到 1.0 時邊緣被畫糊

SDXL 只負責在這個底圖上疊材質/光澤/風格,不負責決定「有幾塊」「顏色怎麼排」。

## 範本圖從哪來

範本圖可以是任何來源(使用者提供的草圖、美術自己畫的,或程式產生),不限定畫法。`tools_src/generate.py` 裡的 `build_wheel_segment_template(n_segments, width, height, colors, gold)` 是一個現成的輔助函式,用來畫「圓形外框 + N 條放射狀分隔線 + 交錯色塊」這種放射狀等分圖示的範本,不是獨立的 CLI task,是給呼叫端(agent)自己 import 呼叫、存成檔案後再餵給 `--structure-ref` 用:

```python
import importlib.util
spec = importlib.util.spec_from_file_location("generate", "<generate_script 路徑>")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
img = m.build_wheel_segment_template(n_segments=8, width=1024, height=1024)
img.save("<暫存路徑>/template.png")
```

存好之後正常呼叫:

```
icon_asset --prompt "..." --structure-ref "<暫存路徑>/template.png" --output-dir <output_dir>
```

放射狀等分只是其中一種結構類型,遇到其他「結構/配置已經確定、AI 用文字講不清楚」的圖示,自己畫一張對應的範本圖(規則相同:目標結構的線條/色塊直接畫在圖上)一樣可以餵給 `--structure-ref`,不用侷限在轉盤這個案例上。

## 已知取捨:結構鎖住了,精細裝飾細節會被壓掉

2026-08-19 實測(轉盤案例,8 等分放射狀圖示):`--structure-ref` 能穩定鎖住結構跟顏色配置(反覆測試分區數量/顏色都沒跑掉),denoise 從 0.55 一路測到 0.85 質感都持續提升(從死板平面到有玻璃寶石光澤球面感),但**鑲花雕紋這類需要額外邊緣線條的裝飾細節,不管怎麼調 denoise 都沒有明顯出現**。推測原因是 Canny ControlNet 鎖邊緣的同時,也會壓抑「多畫細碎額外線條」這件事——這是這個做法的結構性限制,不是 denoise 沒調好,繼續往上推 denoise 更可能先讓結構跑掉,不會先讓雕紋跑出來。跟使用者說明時要講清楚這個取捨,不要保證「結構鎖住又能有精細雕花」兩者都要。

## 已知踩坑:三種失敗模式的演進紀錄

這個功能是從三次失敗迭代出來的,紀錄一下避免以後重踩:
1. **純文字描述「切成 N 等份」**:SDXL 對精確計數幾何任務不可靠,分區數量對不上,反覆重跑會在「偽資訊圖表(冒出亂碼文字)」「花瓣/寶石裝飾蓋掉分區結構」之間打轉
2. **只用純線稿 ControlNet 鎖邊緣位置**(不搭配 img2img):線的位置鎖住了,但顏色配置沒被鎖住,SDXL 還是會整張畫成單一漸層蓋過分區邊界——ControlNet canny 只鎖邊緣結構,不會連帶鎖住「這幾塊顏色要交錯」這種區域級語意
3. **範本圖直接畫好顏色 + img2img + ControlNet 雙重鎖**(目前採用的做法):結構跟顏色配置才真正穩定
