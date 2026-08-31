"""Detect machine-local ComfyUI video capabilities without downloading assets.

The detector writes a capability manifest consumed by ``tools/generate.py``.
It only probes the selected Python runtime, scans already-present model files,
and optionally reads ComfyUI's ``/object_info`` endpoint.  It never installs
packages or downloads models.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


SCHEMA_VERSION = 1
MODEL_DIRECTORIES = {
    "h3": {
        "i2v_unet": "diffusion_models",
        "ref_unet": "diffusion_models",
        "clip": "text_encoders",
        "video_vae": "vae",
        "audio_vae": "vae",
    },
    "wan": {
        "i2v_unet": "diffusion_models",
        "control_unet": "diffusion_models",
        "clip": "text_encoders",
        "vae": "vae",
    },
}


def _load_generate_catalog():
    """Load the canonical implementation catalog beside this script."""
    try:
        from comfyui_pipeline import video_catalog as catalog
    except ImportError as exc:
        raise RuntimeError(
            "找不到 comfyui_pipeline.video_catalog；無法取得影片 graph catalog。"
        ) from exc
    return catalog


def _default_python(comfyui_path):
    if os.name == "nt":
        return os.path.join(comfyui_path, ".venv", "Scripts", "python.exe")
    return os.path.join(comfyui_path, ".venv", "bin", "python")


def _runtime_probe(python_exe):
    code = r'''
import json
import platform
import sys

result = {
    "python": ".".join(str(part) for part in sys.version_info[:3]),
    "platform": platform.platform(),
    "pillow": None,
    "torch": None,
    "pyav": None,
    "torch_cuda": None,
    "gpu_name": None,
    "torch_cuda_version": None,
    "error": None,
}
try:
    import PIL
    result["pillow"] = getattr(PIL, "__version__", None)
except Exception as exc:
    result["error"] = "Pillow: " + str(exc)
try:
    import torch
    result["torch"] = getattr(torch, "__version__", None)
    result["torch_cuda_version"] = getattr(getattr(torch, "version", None), "cuda", None)
    result["torch_cuda"] = bool(torch.cuda.is_available())
    if result["torch_cuda"]:
        result["gpu_name"] = torch.cuda.get_device_name(0)
except Exception as exc:
    result["error"] = (result["error"] + "; " if result["error"] else "") + "Torch: " + str(exc)
try:
    import av
    result["pyav"] = getattr(av, "__version__", None)
except Exception as exc:
    result["error"] = (result["error"] + "; " if result["error"] else "") + "PyAV: " + str(exc)
print(json.dumps(result, ensure_ascii=False))
'''
    try:
        completed = subprocess.run(
            [os.fspath(python_exe), "-c", code],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "python": None,
            "pillow": None,
            "torch": None,
            "pyav": None,
            "torch_cuda": None,
            "gpu_name": None,
            "torch_cuda_version": None,
            "probe_error": str(exc),
        }
    stdout = (completed.stdout or "").strip().splitlines()
    if not stdout:
        return {
            "python": None,
            "pillow": None,
            "torch": None,
            "pyav": None,
            "torch_cuda": None,
            "gpu_name": None,
            "torch_cuda_version": None,
            "probe_error": (completed.stderr or "").strip() or f"probe exit={completed.returncode}",
        }
    try:
        result = json.loads(stdout[-1])
    except json.JSONDecodeError as exc:
        return {
            "python": None,
            "pillow": None,
            "torch": None,
            "pyav": None,
            "torch_cuda": None,
            "gpu_name": None,
            "torch_cuda_version": None,
            "probe_error": f"runtime probe JSON 無效: {exc}; stdout={stdout[-1]!r}",
        }
    if completed.returncode != 0:
        result["probe_error"] = (completed.stderr or "").strip() or f"probe exit={completed.returncode}"
    return result


def _read_json(path, label):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        return None
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


def _schema_fingerprint(payload, classes):
    selected = {}
    for name in sorted(classes):
        info = payload.get(name)
        if not isinstance(info, dict):
            continue
        selected[name] = {
            key: info.get(key)
            for key in ("input", "output", "output_name", "display_name", "name")
            if key in info
        }
    encoded = json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _query_object_info(comfy_url, timeout):
    if not comfy_url:
        return {
            "status": "not_checked",
            "url": None,
            "classes": [],
            "error": "未提供 --comfy-url；generate.py 會在 queue 前重新查詢",
        }
    url = f"{comfy_url}/object_info"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except Exception as exc:
        return {
            "status": "not_checked",
            "url": url,
            "classes": [],
            "error": str(exc),
        }
    if not isinstance(payload, dict):
        return {
            "status": "error",
            "url": url,
            "classes": [],
            "error": "ComfyUI /object_info 回應不是 JSON object",
        }
    classes = sorted(str(name) for name in payload)
    return {
        "status": "available",
        "url": url,
        "classes": classes,
        "schema_fingerprint": _schema_fingerprint(payload, classes),
        "error": None,
    }


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _model_entry(backend, key, filename, model_roots, include_hash=False):
    directory = MODEL_DIRECTORIES[backend][key]
    candidates = [os.path.abspath(os.path.join(root, directory, filename)) for root in model_roots]
    present_path = next((path for path in candidates if os.path.isfile(path)), None)
    path = present_path or (candidates[0] if candidates else None)
    return {
        "file": filename,
        "directory": directory,
        "path": path,
        "present": bool(present_path),
        "size_bytes": os.path.getsize(present_path) if present_path else None,
        # Large model hashes can take minutes; only calculate when the
        # operator explicitly requests --hash-models.
        "sha256": _sha256_file(present_path) if present_path and include_hash else None,
    }


def _required_nodes(spec, capability, control_type=None, catalog=None):
    nodes = list(spec.get("required_nodes", {}).get(capability, ()))
    if capability == "control_video" and control_type and catalog is not None:
        nodes.append(catalog.VIDEO_CONTROL_NODES[control_type])
    return tuple(dict.fromkeys(nodes))


def _runtime_is_usable(runtime, device_config):
    if not all(runtime.get(key) for key in ("python", "pillow", "torch", "pyav")):
        return False
    if isinstance(device_config, dict) and device_config.get("backend") == "cuda":
        return runtime.get("torch_cuda") is True
    return True


def detect(args):
    catalog = _load_generate_catalog()
    comfyui_path = os.path.abspath(os.fspath(args.comfyui_path))
    python_exe = os.path.abspath(os.fspath(args.python_exe or _default_python(comfyui_path)))
    if not os.path.isfile(python_exe):
        raise RuntimeError(f"找不到影片 runtime Python: {python_exe}")

    model_roots = [os.path.abspath(os.fspath(root)) for root in (args.model_root or [])]
    if not model_roots:
        model_roots = [os.path.join(comfyui_path, "models")]
    device_config_path = os.path.abspath(
        os.fspath(args.device_config or os.path.join(comfyui_path, "tools", "device_config.json"))
    )
    device_config = _read_json(device_config_path, "device_config")
    runtime = _runtime_probe(python_exe)
    node_check = _query_object_info(_normalise_url(args.comfy_url), args.http_timeout)
    object_classes = set(node_check.get("classes", ())) if node_check.get("status") == "available" else None
    runtime_usable = _runtime_is_usable(runtime, device_config)

    backends = {}
    for backend, implementation in catalog.VIDEO_BACKEND_SPECS.items():
        models = {
            key: _model_entry(
                backend, key, filename, model_roots,
                include_hash=bool(getattr(args, "hash_models", False)),
            )
            for key, filename in implementation["models"].items()
        }
        capabilities = []
        reasons = {}
        for capability in implementation["capabilities"]:
            required_models = implementation["required_models"].get(capability, ())
            missing_models = [key for key in required_models if not models[key]["present"]]
            required_nodes = _required_nodes(implementation, capability, args.control_type, catalog)
            missing_nodes = sorted(set(required_nodes) - object_classes) if object_classes is not None else []
            if missing_models:
                reasons[capability] = {"missing_models": missing_models}
                continue
            if not runtime_usable:
                reasons[capability] = {"runtime": "Pillow/Torch/PyAV 或 CUDA 不可用"}
                continue
            if object_classes is not None and missing_nodes:
                reasons[capability] = {"missing_nodes": missing_nodes}
                continue
            capabilities.append(capability)
        backends[backend] = {
            "available": bool(capabilities),
            "capabilities": sorted(capabilities),
            "models": models,
            "required_nodes": {
                capability: list(nodes)
                for capability, nodes in implementation["required_nodes"].items()
            },
            "reasons": reasons,
        }

    default_backend = args.default_backend
    if default_backend and not backends[default_backend]["available"]:
        raise RuntimeError(
            f"指定的 default backend {default_backend!r} 在這台機器不可用；"
            f"請先補齊模型/runtime/node，或不要設定 default_backend。"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "machine": platform.node() or None,
        "comfyui_path": comfyui_path,
        "python_exe": python_exe,
        "model_roots": model_roots,
        "device_config_path": device_config_path,
        "device_config": device_config,
        "runtime": {
            key: runtime.get(key)
            for key in ("python", "pillow", "torch", "pyav")
        },
        "runtime_probe": runtime,
        "node_check": node_check,
        "default_backend": default_backend,
        "tasks": {
            task: list(dict.fromkeys([catalog.VIDEO_TASK_CAPS[task], *catalog.VIDEO_TASK_EXTRA_CAPS.get(task, ())]))
            for task in catalog.VIDEO_TASK_CAPS
        },
        "backends": backends,
    }


def write_config(path, config, allow_overwrite=False):
    path = os.path.abspath(os.fspath(path))
    if os.path.lexists(path) and not allow_overwrite:
        raise RuntimeError(
            f"拒絕覆寫既有影片 capability config: {path}；需要明確給 --overwrite"
        )
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=os.path.dirname(path) or ".")
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
        description="偵測已安裝的 ComfyUI 影片 backend/capability；不下載模型或套件。"
    )
    parser.add_argument("--comfyui-path", required=True, help="ComfyUI 安裝根目錄")
    parser.add_argument("--python-exe", help="影片 runtime Python；預設使用 ComfyUI/.venv")
    parser.add_argument("--model-root", action="append", help="models 根目錄，可重複指定")
    parser.add_argument("--device-config", help="device_config.json 路徑")
    parser.add_argument("--comfy-url", help="可選；若 ComfyUI 正在執行則檢查 /object_info")
    parser.add_argument("--http-timeout", type=float, default=10.0)
    parser.add_argument(
        "--default-backend", choices=["h3", "wan"],
        help="明確寫入 machine config 的預設後端；不給就保持 null，CLI 必須明確給 --backend",
    )
    parser.add_argument("--control-type", choices=["canny", "pose", "depth"], default="pose")
    parser.add_argument(
        "--out", help="輸出 JSON 路徑；預設 <ComfyUI>/tools/video_capabilities.json"
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="明確允許更新既有 capability config",
    )
    parser.add_argument(
        "--hash-models", action="store_true",
        help="明確要求計算已存在模型 SHA-256；大型模型可能耗時，預設只記錄 size_bytes",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.http_timeout <= 0:
        parser.error("--http-timeout 必須是正數")
    try:
        config = detect(args)
        out = args.out or os.path.join(os.path.abspath(args.comfyui_path), "tools", "video_capabilities.json")
        path = write_config(out, config, allow_overwrite=args.overwrite)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    summary = {
        "path": path,
        "machine": config["machine"],
        "default_backend": config["default_backend"],
        "node_check": config["node_check"]["status"],
        "runtime": config["runtime"],
        "backends": {
            name: {
                "available": spec["available"],
                "capabilities": spec["capabilities"],
            }
            for name, spec in config["backends"].items()
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
