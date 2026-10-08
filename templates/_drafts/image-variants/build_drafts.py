"""產生 PR 4.1 的原型 template(方案 A 與方案 B),只在刻意改原型時執行。

    python templates/_drafts/image-variants/build_drafts.py --write

- 方案 A(``a/``):每種結構組合一份固定 graph。concept 依「LoRA × 去背」各一份;pose_only 依
  「control_type × control_backend × LoRA」各一份。全部只用現有 runner 的 slot,不需要改 runner。
- 方案 B(``b/``):每個 task 一份 base graph(和方案 A 的無變化版本位元組相同),外加
  ``variants.json``,宣告會插入／替換節點的 option。``option_ops.py`` 是對應的 runner 擴充原型。

graph 的來源是產線 builder(``tools_src/comfyui_pipeline/image_graphs.py``,只讀):用代表值組一次,
再把必填文字換成 ``__XXX__`` 占位、seed 換成 -1。之後這些檔案就是固定的;等價測試
(``tests/test_image_variant_drafts.py``)拿 golden fixture 比對,不會重跑這支程式。
目錄以 ``_`` 開頭,runner 的 ``discover`` 不會收錄(見 templates/README.md)。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools_src"))
sys.path.insert(0, str(REPO / "tests"))

from comfyui_pipeline import profiles as _profiles  # noqa: E402
from comfyui_pipeline.runner import template as T  # noqa: E402
import golden_image_graphs as golden  # noqa: E402

VERSION = "0.1.0"
MIN_COMFYUI = "0.34.0"
FAMILY_TIER = {"sdxl": "sdxl", "sd15": "sd15"}  # 用哪個 tier 的 DEVICE 產生該家族的 graph
FAMILY_PROFILE = {"sdxl": "sdxl_standard", "sd15": "sd15_light"}
CONTROL_TYPES = ("canny", "pose", "depth")
CONTROL_BACKENDS = ("verified", "union")
CONTROLNET_AUX = {"id": "comfyui_controlnet_aux", "source": "registry"}
AUX_CLASSES = {"OpenposePreprocessor", "DepthAnythingV2Preprocessor"}
PIN_STATUS = "原型(PR 4.1):sha256 留到正式 template(PR 4.2)補齊"
EVIDENCE = [
    {"path": "tools_src/comfyui_pipeline/image_graphs.py", "note": "graph 由產線 builder 產生(PR 4.1 原型)"},
    {"path": "tests/fixtures/image_graphs_golden/sdxl.json", "note": "等價判準:99 組圖片 golden"},
]
LOADER_ROLE = {"CheckpointLoaderSimple": ("checkpoint", "ckpt_name", "checkpoint"),
               "ControlNetLoader": ("controlnet", "control_net_name", None),
               "LoadBackgroundRemovalModel": ("bg_removal", "bg_removal_name", "bg_removal")}


# ---------- 產生 graph(只讀呼叫 builder) ----------

def load_ig():
    return golden.load_image_graphs()


def use_family(ig, family):
    device = golden.TIER_DEVICES[FAMILY_TIER[family]]
    ig.DEVICE = dict(device)
    ig.CKPT = device["checkpoint"]


def build_variant(ig, family, task, lora=False, remove_bg=False, control_type="canny", control_backend="verified"):
    """用代表值呼叫 builder,回傳 (graph, builder 回傳的輸出節點)。"""
    use_family(ig, family)
    lora_kwargs = {"lora_name": "__LORA_NAME__", "lora_strength": 0.8} if lora else {}
    if task == "concept":
        graph, out = ig.build_concept("__PROMPT__", seed=0, **lora_kwargs)
    elif task == "pose_only":
        graph, out = ig.build_pose_only("__PROMPT__", "__POSE_REF__", seed=0, control_type=control_type,
                                        control_backend=control_backend, **lora_kwargs)
    else:
        raise ValueError(task)
    if remove_bg:
        out = ig.attach_bg_removal(graph, out)
    for node in graph.values():
        if node["class_type"] == "KSampler":
            node["inputs"]["seed"] = -1
    return graph, out


# ---------- template.json ----------

def slots_for(graph, family):
    """依 graph 內容宣告 slot。數值類的預設值就是 graph 裡的值(家族的設定檔值)。"""
    by_class = {}
    for node_id, node in graph.items():
        by_class.setdefault(node["class_type"], []).append(node_id)
    ks = by_class["KSampler"][0]
    ksi = graph[ks]["inputs"]
    pos, neg = ksi["positive"][0], ksi["negative"][0]
    if graph[pos]["class_type"] == "ControlNetApplyAdvanced":  # pose_only:KSampler 接的是 ControlNet 輸出
        apply_id = pos
        pos, neg = graph[apply_id]["inputs"]["positive"][0], graph[apply_id]["inputs"]["negative"][0]
    else:
        apply_id = None
    latent = by_class["EmptyLatentImage"][0]
    ckpt = by_class["CheckpointLoaderSimple"][0]
    slots = {
        "prompt": {"type": "text", "required": True, "validate": {"min_length": 1},
                   "targets": [{"node": pos, "input": "text", "placeholder": "__PROMPT__"}], "help": "正向提示詞"},
        "negative": {"type": "text", "default": graph[neg]["inputs"]["text"],
                     "targets": [{"node": neg, "input": "text"}], "help": "負向提示詞;預設是 builder 的 DEFAULT_NEGATIVE"},
        "width": {"type": "int", "default": graph[latent]["inputs"]["width"], "validate": {"min": 8, "multiple_of": 8},
                  "targets": [{"node": latent, "input": "width"}],
                  "help": "預設是設定檔的原生尺寸;tier 的預設解析度由呼叫端明確傳入"},
        "height": {"type": "int", "default": graph[latent]["inputs"]["height"], "validate": {"min": 8, "multiple_of": 8},
                   "targets": [{"node": latent, "input": "height"}]},
        "batch_size": {"type": "int", "default": 1, "validate": {"min": 1},
                       "targets": [{"node": latent, "input": "batch_size"}]},
        "seed": {"type": "seed", "default": "auto", "targets": [{"node": ks, "input": "seed"}]},
        "steps": {"type": "int", "default": ksi["steps"], "validate": {"min": 1},
                  "targets": [{"node": ks, "input": "steps"}]},
        "cfg": {"type": "float", "default": ksi["cfg"], "validate": {"min": 0},
                "targets": [{"node": ks, "input": "cfg"}]},
        "checkpoint": {"type": "string", "default": graph[ckpt]["inputs"]["ckpt_name"],
                       "targets": [{"node": ckpt, "input": "ckpt_name"}],
                       "help": f"{family} 家族底模;--style 換成同家族的社群底模時由呼叫端傳入"},
    }
    for node_id in by_class.get("LoadImage", []):
        if graph[node_id]["inputs"]["image"] == "__POSE_REF__":
            slots["pose_ref"] = {"type": "image", "upload": True, "required": True,
                                 "targets": [{"node": node_id, "input": "image", "placeholder": "__POSE_REF__"}],
                                 "help": "構圖控制來源圖"}
    if apply_id is not None:
        slots["pose_strength"] = {"type": "float", "default": graph[apply_id]["inputs"]["strength"],
                                  "validate": {"min": 0, "max": 1},
                                  "targets": [{"node": apply_id, "input": "strength"}]}
    for node_id in by_class.get("LoraLoader", []):
        slots["lora_name"] = {"type": "string", "required": True, "validate": {"min_length": 1},
                              "targets": [{"node": node_id, "input": "lora_name", "placeholder": "__LORA_NAME__"}],
                              "help": "models/loras/ 底下的檔名;使用者自備,不 pin"}
        slots["lora_strength"] = {"type": "float", "default": graph[node_id]["inputs"]["strength_model"],
                                  "validate": {"min": 0, "max": 1},
                                  "targets": [{"node": node_id, "input": "strength_model"},
                                              {"node": node_id, "input": "strength_clip"}]}
    return slots


def models_for(graph, family):
    profile = _profiles.load_profile(FAMILY_PROFILE[family])
    dirs = {spec["file"]: spec["dir"] for spec in profile["models"].values()}
    models = []
    for node_id in sorted(graph, key=_node_order):
        node = graph[node_id]
        if node["class_type"] not in LOADER_ROLE:
            continue
        role, field, _key = LOADER_ROLE[node["class_type"]]
        filename = node["inputs"][field]
        directory = dirs[filename]
        models.append({"role": role, "node": node_id, "input": field, "filename": filename,
                       "path": f"models/{directory}/{filename}", "directory": directory, "url": None,
                       "sha256": None, "pin_status": PIN_STATUS})
    return models


def outputs_for(graph):
    saves = {node_id: node for node_id, node in graph.items() if node["class_type"] == "SaveImage"}
    transparent = [n for n, node in saves.items() if node["inputs"]["filename_prefix"] == "transparent"]
    if transparent:
        opaque = [n for n in saves if n not in transparent]
        return [{"id": "transparent", "node": transparent[0], "kind": "image", "role": "candidate"}] + \
               [{"id": "opaque", "node": n, "kind": "image", "role": "preview"} for n in opaque]
    return [{"id": "image", "node": next(iter(saves)), "kind": "image", "role": "candidate"}]


def custom_nodes_for(graph):
    return [dict(CONTROLNET_AUX)] if any(node["class_type"] in AUX_CLASSES for node in graph.values()) else []


def template_data(template_id, title, summary, graph, family, graph_bytes, notes):
    slots = slots_for(graph, family)
    uploads = [name for name, slot in slots.items() if slot.get("upload")]
    return {
        "schema_version": 1,
        "id": template_id,
        "version": VERSION,
        "title": title,
        "summary": summary,
        "status": "draft",
        "status_note": "PR 4.1 原型,只放在 templates/_drafts/,runner 不收錄",
        "min_comfyui_version": MIN_COMFYUI,
        "requires_custom_nodes": custom_nodes_for(graph),
        "graph": {"file": "graph.api.json", "format": "comfyui-api",
                  "sha256": _sha256_bytes(graph_bytes), "canonical_sha256": T.canonical_sha256(graph)},
        "provenance": {
            "derived_from": "tools_src/comfyui_pipeline/image_graphs.py(builder 以代表值產生,見 build_drafts.py)",
            "upstream": {"kind": "none", "name": None, "blob": None, "comfyui_version": None,
                         "note": "原型沒有比對官方範本;正式 template(PR 4.2/4.3)再補"},
            "tested_source_sha256": None,
            "evidence": EVIDENCE,
        },
        "slots": slots,
        "options": {},
        "fixed_notes": notes,
        "pre": [{"step": "upload", "slots": uploads}] if uploads else [],
        "post": [],
        "frame_anchoring": {"first": "none", "last": "none", "reference_role": "none",
                            "time_alignment": "per_source_frame", "continuity": None},
        "models": models_for(graph, family),
        "capability_gate": {"nodes": "from_graph", "selectors": "from_models", "files": "from_models",
                            "platforms": {"windows-cuda": {"status": "untested", "notes": "原型,沒有實機執行"}},
                            "min_memory_mb": None, "capability": "image_generation"},
        "outputs": outputs_for(graph),
    }


# ---------- 方案 A ----------

def a_variants():
    """(template id, family, task, 參數)。id 規則:image/<family>/<task>[-union-<type>|-<type>][-lora][-transparent]。"""
    found = []
    for family in ("sdxl", "sd15"):
        for lora in (False, True):
            for remove_bg in (False, True):
                name = "concept" + ("-lora" if lora else "") + ("-transparent" if remove_bg else "")
                found.append((f"image/{family}/{name}", family, "concept",
                              {"lora": lora, "remove_bg": remove_bg}))
    # pose_only 需要 SDXL ControlNet(sd15_light 設定檔沒有),所以只有 sdxl 家族。
    # 去背在 pose_only 也可以疊加,但原型只示範 control × backend × LoRA 三個軸,避免檔案數再翻倍。
    for backend in CONTROL_BACKENDS:
        for control_type in CONTROL_TYPES:
            for lora in (False, True):
                stem = "pose-only-" + ("union-" if backend == "union" else "") + control_type
                found.append((f"image/sdxl/{stem}" + ("-lora" if lora else ""), "sdxl", "pose_only",
                              {"lora": lora, "control_type": control_type, "control_backend": backend}))
    return found


def a_id(family, task, lora=False, remove_bg=False, control_type="canny", control_backend="verified"):
    """CLI 旗標 → 方案 A 的 template id(第 5 階段薄轉接要做的選擇)。"""
    if task == "concept":
        stem = "concept"
    else:
        stem = "pose-only-" + ("union-" if control_backend == "union" else "") + control_type
    return f"image/{family}/{stem}" + ("-lora" if lora else "") + ("-transparent" if remove_bg else "")


def _title(task, params):
    bits = []
    if task == "pose_only":
        bits.append(("Union " if params["control_backend"] == "union" else "") + params["control_type"])
    if params.get("lora"):
        bits.append("LoRA")
    if params.get("remove_bg"):
        bits.append("去背")
    return task + (f"({'＋'.join(bits)})" if bits else "")


# ---------- 方案 B ----------

def b_specs():
    """(base id, family, task, {option: {choice: builder 參數}})。第一個 choice 是預設(= base graph)。"""
    specs = []
    for family in ("sdxl", "sd15"):
        specs.append((f"image/{family}/concept", family, "concept", {
            "lora": {"off": {}, "on": {"lora": True}},
            "remove_bg": {"off": {}, "on": {"remove_bg": True}},
        }))
    control = {}
    for backend in CONTROL_BACKENDS:
        for control_type in CONTROL_TYPES:
            name = ("union_" if backend == "union" else "") + control_type
            control[name] = {"control_type": control_type, "control_backend": backend}
    specs.append(("image/sdxl/pose-only", "sdxl", "pose_only", {
        "control": control,
        "lora": {"off": {}, "on": {"lora": True}},
    }))
    return specs


def diff_ops(base, variant):
    """把 variant graph 相對 base graph 的差異寫成 option ops(新增／替換節點、改連線、改值)。"""
    ops = []
    removed = sorted(set(base) - set(variant), key=_node_order)
    if removed:
        raise ValueError(f"variant 刪掉了節點 {removed};option ops 不支援刪除")
    for node_id in sorted(variant, key=_node_order):
        after = variant[node_id]
        if node_id not in base:
            ops.append({"op": "add_node", "id": node_id, "node": after})
            continue
        before = base[node_id]
        if before["class_type"] != after["class_type"] or set(before["inputs"]) != set(after["inputs"]):
            ops.append({"op": "replace_node", "id": node_id, "node": after})
            continue
        for field in sorted(after["inputs"]):
            old, new = before["inputs"][field], after["inputs"][field]
            if old == new and type(old) is type(new):
                continue
            kind = "relink" if T._is_link(new) else "set_value"
            ops.append({"op": kind, "node": node_id, "input": field, ("from" if kind == "relink" else "value"): new})
    return ops


def b_choice(base_graph, variant_graph, family):
    base_slots, variant_slots = slots_for(base_graph, family), slots_for(variant_graph, family)
    base_models = {m["role"]: m for m in models_for(base_graph, family)}
    effect = {"ops": diff_ops(base_graph, variant_graph)}
    extra_slots = {name: slot for name, slot in variant_slots.items() if name not in base_slots}
    if extra_slots:
        effect["slots"] = extra_slots
    models = [m for m in models_for(variant_graph, family) if base_models.get(m["role"]) != m]
    if models:
        effect["models"] = models
    custom = [c for c in custom_nodes_for(variant_graph) if c not in custom_nodes_for(base_graph)]
    if custom:
        effect["requires_custom_nodes"] = custom
    if outputs_for(variant_graph) != outputs_for(base_graph):
        effect["outputs"] = outputs_for(variant_graph)
    return effect


# ---------- 寫檔 ----------

def _node_order(node_id):
    digits = "".join(ch for ch in node_id if ch.isdigit())
    return (int(digits) if digits else 0, node_id)


def _sha256_bytes(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def graph_bytes(graph):
    ordered = {key: graph[key] for key in sorted(graph, key=_node_order)}
    return (json.dumps(ordered, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def render():
    """回傳 {相對路徑: bytes}(相對於這個資料夾)。"""
    ig = load_ig()
    saved = (ig.DEVICE, ig.CKPT)
    files = {}
    try:
        for template_id, family, task, params in a_variants():
            graph, _out = build_variant(ig, family, task, **params)
            raw = graph_bytes(graph)
            title = _title(task, params)
            data = template_data(template_id, f"[原型 A] {family} {title}",
                                 f"方案 A:{title} 的固定 graph,結構變化各自一份", graph, family, raw,
                                 "sampler/scheduler 固定為設定檔值;filename_prefix 保留 builder 的值,讓 graph sha256 和切換前相同")
            files[f"a/{template_id}/graph.api.json"] = raw
            files[f"a/{template_id}/template.json"] = json_bytes(data)
        for base_id, family, task, options in b_specs():
            base_graph, _out = build_variant(ig, family, task)
            raw = graph_bytes(base_graph)
            data = template_data(base_id, f"[原型 B] {family} {task}(base)",
                                 f"方案 B:{task} 的 base graph;結構變化由 variants.json 的 option 插入",
                                 base_graph, family, raw,
                                 "base graph 和方案 A 的無變化版本位元組相同;option 見 variants.json")
            spec = {"draft_schema": "option-ops-v0", "base": base_id, "options": {}}
            for option, choices in options.items():
                entries = {}
                for choice, params in choices.items():
                    variant_graph, _ = build_variant(ig, family, task, **params)
                    effect = b_choice(base_graph, variant_graph, family)
                    entries[choice] = {} if not effect["ops"] else effect
                spec["options"][option] = {"default": next(iter(choices)), "choices": entries}
            files[f"b/{base_id}/graph.api.json"] = raw
            files[f"b/{base_id}/template.json"] = json_bytes(data)
            files[f"b/{base_id}/variants.json"] = json_bytes(spec)
    finally:
        ig.DEVICE, ig.CKPT = saved
    return files


def main(argv):
    files = render()
    if "--write" not in argv:
        stale = [rel for rel, raw in files.items() if not (HERE / rel).is_file() or (HERE / rel).read_bytes() != raw]
        print(f"{len(files)} 個檔案;{'全部是最新' if not stale else '需要更新: ' + ', '.join(stale)}")
        print("用 --write 寫出(只在刻意改原型時執行)", file=sys.stderr)
        return 1 if stale else 0
    for rel, raw in files.items():
        path = HERE / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print(f"wrote {len(files)} files under {HERE}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
