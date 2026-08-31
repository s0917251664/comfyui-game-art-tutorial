"""Offline verifier for portable ComfyUI installs.

This tool is intentionally read-only. It checks whether the deployed
``device_config.json`` matches a live ``detect_device.py`` run on the current
machine, then optionally verifies the deployed video capability config.
Hardware differences across machines are expected; the verifier only flags a
deployment as stale when the deployed snapshot does not match the current
machine's detector output.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

SYNC_SOURCE_FILES = (
    ("generate.py", Path("tools_src/generate.py"), Path("tools/generate.py")),
    ("detect_device.py", Path("tools_src/detect_device.py"), Path("tools/detect_device.py")),
)

SYNC_SOURCE_FILES_VIDEO = (
    ("detect_video_capabilities.py", Path("tools_src/detect_video_capabilities.py"), Path("tools/detect_video_capabilities.py")),
)


class VerificationError(RuntimeError):
    """Raised when the verifier cannot complete a check."""


def _normalize_os_label(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    aliases = {
        "windows": "Windows",
        "win32": "Windows",
        "darwin": "macOS",
        "macos": "macOS",
        "osx": "macOS",
        "linux": "Linux",
    }
    return aliases.get(text, str(value).strip())


def _normalize_machine(value):
    if value is None:
        return None
    return str(value).strip().lower()


def _normalize_backend(value):
    if value is None:
        return None
    return str(value).strip().lower()


def _normalize_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_int(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return value
    return int(value)


def _resolve_path(value, base_dir):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve(strict=False)


def _load_json_object(path, label):
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise VerificationError(f"{label} 不存在: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{label} 不是有效 JSON: {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{label} 必須是 JSON object: {path.name}")
    return value


def _normalize_source_text(path):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise VerificationError(f"{path.name} 不存在") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _format_field_diff(field, expected, actual):
    return f"{field}: deployed={actual!r} live={expected!r}"


def _compare_device_configs(live_config, deployed_config):
    if not isinstance(live_config, dict):
        raise VerificationError("live detect() 沒有回傳 JSON object")
    if not isinstance(deployed_config, dict):
        raise VerificationError("device_config.json 必須是 JSON object")

    diffs = []
    comparators = {
        "os": (_normalize_os_label, _normalize_os_label),
        "machine": (_normalize_machine, _normalize_machine),
        "backend": (_normalize_backend, _normalize_backend),
        "tier": (_normalize_text, _normalize_text),
        "checkpoint": (_normalize_text, _normalize_text),
        "default_width": (_normalize_int, _normalize_int),
        "default_height": (_normalize_int, _normalize_int),
        "gpu_name": (_normalize_text, _normalize_text),
        "vram_mb": (_normalize_int, _normalize_int),
        "unified_memory_mb": (_normalize_int, _normalize_int),
        "torch_index_url": (_normalize_text, _normalize_text),
    }
    for field, (live_norm, deployed_norm) in comparators.items():
        live_value = live_norm(live_config.get(field))
        deployed_value = deployed_norm(deployed_config.get(field))
        if live_value != deployed_value:
            diffs.append(_format_field_diff(field, live_value, deployed_value))
    return diffs


def _load_detector_callable(repo_root, detector=None):
    if detector is not None:
        return detector
    detector_path = repo_root / "tools_src" / "detect_device.py"
    if not detector_path.is_file():
        raise VerificationError(f"找不到 live detector: {detector_path.name}")
    spec = importlib.util.spec_from_file_location("_portable_detect_device", detector_path)
    if spec is None or spec.loader is None:
        raise VerificationError("無法載入 detect_device.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "detect"):
        raise VerificationError("detect_device.py 不含 detect()")
    return module.detect


def _load_live_device_snapshot(repo_root, detector=None):
    detector_fn = _load_detector_callable(repo_root, detector)
    try:
        snapshot = detector_fn()
    except Exception as exc:
        raise VerificationError(f"live detect() 執行失敗: {exc}") from exc
    if not isinstance(snapshot, dict):
        raise VerificationError("live detect() 必須回傳 JSON object")
    return snapshot


def _check_source_sync(repo_root, comfyui_path, results, require_video=False):
    for label, repo_relative, deployed_relative in SYNC_SOURCE_FILES:
        repo_file = repo_root / repo_relative
        deployed_file = comfyui_path / deployed_relative
        if not repo_file.is_file():
            results.append(("fail", f"{label} source sync", "repo source 不存在"))
            continue
        if not deployed_file.is_file():
            results.append(("fail", f"{label} source sync", "部署副本不存在"))
            continue
        if _normalize_source_text(repo_file) == _normalize_source_text(deployed_file):
            results.append(("pass", f"{label} source sync", "repo 與部署副本一致"))
        else:
            results.append(
                ("fail", f"{label} source sync", "repo 與部署副本內容不同；請重新同步部署副本")
            )

    if require_video:
        for label, repo_relative, deployed_relative in SYNC_SOURCE_FILES_VIDEO:
            repo_file = repo_root / repo_relative
            deployed_file = comfyui_path / deployed_relative
            if not repo_file.is_file():
                results.append(("fail", f"{label} source sync", "repo source 不存在"))
                continue
            if not deployed_file.is_file():
                results.append(("fail", f"{label} source sync", "部署副本不存在"))
                continue
            if _normalize_source_text(repo_file) == _normalize_source_text(deployed_file):
                results.append(("pass", f"{label} source sync", "repo 與部署副本一致"))
            else:
                results.append(
                    ("fail", f"{label} source sync", "repo 與部署副本內容不同；請重新同步部署副本")
                )


def _resolve_local_config_paths(local_config, config_dir):
    required = ("comfyui_path", "python_exe", "generate_script", "comfyui_url", "output_dir")
    missing = [field for field in required if field not in local_config or local_config[field] in (None, "")]
    if missing:
        raise VerificationError(f"local_config 缺少必要欄位: {', '.join(missing)}")

    resolved = {}
    resolved["comfyui_path"] = _resolve_path(local_config["comfyui_path"], config_dir)
    resolved["python_exe"] = _resolve_path(local_config["python_exe"], config_dir)
    resolved["generate_script"] = _resolve_path(local_config["generate_script"], config_dir)
    resolved["output_dir"] = _resolve_path(local_config["output_dir"], config_dir)
    video_config = local_config.get("video_config")
    resolved["video_config"] = _resolve_path(video_config, config_dir) if video_config else None

    if not resolved["comfyui_path"].is_dir():
        raise VerificationError("local_config.comfyui_path 指向的目錄不存在")
    if not resolved["python_exe"].is_file():
        raise VerificationError("local_config.python_exe 指向的檔案不存在")
    if not resolved["generate_script"].is_file():
        raise VerificationError("local_config.generate_script 指向的檔案不存在")
    if not resolved["output_dir"].is_dir():
        raise VerificationError("local_config.output_dir 指向的目錄不存在")

    comfyui_url = _normalize_url(local_config["comfyui_url"])
    if comfyui_url is None:
        raise VerificationError("local_config.comfyui_url 必須是有效的 http(s) URL")

    resolved["comfyui_url"] = comfyui_url
    return resolved


def _normalize_url(value):
    if value is None:
        return None
    text = str(value).strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text


def _default_video_config_path(comfyui_path):
    return comfyui_path / "tools" / "video_capabilities.json"


def _backend_is_available(spec):
    if not isinstance(spec, dict):
        return False
    if spec.get("available") is False or spec.get("enabled") is False:
        return False
    capabilities = spec.get("capabilities")
    return isinstance(capabilities, (list, tuple, set)) and bool(capabilities)


def _video_model_roots(video_config, video_config_path):
    roots = video_config.get("model_roots")
    if isinstance(roots, str):
        roots = [roots]
    if not isinstance(roots, (list, tuple)):
        roots = []
    resolved = []
    for root in roots:
        if root:
            resolved.append(_resolve_path(root, video_config_path.parent))
    if resolved:
        return resolved
    comfyui_path = video_config.get("comfyui_path")
    if comfyui_path:
        return [_resolve_path(comfyui_path, video_config_path.parent) / "models"]
    return []


def _resolve_video_model_path(entry, video_config, video_config_path):
    if isinstance(entry, str):
        entry = {"file": entry}
    if not isinstance(entry, dict):
        return None

    explicit_path = entry.get("path")
    if explicit_path:
        return _resolve_path(explicit_path, video_config_path.parent)

    filename = entry.get("file") or entry.get("name")
    if not filename:
        return None
    directory = entry.get("directory")
    candidates = []
    for root in _video_model_roots(video_config, video_config_path):
        candidate = root / filename if not directory else root / directory / filename
        candidates.append(candidate)
    return next((candidate for candidate in candidates if candidate.is_file()), candidates[0] if candidates else None)


def _validate_video_config(local_paths, deployed_device_config, video_config, video_config_path):
    if not isinstance(video_config, dict):
        raise VerificationError("video_config 必須是 JSON object")
    if video_config.get("schema_version") != 1:
        raise VerificationError(
            f"video_config schema_version 不支援: {video_config.get('schema_version')!r}"
        )
    embedded_device = video_config.get("device_config")
    if not isinstance(embedded_device, dict):
        raise VerificationError("video_config 缺少內嵌 device_config")

    diffs = _compare_device_configs(deployed_device_config, embedded_device)
    if diffs:
        raise VerificationError(
            "video_config 內嵌 device_config 與外部 device_config 不一致；"
            + "; ".join(diffs)
        )

    expected_comfyui = local_paths["comfyui_path"]
    actual_comfyui = _resolve_path(video_config.get("comfyui_path"), video_config_path.parent) if video_config.get("comfyui_path") else None
    if actual_comfyui != expected_comfyui:
        raise VerificationError(
            "video_config.comfyui_path 與 local_config 不一致；"
            f"deployed={video_config.get('comfyui_path')!r}"
        )

    expected_python = local_paths["python_exe"]
    actual_python = _resolve_path(video_config.get("python_exe"), video_config_path.parent) if video_config.get("python_exe") else None
    if actual_python != expected_python:
        raise VerificationError(
            "video_config.python_exe 與 local_config 不一致；"
            f"deployed={video_config.get('python_exe')!r}"
        )

    backends = video_config.get("backends")
    if not isinstance(backends, dict) or not backends:
        raise VerificationError("video_config 缺少 backends")

    available_backends = []
    missing_paths = []
    size_mismatches = []
    for backend, spec in backends.items():
        if not _backend_is_available(spec):
            continue
        available_backends.append(backend)
        models = spec.get("models")
        if not isinstance(models, dict):
            missing_paths.append(f"{backend}: models 欄位不存在")
            continue
        checked_models = 0
        for model_key, entry in models.items():
            # The detector records every model in a backend, including optional
            # models for capabilities that this machine does not expose.  A
            # present=false entry is therefore valid and must not turn a
            # lightweight/partial backend into a false failure.
            if isinstance(entry, dict) and entry.get("present") is False:
                continue
            checked_models += 1
            resolved_path = _resolve_video_model_path(entry, video_config, video_config_path)
            if resolved_path is None or not resolved_path.is_file():
                missing_paths.append(f"{backend}.{model_key}")
                continue
            if isinstance(entry, dict) and entry.get("size_bytes") is not None:
                expected_size = entry.get("size_bytes")
                if isinstance(expected_size, bool) or not isinstance(expected_size, int):
                    size_mismatches.append(f"{backend}.{model_key}: invalid size_bytes")
                elif resolved_path.stat().st_size != expected_size:
                    size_mismatches.append(
                        f"{backend}.{model_key}: expected={expected_size} "
                        f"actual={resolved_path.stat().st_size}"
                    )
        if checked_models == 0:
            missing_paths.append(f"{backend}: 沒有任何 present model")

    if not available_backends:
        raise VerificationError("video_config 沒有任何 available backend")
    if missing_paths:
        raise VerificationError(
            "video_config 列出的可用 backend 模型路徑不存在；"
            + ", ".join(missing_paths)
        )
    if size_mismatches:
        raise VerificationError(
            "video_config 模型尺寸與 capability snapshot 不一致；"
            + ", ".join(size_mismatches)
        )

    return available_backends


def verify_install(repo_root, config_path, require_video=False, detector=None):
    repo_root = Path(repo_root).resolve(strict=False)
    config_path = Path(config_path)
    if not config_path.is_absolute():
        config_path = (repo_root / config_path).resolve(strict=False)
    config_dir = config_path.parent

    results = []
    results.append(("info", "硬體差異本身是預期行為；這個驗證器只會把未重跑 detect_device.py 的 stale snapshot 標成 FAIL。"))

    local_config = _load_json_object(config_path, "local_config")
    paths = _resolve_local_config_paths(local_config, config_dir)
    results.append(("pass", "local_config", "comfyui_path/python_exe/generate_script/comfyui_url/output_dir 可用"))

    _check_source_sync(repo_root, paths["comfyui_path"], results, require_video=require_video)

    expected_generate_path = paths["comfyui_path"] / "tools" / "generate.py"
    if paths["generate_script"] != expected_generate_path:
        results.append(
            ("fail", "local_config.generate_script",
             "必須指向 <ComfyUI>/tools/generate.py，避免執行到另一份部署副本")
        )
    else:
        results.append(
            ("pass", "local_config.generate_script", "指向 <ComfyUI>/tools/generate.py")
        )

    live_device = _load_live_device_snapshot(repo_root, detector=detector)
    deployed_device_path = paths["comfyui_path"] / "tools" / "device_config.json"
    deployed_device = _load_json_object(deployed_device_path, "device_config")
    diffs = _compare_device_configs(live_device, deployed_device)
    if diffs:
        results.append(
            ("fail", "device_config 對照 live detect()", "; ".join(diffs) + "；請在目標機重跑 detect_device.py")
        )
    else:
        results.append(("pass", "device_config 對照 live detect()", "部署 snapshot 與目標機 live detect() 一致"))

    if require_video:
        video_config_path = paths["video_config"] or _default_video_config_path(paths["comfyui_path"])
        video_config = _load_json_object(video_config_path, "video_config")
        try:
            available_backends = _validate_video_config(paths, deployed_device, video_config, video_config_path)
        except VerificationError as exc:
            results.append(("fail", "video_config", str(exc)))
        else:
            results.append(
                ("pass", "video_config", f"available backend: {', '.join(sorted(available_backends))}")
            )

    passed = sum(1 for kind, *rest in results if kind == "pass")
    failed = sum(1 for kind, *rest in results if kind == "fail")
    return results, passed, failed


def build_parser():
    parser = argparse.ArgumentParser(
        description="離線驗證 ComfyUI 跨設備部署；會先跑 live detect()，再比對部署 snapshot。"
    )
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1], help="repo 根目錄")
    parser.add_argument("--config", default="local_config.json", help="local_config.json 路徑")
    parser.add_argument("--require-video", action="store_true", help="同時驗證 video_capabilities.json")
    return parser


def main(argv=None, detector=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        results, passed, failed = verify_install(
            args.repo_root, args.config, require_video=args.require_video, detector=detector
        )
    except VerificationError as exc:
        print(f"[FAIL] {exc}")
        print("[SUMMARY] passed=0 failed=1")
        return 1

    for item in results:
        kind = item[0]
        if kind == "info":
            print(f"[INFO] {item[1]}")
            continue
        _, name, detail = item
        print(f"[{kind.upper()}] {name}: {detail}")

    print(f"[SUMMARY] passed={passed} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
