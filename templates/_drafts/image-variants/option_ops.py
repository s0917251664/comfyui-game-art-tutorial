"""方案 B 原型:讓 option 可以插入／替換節點(PR 4.1,獨立 helper,不改 runner)。

現有 runner 的 option 只有 ``set_link``(新增一條連線)與 ``set_value``,而且 ``check_patched``
禁止新增或刪除節點、禁止改 class_type。方案 B 要把下面這些搬進 runner(對應的修改點寫在 ADR):

- option 從布林改成「多選一」(``choices``),每個 choice 宣告一組效果;
- 新 op:``add_node``(插入整個節點)、``replace_node``(同 id 換 class_type)、``relink``(改寫既有連線);
- choice 自己的 slot(例如 LoRA 的檔名與強度,目標在插入的節點上),只有選到時才存在;
- choice 自己的 models／requires_custom_nodes／outputs(preflight 與下載要依選擇結果決定);
- patch 後的檢查改成「差異只能落在 slot 目標＋已選 choice 宣告的節點與 input」。

流程:先用現有 runner 載入 base template(雙 hash、slot 驗證照舊)並 patch base slot,
再套用 ``variants.json`` 的 choice,最後做結構檢查。
"""
import copy
from pathlib import Path

from comfyui_pipeline.runner import template as T

SPEC_FILE = "variants.json"
DRAFT_SCHEMA = "option-ops-v0"
OPS = ("add_node", "replace_node", "relink", "set_value")
EFFECT_KEYS = {"ops", "slots", "models", "requires_custom_nodes", "outputs"}


class VariantTemplate:
    def __init__(self, base, spec):
        self.base = base
        self.spec = spec

    @property
    def id(self):
        return self.base.id

    @property
    def options(self):
        return self.spec["options"]


def load(root, template_id, repo_root):
    """載入 base template(runner 的完整驗證)與 variants.json(這裡的驗證)。"""
    base = T.load_template(root, template_id, repo_root=repo_root)
    spec = T.read_json(Path(base.directory) / SPEC_FILE)
    problems = validate_spec(base, spec)
    if problems:
        raise T.TemplateError(problems, template_id)
    return VariantTemplate(base, spec)


def _links(node):
    return [value for value in node["inputs"].values() if T._is_link(value)]


def validate_spec(base, spec):
    """回傳問題清單。重點是讓不同 option 互不干擾:同一個節點或 input 只能被一個 option 動到。"""
    problems = []
    if spec.get("draft_schema") != DRAFT_SCHEMA or spec.get("base") != base.id:
        return [f"variants.json 必須是 {DRAFT_SCHEMA},base 必須是 {base.id}"]
    graph = base.graph
    base_slots = base.slots
    base_targets = base.declared_targets()
    owner = {}  # (node, input) 或 (node, "*") → option 名稱
    added_ids = {}
    output_owner, role_owner = None, {}  # outputs 與 models[].role 也只能由一個 option 改
    for option, entry in spec["options"].items():
        choices = entry.get("choices")
        if not isinstance(choices, dict) or entry.get("default") not in choices:
            problems.append(f"option {option}: 需要 choices 與其中一個 default")
            continue
        if choices[entry["default"]]:
            problems.append(f"option {option}: default choice 必須沒有效果(= base graph)")
        for choice, effect in choices.items():
            where = f"option {option}={choice}"
            if set(effect) - EFFECT_KEYS:
                problems.append(f"{where}: 不認得的欄位 {sorted(set(effect) - EFFECT_KEYS)}")
            local_added = {}
            for op in effect.get("ops", []):
                kind = op.get("op")
                if kind not in OPS:
                    problems.append(f"{where}: op 必須是 {', '.join(OPS)} 之一")
                    continue
                if kind == "add_node":
                    node_id = op["id"]
                    if node_id in graph:
                        problems.append(f"{where}: add_node {node_id} 已經在 base graph")
                    if added_ids.get(node_id, option) != option:
                        problems.append(f"{where}: add_node {node_id} 和 option {added_ids[node_id]} 衝突")
                    added_ids[node_id] = option
                    local_added[node_id] = op["node"]
                    continue
                node_id = op.get("id") if kind == "replace_node" else op.get("node")
                if node_id not in graph and node_id not in local_added:
                    problems.append(f"{where}: {kind} 指向不存在的節點 {node_id}")
                    continue
                key = (node_id, "*") if kind == "replace_node" else (node_id, op["input"])
                # replace_node 會整顆蓋掉節點,所以這個節點上任何別的 option 登記過的 input 都算衝突(不看書寫順序)
                others = [k for k in owner if k[0] == node_id] if kind == "replace_node" else [(node_id, "*"), key]
                for other in others:
                    if owner.get(other, option) != option:
                        problems.append(f"{where}: {key} 和 option {owner[other]} 改動的 {other} 衝突")
                owner[key] = option
                if key in base_targets or any(n == node_id for n, _ in base_targets) and kind == "replace_node":
                    problems.append(f"{where}: {kind} 不能改 base slot 的目標 {key}")
                if kind == "relink":
                    current = graph.get(node_id, local_added.get(node_id, {})).get("inputs", {}).get(op["input"])
                    if current is not None and not T._is_link(current):
                        problems.append(f"{where}: relink 只能改連線,{node_id}.{op['input']} 是值")
                    if not T._is_link(op["from"]):
                        problems.append(f"{where}: from 必須是 [節點 id, 輸出序號]")
            # 插入節點的連線只能指向 base 或同一個 choice 插入的節點
            known = set(graph) | set(local_added)
            for op in effect.get("ops", []):
                kind = op.get("op")
                if kind in ("add_node", "replace_node") and isinstance(op.get("node"), dict):
                    refs = _links(op["node"])
                elif kind == "relink":
                    refs = [op["from"]]
                elif kind == "set_value" and T._is_link(op.get("value")):  # 值也可能是連線,一樣不能指向別的 option 的節點
                    refs = [op["value"]]
                else:
                    refs = []
                for ref in refs:
                    if ref[0] not in known:
                        problems.append(f"{where}: 連線指向不存在的節點 {ref[0]}")
            if "outputs" in effect:
                if output_owner not in (None, option):
                    problems.append(f"{where}: outputs 已經被 option {output_owner} 改動")
                output_owner = option
            for model in effect.get("models", []):
                if role_owner.get(model["role"], option) != option:
                    problems.append(f"{where}: model role {model['role']} 已經被 option {role_owner[model['role']]} 改動")
                role_owner[model["role"]] = option
            # choice 的 slot:名稱不能和 base 重複,目標必須在這個 choice 插入的節點上,占位都要有人認領
            slots = effect.get("slots", {})
            claimed = set()
            for name, slot in slots.items():
                if name in base_slots:
                    problems.append(f"{where}: slot {name} 和 base 重複")
                for target in slot["targets"]:
                    if target["node"] not in local_added:
                        problems.append(f"{where}: slot {name} 的目標 {target['node']} 不是這個 choice 插入的節點")
                    claimed.add((target["node"], target["input"]))
            for node_id, node in local_added.items():
                for field, value in node["inputs"].items():
                    if isinstance(value, str) and T.PLACEHOLDER_RE.match(value) and (node_id, field) not in claimed:
                        problems.append(f"{where}: {node_id}.{field} 的占位 {value} 沒有 slot 認領")
    return problems


def build(vt, values=None, choices=None, upload_paths=None, *, run_id="draft"):
    """回傳 dict(graph, outputs, models, requires_custom_nodes, changes)。"""
    values = dict(values or {})
    chosen = {}
    for option, entry in vt.options.items():
        chosen[option] = (choices or {}).get(option, entry["default"])
        if chosen[option] not in entry["choices"]:
            raise T.TemplateError(f"option {option} 沒有 {chosen[option]!r}(可用: {', '.join(entry['choices'])})", vt.id)
    unknown = set(choices or {}) - set(vt.options)
    if unknown:
        raise T.TemplateError(f"沒有 option {sorted(unknown)}", vt.id)
    effects = [vt.options[o]["choices"][c] for o, c in chosen.items()]
    option_slots = {name: slot for effect in effects for name, slot in effect.get("slots", {}).items()}

    base_values = {k: v for k, v in values.items() if k not in option_slots}
    resolution = T.resolve(vt.base, base_values, run_id=run_id)
    graph, _changes = T.patch(vt.base, resolution, upload_paths)

    allowed_nodes, allowed_inputs, replaced = set(), set(), set()
    for effect in effects:
        for op in effect.get("ops", []):
            kind = op["op"]
            if kind == "add_node":
                graph[op["id"]] = copy.deepcopy(op["node"])
                allowed_nodes.add(op["id"])
            elif kind == "replace_node":
                graph[op["id"]] = copy.deepcopy(op["node"])
                replaced.add(op["id"])
            else:
                graph[op["node"]]["inputs"][op["input"]] = copy.deepcopy(op["from" if kind == "relink" else "value"])
                allowed_inputs.add((op["node"], op["input"]))
    problems = []
    for name, slot in option_slots.items():
        try:
            if name in values:
                value = T.coerce(name, slot, values[name])
            elif "default" in slot:
                value = copy.deepcopy(slot["default"])
            else:
                problems.append(f"slot {name} 必填(選了會用到它的 option)")
                continue
            T.validate_value(name, slot, value)
        except T.TemplateError as exc:
            problems.extend(exc.problems)
            continue
        for target in slot["targets"]:
            graph[target["node"]]["inputs"][target["input"]] = copy.deepcopy(value)
    if problems:
        raise T.TemplateError(problems, vt.id)

    changes = _check(vt, graph, resolution, allowed_nodes, allowed_inputs, replaced)
    outputs, models, custom = vt.base.data["outputs"], list(vt.base.data["models"]), list(vt.base.data["requires_custom_nodes"])
    for effect in effects:
        if "outputs" in effect:
            outputs = effect["outputs"]
        for model in effect.get("models", []):
            models = [m for m in models if m["role"] != model["role"]] + [model]
        custom += [c for c in effect.get("requires_custom_nodes", []) if c not in custom]
    return {"graph": graph, "outputs": outputs, "models": models, "requires_custom_nodes": custom,
            "options": chosen, "changes": changes, "slot_values": resolution["slot_values"]}


def _check(vt, graph, resolution, allowed_nodes, allowed_inputs, replaced):
    """runner check_patched 的擴充版:新增節點、換 class 都必須是已選 choice 宣告的。"""
    problems = []
    for node_id, node in graph.items():
        for field, value in node["inputs"].items():
            if isinstance(value, str) and T.PLACEHOLDER_RE.match(value):
                problems.append(f"{node_id}.{field} 還是占位 {value}")
            if field in T.SEED_INPUTS and value == -1:
                problems.append(f"{node_id}.{field} 還是 -1")
            if T._is_link(value) and value[0] not in graph:
                problems.append(f"{node_id}.{field} 連到不存在的節點 {value[0]}")
    original = vt.base.graph
    extra = set(graph) - set(original) - allowed_nodes
    if extra:
        problems.append(f"新增了沒有宣告的節點 {sorted(extra)}")
    if set(original) - set(graph):
        problems.append(f"節點被刪除 {sorted(set(original) - set(graph))}")
    base_allowed = vt.base.declared_targets()
    changed = []
    for node_id in sorted(set(original) & set(graph)):
        before, after = original[node_id], graph[node_id]
        if node_id in replaced:
            changed.append(f"{node_id}.*")
            continue
        if before["class_type"] != after["class_type"]:
            problems.append(f"節點 {node_id} 的 class_type 被改動")
            continue
        for field in set(before["inputs"]) | set(after["inputs"]):
            old, new = before["inputs"].get(field), after["inputs"].get(field)
            if old == new and type(old) is type(new):
                continue
            if (node_id, field) not in base_allowed and (node_id, field) not in allowed_inputs:
                problems.append(f"{node_id}.{field} 不是宣告過的目標,不能改")
            changed.append(f"{node_id}.{field}")
    if problems:
        raise T.TemplateError(problems, vt.id)
    return sorted(changed) + sorted(f"+{n}" for n in allowed_nodes)
