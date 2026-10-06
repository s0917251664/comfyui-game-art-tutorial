"""影片 capability 設定:載入/正規化 video_capabilities.json、模型與 node 預檢、backend 選擇。

從 generate.py 抽出;``ACTIVE_VIDEO_CONFIG`` 仍是 generate 模組上的狀態,這裡透過 ``runtime.facade`` 讀寫。
"""
import os
import re
import sys

from . import video_catalog as _video_catalog
from .client import (
    DEFAULT_HTTP_TIMEOUT, _read_runtime_config, _relative_config_path, _runtime_config_path_from_env,
)
from .runtime import facade as rt
from .video_catalog import (
    VIDEO_BACKEND_CAPS, VIDEO_BACKEND_SPECS, VIDEO_BACKENDS, VIDEO_CAPABILITY_CONFIG_ENV_VARS,
    VIDEO_CAPABILITY_CONFIG_FILENAME, VIDEO_CAPABILITY_SCHEMA_VERSION, VIDEO_CONTROL_NODES,
    VIDEO_TASK_CAPS, VIDEO_TASK_EXTRA_CAPS, VIDEO_TASKS,
)


def _video_task_capabilities(task):
    """Return every capability required by a task, without choosing a backend."""
    if task not in VIDEO_TASKS:
        return ()
    required = [VIDEO_TASK_CAPS[task], *VIDEO_TASK_EXTRA_CAPS.get(task, ())]
    return tuple(dict.fromkeys(required))


def _normalise_video_capabilities(raw, source):
    if not isinstance(raw, dict):
        raise RuntimeError(f"影片 capability config 必須是 JSON object: {source}")
    version = raw.get("schema_version", raw.get("version"))
    if version != VIDEO_CAPABILITY_SCHEMA_VERSION:
        raise RuntimeError(
            f"影片 capability config 版本不支援: {version!r}；"
            f"需要 {VIDEO_CAPABILITY_SCHEMA_VERSION}: {source}"
        )
    backends = raw.get("backends")
    if not isinstance(backends, dict) or not backends:
        raise RuntimeError(f"影片 capability config 缺少 backends: {source}")
    node_check = raw.get("node_check")
    if node_check is not None:
        if not isinstance(node_check, dict):
            raise RuntimeError(f"影片 capability config 的 node_check 必須是 JSON object: {source}")
        fingerprint = node_check.get("schema_fingerprint")
        if fingerprint is not None and (
                not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", fingerprint)):
            raise RuntimeError(f"影片 capability config 的 schema_fingerprint 無效: {source}")
    for backend, spec in backends.items():
        if backend not in VIDEO_BACKEND_SPECS:
            raise RuntimeError(f"影片 capability config 有未知 backend {backend!r}: {source}")
        if not isinstance(spec, dict):
            raise RuntimeError(f"backend {backend!r} 的設定必須是 JSON object: {source}")
        capabilities = spec.get("capabilities")
        if not isinstance(capabilities, (list, tuple, set)):
            raise RuntimeError(f"backend {backend!r} 缺少 capabilities 清單: {source}")
        if any(not isinstance(cap, str) for cap in capabilities):
            raise RuntimeError(f"backend {backend!r} 的 capabilities 必須是字串: {source}")
        unknown_capabilities = set(capabilities) - set(VIDEO_BACKEND_SPECS[backend]["capabilities"])
        if unknown_capabilities:
            raise RuntimeError(
                f"backend {backend!r} 有未實作 capability: "
                f"{', '.join(sorted(unknown_capabilities))}: {source}"
            )
        models = spec.get("models")
        if not isinstance(models, dict):
            raise RuntimeError(f"backend {backend!r} 缺少 models 設定: {source}")
        for model_key, entry in models.items():
            if isinstance(entry, dict) and entry.get("size_bytes") is not None:
                size = entry.get("size_bytes")
                if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                    raise RuntimeError(
                        f"backend {backend!r} model {model_key!r} 的 size_bytes 無效: {source}"
                    )
    default_backend = raw.get("default_backend")
    if default_backend is not None and default_backend not in backends:
        raise RuntimeError(
            f"影片 capability config 的 default_backend={default_backend!r} 不在 backends: {source}"
        )
    config = dict(raw)
    config["_source"] = source
    config["backends"] = {
        backend: dict(spec) for backend, spec in backends.items()
    }
    return config


def load_video_capabilities(runtime_config_path=None, video_config_path=None):
    """Load a machine-specific video capability config; never invent a backend.

    ``--config`` remains the runtime config containing ``comfyui_url``. It may
    point at a separate ``video_config``/``video_capabilities`` JSON path or an
    inline object. For an installed ComfyUI, the conventional sibling file
    ``<comfyui>/tools/video_capabilities.json`` is accepted when the runtime
    config contains ``comfyui_path`` or ``generate_script``. There is no
    implicit repository-local config lookup because the deployed script is
    commonly executed from a different machine and working directory.
    """
    explicit = video_config_path or next(
        (os.environ.get(name) for name in VIDEO_CAPABILITY_CONFIG_ENV_VARS if os.environ.get(name)),
        None,
    )
    raw = None
    source = None
    if explicit:
        source = os.path.abspath(os.fspath(explicit))
        raw = _read_runtime_config(source)
    else:
        runtime_path = _runtime_config_path_from_env(runtime_config_path)
        if runtime_path:
            runtime_path = os.path.abspath(os.fspath(runtime_path))
            runtime = _read_runtime_config(runtime_path)
            for key in ("video_config", "video_capabilities"):
                candidate = runtime.get(key)
                if isinstance(candidate, dict):
                    raw, source = candidate, f"{runtime_path}:{key}"
                    break
                if candidate:
                    source = _relative_config_path(candidate, runtime_path)
                    raw = _read_runtime_config(source)
                    break
            if raw is None:
                roots = []
                for key in ("comfyui_path", "generate_script"):
                    value = runtime.get(key)
                    if value:
                        root = os.fspath(value)
                        if key == "generate_script":
                            root = os.path.dirname(root)
                        roots.append(os.path.join(root, VIDEO_CAPABILITY_CONFIG_FILENAME))
                existing = next((path for path in roots if os.path.isfile(path)), None)
                if existing:
                    source = os.path.abspath(existing)
                    raw = _read_runtime_config(source)
        if raw is None:
            raise RuntimeError(
                "未設定影片 capability config；請使用 --video-config/VIDEO_CONFIG，"
                "或在 --config JSON 內指定 video_config。影片不會猜測 H3/Wan。"
            )
    return _normalise_video_capabilities(raw, source)


def _configured_backend_spec(config, backend):
    spec = config.get("backends", {}).get(backend)
    if not isinstance(spec, dict):
        raise RuntimeError(
            f"影片 capability config 沒有 backend {backend!r}；"
            f"可用設定: {', '.join(sorted(config.get('backends', {}))) or '無'}"
        )
    if spec.get("available") is False or spec.get("enabled") is False:
        reason = spec.get("reason") or "設定標示為不可用"
        raise RuntimeError(f"影片 backend {backend} 不可用: {reason}")
    return spec


def _configured_capabilities(config, backend):
    spec = _configured_backend_spec(config, backend)
    return set(spec.get("capabilities", ()))


def _video_model_file_name(backend, model_key):
    """Resolve the graph-visible model name from the active machine config."""
    if rt.ACTIVE_VIDEO_CONFIG is None:
        try:
            return VIDEO_BACKEND_SPECS[backend]["models"][model_key]
        except KeyError as exc:
            raise RuntimeError(f"內建影片 backend {backend!r} 缺少模型欄位 {model_key!r}") from exc
    spec = _configured_backend_spec(rt.ACTIVE_VIDEO_CONFIG, backend)
    entry = spec.get("models", {}).get(model_key)
    if isinstance(entry, str):
        name = entry
    elif isinstance(entry, dict):
        name = entry.get("file") or entry.get("name")
    else:
        name = None
    if not name:
        raise RuntimeError(
            f"影片 capability config 的 backend {backend!r} 缺少 graph 模型欄位 {model_key!r}"
        )
    return os.fspath(name)


def _video_model_roots(config):
    roots = config.get("model_roots")
    if isinstance(roots, str):
        roots = [roots]
    if not isinstance(roots, (list, tuple)):
        roots = []
    roots = [os.fspath(root) for root in roots if root]
    if not roots:
        comfyui_path = config.get("comfyui_path")
        if comfyui_path:
            roots = [os.path.join(os.fspath(comfyui_path), "models")]
    return roots


def _video_model_path(config, entry):
    if isinstance(entry, str):
        filename = entry
        directory = None
        explicit_path = None
    elif isinstance(entry, dict):
        filename = entry.get("file") or entry.get("name")
        directory = entry.get("directory")
        explicit_path = entry.get("path")
    else:
        filename = directory = explicit_path = None
    if explicit_path:
        path = os.fspath(explicit_path)
        if not os.path.isabs(path):
            source = config.get("_source")
            path = _relative_config_path(path, source) if source and os.path.isfile(source) else os.path.abspath(path)
        return path
    if not filename:
        return None
    roots = _video_model_roots(config)
    candidates = []
    for root in roots:
        candidates.append(os.path.join(root, os.fspath(directory), os.fspath(filename)) if directory else os.path.join(root, os.fspath(filename)))
    return next((path for path in candidates if os.path.isfile(path)), candidates[0] if candidates else None)


def _required_video_model_keys(backend, capabilities):
    spec = VIDEO_BACKEND_SPECS[backend]
    keys = []
    for capability in capabilities:
        keys.extend(spec["required_models"].get(capability, ()))
    return tuple(dict.fromkeys(keys))


def _validate_video_models(config, backend, capabilities):
    spec = _configured_backend_spec(config, backend)
    missing = []
    for key in _required_video_model_keys(backend, capabilities):
        entry = spec.get("models", {}).get(key)
        path = _video_model_path(config, entry)
        if not path or not os.path.isfile(path):
            shown = path or repr(entry)
            missing.append(f"{key}={shown}")
            continue
        expected_size = entry.get("size_bytes") if isinstance(entry, dict) else None
        if expected_size is not None:
            actual_size = os.path.getsize(path)
            if actual_size != expected_size:
                missing.append(
                    f"{key}={path} (size_bytes config={expected_size}, actual={actual_size})"
                )
    if missing:
        raise RuntimeError(
            f"影片 backend {backend} 缺少必要模型，已在 upload/queue 前停止: "
            + "; ".join(missing)
            + f"；config={config.get('_source')}"
        )


def _required_video_nodes(backend, capabilities, config, control_type=None):
    builtin = VIDEO_BACKEND_SPECS[backend]["required_nodes"]
    spec = _configured_backend_spec(config, backend)
    configured = spec.get("required_nodes")
    if not isinstance(configured, dict):
        configured = builtin
    nodes = []
    # The graph builder is the source of truth for task shape: I2V/last-frame
    # uses the I2V sampler, character_ref uses the reference sampler, and
    # control_video uses the control sampler. Do not validate unrelated graph
    # nodes just because they belong to the same backend.
    graph_capability = "i2v" if "i2v" in capabilities else None
    if graph_capability is None and "last_frame" in capabilities:
        graph_capability = "last_frame"
    if graph_capability is None and "character_ref" in capabilities:
        graph_capability = "character_ref"
    if graph_capability is None and "control_video" in capabilities:
        graph_capability = "control_video"
    selected = [graph_capability] if graph_capability else []
    for capability in selected:
        values = configured.get(capability, builtin.get(capability, ()))
        if isinstance(values, str):
            values = (values,)
        nodes.extend(values or ())
    if "control_video" in capabilities and control_type:
        nodes.append(VIDEO_CONTROL_NODES[control_type])
    return tuple(dict.fromkeys(node for node in nodes if node))


def _node_schema_fingerprint(payload, required_nodes=None):
    return _video_catalog.node_schema_fingerprint(payload, required_nodes)


def validate_comfy_video_nodes(comfy_url, required_nodes, request_timeout=DEFAULT_HTTP_TIMEOUT,
                               expected_schema_fingerprint=None):
    required = tuple(dict.fromkeys(required_nodes))
    payload = rt._fetch_comfy_object_info(comfy_url, request_timeout=request_timeout)
    available = set(payload)
    missing = sorted(set(required) - available)
    if missing:
        raise RuntimeError(
            "ComfyUI 缺少影片 graph 必要 nodes，已在 upload/queue 前停止: "
            + ", ".join(missing)
        )
    if expected_schema_fingerprint:
        actual = _node_schema_fingerprint(payload)
        if actual != expected_schema_fingerprint:
            raise RuntimeError(
                "ComfyUI 影片依賴 node input schema fingerprint 不一致，"
                f"config={expected_schema_fingerprint}, actual={actual}；已停止"
            )
    return available


def _runtime_versions_for_video():
    versions = {"python": ".".join(str(part) for part in sys.version_info[:3])}
    if rt.PILImage is None:
        raise RuntimeError("影片 task 需要 Pillow，但目前執行 Python 沒有 Pillow")
    try:
        import PIL
    except ImportError as exc:
        raise RuntimeError("影片 task 需要 Pillow，但目前執行 Python 無法 import PIL") from exc
    versions["pillow"] = getattr(PIL, "__version__", None)
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("影片 task 需要目前 ComfyUI Python 的 PyTorch runtime") from exc
    versions["torch"] = getattr(torch, "__version__", None)
    try:
        import av
    except ImportError as exc:
        raise RuntimeError("影片 task 需要 PyAV 以驗證輸出 FPS/幀數/音訊") from exc
    versions["pyav"] = getattr(av, "__version__", None)
    return versions, torch


def validate_video_runtime(config):
    actual, torch = _runtime_versions_for_video()
    expected = config.get("runtime")
    if isinstance(expected, dict):
        mismatches = []
        for key, expected_value in expected.items():
            if expected_value in (None, "", "pending"):
                continue
            if isinstance(expected_value, dict):
                expected_value = expected_value.get("version")
            if expected_value and str(actual.get(key)) != str(expected_value):
                mismatches.append(f"{key}: config={expected_value!r}, actual={actual.get(key)!r}")
        if mismatches:
            raise RuntimeError(
                "影片 runtime 與 capability config 不一致，已在 upload/queue 前停止: "
                + "; ".join(mismatches)
            )
    device = config.get("device_config")
    if isinstance(device, dict) and device.get("backend") == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("capability config 要求 CUDA，但目前 PyTorch 看不到 CUDA")
        expected_gpu = device.get("gpu_name")
        if expected_gpu:
            actual_gpu = torch.cuda.get_device_name(0)
            if actual_gpu != expected_gpu:
                raise RuntimeError(
                    f"capability config 要求 GPU {expected_gpu!r}，目前是 {actual_gpu!r}；"
                    "影片模型不會跨 GPU 靜默切換"
                )
    return actual


def configure_video_capability(task, requested_backend=None, runtime_config_path=None,
                               video_config_path=None, comfy_url=None,
                               request_timeout=DEFAULT_HTTP_TIMEOUT, control_type=None):
    """Select and validate one configured backend before any input upload."""
    config = load_video_capabilities(runtime_config_path, video_config_path)
    backend = requested_backend or config.get("default_backend")
    if not backend:
        raise RuntimeError(
            f"影片 task {task} 沒有 backend 選擇；請明確給 --backend，"
            "或在 capability config 設定 default_backend。"
        )
    if backend not in VIDEO_BACKEND_SPECS:
        raise RuntimeError(f"未知影片 backend {backend!r}；可用: {', '.join(VIDEO_BACKENDS)}")
    configured = _configured_capabilities(config, backend)
    required = _video_task_capabilities(task)
    missing_caps = [cap for cap in required if cap not in configured]
    if missing_caps:
        raise RuntimeError(
            f"task {task} 在 backend {backend} 沒有完整 capability: "
            f"缺 {', '.join(missing_caps)}；不會靜默改用另一個 backend"
        )
    rt.validate_video_runtime(config)
    _validate_video_models(config, backend, required)
    if not comfy_url:
        raise RuntimeError("影片生成需要 ComfyUI URL 以驗證 /object_info")
    nodes = _required_video_nodes(backend, required, config, control_type=control_type)
    expected_fingerprint = None
    node_check = config.get("node_check")
    if isinstance(node_check, dict):
        expected_fingerprint = node_check.get("schema_fingerprint")
    rt.validate_comfy_video_nodes(
        comfy_url, nodes, request_timeout=request_timeout,
        expected_schema_fingerprint=expected_fingerprint,
    )
    rt.ACTIVE_VIDEO_CONFIG = config
    return backend


def backend_has(backend, cap, capability_config=None):
    config = capability_config or rt.ACTIVE_VIDEO_CONFIG
    if config is not None:
        try:
            return cap in _configured_capabilities(config, backend)
        except RuntimeError:
            return False
    return cap in VIDEO_BACKEND_CAPS.get(backend, ())


def require_video_backend(task, backend, capability_config=None):
    """確認 task/backend 組合已實作，未支援時直接 fail-fast。

    backend 是 task 的明確實作選擇；不能從 process-wide ``sys.argv`` 猜測
    呼叫端是否指定過它，也不能在未支援時靜默改走另一個 backend。
    """
    if not backend:
        raise SystemExit(
            f"{task} 沒有選定影片 backend；請明確給 --backend，"
            "或在 machine capability config 設定 default_backend。"
        )
    if backend not in VIDEO_BACKENDS:
        raise SystemExit(f"未知 --backend {backend!r},可用: {', '.join(VIDEO_BACKENDS)}")
    needs = _video_task_capabilities(task)
    if capability_config is None:
        available = set(VIDEO_BACKEND_CAPS.get(backend, ()))
        ok = [b for b, caps in VIDEO_BACKEND_CAPS.items() if all(cap in caps for cap in needs)]
    else:
        available = _configured_capabilities(capability_config, backend)
        ok = [
            b for b in capability_config.get("backends", {})
            if all(cap in _configured_capabilities(capability_config, b) for cap in needs)
        ]
    missing = [cap for cap in needs if cap not in available]
    if missing:
        raise SystemExit(
            f"{task} 目前沒有 {backend} 實作(缺 {', '.join(missing)})。"
            f"可用: {', '.join(ok) or '無'}。"
            f"不要因此改 task 名稱;接上這個 backend 之後同一個 CLI 就能跑。"
        )
    return backend
