"""
穩定產圖核心腳本(不吃自然語言,只吃結構化參數)。

設計原則:
- 每個 task 對應一組鎖死大部分參數的 ComfyUI graph,只有明確列出的欄位可調
- 不靠 LLM 每次臨場組 JSON,參數集固定、行為可預期、可重複
- 上層(Skill/agent)的工作只是把自然語言整理成這裡要的結構化參數,不做生成邏輯本身

Usage:
    python generate.py --config local_config.json concept --prompt "a female game character concept art, fantasy armor" [--negative ...] [--seed N] [--width 1024] [--height 1024] [--remove-bg]
    python generate.py --config local_config.json flux2_concept --prompt "a readable game item concept" [--seed N] [--width 1024] [--height 1024]
    python generate.py --config local_config.json flux2_edit --prompt "turn the armor silver" --image path.png [--seed N]
    python generate.py --comfy-url http://127.0.0.1:8188 character_action --prompt "..." --character-ref path.png --pose-ref path.png [--pose-strength 1.0] [--remove-bg]
    python generate.py --config local_config.json inpaint --prompt "..." --image path.png --mask path.png [--denoise 1.0]
    python generate.py --config local_config.json img2video --image still.png --prompt "camera locked, idle motion" [--backend h3|wan] [--duration 2] [--timeout 1800]
    python generate.py --comfy-url http://127.0.0.1:8188 character_video --character-ref char.png --prompt "the same character running through a corridor" [--duration 2]
    python generate.py --config local_config.json camera_move --image still.png --camera zoom_in [--duration 2]
    python generate.py --config local_config.json pose_drive --image char.png --motion-ref motion.mp4 --prompt "the character performs the motion"
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
import mimetypes
import ntpath
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

try:
    from PIL import Image as PILImage, ImageDraw, ImageFilter
except ImportError:  # Pillow is only needed by the local template/mask helpers.
    PILImage = None
    ImageDraw = None
    ImageFilter = None

# The deployment copy can live outside this repository.  Do not infer a URL from
# the source tree; callers must provide one explicitly, through the CLI, an
# environment variable, an explicitly named config file, or this compatibility
# override when embedding the module.
COMFY_URL = None
COMFY_URL_ENV_VARS = ("COMFY_URL", "COMFYUI_URL")
COMFY_CONFIG_ENV_VARS = (
    "COMFY_CONFIG", "COMFYUI_CONFIG", "COMFY_CONFIG_PATH", "COMFYUI_CONFIG_PATH",
)
DEFAULT_TIMEOUT = 180.0
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_POLL_TIMEOUT = 15.0
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_POLL_RETRIES = 3
from comfyui_pipeline import image_graphs as _image_graphs
from comfyui_pipeline import video_catalog as _video_catalog
from comfyui_pipeline import video_graphs as _video_graphs

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")
DEFAULT_NEGATIVE = _image_graphs.DEFAULT_NEGATIVE
DEVICE_CONFIG_PATH = _image_graphs.DEVICE_CONFIG_PATH
SDXL_TIERS = _image_graphs.SDXL_TIERS
_require_pillow = _image_graphs._require_pillow
validate_batch = _image_graphs.validate_batch
validate_dimensions = _image_graphs.validate_dimensions
validate_unit_interval = _image_graphs.validate_unit_interval
validate_lora_strength = _image_graphs.validate_lora_strength
validate_scale = _image_graphs.validate_scale
validate_flux2_dimensions = _image_graphs.validate_flux2_dimensions
CONTROLNET_MODELS = _image_graphs.CONTROLNET_MODELS
STYLE_CHECKPOINTS = _image_graphs.STYLE_CHECKPOINTS
RATING_TAGS = _image_graphs.RATING_TAGS
load_device_config = _image_graphs.load_device_config
DEVICE = _image_graphs.DEVICE
CKPT = _image_graphs.CKPT
UPSCALE_MODEL = _image_graphs.UPSCALE_MODEL

def _sync_image_runtime():
    """Keep legacy facade assignments visible to the extracted image module."""
    _image_graphs.DEVICE = DEVICE
    _image_graphs.CKPT = DEVICE.get("checkpoint", CKPT)


def require_sdxl_capability(*args, **kwargs):
    _sync_image_runtime()
    return _image_graphs.require_sdxl_capability(*args, **kwargs)


def _image_builder(name):
    def call(*args, **kwargs):
        _sync_image_runtime()
        return getattr(_image_graphs, name)(*args, **kwargs)
    return call


build_control_preprocessor = _image_builder("build_control_preprocessor")
seed_or_random = _image_builder("seed_or_random")
model_clip_refs = _image_builder("model_clip_refs")
build_concept = _image_builder("build_concept")
build_wheel_segment_template = _image_builder("build_wheel_segment_template")
build_wheel_layer_masks = _image_builder("build_wheel_layer_masks")
build_icon_asset = _image_builder("build_icon_asset")
build_character_action = _image_builder("build_character_action")
build_inpaint = _image_builder("build_inpaint")
build_guided_inpaint = _image_builder("build_guided_inpaint")
build_pose_only = _image_builder("build_pose_only")
build_style_lock = _image_builder("build_style_lock")
build_refine = _image_builder("build_refine")
build_upscale = _image_builder("build_upscale")
build_layer_split = _image_builder("build_layer_split")
attach_bg_removal = _image_builder("attach_bg_removal")
build_flux2_concept = _image_builder("build_flux2_concept")
build_flux2_edit = _image_builder("build_flux2_edit")

CHARACTER_REF_MAX = _video_catalog.CHARACTER_REF_MAX
VIDEO_WAN_UNET = _video_catalog.VIDEO_WAN_UNET
VIDEO_WAN_FUN_UNET = _video_catalog.VIDEO_WAN_FUN_UNET
VIDEO_WAN_CLIP = _video_catalog.VIDEO_WAN_CLIP
VIDEO_WAN_VAE = _video_catalog.VIDEO_WAN_VAE
VIDEO_H3_UNET = _video_catalog.VIDEO_H3_UNET
VIDEO_H3_REF_UNET = _video_catalog.VIDEO_H3_REF_UNET
VIDEO_H3_CLIP = _video_catalog.VIDEO_H3_CLIP
VIDEO_H3_VAE = _video_catalog.VIDEO_H3_VAE
VIDEO_H3_AUDIO_VAE = _video_catalog.VIDEO_H3_AUDIO_VAE
VIDEO_MAX_SIDE = _video_catalog.VIDEO_MAX_SIDE
VIDEO_STEPS = _video_catalog.VIDEO_STEPS
VIDEO_FPS = _video_catalog.VIDEO_FPS
VIDEO_FPS_TOLERANCE = _video_catalog.VIDEO_FPS_TOLERANCE
VIDEO_DURATION_MIN = _video_catalog.VIDEO_DURATION_MIN
VIDEO_DURATION_MAX = _video_catalog.VIDEO_DURATION_MAX
DEFAULT_VIDEO_TIMEOUT = _video_catalog.DEFAULT_VIDEO_TIMEOUT
VIDEO_CAPABILITY_SCHEMA_VERSION = _video_catalog.VIDEO_CAPABILITY_SCHEMA_VERSION
VIDEO_SIDECAR_SCHEMA_VERSION = _video_catalog.VIDEO_SIDECAR_SCHEMA_VERSION
VIDEO_CONTRACT_SCHEMA_VERSION = _video_catalog.VIDEO_CONTRACT_SCHEMA_VERSION
VIDEO_DURATION_TOLERANCE = _video_catalog.VIDEO_DURATION_TOLERANCE
VIDEO_FRAME_TOLERANCE = _video_catalog.VIDEO_FRAME_TOLERANCE
VIDEO_SEAM_WARNING_THRESHOLD = _video_catalog.VIDEO_SEAM_WARNING_THRESHOLD
VIDEO_INPUT_MIN_DURATION = _video_catalog.VIDEO_INPUT_MIN_DURATION
VIDEO_AUDIO_DRIFT_TOLERANCE = _video_catalog.VIDEO_AUDIO_DRIFT_TOLERANCE
VIDEO_CAPABILITY_CONFIG_ENV_VARS = _video_catalog.VIDEO_CAPABILITY_CONFIG_ENV_VARS
VIDEO_CAPABILITY_CONFIG_FILENAME = _video_catalog.VIDEO_CAPABILITY_CONFIG_FILENAME
VIDEO_NEG_DEFAULT = _video_catalog.VIDEO_NEG_DEFAULT
VIDEO_LOOP_SUFFIX = _video_catalog.VIDEO_LOOP_SUFFIX
CAMERA_MOVES = _video_catalog.CAMERA_MOVES
CAMERA_STILL_SUFFIX = _video_catalog.CAMERA_STILL_SUFFIX
CAMERA_ZOOM = _video_catalog.CAMERA_ZOOM
CAMERA_PAN_CROP = _video_catalog.CAMERA_PAN_CROP
VIDEO_BACKEND_SPECS = _video_catalog.VIDEO_BACKEND_SPECS
VIDEO_BACKENDS = _video_catalog.VIDEO_BACKENDS
VIDEO_BACKEND_CAPS = _video_catalog.VIDEO_BACKEND_CAPS
VIDEO_TASK_CAPS = _video_catalog.VIDEO_TASK_CAPS
VIDEO_TASK_EXTRA_CAPS = _video_catalog.VIDEO_TASK_EXTRA_CAPS
VIDEO_CONTROL_NODES = _video_catalog.VIDEO_CONTROL_NODES
VIDEO_TASKS = _video_catalog.VIDEO_TASKS
DEFAULT_VIDEO_BACKEND = _video_catalog.DEFAULT_VIDEO_BACKEND

wan_frame_count = _video_graphs.wan_frame_count
h3_frame_count = _video_graphs.h3_frame_count
camera_move_prompt = _video_graphs.camera_move_prompt
build_camera_end_still = _video_graphs.build_camera_end_still
h3_ref_prompt = _video_graphs.h3_ref_prompt
h3_pose_drive_prompt = _video_graphs.h3_pose_drive_prompt

def _normalise_comfy_url(url):
    """Validate and normalise a ComfyUI base URL without inventing a default."""
    if url is None:
        return None
    value = str(url).strip().rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"ComfyUI URL 必須是完整的 http(s) URL: {url!r}")
    return value


def _read_runtime_config(config_path):
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError as exc:
        raise RuntimeError(f"找不到指定的 runtime config: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"runtime config 不是有效 JSON: {config_path}") from exc
    if not isinstance(config, dict):
        raise RuntimeError(f"runtime config 必須是 JSON object: {config_path}")
    return config


def resolve_comfy_url(cli_url=None, config_path=None):
    """Resolve the ComfyUI URL with CLI > environment > explicit config priority.

    There is deliberately no automatic ``local_config.json`` lookup: a copied
    script must not accidentally connect to a path relative to the source repo.
    """
    for candidate in (cli_url, *(os.environ.get(name) for name in COMFY_URL_ENV_VARS), COMFY_URL):
        if candidate:
            return _normalise_comfy_url(candidate)

    explicit_config = config_path
    if explicit_config is None:
        explicit_config = next((os.environ.get(name) for name in COMFY_CONFIG_ENV_VARS if os.environ.get(name)), None)
    if explicit_config:
        config = _read_runtime_config(explicit_config)
        candidate = config.get("comfyui_url") or config.get("comfy_url")
        if candidate:
            return _normalise_comfy_url(candidate)

    raise RuntimeError(
        "未設定 ComfyUI URL；請使用 --comfy-url、COMFY_URL/COMFYUI_URL，"
        "或透過 --config/COMFY_CONFIG 指定含 comfyui_url 的 JSON。"
    )


def _comfy_endpoint(path, comfy_url=None):
    base = _normalise_comfy_url(comfy_url) if comfy_url else resolve_comfy_url()
    return f"{base}/{path.lstrip('/')}"


def validate_timeout(timeout):
    try:
        number = float(timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"timeout 必須是正數，目前是 {timeout!r}") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"timeout 必須是正數，目前是 {timeout!r}")
    return timeout



class VideoContractError(RuntimeError):
    """An output was decoded but did not satisfy the caller's video contract."""

    def __init__(self, message, metadata=None, errors=None, warnings=None):
        super().__init__(message)
        self.metadata = metadata
        self.errors = list(errors or ())
        self.warnings = list(warnings or ())


class VideoTimeoutError(TimeoutError):
    """Timeout carrying the exact ComfyUI prompt ownership information."""

    def __init__(self, message, prompt_id, queue_status=None):
        super().__init__(message)
        self.prompt_id = str(prompt_id)
        self.queue_status = queue_status or {"status": "unknown"}




def _video_task_capabilities(task):
    """Return every capability required by a task, without choosing a backend."""
    if task not in VIDEO_TASKS:
        return ()
    required = [VIDEO_TASK_CAPS[task], *VIDEO_TASK_EXTRA_CAPS.get(task, ())]
    return tuple(dict.fromkeys(required))


def _runtime_config_path_from_env(explicit_path=None):
    if explicit_path:
        return os.fspath(explicit_path)
    return next(
        (os.environ.get(name) for name in COMFY_CONFIG_ENV_VARS if os.environ.get(name)),
        None,
    )


def _relative_config_path(value, base_path):
    value = os.fspath(value)
    if os.path.isabs(value):
        return value
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(base_path)), value))


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
    if ACTIVE_VIDEO_CONFIG is None:
        try:
            return VIDEO_BACKEND_SPECS[backend]["models"][model_key]
        except KeyError as exc:
            raise RuntimeError(f"內建影片 backend {backend!r} 缺少模型欄位 {model_key!r}") from exc
    spec = _configured_backend_spec(ACTIVE_VIDEO_CONFIG, backend)
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
    """Digest only the node input/output schemas used by this video pipeline."""
    if not isinstance(payload, dict):
        raise ValueError("ComfyUI /object_info 回應不是 JSON object")
    names = sorted(required_nodes or payload)
    selected = {}
    for name in names:
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


def _fetch_comfy_object_info(comfy_url, request_timeout=DEFAULT_HTTP_TIMEOUT):
    req = urllib.request.Request(_comfy_endpoint("object_info", comfy_url))
    try:
        with urllib.request.urlopen(req, timeout=request_timeout) as response:
            payload = json.loads(response.read().decode())
    except Exception as exc:
        raise RuntimeError(
            f"無法在 upload/queue 前查詢 ComfyUI /object_info: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("ComfyUI /object_info 回應不是 JSON object，已停止影片 task")
    return payload


FLUX2_REQUIRED_NODES = (
    "UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode",
    "EmptyFlux2LatentImage", "RandomNoise", "CFGGuider", "KSamplerSelect",
    "Flux2Scheduler", "SamplerCustomAdvanced", "VAEDecode", "SaveImage",
)
FLUX2_EDIT_REQUIRED_NODES = (
    "LoadImage", "ImageScaleToTotalPixels", "GetImageSize", "VAEEncode", "ReferenceLatent",
)


def _node_combo_values(payload, node_name, input_name):
    try:
        spec = payload[node_name]["input"]["required"][input_name]
        values = spec[0]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"ComfyUI node schema 缺少 {node_name}.{input_name}，已停止 FLUX.2 task"
        ) from exc
    if not isinstance(values, list):
        raise RuntimeError(
            f"ComfyUI node schema 的 {node_name}.{input_name} 不是 model combo，已停止 FLUX.2 task"
        )
    return values


def validate_flux2_capability(task, comfy_url, request_timeout=DEFAULT_HTTP_TIMEOUT):
    """Fail before image upload/queue when FLUX.2 nodes or models are absent."""
    required = list(FLUX2_REQUIRED_NODES)
    if task == "flux2_edit":
        required.extend(FLUX2_EDIT_REQUIRED_NODES)
    payload = _fetch_comfy_object_info(comfy_url, request_timeout=request_timeout)
    missing_nodes = sorted(set(required) - set(payload))
    if missing_nodes:
        raise RuntimeError(
            "ComfyUI 缺少 FLUX.2 graph 必要 nodes，已在 upload/queue 前停止: "
            + ", ".join(missing_nodes)
        )
    required_unet = (
        _image_graphs.FLUX2_BASE_UNET if task == "flux2_edit"
        else _image_graphs.FLUX2_DISTILLED_UNET
    )
    checks = (
        ("UNETLoader", "unet_name", required_unet),
        ("CLIPLoader", "clip_name", _image_graphs.FLUX2_CLIP),
        ("VAELoader", "vae_name", _image_graphs.FLUX2_VAE),
    )
    missing_models = [
        filename
        for node_name, input_name, filename in checks
        if filename not in _node_combo_values(payload, node_name, input_name)
    ]
    if missing_models:
        raise RuntimeError(
            "ComfyUI 缺少 FLUX.2 模型，已在 upload/queue 前停止: "
            + ", ".join(missing_models)
        )
    return True


def validate_controlnet_union_capability(comfy_url, request_timeout=DEFAULT_HTTP_TIMEOUT):
    """Fail before reference upload when the experimental Union path is absent."""
    payload = _fetch_comfy_object_info(comfy_url, request_timeout=request_timeout)
    required_nodes = {"ControlNetLoader", "SetUnionControlNetType"}
    missing_nodes = sorted(required_nodes - set(payload))
    if missing_nodes:
        raise RuntimeError(
            "ComfyUI 缺少 ControlNet Union 必要 nodes，已在 upload/queue 前停止: "
            + ", ".join(missing_nodes)
        )
    models = _node_combo_values(payload, "ControlNetLoader", "control_net_name")
    if _image_graphs.CONTROLNET_UNION_MODEL not in models:
        raise RuntimeError(
            "ComfyUI 缺少 ControlNet Union 模型，已在 upload/queue 前停止: "
            + _image_graphs.CONTROLNET_UNION_MODEL
        )
    return True


def validate_comfy_video_nodes(comfy_url, required_nodes, request_timeout=DEFAULT_HTTP_TIMEOUT,
                               expected_schema_fingerprint=None):
    required = tuple(dict.fromkeys(required_nodes))
    payload = _fetch_comfy_object_info(comfy_url, request_timeout=request_timeout)
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
    if PILImage is None:
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
    global ACTIVE_VIDEO_CONFIG
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
    validate_video_runtime(config)
    _validate_video_models(config, backend, required)
    if not comfy_url:
        raise RuntimeError("影片生成需要 ComfyUI URL 以驗證 /object_info")
    nodes = _required_video_nodes(backend, required, config, control_type=control_type)
    expected_fingerprint = None
    node_check = config.get("node_check")
    if isinstance(node_check, dict):
        expected_fingerprint = node_check.get("schema_fingerprint")
    validate_comfy_video_nodes(
        comfy_url, nodes, request_timeout=request_timeout,
        expected_schema_fingerprint=expected_fingerprint,
    )
    ACTIVE_VIDEO_CONFIG = config
    return backend


def upload_image(path, comfy_url=None, request_timeout=DEFAULT_HTTP_TIMEOUT):
    """上傳本機圖片或影片到 ComfyUI input，回傳 LoadImage/LoadVideo 使用的檔名。"""
    validate_timeout(request_timeout)
    filename = os.path.basename(path)
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        _comfy_endpoint("upload/image", comfy_url),
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = urllib.request.urlopen(req, timeout=request_timeout)
    result = json.loads(resp.read().decode())
    try:
        return result["name"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("ComfyUI upload 回應缺少 name") from exc


def _is_transient_poll_error(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (408, 425, 429, 500, 502, 503, 504)
    return isinstance(exc, (urllib.error.URLError, TimeoutError, OSError))


def _poll_error_text(exc):
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read().decode(errors="replace")
        except Exception:
            body = ""
        return f"HTTP {exc.code}" + (f": {body}" if body else "")
    return str(exc) or exc.__class__.__name__


def _query_prompt_queue_status(prompt_id, comfy_url, request_timeout):
    """Best-effort exact ownership lookup; never calls global /interrupt."""
    try:
        req = urllib.request.Request(_comfy_endpoint("queue", comfy_url))
        with urllib.request.urlopen(req, timeout=request_timeout) as response:
            payload = json.loads(response.read().decode())
        if not isinstance(payload, dict):
            return {"status": "unknown", "reason": "queue response was not an object"}
        for status_name in ("queue_pending", "queue_running"):
            entries = payload.get(status_name) or []
            for entry in entries:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    candidate = entry[1] if isinstance(entry[1], str) else entry[0]
                elif isinstance(entry, dict):
                    candidate = entry.get("prompt_id")
                else:
                    candidate = None
                if str(candidate) == str(prompt_id):
                    return {"status": "pending" if status_name == "queue_pending" else "running"}
        return {"status": "not-owned-or-finished"}
    except Exception as exc:
        return {"status": "unknown", "reason": _poll_error_text(exc)}


def _cancel_exact_pending_prompt(prompt_id, comfy_url, request_timeout, queue_status):
    """Use ComfyUI's exact queue deletion only after confirming pending ownership."""
    if not isinstance(queue_status, dict) or queue_status.get("status") != "pending":
        return queue_status
    payload = json.dumps({"delete": [str(prompt_id)]}).encode("utf-8")
    req = urllib.request.Request(
        _comfy_endpoint("queue", comfy_url), data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=request_timeout) as response:
            response.read()
        return {**queue_status, "cancel_attempted": True, "cancelled_prompt_id": str(prompt_id)}
    except Exception as exc:
        return {**queue_status, "cancel_attempted": True, "cancel_error": _poll_error_text(exc)}


def submit_and_wait(prompt, timeout=DEFAULT_TIMEOUT, comfy_url=None,
                    poll_interval=DEFAULT_POLL_INTERVAL, max_poll_retries=DEFAULT_POLL_RETRIES):
    """Queue a prompt and poll history, retaining prompt_id in every terminal error."""
    validate_timeout(timeout)
    validate_timeout(poll_interval if poll_interval else 0.000001)
    if isinstance(max_poll_retries, bool) or not isinstance(max_poll_retries, int) or max_poll_retries < 0:
        raise ValueError(f"max_poll_retries 必須是 0 以上的整數，目前是 {max_poll_retries!r}")

    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        _comfy_endpoint("prompt", comfy_url), data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=min(DEFAULT_HTTP_TIMEOUT, float(timeout)))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"送出失敗: {e.code} {e.read().decode(errors='replace')}") from e

    try:
        result = json.loads(resp.read().decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("ComfyUI queue 回應不是有效 JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("ComfyUI queue 回應必須是 JSON object")
    if result.get("node_errors"):
        raise RuntimeError(f"節點參數錯誤: {json.dumps(result['node_errors'], ensure_ascii=False)}")
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise RuntimeError("ComfyUI 回應缺少 prompt_id")

    start = time.monotonic()
    transient_failures = 0
    while time.monotonic() - start < float(timeout):
        remaining = float(timeout) - (time.monotonic() - start)
        poll_timeout = min(DEFAULT_POLL_TIMEOUT, max(0.001, remaining))
        try:
            hist_req = urllib.request.urlopen(
                _comfy_endpoint(f"history/{urllib.parse.quote(str(prompt_id), safe='')}", comfy_url),
                timeout=poll_timeout,
            )
            history = json.loads(hist_req.read().decode())
        except Exception as exc:
            if not _is_transient_poll_error(exc):
                raise RuntimeError(f"輪詢生成狀態失敗: {_poll_error_text(exc)}, prompt_id={prompt_id}") from exc
            transient_failures += 1
            if transient_failures > max_poll_retries:
                raise RuntimeError(
                    f"輪詢生成狀態暫時失敗，已重試 {max_poll_retries} 次: "
                    f"{_poll_error_text(exc)}, prompt_id={prompt_id}"
                ) from exc
            remaining = float(timeout) - (time.monotonic() - start)
            if remaining <= 0:
                break
            backoff = min(float(poll_interval) * (2 ** (transient_failures - 1)), remaining)
            time.sleep(backoff)
            continue

        transient_failures = 0
        if not isinstance(history, dict):
            raise RuntimeError(f"ComfyUI history 回應格式錯誤, prompt_id={prompt_id}")
        if prompt_id in history:
            entry = history[prompt_id]
            if not isinstance(entry, dict):
                raise RuntimeError(f"ComfyUI history entry 回應格式錯誤, prompt_id={prompt_id}")
            status = entry.get("status", {})
            if not isinstance(status, dict):
                raise RuntimeError(f"ComfyUI history status 回應格式錯誤, prompt_id={prompt_id}")
            if status.get("status_str") == "error":
                raise RuntimeError(f"生成失敗: {json.dumps(status, ensure_ascii=False)}, prompt_id={prompt_id}")
            if status.get("completed"):
                returned = dict(entry)
                returned["_prompt_id"] = str(prompt_id)
                returned["_queue_status"] = "completed"
                return returned
        remaining = float(timeout) - (time.monotonic() - start)
        if remaining > 0:
            time.sleep(min(float(poll_interval), remaining))
    queue_status = _query_prompt_queue_status(prompt_id, comfy_url, DEFAULT_HTTP_TIMEOUT)
    queue_status = _cancel_exact_pending_prompt(
        prompt_id, comfy_url, DEFAULT_HTTP_TIMEOUT, queue_status,
    )
    raise VideoTimeoutError(
        f"等待生成逾時({timeout}s), prompt_id={prompt_id}, queue_status={queue_status['status']}",
        prompt_id, queue_status,
    )


def _safe_output_path(output_dir, filename):
    if not isinstance(filename, str) or not filename:
        raise ValueError("ComfyUI output 缺少有效 filename")
    # Check both POSIX and Windows spellings because a Windows deployment may
    # send back a backslash path even when this process runs on POSIX.
    if (
        os.path.isabs(filename)
        or ntpath.isabs(filename)
        or ntpath.splitdrive(filename)[0]
        or filename.startswith(("/", "\\"))
    ):
        raise ValueError(f"拒絕不安全的 output filename: {filename!r}")
    components = filename.replace("\\", "/").split("/")
    if ".." in components:
        raise ValueError(f"拒絕 path traversal output filename: {filename!r}")

    output_root = os.fspath(output_dir)
    root = os.path.abspath(output_root)
    root_real = os.path.realpath(root)
    candidate = os.path.abspath(os.path.join(output_root, *components))
    candidate_real = os.path.realpath(candidate)
    try:
        # Resolve symlinks for the security check, but return the lexical path
        # the caller supplied so output paths remain stable on macOS (/private).
        inside = os.path.commonpath((root_real, candidate_real)) == root_real
    except ValueError:
        inside = False
    if not inside:
        raise ValueError(f"拒絕 path traversal output filename: {filename!r}")
    # Preserve the caller's relative/absolute output-dir convention.
    return os.path.join(output_root, *components)


def download_outputs(history_entry, output_dir=None, node_ids=None, comfy_url=None,
                     request_timeout=DEFAULT_HTTP_TIMEOUT, allow_overwrite=True):
    """Download selected image/video outputs with safe paths and atomic writes."""
    validate_timeout(request_timeout)
    if not isinstance(history_entry, dict) or not isinstance(history_entry.get("outputs"), dict):
        raise RuntimeError("ComfyUI history 沒有有效的 outputs")
    output_dir = output_dir or OUTPUT_DIR
    paths = []
    os.makedirs(output_dir, exist_ok=True)
    selected_ids = {str(node_id) for node_id in node_ids} if node_ids is not None else None
    downloads = []
    for node_id, node_out in history_entry.get("outputs", {}).items():
        if selected_ids is not None and str(node_id) not in selected_ids:
            continue
        if not isinstance(node_out, dict):
            continue
        for key in ("images", "videos", "gifs"):
            items = node_out.get(key) or []
            if not isinstance(items, (list, tuple)):
                continue
            for item in items:
                filename = item.get("filename") if isinstance(item, dict) else None
                local_path = _safe_output_path(output_dir, filename)
                downloads.append((filename, item, local_path))

    if not allow_overwrite:
        existing = [path for _, _, path in downloads if os.path.lexists(path)]
        if existing:
            raise RuntimeError(
                "拒絕覆寫既有影片輸出，請換 --output-dir/--name，或明確使用 --overwrite: "
                + ", ".join(existing)
            )
    duplicate_paths = []
    seen_paths = set()
    for _, _, path in downloads:
        canonical = os.path.normcase(os.path.realpath(os.path.abspath(path)))
        if canonical in seen_paths:
            duplicate_paths.append(path)
        seen_paths.add(canonical)
    if duplicate_paths:
        raise RuntimeError(
            "ComfyUI history 有多個 output 指向同一個本機檔名，拒絕互相覆寫: "
            + ", ".join(duplicate_paths)
        )

    for filename, item, local_path in downloads:
        query = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": str(item.get("subfolder", "")),
            "type": str(item.get("type", "output")),
        })
        url = f"{_comfy_endpoint('view', comfy_url)}?{query}"
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        partial_path = f"{local_path}.{uuid.uuid4().hex}.part"
        try:
            with urllib.request.urlopen(url, timeout=request_timeout) as response, open(partial_path, "wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            os.replace(partial_path, local_path)
        except Exception:
            try:
                os.unlink(partial_path)
            except FileNotFoundError:
                pass
            raise
        paths.append(local_path)
    if not paths:
        selected = f" node_ids={sorted(selected_ids)}" if selected_ids is not None else ""
        raise RuntimeError(f"ComfyUI 沒有產生任何可下載的 output{selected}")
    return paths


def backend_has(backend, cap, capability_config=None):
    config = capability_config or ACTIVE_VIDEO_CONFIG
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


def run_i2v(backend, prompt, image_filename, width, height, seed, duration,
            last_image_filename=None, filename_prefix="img2video", negative=None):
    """I2V 的 backend 入口。main() 不要自己挑 graph。"""
    if backend == "wan":
        return build_img2video_wan(
            prompt, image_filename, negative=negative,
            width=width, height=height, seed=seed, duration=duration,
            filename_prefix=filename_prefix,
        )
    if backend == "h3":
        return build_img2video_h3(
            prompt, image_filename, width=width, height=height,
            seed=seed, duration=duration, last_image_filename=last_image_filename,
            filename_prefix=filename_prefix,
        )
    raise SystemExit(f"未知 --backend {backend!r}")


def run_character_video(backend, prompt, ref_filenames, width, height, seed, duration,
                        filename_prefix="character_video"):
    if backend == "h3":
        return build_character_video_h3(
            prompt, ref_filenames, width=width, height=height,
            seed=seed, duration=duration, filename_prefix=filename_prefix,
        )
    raise SystemExit(f"character_video 目前沒有 {backend} 實作")


def run_pose_drive(backend, prompt, image_filename, motion_filename, width, height, seed,
                   duration, control_type="pose", filename_prefix="pose_drive", negative=None):
    if backend == "h3":
        return build_pose_drive_h3(
            prompt, image_filename, motion_filename, width=width, height=height,
            seed=seed, duration=duration, control_type=control_type,
            filename_prefix=filename_prefix,
        )
    if backend == "wan":
        return build_pose_drive_wan(
            prompt, image_filename, motion_filename, width=width, height=height,
            seed=seed, duration=duration, control_type=control_type,
            filename_prefix=filename_prefix, negative=negative,
        )
    raise SystemExit(f"pose_drive 目前沒有 {backend} 實作")


def _require_video_duration(duration):
    if not (VIDEO_DURATION_MIN <= duration <= VIDEO_DURATION_MAX):
        raise SystemExit(
            f"--duration 鎖在 {VIDEO_DURATION_MIN}~{VIDEO_DURATION_MAX} 秒,"
            f"更長請拆成多個鏡頭(目前給的是 {duration})。"
        )
    return duration


def _require_wh_pair(args):
    if (getattr(args, "width", None) is None) ^ (getattr(args, "height", None) is None):
        raise SystemExit("--width 跟 --height 要一起給,或兩個都不給(跟來源圖比例走)。")


def video_canvas(image_path, width=None, height=None):
    _require_pillow()
    """把輸出畫布收到 VIDEO_MAX_SIDE 以內、且寬高都是 32 的倍數。
    不給寬高就跟來源圖比例走(先縮最長邊)。16GB 實測只鎖到 768,再大要另測。"""
    if width and height:
        src_w, src_h = width, height
    else:
        with PILImage.open(image_path) as im:
            src_w, src_h = im.size
    long_side = max(src_w, src_h)
    scale = min(1.0, VIDEO_MAX_SIDE / float(long_side))
    w = max(32, int(src_w * scale) // 32 * 32)
    h = max(32, int(src_h * scale) // 32 * 32)
    return w, h


def _image_size(image_path):
    _require_pillow()
    try:
        with PILImage.open(image_path) as image:
            return image.size
    except (OSError, ValueError) as exc:
        raise ValueError(f"無法讀取影片輸入圖片: {image_path}") from exc


def validate_transition_images(start_path, end_path):
    """Reject incompatible A/B aspect ratios before either image is uploaded."""
    start_width, start_height = _image_size(start_path)
    end_width, end_height = _image_size(end_path)
    start_ratio = start_width / float(start_height)
    end_ratio = end_width / float(end_height)
    if not math.isclose(start_ratio, end_ratio, rel_tol=0.0, abs_tol=0.01):
        raise ValueError(
            "transition 的 --start/--end 必須有相近畫布比例；"
            f"目前是 {start_width}x{start_height} 與 {end_width}x{end_height}，"
            "避免尾幀被錯誤拉伸後才送進模型。"
        )
    return (start_width, start_height), (end_width, end_height)


def _make_temp_image_path(output_dir, prefix):
    """在指定輸出目錄建立唯一的暫存 PNG 路徑，並關閉 mkstemp 的 fd。

    呼叫端會在上傳到 ComfyUI 後刪除這個檔案；使用 ``mkstemp`` 避免同時執行
    多個影片 task 時共用固定檔名，也避免 Windows 上開啟中的 NamedTemporaryFile
    無法被 Pillow/ffmpeg 重新開啟。
    """
    output_dir = os.fspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".png", dir=output_dir)
    os.close(fd)
    return path


def _remove_temp_file(path):
    if not path:
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _video_streams(container):
    streams = getattr(container, "streams", None)
    video = getattr(streams, "video", ()) if streams is not None else ()
    if not video:
        raise RuntimeError("影片沒有 video stream")
    return video


def _fps_fraction(rate):
    """將 PyAV 的 Fraction/數值 frame rate 正規化成可精確比較的 Fraction。"""
    if rate is None:
        return None
    if isinstance(rate, Fraction):
        return rate
    try:
        numerator, denominator = rate.numerator, rate.denominator
    except AttributeError:
        numerator = denominator = None
    if numerator is not None and denominator is not None:
        try:
            return Fraction(numerator, denominator)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    try:
        return Fraction(str(rate))
    except (TypeError, ValueError, ZeroDivisionError):
        try:
            return Fraction(str(float(rate)))
        except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            raise ValueError(f"無法辨識影片 FPS: {rate!r}") from exc


def _read_motion_fps(video_path):
    """讀取動作參考片的平均 FPS；未知或無法解析時不猜測。"""
    try:
        import av
    except ImportError as exc:
        raise RuntimeError("pose_drive 需要 PyAV 才能驗證 --motion-ref 的 FPS") from exc
    container = av.open(video_path)
    try:
        stream = _video_streams(container)[0]
        rate = getattr(stream, "average_rate", None)
    finally:
        container.close()
    if rate is None:
        raise ValueError(f"--motion-ref 無法辨識 FPS: {video_path}")
    try:
        fps = float(rate)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"--motion-ref 無法辨識 FPS: {rate!r}") from exc
    if not math.isfinite(fps):
        raise ValueError(f"--motion-ref 無法辨識 FPS: {rate!r}")
    return fps


def validate_motion_reference_fps(video_path):
    """pose_drive 不做重採樣，只接受接近產線 24 FPS 的動作參考影片。"""
    fps = _read_motion_fps(video_path)
    if not math.isclose(fps, float(VIDEO_FPS), rel_tol=0.0, abs_tol=VIDEO_FPS_TOLERANCE):
        raise ValueError(
            f"--motion-ref 必須是接近 {VIDEO_FPS} FPS 的影片，目前是 {fps:g} FPS；"
            "產線不會靜默重採樣，請先轉成 24 FPS。"
        )
    return fps


def validate_video_input(video_path, label="影片輸入", min_duration=VIDEO_INPUT_MIN_DURATION,
                         require_fps=None):
    """Decode an input before upload/queue; never let a corrupt/empty video reach ComfyUI."""
    try:
        import av
    except ImportError as exc:
        raise RuntimeError(f"{label} 需要 PyAV 才能驗證可解碼性") from exc
    path = os.path.abspath(os.fspath(video_path))
    if not os.path.isfile(path):
        raise ValueError(f"{label} 不存在: {path}")
    try:
        container = av.open(path)
    except Exception as exc:
        raise ValueError(f"{label} 無法解碼: {path}: {exc}") from exc
    try:
        stream = _video_streams(container)[0]
        fps_fraction = _fps_fraction(getattr(stream, "average_rate", None))
        if fps_fraction is None or fps_fraction <= 0:
            raise ValueError(f"{label} 缺少有效 FPS: {path}")
        frames = 0
        for _ in container.decode(video=0):
            frames += 1
        if frames < 1:
            raise ValueError(f"{label} 沒有影格: {path}")
        duration = frames / float(fps_fraction)
        if duration < float(min_duration):
            raise ValueError(
                f"{label} 時長不足: {duration:.3f}s < {float(min_duration):.3f}s: {path}"
            )
        fps = float(fps_fraction)
        if require_fps is not None and not math.isclose(
                fps, float(require_fps), rel_tol=0.0, abs_tol=VIDEO_FPS_TOLERANCE):
            raise ValueError(
                f"{label} 必須接近 {require_fps} FPS，目前是 {fps:g} FPS: {path}"
            )
        return {
            "path": path, "width": int(stream.width), "height": int(stream.height),
            "fps": fps, "frames": frames, "duration_seconds": round(duration, 6),
            "audio": bool(getattr(container.streams, "audio", ()) or ()),
        }
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise ValueError(f"{label} 解碼失敗: {path}: {exc}") from exc
    finally:
        container.close()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_identifier(value, label):
    if value is None:
        return None
    value = str(value).strip()
    if not value or len(value) > 96 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError(
            f"{label} 只能包含英數字、.、_、-，且長度 1~96；不接受路徑或空白: {value!r}"
        )
    return value


def video_filename_prefix(task, shot_id=None, name=None):
    name = _safe_identifier(name, "--name")
    shot_id = _safe_identifier(shot_id, "--shot-id")
    if name:
        return name
    if shot_id:
        return f"shot_{shot_id}_{task}"
    return task


def _video_expected_frames(backend, duration):
    if backend == "wan":
        return wan_frame_count(duration)
    if backend == "h3":
        return h3_frame_count(duration)
    return None


def make_video_contract(task, backend, width, height, duration=None, audio_expected=None,
                        expected_frames=None, frame_tolerance=VIDEO_FRAME_TOLERANCE,
                        input_metadata=None):
    if expected_frames is None and duration is not None and backend in ("h3", "wan"):
        expected_frames = _video_expected_frames(backend, duration)
    expected_duration = (
        expected_frames / float(VIDEO_FPS) if expected_frames is not None else duration
    )
    contract = {
        "schema_version": VIDEO_CONTRACT_SCHEMA_VERSION,
        "task": task,
        "backend": backend,
        "width": int(width) if width is not None else None,
        "height": int(height) if height is not None else None,
        "fps": VIDEO_FPS,
        "fps_tolerance": VIDEO_FPS_TOLERANCE,
        "requested_duration_seconds": float(duration) if duration is not None else None,
        "expected_duration_seconds": round(expected_duration, 6) if expected_duration is not None else None,
        "duration_tolerance_seconds": VIDEO_DURATION_TOLERANCE,
        "expected_frames": expected_frames,
        "frame_tolerance": int(frame_tolerance),
        "audio_expected": audio_expected,
    }
    if input_metadata is not None:
        contract["input_metadata"] = input_metadata
    return contract


def _digest_json(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _config_digest(config):
    if not isinstance(config, dict):
        return None
    clean = {key: value for key, value in config.items() if key != "_source"}
    return _digest_json(clean)


def _video_model_records(config, backend):
    if not isinstance(config, dict) or backend not in config.get("backends", {}):
        return []
    records = []
    for key, entry in config["backends"][backend].get("models", {}).items():
        if isinstance(entry, str):
            record = {"key": key, "file": entry, "size_bytes": None, "sha256": None}
        elif isinstance(entry, dict):
            record = {
                "key": key,
                "file": entry.get("file") or entry.get("name"),
                "size_bytes": entry.get("size_bytes"),
                "sha256": entry.get("sha256"),
            }
        else:
            continue
        records.append(record)
    return records


def _input_records(paths):
    records = []
    for path in paths or ():
        absolute = os.path.abspath(os.fspath(path))
        if not os.path.isfile(absolute):
            # The normal CLI validates every input before upload.  Keeping a
            # null record here makes mocked/embedder calls diagnosable without
            # fabricating a digest; such a record can never satisfy --resume.
            records.append({"path": absolute, "sha256": None, "size_bytes": None})
            continue
        records.append({
            "path": absolute,
            "sha256": _sha256_file(absolute),
            "size_bytes": os.path.getsize(absolute),
        })
    return records


def _continuity_metric(image_a, image_b):
    _require_pillow()
    a = image_a.convert("RGB").resize((64, 64), PILImage.Resampling.BILINEAR)
    b = image_b.convert("RGB").resize((64, 64), PILImage.Resampling.BILINEAR)
    total = 0
    for y in range(64):
        for x in range(64):
            left, right = a.getpixel((x, y)), b.getpixel((x, y))
            total += sum(abs(int(one) - int(other)) for one, other in zip(left, right)) / (255.0 * 3.0)
    return total / (64 * 64)


def _first_last_video_images(video_path):
    import av
    container = av.open(video_path)
    first = last = None
    try:
        for frame in container.decode(video=0):
            image = frame.to_image().convert("RGB")
            if first is None:
                first = image.copy()
            last = image.copy()
    finally:
        container.close()
    if first is None or last is None:
        raise RuntimeError(f"影片沒有畫面，無法計算連續性: {video_path}")
    return first, last


def _continuity_warnings(video_path, task, references=None):
    """Warning-only pixel continuity diagnostics; never judge character identity."""
    if task == "pose_drive" or task == "character_video":
        return []
    first, last = _first_last_video_images(video_path)
    refs = references or {}
    pairs = []
    if task == "fx_loop":
        pairs.append(("seam", first, last))
    if refs.get("start") is not None:
        with PILImage.open(refs["start"]) as image:
            pairs.append(("start", image.copy(), first))
    if refs.get("end") is not None:
        with PILImage.open(refs["end"]) as image:
            pairs.append(("end", last, image.copy()))
    if refs.get("source") is not None:
        with PILImage.open(refs["source"]) as image:
            pairs.append(("source", image.copy(), first))
    warnings = []
    for label, left, right in pairs:
        score = _continuity_metric(left, right)
        if score > VIDEO_SEAM_WARNING_THRESHOLD:
            warnings.append({
                "kind": "continuity",
                "label": label,
                "score": round(score, 6),
                "threshold": VIDEO_SEAM_WARNING_THRESHOLD,
                "message": "連續性指標超過 warning 閾值；僅供人工檢查，不代表身份失敗",
            })
    return warnings


def build_img2video_wan(prompt, image_filename, negative=None, width=832, height=480,
                        seed=None, duration=2.0, filename_prefix="img2video"):
    seed = seed_or_random(seed)
    length = wan_frame_count(duration)
    negative = negative or VIDEO_NEG_DEFAULT
    g = {
        "37": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("wan", "i2v_unet"), "weight_dtype": "default"}},
        "38": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("wan", "clip"), "type": "wan", "device": "default"}},
        "39": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("wan", "vae")}},
        "48": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["37", 0], "shift": 8.0}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["38", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["38", 0]}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "55": {"class_type": "Wan22ImageToVideoLatent", "inputs": {
            "vae": ["39", 0], "start_image": ["56", 0],
            "width": width, "height": height, "length": length, "batch_size": 1}},
        "3": {"class_type": "KSampler", "inputs": {
            "model": ["48", 0], "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["55", 0], "seed": seed, "steps": VIDEO_STEPS, "cfg": 5.0,
            "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["39", 0]}},
        "57": {"class_type": "CreateVideo", "inputs": {"images": ["8", 0], "fps": float(VIDEO_FPS)}},
        "58": {"class_type": "SaveVideo", "inputs": {
            "video": ["57", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "58"


def build_pose_drive_wan(prompt, image_filename, motion_filename, width=768, height=768,
                         seed=None, duration=2.0, control_type="pose",
                         filename_prefix="pose_drive", negative=None):
    """pose_drive 的 wan 實作:Fun Control 5B,角色靜幀當 ref_image,動作影片抽幀後走 canny/pose/depth。
    跟 I2V 用的 TI2V 5B 是不同 UNET,task 層不要寫這個檔名。"""
    seed = seed_or_random(seed)
    length = wan_frame_count(duration)
    negative = negative or VIDEO_NEG_DEFAULT
    g = {
        "37": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("wan", "control_unet"), "weight_dtype": "default"}},
        "38": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("wan", "clip"), "type": "wan", "device": "default"}},
        "39": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("wan", "vae")}},
        "48": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["37", 0], "shift": 8.0}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["38", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["38", 0]}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "80": {"class_type": "LoadVideo", "inputs": {"file": motion_filename}},
        "81": {"class_type": "GetVideoComponents", "inputs": {"video": ["80", 0]}},
        "82": build_control_preprocessor(control_type, "81"),
        "55": {"class_type": "Wan22FunControlToVideo", "inputs": {
            "positive": ["6", 0], "negative": ["7", 0], "vae": ["39", 0],
            "width": width, "height": height, "length": length, "batch_size": 1,
            "ref_image": ["56", 0], "control_video": ["82", 0]}},
        "3": {"class_type": "KSampler", "inputs": {
            "model": ["48", 0], "positive": ["55", 0], "negative": ["55", 1],
            "latent_image": ["55", 2], "seed": seed, "steps": VIDEO_STEPS, "cfg": 5.0,
            "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["39", 0]}},
        "57": {"class_type": "CreateVideo", "inputs": {"images": ["8", 0], "fps": float(VIDEO_FPS)}},
        "58": {"class_type": "SaveVideo", "inputs": {
            "video": ["57", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "58"


def extract_video_frames(video_path, output_dir=None):
    """Transactional mp4 -> png extraction; a failed run keeps the previous set."""
    import av
    output_dir = output_dir or os.path.dirname(os.path.abspath(video_path))
    # SaveVideo 常吐 foo_00001_.mp4,直接加 _frames 會變成 foo_00001__frames。
    stem = os.path.splitext(os.path.basename(video_path))[0].rstrip("_")
    frame_dir = os.path.join(output_dir, stem + "_frames")
    if os.path.islink(frame_dir):
        raise RuntimeError(f"抽幀目錄是 symlink，拒絕清理: {frame_dir}")
    parent = os.path.dirname(frame_dir) or "."
    os.makedirs(parent, exist_ok=True)
    if os.path.islink(frame_dir):
        raise RuntimeError(f"抽幀目錄是 symlink，拒絕清理: {frame_dir}")
    staging = tempfile.mkdtemp(prefix=f".{os.path.basename(frame_dir)}.", dir=parent)
    paths = []
    try:
        # Preserve user-owned non-frame files from the previous directory, but
        # never follow links or copy an unexpected directory into the staging set.
        if os.path.isdir(frame_dir):
            for entry in os.scandir(frame_dir):
                if re.fullmatch(r"\d+\.png", entry.name):
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        raise RuntimeError(f"抽幀輸出檔不是安全的一般檔案: {entry.path}")
                    continue
                if entry.is_symlink():
                    raise RuntimeError(f"抽幀保留項目是 symlink，拒絕複製: {entry.path}")
                destination = os.path.join(staging, entry.name)
                if entry.is_file(follow_symlinks=False):
                    shutil.copy2(entry.path, destination)
                elif entry.is_dir(follow_symlinks=False):
                    shutil.copytree(entry.path, destination, symlinks=False)
                else:
                    raise RuntimeError(f"抽幀保留項目不是一般檔案或目錄: {entry.path}")
        container = av.open(video_path)
        try:
            for i, frame in enumerate(container.decode(video=0)):
                p = os.path.join(staging, f"{i:03d}.png")
                frame.to_image().save(p)
                paths.append(p)
        finally:
            container.close()
        if not paths:
            raise RuntimeError(f"影片沒有影格，未更新既有抽幀目錄: {video_path}")
        old_dir = None
        if os.path.lexists(frame_dir):
            old_dir = tempfile.mkdtemp(prefix=f".{os.path.basename(frame_dir)}.old.", dir=parent)
            os.rmdir(old_dir)
            os.replace(frame_dir, old_dir)
        try:
            os.replace(staging, frame_dir)
        except Exception:
            if old_dir is not None and not os.path.lexists(frame_dir):
                os.replace(old_dir, frame_dir)
            raise
        if old_dir is not None:
            shutil.rmtree(old_dir)
        paths = [os.path.join(frame_dir, os.path.basename(path)) for path in paths]
    except Exception:
        if os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)
        raise
    print(f"[抽幀] {len(paths)} 張 -> {frame_dir}")
    return paths, frame_dir


def extract_last_frame(video_path, dest_path):
    """clip_extend:上一鏡最後一幀當下一鏡靜幀。"""
    import av
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)) or ".", exist_ok=True)
    container = av.open(video_path)
    last = None
    try:
        for frame in container.decode(video=0):
            last = frame
    finally:
        container.close()
    if last is None:
        raise RuntimeError(f"影片沒有畫面: {video_path}")
    last.to_image().save(dest_path)
    return dest_path


def _resize_video_image(image, width, height, mode):
    if image.size == (width, height):
        return image
    if mode == "stretch":
        return image.resize((width, height), PILImage.Resampling.LANCZOS)
    source_ratio = image.width / float(image.height)
    target_ratio = width / float(height)
    if mode == "fit":
        scale = min(width / image.width, height / image.height)
        resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), PILImage.Resampling.LANCZOS)
        canvas = PILImage.new("RGB", (width, height), (0, 0, 0))
        canvas.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
        return canvas
    if mode == "fill":
        scale = max(width / image.width, height / image.height)
        resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), PILImage.Resampling.LANCZOS)
        left = max(0, (resized.width - width) // 2)
        top = max(0, (resized.height - height) // 2)
        return resized.crop((left, top, left + width, top + height))
    raise ValueError(f"未知 resize_mode: {mode!r}")


def concat_videos(video_paths, dest_path, allow_overwrite=False, resize_mode="strict",
                  audio_policy="require-consistent"):
    """Basic local concatenation with explicit geometry/audio policies."""
    if len(video_paths) < 2:
        raise RuntimeError("video_concat 至少要兩支影片")
    if resize_mode not in ("strict", "fit", "fill", "stretch"):
        raise ValueError("resize_mode 必須是 strict/fit/fill/stretch")
    if audio_policy not in ("require-consistent", "drop", "silence-missing"):
        raise ValueError("audio_policy 必須是 require-consistent/drop/silence-missing")
    dest_path = os.fspath(dest_path)
    dest_canonical = os.path.normcase(os.path.realpath(os.path.abspath(dest_path)))
    for source in video_paths:
        source_canonical = os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(source))))
        if source_canonical == dest_canonical:
            raise ValueError(f"video_concat 輸入影片不可與輸出路徑相同: {source!r}")
    if os.path.lexists(dest_path) and not allow_overwrite:
        raise RuntimeError(
            f"拒絕覆寫既有 video_concat 輸出: {dest_path!r}；"
            "請換 --name，或明確使用 --overwrite"
        )
    _require_pillow()
    import av

    stream_specs = []
    audio_present = []
    input_durations = []
    for source in video_paths:
        try:
            inp = av.open(source)
        except Exception as exc:
            raise ValueError(f"video_concat 無法解碼輸入影片 {source!r}: {exc}") from exc
        try:
            vs = _video_streams(inp)[0]
            # 保留原本無 average_rate 時採 24 FPS 的行為；有明確 rate 時則用
            # Fraction 精確比較，避免 24/25 或 23.976/24 被靜默混接。
            fps = _fps_fraction(getattr(vs, "average_rate", None))
            if fps is None:
                fps = Fraction(VIDEO_FPS, 1)
            elif fps <= 0:
                raise ValueError(f"影片 FPS 必須大於 0: {source!r}")
            stream_specs.append((vs.width, vs.height, fps))
            audio_present.append(bool(getattr(inp.streams, "audio", ()) or ()))
            decoder = getattr(inp, "decode", None)
            input_durations.append(
                sum(1 for _ in decoder(video=0)) / float(fps) if decoder is not None else None
            )
        finally:
            inp.close()

    expected_fps = stream_specs[0][2]
    mismatched = [
        (source, spec[2])
        for source, spec in zip(video_paths, stream_specs)
        if spec[2] != expected_fps
    ]
    if mismatched:
        details = ", ".join(f"{source!r}={float(rate):g} FPS" for source, rate in mismatched)
        raise ValueError(
            f"video_concat 所有輸入影片必須使用相同 FPS；"
            f"第一支={float(expected_fps):g} FPS，{details}"
        )
    if expected_fps != Fraction(VIDEO_FPS, 1):
        raise ValueError(
            f"video_concat 只接受產線 {VIDEO_FPS} FPS 影片，目前第一支是 {float(expected_fps):g} FPS"
        )

    width, height = stream_specs[0][0], stream_specs[0][1]
    mismatched_dimensions = [
        (source, spec[0], spec[1])
        for source, spec in zip(video_paths, stream_specs)
        if (spec[0], spec[1]) != (width, height)
    ]
    if mismatched_dimensions and resize_mode == "strict":
        details = ", ".join(f"{source!r}={w}x{h}" for source, w, h in mismatched_dimensions)
        raise ValueError(
            "video_concat 輸入影片尺寸不同，預設拒絕以免默默 stretch；"
            f"第一支={width}x{height}，{details}。請明確給 --resize-mode fit/fill/stretch"
        )
    fps = expected_fps
    all_audio = all(audio_present)
    any_audio = any(audio_present)
    if audio_policy == "require-consistent" and any_audio and not all_audio:
        raise ValueError(
            "video_concat 輸入音訊不一致；預設拒絕混合有聲/無聲。"
            "請明確給 --audio-policy drop 或 silence-missing"
        )
    keep_audio = all_audio if audio_policy == "require-consistent" else (
        any_audio if audio_policy == "silence-missing" else False
    )
    if keep_audio:
        for src, has_audio, video_duration in zip(video_paths, audio_present, input_durations):
            if not has_audio:
                continue
            if video_duration is None:
                continue
            inp = av.open(src)
            try:
                audio_stream = list(getattr(inp.streams, "audio", ()) or ())[0]
                a_duration = getattr(audio_stream, "duration", None)
                a_base = getattr(audio_stream, "time_base", None)
                if a_duration is not None and a_base is not None:
                    actual = float(a_duration * a_base)
                    if abs(actual - video_duration) > VIDEO_AUDIO_DRIFT_TOLERANCE:
                        raise ValueError(
                            f"video_concat 音畫 duration drift 超過 {VIDEO_AUDIO_DRIFT_TOLERANCE}s: "
                            f"{src!r} video={video_duration:.3f}s audio={actual:.3f}s"
                        )
            finally:
                inp.close()
    dest_dir = os.path.dirname(os.path.abspath(dest_path)) or "."
    os.makedirs(dest_dir, exist_ok=True)
    fd, temp_dest = tempfile.mkstemp(
        prefix=f".{os.path.basename(dest_path)}.", suffix=".mp4", dir=dest_dir
    )
    os.close(fd)
    out = None
    try:
        out = av.open(temp_dest, "w")
        out_v = out.add_stream("libx264", rate=fps)
        out_v.width = width
        out_v.height = height
        out_v.pix_fmt = "yuv420p"
        # 兩個 stream 都要在寫任何 packet 之前建好,不然 mp4 mux 會 EINVAL
        out_a = out.add_stream("aac", rate=32000) if keep_audio else None
        for src in video_paths:
            inp = av.open(src)
            try:
                for frame in inp.decode(video=0):
                    img = frame.to_image()
                    if img.size != (width, height):
                        img = _resize_video_image(img, width, height, resize_mode)
                    of = av.VideoFrame.from_image(img)
                    for packet in out_v.encode(of):
                        out.mux(packet)
            finally:
                inp.close()
        for packet in out_v.encode():
            out.mux(packet)
        if out_a:
            resampler = av.AudioResampler(format="fltp", layout="stereo", rate=32000)
            sample_i = 0
            sample_rate = 32000
            for src, has_audio, video_duration in zip(video_paths, audio_present, input_durations):
                ain = av.open(src)
                try:
                    frames_in = list(ain.decode(audio=0)) if has_audio else []
                finally:
                    ain.close()
                if not has_audio and audio_policy == "silence-missing" and video_duration is not None:
                    silence_samples = max(1, round(video_duration * sample_rate))
                    silence = av.AudioFrame(format="fltp", layout="stereo", samples=silence_samples)
                    silence.sample_rate = sample_rate
                    for plane in silence.planes:
                        plane.update(bytes(plane.buffer_size))
                    frames_in = [silence]
                frames_in.append(None)
                for frame in frames_in:
                    resampled = resampler.resample(frame) or []
                    if not isinstance(resampled, (list, tuple)):
                        resampled = [resampled]
                    for rf in resampled:
                        if rf is None:
                            continue
                        rf.pts = sample_i
                        sample_i += rf.samples
                        for packet in out_a.encode(rf) or []:
                            out.mux(packet)
            for packet in out_a.encode(None) or []:
                out.mux(packet)
        out.close()
        out = None
        os.replace(temp_dest, dest_path)
    except Exception:
        if out is not None:
            try:
                out.close()
            except Exception:
                pass
        try:
            os.unlink(temp_dest)
        except FileNotFoundError:
            pass
        raise
    note = "含立體聲" if keep_audio else "無聲(有鏡頭沒有音軌,整段不接聲音)"
    print(f"[接片] {len(video_paths)} 支 -> {dest_path} ({note})")
    return dest_path


VIDEO_COMPOSITE_BACKGROUND_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".m4v")


def composite_videos(foreground_path, background_path, dest_path, chroma_color="00FF00",
                     tolerance=60.0, softness=40.0, resize_mode="fill", allow_overwrite=False):
    """Chroma-key 前景疊到背景(影片或靜態圖)上，純本機 PyAV+numpy 逐幀合成，不經 ComfyUI。

    只吃前景本身的音軌(背景音軌一律丟棄)——這條產線目前只有一個會有音軌的來源
    (h3 backend 生成的前景)，混兩條音軌的取捨留給外部剪接軟體，不在這裡猜。
    """
    if resize_mode not in ("strict", "fit", "fill", "stretch"):
        raise ValueError("resize_mode 必須是 strict/fit/fill/stretch")
    if not (0.0 <= tolerance <= 255.0):
        raise ValueError(f"--tolerance 必須介於 0..255: {tolerance!r}")
    if not (0.0 < softness <= 255.0):
        raise ValueError(f"--softness 必須介於 0(不含)..255: {softness!r}")
    chroma_color = str(chroma_color).strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", chroma_color or ""):
        raise ValueError(f"--chroma-color 必須是 6 碼十六進位色碼(例如 00FF00): {chroma_color!r}")
    chroma_rgb = tuple(int(chroma_color[i:i + 2], 16) for i in (0, 2, 4))

    dest_path = os.fspath(dest_path)
    dest_canonical = os.path.normcase(os.path.realpath(os.path.abspath(dest_path)))
    for source in (foreground_path, background_path):
        source_canonical = os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(source))))
        if source_canonical == dest_canonical:
            raise ValueError(f"video_composite 輸入不可與輸出路徑相同: {source!r}")
    if os.path.lexists(dest_path) and not allow_overwrite:
        raise RuntimeError(
            f"拒絕覆寫既有 video_composite 輸出: {dest_path!r}；"
            "請換 --name，或明確使用 --overwrite"
        )
    _require_pillow()
    import numpy as np
    import av

    try:
        fg_in = av.open(foreground_path)
    except Exception as exc:
        raise ValueError(f"video_composite 無法解碼 --foreground {foreground_path!r}: {exc}") from exc
    try:
        fg_vs = _video_streams(fg_in)[0]
        fps = _fps_fraction(getattr(fg_vs, "average_rate", None)) or Fraction(VIDEO_FPS, 1)
        if fps != Fraction(VIDEO_FPS, 1):
            raise ValueError(
                f"video_composite --foreground 只接受產線 {VIDEO_FPS} FPS 影片，"
                f"目前是 {float(fps):g} FPS"
            )
        width, height = fg_vs.width, fg_vs.height
        fg_audio_present = bool(getattr(fg_in.streams, "audio", ()) or ())
    except Exception:
        fg_in.close()
        raise

    background_is_video = os.path.splitext(background_path)[1].lower() in VIDEO_COMPOSITE_BACKGROUND_EXTS
    bg_in = None
    bg_image = None
    if background_is_video:
        try:
            bg_in = av.open(background_path)
        except Exception as exc:
            fg_in.close()
            raise ValueError(f"video_composite 無法解碼 --background {background_path!r}: {exc}") from exc
        try:
            bg_vs = _video_streams(bg_in)[0]
            bg_fps = _fps_fraction(getattr(bg_vs, "average_rate", None)) or Fraction(VIDEO_FPS, 1)
            if bg_fps != Fraction(VIDEO_FPS, 1):
                raise ValueError(
                    f"video_composite --background 只接受產線 {VIDEO_FPS} FPS 影片，"
                    f"目前是 {float(bg_fps):g} FPS"
                )
            bg_size = (bg_vs.width, bg_vs.height)
        except Exception:
            bg_in.close()
            fg_in.close()
            raise
    else:
        try:
            with PILImage.open(background_path) as im:
                bg_image = im.convert("RGB")
                bg_size = bg_image.size
        except Exception as exc:
            fg_in.close()
            raise ValueError(f"video_composite 無法讀取 --background 圖片 {background_path!r}: {exc}") from exc

    if resize_mode == "strict" and bg_size != (width, height):
        fg_in.close()
        if bg_in is not None:
            bg_in.close()
        raise ValueError(
            "video_composite 背景尺寸跟前景不同，--resize-mode strict 拒絕縮放；"
            f"前景={width}x{height}，背景={bg_size}。"
            "請明確給 --resize-mode fit/fill/stretch"
        )

    key_rgb = np.array(chroma_rgb, dtype=np.int16)
    dest_dir = os.path.dirname(os.path.abspath(dest_path)) or "."
    os.makedirs(dest_dir, exist_ok=True)
    fd, temp_dest = tempfile.mkstemp(
        prefix=f".{os.path.basename(dest_path)}.", suffix=".mp4", dir=dest_dir
    )
    os.close(fd)
    out = None
    try:
        out = av.open(temp_dest, "w")
        out_v = out.add_stream("libx264", rate=fps)
        out_v.width = width
        out_v.height = height
        out_v.pix_fmt = "yuv420p"
        out_a = out.add_stream("aac", rate=32000) if fg_audio_present else None
        bg_decoder = bg_in.decode(video=0) if bg_in is not None else None
        frame_count = 0
        for fg_frame in fg_in.decode(video=0):
            fg_im = fg_frame.to_image().convert("RGB")
            if bg_in is None:
                bg_im = bg_image
            else:
                try:
                    bg_frame = next(bg_decoder)
                except StopIteration:
                    # PyAV/FFmpeg seek behavior varies by container. Reopening is slower than
                    # seek but deterministic, and keeps memory constant while looping a short
                    # background underneath a longer foreground.
                    bg_in.close()
                    bg_in = av.open(background_path)
                    bg_decoder = bg_in.decode(video=0)
                    try:
                        bg_frame = next(bg_decoder)
                    except StopIteration as exc:
                        raise ValueError(
                            f"video_composite --background 沒有畫面: {background_path}"
                        ) from exc
                bg_im = bg_frame.to_image().convert("RGB")
            bg_im = _resize_video_image(bg_im, width, height, resize_mode)
            fg_arr = np.asarray(fg_im, dtype=np.int16)
            bg_arr = np.asarray(bg_im, dtype=np.uint8).astype(np.float32)
            dist = np.abs(fg_arr - key_rgb).max(axis=2).astype(np.float32)
            alpha = np.clip((dist - tolerance) / softness, 0.0, 1.0)[:, :, None]
            composited = fg_arr.astype(np.float32) * alpha + bg_arr * (1.0 - alpha)
            of = av.VideoFrame.from_ndarray(np.clip(composited, 0, 255).astype(np.uint8), format="rgb24")
            for packet in out_v.encode(of):
                out.mux(packet)
            frame_count += 1
        if not frame_count:
            raise ValueError(f"video_composite --foreground 沒有畫面: {foreground_path}")
        for packet in out_v.encode():
            out.mux(packet)
        if out_a:
            ain = av.open(foreground_path)
            try:
                resampler = av.AudioResampler(format="fltp", layout="stereo", rate=32000)
                sample_i = 0
                for frame in ain.decode(audio=0):
                    resampled = resampler.resample(frame) or []
                    if not isinstance(resampled, (list, tuple)):
                        resampled = [resampled]
                    for rf in resampled:
                        if rf is None:
                            continue
                        rf.pts = sample_i
                        sample_i += rf.samples
                        for packet in out_a.encode(rf) or []:
                            out.mux(packet)
                for rf in resampler.resample(None) or []:
                    rf.pts = sample_i
                    sample_i += rf.samples
                    for packet in out_a.encode(rf) or []:
                        out.mux(packet)
            finally:
                ain.close()
            for packet in out_a.encode(None) or []:
                out.mux(packet)
        out.close()
        out = None
        os.replace(temp_dest, dest_path)
    except Exception:
        if out is not None:
            try:
                out.close()
            except Exception:
                pass
        try:
            os.unlink(temp_dest)
        except FileNotFoundError:
            pass
        raise
    finally:
        fg_in.close()
        if bg_in is not None:
            bg_in.close()
    note = "含前景音軌" if fg_audio_present else "無聲"
    print(f"[合成] {foreground_path} + {background_path} -> {dest_path} ({note})")
    return dest_path


def inspect_video_output(video_path, task=None, backend=None, elapsed_seconds=None):
    """Read the delivered mp4 itself; a filename alone never counts as a pass."""
    import av

    video_path = os.fspath(video_path)
    if not os.path.isfile(video_path):
        raise RuntimeError(f"影片輸出不存在: {video_path}")
    container = av.open(video_path)
    try:
        video_stream = _video_streams(container)[0]
        fps_fraction = _fps_fraction(getattr(video_stream, "average_rate", None))
        if fps_fraction is None or fps_fraction <= 0:
            raise RuntimeError(f"影片輸出缺少有效 FPS: {video_path}")
        frame_count = sum(1 for _ in container.decode(video=0))
        video_duration = None
        stream_duration = getattr(video_stream, "duration", None)
        time_base = getattr(video_stream, "time_base", None)
        if stream_duration is not None and time_base is not None:
            try:
                video_duration = float(stream_duration * time_base)
            except (TypeError, ValueError):
                video_duration = None
        if not video_duration or video_duration <= 0:
            video_duration = frame_count / float(fps_fraction)
        codec_context = getattr(video_stream, "codec_context", None)
        pixel_format = getattr(getattr(codec_context, "format", None), "name", None)
        audio = []
        for stream in list(getattr(container.streams, "audio", ()) or ()):
            audio_codec = getattr(stream, "codec_context", None)
            layout = getattr(stream, "layout", None)
            audio_duration = None
            a_duration = getattr(stream, "duration", None)
            a_time_base = getattr(stream, "time_base", None)
            if a_duration is not None and a_time_base is not None:
                try:
                    audio_duration = float(a_duration * a_time_base)
                except (TypeError, ValueError):
                    audio_duration = None
            audio.append({
                "codec": getattr(audio_codec, "name", None),
                "channels": getattr(audio_codec, "channels", None),
                "layout": getattr(layout, "name", None) or (str(layout) if layout else None),
                "sample_rate": getattr(audio_codec, "sample_rate", None),
                "duration_seconds": round(audio_duration, 6) if audio_duration is not None else None,
            })
        metadata = {
            "task": task,
            "backend": backend,
            "path": os.path.abspath(video_path),
            "size_bytes": os.path.getsize(video_path),
            "container": getattr(getattr(container, "format", None), "name", None),
            "codec": getattr(codec_context, "name", None),
            "pixel_format": pixel_format,
            "width": int(video_stream.width),
            "height": int(video_stream.height),
            "fps": float(fps_fraction),
            "frames": frame_count,
            "duration_seconds": round(video_duration, 6),
            "audio": bool(audio),
            "audio_streams": audio,
        }
    except (RuntimeError, ValueError):
        raise
    except Exception as exc:
        raise RuntimeError(f"影片輸出解碼/檢查失敗: {video_path}: {exc}") from exc
    finally:
        container.close()
    if elapsed_seconds is not None:
        metadata["elapsed_seconds"] = round(float(elapsed_seconds), 3)
    return metadata


def _validate_video_contract(metadata, contract):
    errors = []
    if contract is None:
        contract = make_video_contract(
            metadata.get("task"), metadata.get("backend"), metadata.get("width"),
            metadata.get("height"), audio_expected=None, expected_frames=None,
        )
    for key in ("width", "height"):
        expected = contract.get(key)
        if expected is not None and metadata.get(key) != expected:
            errors.append(f"{key} mismatch: expected={expected}, actual={metadata.get(key)}")
    expected_fps = contract.get("fps", VIDEO_FPS)
    fps_tolerance = float(contract.get("fps_tolerance", VIDEO_FPS_TOLERANCE))
    if expected_fps is not None and not math.isclose(
            metadata["fps"], float(expected_fps), rel_tol=0.0, abs_tol=fps_tolerance):
        errors.append(f"fps mismatch: expected={expected_fps}, actual={metadata['fps']:g}")
    if metadata.get("frames", 0) < 1:
        errors.append("影片輸出沒有影格")
    expected_frames = contract.get("expected_frames")
    if expected_frames is not None:
        tolerance = int(contract.get("frame_tolerance", VIDEO_FRAME_TOLERANCE))
        if abs(int(metadata["frames"]) - int(expected_frames)) > tolerance:
            errors.append(
                f"frame count mismatch: expected={expected_frames}±{tolerance}, actual={metadata['frames']}"
            )
    expected_duration = contract.get("expected_duration_seconds")
    if expected_duration is None:
        expected_duration = contract.get("requested_duration_seconds")
    if expected_duration is not None and abs(
            float(metadata["duration_seconds"]) - float(expected_duration)
    ) > float(contract.get("duration_tolerance_seconds", VIDEO_DURATION_TOLERANCE)):
        errors.append(
            f"duration mismatch: expected={float(expected_duration):.3f}s, "
            f"actual={float(metadata['duration_seconds']):.3f}s"
        )
    audio_expected = contract.get("audio_expected")
    if audio_expected is not None and bool(metadata.get("audio")) != bool(audio_expected):
        errors.append(
            f"audio mismatch: expected={'present' if audio_expected else 'absent'}, "
            f"actual={'present' if metadata.get('audio') else 'absent'}"
        )
    return errors


def report_video_output(video_path, task, backend, elapsed_seconds=None, expected_contract=None,
                        continuity_refs=None):
    metadata = inspect_video_output(
        video_path, task=task, backend=backend, elapsed_seconds=elapsed_seconds
    )
    errors = _validate_video_contract(metadata, expected_contract)
    warnings = _continuity_warnings(video_path, task, continuity_refs) if not errors else []
    metadata["validation"] = {
        "status": "fail" if errors else ("warning" if warnings else "pass"),
        "errors": errors,
        "warnings": warnings,
    }
    if errors:
        raise VideoContractError(
            f"影片輸出不符合契約: {video_path}: {'; '.join(errors)}",
            metadata=metadata, errors=errors, warnings=warnings,
        )
    print("[影片驗證] " + json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    return metadata


def _sidecar_path(video_path):
    return os.fspath(video_path) + ".json"


def _write_json_atomic(path, payload, allow_overwrite=True):
    path = os.path.abspath(os.fspath(path))
    if os.path.lexists(path) and not allow_overwrite:
        raise RuntimeError(f"拒絕覆寫既有 JSON sidecar: {path}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(_json_safe(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return path


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return repr(value)


def write_video_sidecar(video_path, task, backend, seed, prompt, negative, input_paths,
                        capability_config, contract, actual_metadata, prompt_id=None,
                        elapsed_seconds=None, warnings=None, allow_overwrite=True):
    """Write trace metadata without embedding runtime credentials or raw config."""
    config_digest = _config_digest(capability_config)
    payload = {
        "schema_version": VIDEO_SIDECAR_SCHEMA_VERSION,
        "task": task,
        "backend": backend,
        "resolved_seed": int(seed) if seed is not None else None,
        "prompt": prompt or "",
        "negative": negative or "",
        "inputs": _input_records(input_paths),
        "capability_config_digest": config_digest,
        "model_records": _video_model_records(capability_config, backend),
        "prompt_id": str(prompt_id) if prompt_id is not None else None,
        "requested_contract": contract,
        "actual_pyav_metadata": actual_metadata,
        "warnings": list(warnings or actual_metadata.get("validation", {}).get("warnings", [])),
        "elapsed_seconds": round(float(elapsed_seconds), 3) if elapsed_seconds is not None else None,
        "output_path": os.path.abspath(os.fspath(video_path)),
    }
    return _write_json_atomic(_sidecar_path(video_path), payload, allow_overwrite=allow_overwrite)


def _resume_signature(sidecar):
    return {
        "task": sidecar.get("task"),
        "backend": sidecar.get("backend"),
        "resolved_seed": sidecar.get("resolved_seed"),
        "inputs_digest": _digest_json(sidecar.get("inputs", [])),
        "capability_config_digest": sidecar.get("capability_config_digest"),
        "contract_digest": _digest_json(sidecar.get("requested_contract")),
    }


def resume_video_output(video_path, expected_task, expected_backend, expected_seed,
                        input_paths, capability_config, contract):
    """Return a verified output only when every reproducibility field matches exactly."""
    video_path = os.path.abspath(os.fspath(video_path))
    sidecar = _sidecar_path(video_path)
    if not os.path.isfile(video_path) or not os.path.isfile(sidecar):
        raise RuntimeError(f"--resume 找不到完整影片 + sidecar: {video_path}")
    try:
        with open(sidecar, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"--resume sidecar 無法讀取，拒絕猜測: {sidecar}") from exc
    expected = {
        "task": expected_task,
        "backend": expected_backend,
        "resolved_seed": expected_seed,
        "inputs_digest": _digest_json(_input_records(input_paths)),
        "capability_config_digest": _config_digest(capability_config),
        "contract_digest": _digest_json(contract),
    }
    if _resume_signature(payload) != expected:
        raise RuntimeError(f"--resume sidecar 契約/輸入/config 不完全相符，拒絕跳過: {sidecar}")
    metadata = report_video_output(
        video_path, task=expected_task, backend=expected_backend,
        expected_contract=contract,
    )
    return metadata


def _find_named_video_output(output_dir, prefix):
    output_dir = os.path.abspath(os.fspath(output_dir))
    candidates = []
    if not os.path.isdir(output_dir):
        return None
    for entry in os.scandir(output_dir):
        if not entry.is_file(follow_symlinks=False) or not entry.name.lower().endswith(".mp4"):
            continue
        if os.path.splitext(entry.name)[0].startswith(prefix):
            candidates.append(entry.path)
    if len(candidates) != 1:
        return None
    return candidates[0]


def write_video_timeout_record(output_dir, prefix, task, backend, seed, prompt, negative,
                              input_paths, capability_config, contract, exc):
    path = os.path.join(os.path.abspath(os.fspath(output_dir)), f"{prefix}.timeout.json")
    payload = {
        "schema_version": VIDEO_SIDECAR_SCHEMA_VERSION,
        "status": "timeout",
        "task": task,
        "backend": backend,
        "resolved_seed": seed,
        "prompt": prompt or "",
        "negative": negative or "",
        "inputs": _input_records(input_paths),
        "capability_config_digest": _config_digest(capability_config),
        "requested_contract": contract,
        "prompt_id": getattr(exc, "prompt_id", None),
        "queue_status": getattr(exc, "queue_status", {"status": "unknown"}),
        "message": str(exc),
    }
    return _write_json_atomic(path, payload)


def build_img2video_h3(prompt, image_filename, width=768, height=768, seed=None, duration=2.0,
                       last_image_filename=None, filename_prefix="img2video"):
    seed = seed_or_random(seed)
    length = h3_frame_count(duration)
    g = {
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("h3", "i2v_unet"), "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("h3", "clip"), "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "video_vae")}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "audio_vae")}},
        "shift": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "104": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["13", 0], "vae": ["11", 0], "first_frame": ["56", 0],
            "prompt": prompt, "width": width, "height": height, "length": length}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {
            "model": ["shift", 0], "scheduler": "simple", "steps": VIDEO_STEPS, "denoise": 1.0}},
        "16": {"class_type": "BasicGuider", "inputs": {
            "model": ["shift", 0], "conditioning": ["104", 0]}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
            "sigmas": ["9", 0], "latent_image": ["104", 1]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["11", 0]}},
        "23": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["24", 0]}},
        "91": {"class_type": "CreateVideo", "inputs": {
            "images": ["10", 0], "audio": ["23", 0], "fps": float(VIDEO_FPS), "bit_depth": 8}},
        "92": {"class_type": "SaveVideo", "inputs": {
            "video": ["91", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    if last_image_filename:
        g["56b"] = {"class_type": "LoadImage", "inputs": {"image": last_image_filename}}
        g["104"]["inputs"]["last_frame"] = ["56b", 0]
    return g, "92"


def build_character_video_h3(prompt, ref_filenames, width=768, height=768, seed=None, duration=2.0,
                             filename_prefix="character_video"):
    """character_video 的 h3 實作(Ref2VA)。task 契約見 run_character_video,不要從 main 直接叫這個。
    ref_image_size 鎖 match;官方 max 保身份更好但每個 step 都帶參考 token,16GB 上沒實測過不開旗標。
    """
    if not (1 <= len(ref_filenames) <= CHARACTER_REF_MAX):
        raise ValueError(
            f"character_video 要 1~{CHARACTER_REF_MAX} 張參考圖,目前 {len(ref_filenames)}"
        )
    seed = seed_or_random(seed)
    length = h3_frame_count(duration)
    prompt = h3_ref_prompt(prompt, len(ref_filenames))
    g = {
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("h3", "ref_unet"), "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("h3", "clip"), "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "video_vae")}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "audio_vae")}},
        "shift": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "104": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
            "clip": ["13", 0], "vae": ["11", 0], "audio_vae": ["24", 0],
            "prompt": prompt, "width": width, "height": height, "length": length,
            "ref_image_size": "match"}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {
            "model": ["shift", 0], "scheduler": "simple", "steps": VIDEO_STEPS, "denoise": 1.0}},
        "16": {"class_type": "BasicGuider", "inputs": {
            "model": ["shift", 0], "conditioning": ["104", 0]}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
            "sigmas": ["9", 0], "latent_image": ["104", 1]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["11", 0]}},
        "23": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["24", 0]}},
        "91": {"class_type": "CreateVideo", "inputs": {
            "images": ["10", 0], "audio": ["23", 0], "fps": float(VIDEO_FPS), "bit_depth": 8}},
        "92": {"class_type": "SaveVideo", "inputs": {
            "video": ["91", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    for i, fn in enumerate(ref_filenames):
        nid = f"56r{i}"
        g[nid] = {"class_type": "LoadImage", "inputs": {"image": fn}}
        g["104"]["inputs"][f"ref_images.ref_image_{i}"] = [nid, 0]
    return g, "92"


def build_pose_drive_h3(prompt, image_filename, motion_filename, width=768, height=768,
                        seed=None, duration=2.0, control_type="pose",
                        filename_prefix="pose_drive"):
    """pose_drive 的 h3 實作:同一顆 Ref2VA,角色靜幀當 ref_image_0,動作片抽幀後走 pose/canny/depth 當 ref_video_0。
    ComfyUI 0.34.0 沒有 MiniMaxH3FunControlNetApply(PR #15860 還沒進),所以不是真正的 ControlNet Union;
    預處理動作片是為了不要把動作片裡那個人的臉漏進輸出。身份鎖比 wan Fun Control 穩,但仍不是像素鎖臉。
    負向詞這顆沒入口,呼叫端給了也忽略。"""
    seed = seed_or_random(seed)
    length = h3_frame_count(duration)
    prompt = h3_pose_drive_prompt(prompt)
    g = {
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("h3", "ref_unet"), "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("h3", "clip"), "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "video_vae")}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "audio_vae")}},
        "shift": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "80": {"class_type": "LoadVideo", "inputs": {"file": motion_filename}},
        "81": {"class_type": "GetVideoComponents", "inputs": {"video": ["80", 0]}},
        "82": build_control_preprocessor(control_type, "81"),
        "104": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
            "clip": ["13", 0], "vae": ["11", 0], "audio_vae": ["24", 0],
            "prompt": prompt, "width": width, "height": height, "length": length,
            "ref_image_size": "match",
            "ref_images.ref_image_0": ["56", 0],
            "ref_videos.ref_video_0": ["82", 0]}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {
            "model": ["shift", 0], "scheduler": "simple", "steps": VIDEO_STEPS, "denoise": 1.0}},
        "16": {"class_type": "BasicGuider", "inputs": {
            "model": ["shift", 0], "conditioning": ["104", 0]}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
            "sigmas": ["9", 0], "latent_image": ["104", 1]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["11", 0]}},
        "23": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["24", 0]}},
        "91": {"class_type": "CreateVideo", "inputs": {
            "images": ["10", 0], "audio": ["23", 0], "fps": float(VIDEO_FPS), "bit_depth": 8}},
        "92": {"class_type": "SaveVideo", "inputs": {
            "video": ["91", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "92"


def _add_runtime_arguments(parser):
    """Add runtime options to both root and subparser for ergonomic placement."""
    parser.add_argument(
        "--comfy-url", dest="comfy_url", default=argparse.SUPPRESS,
        help="ComfyUI base URL；優先於 COMFY_URL/COMFYUI_URL 與 --config。",
    )
    parser.add_argument(
        "--config", "--runtime-config", dest="config_path", default=argparse.SUPPRESS,
        help="明確指定含 comfyui_url 的 runtime JSON（不會自動搜尋 repo local_config.json）。",
    )
    parser.add_argument(
        "--video-config", dest="video_config_path", default=argparse.SUPPRESS,
        help=("明確指定 machine-specific video_capabilities.json；影片不會從 task 名稱猜測 "
              "H3/Wan。未指定時可由 --config 的 video_config 或 ComfyUI/tools/video_capabilities.json 找到。"),
    )
    parser.add_argument(
        "--timeout", type=float, default=argparse.SUPPRESS,
        help=(f"prompt 送達後輪詢生成結果的秒數上限；圖片預設 {DEFAULT_TIMEOUT:g}，"
              f"影片預設 {DEFAULT_VIDEO_TIMEOUT:g}。"),
    )


def _validate_cli_args(args):
    default_timeout = DEFAULT_VIDEO_TIMEOUT if args.task in VIDEO_TASK_CAPS else DEFAULT_TIMEOUT
    args.timeout = getattr(args, "timeout", default_timeout)
    validate_timeout(args.timeout)
    if args.task in {"concept", "icon_asset", "character_action", "pose_only", "style_lock"}:
        validate_batch(args.batch)
        validate_lora_strength(args.lora_strength)
    if args.task in {"concept", "character_action", "pose_only", "style_lock", "icon_asset"}:
        validate_dimensions(args.width, args.height)
    if args.task == "flux2_concept":
        validate_flux2_dimensions(args.width, args.height)
    if args.task in {"inpaint", "guided_inpaint", "refine", "upscale"}:
        validate_unit_interval(args.denoise, "denoise")
    if args.task == "upscale":
        validate_scale(args.scale)
    if args.task in {"character_action", "style_lock"}:
        validate_unit_interval(args.ip_weight, "ip_weight")
    if args.task in {"character_action", "pose_only"}:
        validate_unit_interval(args.pose_strength, "pose_strength")
    if args.task == "icon_asset":
        validate_unit_interval(args.appearance_weight, "appearance_weight")
    if args.task == "guided_inpaint":
        validate_unit_interval(args.control_strength, "control_strength")
        validate_unit_interval(args.appearance_weight, "appearance_weight")
    if args.task in VIDEO_TASK_CAPS and args.width is not None and args.height is not None:
        validate_dimensions(args.width, args.height)
    if args.task in VIDEO_TASKS:
        _safe_identifier(getattr(args, "shot_id", None), "--shot-id")
        _safe_identifier(getattr(args, "name", None), "--name")
        if getattr(args, "resume", False) and args.task != "video_concat" and not (
                getattr(args, "shot_id", None) or getattr(args, "name", None)):
            raise ValueError("--resume 需要 --name 或 --shot-id 才能精確定位輸出")
    if args.task in ("video_concat", "video_composite"):
        _safe_identifier(args.name, "--name")
        _safe_identifier(getattr(args, "shot_id", None), "--shot-id")


def _validate_task_capabilities(args):
    try:
        if args.task == "character_action":
            require_sdxl_capability("character_action (ControlNet/IPAdapter)")
        elif args.task == "pose_only":
            require_sdxl_capability("pose_only (ControlNet)")
        elif args.task == "style_lock":
            require_sdxl_capability("style_lock (IPAdapter)")
        elif args.task == "icon_asset":
            if args.structure_ref:
                require_sdxl_capability("icon_asset 的 structure-ref/ControlNet")
            if args.appearance_ref:
                require_sdxl_capability("icon_asset 的 appearance-ref/IPAdapter")
        elif args.task == "guided_inpaint":
            if args.control_type:
                require_sdxl_capability("guided_inpaint 的 ControlNet")
            if args.appearance_ref:
                require_sdxl_capability("guided_inpaint 的 IPAdapter")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


def main(argv=None):
    global ACTIVE_VIDEO_CONFIG
    # A process may invoke main() more than once in tests or an embedding. Do
    # not let a previous machine config leak into a later task.
    ACTIVE_VIDEO_CONFIG = None
    ap = argparse.ArgumentParser(description="穩定產圖核心腳本")
    _add_runtime_arguments(ap)
    sub = ap.add_subparsers(dest="task", required=True)

    # 共用參數:每個 task 都能指定成品要存去哪(不指定就用預設的 tools/generated/)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-dir", help=f"成品存放資料夾,預設 {OUTPUT_DIR}")
    _add_runtime_arguments(common)

    # 會用到底模 checkpoint 的 task 額外共用 --style(layer_split 純裁切、不吃底模,不套用這組)
    model_common = argparse.ArgumentParser(add_help=False, parents=[common])
    model_common.add_argument(
        "--style", choices=list(STYLE_CHECKPOINTS),
        help="換一顆風格底模(選配,不給就用這台機器裝機時鎖定的預設 checkpoint)。"
             "realistic=寫實(Juggernaut XL)、illustration=插畫/概念藝術(Illustrious XL)、"
             "anime=二次元/動漫(Pony Diffusion V6 XL)。需要先在這台機器裝好對應 checkpoint,"
             "見 skills/comfyui-install/reference/models.md;只支援 SDXL 家族 tier。",
    )
    model_common.add_argument(
        "--rating", choices=["safe", "questionable", "explicit"],
        help="內容分級標籤(選配,不給就不加任何分級標籤,prompt 完全不變)。"
             "只在 --style anime/illustration 時有意義——這兩顆底模訓練時就用分級標籤控制內容尺度,"
             "不是這裡另外加的過濾機制;--style realistic 或不給 --style 時使用這個選項會直接報錯。",
    )

    # 有 --prompt 的 task(全部除了 layer_split)都共用 --negative/--seed
    prompt_common = argparse.ArgumentParser(add_help=False, parents=[model_common])
    prompt_common.add_argument("--negative")
    prompt_common.add_argument("--seed", type=int)

    # 從零/從參考圖生成的探索型 task(concept/icon_asset/character_action/pose_only/style_lock)
    # 才支援「多生幾版比較」跟套 LoRA——inpaint/guided_inpaint/refine/upscale 是修改既有圖片,
    # 這兩個概念對它們沒有意義,不要因為想共用參數就硬塞給不適用的 task
    batch_lora_common = argparse.ArgumentParser(add_help=False, parents=[prompt_common])
    batch_lora_common.add_argument("--batch", type=int, default=1, help="一次生成幾個版本比較")
    batch_lora_common.add_argument("--lora", help="LoRA 檔名(models/loras/ 底下),不給就不套用")
    batch_lora_common.add_argument("--lora-strength", type=float, default=0.8)

    p_concept = sub.add_parser("concept", help="概念圖(純文字)", parents=[batch_lora_common])
    p_concept.add_argument("--prompt", required=True)
    p_concept.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_concept.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_concept.add_argument("--remove-bg", action="store_true")

    # Experimental FLUX.2 tasks are deliberately separate from model_common:
    # --style/--rating/SDXL LoRA and negative prompts are not compatible with
    # this backend and must not appear to be supported by parser inheritance.
    p_flux2_concept = sub.add_parser(
        "flux2_concept",
        help="實驗性 FLUX.2 Klein 4B 蒸餾版概念圖(4 steps；不取代 SDXL concept)",
        parents=[common],
    )
    p_flux2_concept.add_argument("--prompt", required=True)
    p_flux2_concept.add_argument("--width", type=int, default=1024)
    p_flux2_concept.add_argument("--height", type=int, default=1024)
    p_flux2_concept.add_argument("--seed", type=int)

    p_flux2_edit = sub.add_parser(
        "flux2_edit",
        help="實驗性 FLUX.2 Klein 4B base 單參考圖語意編輯(輸出約一百萬像素)",
        parents=[common],
    )
    p_flux2_edit.add_argument("--prompt", required=True, help="要如何修改來源圖")
    p_flux2_edit.add_argument("--image", required=True, help="來源／參考圖路徑")
    p_flux2_edit.add_argument("--seed", type=int)

    p_icon = sub.add_parser("icon_asset", help="單一小型 UI 圖示/物件素材(不是整個 UI 畫面),永遠去背輸出透明背景", parents=[batch_lora_common])
    p_icon.add_argument("--prompt", required=True)
    p_icon.add_argument("--width", type=int, default=1024)
    p_icon.add_argument("--height", type=int, default=1024)
    p_icon.add_argument("--structure-ref", help="這個圖示的結構/色塊配置已經有明確答案、不該讓 AI 自己瞎猜時用(例如放射狀精準等分):給一張範本圖路徑,用 img2img + Canny ControlNet 把結構跟顏色配置都鎖住,SDXL 只負責疊材質/光澤;不給就跟以前一樣純靠文字描述。範本圖從哪來見 skills/comfyui-art-gen/reference/structure-ref.md")
    p_icon.add_argument("--appearance-ref", help="外觀參考圖路徑(選用,例如使用者提供的一張成品圖,想讓畫面材質/質感偏向那張圖)——用 IPAdapter,不給就純靠文字描述外觀,原則同 guided_inpaint 的 --appearance-ref")
    p_icon.add_argument("--appearance-weight", type=float, default=0.8, help="外觀參考圖的貼合強度,原則同 --ip-weight")

    p_char = sub.add_parser("character_action", help="角色動作圖(角色參考圖 + 姿勢線稿)", parents=[batch_lora_common])
    p_char.add_argument("--prompt", required=True)
    p_char.add_argument("--character-ref", required=True, help="角色參考圖路徑")
    p_char.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_char.add_argument("--ip-weight", type=float, default=0.8)
    p_char.add_argument("--pose-strength", type=float, default=1.0)
    p_char.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="姿勢/構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_char.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_char.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_char.add_argument("--remove-bg", action="store_true")

    p_inpaint = sub.add_parser("inpaint", help="局部調整(需要來源圖 + 遮罩圖)", parents=[prompt_common])
    p_inpaint.add_argument("--prompt", required=True)
    p_inpaint.add_argument("--image", required=True, help="來源圖路徑")
    p_inpaint.add_argument("--mask", required=True, help="遮罩圖路徑(需帶 alpha 通道,要重畫的區域 alpha=0/透明,其餘 alpha=255/不透明——用 ComfyUI MaskEditor 存的檔案格式一定對)")
    p_inpaint.add_argument("--denoise", type=float, default=1.0)

    p_guided = sub.add_parser(
        "guided_inpaint",
        help="局部重繪 + 結構鎖定/外觀參考圖(遮罩範圍內可選擇鎖住結構、可選擇用一張圖決定外觀,而不是只能靠文字描述;用於換武器/道具但要保持握姿、套用美術自畫材質紋理這類需求)",
        parents=[prompt_common],
    )
    p_guided.add_argument("--prompt", required=True)
    p_guided.add_argument("--image", required=True, help="來源圖路徑")
    p_guided.add_argument("--mask", required=True, help="遮罩圖路徑(同 inpaint,需帶 alpha 通道,要重畫的區域 alpha=0)")
    p_guided.add_argument("--control-ref", help="結構引導來源圖路徑,不給就用 --image 本身(從同一張圖抽取結構);沒給 --control-type 的話這個參數沒作用")
    p_guided.add_argument("--control-type", choices=["canny", "pose", "depth"],
                           help="要鎖定的結構類型(選用,不給就不鎖結構):pose=骨架關節(手部/肢體動作類需求),canny=輪廓邊緣、depth=立體起伏(材質/紋路類需求)")
    p_guided.add_argument("--control-strength", type=float, default=1.0)
    p_guided.add_argument("--appearance-ref", help="外觀參考圖路徑(選用,例如美術自己畫的材質/紋理圖)——不給就純靠文字描述外觀。建議用乾淨的材質特寫,不要整張場景圖,不然背景/光影會一起被帶進來")
    p_guided.add_argument("--appearance-weight", type=float, default=0.8, help="外觀參考圖的貼合強度,原則同 --ip-weight")
    p_guided.add_argument("--denoise", type=float, default=1.0)

    p_pose = sub.add_parser("pose_only", help="單獨用姿勢/線稿控制構圖,不鎖角色一致性", parents=[batch_lora_common])
    p_pose.add_argument("--prompt", required=True)
    p_pose.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_pose.add_argument("--pose-strength", type=float, default=1.0)
    p_pose.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_pose.add_argument(
        "--control-backend", choices=["verified", "union"], default="verified",
        help="ControlNet 後端；verified=既有三顆正式模型(預設)，union=實驗性 xinsir ProMax A/B",
    )
    p_pose.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_pose.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_pose.add_argument("--remove-bg", action="store_true")

    p_style = sub.add_parser("style_lock", help="單獨鎖角色/風格一致性,姿勢隨意(不需要姿勢參考圖)", parents=[batch_lora_common])
    p_style.add_argument("--prompt", required=True)
    p_style.add_argument("--character-ref", required=True, help="角色/風格參考圖路徑")
    p_style.add_argument("--ip-weight", type=float, default=0.8)
    p_style.add_argument("--width", type=int, default=DEVICE["default_width"])
    p_style.add_argument("--height", type=int, default=DEVICE["default_height"])
    p_style.add_argument("--remove-bg", action="store_true")

    p_refine = sub.add_parser("refine", help="圖生圖:草稿精緻化 / 材質顏色變體(保留原圖構圖)", parents=[prompt_common])
    p_refine.add_argument("--prompt", required=True)
    p_refine.add_argument("--image", required=True, help="來源圖路徑(草稿或要換材質的圖)")
    p_refine.add_argument("--denoise", type=float, default=0.6, help="0.3~0.4 大致保留構圖只上色;0.6~0.7 細節大幅改變;0.9+ 幾乎重畫")
    p_refine.add_argument("--remove-bg", action="store_true")

    p_upscale = sub.add_parser("upscale", help="放大精修(放大模型 + 二次取樣補細節,不是單純拉大)", parents=[prompt_common])
    p_upscale.add_argument("--prompt", required=True, help="用來引導二次取樣補細節,通常沿用原本生成這張圖時的 prompt")
    p_upscale.add_argument("--image", required=True, help="來源圖路徑(要放大的圖)")
    p_upscale.add_argument("--scale", type=float, default=2.0, help="相對原圖的放大倍率(預設 2 倍),最高 4 倍")
    p_upscale.add_argument("--denoise", type=float, default=0.4, help="二次取樣補細節的強度:太低細節補不夠,太高會偏離原圖構圖")

    p_layer = sub.add_parser(
        "layer_split",
        help="把一張已定稿的完成圖依遮罩切出單一圖層(不重新生成內容,純粹裁切透明度)——用於複合式 UI 元件想事後拆出幾個大塊可疊放區域,拆一層呼叫一次",
        parents=[common],
    )
    p_layer.add_argument("--image", required=True, help="來源圖路徑(已定稿的完成圖)")
    p_layer.add_argument("--mask", required=True, help="這一層的遮罩圖路徑(同 inpaint 慣例,需帶 alpha 通道,要保留進這一層的區域 alpha=0)")
    p_layer.add_argument("--layer-name", required=True, help="這一層的名稱,用來組輸出檔名前綴(例如 border、center_hub)")

    video_common = argparse.ArgumentParser(add_help=False, parents=[common])
    video_common.add_argument(
        "--backend", choices=list(VIDEO_BACKENDS), default=argparse.SUPPRESS,
        help=("影片實作後端；不給時只使用 capability config 明確設定的 default_backend，"
              "不會無條件預設 H3。某個 task 若還沒接這個 backend，會直接報錯。"),
    )
    video_common.add_argument(
        "--overwrite", action="store_true",
        help="明確允許覆寫同名影片輸出；預設拒絕以免重跑破壞既有素材。",
    )
    video_common.add_argument(
        "--shot-id", help="安全鏡號；用於可追溯的輸出檔名前綴，例如 A01。",
    )
    video_common.add_argument(
        "--name", help="安全輸出檔名前綴；指定後優先於 --shot-id。",
    )
    video_common.add_argument(
        "--resume", action="store_true",
        help="只在同名影片 sidecar 的 task/backend/seed/input/config/contract 全相符且重新驗證通過時跳過",
    )

    p_vid = sub.add_parser(
        "img2video",
        help="讓已過關的靜幀動起來(短片)。跟圖片產線的 --style / ControlNet / IPAdapter 不相容。",
        parents=[video_common],
    )
    p_vid.add_argument("--prompt", required=True, help="這段要怎麼動(鏡頭鎖定/運鏡/動作),英文較穩")
    p_vid.add_argument("--image", required=True, help="已過關的靜幀路徑,不要用文生影片賭第一幀")
    p_vid.add_argument("--duration", type=float, default=2.0,
                        help="秒數,鎖在 2~6(預設 2)。更長要拆鏡,不要一次生整部片")
    p_vid.add_argument("--width", type=int, help="輸出寬,不給就跟來源圖比例走,最長邊上限 768")
    p_vid.add_argument("--height", type=int, help="輸出高,不給就跟來源圖比例走,最長邊上限 768")
    p_vid.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_vid.add_argument("--seed", type=int)
    p_vid.add_argument("--extract-frames", action="store_true", help="順便抽 png 序列到 <mp4 檔名>_frames/")

    p_fx = sub.add_parser(
        "fx_loop",
        help="鏡頭鎖定的循環特效/環境元素(火、法陣、旗幟)。要能接首尾幀的 backend。預設抽幀交引擎。",
        parents=[video_common],
    )
    p_fx.add_argument("--prompt", required=True, help="循環怎麼動,會自動補上 seamless loop 約束")
    p_fx.add_argument("--image", required=True, help="特效/元件的靜幀")
    p_fx.add_argument("--duration", type=float, default=2.0, help="秒數,鎖在 2~6,預設 2")
    p_fx.add_argument("--width", type=int)
    p_fx.add_argument("--height", type=int)
    p_fx.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_fx.add_argument("--seed", type=int)
    p_fx.add_argument("--no-extract-frames", dest="extract_frames", action="store_false",
                      help="不要抽 png 序列(預設會抽)")
    p_fx.set_defaults(extract_frames=True)

    p_tr = sub.add_parser(
        "transition",
        help="內容轉場:已知 A、已知 B,模型只負責中間。要能接首尾幀的 backend。傳統硬切/疊化不要用這個。",
        parents=[video_common],
    )
    p_tr.add_argument("--prompt", required=True, help="中間發生什麼")
    p_tr.add_argument("--start", required=True, help="起始靜幀")
    p_tr.add_argument("--end", required=True, help="結束靜幀")
    p_tr.add_argument("--duration", type=float, default=2.0)
    p_tr.add_argument("--width", type=int)
    p_tr.add_argument("--height", type=int)
    p_tr.add_argument("--seed", type=int)
    p_tr.add_argument("--extract-frames", action="store_true")

    p_ext = sub.add_parser(
        "clip_extend",
        help="同一場下一鏡:吃上一支 mp4 的最後一幀(或一張靜幀)再往後生成。長片連戲用這個,不要拉長單次 duration。",
        parents=[video_common],
    )
    p_ext.add_argument("--prompt", required=True, help="接下來發生什麼")
    p_ext.add_argument("--video", help="上一支 mp4,會抽最後一幀當本鏡靜幀")
    p_ext.add_argument("--image", help="若已有上一鏡尾幀靜幀,跟 --video 二選一")
    p_ext.add_argument("--duration", type=float, default=2.0)
    p_ext.add_argument("--width", type=int)
    p_ext.add_argument("--height", type=int)
    p_ext.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_ext.add_argument("--seed", type=int)
    p_ext.add_argument("--extract-frames", action="store_true")

    p_cat = sub.add_parser(
        "video_concat",
        help="把多支已生成的短片接成一支(外部組裝,不是剪接台)。解析度跟第一支對齊。每支都有音軌才接立體聲。",
        parents=[common],
    )
    p_cat.add_argument("--video", action="append", required=True, help="可重複給多次,順序就是播放順序")
    p_cat.add_argument("--name", default="video_concat", help="輸出檔名前綴,預設 video_concat")
    p_cat.add_argument(
        "--overwrite", action="store_true",
        help="明確允許覆寫既有輸出；預設拒絕以免重跑破壞既有素材。",
    )
    p_cat.add_argument(
        "--resize-mode", choices=["strict", "fit", "fill", "stretch"], default="strict",
        help="尺寸不一致時的明確處理；預設 strict 拒絕，fit 加黑邊，fill 裁切，stretch 拉伸。",
    )
    p_cat.add_argument(
        "--audio-policy", choices=["require-consistent", "drop", "silence-missing"],
        default="require-consistent",
        help="混合有聲/無聲的處理；預設拒絕，drop 丟掉全部音訊，silence-missing 補靜音。",
    )
    p_cat.add_argument("--shot-id", help="安全鏡號，供 concat sidecar 追溯。")
    p_cat.add_argument("--resume", action="store_true", help="驗證既有 concat sidecar 後才跳過。")

    p_comp = sub.add_parser(
        "video_composite",
        help=(
            "把綠幕前景疊到背景(影片或靜態圖)上——chroma key，純本機 PyAV+numpy 逐幀合成，"
            "不經 ComfyUI、不呼叫任何生成模型。前景必須是本產線輸出的綠幕素材(見"
            "comfyui-video-gen skill)。目前不支援 --resume。"
        ),
        parents=[common],
    )
    p_comp.add_argument("--foreground", required=True, help="綠幕前景 mp4(產線輸出，24fps)")
    p_comp.add_argument("--background", required=True, help="背景 mp4(24fps)或靜態圖片")
    p_comp.add_argument(
        "--chroma-color", default="00FF00",
        help="去背色碼,6 碼十六進位,預設純綠 00FF00(跟這條產線的綠幕素材慣例一致)",
    )
    p_comp.add_argument(
        "--tolerance", type=float, default=60.0,
        help="判定為背景色的色距門檻,0..255,預設 60；數值越大摳得越乾淨但邊緣越容易吃色",
    )
    p_comp.add_argument(
        "--softness", type=float, default=40.0,
        help="邊緣羽化寬度,0(不含)..255,預設 40；數值越小邊緣越銳利但越容易有鋸齒/色邊",
    )
    p_comp.add_argument(
        "--resize-mode", choices=["strict", "fit", "fill", "stretch"], default="fill",
        help="背景尺寸跟前景不同時的處理；預設 fill 裁切填滿(背景本來就少有跟前景同尺寸的情況)，"
             "strict 拒絕，fit 加黑邊，stretch 拉伸。",
    )
    p_comp.add_argument("--name", default="video_composite", help="輸出檔名前綴,預設 video_composite")
    p_comp.add_argument(
        "--overwrite", action="store_true",
        help="明確允許覆寫既有輸出；預設拒絕以免重跑破壞既有素材。",
    )
    p_comp.add_argument("--shot-id", help="安全鏡號，供 sidecar 追溯。")

    p_cam = sub.add_parser(
        "camera_move",
        help="攝影組運鏡:主體盡量靜止,只有攝影機在動。--camera 是鎖死枚舉。",
        parents=[video_common],
    )
    p_cam.add_argument("--image", required=True, help="已過關的靜幀")
    p_cam.add_argument(
        "--camera", required=True, choices=list(CAMERA_MOVES),
        help="運鏡:static/pan_up/pan_down/pan_left/pan_right/zoom_in/zoom_out/orbit_cw/orbit_ccw",
    )
    p_cam.add_argument(
        "--prompt", default="",
        help="選填場景描述。不給就當主體完全靜止;運鏡以 --camera 為準,不要在這裡另寫一種運鏡",
    )
    p_cam.add_argument("--duration", type=float, default=2.0)
    p_cam.add_argument("--width", type=int)
    p_cam.add_argument("--height", type=int)
    p_cam.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_cam.add_argument("--seed", type=int)
    p_cam.add_argument("--extract-frames", action="store_true")

    p_cv = sub.add_parser(
        "character_video",
        help="角色參考生影片:參考圖鎖身份,第一幀不必是那張定稿圖。對應靜態 style_lock,不是 img2video。",
        parents=[video_common],
    )
    p_cv.add_argument("--prompt", required=True, help="新鏡頭裡這個角色在做什麼(英文較穩)")
    p_cv.add_argument(
        "--character-ref", action="append", required=True,
        help="角色參考圖,可重複給最多 9 張(多角度/特寫較穩)。第一張同時決定預設畫布比例",
    )
    p_cv.add_argument("--duration", type=float, default=2.0, help="秒數,鎖在 2~6,預設 2")
    p_cv.add_argument("--width", type=int)
    p_cv.add_argument("--height", type=int)
    p_cv.add_argument("--seed", type=int)
    p_cv.add_argument("--extract-frames", action="store_true")

    p_pd = sub.add_parser(
        "pose_drive",
        help="表演驅動:角色靜幀 + 動作參考影片。對應靜態 character_action,姿勢來源是影片不是一張 pose 圖。",
        parents=[video_common],
    )
    p_pd.add_argument("--prompt", required=True, help="這段鏡頭裡角色在做什麼(英文較穩)")
    p_pd.add_argument("--image", required=True, help="角色參考靜幀(這是誰)")
    p_pd.add_argument("--motion-ref", required=True, help="動作參考影片(這段怎麼動)")
    p_pd.add_argument(
        "--control-type", choices=["canny", "pose", "depth"], default="pose",
        help="動作怎麼抽:pose=骨架(預設,表演/肢體),canny=邊緣,depth=前後景",
    )
    p_pd.add_argument("--duration", type=float, default=2.0, help="秒數,鎖在 2~6,預設 2。長過參考影片的部分控制會變弱")
    p_pd.add_argument("--width", type=int)
    p_pd.add_argument("--height", type=int)
    p_pd.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_pd.add_argument("--seed", type=int)
    p_pd.add_argument("--extract-frames", action="store_true")

    args = ap.parse_args(argv)
    try:
        _validate_cli_args(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    style_checkpoint = None
    if getattr(args, "style", None):
        if DEVICE.get("tier") not in ("sdxl_high", "sdxl", "sdxl_light"):
            raise SystemExit(
                f"--style 目前只支援 SDXL 家族機器(sdxl_high/sdxl/sdxl_light),"
                f"這台機器偵測到的 tier 是 {DEVICE.get('tier')!r}。"
                f"這幾個風格 checkpoint 都是 SDXL 架構,跟 sd15 tier 的 ControlNet/IPAdapter 對不上,"
                f"直接送出去 ComfyUI 執行期會 shape mismatch。"
            )
        style_checkpoint = STYLE_CHECKPOINTS[args.style]

    if getattr(args, "rating", None):
        if args.style not in RATING_TAGS:
            raise SystemExit(
                f"--rating 只在 --style anime/illustration 時有意義(這兩顆底模訓練資料本身用分級標籤"
                f"控制內容尺度),目前 --style={args.style!r} 沒有這個標籤慣例,加了也沒效果,直接擋下來。"
            )
        args.prompt = f"{RATING_TAGS[args.style][args.rating]}, {args.prompt}"

    _validate_task_capabilities(args)
    # video_concat/video_composite 只在本機用 PyAV(+numpy)組裝既有影片，不會上傳、排程或
    # 下載 ComfyUI output；因此不能因為共用 parser 就強迫它們先解析 ComfyUI URL。
    comfy_url = None
    if args.task not in ("video_concat", "video_composite"):
        comfy_url = resolve_comfy_url(getattr(args, "comfy_url", None), getattr(args, "config_path", None))
    request_timeout = min(DEFAULT_HTTP_TIMEOUT, float(args.timeout))

    if args.task in {"flux2_concept", "flux2_edit"}:
        try:
            validate_flux2_capability(args.task, comfy_url, request_timeout=request_timeout)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc

    if args.task == "pose_only" and args.control_backend == "union":
        try:
            validate_controlnet_union_capability(
                comfy_url, request_timeout=request_timeout,
            )
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc

    if args.task in VIDEO_TASKS:
        try:
            args.backend = configure_video_capability(
                args.task,
                requested_backend=getattr(args, "backend", None),
                runtime_config_path=getattr(args, "config_path", None),
                video_config_path=getattr(args, "video_config_path", None),
                comfy_url=comfy_url,
                request_timeout=request_timeout,
                control_type=getattr(args, "control_type", None),
            )
        except (RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc

    # Resolve randomness exactly once before any video graph is built. Every
    # builder receives this integer, and the same value is persisted in the
    # output sidecar for reproducibility/resume checks.
    if args.task in VIDEO_TASKS:
        args.seed = seed_or_random(getattr(args, "seed", None))

    video_started = (
        time.monotonic()
        if args.task in VIDEO_TASKS or args.task in ("video_concat", "video_composite")
        else None
    )
    video_contract = None
    video_inputs = []
    continuity_refs = {}
    video_prompt = getattr(args, "prompt", "")
    video_negative = getattr(args, "negative", None)
    video_prefix = None

    def upload(path):
        return upload_image(path, comfy_url=comfy_url, request_timeout=request_timeout)

    if args.task == "concept":
        prompt, out_id = build_concept(args.prompt, args.negative, args.width, args.height, args.seed,
                                        batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
                                        checkpoint=style_checkpoint)
    elif args.task == "flux2_concept":
        prompt, out_id = build_flux2_concept(
            args.prompt, width=args.width, height=args.height, seed=args.seed,
        )
    elif args.task == "flux2_edit":
        img_fn = upload(args.image)
        prompt, out_id = build_flux2_edit(args.prompt, img_fn, seed=args.seed)
    elif args.task == "icon_asset":
        structure_fn = upload(args.structure_ref) if args.structure_ref else None
        appearance_fn = upload(args.appearance_ref) if args.appearance_ref else None
        prompt, out_id = build_icon_asset(args.prompt, args.negative, args.width, args.height, args.seed,
                                           batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
                                           structure_ref_filename=structure_fn, checkpoint=style_checkpoint,
                                           appearance_ref_filename=appearance_fn, appearance_weight=args.appearance_weight)
    elif args.task == "character_action":
        char_fn = upload(args.character_ref)
        pose_fn = upload(args.pose_ref)
        prompt, out_id = build_character_action(
            args.prompt, char_fn, pose_fn, args.negative,
            width=args.width, height=args.height,
            seed=args.seed, ip_weight=args.ip_weight, pose_strength=args.pose_strength,
            batch_size=args.batch, control_type=args.control_type,
            lora_name=args.lora, lora_strength=args.lora_strength, checkpoint=style_checkpoint,
        )
    elif args.task == "inpaint":
        img_fn = upload(args.image)
        mask_fn = upload(args.mask)
        prompt, out_id = build_inpaint(args.prompt, img_fn, mask_fn, args.negative,
                                        denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint)
    elif args.task == "guided_inpaint":
        img_fn = upload(args.image)
        mask_fn = upload(args.mask)
        control_fn = None
        if args.control_type:
            control_fn = upload(args.control_ref) if args.control_ref else img_fn
        appearance_fn = upload(args.appearance_ref) if args.appearance_ref else None
        prompt, out_id = build_guided_inpaint(
            args.prompt, img_fn, mask_fn, args.negative,
            control_ref_filename=control_fn, control_type=args.control_type, control_strength=args.control_strength,
            appearance_ref_filename=appearance_fn, appearance_weight=args.appearance_weight,
            denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint,
        )
    elif args.task == "pose_only":
        pose_fn = upload(args.pose_ref)
        prompt, out_id = build_pose_only(args.prompt, pose_fn, args.negative,
                                          width=args.width, height=args.height,
                                          seed=args.seed, pose_strength=args.pose_strength,
                                          batch_size=args.batch, control_type=args.control_type,
                                          lora_name=args.lora, lora_strength=args.lora_strength,
                                          checkpoint=style_checkpoint,
                                          control_backend=args.control_backend)
    elif args.task == "style_lock":
        char_fn = upload(args.character_ref)
        prompt, out_id = build_style_lock(args.prompt, char_fn, args.negative,
                                           width=args.width, height=args.height,
                                           seed=args.seed, ip_weight=args.ip_weight,
                                           batch_size=args.batch,
                                           lora_name=args.lora, lora_strength=args.lora_strength,
                                           checkpoint=style_checkpoint)
    elif args.task == "refine":
        img_fn = upload(args.image)
        prompt, out_id = build_refine(args.prompt, img_fn, args.negative,
                                       denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint)
    elif args.task == "upscale":
        img_fn = upload(args.image)
        prompt, out_id = build_upscale(args.prompt, img_fn, args.negative,
                                        scale=args.scale, denoise=args.denoise, seed=args.seed,
                                        checkpoint=style_checkpoint)
    elif args.task == "layer_split":
        img_fn = upload(args.image)
        mask_fn = upload(args.mask)
        prompt, out_id = build_layer_split(img_fn, mask_fn, args.layer_name)
    elif args.task == "img2video":
        backend = require_video_backend(args.task, args.backend, ACTIVE_VIDEO_CONFIG)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        video_inputs = [args.image]
        continuity_refs = {"source": args.image}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = run_i2v(
            backend, args.prompt, img_fn, width, height, args.seed, duration,
            filename_prefix=video_prefix, negative=args.negative,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "fx_loop":
        backend = require_video_backend(args.task, args.backend, ACTIVE_VIDEO_CONFIG)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        loop_prompt = args.prompt if "loop" in args.prompt.lower() else f"{args.prompt}, {VIDEO_LOOP_SUFFIX}"
        video_prompt = loop_prompt
        video_inputs = [args.image]
        continuity_refs = {"source": args.image}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = run_i2v(
            backend, loop_prompt, img_fn, width, height, args.seed, duration,
            last_image_filename=img_fn, filename_prefix=video_prefix, negative=args.negative,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "transition":
        backend = require_video_backend(args.task, args.backend, ACTIVE_VIDEO_CONFIG)
        duration = _require_video_duration(args.duration)
        if (args.width is None) ^ (args.height is None):
            raise SystemExit("--width 跟 --height 要一起給,或兩個都不給。")
        try:
            validate_transition_images(args.start, args.end)
        except (OSError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        width, height = video_canvas(args.start, args.width, args.height)
        start_fn = upload(args.start)
        end_fn = upload(args.end)
        video_inputs = [args.start, args.end]
        continuity_refs = {"start": args.start, "end": args.end}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = run_i2v(
            backend, args.prompt, start_fn, width, height, args.seed, duration,
            last_image_filename=end_fn, filename_prefix=video_prefix,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "clip_extend":
        if bool(args.video) == bool(args.image):
            raise SystemExit("clip_extend 要 --video 上一支 mp4,或 --image 上一鏡尾幀,只能給一個。")
        backend = require_video_backend(args.task, args.backend, ACTIVE_VIDEO_CONFIG)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        still = args.image
        temp_still = None
        if args.video:
            if os.path.isfile(os.path.abspath(os.fspath(args.video))):
                try:
                    validate_video_input(args.video, label="clip_extend --video", min_duration=VIDEO_INPUT_MIN_DURATION)
                except (RuntimeError, ValueError) as exc:
                    raise SystemExit(str(exc)) from exc
            out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
            temp_still = _make_temp_image_path(out_dir, "_clip_extend_last_")
            try:
                extract_last_frame(args.video, temp_still)
                print(f"[連戲] 上一鏡尾幀 -> {temp_still}")
                still = temp_still
                width, height = video_canvas(still, args.width, args.height)
                img_fn = upload(still)
            finally:
                _remove_temp_file(temp_still)
        else:
            width, height = video_canvas(still, args.width, args.height)
            img_fn = upload(still)
        video_inputs = [args.video] if args.video else [args.image]
        continuity_refs = {"source": still} if args.image else {}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = run_i2v(
            backend, args.prompt, img_fn, width, height, args.seed, duration,
            filename_prefix=video_prefix, negative=args.negative,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "video_concat":
        out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
        try:
            if all(os.path.isfile(os.path.abspath(os.fspath(path))) for path in args.video):
                input_metadata = [
                    validate_video_input(path, label=f"video_concat input[{index}]")
                    for index, path in enumerate(args.video)
                ]
            else:
                # concat_videos performs the authoritative open/decode check;
                # this fallback only keeps mocked local callers from needing
                # real media while still failing safely in production.
                input_metadata = [{
                    "path": os.path.abspath(os.fspath(path)), "width": 0, "height": 0,
                    "fps": VIDEO_FPS, "frames": 0, "duration_seconds": 0.0, "audio": False,
                } for path in args.video]
        except (RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        if args.audio_policy == "require-consistent":
            audio_flags = [bool(item["audio"]) for item in input_metadata]
            if any(audio_flags) and not all(audio_flags):
                raise SystemExit(
                    "video_concat 輸入音訊不一致；預設拒絕混合有聲/無聲。"
                    "請明確給 --audio-policy drop 或 silence-missing"
                )
        expected_audio = (
            False if args.audio_policy == "drop" else
            any(item["audio"] for item in input_metadata)
        )
        video_inputs = list(args.video)
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        total_frames = sum(item["frames"] for item in input_metadata)
        total_duration = sum(item["duration_seconds"] for item in input_metadata)
        video_contract = make_video_contract(
            args.task, "local", input_metadata[0]["width"], input_metadata[0]["height"],
            duration=total_duration, audio_expected=expected_audio,
            expected_frames=total_frames, frame_tolerance=VIDEO_FRAME_TOLERANCE,
            input_metadata=input_metadata,
        )
        video_contract["resize_mode"] = args.resize_mode
        video_contract["audio_policy"] = args.audio_policy
        try:
            dest = _safe_output_path(out_dir, f"{video_prefix}.mp4")
        except (TypeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        os.makedirs(out_dir, exist_ok=True)
        if args.resume:
            try:
                metadata = resume_video_output(
                    dest, args.task, "local", None, video_inputs, None, video_contract,
                )
            except (RuntimeError, VideoContractError) as exc:
                raise SystemExit(str(exc)) from exc
            print(f"[恢復] {dest}")
            return
        concat_kwargs = {"allow_overwrite": args.overwrite}
        if args.resize_mode != "strict":
            concat_kwargs["resize_mode"] = args.resize_mode
        if args.audio_policy != "require-consistent":
            concat_kwargs["audio_policy"] = args.audio_policy
        concat_videos(args.video, dest, **concat_kwargs)
        print(f"[完成] {dest}")
        elapsed = time.monotonic() - video_started if video_started else None
        report_contract = None if any(item["width"] == 0 for item in input_metadata) else video_contract
        metadata = report_video_output(
            dest, task="video_concat", backend="local", elapsed_seconds=elapsed,
            **({"expected_contract": report_contract} if report_contract is not None else {}),
        )
        write_video_sidecar(
            dest, args.task, "local", None, "", "", video_inputs, None,
            video_contract, metadata, elapsed_seconds=elapsed,
        )
        return
    elif args.task == "video_composite":
        out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
        background_is_video = (
            os.path.splitext(args.background)[1].lower() in VIDEO_COMPOSITE_BACKGROUND_EXTS
        )
        try:
            if os.path.isfile(os.path.abspath(os.fspath(args.foreground))):
                fg_metadata = validate_video_input(args.foreground, label="video_composite --foreground")
            else:
                # composite_videos performs the authoritative open/decode check;
                # this fallback only keeps mocked local callers from needing
                # real media while still failing safely in production.
                fg_metadata = {
                    "path": os.path.abspath(os.fspath(args.foreground)), "width": 0, "height": 0,
                    "fps": VIDEO_FPS, "frames": 0, "duration_seconds": 0.0, "audio": False,
                }
            if background_is_video and os.path.isfile(os.path.abspath(os.fspath(args.background))):
                validate_video_input(args.background, label="video_composite --background")
        except (RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        video_inputs = [args.foreground, args.background]
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        video_contract = make_video_contract(
            args.task, "local", fg_metadata["width"], fg_metadata["height"],
            duration=fg_metadata["duration_seconds"], audio_expected=fg_metadata["audio"],
            expected_frames=fg_metadata["frames"], frame_tolerance=VIDEO_FRAME_TOLERANCE,
            input_metadata=[fg_metadata],
        )
        video_contract["resize_mode"] = args.resize_mode
        video_contract["chroma_color"] = args.chroma_color
        video_contract["tolerance"] = args.tolerance
        video_contract["softness"] = args.softness
        try:
            dest = _safe_output_path(out_dir, f"{video_prefix}.mp4")
        except (TypeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        os.makedirs(out_dir, exist_ok=True)
        try:
            composite_videos(
                args.foreground, args.background, dest,
                chroma_color=args.chroma_color, tolerance=args.tolerance, softness=args.softness,
                resize_mode=args.resize_mode, allow_overwrite=args.overwrite,
            )
        except (RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        print(f"[完成] {dest}")
        elapsed = time.monotonic() - video_started if video_started else None
        report_contract = None if fg_metadata["width"] == 0 else video_contract
        metadata = report_video_output(
            dest, task="video_composite", backend="local", elapsed_seconds=elapsed,
            **({"expected_contract": report_contract} if report_contract is not None else {}),
        )
        write_video_sidecar(
            dest, args.task, "local", None, "", "", video_inputs, None,
            video_contract, metadata, elapsed_seconds=elapsed,
        )
        return
    elif args.task == "character_video":
        backend = require_video_backend(args.task, args.backend, ACTIVE_VIDEO_CONFIG)
        refs = args.character_ref
        if len(refs) > CHARACTER_REF_MAX:
            raise SystemExit(
                f"--character-ref 最多 {CHARACTER_REF_MAX} 張,目前 {len(refs)}"
            )
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(refs[0], args.width, args.height)
        ref_fns = [upload(p) for p in refs]
        video_inputs = list(refs)
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = run_character_video(
            backend, args.prompt, ref_fns, width, height, args.seed, duration,
            filename_prefix=video_prefix,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "camera_move":
        backend = require_video_backend(args.task, args.backend, ACTIVE_VIDEO_CONFIG)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        video_inputs = [args.image]
        continuity_refs = {"source": args.image}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        cam_prompt = camera_move_prompt(args.camera, args.prompt)
        last_fn = None
        end_path = None
        try:
            if backend_has(backend, "last_frame"):
                if args.camera == "static":
                    last_fn = img_fn
                elif args.camera not in ("orbit_cw", "orbit_ccw"):
                    out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
                    end_path = _make_temp_image_path(out_dir, "_camera_end_")
                    build_camera_end_still(args.image, args.camera, width, height, end_path)
                    print(f"[運鏡] 終點靜幀 -> {end_path}")
                    last_fn = upload(end_path)
            prompt, out_id = run_i2v(
                backend, cam_prompt, img_fn, width, height, args.seed, duration,
                last_image_filename=last_fn, filename_prefix=video_prefix,
                negative=args.negative,
            )
        finally:
            _remove_temp_file(end_path)
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "pose_drive":
        backend = require_video_backend(args.task, args.backend, ACTIVE_VIDEO_CONFIG)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        print(
            "[提醒] pose_drive 的角色靜幀姿勢/朝向要接近動作片第一幀;"
            "對不上(例如站姿去套走路)會雙人/重影。",
            file=sys.stderr,
        )
        try:
            # Keep the cheap FPS-specific diagnostic first; the full decode
            # preflight follows and catches empty/truncated references.
            validate_motion_reference_fps(args.motion_ref)
            validate_video_input(
                args.motion_ref, label="pose_drive --motion-ref",
                min_duration=duration, require_fps=VIDEO_FPS,
            )
        except (RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        motion_fn = upload(args.motion_ref)
        video_inputs = [args.image, args.motion_ref]
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = run_pose_drive(
            backend, args.prompt, img_fn, motion_fn, width, height, args.seed, duration,
            control_type=args.control_type, filename_prefix=video_prefix,
            negative=args.negative,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    else:
        raise SystemExit(f"未知 task: {args.task}")

    if args.task in VIDEO_TASKS:
        if video_contract is None or video_prefix is None:
            raise RuntimeError(f"影片 task {args.task} 沒有建立輸出契約或安全命名")
        if args.resume:
            out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
            candidate = _find_named_video_output(out_dir, video_prefix)
            if candidate is None:
                raise SystemExit(
                    f"--resume 找不到唯一的 {video_prefix!r} mp4 + sidecar；"
                    "不確定狀態不會猜測或重新送出工作"
                )
            try:
                metadata = resume_video_output(
                    candidate, args.task, args.backend, args.seed, video_inputs,
                    ACTIVE_VIDEO_CONFIG, video_contract,
                )
            except (RuntimeError, VideoContractError) as exc:
                raise SystemExit(str(exc)) from exc
            print(f"[恢復] {candidate}")
            return

    target_output_id = None
    if args.task == "icon_asset" or getattr(args, "remove_bg", False):
        target_output_id = attach_bg_removal(prompt, out_id)

    print(f"[送出] task={args.task}")
    try:
        history = submit_and_wait(prompt, timeout=args.timeout, comfy_url=comfy_url)
    except VideoTimeoutError as exc:
        if args.task in VIDEO_TASKS:
            out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
            prefix = video_prefix or video_filename_prefix(args.task)
            write_video_timeout_record(
                out_dir, prefix, args.task, getattr(args, "backend", None),
                getattr(args, "seed", None), video_prompt, video_negative,
                video_inputs, ACTIVE_VIDEO_CONFIG, video_contract, exc,
            )
        raise
    paths = download_outputs(
        history,
        output_dir=getattr(args, "output_dir", None),
        node_ids=[target_output_id] if target_output_id else None,
        comfy_url=comfy_url,
        request_timeout=request_timeout,
        allow_overwrite=(getattr(args, "overwrite", False) if args.task in VIDEO_TASKS else True),
    )
    if args.task in VIDEO_TASKS:
        video_paths = [path for path in paths if path.lower().endswith(".mp4")]
        if not video_paths:
            raise RuntimeError(f"影片 task {args.task} 沒有產生 mp4 output，已拒絕把錯誤輸出當成成功")
    else:
        video_paths = []
    for p in paths:
        print(f"[完成] {p}")
        if p.lower().endswith(".mp4") and args.task in VIDEO_TASKS:
            elapsed = time.monotonic() - video_started if video_started else None
            try:
                metadata = report_video_output(
                    p, task=args.task, backend=args.backend,
                    elapsed_seconds=elapsed, expected_contract=video_contract,
                    continuity_refs=continuity_refs,
                )
            except VideoContractError as exc:
                # Persist the decoded evidence even for a failed contract so
                # operators can diagnose a bad render without treating it as success.
                write_video_sidecar(
                    p, args.task, args.backend, args.seed, video_prompt, video_negative,
                    video_inputs, ACTIVE_VIDEO_CONFIG, video_contract,
                    exc.metadata or {"validation": {"status": "fail", "errors": exc.errors}},
                    prompt_id=history.get("_prompt_id") if isinstance(history, dict) else None,
                    elapsed_seconds=elapsed, warnings=exc.warnings,
                )
                raise
            write_video_sidecar(
                p, args.task, args.backend, args.seed, video_prompt, video_negative,
                video_inputs, ACTIVE_VIDEO_CONFIG, video_contract, metadata,
                prompt_id=history.get("_prompt_id") if isinstance(history, dict) else None,
                elapsed_seconds=elapsed,
            )
            if getattr(args, "extract_frames", False):
                frame_paths, frame_dir = extract_video_frames(
                    p, getattr(args, "output_dir", None)
                )
                if len(frame_paths) != metadata["frames"]:
                    raise RuntimeError(
                        f"抽幀數量與影片不一致: video={metadata['frames']}, "
                        f"frames={len(frame_paths)}, dir={frame_dir}"
                    )
                print(f"[幀驗證] task={args.task} backend={args.backend} frames={len(frame_paths)} dir={frame_dir}")


if __name__ == "__main__":
    main()
