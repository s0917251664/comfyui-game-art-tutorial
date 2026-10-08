"""圖片 task 改成 runner template 的薄轉接。

第 5.1 階段：concept、icon_asset、refine、character_action、pose_only、style_lock。
第 5.2 階段：inpaint、guided_inpaint、upscale、layer_split、flux2_concept、flux2_edit。
形狀對齊 ``tasks/video_edit.py`` 的 VACE：load、resolve、有 ``from_pre`` 才 fill、patch。
不呼叫 ``runner.run``（那會 queue）。``filename_prefix`` 是一般 string slot，呼叫端填
builder 的前綴；layer_split 用 ``layer_<layer_name>``。

sd15 的 concept／icon_asset／refine／inpaint／guided_inpaint／upscale
若選到的 template 目錄不存在，回傳 None，呼叫端繼續用 builder
（本機沒有 dreamshaper_8，sd15 template 沒落地）。
sdxl、layer_split、FLUX.2，以及 character_action／pose_only／style_lock
目錄不存在就停止，不改走 builder。
"""
from pathlib import Path

from . import image_graphs
from . import image_runtime
from .image_graphs import ICON_ASSET_NEGATIVE_SUFFIX, ICON_ASSET_PROMPT_SUFFIX, attach_bg_removal
from .image_template_select import variant_id
from .runner import template as runner_template

# builder 寫死的 SaveImage 前綴。template 預設相同；呼叫端仍明確填入。
# layer_split 的前綴含 --layer-name，不在這張表。
FILENAME_PREFIX = {
    "concept": "concept",
    "icon_asset": "icon_asset",
    "refine": "refine",
    "character_action": "character_action",
    "pose_only": "pose_only",
    "style_lock": "style_lock",
    "inpaint": "inpaint",
    "guided_inpaint": "guided_inpaint",
    "upscale": "upscale",
    "flux2_concept": "flux2_concept",
    "flux2_edit": "flux2_edit",
}
_FAMILY_FREE = frozenset({"layer_split", "flux2_concept", "flux2_edit"})
_TEMPLATE_TASKS = frozenset(FILENAME_PREFIX) | _FAMILY_FREE
# sd15 目錄缺失時才允許退回 builder。layer_split／FLUX.2 不分家族，不在這張表。
_SD15_BUILDER_FALLBACK = frozenset({
    "concept", "icon_asset", "refine", "inpaint", "guided_inpaint", "upscale",
})


def wants_background_removal(args):
    """CLI 會去背的情況：icon_asset 一定去背，其餘看 --remove-bg。"""
    return args.task == "icon_asset" or bool(getattr(args, "remove_bg", False))


def _repo_root():
    """從這個檔案往上找含 SDXL concept template 的 repo。部署到 ComfyUI/tools 時還沒有 templates/。"""
    for parent in Path(__file__).resolve().parents:
        marker = parent / "templates" / "image" / "sdxl" / "concept" / "template.json"
        if marker.is_file():
            return parent
    return None


def _template_json(template_id):
    root = _repo_root()
    if root is None:
        return None
    return root.joinpath("templates", *template_id.split("/"), "template.json")


def _put(values, slots, name, value):
    if value is not None and name in slots:
        values[name] = value


def _canvas(task, args):
    """跟 builder 同一套預設寬高。icon 用家族原生尺寸，不跟 tier 縮小。"""
    if task == "icon_asset":
        native_w, native_h = image_graphs._active_profile()["resolution"]["native"]
        width = native_w if getattr(args, "width", None) is None else args.width
        height = native_h if getattr(args, "height", None) is None else args.height
    else:
        default_w, default_h = image_graphs._default_size()
        width = default_w if getattr(args, "width", None) is None else args.width
        height = default_h if getattr(args, "height", None) is None else args.height
    return width, height


def _filename_prefix(args):
    """builder 的 SaveImage 前綴。layer_split 用 ``layer_<layer_name>``，不要寫死。"""
    if args.task == "layer_split":
        return f"layer_{args.layer_name}"
    return FILENAME_PREFIX[args.task]


def _local_paths(args):
    """本機路徑，只交給 resolve。沒有的參考圖不放；沒給 control-type 就不放 control。"""
    task = args.task
    paths = {}

    def keep(slot, path):
        if path:
            paths[slot] = path

    if task == "refine":
        keep("image", args.image)
    elif task == "icon_asset":
        keep("structure_ref", getattr(args, "structure_ref", None))
        keep("appearance_ref", getattr(args, "appearance_ref", None))
    elif task == "character_action":
        keep("character_ref", args.character_ref)
        keep("pose_ref", args.pose_ref)
    elif task == "pose_only":
        keep("pose_ref", args.pose_ref)
    elif task == "style_lock":
        keep("character_ref", args.character_ref)
    elif task in ("inpaint", "upscale", "layer_split", "flux2_edit"):
        keep("image", args.image)
        if task in ("inpaint", "layer_split"):
            keep("mask", args.mask)
    elif task == "guided_inpaint":
        keep("image", args.image)
        keep("mask", args.mask)
        if getattr(args, "control_type", None):
            keep("control_ref", args.control_ref or args.image)
        if getattr(args, "appearance_ref", None):
            keep("appearance_ref", args.appearance_ref)
    return paths


def _upload_paths(args, local_paths, upload):
    """先 upload。有 control-type 但沒給 --control-ref 時，結構圖沿用已上傳的來源圖。"""
    uploaded = {}
    for slot, path in local_paths.items():
        if slot == "control_ref" and not getattr(args, "control_ref", None):
            uploaded[slot] = uploaded["image"]
            continue
        uploaded[slot] = upload(path)
    return uploaded


def _slot_values(args, slots, style_checkpoint):
    task = args.task
    values = {}
    if "prompt" in slots:
        prompt = args.prompt
        if task == "icon_asset":
            prompt += ICON_ASSET_PROMPT_SUFFIX
        values["prompt"] = prompt
    if "filename_prefix" in slots:
        values["filename_prefix"] = _filename_prefix(args)
    if getattr(args, "negative", None):
        negative = args.negative
        if task == "icon_asset":
            negative += ICON_ASSET_NEGATIVE_SUFFIX
        _put(values, slots, "negative", negative)
    if "width" in slots or "height" in slots:
        if task == "flux2_concept":
            width, height = args.width, args.height
        else:
            width, height = _canvas(task, args)
        _put(values, slots, "width", width)
        _put(values, slots, "height", height)
    _put(values, slots, "batch_size", getattr(args, "batch", None))
    # 省略 --seed 時只抽一次，而且用 builder 的 48-bit。留給 slot 的 "auto" 會再抽 32-bit。
    _put(values, slots, "seed", image_graphs.seed_or_random(getattr(args, "seed", None)))
    sampling = image_graphs._resolve_sampling()
    _put(values, slots, "steps", sampling["steps"])
    _put(values, slots, "cfg", sampling["cfg"])
    _put(values, slots, "denoise", getattr(args, "denoise", None))
    scale = getattr(args, "scale", None)
    if scale is not None:
        _put(values, slots, "scale_by", scale / 4.0)
    if "checkpoint" in slots:
        _put(values, slots, "checkpoint", style_checkpoint or image_graphs._default_checkpoint())
    if getattr(args, "lora", None):
        _put(values, slots, "lora_name", args.lora)
        _put(values, slots, "lora_strength", getattr(args, "lora_strength", None))
    _put(values, slots, "pose_strength", getattr(args, "pose_strength", None))
    _put(values, slots, "ip_weight", getattr(args, "ip_weight", None))
    _put(values, slots, "appearance_weight", getattr(args, "appearance_weight", None))
    _put(values, slots, "control_strength", getattr(args, "control_strength", None))
    return values, sampling


def _align_baked_sampling(graph, sampling):
    """sampler／scheduler 不是 slot，烤的是產生 template 時的設定檔。

    和目前設定檔相同就不改。不同才改 KSampler 這兩個欄位，否則送出的 graph 對不上 builder。
    回傳實際改過的 ``node.field``；目前兩份設定檔都是 euler／normal，正常是空清單。
    """
    changed = []
    for node_id, node in graph.items():
        if not isinstance(node, dict) or node.get("class_type") != "KSampler":
            continue
        inputs = node.get("inputs") or {}
        for field, key in (("sampler_name", "sampler"), ("scheduler", "scheduler")):
            if inputs.get(field) != sampling[key]:
                inputs[field] = sampling[key]
                changed.append(f"{node_id}.{field}")
    return changed


def _image_node(graph):
    """builder 回傳的是不透明 SaveImage 前面的圖片節點，不是 SaveImage 本身。"""
    for node in graph.values():
        if not isinstance(node, dict) or node.get("class_type") != "SaveImage":
            continue
        inputs = node.get("inputs") or {}
        if inputs.get("filename_prefix") == "transparent":
            continue
        images = inputs.get("images")
        if isinstance(images, list) and images:
            return str(images[0])
    raise RuntimeError("template graph 沒有不透明的 SaveImage，無法對齊 builder 的輸出節點")


def _variant_flags(args):
    return dict(
        lora=bool(getattr(args, "lora", None)),
        remove_bg=wants_background_removal(args),
        control_type=getattr(args, "control_type", None),
        control_backend=getattr(args, "control_backend", "verified") or "verified",
        structure_ref=bool(getattr(args, "structure_ref", None)),
        appearance_ref=bool(getattr(args, "appearance_ref", None)),
    )


def graph_from_template(ctx, args, style_checkpoint, upload):
    """組好就回傳 ``(graph, image_node_id)``。sd15 目錄不存在回傳 None，且尚未 upload。"""
    if args.task not in _TEMPLATE_TASKS:
        raise ValueError(f"不是 template 轉接的圖片 task: {args.task}")
    image_runtime.sync_image_runtime(ctx)
    flags = _variant_flags(args)
    family = None
    if args.task in _FAMILY_FREE:
        template_id = variant_id(args.task, **flags)
    else:
        family = image_graphs._active_profile()["family"]
        try:
            template_id = variant_id(args.task, family, **flags)
        except ValueError:
            # sd15 不支援的組合（例如 guided 的 ControlNet）沒有 template，維持 builder 的錯誤。
            if family == "sd15" and args.task in _SD15_BUILDER_FALLBACK:
                return None
            raise
    path = _template_json(template_id)
    if path is None or not path.is_file():
        if family == "sd15" and args.task in _SD15_BUILDER_FALLBACK:
            return None
        where = path if path is not None else template_id
        raise SystemExit(
            f"{args.task} 的 graph 在 {template_id}（固定 template，由 runner 填值），"
            f"但找不到 {where}。"
            "請從 repo 執行 python tools_src/generate.py。"
            "SD1.5 的 template 尚未落地時，concept／icon_asset／refine／"
            "inpaint／guided_inpaint／upscale 會改走 builder。"
            "SDXL、layer_split 與 FLUX.2 不會改走 builder。"
        )
    root = _repo_root()
    template = runner_template.load_template(
        runner_template.templates_root(root), template_id, repo_root=root)
    values, sampling = _slot_values(args, template.slots, style_checkpoint)
    local_paths = _local_paths(args)
    uploads = _upload_paths(args, local_paths, upload)
    resolution = runner_template.resolve(template, {**local_paths, **values}, run_id="image-task")
    if any(slot.get("from_pre") for slot in template.slots.values()):
        runner_template.fill_from_pre(template, resolution, {})
    graph, _changes = runner_template.patch(template, resolution, uploads)
    _align_baked_sampling(graph, sampling)
    return graph, _image_node(graph)


def transparent_save_id(graph):
    for node_id, node in graph.items():
        if not isinstance(node, dict) or node.get("class_type") != "SaveImage":
            continue
        if (node.get("inputs") or {}).get("filename_prefix") == "transparent":
            return node_id
    return None


def background_removal_output(graph, image_node_id):
    """去背 SaveImage 的節點 id。template 已含去背就不要再接一次，否則 graph sha256 會變。

    sd15 仍走 builder 時 graph 沒有這顆節點，沿用 ``attach_bg_removal``。
    """
    found = transparent_save_id(graph)
    if found is not None:
        return found
    return attach_bg_removal(graph, image_node_id)
