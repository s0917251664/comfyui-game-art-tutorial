"""recipe 的載入、展開與確認點續跑。只用標準庫,不連 ComfyUI、不 queue prompt。

一份 recipe 是 ``templates/recipes/<id>/recipe.json``(不是 ``template.json``,所以 template discover 掃不到)。
``templates/recipes/_drafts/<id>/`` 要明確要求才看得到。

每一步是已登記的 template、本機指令、說明,或確認點。跑到確認點就把 ``recipe.state.json`` 寫進該次資料夾並停下;
沒有確認紀錄就不能做確認點之後的步驟。``content_review`` 一律是 pending,這裡不寫 accept。

實際執行 template 或本機指令都交給 executor。預設的 :class:`OfflineExecutor` 不送 ComfyUI、也不跑子程序。
測試注入假 clock 與假 executor:``run_template(template_id, slots, step_dir)`` 回傳輸出路徑。
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import template as T

SCHEMA_VERSION = 1
RECIPE_FILE = "recipe.json"
STATE_FILE = "recipe.state.json"
DRAFT_DIR = "_drafts"
CONTENT_REVIEW = "pending"

REQUIRED_FIELDS = ("schema_version", "id", "version", "title", "summary", "status", "inputs", "steps")
OPTIONAL_FIELDS = ("status_note",)
STATUSES = ("draft", "technical_pass", "retired")
STEP_KINDS = ("template", "confirm", "local", "note")
INPUT_TYPES = ("text", "string", "int", "float", "bool", "seed", "path")
INPUT_KEYS = ("type", "required", "default", "help", "enum")
SUPPORTS = ("planned", "unsupported", "ready")
TEMPLATE_STEP_KEYS = ("id", "kind", "template", "slots", "executable", "frame_anchoring", "support", "text")
CONFIRM_STEP_KEYS = ("id", "kind", "message", "look_at")
LOCAL_STEP_KEYS = ("id", "kind", "command", "args", "outputs", "text")
NOTE_STEP_KEYS = ("id", "kind", "text", "template", "support")
FRAME_KEYS = ("first", "last", "note")

RECIPE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STEP_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
INPUT_NAME_RE = STEP_ID_RE
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
ARG_KEY_RE = re.compile(r"^--[a-z0-9][a-z0-9-]*$")
REF_RE = re.compile(
    r"^\{(inputs\.[a-z][a-z0-9_]*|steps\.[a-z][a-z0-9_]*\.(?:outputs\.[a-z][a-z0-9_]*|dir))\}$")
TOKEN_RE = re.compile(r"\{[^{}]*\}")
TRUE_WORDS = {"true", "1", "yes", "on"}
FALSE_WORDS = {"false", "0", "no", "off"}


class RecipeError(ValueError):
    """recipe 本身或這次給的值不合規。"""

    def __init__(self, problems, where=None):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        head = f"{where}: " if where else ""
        if len(self.problems) == 1:
            message = head + self.problems[0]
        else:
            message = head + "\n" + "\n".join(f"  - {item}" for item in self.problems)
        super().__init__(message)


class RecipeNotRunnable(Exception):
    """這一步現在不能做(沒有接上 ComfyUI 或本機執行器)。不是參數錯誤,呼叫端要寫 state 後停下。"""


class Recipe:
    def __init__(self, recipe_id, directory, data, draft, path):
        self.id = recipe_id
        self.directory = Path(directory)
        self.data = data
        self.draft = draft
        self.path = Path(path)

    @property
    def version(self):
        return self.data["version"]

    @property
    def steps(self):
        return self.data["steps"]


def recipes_root(repo_root):
    return Path(repo_root) / "templates" / "recipes"


def _read_json(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def _id_from_rel(rel):
    if any(part.startswith("_") and part != DRAFT_DIR for part in rel.parts):
        raise RecipeError(f"recipe 路徑不對: {rel.as_posix()}")
    parts = [part for part in rel.parts if part != DRAFT_DIR]
    if len(parts) != 1 or not RECIPE_ID_RE.fullmatch(parts[0]):
        raise RecipeError(f"recipe 路徑不對: {rel.as_posix()}(id 要等於資料夾名,例如 object-mark-inpaint)")
    return parts[0]


def discover(root, *, include_drafts=False):
    """回傳 recipe id(字母排序)。``_drafts`` 要 ``include_drafts`` 才列入;其他底線資料夾一律略過。"""
    root = Path(root)
    found, seen = [], set()
    if not root.is_dir():
        return found
    for path in sorted(root.rglob(RECIPE_FILE)):
        rel = path.parent.relative_to(root)
        if any(part.startswith("_") and part != DRAFT_DIR for part in rel.parts):
            continue
        draft = DRAFT_DIR in rel.parts
        if draft and not include_drafts:
            continue
        recipe_id = _id_from_rel(rel)
        if recipe_id in seen:
            raise RecipeError(f"recipe id {recipe_id} 重複")
        seen.add(recipe_id)
        found.append(recipe_id)
    return sorted(found)


def _locate(root, recipe_id, *, include_drafts):
    if not isinstance(recipe_id, str) or not RECIPE_ID_RE.fullmatch(recipe_id):
        raise RecipeError(f"recipe id 格式不對: {recipe_id!r}(例如 object-mark-inpaint)")
    root = Path(root)
    direct = root / recipe_id / RECIPE_FILE
    draft = root / DRAFT_DIR / recipe_id / RECIPE_FILE
    if direct.is_file() and draft.is_file():
        raise RecipeError(f"recipe id {recipe_id} 同時出現在 recipes/ 與 {DRAFT_DIR}/")
    if direct.is_file():
        return direct, False
    if draft.is_file():
        if not include_drafts:
            raise RecipeError(f"recipe {recipe_id} 在 {DRAFT_DIR},一般指令不會跑。要加 --draft")
        return draft, True
    known = discover(root, include_drafts=include_drafts)
    extra = f"(可用: {', '.join(known)})" if known else ""
    raise RecipeError(f"找不到 recipe {recipe_id!r}{extra}")


def template_contract(templates_root, template_id):
    """讀 template.json 的 slot／output 名稱。檔案不存在回傳 None;不跑 template.py 的 graph 驗證。"""
    if templates_root is None or not isinstance(template_id, str):
        return None
    path = Path(templates_root).joinpath(*template_id.split("/")) / T.TEMPLATE_FILE
    if not path.is_file():
        return None
    try:
        data = _read_json(path)
    except (OSError, ValueError) as exc:
        return {"error": f"template.json 讀不到: {exc}", "slots": {}, "outputs": []}
    if not isinstance(data, dict) or not isinstance(data.get("slots"), dict):
        return {"error": "template.json 沒有 slots", "slots": {}, "outputs": []}
    outputs = []
    for item in data.get("outputs") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            outputs.append(item["id"])
    return {"slots": data["slots"], "outputs": outputs, "error": None}


def load_recipe(root, recipe_id, *, include_drafts=False, templates_root=None):
    path, draft = _locate(root, recipe_id, include_drafts=include_drafts)
    try:
        data = _read_json(path)
    except (OSError, ValueError) as exc:
        raise RecipeError(f"recipe.json 不是合法 JSON: {exc}", recipe_id) from exc
    if not isinstance(data, dict):
        raise RecipeError("recipe.json 必須是 JSON object", recipe_id)
    problems = _validate(data, recipe_id, templates_root)
    if problems:
        raise RecipeError(problems, recipe_id)
    return Recipe(recipe_id, path.parent, data, draft, path)


def _validate(data, recipe_id, templates_root):
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
    if data["id"] != recipe_id:
        problems.append(f"id {data['id']!r} 和資料夾 {recipe_id!r} 不同")
    if not isinstance(data["version"], str) or not SEMVER_RE.fullmatch(data["version"]):
        problems.append("version 必須是 semver(例如 0.1.0)")
    for key in ("title", "summary"):
        if not isinstance(data[key], str) or not data[key].strip():
            problems.append(f"{key} 必須是非空字串")
    if data["status"] not in STATUSES:
        problems.append(f"status 必須是 {', '.join(STATUSES)} 之一")
    if "status_note" in data and not isinstance(data["status_note"], str):
        problems.append("status_note 必須是字串")
    inputs = data["inputs"]
    if not isinstance(inputs, dict):
        return problems + ["inputs 必須是 object(沒有輸入就寫 {})"]
    for name, spec in inputs.items():
        _check_input(name, spec, problems)
    steps = data["steps"]
    if not isinstance(steps, list) or not steps:
        return problems + ["steps 必須是非空陣列"]
    earlier, seen = {}, set()
    for index, step in enumerate(steps):
        where = f"steps[{index}]"
        if not isinstance(step, dict):
            problems.append(f"{where}: 必須是 object")
            continue
        step_id = step.get("id")
        if not isinstance(step_id, str) or not STEP_ID_RE.fullmatch(step_id):
            problems.append(f"{where}: id 只能用小寫英數與底線")
            step_id = None
        elif step_id in seen:
            problems.append(f"{where}: id {step_id} 重複")
        else:
            seen.add(step_id)
        kind = step.get("kind")
        if kind not in STEP_KINDS:
            problems.append(f"{where}: kind 必須是 {', '.join(STEP_KINDS)} 之一")
            continue
        allowed = {
            "template": TEMPLATE_STEP_KEYS, "confirm": CONFIRM_STEP_KEYS,
            "local": LOCAL_STEP_KEYS, "note": NOTE_STEP_KEYS,
        }[kind]
        unknown = set(step) - set(allowed)
        if unknown:
            problems.append(f"{where}: {kind} 不認得的欄位 {', '.join(sorted(unknown))}")
        contract = _check_step_fields(step, where, templates_root, problems)
        if step_id:
            _check_step_refs(step, where, set(inputs), earlier, problems)
            earlier[step_id] = _output_names(step, contract)
    return problems


def _check_input(name, spec, problems):
    where = f"inputs.{name}"
    if not INPUT_NAME_RE.fullmatch(name):
        problems.append(f"{where}: 名稱只能用小寫英數與底線")
    if not isinstance(spec, dict):
        problems.append(f"{where}: 必須是 object")
        return
    unknown = set(spec) - set(INPUT_KEYS)
    if unknown:
        problems.append(f"{where}: 不認得的欄位 {', '.join(sorted(unknown))}")
    kind = spec.get("type")
    if kind not in INPUT_TYPES:
        problems.append(f"{where}: type 必須是 {', '.join(INPUT_TYPES)} 之一")
        return
    if "required" in spec and not isinstance(spec["required"], bool):
        problems.append(f"{where}: required 必須是 true 或 false")
    if "help" in spec and not isinstance(spec["help"], str):
        problems.append(f"{where}: help 必須是字串")
    enum = spec.get("enum")
    if enum is not None:
        if kind not in ("string", "text") or not isinstance(enum, list) or not enum or not all(isinstance(item, str) for item in enum):
            problems.append(f"{where}: enum 只能用在 string／text,而且要是非空字串陣列")
        elif "default" in spec and spec["default"] not in enum:
            problems.append(f"{where}: default 不在 enum 裡")
    if "default" in spec:
        _check_literal(where, kind, spec["default"], problems)


def _check_literal(where, kind, value, problems):
    if kind in ("text", "string", "path", "seed") and kind != "seed":
        if not isinstance(value, str):
            problems.append(f"{where}: {kind} 的值必須是字串")
    elif kind == "seed":
        if value != "auto" and not _is_int(value):
            problems.append(f"{where}: seed 必須是 auto 或整數")
    elif kind == "int" and not _is_int(value):
        problems.append(f"{where}: int 的值必須是整數")
    elif kind == "float" and not _is_number(value):
        problems.append(f"{where}: float 的值必須是數字")
    elif kind == "bool" and not isinstance(value, bool):
        problems.append(f"{where}: bool 的值必須是 true 或 false")


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_step_fields(step, where, templates_root, problems):
    kind = step["kind"]
    if kind == "template":
        template_id = step.get("template")
        if not isinstance(template_id, str) or not T.ID_RE.fullmatch(template_id):
            problems.append(f"{where}: template id 格式不對: {template_id!r}")
            template_id = None
        if not isinstance(step.get("slots"), dict):
            problems.append(f"{where}: slots 必須是 object")
        else:
            for name, value in step["slots"].items():
                if not isinstance(name, str) or not STEP_ID_RE.fullmatch(name):
                    problems.append(f"{where}: slot 名稱不對: {name!r}")
                elif not _is_slot_value(value):
                    problems.append(f"{where}: slot {name} 的值必須是字串、數字或布林")
        if "executable" in step and not isinstance(step["executable"], bool):
            problems.append(f"{where}: executable 必須是 true 或 false")
        _check_support(step, where, problems)
        _check_frame(step, where, problems)
        _check_text(step, where, problems, required=False)
        contract = template_contract(templates_root, template_id) if template_id else None
        if contract and contract.get("error") and step.get("executable", True):
            problems.append(f"{where}: {contract['error']}")
        elif contract and not contract.get("error"):
            _check_template_slots(step, where, contract, problems)
        return contract
    if kind == "confirm":
        message = step.get("message")
        if not isinstance(message, str) or not message.strip():
            problems.append(f"{where}: message 必須是非空字串")
        if "look_at" in step and not isinstance(step["look_at"], str):
            problems.append(f"{where}: look_at 必須是字串")
        return None
    if kind == "local":
        if not isinstance(step.get("command"), str) or not step["command"].strip():
            problems.append(f"{where}: command 必須是非空字串")
        args = step.get("args", {})
        if "args" in step and not isinstance(args, dict):
            problems.append(f"{where}: args 必須是 object")
        elif isinstance(args, dict):
            for key, value in args.items():
                if not isinstance(key, str) or not ARG_KEY_RE.fullmatch(key):
                    problems.append(f"{where}: 參數名稱要像 --input,收到 {key!r}")
                elif not _is_slot_value(value):
                    problems.append(f"{where}: 參數 {key} 的值必須是字串、數字或布林")
        outputs = step.get("outputs", [])
        if "outputs" in step and (not isinstance(outputs, list) or not all(isinstance(item, str) and STEP_ID_RE.fullmatch(item) for item in outputs)):
            problems.append(f"{where}: outputs 必須是輸出名稱陣列")
        elif isinstance(outputs, list) and len(outputs) != len(set(outputs)):
            problems.append(f"{where}: outputs 名稱重複")
        _check_text(step, where, problems, required=False)
        return None
    if not isinstance(step.get("text"), str) or not step["text"].strip():
        problems.append(f"{where}: text 必須是非空字串")
    if "template" in step and (not isinstance(step["template"], str) or not T.ID_RE.fullmatch(step["template"])):
        problems.append(f"{where}: template id 格式不對: {step.get('template')!r}")
    _check_support(step, where, problems)
    return template_contract(templates_root, step["template"]) if isinstance(step.get("template"), str) else None


def _check_support(step, where, problems):
    if "support" in step and step["support"] not in SUPPORTS:
        problems.append(f"{where}: support 必須是 {', '.join(SUPPORTS)} 之一")


def _check_frame(step, where, problems):
    frame = step.get("frame_anchoring")
    if frame is None:
        return
    if not isinstance(frame, dict) or set(frame) - set(FRAME_KEYS):
        problems.append(f"{where}: frame_anchoring 只能有 first、last、note")
        return
    for key, value in frame.items():
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{where}: frame_anchoring.{key} 必須是非空字串")


def _check_text(step, where, problems, *, required):
    if "text" not in step:
        if required:
            problems.append(f"{where}: text 必須是非空字串")
        return
    if not isinstance(step["text"], str) or not step["text"].strip():
        problems.append(f"{where}: text 必須是非空字串")


def _is_slot_value(value):
    return isinstance(value, str) or _is_number(value) or isinstance(value, bool)


def _check_template_slots(step, where, contract, problems):
    slots = contract["slots"]
    mapping = step.get("slots") if isinstance(step.get("slots"), dict) else {}
    for name in mapping:
        if name not in slots:
            problems.append(f"{where}: template 沒有 slot {name}")
            continue
        slot = slots[name]
        if not isinstance(slot, dict):
            continue
        if slot.get("type") == "output_prefix" or slot.get("generated") or slot.get("from_pre"):
            problems.append(f"{where}: slot {name} 由 template runner 產生,recipe 不能指定")
    if step.get("executable", True) is False:
        return
    for name, slot in slots.items():
        if not isinstance(slot, dict):
            continue
        if slot.get("type") == "output_prefix" or slot.get("generated") or slot.get("from_pre"):
            continue
        if slot.get("required") and "default" not in slot and name not in mapping:
            problems.append(f"{where}: 缺少必填 slot {name}")


def _output_names(step, contract):
    """回傳這個步驟可以被後面引用的輸出名稱。None 表示 template 還沒登記,名稱先不擋。"""
    kind = step["kind"]
    if kind == "local":
        return set(step.get("outputs") or [])
    if kind == "template":
        if contract is None or contract.get("error"):
            return None
        return set(contract.get("outputs") or [])
    return set()


def _check_step_refs(step, where, inputs, earlier, problems):
    for label, text in _ref_strings(step):
        if not isinstance(text, str):
            continue
        for token in TOKEN_RE.findall(text):
            match = REF_RE.fullmatch(token)
            if not match:
                problems.append(f"{where}: {label} 不認得的參考 {token}")
                continue
            body = match.group(1)
            if body.startswith("inputs."):
                name = body.split(".", 1)[1]
                if name not in inputs:
                    problems.append(f"{where}: {label} 引用了沒有的輸入 {name}")
                continue
            parts = body.split(".")
            step_id, output = parts[1], parts[3] if len(parts) == 4 else None
            if step_id not in earlier:
                problems.append(f"{where}: {label} 引用了還沒出現的步驟 {step_id}")
                continue
            allowed = earlier[step_id]
            if output is not None and allowed is not None and output not in allowed:
                problems.append(f"{where}: {label} 步驟 {step_id} 沒有輸出 {output}")
        if text.count("{") != len(TOKEN_RE.findall(text)) or text.count("}") != text.count("{"):
            problems.append(f"{where}: {label} 的大括號沒有成對")


def _ref_strings(step):
    found = []
    slots = step.get("slots")
    if isinstance(slots, dict):
        found.extend((f"slot {name}", value) for name, value in slots.items())
    args = step.get("args")
    if isinstance(args, dict):
        found.extend((f"args {name}", value) for name, value in args.items())
    for key in ("message", "look_at", "command"):
        if key in step:
            found.append((key, step[key]))
    return found


def _is_required(spec):
    if "required" in spec:
        return bool(spec["required"])
    return "default" not in spec


def coerce_inputs(recipe, values, *, require):
    """把 ``--set`` 收成 recipe 輸入。``require`` 為假時,缺必填只略過(dry-run)。"""
    specs = recipe.data["inputs"]
    values = dict(values or {})
    unknown = sorted(set(values) - set(specs))
    problems = [f"沒有輸入 {', '.join(unknown)}"] if unknown else []
    coerced = {}
    for name, spec in specs.items():
        if name in values:
            coerced[name] = _coerce(name, spec, values[name], problems)
        elif "default" in spec:
            coerced[name] = spec["default"]
        elif require and _is_required(spec):
            problems.append(f"缺少輸入 {name}")
    if problems:
        raise RecipeError(problems, recipe.id)
    return coerced


def _coerce(name, spec, value, problems):
    kind = spec["type"]
    where = f"輸入 {name}"
    if kind in ("text", "string", "path"):
        if not isinstance(value, str):
            problems.append(f"{where} 必須是字串")
            return value
        if spec.get("enum") and value not in spec["enum"]:
            problems.append(f"{where} 必須是 {'／'.join(spec['enum'])} 之一,收到 {value!r}")
        return value
    if kind == "seed":
        if value == "auto":
            return "auto"
        if _is_int(value):
            return value
        if isinstance(value, str):
            try:
                return int(value, 10)
            except ValueError:
                pass
        problems.append(f"{where} 必須是 auto 或整數,收到 {value!r}")
        return value
    if kind == "int":
        if _is_int(value):
            return value
        if isinstance(value, str):
            try:
                return int(value, 10)
            except ValueError:
                pass
        problems.append(f"{where} 必須是整數,收到 {value!r}")
        return value
    if kind == "float":
        if _is_number(value) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
        problems.append(f"{where} 必須是數字,收到 {value!r}")
        return value
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in TRUE_WORDS | FALSE_WORDS:
            return value.strip().lower() in TRUE_WORDS
        problems.append(f"{where} 必須是 true 或 false,收到 {value!r}")
        return value
    problems.append(f"{where} 的型別無法轉換")
    return value


def plan(recipe, templates_root):
    """展開 dry-run。不連線、不寫 state。template 檔不在時 resolution 是 unresolved,不丟錯。"""
    steps = [_plan_step(step, index, templates_root) for index, step in enumerate(recipe.steps)]
    return {
        "kind": "recipe_dry_run",
        "recipe": {
            "id": recipe.id, "version": recipe.version, "status": recipe.data["status"],
            "title": recipe.data["title"], "summary": recipe.data["summary"],
            "status_note": recipe.data.get("status_note"), "draft": recipe.draft,
        },
        "inputs": recipe.data["inputs"],
        "steps": steps,
        "note": "dry-run:沒有連線 ComfyUI、沒有送出、沒有寫 recipe.state.json",
    }


def _plan_step(step, index, templates_root):
    kind = step["kind"]
    row = {"index": index, "id": step["id"], "kind": kind, "confirmation_point": kind == "confirm",
           "calls_comfyui": False}
    if kind == "confirm":
        row.update(resolution="confirm", message=step["message"], look_at=step.get("look_at"))
        return row
    if kind == "local":
        row.update(resolution="local", command=step["command"], args=step.get("args") or {},
                   outputs=list(step.get("outputs") or []), text=step.get("text"))
        return row
    if kind == "note":
        support = step.get("support")
        row.update(resolution="unsupported" if support == "unsupported" else "note",
                   text=step["text"], template=step.get("template"), support=support)
        return row
    contract = template_contract(templates_root, step["template"])
    executable = step.get("executable", True)
    support = step.get("support")
    if support == "unsupported":
        resolution = "unsupported"
    elif contract is None or contract.get("error"):
        resolution = "unresolved"
    elif not executable:
        resolution = "described"
    else:
        resolution = "resolved"
    row.update(template=step["template"], resolution=resolution, executable=executable, support=support,
               slots=step.get("slots") or {}, text=step.get("text"), frame_anchoring=step.get("frame_anchoring"),
               calls_comfyui=bool(executable and resolution == "resolved"))
    return row


def format_plan(payload, *, heading):
    info = payload["recipe"]
    draft = "  (_drafts)" if info["draft"] else ""
    lines = [f"{heading} {info['id']}  v{info['version']}  {info['status']}{draft}", info["title"], info["summary"]]
    if info.get("status_note"):
        lines.append(f"狀態說明: {info['status_note']}")
    lines.append("")
    lines.append("inputs:")
    for name, spec in payload["inputs"].items():
        bits = [spec["type"], "必填" if _is_required(spec) else "可省略"]
        if "default" in spec:
            bits.append(f"預設 {json.dumps(spec['default'], ensure_ascii=False)}")
        if spec.get("enum"):
            bits.append("可選 " + "／".join(spec["enum"]))
        lines.append(f"  {name}: {'；'.join(bits)}")
        if spec.get("help"):
            lines.append(f"      {spec['help']}")
    lines.append("")
    for step in payload["steps"]:
        lines.extend(_format_step(step))
    lines.append(payload["note"])
    return "\n".join(lines)


def _format_step(step):
    head = f"[{step['index']}] {step['id']}  kind={step['kind']}"
    if step["kind"] == "template":
        head += f"  template={step['template']}  {step['resolution']}"
        if step.get("support"):
            head += f"  support={step['support']}"
        if step.get("executable") is False:
            head += "  executable=false"
    elif step["kind"] == "note" and step.get("template"):
        head += f"  template={step['template']}  {step['resolution']}"
    elif step["kind"] == "local":
        head += "  (本機,不呼叫 ComfyUI)"
    lines = [head]
    if step["kind"] == "template":
        for name, value in (step.get("slots") or {}).items():
            lines.append(f"    {name} = {_show_value(value)}")
        if step.get("frame_anchoring"):
            frame = step["frame_anchoring"]
            lines.append("    frame_anchoring: " + ", ".join(f"{key}={frame[key]}" for key in frame))
    if step["kind"] == "local":
        lines.append(f"    command: {step['command']}")
        for name, value in (step.get("args") or {}).items():
            lines.append(f"    {name} = {_show_value(value)}")
    if step.get("message"):
        lines.append(f"    {step['message']}")
    if step.get("look_at"):
        lines.append(f"    look_at: {step['look_at']}")
    if step.get("text"):
        lines.append(f"    {step['text']}")
    return lines


def _show_value(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


# ---------- 執行與續跑 ----------

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def prepare_output_dir(path):
    out = Path(path).expanduser().resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise RecipeError(f"--output-dir 必須是不存在或空的資料夾: {out}")
    out.mkdir(parents=True, exist_ok=True)
    return out


def _lock_review(state):
    state["content_review"] = CONTENT_REVIEW
    for step in state.get("steps") or []:
        if isinstance(step, dict):
            step["content_review"] = CONTENT_REVIEW
    for record in state.get("confirmations") or []:
        if isinstance(record, dict):
            record["content_review"] = CONTENT_REVIEW


def save_state(directory, state):
    _lock_review(state)
    path = Path(directory) / STATE_FILE
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def load_state(directory):
    path = Path(directory) / STATE_FILE
    if not path.is_file():
        raise RecipeError(f"找不到 {STATE_FILE}: {path}")
    try:
        state = _read_json(path)
    except (OSError, ValueError) as exc:
        raise RecipeError(f"{STATE_FILE} 不是合法 JSON: {exc}") from exc
    if not isinstance(state, dict) or not isinstance(state.get("recipe"), dict) or "id" not in state["recipe"]:
        raise RecipeError(f"{STATE_FILE} 缺少 recipe id")
    if not isinstance(state.get("steps"), list) or not isinstance(state.get("confirmations"), list):
        raise RecipeError(f"{STATE_FILE} 缺少 steps 或 confirmations")
    if not _is_int(state.get("next_index")):
        raise RecipeError(f"{STATE_FILE} 的 next_index 不對")
    _lock_review(state)
    return state


def _initial_state(recipe, inputs):
    return {
        "schema_version": SCHEMA_VERSION,
        "recipe": {"id": recipe.id, "version": recipe.version},
        "draft": recipe.draft,
        "next_index": 0,
        "status": "running",
        "inputs": inputs,
        "content_review": CONTENT_REVIEW,
        "steps": [],
        "confirmations": [],
    }


class OfflineExecutor:
    """不連 ComfyUI、不 queue、不跑本機子程序。template／local 步驟會停在執行前。"""

    def run_template(self, template_id, slots, step_dir):
        raise RecipeNotRunnable(f"template {template_id} 需要 ComfyUI,這次沒有送出、沒有 queue")

    def run_local(self, command, args, step_dir):
        raise RecipeNotRunnable(f"本機步驟尚未執行({command})。這次沒有呼叫外部程式,也沒有呼叫 ComfyUI")


def start_run(recipe, output_dir, values, *, templates_root, executor=None, clock=None, out=None):
    inputs = coerce_inputs(recipe, values, require=True)
    directory = prepare_output_dir(output_dir)
    state = _initial_state(recipe, inputs)
    save_state(directory, state)
    return _advance(directory, recipe, state, templates_root, executor or OfflineExecutor(), clock or utc_now, out)


def resume_run(directory, *, recipes_root, templates_root, confirm=False, executor=None, clock=None, out=None):
    directory = Path(directory).expanduser().resolve()
    state = load_state(directory)
    recipe = load_recipe(recipes_root, state["recipe"]["id"], include_drafts=bool(state.get("draft")),
                         templates_root=templates_root)
    if recipe.version != state["recipe"].get("version"):
        raise RecipeError(
            f"state 的 recipe 版本是 {state['recipe'].get('version')},現在的檔案是 {recipe.version}")
    clock = clock or utc_now
    if confirm:
        barrier = _first_open_confirm(recipe.steps, state)
        if barrier is None:
            raise RecipeError("沒有待確認的步驟")
        step = recipe.steps[barrier]
        _ensure_confirmation(state, step, barrier, _try_resolve(step.get("look_at"), state))
        for record in state["confirmations"]:
            if record["step_id"] == step["id"]:
                record["confirmed"] = True
                record["at"] = clock()
                record["content_review"] = CONTENT_REVIEW
        state["next_index"] = barrier + 1
        state["status"] = "running"
        state.pop("blocked", None)
        save_state(directory, state)
    return _advance(directory, recipe, state, templates_root, executor or OfflineExecutor(), clock, out)


def _advance(directory, recipe, state, templates_root, executor, clock, out):
    steps = recipe.steps
    while state["next_index"] < len(steps):
        barrier = _first_open_confirm(steps, state)
        index = state["next_index"]
        if barrier is not None and index > barrier:
            state["next_index"] = barrier
            return _wait(directory, recipe, state, barrier, out)
        step = steps[index]
        if step["kind"] == "confirm":
            if not _is_confirmed(state, step["id"]):
                return _wait(directory, recipe, state, index, out)
            state["next_index"] = index + 1
            continue
        if _is_descriptive(step):
            _record_described(state, step, index, templates_root, clock)
            state["next_index"] = index + 1
            state.pop("blocked", None)
            save_state(directory, state)
            continue
        if step["kind"] == "template":
            if template_contract(templates_root, step["template"]) is None:
                state["status"] = "blocked"
                state["blocked"] = {"index": index, "id": step["id"], "template": step["template"],
                                    "reason": "unresolved"}
                save_state(directory, state)
                _say(out, f"template {step['template']} 尚未登記(unresolved),沒有送出、沒有 queue")
                return 0
            if _run_bound_step(directory, state, step, index, executor, clock, out, kind="template"):
                return 0
            continue
        if step["kind"] == "local":
            if _run_bound_step(directory, state, step, index, executor, clock, out, kind="local"):
                return 0
            continue
        raise RecipeError(f"不認得的步驟種類 {step['kind']}")
    state["status"] = "completed"
    state["content_review"] = CONTENT_REVIEW
    state.pop("blocked", None)
    save_state(directory, state)
    _say(out, "recipe 步驟已跑完。內容審查仍是 pending。")
    return 0


def _wait(directory, recipe, state, index, out):
    step = recipe.steps[index]
    state["status"] = "waiting_confirm"
    state["next_index"] = index
    look_at = _try_resolve(step.get("look_at"), state)
    _ensure_confirmation(state, step, index, look_at)
    save_state(directory, state)
    _say(out, "等待確認")
    _say(out, step["message"])
    if look_at:
        _say(out, f"請看: {look_at}")
    return 0


def _say(out, text):
    if out is not None:
        print(text, file=out)


def _is_descriptive(step):
    if step["kind"] in ("note",):
        return True
    if step.get("support") == "unsupported":
        return True
    return step["kind"] == "template" and step.get("executable", True) is False


def _record_described(state, step, index, templates_root, clock):
    support = step.get("support")
    if support == "unsupported":
        resolution = "unsupported"
    elif step["kind"] == "template" and template_contract(templates_root, step.get("template")) is None:
        resolution = "unresolved"
    elif step["kind"] == "note":
        resolution = "note"
    else:
        resolution = "described"
    started = clock()
    state["steps"].append({
        "index": index, "id": step["id"], "kind": step["kind"], "status": "described",
        "resolution": resolution, "template": step.get("template"), "support": support,
        "text": step.get("text"), "command": None, "slots": step.get("slots") or {},
        "outputs": {}, "dir": None, "started_at": started, "finished_at": clock(),
        "content_review": CONTENT_REVIEW,
    })


def _run_bound_step(directory, state, step, index, executor, clock, out, *, kind):
    """執行一步。回傳 True 表示已停下(沒有往下)。"""
    step_dir = (Path(directory) / "steps" / f"{index:02d}-{step['id']}").resolve()
    step_dir.mkdir(parents=True, exist_ok=True)
    started = clock()
    try:
        if kind == "template":
            slots = {name: resolve_value(value, state) for name, value in (step.get("slots") or {}).items()}
            result = executor.run_template(step["template"], slots, str(step_dir))
            command = _result_command(result) or _template_command(step["template"], slots)
            detail = slots
        else:
            args = {name: resolve_value(value, state) for name, value in (step.get("args") or {}).items()}
            command_text = resolve_value(step["command"], state)
            result = executor.run_local(command_text, args, str(step_dir))
            command = _result_command(result) or _local_command(command_text, args)
            detail = args
    except RecipeNotRunnable as exc:
        state["status"] = "blocked"
        state["blocked"] = {"index": index, "id": step["id"], "reason": str(exc)}
        save_state(directory, state)
        _say(out, str(exc))
        return True
    if not isinstance(result, dict):
        raise RecipeError(f"步驟 {step['id']} 的 executor 必須回傳 dict")
    outputs = _normalize_outputs(step, result)
    state["steps"].append({
        "index": index, "id": step["id"], "kind": kind, "status": "completed",
        "template": step.get("template"), "command": command, "slots": detail, "outputs": outputs,
        "dir": str(step_dir), "started_at": started, "finished_at": clock(),
        "content_review": CONTENT_REVIEW,
    })
    state["next_index"] = index + 1
    state["status"] = "running"
    state.pop("blocked", None)
    save_state(directory, state)
    return False


def _result_command(result):
    command = result.get("command") if isinstance(result, dict) else None
    return command if isinstance(command, str) and command.strip() else None


def _normalize_outputs(step, result):
    raw = result.get("outputs") if isinstance(result, dict) else None
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise RecipeError(f"步驟 {step['id']} 的 outputs 必須是 object")
    outputs = {str(key): str(value) for key, value in raw.items()}
    missing = [name for name in step.get("outputs") or [] if name not in outputs]
    if missing:
        raise RecipeError(f"步驟 {step['id']} 沒有回傳輸出 {', '.join(missing)}")
    return outputs


def _template_command(template_id, slots):
    parts = [f"gameart.py run {template_id}"]
    for name in sorted(slots):
        parts.append(f"--set {name}={slots[name]}")
    return " ".join(parts)


def _local_command(command, args):
    parts = [command]
    for name in sorted(args):
        parts.append(f"{name} {args[name]}")
    return " ".join(parts)


def _first_open_confirm(steps, state):
    for index, step in enumerate(steps):
        if step["kind"] == "confirm" and not _is_confirmed(state, step["id"]):
            return index
    return None


def _is_confirmed(state, step_id):
    return any(item.get("step_id") == step_id and item.get("confirmed") for item in state["confirmations"])


def _ensure_confirmation(state, step, index, look_at):
    for record in state["confirmations"]:
        if record.get("step_id") == step["id"]:
            record["index"] = index
            record["message"] = step["message"]
            record["look_at"] = look_at
            record["content_review"] = CONTENT_REVIEW
            return record
    record = {
        "step_id": step["id"], "index": index, "confirmed": False, "at": None,
        "message": step["message"], "look_at": look_at, "content_review": CONTENT_REVIEW,
    }
    state["confirmations"].append(record)
    return record


def resolve_value(value, state):
    if not isinstance(value, str):
        return value
    match = REF_RE.fullmatch(value)
    if match:
        return _lookup(match.group(1), state)
    if "{" in value or "}" in value:
        return REF_RE.sub(lambda item: str(_lookup(item.group(1), state)), value)
    return value


def _try_resolve(value, state):
    if value is None:
        return None
    try:
        return str(resolve_value(value, state))
    except RecipeError:
        return value


def _lookup(body, state):
    if body.startswith("inputs."):
        name = body.split(".", 1)[1]
        if name not in state["inputs"]:
            raise RecipeError(f"找不到輸入 {name}")
        return state["inputs"][name]
    parts = body.split(".")
    step_id = parts[1]
    evidence = next((item for item in state["steps"] if item.get("id") == step_id), None)
    if evidence is None:
        raise RecipeError(f"步驟 {step_id} 還沒有結果,不能引用 {body}")
    if parts[2] == "dir":
        if not evidence.get("dir"):
            raise RecipeError(f"步驟 {step_id} 沒有目錄")
        return evidence["dir"]
    output = parts[3]
    outputs = evidence.get("outputs") or {}
    if output not in outputs:
        raise RecipeError(f"步驟 {step_id} 沒有輸出 {output}")
    return outputs[output]
