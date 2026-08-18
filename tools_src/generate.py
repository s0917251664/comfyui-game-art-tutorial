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
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

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
                   lora_name=None, lora_strength=0.8):
    width = width or DEVICE["default_width"]
    height = height or DEVICE["default_height"]
    negative = negative or DEFAULT_NEGATIVE
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}}}
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


# ---------- task: character_action(Ch7 ControlNet + Ch8 IPAdapter 合併)----------
def build_character_action(prompt, character_ref_filename, pose_ref_filename, negative=None,
                            width=None, height=None, seed=None, steps=25, cfg=7.0,
                            ip_weight=0.8, pose_strength=1.0, batch_size=1, control_type="canny",
                            lora_name=None, lora_strength=0.8):
    negative = negative or DEFAULT_NEGATIVE
    width = width or DEVICE["default_width"]
    height = height or DEVICE["default_height"]
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}}}
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
                   seed=None, steps=25, cfg=7.0, grow_mask_by=6):
    negative = negative or DEFAULT_NEGATIVE
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
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


# ---------- task: guided_inpaint(局部重繪 + ControlNet 結構鎖定)----------
# 解決 inpaint 大範圍全自由重繪的失敗模式:遮罩範圍內同時要求「結構(手指關節/物體輪廓)
# 不能崩」跟「外觀(武器造型/材質紋路)要換」時,純 inpaint 沒有任何錨點,兩者一起賭,
# 失敗率會疊乘(2026-08-18 女角色武器置換連續失敗多次才確認這個問題,不是遮罩位置或
# prompt 措辭能解決的)。guided_inpaint 額外疊一層 ControlNet:遮罩範圍內結構被控制圖
# 釘住,只有外觀由 denoise 自由生成——control_type 依需求選:pose 用於手部/肢體姿勢類
# 需求(換武器同時保持握姿),canny/depth 用於物體輪廓/立體起伏類需求(換材質紋路同時
# 保持造型,例如龍鱗紋路、道具圖示材質變體)。control_ref 預設沿用 --image 本身(從同一
# 張圖抽取結構),需要用不同圖的結構當引導時才另外指定。
def build_guided_inpaint(prompt, image_filename, mask_filename, control_ref_filename, negative=None,
                          control_type="canny", control_strength=1.0, denoise=1.0,
                          seed=None, steps=25, cfg=7.0, grow_mask_by=6):
    negative = negative or DEFAULT_NEGATIVE
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "5": {"class_type": "LoadImage", "inputs": {"image": mask_filename}},
        "6": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {"pixels": ["4", 0], "vae": ["1", 2], "mask": ["5", 1], "grow_mask_by": grow_mask_by},
        },
        "7": {"class_type": "LoadImage", "inputs": {"image": control_ref_filename}},
    }
    graph["8"] = build_control_preprocessor(control_type, "7")
    graph.update({
        "9": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODELS[control_type]}},
        "10": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["2", 0], "negative": ["3", 0], "control_net": ["9", 0], "image": ["8", 0],
                "strength": control_strength, "start_percent": 0.0, "end_percent": 1.0,
            },
        },
        "11": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0], "positive": ["10", 0], "negative": ["10", 1], "latent_image": ["6", 0],
                "seed": seed_or_random(seed), "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            },
        },
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["1", 2]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "guided_inpaint"}},
    })
    return graph, "12"


# ---------- task: pose_only(Ch7:單獨 ControlNet,不鎖角色)----------
def build_pose_only(prompt, pose_ref_filename, negative=None, width=None, height=None,
                     seed=None, steps=25, cfg=7.0, pose_strength=1.0, batch_size=1,
                     control_type="canny", lora_name=None, lora_strength=0.8):
    negative = negative or DEFAULT_NEGATIVE
    width = width or DEVICE["default_width"]
    height = height or DEVICE["default_height"]
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}}}
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
                      lora_name=None, lora_strength=0.8):
    negative = negative or DEFAULT_NEGATIVE
    width = width or DEVICE["default_width"]
    height = height or DEVICE["default_height"]
    graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}}}
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
                  seed=None, steps=25, cfg=7.0):
    negative = negative or DEFAULT_NEGATIVE
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
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
                   seed=None, steps=25, cfg=7.0):
    negative = negative or DEFAULT_NEGATIVE
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
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


def attach_bg_removal(prompt, image_node_id):
    """在既有 graph 後面接上去背,回傳新增節點後的 SaveImage 節點 id(RGBA)。"""
    next_id = str(max(int(k) for k in prompt.keys()) + 1)
    n1, n2, n3 = next_id, str(int(next_id) + 1), str(int(next_id) + 2)
    prompt[n1] = {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}}
    prompt[n2] = {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": [n1, 0], "image": [image_node_id, 0]}}
    prompt[n3] = {"class_type": "JoinImageWithAlpha", "inputs": {"image": [image_node_id, 0], "alpha": [n2, 0]}}
    save_id = str(int(n3) + 1)
    prompt[save_id] = {"class_type": "SaveImage", "inputs": {"images": [n3, 0], "filename_prefix": "transparent"}}
    return save_id


def main():
    ap = argparse.ArgumentParser(description="穩定產圖核心腳本")
    sub = ap.add_subparsers(dest="task", required=True)

    # 共用參數:每個 task 都能指定成品要存去哪(不指定就用預設的 tools/generated/)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-dir", help=f"成品存放資料夾,預設 {OUTPUT_DIR}")

    p_concept = sub.add_parser("concept", help="概念圖(純文字)", parents=[common])
    p_concept.add_argument("--prompt", required=True)
    p_concept.add_argument("--negative")
    p_concept.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_concept.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_concept.add_argument("--seed", type=int)
    p_concept.add_argument("--batch", type=int, default=1, help="一次生成幾個版本比較")
    p_concept.add_argument("--lora", help="LoRA 檔名(models/loras/ 底下),不給就不套用")
    p_concept.add_argument("--lora-strength", type=float, default=0.8)
    p_concept.add_argument("--remove-bg", action="store_true")

    p_char = sub.add_parser("character_action", help="角色動作圖(角色參考圖 + 姿勢線稿)", parents=[common])
    p_char.add_argument("--prompt", required=True)
    p_char.add_argument("--character-ref", required=True, help="角色參考圖路徑")
    p_char.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_char.add_argument("--negative")
    p_char.add_argument("--ip-weight", type=float, default=0.8)
    p_char.add_argument("--pose-strength", type=float, default=1.0)
    p_char.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="姿勢/構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_char.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_char.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_char.add_argument("--seed", type=int)
    p_char.add_argument("--batch", type=int, default=1, help="一次生成幾個版本比較")
    p_char.add_argument("--lora", help="LoRA 檔名(models/loras/ 底下),不給就不套用")
    p_char.add_argument("--lora-strength", type=float, default=0.8)
    p_char.add_argument("--remove-bg", action="store_true")

    p_inpaint = sub.add_parser("inpaint", help="局部調整(需要來源圖 + 遮罩圖)", parents=[common])
    p_inpaint.add_argument("--prompt", required=True)
    p_inpaint.add_argument("--image", required=True, help="來源圖路徑")
    p_inpaint.add_argument("--mask", required=True, help="遮罩圖路徑(需帶 alpha 通道,要重畫的區域 alpha=0/透明,其餘 alpha=255/不透明——用 ComfyUI MaskEditor 存的檔案格式一定對)")
    p_inpaint.add_argument("--negative")
    p_inpaint.add_argument("--denoise", type=float, default=1.0)
    p_inpaint.add_argument("--seed", type=int)

    p_guided = sub.add_parser(
        "guided_inpaint",
        help="局部重繪 + ControlNet 結構鎖定(遮罩範圍內結構被釘住,只有外觀自由生成;用於換武器/道具但要保持握姿、換材質紋路但要保持造型這類需求)",
        parents=[common],
    )
    p_guided.add_argument("--prompt", required=True)
    p_guided.add_argument("--image", required=True, help="來源圖路徑")
    p_guided.add_argument("--mask", required=True, help="遮罩圖路徑(同 inpaint,需帶 alpha 通道,要重畫的區域 alpha=0)")
    p_guided.add_argument("--control-ref", help="結構引導來源圖路徑,不給就用 --image 本身(從同一張圖抽取結構)")
    p_guided.add_argument("--control-type", choices=["canny", "pose", "depth"], required=True,
                           help="要鎖定的結構類型:pose=骨架關節(手部/肢體動作類需求),canny=輪廓邊緣、depth=立體起伏(材質/紋路類需求)")
    p_guided.add_argument("--control-strength", type=float, default=1.0)
    p_guided.add_argument("--negative")
    p_guided.add_argument("--denoise", type=float, default=1.0)
    p_guided.add_argument("--seed", type=int)

    p_pose = sub.add_parser("pose_only", help="單獨用姿勢/線稿控制構圖,不鎖角色一致性", parents=[common])
    p_pose.add_argument("--prompt", required=True)
    p_pose.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_pose.add_argument("--negative")
    p_pose.add_argument("--pose-strength", type=float, default=1.0)
    p_pose.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_pose.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_pose.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_pose.add_argument("--seed", type=int)
    p_pose.add_argument("--batch", type=int, default=1, help="一次生成幾個版本比較")
    p_pose.add_argument("--lora", help="LoRA 檔名(models/loras/ 底下),不給就不套用")
    p_pose.add_argument("--lora-strength", type=float, default=0.8)
    p_pose.add_argument("--remove-bg", action="store_true")

    p_style = sub.add_parser("style_lock", help="單獨鎖角色/風格一致性,姿勢隨意(不需要姿勢參考圖)", parents=[common])
    p_style.add_argument("--prompt", required=True)
    p_style.add_argument("--character-ref", required=True, help="角色/風格參考圖路徑")
    p_style.add_argument("--negative")
    p_style.add_argument("--ip-weight", type=float, default=0.8)
    p_style.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_style.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_style.add_argument("--seed", type=int)
    p_style.add_argument("--batch", type=int, default=1, help="一次生成幾個版本比較")
    p_style.add_argument("--lora", help="LoRA 檔名(models/loras/ 底下),不給就不套用")
    p_style.add_argument("--lora-strength", type=float, default=0.8)
    p_style.add_argument("--remove-bg", action="store_true")

    p_refine = sub.add_parser("refine", help="圖生圖:草稿精緻化 / 材質顏色變體(保留原圖構圖)", parents=[common])
    p_refine.add_argument("--prompt", required=True)
    p_refine.add_argument("--image", required=True, help="來源圖路徑(草稿或要換材質的圖)")
    p_refine.add_argument("--negative")
    p_refine.add_argument("--denoise", type=float, default=0.6, help="0.3~0.4 大致保留構圖只上色;0.6~0.7 細節大幅改變;0.9+ 幾乎重畫")
    p_refine.add_argument("--seed", type=int)
    p_refine.add_argument("--remove-bg", action="store_true")

    p_upscale = sub.add_parser("upscale", help="放大精修(放大模型 + 二次取樣補細節,不是單純拉大)", parents=[common])
    p_upscale.add_argument("--prompt", required=True, help="用來引導二次取樣補細節,通常沿用原本生成這張圖時的 prompt")
    p_upscale.add_argument("--image", required=True, help="來源圖路徑(要放大的圖)")
    p_upscale.add_argument("--negative")
    p_upscale.add_argument("--scale", type=float, default=2.0, help="相對原圖的放大倍率(預設 2 倍),最高 4 倍")
    p_upscale.add_argument("--denoise", type=float, default=0.4, help="二次取樣補細節的強度:太低細節補不夠,太高會偏離原圖構圖")
    p_upscale.add_argument("--seed", type=int)

    args = ap.parse_args()

    if args.task == "concept":
        prompt, out_id = build_concept(args.prompt, args.negative, args.width, args.height, args.seed,
                                        batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength)
    elif args.task == "character_action":
        char_fn = upload_image(args.character_ref)
        pose_fn = upload_image(args.pose_ref)
        prompt, out_id = build_character_action(
            args.prompt, char_fn, pose_fn, args.negative,
            width=args.width, height=args.height,
            seed=args.seed, ip_weight=args.ip_weight, pose_strength=args.pose_strength,
            batch_size=args.batch, control_type=args.control_type,
            lora_name=args.lora, lora_strength=args.lora_strength,
        )
    elif args.task == "inpaint":
        img_fn = upload_image(args.image)
        mask_fn = upload_image(args.mask)
        prompt, out_id = build_inpaint(args.prompt, img_fn, mask_fn, args.negative,
                                        denoise=args.denoise, seed=args.seed)
    elif args.task == "guided_inpaint":
        img_fn = upload_image(args.image)
        mask_fn = upload_image(args.mask)
        control_fn = upload_image(args.control_ref) if args.control_ref else img_fn
        prompt, out_id = build_guided_inpaint(
            args.prompt, img_fn, mask_fn, control_fn, args.negative,
            control_type=args.control_type, control_strength=args.control_strength,
            denoise=args.denoise, seed=args.seed,
        )
    elif args.task == "pose_only":
        pose_fn = upload_image(args.pose_ref)
        prompt, out_id = build_pose_only(args.prompt, pose_fn, args.negative,
                                          width=args.width, height=args.height,
                                          seed=args.seed, pose_strength=args.pose_strength,
                                          batch_size=args.batch, control_type=args.control_type,
                                          lora_name=args.lora, lora_strength=args.lora_strength)
    elif args.task == "style_lock":
        char_fn = upload_image(args.character_ref)
        prompt, out_id = build_style_lock(args.prompt, char_fn, args.negative,
                                           width=args.width, height=args.height,
                                           seed=args.seed, ip_weight=args.ip_weight,
                                           batch_size=args.batch,
                                           lora_name=args.lora, lora_strength=args.lora_strength)
    elif args.task == "refine":
        img_fn = upload_image(args.image)
        prompt, out_id = build_refine(args.prompt, img_fn, args.negative,
                                       denoise=args.denoise, seed=args.seed)
    elif args.task == "upscale":
        img_fn = upload_image(args.image)
        prompt, out_id = build_upscale(args.prompt, img_fn, args.negative,
                                        scale=args.scale, denoise=args.denoise, seed=args.seed)
    else:
        raise SystemExit(f"未知 task: {args.task}")

    if getattr(args, "remove_bg", False):
        attach_bg_removal(prompt, out_id)

    print(f"[送出] task={args.task}")
    history = submit_and_wait(prompt)
    paths = download_outputs(history, output_dir=getattr(args, "output_dir", None))
    for p in paths:
        print(f"[完成] {p}")


if __name__ == "__main__":
    main()
