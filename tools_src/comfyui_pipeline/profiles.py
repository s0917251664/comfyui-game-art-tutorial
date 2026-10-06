"""Load the static, platform-independent image model profiles.

Profiles live next to this module in ``profiles/*.json`` and are deployed with
the rest of ``comfyui_pipeline/``.  Every machine reads the same files; what
differs per machine is only which profile its ``device_config.json`` tier maps
to.  See ``docs/model-profiles-design.md``.
"""

import hashlib
import json
import os

# image_capabilities.json 記錄產生時的設備指紋;generate.py/驗證器用同一組欄位判斷快照是否過期。
FINGERPRINT_FIELDS = ("platform_key", "backend", "tier", "gpu_name", "usable_memory_mb", "precision_support")

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
SCHEMA_VERSION = 1
VALIDATION_STATUSES = frozenset(("verified", "experimental", "unverified", "unsupported"))
# effective_validation 另可回傳 "verified_other_env":有證據,但目前環境與證據記錄的環境不同。
_REQUIRED_KEYS = ("schema_version", "id", "family", "kind", "tiers", "requirements",
                  "models", "sampling", "resolution", "tasks", "validation")
_SAMPLING_KEYS = ("steps", "cfg", "sampler", "scheduler")

_cache = {}


class ProfileError(RuntimeError):
    """Raised when a profile file is missing or does not match the schema."""


def _fail(profile_id, message):
    raise ProfileError(f"模型設定檔 {profile_id!r} 無效：{message}")


_EVIDENCE_REQUIRED = ("report", "report_sha256", "profile_sha256", "env", "approved_by", "approved_at")
ENV_KEYS = ("comfyui_version", "comfyui_commit", "models_hash", "custom_nodes_hash")
_ENV_LABELS = {
    "comfyui_version": "comfyui 版本",
    "comfyui_commit": "comfyui commit",
    "models_hash": "模型庫內容",
    "custom_nodes_hash": "custom_nodes 清單",
}


def _validate_platform_validation(profile_id, profile, platform_key, record):
    """驗證單一平台的 validation。兩種寫法並存:

    - 舊式 dict:``{status, tasks?, min_verified_memory_mb?, evidence?}``(手寫紀錄,視為 legacy 證據)。
    - 新式 list:證據項目清單,每項 ``{report, report_sha256, tasks, profile_sha256, env, min_memory_mb,
      approved_by, approved_at}``;``report: null`` 且 ``legacy: true`` 是無環境紀錄的舊證據。
    """
    where = f"validation.{platform_key}"
    if isinstance(record, dict):
        if record.get("status") not in VALIDATION_STATUSES:
            _fail(profile_id, f"{where}.status 無效：{record.get('status')!r}")
        entries = [record]
    elif isinstance(record, list):
        entries = record
    else:
        _fail(profile_id, f"{where} 必須是 object(舊式)或證據清單")
    for index, entry in enumerate(entries):
        label = where if isinstance(record, dict) else f"{where}[{index}]"
        if not isinstance(entry, dict):
            _fail(profile_id, f"{label} 必須是 object")
        if isinstance(record, list):
            status = entry.get("status", "verified")
            if status not in VALIDATION_STATUSES:
                _fail(profile_id, f"{label}.status 無效：{status!r}")
            if entry.get("legacy"):
                if entry.get("report") is not None:
                    _fail(profile_id, f"{label} 是 legacy 項目,report 必須是 null")
            else:
                absent = [key for key in _EVIDENCE_REQUIRED if not entry.get(key)]
                if absent:
                    _fail(profile_id, f"{label} 缺少欄位 {', '.join(absent)}")
                if not isinstance(entry["env"], dict) or set(entry["env"]) - set(ENV_KEYS):
                    _fail(profile_id, f"{label}.env 只能包含 {', '.join(ENV_KEYS)}")
            if not isinstance(entry.get("tasks"), list):
                _fail(profile_id, f"{label}.tasks 必須是清單")
        unknown_tasks = set(entry.get("tasks") or ()) - set(profile["tasks"])
        if unknown_tasks:
            _fail(profile_id, f"{label} 列出設定檔沒有的 task：{', '.join(sorted(unknown_tasks))}")


def _group_members(models, ref):
    """``controlnet.*`` 群組 = 同前綴且非 experimental 的模型;實驗性模型不能滿足必要需求。"""
    prefix = ref[:-1]
    return sorted(key for key, entry in models.items()
                  if key.startswith(prefix) and not entry.get("experimental"))


def validate_profile(profile, expected_id=None):
    """Check structural invariants; return ``profile`` unchanged when valid."""
    if not isinstance(profile, dict):
        raise ProfileError("模型設定檔必須是 JSON object")
    profile_id = profile.get("id")
    missing = [key for key in _REQUIRED_KEYS if key not in profile]
    if missing:
        _fail(profile_id, f"缺少欄位 {', '.join(missing)}")
    if profile["schema_version"] != SCHEMA_VERSION:
        _fail(profile_id, f"schema_version 必須是 {SCHEMA_VERSION}")
    if expected_id is not None and profile_id != expected_id:
        _fail(profile_id, f"id 與檔名 {expected_id!r} 不一致")

    models = profile["models"]
    if not isinstance(models, dict) or "checkpoint" not in models:
        _fail(profile_id, "models 必須包含 checkpoint")
    for key, entry in models.items():
        if not isinstance(entry, dict) or not entry.get("dir") or not entry.get("file"):
            _fail(profile_id, f"models.{key} 必須有 dir 與 file")
        nodes = entry.get("nodes", [])
        if not isinstance(nodes, list) or any(not isinstance(node, str) or not node for node in nodes):
            _fail(profile_id, f"models.{key}.nodes 必須是 node class 名稱清單")

    sampling = profile["sampling"]
    if not isinstance(sampling, dict) or any(key not in sampling for key in _SAMPLING_KEYS):
        _fail(profile_id, f"sampling 必須包含 {', '.join(_SAMPLING_KEYS)}")

    by_memory = profile["resolution"].get("by_memory")
    if not isinstance(by_memory, list) or not by_memory:
        _fail(profile_id, "resolution.by_memory 必須是非空清單")
    thresholds = [row.get("min_usable_memory_mb") for row in by_memory]
    if any(not isinstance(value, int) for value in thresholds) or thresholds != sorted(thresholds, reverse=True):
        _fail(profile_id, "resolution.by_memory 必須依 min_usable_memory_mb 由大到小排列")
    multiple = profile["resolution"].get("multiple_of", 8)
    for row in by_memory:
        size = row.get("default")
        if (not isinstance(size, list) or len(size) != 2
                or any(not isinstance(v, int) or v <= 0 or v % multiple for v in size)):
            _fail(profile_id, f"resolution.by_memory 的 default 必須是兩個 {multiple} 的倍數")

    for task, spec in profile["tasks"].items():
        for ref in list(spec.get("requires", ())) + list(spec.get("optional_requires", ())):
            if ref.endswith(".*"):
                if not _group_members(models, ref):
                    _fail(profile_id, f"tasks.{task} 引用的模型群組 {ref} 沒有非實驗性成員")
            elif ref not in models:
                _fail(profile_id, f"tasks.{task} 引用不存在的模型 {ref}")

    if not isinstance(profile["validation"], dict):
        _fail(profile_id, "validation 必須是 object")
    for platform_key, record in profile["validation"].items():
        _validate_platform_validation(profile_id, profile, platform_key, record)
    return profile


def list_profile_ids():
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted(name[:-5] for name in os.listdir(PROFILES_DIR) if name.endswith(".json"))


def load_profile(profile_id):
    if profile_id in _cache:
        return _cache[profile_id]
    path = os.path.join(PROFILES_DIR, f"{profile_id}.json")
    try:
        with open(path, encoding="utf-8") as handle:
            profile = json.load(handle)
    except FileNotFoundError as exc:
        raise ProfileError(f"找不到模型設定檔 {path}；部署時要複製整個 comfyui_pipeline/ 資料夾") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f"模型設定檔不是合法 JSON：{path}: {exc}") from exc
    _cache[profile_id] = validate_profile(profile, expected_id=profile_id)
    return _cache[profile_id]


def profile_id_for_tier(tier):
    """Map a ``device_config.json`` tier to its profile id, or ``None`` if unknown."""
    for profile_id in list_profile_ids():
        if tier in load_profile(profile_id)["tiers"]:
            return profile_id
    return None


def model_file(profile, key):
    entry = profile["models"].get(key)
    if entry is None:
        raise ProfileError(
            f"模型設定檔 {profile['id']!r} 沒有模型 {key!r}；這個設定檔不支援需要它的功能"
        )
    return entry["file"]


def task_requirements(profile, task):
    """回傳 task 的模型需求。

    ``required`` 每一項是「候選模型 key 清單」,清單內任一個存在即滿足(一般模型只有一個候選,
    ``controlnet.*`` 群組展開成所有非實驗性成員)。``optional`` 是只影響額外功能的模型 key。
    """
    spec = profile["tasks"].get(task)
    if spec is None:
        raise ProfileError(f"模型設定檔 {profile['id']!r} 不提供 task {task!r}")
    models = profile["models"]
    required = []
    for ref in spec.get("requires", ()):
        required.append(_group_members(models, ref) if ref.endswith(".*") else [ref])
    optional = []
    for ref in spec.get("optional_requires", ()):
        for key in (_group_members(models, ref) if ref.endswith(".*") else [ref]):
            if key not in optional:
                optional.append(key)
    return {"required": required, "optional": optional}


def platform_eligibility(profile, device):
    """回傳這台機器不符合設定檔 requirements 的原因清單;空清單代表符合。"""
    reasons = []
    requirements = profile["requirements"]
    backend = device.get("backend")
    if requirements.get("backends") and backend not in requirements["backends"]:
        reasons.append(f"加速後端 {backend!r} 不在支援清單 {requirements['backends']}")
    usable = device.get("usable_memory_mb")
    minimum = requirements.get("min_usable_memory_mb", 0)
    if usable is None:
        reasons.append("device_config.json 缺少 usable_memory_mb；請在這台機器重跑 detect_device.py")
    elif usable < minimum:
        reasons.append(f"可用記憶體 {usable} MB 低於需求 {minimum} MB")
    supported = device.get("precision_support")
    wanted = requirements.get("precision")
    if supported is None:
        reasons.append("device_config.json 缺少 precision_support；請在這台機器重跑 detect_device.py")
    elif wanted and not set(wanted) & set(supported):
        reasons.append(f"精度需求 {wanted} 與這台機器支援的 {supported} 沒有交集")
    return reasons


def profile_content_sha256(profile):
    """設定檔內容雜湊,**不含 validation 區塊**。

    驗證證據本身會寫進設定檔的 validation;若雜湊包含它,記錄證據就會讓自己綁定的雜湊失效。
    所以只對「會影響產圖行為」的欄位(模型、取樣、解析度、task 需求等)取雜湊。
    """
    content = {key: value for key, value in profile.items() if key != "validation"}
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def env_from_components(components):
    """把 fingerprint.compute_components() 的結果攤平成證據項目的 ``env`` 欄位(缺的值是 None)。"""
    components = components or {}
    comfyui = components.get("comfyui") or {}
    return {
        "comfyui_version": comfyui.get("version"),
        "comfyui_commit": comfyui.get("commit"),
        "models_hash": (components.get("models") or {}).get("hash"),
        "custom_nodes_hash": (components.get("custom_nodes") or {}).get("hash"),
    }


def validation_entries(profile, platform_key):
    """回傳該平台的證據項目清單(統一格式);舊式 dict 轉成一個 legacy 項目。"""
    record = profile["validation"].get(platform_key)
    if not record:
        return []
    if isinstance(record, dict):
        return [{
            "legacy": True, "report": None, "status": record["status"], "tasks": record.get("tasks"),
            "min_memory_mb": record.get("min_verified_memory_mb"), "evidence": record.get("evidence"),
        }]
    entries = []
    for entry in record:
        entry = dict(entry)
        entry.setdefault("status", "verified")
        entry["legacy"] = bool(entry.get("legacy"))
        entries.append(entry)
    return entries


def needs_env(profile, platform_key):
    """該平台是否有需要比對環境的證據項目(只有 legacy 時不必計算環境指紋)。"""
    return any(not entry["legacy"] for entry in validation_entries(profile, platform_key))


def _env_differences(entry, profile, env):
    """證據項目與目前環境的差異說明清單;空清單代表一致(或目前環境未知,無從比較)。"""
    diffs = []
    recorded = entry.get("env") or {}
    for key in ENV_KEYS:
        old = recorded.get(key)
        new = (env or {}).get(key)
        if old is None or new is None or old == new:
            continue
        if key == "comfyui_commit":
            diffs.append(f"{_ENV_LABELS[key]} {str(old)[:8]}→{str(new)[:8]}")
        elif key in ("models_hash", "custom_nodes_hash"):
            diffs.append(f"{_ENV_LABELS[key]}已變動")
        else:
            diffs.append(f"{_ENV_LABELS[key]} {old}→{new}")
    if entry.get("profile_sha256") and entry["profile_sha256"] != profile_content_sha256(profile):
        diffs.append("設定檔內容已變動")
    return diffs


def evaluate_validation(profile, platform_key, usable_memory_mb, task, env=None):
    """回傳 dict: ``status``、``reason``、``basis``、``evidence``。

    status 為 verified / experimental / unverified / unsupported / verified_other_env。
    basis:``evidence``(有報告證據且環境一致)、``legacy``(無環境紀錄的舊證據,視同 verified)、
    ``other_env``、``None``。``env`` 是 env_from_components() 的結果;None 代表不比對環境。
    """
    def result(status, reason=None, basis=None, evidence=None):
        return {"status": status, "reason": reason, "basis": basis, "evidence": evidence}

    entries = validation_entries(profile, platform_key)
    if not entries:
        return result("unverified", f"{platform_key} 平台沒有驗證紀錄")
    if any(entry["status"] == "unsupported" for entry in entries):
        return result("unsupported")
    covering = [e for e in entries if e.get("tasks") is None or task in e["tasks"]]
    if not covering:
        return result("unverified", f"{platform_key} 的驗證紀錄未涵蓋 {task}")
    in_memory, memory_reason = [], None
    for entry in covering:
        minimum = entry.get("min_memory_mb")
        if minimum and (usable_memory_mb is None or usable_memory_mb < minimum):
            memory_reason = memory_reason or (
                f"可用記憶體 {usable_memory_mb} MB 低於 {platform_key} 驗證時的 {minimum} MB")
        else:
            in_memory.append(entry)
    if not in_memory:
        return result("unverified", memory_reason)
    for entry in in_memory:
        if entry["status"] == "experimental":
            return result("experimental", None, evidence=entry.get("report") or entry.get("evidence"))
    verified = [e for e in in_memory if e["status"] == "verified"]
    new_style = [e for e in verified if not e["legacy"]]
    for entry in new_style:
        if not _env_differences(entry, profile, env):
            return result("verified", None, "evidence", entry["report"])
    legacy = [e for e in verified if e["legacy"]]
    if legacy:
        return result("verified", None, "legacy", legacy[0].get("evidence"))
    if not new_style:
        return result(in_memory[0]["status"])
    # 只剩環境不同的證據:用最近一次核准的項目說明
    latest = max(new_style, key=lambda e: e.get("approved_at") or "")
    diffs = _env_differences(latest, profile, env)
    when = (latest.get("approved_at") or "")[:10] or "先前"
    return result("verified_other_env",
                  f"已在 {when} 的環境驗證;目前環境不同({'、'.join(diffs)})", "other_env", latest["report"])


def effective_validation(profile, platform_key, usable_memory_mb, task, env=None):
    """回傳 (status, reason)。沒有紀錄、task 未涵蓋或記憶體低於驗證值時降為 unverified。"""
    outcome = evaluate_validation(profile, platform_key, usable_memory_mb, task, env)
    return outcome["status"], outcome["reason"]


def device_fingerprint(device):
    selected = {field: device.get(field) for field in FINGERPRINT_FIELDS}
    encoded = json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def default_resolution(profile, usable_memory_mb):
    """Pick the default canvas for a machine's usable memory (MB)."""
    for row in profile["resolution"]["by_memory"]:
        if usable_memory_mb >= row["min_usable_memory_mb"]:
            return tuple(row["default"])
    return tuple(profile["resolution"]["by_memory"][-1]["default"])
