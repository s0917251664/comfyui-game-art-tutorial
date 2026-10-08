"""離線產生 templates/image/**。不進 runner 執行路徑。

呼叫 image_graphs builder（只讀）產生 graph，把會變的文字換成 placeholder、
seed 換成 -1，寫出 graph.api.json 與 template.json。模型 sha256 讀本機 ComfyUI
的檔案；檔案不在磁碟上就不寫該 variant，也不捏造 hash。

用法:
  python tools_src/maintenance/build_image_templates.py --list
  python tools_src/maintenance/build_image_templates.py --write --comfyui C:\\Users\\XU\\ComfyUI --groups sdxl layer_split
"""

import argparse
import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools_src"))

from comfyui_pipeline.image_template_select import GROUPS, iter_variants  # noqa: E402
from comfyui_pipeline.profiles import load_profile  # noqa: E402

_stderr = io.StringIO()
with contextlib.redirect_stderr(_stderr):
    from comfyui_pipeline import image_graphs as ig  # noqa: E402
from comfyui_pipeline.image_graphs import (  # noqa: E402
    ICON_ASSET_NEGATIVE_SUFFIX,
    ICON_ASSET_PROMPT_SUFFIX,
)
from comfyui_pipeline.runner import template as runner_template  # noqa: E402

TEMPLATES = ROOT / "templates"
CACHE_PATH = ROOT / "output" / "image-template-model-hashes.json"
# 本機還沒有 SD1.5 底模時允許跳過；其他檔案缺失就整批停下來。
ALLOWED_MISSING = frozenset({"dreamshaper_8.safetensors"})

FAMILY_DEVICE = {
    "sdxl": {
        "tier": "sdxl", "checkpoint": "sd_xl_base_1.0.safetensors",
        "default_width": 1024, "default_height": 1024,
    },
    "sd15": {
        "tier": "sd15", "checkpoint": "dreamshaper_8.safetensors",
        "default_width": 512, "default_height": 512,
    },
}
FLUX_DIRS = {
    "flux-2-klein-4b-fp8.safetensors": "diffusion_models",
    "flux-2-klein-base-4b-fp8.safetensors": "diffusion_models",
    "qwen_3_4b.safetensors": "text_encoders",
    "flux2-vae.safetensors": "vae",
}
LOADERS = {
    "CheckpointLoaderSimple": ("checkpoint", "ckpt_name"),
    "ControlNetLoader": ("controlnet", "control_net_name"),
    "LoadBackgroundRemovalModel": ("bg_removal", "bg_removal_name"),
    "CLIPVisionLoader": ("clip_vision", "clip_name"),
    "IPAdapterModelLoader": ("ipadapter", "ipadapter_file"),
    "UpscaleModelLoader": ("upscale", "model_name"),
    "UNETLoader": ("unet", "unet_name"),
    "CLIPLoader": ("clip", "clip_name"),
    "VAELoader": ("vae", "vae_name"),
}
UPLOAD_SLOTS = (
    ("__IMAGE__", "image", "image", "來源圖"),
    ("__MASK__", "mask", "mask_image", "遮罩（alpha=0 的區域要重畫或保留進圖層）"),
    ("__POSE_REF__", "pose_ref", "image", "姿勢或結構參考圖"),
    ("__CHARACTER_REF__", "character_ref", "image", "角色參考圖"),
    ("__STRUCTURE_REF__", "structure_ref", "image", "圖示結構參考圖"),
    ("__APPEARANCE_REF__", "appearance_ref", "image", "外觀參考圖"),
    ("__CONTROL_REF__", "control_ref", "image", "guided_inpaint 的 ControlNet 參考圖；沒另給時傳與來源圖相同的上傳名"),
)
TASK_TITLE = {
    "concept": "文字概念圖",
    "icon_asset": "圖示素材",
    "refine": "圖生圖精修",
    "inpaint": "局部重繪",
    "guided_inpaint": "有錨點的局部重繪",
    "character_action": "角色動作",
    "pose_only": "姿勢控制",
    "style_lock": "外觀鎖定",
    "upscale": "放大精修",
    "layer_split": "遮罩拆層",
    "flux2_concept": "FLUX.2 文字概念圖",
    "flux2_edit": "FLUX.2 參考圖編修",
}
BUILDER_NAME = {
    "concept": "build_concept",
    "icon_asset": "build_icon_asset",
    "refine": "build_refine",
    "inpaint": "build_inpaint",
    "guided_inpaint": "build_guided_inpaint",
    "character_action": "build_character_action",
    "pose_only": "build_pose_only",
    "style_lock": "build_style_lock",
    "upscale": "build_upscale",
    "layer_split": "build_layer_split",
    "flux2_concept": "build_flux2_concept",
    "flux2_edit": "build_flux2_edit",
}
SIZE_TASKS = frozenset({"concept", "character_action", "pose_only", "style_lock"})
DENOISE_TASKS = frozenset({"refine", "inpaint", "guided_inpaint", "upscale"})
UPSTREAM_NOTE = (
    "graph 由 image_graphs builder 產生，不是從官方 workflow template 派生。"
    "ComfyUI 0.34.0 內建的官方範本是 UI workflow，對不上這份 API graph，所以 kind 是 none。"
)


class BuildError(RuntimeError):
    pass


def log(message):
    print(message, file=sys.stderr, flush=True)


def dumps(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def activate(family):
    device = FAMILY_DEVICE["sdxl" if family is None else family]
    ig.DEVICE = dict(device)
    ig.CKPT = device["checkpoint"]
    ig.ACTIVE_PROFILE_ID = None


def file_dirs(spec):
    if spec["task"].startswith("flux2"):
        return dict(FLUX_DIRS)
    if spec["task"] == "layer_split":
        return {}
    profile_id = "sd15_light" if spec["family"] == "sd15" else "sdxl_standard"
    found = {}
    for entry in load_profile(profile_id)["models"].values():
        previous = found.get(entry["file"])
        if previous is not None and previous != entry["dir"]:
            raise BuildError(f"{entry['file']} 在 {profile_id} 有兩個 directory")
        found[entry["file"]] = entry["dir"]
    return found


def build_graph(spec):
    """用 placeholder 呼叫 builder。seed 先給 0，稍後改成 -1。"""
    activate(spec["family"])
    task = spec["task"]
    lora_name = "__LORA_NAME__" if spec["lora"] else None
    if task == "concept":
        graph, image_node = ig.build_concept("__PROMPT__", seed=0, lora_name=lora_name)
    elif task == "icon_asset":
        graph, image_node = ig.build_icon_asset(
            "__PROMPT__", seed=0, lora_name=lora_name,
            structure_ref_filename="__STRUCTURE_REF__" if spec["structure_ref"] else None,
            appearance_ref_filename="__APPEARANCE_REF__" if spec["appearance_ref"] else None,
        )
    elif task == "refine":
        graph, image_node = ig.build_refine("__PROMPT__", "__IMAGE__", seed=0)
    elif task == "inpaint":
        graph, image_node = ig.build_inpaint("__PROMPT__", "__IMAGE__", "__MASK__", seed=0)
    elif task == "guided_inpaint":
        kwargs = {}
        if spec["control_type"]:
            kwargs["control_type"] = spec["control_type"]
            kwargs["control_ref_filename"] = "__CONTROL_REF__"
        if spec["appearance_ref"]:
            kwargs["appearance_ref_filename"] = "__APPEARANCE_REF__"
        graph, image_node = ig.build_guided_inpaint("__PROMPT__", "__IMAGE__", "__MASK__", seed=0, **kwargs)
    elif task == "character_action":
        graph, image_node = ig.build_character_action(
            "__PROMPT__", "__CHARACTER_REF__", "__POSE_REF__", seed=0,
            control_type=spec["control_type"] or "canny", lora_name=lora_name,
        )
    elif task == "pose_only":
        graph, image_node = ig.build_pose_only(
            "__PROMPT__", "__POSE_REF__", seed=0,
            control_type=spec["control_type"] or "canny",
            control_backend=spec["control_backend"], lora_name=lora_name,
        )
    elif task == "style_lock":
        graph, image_node = ig.build_style_lock(
            "__PROMPT__", "__CHARACTER_REF__", seed=0, lora_name=lora_name,
        )
    elif task == "upscale":
        graph, image_node = ig.build_upscale("__PROMPT__", "__IMAGE__", seed=0)
    elif task == "layer_split":
        graph, image_node = ig.build_layer_split("__IMAGE__", "__MASK__", "frame")
    elif task == "flux2_concept":
        graph, image_node = ig.build_flux2_concept("__PROMPT__", seed=0)
    elif task == "flux2_edit":
        graph, image_node = ig.build_flux2_edit("__PROMPT__", "__IMAGE__", seed=0)
    else:
        raise BuildError(f"沒有 builder: {task}")
    if spec["remove_bg"]:
        ig.attach_bg_removal(graph, image_node)
    for node in graph.values():
        inputs = node["inputs"]
        for field in ("seed", "noise_seed"):
            if isinstance(inputs.get(field), int):
                inputs[field] = -1
    if task != "layer_split":
        found = 0
        for node in graph.values():
            if node["class_type"] != "CLIPTextEncode":
                continue
            text = node["inputs"].get("text")
            if isinstance(text, str) and text.startswith("__PROMPT__"):
                node["inputs"]["text"] = "__PROMPT__"
                found += 1
        if found != 1:
            raise BuildError(f"{spec['id']}: prompt 占位數量是 {found}（icon 後綴應整段換成 __PROMPT__）")
    return graph


def _targets(graph, class_type, field, predicate):
    found, values = [], []
    for node_id, node in graph.items():
        if node["class_type"] != class_type:
            continue
        value = node["inputs"].get(field)
        if predicate(value):
            found.append({"node": node_id, "input": field})
            values.append(value)
    return found, values


def _one_value(spec_id, label, values):
    if any(item != values[0] or type(item) is not type(values[0]) for item in values):
        raise BuildError(f"{spec_id}: {label} 的預設值不一致 {values!r}")
    return values[0]


def _slot(kind, targets, help_text, *, default=None, required=False, validate=None, upload=False, placeholder=None):
    body = {"type": kind, "targets": []}
    for target in targets:
        item = {"node": target["node"], "input": target["input"]}
        if placeholder:
            item["placeholder"] = placeholder
        body["targets"].append(item)
    if upload:
        body["upload"] = True
    if required:
        body["required"] = True
    elif default is not None or kind == "seed":
        body["default"] = "auto" if kind == "seed" else default
    if validate:
        body["validate"] = validate
    body["help"] = help_text
    return body


def build_slots(spec, graph):
    slots = {}
    task = spec["task"]
    prompt_targets, _ = _targets(graph, "CLIPTextEncode", "text", lambda value: value == "__PROMPT__")
    if prompt_targets:
        slots["prompt"] = _slot(
            "text", prompt_targets, "正向提示詞", required=True,
            validate={"min_length": 1}, placeholder="__PROMPT__",
        )
    if task == "icon_asset":
        help_prompt = (
            "正向提示詞，要含圖示後綴「" + ICON_ASSET_PROMPT_SUFFIX + "」。"
            "builder 會把後綴接在整段文字後面，slot 無法只替換前半段。"
        )
        slots["prompt"]["help"] = help_prompt
    negative_targets, negative_values = _targets(
        graph, "CLIPTextEncode", "text",
        lambda value: isinstance(value, str) and value != "" and not value.startswith("__"),
    )
    if negative_targets:
        default_negative = _one_value(spec["id"], "negative", negative_values)
        help_negative = "負向提示詞"
        if task == "icon_asset":
            help_negative += "。預設已含圖示負向後綴。"
            if not default_negative.endswith(ICON_ASSET_NEGATIVE_SUFFIX):
                raise BuildError(f"{spec['id']}: icon negative 沒有後綴")
        slots["negative"] = _slot("text", negative_targets, help_negative, default=default_negative)

    width_targets, width_values = [], []
    height_targets, height_values = [], []
    for node_id, node in graph.items():
        for field, bucket, values in (
            ("width", width_targets, width_values), ("height", height_targets, height_values),
        ):
            value = node["inputs"].get(field)
            if isinstance(value, int) and not isinstance(value, bool):
                bucket.append({"node": node_id, "input": field})
                values.append(value)
    multiple = 16 if task == "flux2_concept" else 8
    if width_targets or height_targets:
        if not width_targets or not height_targets:
            raise BuildError(f"{spec['id']}: 寬高 slot 不成對")
        if task == "icon_asset":
            size_help = "icon 用家族原生尺寸，不跟 tier 縮小。"
        elif task == "flux2_concept":
            size_help = "FLUX.2 concept 預設 1024，必須是 16 的倍數。"
        else:
            size_help = "用 tier 預設解析度的 task 由呼叫端傳入；template 預設是家族原生尺寸。"
        slots["width"] = _slot(
            "int", width_targets, "寬度。" + size_help,
            default=_one_value(spec["id"], "width", width_values),
            validate={"min": 64, "max": 4096, "multiple_of": multiple},
        )
        slots["height"] = _slot(
            "int", height_targets, "高度。" + size_help,
            default=_one_value(spec["id"], "height", height_values),
            validate={"min": 64, "max": 4096, "multiple_of": multiple},
        )
    batch_targets, batch_values = _targets(
        graph, "EmptyLatentImage", "batch_size", lambda value: isinstance(value, int) and not isinstance(value, bool),
    )
    if batch_targets:
        slots["batch_size"] = _slot(
            "int", batch_targets, "EmptyLatentImage 的張數",
            default=_one_value(spec["id"], "batch_size", batch_values),
            validate={"min": 1, "max": 16},
        )
    seed_targets = []
    for node_id, node in graph.items():
        for field in ("seed", "noise_seed"):
            if node["inputs"].get(field) == -1:
                seed_targets.append({"node": node_id, "input": field})
    if seed_targets:
        slots["seed"] = _slot("seed", seed_targets, "亂數種子。auto 由 runner 抽一個非負整數。")
    step_targets, step_values = _targets(
        graph, "KSampler", "steps", lambda value: isinstance(value, int) and not isinstance(value, bool),
    )
    if step_targets:
        slots["steps"] = _slot(
            "int", step_targets, "KSampler 步數",
            default=_one_value(spec["id"], "steps", step_values), validate={"min": 1, "max": 150},
        )
    cfg_targets, cfg_values = _targets(graph, "KSampler", "cfg", lambda value: isinstance(value, float))
    if cfg_targets:
        slots["cfg"] = _slot(
            "float", cfg_targets, "KSampler CFG",
            default=_one_value(spec["id"], "cfg", cfg_values), validate={"min": 0, "max": 30},
        )
    if task in DENOISE_TASKS:
        denoise_targets, denoise_values = _targets(graph, "KSampler", "denoise", lambda value: isinstance(value, float))
        if denoise_targets:
            slots["denoise"] = _slot(
                "float", denoise_targets, "重繪幅度",
                default=_one_value(spec["id"], "denoise", denoise_values), validate={"min": 0, "max": 1},
            )
    ckpt_targets, ckpt_values = _targets(
        graph, "CheckpointLoaderSimple", "ckpt_name", lambda value: isinstance(value, str) and not value.startswith("__"),
    )
    if ckpt_targets:
        slots["checkpoint"] = _slot(
            "string", ckpt_targets, "底模檔名。預設是這個家族的底模；--style 換檔時由呼叫端傳入。",
            default=_one_value(spec["id"], "checkpoint", ckpt_values),
        )
    lora_targets, _ = _targets(graph, "LoraLoader", "lora_name", lambda value: value == "__LORA_NAME__")
    if lora_targets:
        slots["lora_name"] = _slot(
            "string", lora_targets, "LoRA 檔名。使用者自備，不進 models pin。",
            required=True, placeholder="__LORA_NAME__",
        )
        strength_targets, strength_values = [], []
        for node_id, node in graph.items():
            if node["class_type"] != "LoraLoader":
                continue
            for field in ("strength_model", "strength_clip"):
                strength_targets.append({"node": node_id, "input": field})
                strength_values.append(node["inputs"][field])
        slots["lora_strength"] = _slot(
            "float", strength_targets, "LoRA 強度，同時寫入 strength_model 與 strength_clip",
            default=_one_value(spec["id"], "lora_strength", strength_values), validate={"min": 0, "max": 1},
        )
    if task in ("character_action", "pose_only"):
        pose_targets, pose_values = _targets(graph, "ControlNetApplyAdvanced", "strength", lambda value: isinstance(value, float))
        slots["pose_strength"] = _slot(
            "float", pose_targets, "ControlNet 強度",
            default=_one_value(spec["id"], "pose_strength", pose_values), validate={"min": 0, "max": 1},
        )
    if (task == "icon_asset" and spec["structure_ref"]) or (task == "guided_inpaint" and spec["control_type"]):
        control_targets, control_values = _targets(
            graph, "ControlNetApplyAdvanced", "strength", lambda value: isinstance(value, float),
        )
        slots["control_strength"] = _slot(
            "float", control_targets, "ControlNet 強度",
            default=_one_value(spec["id"], "control_strength", control_values), validate={"min": 0, "max": 1},
        )
    weight_name = None
    if task in ("character_action", "style_lock"):
        weight_name = "ip_weight"
    elif task in ("icon_asset", "guided_inpaint") and spec["appearance_ref"]:
        weight_name = "appearance_weight"
    if weight_name:
        weight_targets, weight_values = _targets(graph, "IPAdapterAdvanced", "weight", lambda value: isinstance(value, float))
        slots[weight_name] = _slot(
            "float", weight_targets, "IPAdapter 權重",
            default=_one_value(spec["id"], weight_name, weight_values), validate={"min": 0, "max": 1},
        )
    scale_targets, scale_values = _targets(graph, "ImageScaleBy", "scale_by", lambda value: isinstance(value, float))
    if scale_targets:
        slots["scale_by"] = _slot(
            "float", scale_targets, "放大模型固定 4 倍後再縮放的倍率。CLI 的 --scale 2 對應 0.5。",
            default=_one_value(spec["id"], "scale_by", scale_values), validate={"min": 0, "max": 1},
        )
    by_placeholder = {marker: (name, kind, help_text) for marker, name, kind, help_text in UPLOAD_SLOTS}
    upload_targets = {name: [] for _marker, name, _kind, _help in UPLOAD_SLOTS}
    for node_id, node in graph.items():
        if node["class_type"] != "LoadImage":
            continue
        marker = node["inputs"].get("image")
        if marker not in by_placeholder:
            raise BuildError(f"{spec['id']}: LoadImage {node_id} 的檔名不是 placeholder: {marker!r}")
        name = by_placeholder[marker][0]
        upload_targets[name].append({"node": node_id, "input": "image"})
    for marker, name, kind, help_text in UPLOAD_SLOTS:
        if upload_targets[name]:
            slots[name] = _slot(kind, upload_targets[name], help_text, required=True, upload=True, placeholder=marker)
    prefix_targets, prefix_values = _targets(
        graph, "SaveImage", "filename_prefix",
        lambda value: isinstance(value, str) and value != "transparent",
    )
    if len(prefix_targets) != 1:
        raise BuildError(f"{spec['id']}: 非 transparent 的 SaveImage 數量是 {len(prefix_targets)}")
    prefix = _one_value(spec["id"], "filename_prefix", prefix_values)
    slots["filename_prefix"] = _slot(
        "string", prefix_targets,
        "存檔前綴，預設沿用 builder。不用 output_prefix，避免被改成 gameart/...",
        default=prefix,
    )
    if task in SIZE_TASKS and "width" not in slots:
        raise BuildError(f"{spec['id']}: 這個 task 應該有寬高 slot")
    return slots


def custom_nodes(graph):
    classes = {node["class_type"] for node in graph.values()}
    found = []
    if classes & {"OpenposePreprocessor", "DepthAnythingV2Preprocessor"}:
        found.append({"id": "comfyui_controlnet_aux", "source": "registry"})
    if classes & {"IPAdapterAdvanced", "IPAdapterModelLoader"}:
        found.append({"id": "comfyui_ipadapter_plus", "source": "registry"})
    return found


def model_needs(spec, graph):
    dirs = file_dirs(spec)
    needs = []
    for node_id, node in graph.items():
        if node["class_type"] not in LOADERS:
            continue
        role, field = LOADERS[node["class_type"]]
        filename = node["inputs"].get(field)
        if not isinstance(filename, str) or filename.startswith("__"):
            raise BuildError(f"{spec['id']}: {node_id}.{field} 不是模型檔名 {filename!r}")
        directory = dirs.get(filename)
        if not directory:
            raise BuildError(f"{spec['id']}: 不知道 {filename} 的 models 子目錄")
        needs.append({
            "role": role, "node": node_id, "input": field, "filename": filename, "directory": directory,
        })
    return needs


def outputs_for(graph):
    saves = [(node_id, node) for node_id, node in graph.items() if node["class_type"] == "SaveImage"]
    transparent = [node_id for node_id, node in saves if node["inputs"].get("filename_prefix") == "transparent"]
    opaque = [node_id for node_id, node in saves if node["inputs"].get("filename_prefix") != "transparent"]
    if transparent:
        if len(transparent) != 1 or len(opaque) != 1:
            raise BuildError(f"去背輸出數量不對: transparent={transparent} opaque={opaque}")
        return [
            {"id": "opaque", "node": opaque[0], "kind": "image", "role": "preview"},
            {"id": "transparent", "node": transparent[0], "kind": "image", "role": "candidate"},
        ]
    if len(saves) != 1:
        raise BuildError(f"SaveImage 數量不對: {[node_id for node_id, _node in saves]}")
    return [{"id": "image", "node": saves[0][0], "kind": "image", "role": "candidate"}]


def title_of(spec):
    bits = []
    if spec["family"]:
        bits.append(spec["family"].upper())
    if spec["control_backend"] == "union":
        bits.append("Union")
    if spec["control_type"]:
        bits.append(spec["control_type"])
    if spec["structure_ref"]:
        bits.append("結構參考")
    if spec["appearance_ref"]:
        bits.append("外觀參考")
    if spec["lora"]:
        bits.append("LoRA")
    if spec["remove_bg"]:
        bits.append("去背")
    base = TASK_TITLE[spec["task"]]
    return f"{base}（{'、'.join(bits)}）" if bits else base


def fixed_notes(spec):
    notes = ["filename_prefix 維持 builder 的前綴，不用 output_prefix。"]
    if spec["family"]:
        notes.append("tier 只影響呼叫端傳入的寬高；template 預設是家族原生尺寸。")
    if spec["lora"]:
        notes.append("LoRA 檔由呼叫端傳入，不進 models pin。")
    if spec["task"] == "icon_asset":
        notes.append("prompt 要傳入已含圖示後綴的完整文字；negative 預設已含圖示負向後綴。")
    if spec["task"].startswith("flux2"):
        notes.append("FLUX.2 的 steps 與 cfg 鎖死，不做成 slot。")
    if spec["task"] == "layer_split":
        notes.append("filename_prefix 預設是 layer_frame。")
    if spec["remove_bg"]:
        notes.append("去背 SaveImage 的前綴維持 transparent，不另做 slot。")
    return "".join(notes)


def template_document(spec, graph, graph_sha, canonical_sha, models):
    slots = build_slots(spec, graph)
    upload_names = [name for _marker, name, _kind, _help in UPLOAD_SLOTS if name in slots]
    return {
        "schema_version": 1,
        "id": spec["id"],
        "version": "0.1.0",
        "title": title_of(spec),
        "summary": f"{title_of(spec)}。固定 API graph，runner 只填 slot。",
        "status": "draft",
        "status_note": "尚未實機執行。windows-cuda 與 macos-mps 都是 untested。",
        "min_comfyui_version": "0.34.0",
        "requires_custom_nodes": custom_nodes(graph),
        "graph": {
            "file": "graph.api.json",
            "format": "comfyui-api",
            "sha256": graph_sha,
            "canonical_sha256": canonical_sha,
        },
        "provenance": {
            "derived_from": (
                f"comfyui_pipeline.image_graphs.{BUILDER_NAME[spec['task']]}；"
                "離線產生器 tools_src/maintenance/build_image_templates.py"
            ),
            "upstream": {
                "kind": "none",
                "name": None,
                "blob": None,
                "comfyui_version": None,
                "note": UPSTREAM_NOTE,
            },
            "tested_source_sha256": None,
            "evidence": [
                {"path": "tools_src/comfyui_pipeline/image_graphs.py", "note": "graph 的 builder"},
                {"path": "tests/fixtures/image_graphs_golden/sdxl.json", "note": "圖片 golden graph"},
                {
                    "path": "docs/knowledge/decisions/2026-10-08-image-template-variants.md",
                    "note": "方案 A 與家族對應的決定",
                },
            ],
        },
        "slots": slots,
        "options": {},
        "fixed_notes": fixed_notes(spec),
        "pre": [{"step": "upload", "slots": upload_names}] if upload_names else [],
        "post": [],
        "frame_anchoring": {
            "first": "none",
            "last": "none",
            "reference_role": "none",
            "time_alignment": None,
            "continuity": None,
        },
        "models": models,
        "capability_gate": {
            "nodes": "from_graph",
            "selectors": "from_models",
            "files": "from_models",
            "extra_nodes": [],
            "platforms": {
                "windows-cuda": {"status": "untested"},
                "macos-mps": {"status": "untested"},
            },
            "min_memory_mb": None,
            "capability": "image_generation",
        },
        "outputs": outputs_for(graph),
    }


class Hasher:
    def __init__(self, comfyui):
        self.models = Path(comfyui) / "models"
        self.cache = {}
        if CACHE_PATH.is_file():
            self.cache = json.loads(CACHE_PATH.read_bytes().decode("utf-8"))

    def save(self):
        write_bytes(CACHE_PATH, dumps(self.cache))

    def measure(self, filename, directory):
        path = self.models / directory / filename
        if not path.is_file():
            return None
        stat = path.stat()
        key = str(path)
        cached = self.cache.get(key)
        if cached and cached.get("size") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns:
            digest = cached["sha256"]
        else:
            log(f"hash {filename} ({stat.st_size} bytes)")
            digest = sha256_file(path)
            self.cache[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": digest}
            self.save()
        return {
            "path": f"models/{directory}/{filename}",
            "size_bytes": stat.st_size,
            "sha256": digest,
        }


def _check_document(spec, graph, needs):
    """先用占位 hash 跑 validator，模型檔還沒讀完就擋下 slot／結構錯誤。"""
    placeholder = {
        (item["directory"], item["filename"]): {
            "path": f"models/{item['directory']}/{item['filename']}",
            "size_bytes": 1,
            "sha256": "0" * 64,
        }
        for item in needs
    }
    graph_bytes = dumps(graph)
    document = template_document(
        spec, graph, hashlib.sha256(graph_bytes).hexdigest(),
        runner_template.canonical_sha256(graph), pin_models(needs, placeholder),
    )
    template = runner_template.Template(
        spec["id"], TEMPLATES.joinpath(*spec["id"].split("/")), document, graph,
        document["graph"]["sha256"], document["graph"]["canonical_sha256"], "0" * 64,
    )
    problems = runner_template.validate_template(template, ROOT)
    if problems:
        raise BuildError(spec["id"] + ":\n" + "\n".join(problems))


def pin_models(needs, measured):
    pins = []
    for item in needs:
        meta = measured[(item["directory"], item["filename"])]
        pins.append({
            "role": item["role"],
            "node": item["node"],
            "input": item["input"],
            "filename": item["filename"],
            "path": meta["path"],
            "directory": item["directory"],
            "size_bytes": meta["size_bytes"],
            "sha256": meta["sha256"],
            "source": None,
            "url": None,
        })
    return pins


def comfyui_root(arg):
    if arg:
        return Path(arg)
    config_path = ROOT / "local_config.json"
    if not config_path.is_file():
        raise BuildError("沒有 --comfyui，而且 repo 沒有 local_config.json")
    config = json.loads(config_path.read_bytes().decode("utf-8"))
    raw = config.get("comfyui_path")
    if not raw:
        raise BuildError("local_config.json 沒有 comfyui_path")
    return Path(raw)


def write_groups(groups, comfyui):
    hasher = Hasher(comfyui)
    if not hasher.models.is_dir():
        raise BuildError(f"找不到模型目錄 {hasher.models}")
    built, skipped = [], []
    for spec in iter_variants(*groups):
        graph = build_graph(spec)
        needs = model_needs(spec, graph)
        missing_paths = []
        unexpected = []
        for item in needs:
            path = hasher.models / item["directory"] / item["filename"]
            if path.is_file():
                continue
            if item["filename"] in ALLOWED_MISSING:
                missing_paths.append(path)
            else:
                unexpected.append(path)
        if unexpected:
            lines = "\n".join(f"  {spec['id']}: {path}" for path in unexpected)
            raise BuildError(f"模型檔不在磁碟上，已停止，不寫假 hash:\n{lines}")
        if missing_paths:
            skipped.append((spec["id"], missing_paths))
            log(f"skip {spec['id']}: 缺少 {', '.join(path.name for path in missing_paths)}")
            continue
        _check_document(spec, graph, needs)
        built.append((spec, graph, needs))
    measured = {}
    for _spec, _graph, needs in built:
        for item in needs:
            key = (item["directory"], item["filename"])
            if key not in measured:
                measured[key] = hasher.measure(item["filename"], item["directory"])
                if measured[key] is None:
                    raise BuildError(f"剛才還在的檔案消失了: {key}")
    written = []
    for spec, graph, needs in built:
        folder = TEMPLATES.joinpath(*spec["id"].split("/"))
        graph_bytes = dumps(graph)
        document = template_document(
            spec, graph, hashlib.sha256(graph_bytes).hexdigest(),
            runner_template.canonical_sha256(graph), pin_models(needs, measured),
        )
        write_bytes(folder / "graph.api.json", graph_bytes)
        write_bytes(folder / "template.json", dumps(document))
        runner_template.load_template(TEMPLATES, spec["id"], repo_root=ROOT)
        written.append(spec["id"])
        log(f"wrote {spec['id']}")
    return written, skipped


def main(argv):
    parser = argparse.ArgumentParser(description="離線產生圖片 template")
    parser.add_argument("--comfyui", help="ComfyUI 根目錄。未給則讀 local_config.json 的 comfyui_path")
    parser.add_argument("--groups", nargs="+", choices=GROUPS, default=["sdxl", "layer_split", "flux2"])
    parser.add_argument("--list", action="store_true", help="只印 template id")
    parser.add_argument("--write", action="store_true", help="寫入 templates/image 並用 load_template 驗證")
    args = parser.parse_args(argv)
    specs = list(iter_variants(*args.groups))
    if args.list or not args.write:
        for spec in specs:
            print(spec["id"])
        print(f"{len(specs)} templates", file=sys.stderr)
        return 0 if args.list else 2
    try:
        written, skipped = write_groups(args.groups, comfyui_root(args.comfyui))
    except (BuildError, runner_template.TemplateError) as exc:
        log(str(exc))
        return 1
    log(f"wrote {len(written)}; skipped {len(skipped)}")
    for template_id, paths in skipped:
        log(f"  skipped {template_id}: {', '.join(str(path) for path in paths)}")
    return 2 if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
