"""圖片 task 的送出前檢查:/object_info 比對、image_capabilities.json、設定檔選用、FLUX.2/ControlNet Union preflight。

從 generate.py 抽出。
"""
import os
import sys

from . import image_graphs as _image_graphs
from . import profiles as _profiles
from .client import (
    DEFAULT_HTTP_TIMEOUT, _read_runtime_config, _relative_config_path, _runtime_config_path_from_env,
)
from .image_graphs import DEVICE_CONFIG_PATH
from .client import _fetch_comfy_object_info


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


IMAGE_GRAPH_TASKS = frozenset((
    "concept", "flux2_concept", "flux2_edit", "icon_asset", "character_action", "inpaint",
    "guided_inpaint", "pose_only", "style_lock", "refine", "upscale", "layer_split",
))
# 走模型設定檔(profiles/*.json)的圖片 task;FLUX.2 另有 validate_flux2_capability。
IMAGE_PROFILE_TASKS = IMAGE_GRAPH_TASKS - {"flux2_concept", "flux2_edit"}
PREFLIGHT_IMAGE_PLACEHOLDER = "__preflight_input__.png"
# 會載入模型檔的 loader node 與它的檔名 input;送出前逐一比對 /object_info 的選項清單。
IMAGE_MODEL_INPUTS = {
    "CheckpointLoaderSimple": "ckpt_name",
    "ControlNetLoader": "control_net_name",
    "IPAdapterModelLoader": "ipadapter_file",
    "CLIPVisionLoader": "clip_name",
    "LoadBackgroundRemovalModel": "bg_removal_name",
    "UpscaleModelLoader": "model_name",
    "LoraLoader": "lora_name",
}


def _object_info_options(payload, node_name, input_name):
    """讀 combo 選項;同時支援舊格式 [[...], {...}] 與新格式 ["COMBO", {"options": [...]}]。"""
    try:
        inputs = payload[node_name]["input"]
    except (KeyError, TypeError):
        return None
    for section in ("required", "optional"):
        spec = (inputs.get(section) or {}).get(input_name) if isinstance(inputs, dict) else None
        if not isinstance(spec, (list, tuple)) or not spec:
            continue
        if isinstance(spec[0], list):
            return spec[0]
        if spec[0] == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
            options = spec[1].get("options")
            if isinstance(options, list):
                return options
    return None


def check_image_graph_against_object_info(graph, payload):
    """回傳 (缺少的 node class, 缺少的模型描述);兩者都空代表 ComfyUI 端具備這個 graph。"""
    classes = {node.get("class_type") for node in graph.values() if isinstance(node, dict)}
    missing_nodes = sorted(name for name in classes if name not in payload)
    missing_models = set()
    for node in graph.values():
        class_type = node.get("class_type")
        field = IMAGE_MODEL_INPUTS.get(class_type)
        if not field or class_type in missing_nodes:
            continue
        value = node.get("inputs", {}).get(field)
        options = _object_info_options(payload, class_type, field)
        if options is None:
            missing_models.add(f"{class_type}.{field}（ComfyUI node schema 讀不到模型清單）")
        elif value not in options:
            missing_models.add(f"{value}（{class_type}）")
    return missing_nodes, sorted(missing_models)


IMAGE_CAPABILITY_CONFIG_FILENAME = "image_capabilities.json"


def load_image_capabilities(runtime_config_path=None, image_config_path=None):
    """找 machine-specific image_capabilities.json,回傳 (config, source);找不到回傳 (None, None)。

    這份檔案是選配:找不到時圖片 task 沿用 device_config.json 的 tier 對應。查找順序是
    --image-config → --config 的 image_config → --config 的 comfyui_path/tools 或 generate_script 同目錄
    → device_config.json 同目錄。不搜尋 repository,理由同 video capability config。
    只有 --image-config 指向不存在的檔案才報錯;local_config.json 的 image_config 是安裝時預先寫好的
    路徑,步驟 8b 還沒跑時檔案本來就不存在,只提醒、不阻擋。
    """
    if image_config_path:
        source = os.path.abspath(os.fspath(image_config_path))
        return _read_runtime_config(source), source
    candidates = []
    runtime_path = _runtime_config_path_from_env(runtime_config_path)
    if runtime_path:
        runtime_path = os.path.abspath(os.fspath(runtime_path))
        runtime = _read_runtime_config(runtime_path)
        explicit = runtime.get("image_config")
        if explicit:
            source = os.path.abspath(_relative_config_path(explicit, runtime_path))
            if not os.path.exists(source):
                print(
                    f"[提醒] {runtime_path} 的 image_config 指向的 {source} 還不存在,"
                    "圖片 task 沿用 device_config.json 的 tier 對應;要啟用請執行 detect_image_capabilities.py。",
                    file=sys.stderr,
                )
                return None, None
            return _read_runtime_config(source), source
        if runtime.get("comfyui_path"):
            candidates.append(os.path.join(os.fspath(runtime["comfyui_path"]), "tools", IMAGE_CAPABILITY_CONFIG_FILENAME))
        if runtime.get("generate_script"):
            candidates.append(os.path.join(os.path.dirname(os.fspath(runtime["generate_script"])), IMAGE_CAPABILITY_CONFIG_FILENAME))
    candidates.append(os.path.join(os.path.dirname(DEVICE_CONFIG_PATH), IMAGE_CAPABILITY_CONFIG_FILENAME))
    existing = next((path for path in candidates if os.path.isfile(path)), None)
    if existing is None:
        return None, None
    source = os.path.abspath(existing)
    return _read_runtime_config(source), source


def _current_env(capabilities):
    """目前機器的環境指紋(供比對驗證證據);沒有快照路徑資訊或讀取失敗時回傳 None(不比對)。"""
    if not capabilities or not capabilities.get("comfyui_path"):
        return None
    try:
        from . import fingerprint as _fp
        return _profiles.env_from_components(
            _fp.compute_components(capabilities["comfyui_path"], capabilities.get("model_roots")))
    except Exception:
        return None


def resolve_image_profile(task, device, cli_profile=None, capabilities=None, capabilities_source=None):
    """決定這次圖片 task 用哪份模型設定檔;回傳 profile id,或 None 代表沿用 tier 對應。

    來源優先序:--profile → image_capabilities.json 的 default_profile → 無(tier 對應)。
    明確選用時一律檢查:設定檔存在、符合這台平台(後端/記憶體/精度)、提供這個 task;
    來自 capability 快照時再確認快照的設備指紋沒有過期。驗證狀態不是 verified 時只提醒、不阻擋。
    """
    if task not in IMAGE_PROFILE_TASKS:
        if cli_profile:
            raise RuntimeError(f"--profile 只適用於使用圖片模型設定檔的 task；{task} 不使用設定檔")
        return None
    if cli_profile:
        chosen, source = cli_profile, "--profile"
    else:
        chosen = (capabilities or {}).get("default_profile")
        source = f"{capabilities_source} 的 default_profile"
        if not chosen:
            return None
        if capabilities.get("device_fingerprint") != _profiles.device_fingerprint(device):
            raise RuntimeError(
                f"{capabilities_source} 與目前 device_config.json 的設備資料不一致（換過設備或重跑過 detect_device.py）；"
                "請在這台機器重跑 detect_image_capabilities.py"
            )
    profile = _profiles.load_profile(chosen)
    reasons = _profiles.platform_eligibility(profile, device)
    if reasons:
        raise RuntimeError(f"模型設定檔 {chosen!r}（來源：{source}）不適用這台機器：" + "；".join(reasons))
    if task not in profile["tasks"]:
        raise RuntimeError(
            f"模型設定檔 {chosen!r} 不提供 {task}；這個設定檔可用的 task：{', '.join(sorted(profile['tasks']))}"
        )
    env = _current_env(capabilities) if _profiles.needs_env(profile, device.get("platform_key")) else None
    status, reason = _profiles.effective_validation(
        profile, device.get("platform_key"), device.get("usable_memory_mb"), task, env,
    )
    if status == "verified_other_env":
        print(f"[提醒] 模型設定檔 {chosen} 的 {task}:{reason}。結果可能與驗證時不同(不阻擋)。", file=sys.stderr)
    elif status != "verified":
        print(
            f"[提醒] 模型設定檔 {chosen} 的 {task} 在這台機器的驗證狀態是 {status}"
            f"（{reason or '沒有額外說明'}），結果可能與已驗證平台不同。",
            file=sys.stderr,
        )
    return chosen


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
