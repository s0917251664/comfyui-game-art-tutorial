"""Load the static, platform-independent image model profiles.

Profiles live next to this module in ``profiles/*.json`` and are deployed with
the rest of ``comfyui_pipeline/``.  Every machine reads the same files; what
differs per machine is only which profile its ``device_config.json`` tier maps
to.  See ``docs/model-profiles-design.md``.
"""

import json
import os

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
SCHEMA_VERSION = 1
VALIDATION_STATUSES = frozenset(("verified", "experimental", "unverified", "unsupported"))
_REQUIRED_KEYS = ("schema_version", "id", "family", "kind", "tiers", "requirements",
                  "models", "sampling", "resolution", "tasks", "validation")
_SAMPLING_KEYS = ("steps", "cfg", "sampler", "scheduler")

_cache = {}


class ProfileError(RuntimeError):
    """Raised when a profile file is missing or does not match the schema."""


def _fail(profile_id, message):
    raise ProfileError(f"模型設定檔 {profile_id!r} 無效：{message}")


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
                prefix = ref[:-1]
                if not any(key.startswith(prefix) for key in models):
                    _fail(profile_id, f"tasks.{task} 引用不存在的模型群組 {ref}")
            elif ref not in models:
                _fail(profile_id, f"tasks.{task} 引用不存在的模型 {ref}")

    for platform_key, record in profile["validation"].items():
        status = record.get("status") if isinstance(record, dict) else None
        if status not in VALIDATION_STATUSES:
            _fail(profile_id, f"validation.{platform_key}.status 無效：{status!r}")
        unknown_tasks = set(record.get("tasks", ())) - set(profile["tasks"])
        if unknown_tasks:
            _fail(profile_id, f"validation.{platform_key} 列出設定檔沒有的 task：{', '.join(sorted(unknown_tasks))}")
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


def default_resolution(profile, usable_memory_mb):
    """Pick the default canvas for a machine's usable memory (MB)."""
    for row in profile["resolution"]["by_memory"]:
        if usable_memory_mb >= row["min_usable_memory_mb"]:
            return tuple(row["default"])
    return tuple(profile["resolution"]["by_memory"][-1]["default"])
