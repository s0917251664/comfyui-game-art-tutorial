"""template 的載入、驗證、slot 解析與 patch。只用標準庫,不連 ComfyUI。

一份 template 是 ``templates/<id>/`` 資料夾,內含 ``graph.api.json``(固定的 ComfyUI API graph,
位元組不改)與 ``template.json``(可替換欄位、模型 pin、平台狀態等)。

載入時一律強制檢查(不符合就拒絕,不是只警告):
- graph 的位元組 sha256 與 canonical sha256 都和 template.json 記錄的一致;
- 每個 slot、option、model 指向的節點與 input 都存在於 graph;
- graph 裡每個 ``__XXX__`` 占位都被某個 slot 認領,每個 ``seed``／``noise_seed == -1`` 都被 seed slot 認領;
- 兩個 slot 不能寫同一個目標(除非其中一個寫了 ``default_from``)。

patch 之後再檢查一次:沒有剩下占位、沒有 -1 seed,而且和原 graph 的差異只落在 slot 與已啟用
option 宣告的目標上。這是把 R2「不臨場改 graph」變成程式強制的規則。
"""
import copy
import json
import random
import re
from pathlib import Path

from ..image_results import graph_sha256 as canonical_sha256  # 和 result manifest 的 graph_sha256 同一個算法
from . import steps as _steps

SCHEMA_VERSION = 1
TEMPLATE_FILE = "template.json"
GRAPH_FORMAT = "comfyui-api"
SCHEMA_DIR = "_schema"

REQUIRED_FIELDS = ("schema_version", "id", "version", "title", "summary", "status", "min_comfyui_version",
                   "requires_custom_nodes", "graph", "provenance", "slots", "pre", "post", "frame_anchoring", "models",
                   "capability_gate", "outputs")
OPTIONAL_FIELDS = ("status_note", "options", "constraints", "fixed_notes")
STATUSES = ("draft", "technical_pass", "retired")
PLATFORM_STATUSES = ("technical_pass", "untested", "unsupported")
SLOT_TYPES = ("text", "string", "int", "float", "bool", "seed", "points", "image", "video", "mask_image",
              "path", "output_prefix")
UPLOAD_TYPES = frozenset({"image", "video", "mask_image"})
# 本機輸入:只給 pre／post 步驟讀,不上傳、不寫進 graph(targets 是 [])。
# path 是檔案或資料夾(例如遮罩 PNG 資料夾或 layers.zip);image／video／mask_image 沒有 upload 時也是本機檔。
FILE_TYPES = UPLOAD_TYPES | {"path"}
FROM_PRE_TYPES = frozenset({"text", "string", "int", "float", "bool"})
PRE_MARK = "<pre:{}>"
VALIDATE_KEYS = {
    "text": {"min_length", "max_length"},
    "string": {"pattern", "enum", "min_length", "max_length"},
    "int": {"min", "max", "multiple_of", "enum"},
    "float": {"min", "max", "enum"},
    "points": {"min_items", "max_items"},
}
SLOT_KEYS = {"type", "targets", "default", "required", "validate", "tested_values", "help", "upload", "default_from",
             "generated", "from_pre"}
TARGET_KEYS = {"node", "input", "placeholder"}
OPTION_OPS = ("set_link", "set_value")
CONSTRAINT_RULES = ("points_within",)
ANCHOR_VALUES = ("image", "conditioning", "same_as_first", "none")
REFERENCE_ROLES = ("identity", "selection", "none")
TIME_ALIGNMENTS = ("source_from_frame_0", "per_source_frame", None)
OUTPUT_KINDS = ("video", "image", "image_sequence")
OUTPUT_ROLES = ("candidate", "mask", "preview")
MODEL_KEYS = {"role", "node", "input", "filename", "path", "directory", "url", "size_bytes", "sha256", "source",
              "notes", "pin_status", "auto_download", "platforms"}
# platforms 裡每個平台的 pin。windows-cuda 必須和頂層 filename 相同；預檢仍只看頂層 pin。
PLATFORM_PIN_KEYS = frozenset({"filename", "sha256", "size_bytes"})
SOURCE_KEYS = {"repo", "revision", "file"}
# 對齊官方範本 properties.models[].url(Hugging Face 下載網址);我們固定 revision,不用 main。
MODEL_URL = "https://huggingface.co/{repo}/resolve/{revision}/{file}"
CUSTOM_NODE_SOURCES = ("registry", "repo")
UPSTREAM_KINDS = ("workflow_templates", "core_blueprint", "none")
UPSTREAM_KEYS = {"kind", "name", "blob", "comfyui_version", "note"}

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)+$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REGISTRY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PLATFORM_RE = re.compile(r"^[a-z0-9]+-[a-z0-9]+$")
PLACEHOLDER_RE = re.compile(r"^__[A-Z0-9_]+__$")
SEED_INPUTS = ("seed", "noise_seed")
SEED_MAX = 2 ** 53 - 1
AUTO_SEED_MAX = 2 ** 32 - 1
UPLOAD_MARK = "<upload:{}>"
TRUE_WORDS = {"true", "1", "yes", "on"}
FALSE_WORDS = {"false", "0", "no", "off"}


class TemplateError(ValueError):
    """template 本身或使用者給的值不合規。``problems`` 是逐條原因。"""

    def __init__(self, problems, where=None):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        head = f"{where}: " if where else ""
        if len(self.problems) == 1:
            message = head + self.problems[0]
        else:
            message = head + "\n" + "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(message)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and _is_int(value[1])


def read_json(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def file_sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Template:
    """載入並驗證過的 template。``graph`` 是原始 graph,請勿就地修改(patch 會先深拷貝)。"""

    def __init__(self, template_id, directory, data, graph, graph_sha256, graph_canonical_sha256,
                 template_json_sha256):
        self.id = template_id
        self.directory = Path(directory)
        self.data = data
        self.graph = graph
        self.graph_sha256 = graph_sha256
        self.graph_canonical_sha256 = graph_canonical_sha256
        self.template_json_sha256 = template_json_sha256

    @property
    def version(self):
        return self.data["version"]

    @property
    def slots(self):
        return self.data["slots"]

    @property
    def options(self):
        return self.data.get("options") or {}

    def upload_slots(self):
        return [name for name, slot in self.slots.items() if slot.get("upload")]

    def deferred_slots(self):
        """值由 pre 步驟決定的 slot:``generated``(pre 產生的上傳檔)與 ``from_pre``(pre 量到的值)。"""
        return [name for name, slot in self.slots.items() if slot.get("generated") or slot.get("from_pre")]

    def declared_targets(self, enabled_options=()):
        """slot 與已啟用 option 會寫入的 (node, input) 集合。"""
        found = {(t["node"], t["input"]) for slot in self.slots.values() for t in slot["targets"]}
        for name in enabled_options:
            for op in self.options[name]["when_true"]:
                found.add((op["node"], op["input"]))
        return found


# ---------- 探索與載入 ----------

def templates_root(repo_root):
    return Path(repo_root) / "templates"


def discover(root):
    """回傳所有 template id(依字母排序)。``_schema`` 之類底線開頭的資料夾略過。"""
    root = Path(root)
    found = []
    for path in sorted(root.rglob(TEMPLATE_FILE)):
        rel = path.parent.relative_to(root)
        if any(part.startswith("_") for part in rel.parts):
            continue
        found.append(rel.as_posix())
    return found


def load_template(root, template_id, repo_root=None):
    """載入 ``<root>/<template_id>/template.json`` 並完整驗證;有任何問題就丟 TemplateError。"""
    if not isinstance(template_id, str) or not ID_RE.match(template_id):
        raise TemplateError(f"template id 格式不對: {template_id!r}(例如 video/wan-animate/mix)")
    root = Path(root)
    directory = root.joinpath(*template_id.split("/"))
    path = directory / TEMPLATE_FILE
    if not path.is_file():
        known = discover(root) if root.is_dir() else []
        raise TemplateError(f"找不到 template {template_id!r}" + (f"(可用: {', '.join(known)})" if known else ""))
    try:
        data = read_json(path)
    except ValueError as exc:
        raise TemplateError(f"template.json 不是合法 JSON: {exc}", template_id) from exc
    if not isinstance(data, dict):
        raise TemplateError("template.json 必須是 JSON object", template_id)
    problems = _check_header(data, template_id)
    if problems:
        raise TemplateError(problems, template_id)
    graph_path = directory / data["graph"]["file"]
    if not graph_path.is_file():
        raise TemplateError(f"找不到 graph 檔 {graph_path.name}", template_id)
    byte_sha = file_sha256(graph_path)
    try:
        graph = read_json(graph_path)
    except ValueError as exc:
        raise TemplateError(f"{graph_path.name} 不是合法 JSON: {exc}", template_id) from exc
    canonical = canonical_sha256(graph)
    hash_problems = []
    if byte_sha != data["graph"]["sha256"]:
        hint = ("內容相同、只有位元組不同,通常是 CRLF/LF 換行被 git 轉換;請確認 .gitattributes 的 "
                "templates/** -text 並重新 checkout" if canonical == data["graph"]["canonical_sha256"]
                else "內容也不同,graph 被改過")
        hash_problems.append(
            f"graph 位元組 sha256 不符: 檔案 {byte_sha},template.json 記錄 {data['graph']['sha256']}({hint})")
    if canonical != data["graph"]["canonical_sha256"]:
        hash_problems.append(
            f"graph canonical sha256 不符: 檔案 {canonical},template.json 記錄 {data['graph']['canonical_sha256']}"
            "(graph 內容被改過)")
    if hash_problems:
        raise TemplateError(hash_problems, template_id)
    template = Template(template_id, directory, data, graph, byte_sha, canonical, file_sha256(path))
    problems = validate_template(template, repo_root if repo_root is not None else root.parent)
    if problems:
        raise TemplateError(problems, template_id)
    return template


def _check_header(data, template_id):
    problems = []
    for key in REQUIRED_FIELDS:
        if key not in data:
            problems.append(f"缺少必填欄位 {key}")
    for key in data:
        if key not in REQUIRED_FIELDS and key not in OPTIONAL_FIELDS:
            problems.append(f"不認得的欄位 {key}")
    if problems:
        return problems
    if data["schema_version"] != SCHEMA_VERSION:
        problems.append(f"schema_version 必須是 {SCHEMA_VERSION}")
    if data["id"] != template_id:
        problems.append(f"id {data['id']!r} 和資料夾路徑 {template_id!r} 不同")
    if not isinstance(data["version"], str) or not SEMVER_RE.match(data["version"]):
        problems.append("version 必須是 semver(例如 1.0.0)")
    if data["status"] not in STATUSES:
        problems.append(f"status 必須是 {', '.join(STATUSES)} 之一")
    if not isinstance(data["min_comfyui_version"], str) or not SEMVER_RE.match(data["min_comfyui_version"]):
        problems.append("min_comfyui_version 必須是 X.Y.Z(例如 0.34.0)")
    problems.extend(_check_custom_nodes(data["requires_custom_nodes"]))
    graph = data["graph"]
    if not isinstance(graph, dict) or set(graph) != {"file", "format", "sha256", "canonical_sha256"}:
        problems.append("graph 必須剛好有 file、format、sha256、canonical_sha256")
    else:
        if not isinstance(graph["file"], str) or "/" in graph["file"] or "\\" in graph["file"] or graph["file"].startswith("."):
            problems.append("graph.file 必須是同資料夾裡的檔名")
        if graph["format"] != GRAPH_FORMAT:
            problems.append(f"graph.format 必須是 {GRAPH_FORMAT}")
        for key in ("sha256", "canonical_sha256"):
            if not isinstance(graph[key], str) or not SHA256_RE.match(graph[key]):
                problems.append(f"graph.{key} 必須是 64 位小寫十六進位")
    return problems


def _check_custom_nodes(nodes):
    """requires_custom_nodes:[{id, source}]。source=registry 時 id 是 Comfy registry id;repo 是這個 repo 的套件。"""
    if not isinstance(nodes, list):
        return ["requires_custom_nodes 必須是陣列(不需要 custom node 時寫 [])"]
    problems, seen = [], set()
    for index, node in enumerate(nodes):
        where = f"requires_custom_nodes[{index}]"
        if not isinstance(node, dict) or set(node) != {"id", "source"}:
            problems.append(f"{where}: 必須剛好有 id、source")
            continue
        if not isinstance(node["id"], str) or not REGISTRY_ID_RE.match(node["id"]):
            problems.append(f"{where}: id 格式不對: {node['id']!r}")
        elif node["id"] in seen:
            problems.append(f"{where}: id {node['id']} 重複")
        else:
            seen.add(node["id"])
        if node["source"] not in CUSTOM_NODE_SOURCES:
            problems.append(f"{where}: source 必須是 {'／'.join(CUSTOM_NODE_SOURCES)} 之一")
    return problems


def parse_version(text):
    """``0.34.0``、``v0.34.0``、``0.34.0-dev`` → (0, 34, 0);認不出來回傳 None。"""
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", text.strip()) if isinstance(text, str) else None
    return tuple(int(part) for part in match.groups()) if match else None


# ---------- 驗證 ----------

def validate_template(template, repo_root=None):
    """回傳問題清單(空清單 = 通過)。"""
    data, graph = template.data, template.graph
    problems = []
    if not isinstance(graph, dict) or not graph:
        return ["graph 必須是非空的 JSON object(ComfyUI API 格式)"]
    for node_id, node in graph.items():
        if not isinstance(node, dict) or not isinstance(node.get("class_type"), str) or \
                not isinstance(node.get("inputs"), dict):
            problems.append(f"graph 節點 {node_id} 缺少 class_type 或 inputs")
    if problems:
        return problems

    def has_input(node, name):
        return node in graph and name in graph[node]["inputs"]

    slots = data["slots"]
    options = data.get("options") or {}
    if not isinstance(slots, dict) or not slots:
        return problems + ["slots 必須是非空 object"]
    if not isinstance(options, dict):
        problems.append("options 必須是 object")
        options = {}

    # slots
    claimed = {}
    for name, slot in slots.items():
        where = f"slot {name}"
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            problems.append(f"{where}: 名稱只能用小寫英數與底線")
        if not isinstance(slot, dict):
            problems.append(f"{where}: 必須是 object")
            continue
        unknown = set(slot) - SLOT_KEYS
        if unknown:
            problems.append(f"{where}: 不認得的欄位 {', '.join(sorted(unknown))}")
        kind = slot.get("type")
        if kind not in SLOT_TYPES:
            problems.append(f"{where}: type 必須是 {', '.join(SLOT_TYPES)} 之一")
            continue
        upload = slot.get("upload", False)
        if not isinstance(upload, bool) or upload and kind not in UPLOAD_TYPES:
            problems.append(f"{where}: upload 只能用在 image／video／mask_image(true/false)")
        local_file = kind in FILE_TYPES and not upload
        generated, from_pre = slot.get("generated", False), slot.get("from_pre")
        if not isinstance(generated, bool) or generated and not upload:
            problems.append(f"{where}: generated 只能用在 upload 的 slot(值是 pre 步驟產生的檔案)")
        if from_pre is not None:
            if kind not in FROM_PRE_TYPES:
                problems.append(f"{where}: from_pre 只能用在 {'／'.join(sorted(FROM_PRE_TYPES))}")
            elif not _steps.is_step_result_ref(from_pre):
                problems.append(f"{where}: from_pre 要寫成 {{pre.<步驟>.<欄位>}},可用: "
                                + "、".join(f"{s}.{f}" for s, fields in _steps.STEP_RESULTS.items() for f in fields))
        rules = slot.get("validate") or {}
        bad_rules = set(rules) - VALIDATE_KEYS.get(kind, set())
        if bad_rules:
            problems.append(f"{where}: {kind} 不支援驗證規則 {', '.join(sorted(bad_rules))}")
        if "pattern" in rules:
            try:
                re.compile(rules["pattern"])
            except re.error as exc:
                problems.append(f"{where}: pattern 不是合法正規表示式: {exc}")
        targets = slot.get("targets")
        if not isinstance(targets, list):
            problems.append(f"{where}: targets 必須是陣列")
            continue
        if local_file and targets:
            problems.append(f"{where}: 本機輸入(path 或沒有 upload 的 {kind})不寫進 graph,targets 要是 []")
            continue
        if not targets and not local_file and (upload or kind in ("seed", "points", "output_prefix") or from_pre):
            problems.append(f"{where}: targets 必須是非空陣列")
            continue
        for target in targets:
            if not isinstance(target, dict) or set(target) - TARGET_KEYS or "node" not in target or "input" not in target:
                problems.append(f"{where}: target 只能有 node、input、placeholder")
                continue
            node, field = target["node"], target["input"]
            if not has_input(node, field):
                problems.append(f"{where}: graph 沒有節點 {node} 的 input {field!r}")
                continue
            current = graph[node]["inputs"][field]
            if _is_link(current):
                problems.append(f"{where}: {node}.{field} 是節點連線,不能當 slot 目標")
                continue
            if "placeholder" in target and current != target["placeholder"]:
                problems.append(f"{where}: {node}.{field} 目前是 {current!r},不是宣告的占位 {target['placeholder']!r}")
            if isinstance(current, str) and PLACEHOLDER_RE.match(current) and target.get("placeholder") != current:
                problems.append(f"{where}: {node}.{field} 是占位 {current!r},target 要寫 placeholder")
            if not (from_pre and isinstance(current, str) and PLACEHOLDER_RE.match(current)):
                problems.extend(_type_matches_graph(where, kind, node, field, current))
            claimed.setdefault((node, field), []).append(name)
        has_default = "default" in slot or "default_from" in slot
        if kind == "output_prefix" or generated or from_pre:
            if has_default or slot.get("required"):
                problems.append(f"{where}: 值由 runner 或 pre 步驟決定,不能有 default 或 required")
        elif not slot.get("required") and not has_default:
            problems.append(f"{where}: 不是 required 就必須有 default 或 default_from")
        elif slot.get("required") and has_default:
            problems.append(f"{where}: required 和 default 不能同時寫")
        if "default_from" in slot:
            source = slots.get(slot["default_from"])
            if not isinstance(source, dict) or source.get("type") != kind or slot["default_from"] == name:
                problems.append(f"{where}: default_from 必須指向另一個同類型的 slot")
        if "default" in slot and kind != "output_prefix":
            if not (kind == "seed" and slot["default"] == "auto"):
                try:
                    validate_value(name, slot, slot["default"])
                except TemplateError as exc:
                    problems.append(f"{where}: default 不合規: {exc}")
        tested = slot.get("tested_values")
        if tested is not None and not isinstance(tested, list):
            problems.append(f"{where}: tested_values 必須是陣列")

    for (node, field), names in sorted(claimed.items()):
        if len(names) > 1 and not any("default_from" in slots[n] for n in names):
            problems.append(f"{node}.{field} 被多個 slot 寫入: {', '.join(names)}")

    # graph 裡的占位與 -1 seed 都必須有人認領
    seed_targets = {(t["node"], t["input"]) for s in slots.values() if isinstance(s, dict) and s.get("type") == "seed"
                    for t in s.get("targets") or [] if isinstance(t, dict)}
    for node_id, node in graph.items():
        for field, value in node["inputs"].items():
            if isinstance(value, str) and PLACEHOLDER_RE.match(value) and (node_id, field) not in claimed:
                problems.append(f"graph {node_id}.{field} 的占位 {value} 沒有 slot 認領")
            if field in SEED_INPUTS and value == -1 and (node_id, field) not in seed_targets:
                problems.append(f"graph {node_id}.{field} = -1 沒有 seed slot 認領")

    # options
    for name, option in options.items():
        where = f"option {name}"
        if not isinstance(option, dict) or not isinstance(option.get("default"), bool) or \
                not isinstance(option.get("when_true"), list) or not option["when_true"]:
            problems.append(f"{where}: 需要布林 default 與非空 when_true")
            continue
        if set(option) - {"default", "when_true", "help"}:
            problems.append(f"{where}: 只能有 default、when_true、help")
        for op in option["when_true"]:
            kind = op.get("op") if isinstance(op, dict) else None
            if kind not in OPTION_OPS:
                problems.append(f"{where}: op 必須是 {', '.join(OPTION_OPS)} 之一")
                continue
            node, field = op.get("node"), op.get("input")
            if node not in graph:
                problems.append(f"{where}: graph 沒有節點 {node}")
                continue
            if (node, field) in claimed:
                problems.append(f"{where}: {node}.{field} 已經是 slot 目標")
            if kind == "set_link":
                if set(op) != {"op", "node", "input", "from"}:
                    problems.append(f"{where}: set_link 需要剛好 node、input、from")
                    continue
                if field in graph[node]["inputs"]:
                    problems.append(f"{where}: set_link 只能新增連線,{node}.{field} 已經存在")
                src = op["from"]
                if not _is_link(src) or src[0] not in graph or src[1] < 0:
                    problems.append(f"{where}: from 必須是 [既有節點 id, 輸出序號]")
            else:
                if set(op) != {"op", "node", "input", "value"}:
                    problems.append(f"{where}: set_value 需要剛好 node、input、value")
                    continue
                if field not in graph[node]["inputs"]:
                    problems.append(f"{where}: set_value 只能改既有 input,{node}.{field} 不存在")

    # constraints
    for index, rule in enumerate(data.get("constraints") or []):
        where = f"constraints[{index}]"
        if not isinstance(rule, dict) or rule.get("rule") not in CONSTRAINT_RULES:
            problems.append(f"{where}: rule 必須是 {', '.join(CONSTRAINT_RULES)} 之一")
            continue
        for key in ("slot", "width", "height"):
            if rule.get(key) not in slots:
                problems.append(f"{where}: {key} 指向不存在的 slot {rule.get(key)!r}")
        if slots.get(rule.get("slot"), {}).get("type") != "points":
            problems.append(f"{where}: points_within 的 slot 必須是 points")

    # pre / post / outputs
    outputs = data["outputs"]
    output_ids = set()
    if not isinstance(outputs, list) or not outputs:
        problems.append("outputs 必須是非空陣列")
        outputs = []
    for index, output in enumerate(outputs):
        where = f"outputs[{index}]"
        if not isinstance(output, dict):
            problems.append(f"{where}: 必須是 object")
            continue
        if output.get("id") in output_ids or not isinstance(output.get("id"), str):
            problems.append(f"{where}: id 缺少或重複")
        output_ids.add(output.get("id"))
        if output.get("node") not in graph:
            problems.append(f"{where}: graph 沒有節點 {output.get('node')}")
        if output.get("kind") not in OUTPUT_KINDS:
            problems.append(f"{where}: kind 必須是 {', '.join(OUTPUT_KINDS)} 之一")
        if output.get("role") not in OUTPUT_ROLES:
            problems.append(f"{where}: role 必須是 {', '.join(OUTPUT_ROLES)} 之一")
        if "expect_count" in output and (not _is_int(output["expect_count"]) or output["expect_count"] < 1):
            problems.append(f"{where}: expect_count 必須是正整數")
    problems.extend(_steps.validate_steps(data["pre"], "pre", slots, options, output_ids))
    problems.extend(_steps.validate_steps(data["post"], "post", slots, options, output_ids))
    uploaded = _steps.uploaded_slots(data["pre"])
    for name in template.upload_slots():
        if uploaded.count(name) != 1:
            problems.append(f"slot {name}: 必須剛好出現在一個 upload 步驟")
    for name in uploaded:
        if name in slots and not slots[name].get("upload"):
            problems.append(f"upload 步驟列了沒有 upload 的 slot {name}")
    problems.extend(_steps.validate_step_slots(data["pre"], data["post"], slots))

    problems.extend(_validate_anchoring(data["frame_anchoring"]))
    problems.extend(_validate_models(data["models"], graph, data["status"]))
    problems.extend(_validate_gate(data["capability_gate"]))
    problems.extend(_validate_provenance(data["provenance"], repo_root))
    return problems


def _type_matches_graph(where, kind, node, field, current):
    placeholder = isinstance(current, str) and PLACEHOLDER_RE.match(current)
    ok = {
        "text": isinstance(current, str), "string": isinstance(current, str),
        "int": _is_int(current), "float": _is_number(current), "bool": isinstance(current, bool),
        "seed": _is_int(current), "points": bool(placeholder), "output_prefix": bool(placeholder),
        "image": bool(placeholder), "video": bool(placeholder), "mask_image": bool(placeholder),
    }[kind]
    if not ok:
        return [f"{where}: {node}.{field} 目前的值 {current!r} 和 slot 類型 {kind} 不相容"]
    return []


def _validate_anchoring(anchor):
    if not isinstance(anchor, dict):
        return ["frame_anchoring 必須是 object"]
    problems = []
    if set(anchor) != {"first", "last", "reference_role", "time_alignment", "continuity"}:
        problems.append("frame_anchoring 必須剛好有 first、last、reference_role、time_alignment、continuity")
        return problems
    for key in ("first", "last"):
        if anchor[key] not in ANCHOR_VALUES:
            problems.append(f"frame_anchoring.{key} 必須是 {', '.join(ANCHOR_VALUES)} 之一")
    if anchor["reference_role"] not in REFERENCE_ROLES:
        problems.append(f"frame_anchoring.reference_role 必須是 {', '.join(REFERENCE_ROLES)} 之一")
    if anchor["time_alignment"] not in TIME_ALIGNMENTS:
        names = ", ".join("null" if item is None else item for item in TIME_ALIGNMENTS)
        problems.append(f"frame_anchoring.time_alignment 必須是 {names} 之一")
    cont = anchor["continuity"]
    if cont is not None:
        if not isinstance(cont, dict) or set(cont) != {"segments", "overlap_frames", "seam_frames", "manual_check"} \
                or not _is_int(cont["segments"]) or not _is_int(cont["overlap_frames"]) \
                or not isinstance(cont["seam_frames"], list) or not all(_is_int(v) for v in cont["seam_frames"]):
            problems.append("frame_anchoring.continuity 必須是 null 或 {segments, overlap_frames, seam_frames, manual_check}")
    return problems


def _validate_models(models, graph, status):
    if not isinstance(models, list):
        return ["models 必須是陣列"]
    problems = []
    missing_pin = False
    for index, model in enumerate(models):
        where = f"models[{index}]"
        if not isinstance(model, dict):
            problems.append(f"{where}: 必須是 object")
            continue
        unknown = set(model) - MODEL_KEYS
        if unknown:
            problems.append(f"{where}: 不認得的欄位 {', '.join(sorted(unknown))}")
        for key in ("role", "node", "input", "filename"):
            if not isinstance(model.get(key), str) or not model.get(key):
                problems.append(f"{where}: {key} 必填")
        node, field = model.get("node"), model.get("input")
        if node not in graph or field not in graph[node]["inputs"]:
            problems.append(f"{where}: graph 沒有節點 {node} 的 input {field!r}")
        elif graph[node]["inputs"][field] != model.get("filename"):
            problems.append(f"{where}: graph {node}.{field} 是 {graph[node]['inputs'][field]!r},"
                            f"不是 {model.get('filename')!r}")
        sha = model.get("sha256")
        if sha is None:
            missing_pin = True
            if not isinstance(model.get("pin_status"), str) or not model["pin_status"]:
                problems.append(f"{where}: sha256 為 null 時必須寫 pin_status 說明")
        else:
            if not isinstance(sha, str) or not SHA256_RE.match(sha):
                problems.append(f"{where}: sha256 必須是 64 位小寫十六進位或 null")
            if not isinstance(model.get("path"), str) or not _is_int(model.get("size_bytes")):
                problems.append(f"{where}: 有 sha256 時 path 與 size_bytes 也必填")
        if "auto_download" in model and not isinstance(model["auto_download"], bool):
            problems.append(f"{where}: auto_download 必須是 true/false")
        path = model.get("path")
        if isinstance(path, str) and (path.startswith(("/", "\\")) or ":" in path or ".." in path.split("/")):
            problems.append(f"{where}: path 必須是相對 comfyui_path 的路徑(正斜線,不能有 ..)")
        problems.extend(_check_model_location(where, model))
        problems.extend(_check_model_platforms(where, model))
    if missing_pin and status == "technical_pass":
        problems.append("有模型 pin 尚未補齊(sha256 為 null),status 不能是 technical_pass")
    return problems


def _check_model_location(where, model):
    """directory／url 對齊官方 properties.models,必須和 path、source 一致。兩個欄位都必填(不適用時寫 null)。"""
    problems = [f"{where}: 缺少 {key}(不適用時寫 null)" for key in ("directory", "url") if key not in model]
    directory, path, filename = model.get("directory"), model.get("path"), model.get("filename")
    if directory is not None and (not isinstance(directory, str) or not directory
                                  or directory.startswith("/") or ".." in directory.split("/")):
        problems.append(f"{where}: directory 必須是 models/ 底下的資料夾名稱(例如 diffusion_models)或 null")
    elif isinstance(path, str) and isinstance(filename, str):
        if path.startswith("models/"):
            if path != f"models/{directory}/{filename}":
                problems.append(f"{where}: directory {directory!r} 和 path {path!r} 不一致"
                                "(path 在 models/ 底下時必須是 models/<directory>/<filename>)")
        elif directory is not None:
            problems.append(f"{where}: path {path!r} 不在 models/ 底下(例如 custom node 自己的 ckpts),"
                            "directory 要寫 null")
    source, url = model.get("source"), model.get("url")
    if source is not None:
        if not isinstance(source, dict) or set(source) != SOURCE_KEYS or \
                not all(isinstance(source[k], str) and source[k] for k in SOURCE_KEYS):
            return problems + [f"{where}: source 必須是 null 或剛好有 repo、revision、file"]
        if not GIT_SHA_RE.match(source["revision"]):
            problems.append(f"{where}: source.revision 必須是 40 位 commit sha(固定版本,不能用 main)")
        if url != MODEL_URL.format(**source):
            problems.append(f"{where}: url 和 source 不一致,應該是 {MODEL_URL.format(**source)}")
    elif url is not None:
        problems.append(f"{where}: 沒有 source 時 url 必須是 null")
    return problems


def _check_model_platforms(where, model):
    """選用的 platforms：有寫就必須含 windows-cuda，而且 filename（以及 sha256、size_bytes）等於頂層 pin。"""
    if "platforms" not in model:
        return []
    platforms = model["platforms"]
    if not isinstance(platforms, dict) or not platforms:
        return [f"{where}: platforms 必須是非空 object"]
    problems = []
    if "windows-cuda" not in platforms:
        problems.append(f"{where}: 有 platforms 時必須有 windows-cuda，且 filename 等於頂層 filename")
    for key, entry in platforms.items():
        if not isinstance(key, str) or not PLATFORM_RE.match(key):
            problems.append(f"{where}: platforms 的平台名稱 {key!r} 格式不對(例如 windows-cuda)")
            continue
        if not isinstance(entry, dict) or set(entry) != PLATFORM_PIN_KEYS:
            problems.append(f"{where}: platforms.{key} 必須剛好有 filename、sha256、size_bytes")
            continue
        filename = entry["filename"]
        if not isinstance(filename, str) or not filename:
            problems.append(f"{where}: platforms.{key}.filename 必填")
        elif key == "windows-cuda" and filename != model.get("filename"):
            problems.append(f"{where}: platforms.windows-cuda.filename 必須等於頂層 filename {model.get('filename')!r}")
        sha = entry["sha256"]
        if not isinstance(sha, str) or not SHA256_RE.match(sha):
            problems.append(f"{where}: platforms.{key}.sha256 必須是 64 位小寫十六進位")
        elif key == "windows-cuda" and sha != model.get("sha256"):
            problems.append(f"{where}: platforms.windows-cuda.sha256 必須等於頂層 sha256")
        size = entry["size_bytes"]
        if not _is_int(size) or size < 0:
            problems.append(f"{where}: platforms.{key}.size_bytes 必須是非負整數")
        elif key == "windows-cuda" and size != model.get("size_bytes"):
            problems.append(f"{where}: platforms.windows-cuda.size_bytes 必須等於頂層 size_bytes")
    return problems


def _validate_gate(gate):
    if not isinstance(gate, dict):
        return ["capability_gate 必須是 object"]
    problems = []
    expected = {"nodes": "from_graph", "selectors": "from_models", "files": "from_models"}
    for key, value in expected.items():
        if gate.get(key) != value:
            problems.append(f"capability_gate.{key} 目前只支援 {value!r}")
    if set(gate) - {"nodes", "selectors", "files", "extra_nodes", "platforms", "min_memory_mb", "capability"}:
        problems.append("capability_gate 有不認得的欄位")
    if not isinstance(gate.get("extra_nodes", []), list):
        problems.append("capability_gate.extra_nodes 必須是陣列")
    platforms = gate.get("platforms")
    if not isinstance(platforms, dict) or not platforms:
        problems.append("capability_gate.platforms 必須是非空 object")
    else:
        for key, value in platforms.items():
            if not PLATFORM_RE.match(key):
                problems.append(f"capability_gate.platforms: 平台名稱 {key!r} 格式不對(例如 windows-cuda)")
            if not isinstance(value, dict) or value.get("status") not in PLATFORM_STATUSES:
                problems.append(f"capability_gate.platforms.{key}.status 必須是 {', '.join(PLATFORM_STATUSES)} 之一")
            elif set(value) - {"status", "evidence", "notes"}:
                problems.append(f"capability_gate.platforms.{key} 只能有 status、evidence、notes")
    mem = gate.get("min_memory_mb")
    if mem is not None and not _is_int(mem):
        problems.append("capability_gate.min_memory_mb 必須是整數或 null")
    if not isinstance(gate.get("capability"), str):
        problems.append("capability_gate.capability 必填")
    return problems


def _validate_provenance(prov, repo_root):
    if not isinstance(prov, dict) or set(prov) != {"derived_from", "tested_source_sha256", "evidence", "upstream"}:
        return ["provenance 必須剛好有 derived_from、tested_source_sha256、evidence、upstream"]
    problems = _validate_upstream(prov["upstream"])
    if not isinstance(prov["derived_from"], str) or not prov["derived_from"]:
        problems.append("provenance.derived_from 必填")
    sha = prov["tested_source_sha256"]
    if sha is not None and (not isinstance(sha, str) or not SHA256_RE.match(sha)):
        problems.append("provenance.tested_source_sha256 必須是 sha256 或 null")
    evidence = prov["evidence"]
    if not isinstance(evidence, list) or not evidence:
        problems.append("provenance.evidence 必須是非空陣列")
        return problems
    for index, item in enumerate(evidence):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or set(item) - {"path", "note"}:
            problems.append(f"provenance.evidence[{index}] 必須是 {{path, note}}")
            continue
        # 證據文件只在 repo 裡檢查;部署到 <ComfyUI>/tools/templates 的副本沒有 docs/(PR 8.4)
        if repo_root is not None and (Path(repo_root) / "docs").is_dir():
            rel = item["path"].split("#", 1)[0]
            if not (Path(repo_root) / rel).exists():
                problems.append(f"provenance.evidence[{index}]: repo 裡沒有 {rel}")
    return problems


def _validate_upstream(upstream):
    """provenance.upstream:對應的官方範本或 core blueprint。沒有對應時 kind=none,並在 note 說明。"""
    if not isinstance(upstream, dict) or not {"kind", "name", "blob", "comfyui_version"} <= set(upstream) \
            or set(upstream) - UPSTREAM_KEYS:
        return ["provenance.upstream 必須有 kind、name、blob、comfyui_version(可另加 note)"]
    kind, note = upstream["kind"], upstream.get("note")
    if kind not in UPSTREAM_KINDS:
        return [f"provenance.upstream.kind 必須是 {'／'.join(UPSTREAM_KINDS)} 之一"]
    problems = []
    if "note" in upstream and (not isinstance(note, str) or not note):
        problems.append("provenance.upstream.note 必須是非空字串")
    if kind == "none":
        if any(upstream[key] is not None for key in ("name", "blob", "comfyui_version")):
            problems.append("provenance.upstream.kind 是 none 時,name、blob、comfyui_version 都要是 null")
        if not note:
            problems.append("provenance.upstream.kind 是 none 時要在 note 說明為什麼沒有對應的官方來源")
        return problems
    name = upstream["name"]
    if not isinstance(name, str) or not name:
        problems.append("provenance.upstream.name 必填")
    elif kind == "workflow_templates" and (name.endswith(".json") or not re.match(r"^[A-Za-z0-9_.-]+$", name)):
        problems.append("provenance.upstream.name 是官方範本名稱,不含 .json(例如 video_wan_vace_inpainting)")
    elif kind == "core_blueprint" and not name.endswith(".json"):
        problems.append("provenance.upstream.name 是 ComfyUI blueprints/ 裡的檔名,要含 .json")
    if not isinstance(upstream["blob"], str) or not GIT_SHA_RE.match(upstream["blob"]):
        problems.append("provenance.upstream.blob 必須是 40 位 git blob sha(git hash-object 的結果)")
    if not isinstance(upstream["comfyui_version"], str) or not SEMVER_RE.match(upstream["comfyui_version"]):
        problems.append("provenance.upstream.comfyui_version 必須是 X.Y.Z")
    return problems


# ---------- slot 值 ----------

def coerce(name, slot, raw):
    """把 ``--set`` 的字串(或 values.json 的原生值)轉成 slot 型別;不合法丟 TemplateError。"""
    kind = slot["type"]
    if kind == "output_prefix":
        raise TemplateError(f"slot {name}: output prefix 由 runner 產生,不能指定")
    if kind in ("int", "seed"):
        if kind == "seed" and raw == "auto":
            return "auto"
        if isinstance(raw, str):
            try:
                return int(raw.strip())
            except ValueError:
                raise TemplateError(f"slot {name}: 需要整數,收到 {raw!r}") from None
        if _is_int(raw):
            return raw
        raise TemplateError(f"slot {name}: 需要整數,收到 {raw!r}")
    if kind == "float":
        if isinstance(raw, str):
            try:
                return float(raw.strip())
            except ValueError:
                raise TemplateError(f"slot {name}: 需要數字,收到 {raw!r}") from None
        if _is_number(raw):
            return float(raw)
        raise TemplateError(f"slot {name}: 需要數字,收到 {raw!r}")
    if kind == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.strip().lower() in TRUE_WORDS | FALSE_WORDS:
            return raw.strip().lower() in TRUE_WORDS
        raise TemplateError(f"slot {name}: 需要 true/false,收到 {raw!r}")
    if kind == "points":
        value = raw
        if isinstance(raw, str):
            try:
                value = json.loads(raw)
            except ValueError:
                raise TemplateError(f"slot {name}: 點位要寫成 JSON,例如 '[{{\"x\":192,\"y\":192}}]'") from None
        return value
    if not isinstance(raw, str):
        raise TemplateError(f"slot {name}: 需要字串,收到 {raw!r}")
    return raw


def validate_value(name, slot, value):
    """依 slot 的類型與 validate 規則檢查已轉型的值。"""
    kind, rules = slot["type"], slot.get("validate") or {}
    where = f"slot {name}"
    if kind in ("text", "string"):
        if not isinstance(value, str):
            raise TemplateError(f"{where}: 需要字串")
        if "min_length" in rules and len(value) < rules["min_length"]:
            raise TemplateError(f"{where}: 至少要 {rules['min_length']} 個字")
        if "max_length" in rules and len(value) > rules["max_length"]:
            raise TemplateError(f"{where}: 最多 {rules['max_length']} 個字")
        if "pattern" in rules and not re.fullmatch(rules["pattern"], value):
            raise TemplateError(f"{where}: {value!r} 不符合格式 {rules['pattern']}")
        if "enum" in rules and value not in rules["enum"]:
            raise TemplateError(f"{where}: 只能是 {rules['enum']}")
    elif kind in ("int", "float"):
        if kind == "int" and not _is_int(value) or kind == "float" and not _is_number(value):
            raise TemplateError(f"{where}: 需要{'整數' if kind == 'int' else '數字'}")
        if "enum" in rules and value not in rules["enum"]:
            raise TemplateError(f"{where}: 只能是 {rules['enum']},收到 {value}")
        if "min" in rules and value < rules["min"]:
            raise TemplateError(f"{where}: 不能小於 {rules['min']},收到 {value}")
        if "max" in rules and value > rules["max"]:
            raise TemplateError(f"{where}: 不能大於 {rules['max']},收到 {value}")
        if "multiple_of" in rules and value % rules["multiple_of"]:
            raise TemplateError(f"{where}: 必須是 {rules['multiple_of']} 的倍數,收到 {value}")
    elif kind == "bool":
        if not isinstance(value, bool):
            raise TemplateError(f"{where}: 需要 true/false")
    elif kind == "seed":
        if not _is_int(value) or value < 0 or value > SEED_MAX:
            raise TemplateError(f"{where}: seed 必須是 0..{SEED_MAX} 的整數(不可為 -1),收到 {value!r}")
    elif kind == "points":
        if not isinstance(value, list):
            raise TemplateError(f"{where}: 點位必須是陣列")
        for point in value:
            if not isinstance(point, dict) or set(point) != {"x", "y"} or \
                    not _is_number(point["x"]) or not _is_number(point["y"]):
                raise TemplateError(f"{where}: 每個點都要是 {{\"x\": 數字, \"y\": 數字}},收到 {point!r}")
        if "min_items" in rules and len(value) < rules["min_items"]:
            raise TemplateError(f"{where}: 至少要 {rules['min_items']} 個點")
        if "max_items" in rules and len(value) > rules["max_items"]:
            raise TemplateError(f"{where}: 最多 {rules['max_items']} 個點")
    elif kind in FILE_TYPES:
        if not isinstance(value, str) or not value:
            raise TemplateError(f"{where}: 需要檔案路徑")


def output_prefix(template_id, run_id):
    return f"gameart/{template_id.replace('/', '-')}/{run_id}"


def resolve(template, values=None, options=None, *, run_id, dry_run=False, rng=None, allow_missing=False):
    """解析所有 slot 與 option 的值。

    ``values``:{slot: 原始值}(``--set`` 的字串或 values.json 的原生值)。
    ``options``:{option: bool}。回傳 dict:slot_values、seed_sources、options、inputs(上傳 slot 的本機路徑)、
    warnings、missing(``allow_missing`` 時沒有值的必填 slot)。dry-run 時缺少的上傳 slot 只警告,graph 裡會顯示
    ``<upload:slot>``。``allow_missing``(preflight 用)把缺少的必填 slot 也降為警告,只檢查環境。
    """
    values = dict(values or {})
    options = dict(options or {})
    rng = rng or random.SystemRandom()
    slots, problems, warnings = template.slots, [], []
    for name in values:
        if name not in slots:
            problems.append(f"沒有 slot {name!r}(可用: {', '.join(n for n, s in slots.items() if s['type'] != 'output_prefix')})")
    for name in options:
        if name not in template.options:
            problems.append(f"沒有 option {name!r}" + (f"(可用: {', '.join(template.options)})" if template.options else "(這份 template 沒有 option)"))
    if problems:
        raise TemplateError(problems, template.id)

    resolved, seed_sources, inputs = {}, {}, {}
    pending_from, missing = [], []
    for name, slot in slots.items():
        kind = slot["type"]
        try:
            if kind == "output_prefix":
                if name in values:
                    coerce(name, slot, values[name])
                resolved[name] = output_prefix(template.id, run_id)
                continue
            if slot.get("generated") or slot.get("from_pre"):
                if name in values:
                    raise TemplateError(f"slot {name}: 值由 pre 步驟產生,不能指定")
                continue
            if name in values:
                value = coerce(name, slot, values[name])
                source = "explicit"
            elif "default_from" in slot:
                pending_from.append(name)
                continue
            elif "default" in slot:
                value, source = copy.deepcopy(slot["default"]), "default"
            elif kind in FILE_TYPES and dry_run:
                warnings.append(f"slot {name} 沒有提供檔案;graph 以 {UPLOAD_MARK.format(name)} 代替")
                continue
            elif allow_missing:
                missing.append(name)
                continue
            else:
                problems.append(f"slot {name} 必填" + (f"({slot['help']})" if slot.get("help") else ""))
                continue
            if kind == "seed" and value == "auto":
                value, source = rng.randint(0, AUTO_SEED_MAX), "auto"
            validate_value(name, slot, value)
        except TemplateError as exc:
            problems.extend(exc.problems)
            continue
        if kind in FILE_TYPES:
            inputs[name] = value
            continue
        resolved[name] = value
        if kind == "seed":
            seed_sources[name] = source
    for name in pending_from:
        source_name = slots[name]["default_from"]
        if source_name in resolved:
            resolved[name] = resolved[source_name]
            if slots[name]["type"] == "seed":
                seed_sources[name] = f"default_from:{source_name}"
    if problems:
        raise TemplateError(problems, template.id)

    for rule in template.data.get("constraints") or []:
        points = resolved.get(rule["slot"]) or []
        width, height = resolved.get(rule["width"]), resolved.get(rule["height"])
        for point in points:
            if not (0 <= point["x"] < width and 0 <= point["y"] < height):
                problems.append(f"slot {rule['slot']}: 點 {point} 超出輸出範圍 0 <= x < {width}、0 <= y < {height}"
                                "(座標是輸出寬高的中心裁切座標,不是原圖像素)")
    if problems:
        raise TemplateError(problems, template.id)

    for name, slot in slots.items():
        tested = slot.get("tested_values")
        if tested and name in resolved and resolved[name] not in tested:
            warnings.append(f"slot {name}={resolved[name]!r} 沒有實測紀錄(實測過: {tested})")
    chosen = {}
    for name, option in template.options.items():
        value = options.get(name, option["default"])
        if not isinstance(value, bool):
            raise TemplateError(f"option {name} 需要 true/false", template.id)
        chosen[name] = value
    continuity = template.data["frame_anchoring"].get("continuity")
    if continuity and continuity.get("manual_check") == "seam":
        seam = "/".join(str(frame) for frame in continuity["seam_frames"])
        warnings.append(f"延伸段接縫(第 {seam} 幀前後)需要人工檢查")
    if missing:
        warnings.append(f"沒有提供必填 slot: {', '.join(missing)};只檢查環境,不產生 graph")
    return {"slot_values": resolved, "seed_sources": seed_sources, "options": chosen, "inputs": inputs,
            "warnings": warnings, "missing": missing}


def fill_from_pre(template, resolution, pre_results):
    """實際執行時,pre 步驟跑完後填入 ``from_pre`` slot 的值(就地更新 resolution)並驗證。回傳填了哪些。"""
    problems, filled = [], []
    for name, slot in template.slots.items():
        if not slot.get("from_pre"):
            continue
        try:
            value = _steps.resolve_param(slot["from_pre"], resolution["slot_values"], resolution["options"],
                                         pre_results)
            validate_value(name, slot, value)
        except KeyError as exc:
            problems.append(f"slot {name}: {exc.args[0] if exc.args else exc}")
            continue
        except TemplateError as exc:
            problems.extend(exc.problems)
            continue
        resolution["slot_values"][name] = value
        filled.append(name)
    if problems:
        raise TemplateError(problems, template.id)
    return filled


# ---------- patch ----------

def _encode(slot, value):
    if slot["type"] == "points":
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def patch(template, resolution, upload_paths=None, *, require_uploads=True):
    """依解析結果產生要送出的 graph(深拷貝),並執行 :func:`check_patched`。

    ``upload_paths``:{slot: ComfyUI 回傳的 ``subfolder/name``}。``require_uploads=False``(dry-run)時,
    缺少的上傳路徑以 ``<upload:slot>`` 標示。回傳 (graph, changes);changes 是改到的 ``node.input`` 清單。
    """
    upload_paths = dict(upload_paths or {})
    graph = copy.deepcopy(template.graph)
    values = resolution["slot_values"]
    missing = []
    for name, slot in template.slots.items():
        if slot.get("upload"):
            if name in upload_paths:
                value = upload_paths[name]
            elif require_uploads:
                missing.append(name)
                continue
            else:
                value = UPLOAD_MARK.format(name)
        elif slot["type"] in FILE_TYPES:
            continue  # 本機輸入,不寫進 graph
        elif name in values:
            value = _encode(slot, values[name])
        elif slot.get("from_pre") and not require_uploads:
            value = PRE_MARK.format(slot["from_pre"][len("{pre."):-1])  # dry-run／preflight:pre 步驟還沒跑
        else:
            missing.append(name)
            continue
        for target in slot["targets"]:
            graph[target["node"]]["inputs"][target["input"]] = copy.deepcopy(value)
    if missing:
        raise TemplateError(f"還沒有值的 slot: {', '.join(missing)}", template.id)
    enabled = [name for name, on in resolution["options"].items() if on]
    for name in enabled:
        for op in template.options[name]["when_true"]:
            inputs = graph[op["node"]]["inputs"]
            inputs[op["input"]] = list(op["from"]) if op["op"] == "set_link" else copy.deepcopy(op["value"])
    changes = check_patched(template, graph, enabled, allow_upload_marks=not require_uploads)
    return graph, changes


def graph_changes(original, patched):
    """回傳 (改到的 (node, input) 集合, 結構問題清單)。"""
    changed, problems = set(), []
    for node_id in sorted(set(original) | set(patched)):
        if node_id not in patched:
            problems.append(f"節點 {node_id} 被刪除")
            continue
        if node_id not in original:
            problems.append(f"新增了節點 {node_id}")
            continue
        before, after = original[node_id], patched[node_id]
        if set(before) != set(after) or before.get("class_type") != after.get("class_type"):
            problems.append(f"節點 {node_id} 的 class_type 或欄位被改動")
            continue
        old_inputs, new_inputs = before["inputs"], after["inputs"]
        for field in set(old_inputs) | set(new_inputs):
            if field not in old_inputs or field not in new_inputs or old_inputs[field] != new_inputs[field] \
                    or type(old_inputs[field]) is not type(new_inputs[field]):
                changed.add((node_id, field))
    return changed, problems


def check_patched(template, graph, enabled_options=(), *, allow_upload_marks=False):
    """最後檢查:沒有剩下占位與 -1 seed;差異只在宣告過的目標。回傳排序後的改動清單。"""
    problems = []
    for node_id, node in graph.items():
        for field, value in node.get("inputs", {}).items():
            if isinstance(value, str) and PLACEHOLDER_RE.match(value):
                problems.append(f"{node_id}.{field} 還是占位 {value}")
            if isinstance(value, str) and value.startswith("<upload:") and not allow_upload_marks:
                problems.append(f"{node_id}.{field} 還沒有上傳路徑")
            if isinstance(value, str) and value.startswith("<pre:") and not allow_upload_marks:
                problems.append(f"{node_id}.{field} 還沒有 pre 步驟的值")
            if field in SEED_INPUTS and value == -1:
                problems.append(f"{node_id}.{field} 還是 -1")
    changed, structural = graph_changes(template.graph, graph)
    problems.extend(structural)
    allowed = template.declared_targets(enabled_options)
    for node_id, field in sorted(changed - allowed):
        problems.append(f"{node_id}.{field} 不是宣告過的 slot／option 目標,不能改")
    if problems:
        raise TemplateError(problems, template.id)
    return sorted(f"{node}.{field}" for node, field in changed)


# ---------- 給人看的摘要 ----------

def platform_summary(template):
    platforms = template.data["capability_gate"]["platforms"]
    return {key: value["status"] for key, value in platforms.items()}
