"""偵測這台機器可用的圖片模型設定檔與 task;只掃描既有檔案,不下載模型或套件。

輸出 machine-specific 的 ``image_capabilities.json``(不進版控、不可複製到其他機器)。
設定檔本身(``comfyui_pipeline/profiles/*.json``)是全平台共用的靜態檔,這支工具只回答
「這台機器能選哪些設定檔、實際裝了哪些模型與 node、每個 task 的驗證狀態」。
設計見 docs/model-profiles-design.md。
"""

import argparse
import json
import os
import platform
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comfyui_pipeline import profiles  # noqa: E402

SCHEMA_VERSION = 1
device_fingerprint = profiles.device_fingerprint


def _read_json(path, label):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise RuntimeError(f"找不到 {label}: {path}；請先在這台機器執行 detect_device.py") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} 不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} 必須是 JSON object: {path}")
    return value


def _normalise_url(value):
    if not value:
        return None
    value = str(value).strip().rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"ComfyUI URL 必須是完整的 http(s) URL: {value!r}")
    return value


def query_object_info(comfy_url, timeout):
    """回傳 {"status", "url", "classes", "error"};沒給 URL 或連不上時不檢查 node。"""
    if not comfy_url:
        return {"status": "not_checked", "url": None, "classes": [],
                "error": "未提供 --comfy-url；只檢查模型檔案，generate.py 會在送出前再檢查 node"}
    url = f"{comfy_url}/object_info"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except Exception as exc:
        return {"status": "not_checked", "url": url, "classes": [], "error": str(exc)}
    if not isinstance(payload, dict):
        return {"status": "error", "url": url, "classes": [], "error": "ComfyUI /object_info 回應不是 JSON object"}
    return {"status": "available", "url": url, "classes": sorted(str(name) for name in payload), "error": None}


def _model_entry(entry, model_roots):
    candidates = [os.path.abspath(os.path.join(root, entry["dir"], entry["file"])) for root in model_roots]
    present_path = next((path for path in candidates if os.path.isfile(path)), None)
    return {
        "file": entry["file"],
        "directory": entry["dir"],
        "path": present_path or (candidates[0] if candidates else None),
        "present": present_path is not None,
        "size_bytes": os.path.getsize(present_path) if present_path else None,
        "experimental": bool(entry.get("experimental")),
    }


def _missing_nodes(profile, keys, object_classes):
    if object_classes is None:
        return []
    needed = set()
    for key in keys:
        needed.update(profile["models"][key].get("nodes", ()))
    return sorted(needed - object_classes)


def evaluate_profile(profile, device, model_roots, object_classes):
    platform_key = device.get("platform_key")
    usable = device.get("usable_memory_mb")
    models = {key: _model_entry(entry, model_roots) for key, entry in profile["models"].items()}
    eligibility = profiles.platform_eligibility(profile, device)

    tasks = {}
    for task in profile["tasks"]:
        requirement = profiles.task_requirements(profile, task)
        satisfied_keys, missing_models, missing_files = [], [], []
        for candidates in requirement["required"]:
            present = [key for key in candidates if models[key]["present"]]
            if present:
                satisfied_keys.extend(present)
                continue
            if len(candidates) == 1:
                missing_models.append(candidates[0])
                missing_files.append(models[candidates[0]]["file"])
            else:
                missing_models.append(" | ".join(candidates))
                missing_files.append(" | ".join(models[key]["file"] for key in candidates))
        missing_nodes = _missing_nodes(profile, satisfied_keys, object_classes)
        features = {}
        for key in requirement["optional"] + [k for c in requirement["required"] if len(c) > 1 for k in c]:
            if key in features:
                continue
            feature_nodes = _missing_nodes(profile, [key], object_classes)
            features[key] = {
                "available": models[key]["present"] and not feature_nodes,
                "missing_model": None if models[key]["present"] else models[key]["file"],
                "missing_nodes": feature_nodes,
                "experimental": models[key]["experimental"],
            }
        status, reason = profiles.effective_validation(profile, platform_key, usable, task)
        tasks[task] = {
            "available": not eligibility and not missing_models and not missing_nodes,
            "missing_models": missing_models,
            "missing_files": missing_files,
            "missing_nodes": missing_nodes,
            "features": features,
            "validation": status,
            "validation_reason": reason,
        }

    return {
        "display_name": profile.get("display_name"),
        "family": profile["family"],
        "eligible": not eligibility,
        "eligibility_reasons": eligibility,
        "installed": models["checkpoint"]["present"],
        "models": models,
        "tasks": tasks,
    }


def detect(args):
    comfyui_path = os.path.abspath(os.fspath(args.comfyui_path))
    model_roots = [os.path.abspath(os.fspath(root)) for root in (args.model_root or [])]
    if not model_roots:
        model_roots = [os.path.join(comfyui_path, "models")]
    device_config_path = os.path.abspath(
        os.fspath(args.device_config or os.path.join(comfyui_path, "tools", "device_config.json"))
    )
    device = _read_json(device_config_path, "device_config")
    if not device.get("platform_key"):
        raise RuntimeError(
            "device_config.json 缺少 platform_key 等平台欄位（舊版偵測結果）；請在這台機器重跑 detect_device.py"
        )
    node_check = query_object_info(_normalise_url(args.comfy_url), args.http_timeout)
    object_classes = set(node_check["classes"]) if node_check["status"] == "available" else None

    evaluated = {
        profile_id: evaluate_profile(profiles.load_profile(profile_id), device, model_roots, object_classes)
        for profile_id in profiles.list_profile_ids()
    }
    requested = getattr(args, "default_profile", None)
    if requested:
        # 明確指定(例如大機器刻意選較小的設定檔):必須存在、符合平台且底模已安裝,不自動退回其他設定檔。
        if requested not in evaluated:
            raise RuntimeError(
                f"找不到模型設定檔 {requested!r}；可用: {', '.join(sorted(evaluated))}"
            )
        chosen = evaluated[requested]
        if not chosen["eligible"]:
            raise RuntimeError(
                f"模型設定檔 {requested!r} 不適用這台機器：" + "；".join(chosen["eligibility_reasons"])
            )
        if not chosen["installed"]:
            raise RuntimeError(
                f"模型設定檔 {requested!r} 的底模尚未安裝：{chosen['models']['checkpoint']['file']}"
            )
        default_profile = requested
    else:
        tier_profile = profiles.profile_id_for_tier(device.get("tier"))
        default_profile = None
        if tier_profile and evaluated[tier_profile]["eligible"] and evaluated[tier_profile]["installed"]:
            default_profile = tier_profile

    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "machine": platform.node() or None,
        "comfyui_path": comfyui_path,
        "model_roots": model_roots,
        "device_config_path": device_config_path,
        "platform_key": device.get("platform_key"),
        "tier": device.get("tier"),
        "usable_memory_mb": device.get("usable_memory_mb"),
        "device_fingerprint": device_fingerprint(device),
        "node_check": node_check,
        "default_profile": default_profile,
        "profiles": evaluated,
    }


def write_config(path, config, allow_overwrite=False):
    path = os.path.abspath(os.fspath(path))
    if os.path.lexists(path) and not allow_overwrite:
        raise RuntimeError(f"拒絕覆寫既有圖片 capability config: {path}；需要明確給 --overwrite")
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return path


def build_parser():
    parser = argparse.ArgumentParser(
        description="偵測這台機器可用的圖片模型設定檔與 task；不下載模型或套件。"
    )
    parser.add_argument("--comfyui-path", required=True, help="ComfyUI 安裝根目錄")
    parser.add_argument("--model-root", action="append", help="models 根目錄，可重複指定（對應 extra_model_paths）")
    parser.add_argument("--device-config", help="device_config.json 路徑；預設 <ComfyUI>/tools/device_config.json")
    parser.add_argument("--comfy-url", help="可選；若 ComfyUI 正在執行則檢查 /object_info 的 node")
    parser.add_argument("--http-timeout", type=float, default=10.0)
    parser.add_argument(
        "--default-profile",
        help="明確寫入 default_profile（例如大機器刻意選較小的設定檔）；不給就用 tier 對應且已安裝的設定檔",
    )
    parser.add_argument("--out", help="輸出 JSON 路徑；預設 <ComfyUI>/tools/image_capabilities.json")
    parser.add_argument("--overwrite", action="store_true", help="明確允許更新既有 capability config")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.http_timeout <= 0:
        parser.error("--http-timeout 必須是正數")
    try:
        config = detect(args)
        out = args.out or os.path.join(os.path.abspath(args.comfyui_path), "tools", "image_capabilities.json")
        path = write_config(out, config, allow_overwrite=args.overwrite)
    except (OSError, RuntimeError, ValueError, profiles.ProfileError) as exc:
        parser.error(str(exc))
    summary = {
        "path": path,
        "platform_key": config["platform_key"],
        "default_profile": config["default_profile"],
        "node_check": config["node_check"]["status"],
        "profiles": {
            profile_id: {
                "eligible": spec["eligible"],
                "installed": spec["installed"],
                "available_tasks": sorted(task for task, info in spec["tasks"].items() if info["available"]),
            }
            for profile_id, spec in config["profiles"].items()
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
