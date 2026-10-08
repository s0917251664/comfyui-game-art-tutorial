"""第 5.1 階段：6 個圖片 task 改成 runner template 的薄轉接。

形狀對齊 ``tasks/video_edit.py`` 的 VACE：load、resolve、有 ``from_pre`` 才 fill、patch。
``filename_prefix`` 是一般 string slot，呼叫端填 builder 的前綴，resume／覆寫才找得到同一個名字。

sd15 的 concept／icon_asset／refine 若選到的 template 目錄不存在，回傳 None，
呼叫端繼續用 builder（本機沒有 dreamshaper_8，那 13 份 template 沒落地）。
sdxl 與 character_action／pose_only／style_lock 目錄不存在就停止，不改走 builder。
"""
from pathlib import Path

from . import image_graphs
from . import image_runtime
from .image_graphs import ICON_ASSET_NEGATIVE_SUFFIX, ICON_ASSET_PROMPT_SUFFIX, attach_bg_removal
from .image_template_select import variant_id
from .runner import template as runner_template

# builder 寫死的 SaveImage 前綴。template 預設相同；呼叫端仍明確填入。
FILENAME_PREFIX = {
    "concept": "concept",
    "icon_asset": "icon_asset",
    "refine": "refine",
    "character_action": "character_action",
    "pose_only": "pose_only",
    "style_lock": "style_lock",
}
# 只有這三個在 sd15 有對應 variant；目錄缺失時才允許退回 builder。
_SD15_BUILDER_FALLBACK = frozenset({"concept", "icon_asset", "refine"})


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


def _uploads(args, upload):
    """上傳檔名由呼叫端的 upload 回傳（和 builder 路徑一樣）。"""
    found = {}

    def take(slot, path):
        if path:
            found[slot] = upload(path)

    task = args.task
    if task == "refine":
        take("image", args.image)
    elif task == "icon_asset":
        take("structure_ref", getattr(args, "structure_ref", None))
        take("appearance_ref", getattr(args, "appearance_ref", None))
    elif task == "character_action":
        take("character_ref", args.character_ref)
        take("pose_ref", args.pose_ref)
    elif task == "pose_only":
        take("pose_ref", args.pose_ref)
    elif task == "style_lock":
        take("character_ref", args.character_ref)
    return found


def _slot_values(args, slots, style_checkpoint):
    task = args.task
    prompt = args.prompt
    if task == "icon_asset":
        prompt += ICON_ASSET_PROMPT_SUFFIX
    values = {"prompt": prompt, "filename_prefix": FILENAME_PREFIX[task]}
    if getattr(args, "negative", None):
        negative = args.negative
        if task == "icon_asset":
            negative += ICON_ASSET_NEGATIVE_SUFFIX
        _put(values, slots, "negative", negative)
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
    _put(values, slots, "checkpoint", style_checkpoint or image_graphs._default_checkpoint())
    if getattr(args, "lora", None):
        _put(values, slots, "lora_name", args.lora)
        _put(values, slots, "lora_strength", getattr(args, "lora_strength", None))
    _put(values, slots, "pose_strength", getattr(args, "pose_strength", None))
    _put(values, slots, "ip_weight", getattr(args, "ip_weight", None))
    _put(values, slots, "appearance_weight", getattr(args, "appearance_weight", None))
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


def graph_from_template(ctx, args, style_checkpoint, upload):
    """組好就回傳 ``(graph, image_node_id)``。sd15 目錄不存在回傳 None。"""
    if args.task not in FILENAME_PREFIX:
        raise ValueError(f"不是 template 轉接的圖片 task: {args.task}")
    image_runtime.sync_image_runtime(ctx)
    family = image_graphs._active_profile()["family"]
    template_id = variant_id(
        args.task, family,
        lora=bool(getattr(args, "lora", None)),
        remove_bg=wants_background_removal(args),
        control_type=getattr(args, "control_type", None),
        control_backend=getattr(args, "control_backend", "verified") or "verified",
        structure_ref=bool(getattr(args, "structure_ref", None)),
        appearance_ref=bool(getattr(args, "appearance_ref", None)),
    )
    path = _template_json(template_id)
    if path is None or not path.is_file():
        if family == "sd15" and args.task in _SD15_BUILDER_FALLBACK:
            return None
        where = path if path is not None else template_id
        raise SystemExit(
            f"{args.task} 的 graph 在 {template_id}（固定 template，由 runner 填值），"
            f"但找不到 {where}。"
            "請從 repo 執行 python tools_src/generate.py。"
            "SD1.5 的 template 尚未落地時，只有 concept／icon_asset／refine 會改走 builder。"
        )
    root = _repo_root()
    template = runner_template.load_template(
        runner_template.templates_root(root), template_id, repo_root=root)
    values, sampling = _slot_values(args, template.slots, style_checkpoint)
    uploads = _uploads(args, upload)
    resolution = runner_template.resolve(template, {**uploads, **values}, run_id="image-task")
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
