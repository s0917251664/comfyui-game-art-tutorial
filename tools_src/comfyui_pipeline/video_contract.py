"""影片輸出契約:contract、sidecar、resume、輸出檢查與連續性警告。

從 generate.py 抽出。
"""
import hashlib
import json
import math
import os
import re
import tempfile

from .runtime import facade as rt
from .video_catalog import (
    VIDEO_CONTRACT_SCHEMA_VERSION, VIDEO_DURATION_TOLERANCE, VIDEO_FPS, VIDEO_FPS_TOLERANCE,
    VIDEO_FRAME_TOLERANCE, VIDEO_SEAM_WARNING_THRESHOLD, VIDEO_SIDECAR_SCHEMA_VERSION,
)
from .video_graphs import h3_frame_count, wan_frame_count
from .video_media import _fps_fraction, _video_streams


class VideoContractError(RuntimeError):
    """An output was decoded but did not satisfy the caller's video contract."""

    def __init__(self, message, metadata=None, errors=None, warnings=None):
        super().__init__(message)
        self.metadata = metadata
        self.errors = list(errors or ())
        self.warnings = list(warnings or ())


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
    rt._require_pillow()
    a = image_a.convert("RGB").resize((64, 64), rt.PILImage.Resampling.BILINEAR)
    b = image_b.convert("RGB").resize((64, 64), rt.PILImage.Resampling.BILINEAR)
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
    first, last = rt._first_last_video_images(video_path)
    refs = references or {}
    pairs = []
    if task == "fx_loop":
        pairs.append(("seam", first, last))
    if refs.get("start") is not None:
        with rt.PILImage.open(refs["start"]) as image:
            pairs.append(("start", image.copy(), first))
    if refs.get("end") is not None:
        with rt.PILImage.open(refs["end"]) as image:
            pairs.append(("end", last, image.copy()))
    if refs.get("source") is not None:
        with rt.PILImage.open(refs["source"]) as image:
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
    metadata = rt.report_video_output(
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
