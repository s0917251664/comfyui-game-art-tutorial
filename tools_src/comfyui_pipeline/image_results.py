"""Opt-in technical manifests for successful image task outputs.

These checks describe files and graph metadata only. They do not assess whether
an image is artistically suitable for a game asset.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile


SCHEMA_VERSION = 1
KIND = "image_generation_result"
PROFILE_DIR = Path(__file__).with_name("profiles")


def validate_manifest_path(path):
    """Return a normalized manifest destination, rejecting unsafe targets early."""
    if not isinstance(path, (str, os.PathLike)) or not os.fspath(path).strip():
        raise ValueError("--result-json 需要有效的檔案路徑")
    raw = os.path.abspath(os.path.expanduser(os.fspath(path)))
    if os.path.isdir(raw):
        raise ValueError(f"--result-json 必須是檔案路徑，不可指定資料夾: {raw}")
    if os.path.lexists(raw):
        raise FileExistsError(f"拒絕覆寫既有 result manifest: {raw}")
    parent = os.path.dirname(raw)
    if not os.path.isdir(parent):
        raise ValueError(f"--result-json 的父資料夾不存在: {parent}")
    if not raw.lower().endswith(".json"):
        raise ValueError("--result-json 路徑必須以 .json 結尾")
    return raw


def graph_sha256(graph):
    encoded = json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolved_seeds(graph):
    """Extract all concrete seeds from the exact graph being submitted."""
    found = {}
    for node_id, node in graph.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for key in ("seed", "noise_seed"):
            value = inputs.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                found.setdefault(str(node_id), {})[key] = value
    return found


def selected_models(graph):
    """Record model file inputs from loader nodes in the submitted graph."""
    result = []
    model_keys = {
        "ckpt_name", "control_net_name", "ipadapter_file", "clip_name",
        "bg_removal_name", "model_name", "unet_name", "vae_name", "lora_name",
    }
    for node_id, node in graph.items():
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            continue
        for key, value in node["inputs"].items():
            if key in model_keys and isinstance(value, str):
                result.append({
                    "node_id": str(node_id), "class_type": node.get("class_type"),
                    "input": key, "filename": value,
                })
    return result


def profile_digest(profile_id):
    if profile_id is None:
        return None
    path = PROFILE_DIR / f"{profile_id}.json"
    if not path.is_file():
        raise ValueError(f"無法找到實際選用的圖片 profile: {path}")
    # 內容雜湊(不含 validation 區塊):記錄驗證證據不會讓既有 manifest 綁的 profile hash 失效。
    from . import profiles as _profiles
    return _profiles.profile_content_sha256(json.loads(path.read_text(encoding="utf-8")))


def effective_conditioning(graph):
    return [
        {"node_id": str(node_id), "class_type": node.get("class_type"), "text": node["inputs"]["text"]}
        for node_id, node in graph.items()
        if isinstance(node, dict) and isinstance(node.get("inputs"), dict)
        and isinstance(node["inputs"].get("text"), str)
        and "TextEncode" in str(node.get("class_type", ""))
    ]


def task_parameters(args, outputs, seeds, inputs):
    """Persist resolved, non-secret task options needed to understand a rerun."""
    keys = (
        "negative", "width", "height", "denoise", "scale", "batch",
        "lora", "lora_strength", "style", "rating", "ip_weight", "pose_strength",
        "control_type", "control_backend", "control_strength", "appearance_weight",
        "layer_name", "remove_bg", "appearance_ref", "structure_ref", "control_ref",
    )
    values = {}
    for key in keys:
        value = getattr(args, key, None)
        if value is not None:
            values[key] = value
    prompt = getattr(args, "requested_prompt", getattr(args, "prompt", None))
    if prompt is not None:
        values["prompt"] = prompt
    paths_by_role = {}
    for item in inputs:
        paths_by_role.setdefault(item["role"], []).append(item["path"])
    if paths_by_role:
        values["input_paths"] = paths_by_role
    if len(seeds) == 1:
        only = next(iter(seeds.values()))
        if len(only) == 1:
            values["seed"] = next(iter(only.values()))
    values["actual_dimensions"] = [
        {"width": item["width"], "height": item["height"]} for item in outputs
    ]
    return values


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_records(paths):
    records = []
    seen = set()
    for item in paths:
        if isinstance(item, dict):
            role, path = item.get("role", "input"), item.get("path")
        else:
            role, path = "input", item
        if not path:
            continue
        absolute = os.path.abspath(os.fspath(path))
        identity = (str(role), os.path.normcase(os.path.realpath(absolute)))
        if identity in seen:
            continue
        seen.add(identity)
        if not os.path.isfile(absolute):
            raise ValueError(f"圖片 task 輸入檔案不存在: {absolute}")
        records.append({"role": str(role), "path": absolute, "sha256": _sha256_file(absolute)})
    return records


def graph_output_dimensions(graph):
    dimensions = set()
    for node in graph.values():
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            continue
        inputs = node["inputs"]
        if "LatentImage" in str(node.get("class_type", "")):
            width, height = inputs.get("width"), inputs.get("height")
            if isinstance(width, int) and isinstance(height, int):
                dimensions.add((width, height))
    if len(dimensions) == 1:
        width, height = next(iter(dimensions))
        return {"width": width, "height": height}
    return None


def validate_png_outputs(paths, *, expected_dimensions=None, require_alpha=False,
                         require_transparency=False):
    """Decode every image and capture factual PNG dimensions/channel metadata."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("--result-json 需要 Pillow 才能驗證 PNG output") from exc
    records = []
    errors = []
    for path in paths:
        if not str(path).lower().endswith(".png"):
            continue
        absolute = os.path.abspath(os.fspath(path))
        try:
            with Image.open(absolute) as image:
                image_format = image.format
                width, height = image.size
                mode = image.mode
                image.load()
                if image_format != "PNG":
                    raise ValueError(f"檔案實際格式為 {image_format!r}，不是 PNG")
                has_alpha_channel = "A" in image.getbands() or "transparency" in image.info
                if "A" in image.getbands():
                    alpha = image.getchannel("A")
                    has_transparency = alpha.getextrema()[0] < 255
                elif "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    has_transparency = rgba.getchannel("A").getextrema()[0] < 255
                else:
                    has_transparency = False
            if width <= 0 or height <= 0:
                raise ValueError("尺寸不是正整數")
            if expected_dimensions and (width, height) != (
                    expected_dimensions["width"], expected_dimensions["height"]):
                raise ValueError(
                    f"尺寸 {width}x{height} 與 graph latent 輸出尺寸 "
                    f"{expected_dimensions['width']}x{expected_dimensions['height']} 不符"
                )
            if require_alpha and not has_alpha_channel:
                raise ValueError("輸出缺少 alpha channel")
            if require_transparency and not has_transparency:
                raise ValueError("輸出沒有實際透明像素")
            records.append({
                "path": absolute, "sha256": _sha256_file(absolute),
                "width": int(width), "height": int(height), "mode": mode,
                "has_alpha_channel": bool(has_alpha_channel),
                "has_transparency": bool(has_transparency),
            })
        except (OSError, ValueError) as exc:
            errors.append(f"{absolute}: PNG 無法讀取或尺寸無效 ({exc})")
    if not records:
        errors.append("沒有可讀取的 PNG output")
    if errors:
        raise ValueError("圖片 technical validation 失敗: " + "; ".join(errors))
    return records


def make_manifest(*, task, profile_id, backend, prompt_id, graph, inputs, outputs, args=None,
                  technical_warnings=None):
    seeds = resolved_seeds(graph)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "status": "completed",
        "task": task,
        "profile_id": profile_id,
        "profile_sha256": profile_digest(profile_id),
        "backend": backend,
        "prompt_id": prompt_id,
        "resolved_seeds": seeds,
        "graph_output_dimensions": graph_output_dimensions(graph),
        "graph_sha256": graph_sha256(graph),
        "selected_models": selected_models(graph),
        "effective_conditioning": effective_conditioning(graph),
        "inputs": inputs,
        "outputs": outputs,
        "task_parameters": task_parameters(args, outputs, seeds, inputs) if args is not None else {},
        "technical_validation": {
            "status": "pass",
            "checks": ["png_readable", "positive_dimensions", "sha256_recorded"],
            "warnings": list(technical_warnings or []),
        },
        "content_review": "pending",
    }


def write_manifest_atomic(path, manifest):
    """Create the JSON atomically without replacing an existing destination."""
    path = validate_manifest_path(path)
    payload = (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    fd, temp_path = tempfile.mkstemp(prefix=".image-result-", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link creation is atomic and fails if a destination appeared since validation.
        os.link(temp_path, path)
    except FileExistsError as exc:
        raise FileExistsError(f"拒絕覆寫既有 result manifest: {path}") from exc
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
    return path
