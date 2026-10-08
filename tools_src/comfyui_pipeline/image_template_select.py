"""圖片 task 的結構旗標 → template id。

concept、icon_asset、refine、character_action、pose_only、style_lock、
inpaint、guided_inpaint、upscale、layer_split、flux2_concept、flux2_edit
用這支選 template，再由 ``image_from_template`` 填 slot。
sd15 目錄還沒落地時，concept／icon_asset／refine／inpaint／guided_inpaint／upscale
仍走 builder。layer_split 與 FLUX.2 不分家族，找不到 template 就停止。

id 規則（方案 A，每種會增刪或更換節點的組合各一份）:
``image/<family>/<task 詞幹>[-union-<type>|-<type>][-structure][-appearance][-lora][-transparent]``。
layer_split 與 FLUX.2 不分家族：``image/layer-split``、``image/flux2/concept``、``image/flux2/edit``。
sd15 沒有 ControlNet、IPAdapter、character_action、pose_only、style_lock。
"""

CONTROL_TYPES = ("canny", "pose", "depth")
CONTROL_BACKENDS = ("verified", "union")
FAMILIES = ("sdxl", "sd15")
LORA_TASKS = frozenset({"concept", "icon_asset", "character_action", "pose_only", "style_lock"})
REMOVE_BG_TASKS = frozenset({"concept", "icon_asset", "refine", "character_action", "pose_only", "style_lock"})
# CLI 一定去背的 task 仍保留「不去背」的 graph：golden builder 沒有接 attach_bg_removal。
GROUPS = ("sdxl", "sd15", "layer_split", "flux2")

_TASK_STEM = {
    "concept": "concept",
    "icon_asset": "icon-asset",
    "refine": "refine",
    "inpaint": "inpaint",
    "guided_inpaint": "guided-inpaint",
    "character_action": "character-action",
    "pose_only": "pose-only",
    "style_lock": "style-lock",
    "upscale": "upscale",
    "layer_split": "layer-split",
    "flux2_concept": "concept",
    "flux2_edit": "edit",
}
_SD15_UNSUPPORTED = frozenset({"character_action", "pose_only", "style_lock"})


def _reject(message):
    raise ValueError(message)


def variant_id(task, family=None, *, lora=False, remove_bg=False, control_type=None,
               control_backend="verified", structure_ref=False, appearance_ref=False):
    """回傳 template id。旗標組合不存在就丟 ValueError（sd15 不支援的功能也是）。"""
    if control_backend not in CONTROL_BACKENDS:
        _reject(f"未知 control_backend: {control_backend}")
    if control_type not in (None,) + CONTROL_TYPES:
        _reject(f"未知 control_type: {control_type}")
    if task in ("layer_split", "flux2_concept", "flux2_edit"):
        if family is not None or lora or remove_bg or control_type or structure_ref or appearance_ref \
                or control_backend != "verified":
            _reject(f"{task} 不分家族，也沒有 LoRA／去背／ControlNet 旗標")
        if task == "layer_split":
            return "image/layer-split"
        return "image/flux2/" + _TASK_STEM[task]
    if task not in _TASK_STEM:
        _reject(f"未知圖片 task: {task}")
    if family not in FAMILIES:
        _reject(f"{task} 需要 family sdxl 或 sd15，收到 {family!r}")
    if family == "sd15" and (task in _SD15_UNSUPPORTED or structure_ref or appearance_ref or control_type
                            or control_backend != "verified"):
        _reject(f"sd15 沒有 {task} 的這個組合（ControlNet／IPAdapter／character_action／pose_only／style_lock 不做 sd15 版）")
    if lora and task not in LORA_TASKS:
        _reject(f"{task} 沒有 LoRA 軸")
    if remove_bg and task not in REMOVE_BG_TASKS:
        _reject(f"{task} 沒有 remove-bg 軸")
    if structure_ref and task != "icon_asset":
        _reject("structure_ref 只用於 icon_asset")
    if appearance_ref and task not in ("icon_asset", "guided_inpaint"):
        _reject("appearance_ref 只用於 icon_asset 與 guided_inpaint")
    if control_backend != "verified" and task != "pose_only":
        _reject("control_backend 只用於 pose_only")
    if task in ("pose_only", "character_action"):
        control_type = control_type or "canny"
    elif task == "guided_inpaint":
        pass
    elif control_type is not None:
        _reject(f"{task} 沒有 control_type 軸")

    stem = _TASK_STEM[task]
    if task == "pose_only":
        stem += ("-union-" if control_backend == "union" else "-") + control_type
    elif task == "character_action":
        stem += "-" + control_type
    elif task == "guided_inpaint" and control_type:
        stem += "-" + control_type
    if structure_ref:
        stem += "-structure"
    if appearance_ref:
        stem += "-appearance"
    if lora:
        stem += "-lora"
    if remove_bg:
        stem += "-transparent"
    return f"image/{family}/{stem}"


def _spec(task, family=None, **flags):
    flags.setdefault("lora", False)
    flags.setdefault("remove_bg", False)
    flags.setdefault("control_type", None)
    flags.setdefault("control_backend", "verified")
    flags.setdefault("structure_ref", False)
    flags.setdefault("appearance_ref", False)
    return {"task": task, "family": family, "id": variant_id(task, family, **flags), **flags}


def iter_variants(*groups):
    """產生要落地的 variant。``groups`` 可用 sdxl、sd15、layer_split、flux2。"""
    chosen = groups or GROUPS
    unknown = set(chosen) - set(GROUPS)
    if unknown:
        _reject(f"未知 group: {', '.join(sorted(unknown))}")
    families = [name for name in FAMILIES if name in chosen]
    for family in families:
        for lora in (False, True):
            for remove_bg in (False, True):
                yield _spec("concept", family, lora=lora, remove_bg=remove_bg)
        structures = (False, True) if family == "sdxl" else (False,)
        appearances = (False, True) if family == "sdxl" else (False,)
        for structure_ref in structures:
            for appearance_ref in appearances:
                for lora in (False, True):
                    for remove_bg in (False, True):
                        yield _spec("icon_asset", family, lora=lora, remove_bg=remove_bg,
                                    structure_ref=structure_ref, appearance_ref=appearance_ref)
        for remove_bg in (False, True):
            yield _spec("refine", family, remove_bg=remove_bg)
        yield _spec("inpaint", family)
        if family == "sd15":
            yield _spec("guided_inpaint", family)
        else:
            for control_type in (None,) + CONTROL_TYPES:
                for appearance_ref in (False, True):
                    yield _spec("guided_inpaint", family, control_type=control_type, appearance_ref=appearance_ref)
        yield _spec("upscale", family)
        if family != "sdxl":
            continue
        for control_type in CONTROL_TYPES:
            for lora in (False, True):
                for remove_bg in (False, True):
                    yield _spec("character_action", family, control_type=control_type, lora=lora, remove_bg=remove_bg)
        for control_backend in CONTROL_BACKENDS:
            for control_type in CONTROL_TYPES:
                for lora in (False, True):
                    for remove_bg in (False, True):
                        yield _spec("pose_only", family, control_type=control_type, control_backend=control_backend,
                                    lora=lora, remove_bg=remove_bg)
        for lora in (False, True):
            for remove_bg in (False, True):
                yield _spec("style_lock", family, lora=lora, remove_bg=remove_bg)
    if "layer_split" in chosen:
        yield _spec("layer_split")
    if "flux2" in chosen:
        yield _spec("flux2_concept")
        yield _spec("flux2_edit")


def iter_variant_ids(*groups):
    ids = []
    for spec in iter_variants(*groups):
        if spec["id"] in ids:
            _reject(f"template id 重複: {spec['id']}")
        ids.append(spec["id"])
    return ids
