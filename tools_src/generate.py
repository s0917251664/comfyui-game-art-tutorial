"""
穩定產圖核心腳本(不吃自然語言,只吃結構化參數)。

設計原則:
- 每個 task 對應一組鎖死大部分參數的 ComfyUI graph,只有明確列出的欄位可調
- 不靠 LLM 每次臨場組 JSON,參數集固定、行為可預期、可重複
- 上層(Skill/agent)的工作只是把自然語言整理成這裡要的結構化參數,不做生成邏輯本身

Usage:
    python generate.py concept --prompt "a female game character concept art, fantasy armor" [--negative ...] [--seed N] [--width 1024] [--height 1024] [--remove-bg]
    python generate.py character_action --prompt "..." --character-ref path.png --pose-ref path.png [--pose-strength 1.0] [--remove-bg]
    python generate.py inpaint --prompt "..." --image path.png --mask path.png [--denoise 1.0]
"""
import argparse
import json
import math
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PIL import Image as PILImage, ImageDraw

COMFY_URL = "http://127.0.0.1:8188"
DEFAULT_NEGATIVE = "blurry, low quality, extra fingers, deformed, watermark"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")
DEVICE_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "device_config.json")

# pose_only / character_action 的構圖控制來源,依 --control-type 選擇對應 ControlNet 模型
# (canny=線稿邊緣,pose=骨架姿勢,depth=深度圖),需要 comfyui_controlnet_aux custom node
# 提供 OpenposePreprocessor / DepthAnythingV2Preprocessor,細節見 skills/comfyui-install/SKILL.md
#
# 已知技術債:這裡跟下面 build_character_action/build_style_lock 裡的 ipadapter_file/clip_name
# 都是寫死指向 SDXL 版本,沒有跟著 CKPT(見 load_device_config)的 tier 走。目前只在 SDXL 家族
# tier(sdxl_high/sdxl/sdxl_light)上驗證過。如果之後真的有機器落在 sd15 tier(底模自動換成
# SD1.5 系列),這幾個常數也要跟著換成 SD1.5 對應版本,不然底模跟 ControlNet/IPAdapter 架構
# 對不上,執行期會 shape mismatch——換 tier 時記得回來檢查這裡,不要假設現有檔名通用。
CONTROLNET_MODELS = {
    "canny": "controlnet-canny-sdxl-1.0.safetensors",
    "pose": "controlnet-openpose-sdxl-1.0.safetensors",
    "depth": "controlnet-depth-sdxl-1.0.safetensors",
}

# --style 選填參數的白名單(選配,不裝也完全不影響預設行為)。都是 SDXL 架構的社群微調底模,
# 換掉 CKPT 不用連帶換 ControlNet/IPAdapter/CLIP Vision。只在 SDXL 家族 tier 生效,見 main() 裡的
# tier 檢查——sd15 機器上這幾顆會跟 ControlNet/IPAdapter shape mismatch。
# 各風格的授權/檔案來源見 skills/comfyui-install/reference/models.md,商用前務必自行覆核授權條款
# ——這三顆各自授權都不一樣(Juggernaut/Pony 都有針對「做成付費服務」的限制;Illustrious 依版本
# 不同差很多,2026-08-19 曾經記錯成 MIT,見 models.md 更正說明),不要憑這裡的常數名稱就假設能商用。
STYLE_CHECKPOINTS = {
    "realistic": "juggernautXL_ragnarok.safetensors",
    "illustration": "Illustrious-XL-v1.1.safetensors",
    "anime": "ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
}

# --rating 選填參數(選配,不給就完全不影響 prompt)。只對 anime/illustration 這兩個 --style
# 有意義——這兩顆底模的訓練資料本身就用分級標籤控制內容尺度(Pony 用 rating_xxx,Illustrious
# 沿用 Danbooru 的 rating:xxx),不是這個腳本自己發明的機制。realistic/預設底模沒有對應標籤慣例,
# 給了 --rating 也沒意義,main() 裡會直接擋掉,不要讓它靜默沒效果。
RATING_TAGS = {
    "anime": {"safe": "rating_safe", "questionable": "rating_questionable", "explicit": "rating_explicit"},
    "illustration": {"safe": "rating:general", "questionable": "rating:questionable", "explicit": "rating:explicit"},
}


def build_control_preprocessor(control_type, image_node_id):
    """依 control_type 回傳對應的前處理節點(從 image_node_id 的圖片輸出接進去)。"""
    if control_type == "canny":
        return {"class_type": "Canny", "inputs": {"image": [image_node_id, 0], "low_threshold": 0.4, "high_threshold": 0.8}}
    elif control_type == "pose":
        return {"class_type": "OpenposePreprocessor", "inputs": {"image": [image_node_id, 0]}}
    elif control_type == "depth":
        return {"class_type": "DepthAnythingV2Preprocessor", "inputs": {"image": [image_node_id, 0]}}
    raise ValueError(f"未知 control_type: {control_type}(可用: canny/pose/depth)")


def load_device_config():
    """讀設備偵測結果(detect_device.py 產出),決定用哪個 checkpoint/預設解析度。
    沒有這份設定檔就用保守的 SDXL 預設值,並提醒使用者先跑一次偵測。"""
    if not os.path.exists(DEVICE_CONFIG_PATH):
        print(f"[提醒] 找不到 {DEVICE_CONFIG_PATH},建議先執行 detect_device.py。目前用預設 SDXL 設定。", file=sys.stderr)
        return {"checkpoint": "sd_xl_base_1.0.safetensors", "default_width": 1024, "default_height": 1024}
    with open(DEVICE_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


DEVICE = load_device_config()
CKPT = DEVICE["checkpoint"]


def upload_image(path):
    """上傳一張本機圖片到 ComfyUI 的 input 目錄,回傳可在 LoadImage 節點使用的檔名。"""
    filename = os.path.basename(path)
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read().decode())
    return result["name"]


def submit_and_wait(prompt, timeout=180):
    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt", data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"送出失敗: {e.code} {e.read().decode()}")

    result = json.loads(resp.read().decode())
    if result.get("node_errors"):
        raise RuntimeError(f"節點參數錯誤: {json.dumps(result['node_errors'], ensure_ascii=False)}")
    prompt_id = result["prompt_id"]

    start = time.time()
    while time.time() - start < timeout:
        hist_req = urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=15)
        history = json.loads(hist_req.read().decode())
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"生成失敗: {json.dumps(status, ensure_ascii=False)}")
            if status.get("completed"):
                return entry
        time.sleep(1)
    raise TimeoutError(f"等待生成逾時({timeout}s),prompt_id={prompt_id}")


def download_outputs(history_entry, output_dir=None):
    output_dir = output_dir or OUTPUT_DIR
    paths = []
    os.makedirs(output_dir, exist_ok=True)
    for node_id, node_out in history_entry.get("outputs", {}).items():
        for img in node_out.get("images", []):
            url = (
                f"{COMFY_URL}/view?filename={urllib.parse.quote(img['filename'])}"
                f"&subfolder={urllib.parse.quote(img.get('subfolder', ''))}&type={img.get('type', 'output')}"
            )
            local_path = os.path.join(output_dir, img["filename"])
            urllib.request.urlretrieve(url, local_path)
            paths.append(local_path)
    return paths


def seed_or_random(seed):
    return seed if seed is not None else int.from_bytes(os.urandom(6), "big")


def model_clip_refs(graph, lora_name=None, lora_strength=0.8, ckpt_node_id="1", lora_node_id="1b"):
    """回傳這個 graph 後面該接的 MODEL/CLIP 節點參照。
    有指定 --lora 的話,插入一個 LoraLoader 節點(套在 checkpoint 後面),回傳它的輸出;
    後面所有節點的 model/clip 輸入都要用這裡回傳的參照,不要直接寫死 [ckpt_node_id, 0]/[ckpt_node_id, 1],
    不然 LoRA 會被跳過沒套用到。沒指定 --lora 就直接回傳 checkpoint 節點本身的輸出,行為跟原本一樣。"""
    if not lora_name:
        return [ckpt_node_id, 0], [ckpt_node_id, 1]
    graph[lora_node_id] = {
        "class_type": "LoraLoader",
        "inputs": {
            "model": [ckpt_node_id, 0], "clip": [ckpt_node_id, 1],
            "lora_name": lora_name, "strength_model": lora_strength, "strength_clip": lora_strength,
        },
    }
    return [lora_node_id, 0], [lora_node_id, 1]


# ---------- task: concept (Ch3 系列:純文字概念圖) ----------
def build_concept(prompt, negative=None, width=None, height=None, seed=None, steps=25, cfg=7.0, batch_size=1,
                   lora_name=None, lora_strength=0.8, checkpoint=None):
    width = width or DEVICE["default_width"]
    height = height or DEVICE["default_height"]
    negative = negative or DEFAULT_NEGATIVE
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": model_ref, "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "concept"}},
    })
    return graph, "6"  # 回傳 (prompt, 最終圖片節點id) 方便後續接去背


# ---------- task: icon_asset(單一小型 UI 圖示/物件素材,不是整個 UI 畫面)----------
# 跟 concept 的差異只有三點,其餘 graph 結構完全共用 concept 的模式:
#   1. prompt/negative 固定 append 一段構圖引導詞,把生成結果導向「單一置中物件、無場景背景」
#      ——這同時讓輸出更像可用的圖示素材,也讓後面接的去背(BiRefNet)邊緣更乾淨(背景乾淨的
#      單一主體比「背景也有大量裝飾元素在跟主體搶前景」的構圖更容易被正確分離)
#   2. 預設畫布是 1024x1024 正方形,不吃 DEVICE["default_width/height"](那組預設是給人像
#      直式構圖調的,不適合圖示)
#   3. main() 呼叫這個 task 時一定會接去背,沒有 --remove-bg 旗標讓使用者選——圖示素材預期
#      本來就是要疊加到別的畫面上用,透明背景是這個 task 存在的前提,不是可選項
ICON_ASSET_PROMPT_SUFFIX = ", single centered object, icon design, isolated on plain simple background, clean readable silhouette, no scene, no extra props"
ICON_ASSET_NEGATIVE_SUFFIX = ", cluttered scene, multiple objects, full illustration background, cropped edges"
# icon_asset 的 --structure-ref 用的鎖死參數(這條產線的設計哲學:先求穩定可重複)。
# 2026-08-19 實測踩過三種失敗模式(當時的情境是「輪盤要精準等分成 N 塊」,但結論適用於任何
# 「結構/色塊配置有明確答案、不該讓 AI 自己瞎猜」的圖示):純靠文字描述數量/配置,SDXL 對這種
# 精確計數幾何任務不可靠;改成只用線稿 ControlNet 鎖邊緣位置後,邊緣位置雖然鎖住了,但色塊
# 配置沒被鎖住,SDXL 還是會整張畫成單一漸層蓋過色塊邊界(ControlNet canny 只鎖邊緣結構,不會
# 連帶鎖住「這幾塊顏色要交錯」這種區域級語意)。最後改成:範本圖本身直接畫好目標結構+顏色,
# 同時當 img2img 的底圖(denoise < 1.0,結構/色塊配置跟著像素直接繼承,不用 SDXL 自己決定)
# 加 Canny ControlNet(邊緣位置再鎖一層,img2img 的 denoise 沒到 1.0 時邊緣仍可能被畫糊,兩層
# 一起上比較保險)。denoise 太低(0.55/0.65 實測過)結構顏色鎖得住,但 SDXL 幾乎沒空間疊材質/
# 光澤,畫面會很平;denoise=0.85 是目前實測結構仍然穩、質感明顯提升的甜蜜點。
STRUCTURE_REF_CONTROL_STRENGTH = 0.85
STRUCTURE_REF_DENOISE = 0.85


def build_wheel_segment_template(n_segments, width=1024, height=1024,
                                  colors=((124, 40, 168), (20, 158, 148)), gold=(212, 175, 55),
                                  frame_ratio=None, bead_count=0, hub_ratio=0.12):
    """畫一張『交錯色塊扇形 + 金色分隔線/外框/中心軸』的範本圖,是 icon_asset 的 --structure-ref
    的其中一種產生方式(輪盤/放射狀等分圖示適用)——不是獨立的 CLI task,是給呼叫端(agent 或
    人類)在需要「放射狀精準等分」這種結構時自己呼叫來產生範本檔案用,範例見
    skills/comfyui-art-gen/reference/structure-ref.md。

    frame_ratio(選用,0~1):給了就額外畫一圈獨立的外框環帶(獎區扇形只填到 frame_ratio 對應
    的內側半徑,環帶本身填 gold 顏色),不給就跟原本一樣只在最外緣畫一條細外框線。
    bead_count(選用,搭配 frame_ratio 用):在外框環帶中線畫幾顆等間距白色圓珠裝飾。
    hub_ratio:中心鈕半徑佔整體半徑的比例,搭配 build_wheel_layer_masks() 拆圖層時務必用同一個值,
    否則遮罩邊界會跟這張範本對不齊。
    """
    img = PILImage.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.45
    line_width = max(3, min(width, height) // 200)
    wedge_radius = radius * frame_ratio if frame_ratio else radius

    if frame_ratio:
        # 先畫滿版外框圓蓋住整個範圍,獎區扇形疊上去之後,外圍那圈環帶(wedge_radius~radius
        # 之間)自然只留下框色沒被蓋到,不用另外算環狀多邊形。
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=gold)

    for i in range(n_segments):
        a0 = 2 * math.pi * i / n_segments - math.pi / 2
        a1 = 2 * math.pi * (i + 1) / n_segments - math.pi / 2
        points = [(cx, cy)]
        for s in range(13):
            a = a0 + (a1 - a0) * s / 12
            points.append((cx + wedge_radius * math.cos(a), cy + wedge_radius * math.sin(a)))
        draw.polygon(points, fill=colors[i % len(colors)])

    if frame_ratio and bead_count:
        bead_r = (radius + wedge_radius) / 2
        bead_size = (radius - wedge_radius) * 0.35
        for i in range(bead_count):
            a = 2 * math.pi * i / bead_count
            bx = cx + bead_r * math.sin(a)
            by = cy - bead_r * math.cos(a)
            draw.ellipse([bx - bead_size, by - bead_size, bx + bead_size, by + bead_size], fill=(255, 255, 255))

    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=gold, width=line_width)
    for i in range(n_segments):
        angle = 2 * math.pi * i / n_segments
        x = cx + wedge_radius * math.sin(angle)
        y = cy - wedge_radius * math.cos(angle)
        draw.line([cx, cy, x, y], fill=gold, width=line_width)
    hub_radius = radius * hub_ratio
    draw.ellipse([cx - hub_radius, cy - hub_radius, cx + hub_radius, cy + hub_radius], fill=gold)
    return img


def build_wheel_layer_masks(width=1024, height=1024, frame_ratio=0.86, hub_ratio=0.22):
    """搭配 build_wheel_segment_template(frame_ratio=...) 產生的合成圖,回傳三張跟 layer_split
    格式相容的遮罩(RGBA,要保留進該圖層的區域 alpha=0,其餘 alpha=255):外框環帶、內部獎區、
    中心指針。frame_ratio/hub_ratio 務必跟產生合成圖時用的值一致,否則裁出來的圖層邊界會對不齊。

    中心指針的機關形狀(例如彈片)常常會伸出 hub 圓圈一小段延伸到獎區範圍,這裡刻意把
    hub_ratio 訂得比範本圖畫的中心鈕大一些(範本圖固定畫 0.12,這裡預設 0.22),
    讓指針延伸出去的部分還是被歸進指針圖層,不會被切給獎區圖層。
    """
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.45
    wedge_radius = radius * frame_ratio
    hub_radius = radius * hub_ratio

    def _ring_mask(r_inner, r_outer):
        m = PILImage.new("RGBA", (width, height), (0, 0, 0, 255))
        d = ImageDraw.Draw(m)
        if r_outer > 0:
            d.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=(0, 0, 0, 0))
        if r_inner > 0:
            d.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=(0, 0, 0, 255))
        return m

    frame_mask = _ring_mask(wedge_radius, radius)
    prize_mask = _ring_mask(hub_radius, wedge_radius)
    pointer_mask = _ring_mask(0, hub_radius)
    return frame_mask, prize_mask, pointer_mask


def build_icon_asset(prompt, negative=None, width=1024, height=1024, seed=None, steps=25, cfg=7.0,
                      batch_size=1, lora_name=None, lora_strength=0.8,
                      structure_ref_filename=None, control_strength=STRUCTURE_REF_CONTROL_STRENGTH,
                      structure_ref_denoise=STRUCTURE_REF_DENOISE, checkpoint=None,
                      appearance_ref_filename=None, appearance_weight=0.8):
    negative = (negative or DEFAULT_NEGATIVE) + ICON_ASSET_NEGATIVE_SUFFIX
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt + ICON_ASSET_PROMPT_SUFFIX, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
    })

    if appearance_ref_filename:
        # --appearance-ref:跟 guided_inpaint/style_lock 用同一顆 IPAdapter 模型,把「畫面看起來
        # 像哪張參考圖」的責任從純文字描述轉移到圖片級別的參考,對材質/質感這類文字講不清楚的
        # 特徵比較有效。套在 model_ref 上,KSampler 用的 model 要接這裡回傳的新參照,不要漏接。
        graph["1b2"] = {"class_type": "LoadImage", "inputs": {"image": appearance_ref_filename}}
        graph["1b3"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}}
        graph["1b4"] = {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}}
        graph["1b5"] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref, "ipadapter": ["1b4", 0], "image": ["1b2", 0], "clip_vision": ["1b3", 0],
                "weight": appearance_weight, "weight_type": "linear", "combine_embeds": "concat",
                "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only",
            },
        }
        model_ref = ["1b5", 0]

    if structure_ref_filename:
        # --structure-ref:img2img 吃範本圖當底(denoise < 1.0,結構/色塊配置繼承像素),
        # batch_size 在這個分支沒有作用(單張圖片編碼出來的 latent 本來就是 batch=1)。
        graph["4"] = {"class_type": "LoadImage", "inputs": {"image": structure_ref_filename}}
        graph["4z"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}}
        latent_ref = ["4z", 0]
        denoise = structure_ref_denoise
    else:
        graph["4"] = {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}}
        latent_ref = ["4", 0]
        denoise = 1.0

    positive_ref, negative_ref = ["2", 0], ["3", 0]
    if structure_ref_filename:
        graph["4c"] = build_control_preprocessor("canny", "4")
        graph["4d"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODELS["canny"]}}
        graph["4e"] = {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": positive_ref, "negative": negative_ref, "control_net": ["4d", 0], "image": ["4c", 0],
                "strength": control_strength, "start_percent": 0.0, "end_percent": 1.0,
            },
        }
        positive_ref, negative_ref = ["4e", 0], ["4e", 1]

    graph["5"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_ref, "positive": positive_ref, "negative": negative_ref, "latent_image": latent_ref,
            "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
            "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
        },
    }
    graph["6"] = {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}}
    graph["7"] = {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "icon_asset"}}
    return graph, "6"


# ---------- task: character_action(Ch7 ControlNet + Ch8 IPAdapter 合併)----------
def build_character_action(prompt, character_ref_filename, pose_ref_filename, negative=None,
                            width=None, height=None, seed=None, steps=25, cfg=7.0,
                            ip_weight=0.8, pose_strength=1.0, batch_size=1, control_type="canny",
                            lora_name=None, lora_strength=0.8, checkpoint=None):
    negative = negative or DEFAULT_NEGATIVE
    width = width or DEVICE["default_width"]
    height = height or DEVICE["default_height"]
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
        "4": {"class_type": "LoadImage", "inputs": {"image": character_ref_filename}},
        "5": {"class_type": "LoadImage", "inputs": {"image": pose_ref_filename}},
        # 明確指定 IPAdapter 模型 + CLIP Vision 檔名,不用 IPAdapterUnifiedLoader 的自動猜測
        # (它的 preset 自動配對邏輯會挑到 bigG 版 CLIP Vision,跟我們裝的 ViT-H 版 IPAdapter 模型維度對不上)
        "6a": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}},
        "6b": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}},
        "7": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref, "ipadapter": ["6b", 0], "image": ["4", 0], "clip_vision": ["6a", 0],
                "weight": ip_weight, "weight_type": "linear", "combine_embeds": "concat",
                "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only",
            },
        },
        "8": build_control_preprocessor(control_type, "5"),
        "9": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODELS[control_type]}},
        "10": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["2", 0], "negative": ["3", 0], "control_net": ["9", 0], "image": ["8", 0],
                "strength": pose_strength, "start_percent": 0.0, "end_percent": 1.0,
            },
        },
        "11": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}},
        "12": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["7", 0], "positive": ["10", 0], "negative": ["10", 1], "latent_image": ["11", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}},
        "14": {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": "character_action"}},
    })
    return graph, "13"


# ---------- task: inpaint(Ch6:局部調整)----------
# 遮罩檔案格式陷阱(已實測踩過):ComfyUI 的 LoadImage 節點,MASK 輸出 = 1.0 - 圖片的 alpha 通道,
# 完全沒有 alpha 通道時會靜默回傳空白遮罩(不報錯,但整個遮罩失效,產出看起來幾乎跟原圖一樣)。
# 不是「白色區域=要重畫」的灰階慣例——要重畫的區域必須是 alpha=0(透明),要保留的區域 alpha=255。
# 如果不是透過 ComfyUI 的 MaskEditor 存檔(那個格式一定對),而是agent自己用程式產生遮罩,
# 務必存成帶 alpha 通道的 RGBA 圖,不要用 .convert('RGB') 之類的操作把 alpha 弄丟。
def build_inpaint(prompt, image_filename, mask_filename, negative=None, denoise=1.0,
                   seed=None, steps=25, cfg=7.0, grow_mask_by=6, checkpoint=None):
    negative = negative or DEFAULT_NEGATIVE
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "5": {"class_type": "LoadImage", "inputs": {"image": mask_filename}},
        "6": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {"pixels": ["4", 0], "vae": ["1", 2], "mask": ["5", 1], "grow_mask_by": grow_mask_by},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["6", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "inpaint"}},
    }, "8"


# ---------- task: guided_inpaint(局部重繪 + ControlNet 結構鎖定 + IPAdapter 外觀參考)----------
# 解決 inpaint 大範圍全自由重繪的失敗模式:遮罩範圍內同時要求「結構(手指關節/物體輪廓)
# 不能崩」跟「外觀(武器造型/材質紋路)要換」時,純 inpaint 沒有任何錨點,兩者一起賭,
# 失敗率會疊乘(2026-08-18 女角色武器置換連續失敗多次才確認這個問題,不是遮罩位置或
# prompt 措辭能解決的)。guided_inpaint 額外疊兩層可選的錨點:
#   - ControlNet(control_type 給了才接):遮罩範圍內結構被控制圖釘住——pose 用於手部/
#     肢體姿勢類需求(換武器同時保持握姿),canny/depth 用於物體輪廓/立體起伏類需求
#     (換材質紋路同時保持造型,例如龍鱗紋路、道具圖示材質變體)。control_ref 預設沿用
#     --image 本身(從同一張圖抽取結構)。
#   - IPAdapter(appearance_ref_filename 給了才接):外觀不再只靠文字描述,改用一張參考圖
#     的外觀特徵(2026-08-18 補上,因應「美術自己畫一張材質/紋理圖,要套到角色身上某個
#     部位」這類需求——純文字描述紋理細節通常描述不清楚,需要圖片級別的參考)。跟
#     style_lock/character_action 用同一顆 IPAdapter 模型,參考圖建議是乾淨的材質特寫
#     (不要整張場景圖),不然背景/光影會一起被帶進來污染結果,原則同 IPAdapter 角色參考
#     圖裁緊一點的教訓(見 skills/comfyui-art-gen/reference/ 內對應說明)。
# 兩層都可選、可以同時用、也可以都不用(退化成一般 inpaint 只是多繞一層)。
def build_guided_inpaint(prompt, image_filename, mask_filename, negative=None,
                          control_ref_filename=None, control_type=None, control_strength=1.0,
                          appearance_ref_filename=None, appearance_weight=0.8,
                          denoise=1.0, seed=None, steps=25, cfg=7.0, grow_mask_by=6, checkpoint=None):
    negative = negative or DEFAULT_NEGATIVE
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "5": {"class_type": "LoadImage", "inputs": {"image": mask_filename}},
        "6": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {"pixels": ["4", 0], "vae": ["1", 2], "mask": ["5", 1], "grow_mask_by": grow_mask_by},
        },
    }

    model_ref = ["1", 0]
    if appearance_ref_filename:
        graph["7a"] = {"class_type": "LoadImage", "inputs": {"image": appearance_ref_filename}}
        graph["7b"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}}
        graph["7c"] = {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}}
        graph["7d"] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref, "ipadapter": ["7c", 0], "image": ["7a", 0], "clip_vision": ["7b", 0],
                "weight": appearance_weight, "weight_type": "linear", "combine_embeds": "concat",
                "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only",
            },
        }
        model_ref = ["7d", 0]

    positive_ref, negative_ref = ["2", 0], ["3", 0]
    if control_type:
        graph["8"] = {"class_type": "LoadImage", "inputs": {"image": control_ref_filename or image_filename}}
        graph["9"] = build_control_preprocessor(control_type, "8")
        graph["10"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODELS[control_type]}}
        graph["11"] = {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": positive_ref, "negative": negative_ref, "control_net": ["10", 0], "image": ["9", 0],
                "strength": control_strength, "start_percent": 0.0, "end_percent": 1.0,
            },
        }
        positive_ref, negative_ref = ["11", 0], ["11", 1]

    graph["12"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_ref, "positive": positive_ref, "negative": negative_ref, "latent_image": ["6", 0],
            "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
            "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
        },
    }
    graph["13"] = {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}}
    graph["14"] = {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": "guided_inpaint"}}
    return graph, "13"


# ---------- task: pose_only(Ch7:單獨 ControlNet,不鎖角色)----------
def build_pose_only(prompt, pose_ref_filename, negative=None, width=None, height=None,
                     seed=None, steps=25, cfg=7.0, pose_strength=1.0, batch_size=1,
                     control_type="canny", lora_name=None, lora_strength=0.8, checkpoint=None):
    negative = negative or DEFAULT_NEGATIVE
    width = width or DEVICE["default_width"]
    height = height or DEVICE["default_height"]
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
        "4": {"class_type": "LoadImage", "inputs": {"image": pose_ref_filename}},
        "5": build_control_preprocessor(control_type, "4"),
        "6": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODELS[control_type]}},
        "7": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["2", 0], "negative": ["3", 0], "control_net": ["6", 0], "image": ["5", 0],
                "strength": pose_strength, "start_percent": 0.0, "end_percent": 1.0,
            },
        },
        "8": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}},
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": model_ref, "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["8", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "pose_only"}},
    })
    return graph, "10"


# ---------- task: style_lock(Ch8:單獨 IPAdapter,不鎖姿勢)----------
def build_style_lock(prompt, character_ref_filename, negative=None, width=None, height=None,
                      seed=None, steps=25, cfg=7.0, ip_weight=0.8, batch_size=1,
                      lora_name=None, lora_strength=0.8, checkpoint=None):
    negative = negative or DEFAULT_NEGATIVE
    width = width or DEVICE["default_width"]
    height = height or DEVICE["default_height"]
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}}}
    model_ref, clip_ref = model_clip_refs(graph, lora_name, lora_strength)
    graph.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
        "4": {"class_type": "LoadImage", "inputs": {"image": character_ref_filename}},
        "5": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}},
        "6": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}},
        "7": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref, "ipadapter": ["6", 0], "image": ["4", 0], "clip_vision": ["5", 0],
                "weight": ip_weight, "weight_type": "linear", "combine_embeds": "concat",
                "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only",
            },
        },
        "8": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": batch_size}},
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["7", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["8", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "style_lock"}},
    })
    return graph, "10"


# ---------- task: refine(Ch5:圖生圖,草稿精緻化/材質變體)----------
def build_refine(prompt, image_filename, negative=None, denoise=0.6,
                  seed=None, steps=25, cfg=7.0, checkpoint=None):
    negative = negative or DEFAULT_NEGATIVE
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["5", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "refine"}},
    }, "7"


# ---------- task: upscale(放大精修:放大模型 + 二次 KSampler 補細節)----------
UPSCALE_MODEL = "4x-UltraSharp.pth"  # 4 倍放大模型,scale 參數透過 ImageScaleBy 縮回使用者要的倍率


def build_upscale(prompt, image_filename, negative=None, scale=2.0, denoise=0.4,
                   seed=None, steps=25, cfg=7.0, checkpoint=None):
    negative = negative or DEFAULT_NEGATIVE
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint or CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "5": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALE_MODEL}},
        "6": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["5", 0], "image": ["4", 0]}},
        # UPSCALE_MODEL 固定放大 4 倍,這裡再縮回使用者要的實際倍率(scale/4),避免要另外讀原圖尺寸算絕對像素
        "7": {
            "class_type": "ImageScaleBy",
            "inputs": {"image": ["6", 0], "upscale_method": "lanczos", "scale_by": scale / 4.0},
        },
        "8": {"class_type": "VAEEncode", "inputs": {"pixels": ["7", 0], "vae": ["1", 2]}},
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["8", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            },
        },
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "upscale"}},
    }, "10"


def build_layer_split(image_filename, mask_filename, layer_name):
    """把一張已經畫好的完成圖,依遮罩切成一張跟原圖等尺寸/位置對齊的透明圖層。

    不重新生成畫面內容,純粹是既有圖片的透明度裁切——用於複合式 UI 元件(例如轉盤的外框/
    中心鈕)已經有一張定稿合成圖,想事後切出幾個大塊區域各自疊放/調色的情境。遮罩 alpha
    慣例沿用既有 inpaint/guided_inpaint 那一套(見 skills/comfyui-art-gen/reference/masking.md):
    alpha=0 的區域 = 要保留進這一層,alpha=255 = 不屬於這一層。

    節點邏輯跟 attach_bg_removal() 是同一招:LoadImage 的 MASK 輸出是「1 − alpha」,也就是
    alpha=0(要保留的區域)對應 mask=1;但 JoinImageWithAlpha 內部會把傳入的 alpha 再做一次
    `1 − x` 換算,兩次換算方向相反,所以中間一樣要插 InvertMask,才能讓「mask=1(要保留)」
    最終變成「輸出 alpha=1(不透明)」。
    """
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "2": {"class_type": "LoadImage", "inputs": {"image": mask_filename}},
        "3": {"class_type": "InvertMask", "inputs": {"mask": ["2", 1]}},
        "4": {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["1", 0], "alpha": ["3", 0]}},
        "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": f"layer_{layer_name}"}},
    }, "4"


def attach_bg_removal(prompt, image_node_id):
    """在既有 graph 後面接上去背,回傳新增節點後的 SaveImage 節點 id(RGBA)。

    RemoveBackground 輸出的 MASK 是「1=前景主體」,但 JoinImageWithAlpha 內部會把傳入的
    alpha 做 `1 - mask` 換算(慣例是 ComfyUI 的 MASK 語意「1=要挖掉的區域」),兩者語意相反,
    直接接會讓主體被挖空、背景保留——踩過一次的坑,照 ComfyUI 官方 blueprint
    「Remove Background (BiRefNet)」的做法,中間要插一個 InvertMask 反轉語意。

    節點 id 只能挑純數字的 key 取最大值——這個 graph 裡的節點 id 不保證全是純數字字串(例如
    LoraLoader 固定用 "1b"、icon_asset 的 ControlNet 分支用 "4a"/"4b"/"4c"),對這些 key 呼叫
    int() 會直接噴例外,踩過一次(--wheel-segments 8 --remove-bg 疊加時發現)。
    """
    next_id = str(max(int(k) for k in prompt.keys() if k.isdigit()) + 1)
    n1, n2, n3, n4 = next_id, str(int(next_id) + 1), str(int(next_id) + 2), str(int(next_id) + 3)
    prompt[n1] = {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}}
    prompt[n2] = {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": [n1, 0], "image": [image_node_id, 0]}}
    prompt[n3] = {"class_type": "InvertMask", "inputs": {"mask": [n2, 0]}}
    prompt[n4] = {"class_type": "JoinImageWithAlpha", "inputs": {"image": [image_node_id, 0], "alpha": [n3, 0]}}
    save_id = str(int(n4) + 1)
    prompt[save_id] = {"class_type": "SaveImage", "inputs": {"images": [n4, 0], "filename_prefix": "transparent"}}
    return save_id


def main():
    ap = argparse.ArgumentParser(description="穩定產圖核心腳本")
    sub = ap.add_subparsers(dest="task", required=True)

    # 共用參數:每個 task 都能指定成品要存去哪(不指定就用預設的 tools/generated/)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-dir", help=f"成品存放資料夾,預設 {OUTPUT_DIR}")

    # 會用到底模 checkpoint 的 task 額外共用 --style(layer_split 純裁切、不吃底模,不套用這組)
    model_common = argparse.ArgumentParser(add_help=False, parents=[common])
    model_common.add_argument(
        "--style", choices=list(STYLE_CHECKPOINTS),
        help="換一顆風格底模(選配,不給就用這台機器裝機時鎖定的預設 checkpoint)。"
             "realistic=寫實(Juggernaut XL)、illustration=插畫/概念藝術(Illustrious XL)、"
             "anime=二次元/動漫(Pony Diffusion V6 XL)。需要先在這台機器裝好對應 checkpoint,"
             "見 skills/comfyui-install/reference/models.md;只支援 SDXL 家族 tier。",
    )
    model_common.add_argument(
        "--rating", choices=["safe", "questionable", "explicit"],
        help="內容分級標籤(選配,不給就不加任何分級標籤,prompt 完全不變)。"
             "只在 --style anime/illustration 時有意義——這兩顆底模訓練時就用分級標籤控制內容尺度,"
             "不是這裡另外加的過濾機制;--style realistic 或不給 --style 時使用這個選項會直接報錯。",
    )

    # 有 --prompt 的 task(全部除了 layer_split)都共用 --negative/--seed
    prompt_common = argparse.ArgumentParser(add_help=False, parents=[model_common])
    prompt_common.add_argument("--negative")
    prompt_common.add_argument("--seed", type=int)

    # 從零/從參考圖生成的探索型 task(concept/icon_asset/character_action/pose_only/style_lock)
    # 才支援「多生幾版比較」跟套 LoRA——inpaint/guided_inpaint/refine/upscale 是修改既有圖片,
    # 這兩個概念對它們沒有意義,不要因為想共用參數就硬塞給不適用的 task
    batch_lora_common = argparse.ArgumentParser(add_help=False, parents=[prompt_common])
    batch_lora_common.add_argument("--batch", type=int, default=1, help="一次生成幾個版本比較")
    batch_lora_common.add_argument("--lora", help="LoRA 檔名(models/loras/ 底下),不給就不套用")
    batch_lora_common.add_argument("--lora-strength", type=float, default=0.8)

    p_concept = sub.add_parser("concept", help="概念圖(純文字)", parents=[batch_lora_common])
    p_concept.add_argument("--prompt", required=True)
    p_concept.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_concept.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_concept.add_argument("--remove-bg", action="store_true")

    p_icon = sub.add_parser("icon_asset", help="單一小型 UI 圖示/物件素材(不是整個 UI 畫面),永遠去背輸出透明背景", parents=[batch_lora_common])
    p_icon.add_argument("--prompt", required=True)
    p_icon.add_argument("--width", type=int, default=1024)
    p_icon.add_argument("--height", type=int, default=1024)
    p_icon.add_argument("--structure-ref", help="這個圖示的結構/色塊配置已經有明確答案、不該讓 AI 自己瞎猜時用(例如放射狀精準等分):給一張範本圖路徑,用 img2img + Canny ControlNet 把結構跟顏色配置都鎖住,SDXL 只負責疊材質/光澤;不給就跟以前一樣純靠文字描述。範本圖從哪來見 skills/comfyui-art-gen/reference/structure-ref.md")
    p_icon.add_argument("--appearance-ref", help="外觀參考圖路徑(選用,例如使用者提供的一張成品圖,想讓畫面材質/質感偏向那張圖)——用 IPAdapter,不給就純靠文字描述外觀,原則同 guided_inpaint 的 --appearance-ref")
    p_icon.add_argument("--appearance-weight", type=float, default=0.8, help="外觀參考圖的貼合強度,原則同 --ip-weight")

    p_char = sub.add_parser("character_action", help="角色動作圖(角色參考圖 + 姿勢線稿)", parents=[batch_lora_common])
    p_char.add_argument("--prompt", required=True)
    p_char.add_argument("--character-ref", required=True, help="角色參考圖路徑")
    p_char.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_char.add_argument("--ip-weight", type=float, default=0.8)
    p_char.add_argument("--pose-strength", type=float, default=1.0)
    p_char.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="姿勢/構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_char.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_char.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_char.add_argument("--remove-bg", action="store_true")

    p_inpaint = sub.add_parser("inpaint", help="局部調整(需要來源圖 + 遮罩圖)", parents=[prompt_common])
    p_inpaint.add_argument("--prompt", required=True)
    p_inpaint.add_argument("--image", required=True, help="來源圖路徑")
    p_inpaint.add_argument("--mask", required=True, help="遮罩圖路徑(需帶 alpha 通道,要重畫的區域 alpha=0/透明,其餘 alpha=255/不透明——用 ComfyUI MaskEditor 存的檔案格式一定對)")
    p_inpaint.add_argument("--denoise", type=float, default=1.0)

    p_guided = sub.add_parser(
        "guided_inpaint",
        help="局部重繪 + 結構鎖定/外觀參考圖(遮罩範圍內可選擇鎖住結構、可選擇用一張圖決定外觀,而不是只能靠文字描述;用於換武器/道具但要保持握姿、套用美術自畫材質紋理這類需求)",
        parents=[prompt_common],
    )
    p_guided.add_argument("--prompt", required=True)
    p_guided.add_argument("--image", required=True, help="來源圖路徑")
    p_guided.add_argument("--mask", required=True, help="遮罩圖路徑(同 inpaint,需帶 alpha 通道,要重畫的區域 alpha=0)")
    p_guided.add_argument("--control-ref", help="結構引導來源圖路徑,不給就用 --image 本身(從同一張圖抽取結構);沒給 --control-type 的話這個參數沒作用")
    p_guided.add_argument("--control-type", choices=["canny", "pose", "depth"],
                           help="要鎖定的結構類型(選用,不給就不鎖結構):pose=骨架關節(手部/肢體動作類需求),canny=輪廓邊緣、depth=立體起伏(材質/紋路類需求)")
    p_guided.add_argument("--control-strength", type=float, default=1.0)
    p_guided.add_argument("--appearance-ref", help="外觀參考圖路徑(選用,例如美術自己畫的材質/紋理圖)——不給就純靠文字描述外觀。建議用乾淨的材質特寫,不要整張場景圖,不然背景/光影會一起被帶進來")
    p_guided.add_argument("--appearance-weight", type=float, default=0.8, help="外觀參考圖的貼合強度,原則同 --ip-weight")
    p_guided.add_argument("--denoise", type=float, default=1.0)

    p_pose = sub.add_parser("pose_only", help="單獨用姿勢/線稿控制構圖,不鎖角色一致性", parents=[batch_lora_common])
    p_pose.add_argument("--prompt", required=True)
    p_pose.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_pose.add_argument("--pose-strength", type=float, default=1.0)
    p_pose.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_pose.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_pose.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_pose.add_argument("--remove-bg", action="store_true")

    p_style = sub.add_parser("style_lock", help="單獨鎖角色/風格一致性,姿勢隨意(不需要姿勢參考圖)", parents=[batch_lora_common])
    p_style.add_argument("--prompt", required=True)
    p_style.add_argument("--character-ref", required=True, help="角色/風格參考圖路徑")
    p_style.add_argument("--ip-weight", type=float, default=0.8)
    p_style.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_style.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_style.add_argument("--remove-bg", action="store_true")

    p_refine = sub.add_parser("refine", help="圖生圖:草稿精緻化 / 材質顏色變體(保留原圖構圖)", parents=[prompt_common])
    p_refine.add_argument("--prompt", required=True)
    p_refine.add_argument("--image", required=True, help="來源圖路徑(草稿或要換材質的圖)")
    p_refine.add_argument("--denoise", type=float, default=0.6, help="0.3~0.4 大致保留構圖只上色;0.6~0.7 細節大幅改變;0.9+ 幾乎重畫")
    p_refine.add_argument("--remove-bg", action="store_true")

    p_upscale = sub.add_parser("upscale", help="放大精修(放大模型 + 二次取樣補細節,不是單純拉大)", parents=[prompt_common])
    p_upscale.add_argument("--prompt", required=True, help="用來引導二次取樣補細節,通常沿用原本生成這張圖時的 prompt")
    p_upscale.add_argument("--image", required=True, help="來源圖路徑(要放大的圖)")
    p_upscale.add_argument("--scale", type=float, default=2.0, help="相對原圖的放大倍率(預設 2 倍),最高 4 倍")
    p_upscale.add_argument("--denoise", type=float, default=0.4, help="二次取樣補細節的強度:太低細節補不夠,太高會偏離原圖構圖")

    p_layer = sub.add_parser(
        "layer_split",
        help="把一張已定稿的完成圖依遮罩切出單一圖層(不重新生成內容,純粹裁切透明度)——用於複合式 UI 元件想事後拆出幾個大塊可疊放區域,拆一層呼叫一次",
        parents=[common],
    )
    p_layer.add_argument("--image", required=True, help="來源圖路徑(已定稿的完成圖)")
    p_layer.add_argument("--mask", required=True, help="這一層的遮罩圖路徑(同 inpaint 慣例,需帶 alpha 通道,要保留進這一層的區域 alpha=0)")
    p_layer.add_argument("--layer-name", required=True, help="這一層的名稱,用來組輸出檔名前綴(例如 border、center_hub)")

    args = ap.parse_args()

    style_checkpoint = None
    if getattr(args, "style", None):
        if DEVICE.get("tier") not in ("sdxl_high", "sdxl", "sdxl_light"):
            raise SystemExit(
                f"--style 目前只支援 SDXL 家族機器(sdxl_high/sdxl/sdxl_light),"
                f"這台機器偵測到的 tier 是 {DEVICE.get('tier')!r}。"
                f"這幾個風格 checkpoint 都是 SDXL 架構,跟 sd15 tier 的 ControlNet/IPAdapter 對不上,"
                f"直接送出去 ComfyUI 執行期會 shape mismatch。"
            )
        style_checkpoint = STYLE_CHECKPOINTS[args.style]

    if getattr(args, "rating", None):
        if args.style not in RATING_TAGS:
            raise SystemExit(
                f"--rating 只在 --style anime/illustration 時有意義(這兩顆底模訓練資料本身用分級標籤"
                f"控制內容尺度),目前 --style={args.style!r} 沒有這個標籤慣例,加了也沒效果,直接擋下來。"
            )
        args.prompt = f"{RATING_TAGS[args.style][args.rating]}, {args.prompt}"

    if args.task == "concept":
        prompt, out_id = build_concept(args.prompt, args.negative, args.width, args.height, args.seed,
                                        batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
                                        checkpoint=style_checkpoint)
    elif args.task == "icon_asset":
        structure_fn = upload_image(args.structure_ref) if args.structure_ref else None
        appearance_fn = upload_image(args.appearance_ref) if args.appearance_ref else None
        prompt, out_id = build_icon_asset(args.prompt, args.negative, args.width, args.height, args.seed,
                                           batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
                                           structure_ref_filename=structure_fn, checkpoint=style_checkpoint,
                                           appearance_ref_filename=appearance_fn, appearance_weight=args.appearance_weight)
    elif args.task == "character_action":
        char_fn = upload_image(args.character_ref)
        pose_fn = upload_image(args.pose_ref)
        prompt, out_id = build_character_action(
            args.prompt, char_fn, pose_fn, args.negative,
            width=args.width, height=args.height,
            seed=args.seed, ip_weight=args.ip_weight, pose_strength=args.pose_strength,
            batch_size=args.batch, control_type=args.control_type,
            lora_name=args.lora, lora_strength=args.lora_strength, checkpoint=style_checkpoint,
        )
    elif args.task == "inpaint":
        img_fn = upload_image(args.image)
        mask_fn = upload_image(args.mask)
        prompt, out_id = build_inpaint(args.prompt, img_fn, mask_fn, args.negative,
                                        denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint)
    elif args.task == "guided_inpaint":
        img_fn = upload_image(args.image)
        mask_fn = upload_image(args.mask)
        control_fn = None
        if args.control_type:
            control_fn = upload_image(args.control_ref) if args.control_ref else img_fn
        appearance_fn = upload_image(args.appearance_ref) if args.appearance_ref else None
        prompt, out_id = build_guided_inpaint(
            args.prompt, img_fn, mask_fn, args.negative,
            control_ref_filename=control_fn, control_type=args.control_type, control_strength=args.control_strength,
            appearance_ref_filename=appearance_fn, appearance_weight=args.appearance_weight,
            denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint,
        )
    elif args.task == "pose_only":
        pose_fn = upload_image(args.pose_ref)
        prompt, out_id = build_pose_only(args.prompt, pose_fn, args.negative,
                                          width=args.width, height=args.height,
                                          seed=args.seed, pose_strength=args.pose_strength,
                                          batch_size=args.batch, control_type=args.control_type,
                                          lora_name=args.lora, lora_strength=args.lora_strength,
                                          checkpoint=style_checkpoint)
    elif args.task == "style_lock":
        char_fn = upload_image(args.character_ref)
        prompt, out_id = build_style_lock(args.prompt, char_fn, args.negative,
                                           width=args.width, height=args.height,
                                           seed=args.seed, ip_weight=args.ip_weight,
                                           batch_size=args.batch,
                                           lora_name=args.lora, lora_strength=args.lora_strength,
                                           checkpoint=style_checkpoint)
    elif args.task == "refine":
        img_fn = upload_image(args.image)
        prompt, out_id = build_refine(args.prompt, img_fn, args.negative,
                                       denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint)
    elif args.task == "upscale":
        img_fn = upload_image(args.image)
        prompt, out_id = build_upscale(args.prompt, img_fn, args.negative,
                                        scale=args.scale, denoise=args.denoise, seed=args.seed,
                                        checkpoint=style_checkpoint)
    elif args.task == "layer_split":
        img_fn = upload_image(args.image)
        mask_fn = upload_image(args.mask)
        prompt, out_id = build_layer_split(img_fn, mask_fn, args.layer_name)
    else:
        raise SystemExit(f"未知 task: {args.task}")

    if args.task == "icon_asset" or getattr(args, "remove_bg", False):
        attach_bg_removal(prompt, out_id)

    print(f"[送出] task={args.task}")
    history = submit_and_wait(prompt)
    paths = download_outputs(history, output_dir=getattr(args, "output_dir", None))
    for p in paths:
        print(f"[完成] {p}")


if __name__ == "__main__":
    main()
