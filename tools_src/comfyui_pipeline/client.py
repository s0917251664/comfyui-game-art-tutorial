"""ComfyUI HTTP client:URL 解析、上傳、排隊/輪詢、下載輸出。

從 generate.py 抽出。不依賴任何全域可變狀態:嵌入時的預設 URL 由呼叫端經 ``default_url`` 傳入
(cli 傳 ``RunContext.comfy_url``)。
"""
import json
import math
import mimetypes
import ntpath
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


# 成品預設輸出資料夾:部署時為 <tools>/generated(與 comfyui_pipeline 同層)。
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")

COMFY_URL_ENV_VARS = ("COMFY_URL", "COMFYUI_URL")
COMFY_CONFIG_ENV_VARS = (
    "COMFY_CONFIG", "COMFYUI_CONFIG", "COMFY_CONFIG_PATH", "COMFYUI_CONFIG_PATH",
)
DEFAULT_TIMEOUT = 180.0
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_POLL_TIMEOUT = 15.0
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_POLL_RETRIES = 3


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


def resolve_comfy_url(cli_url=None, config_path=None, default_url=None):
    """Resolve the ComfyUI URL with CLI > environment > explicit config priority.

    There is deliberately no automatic ``local_config.json`` lookup: a copied
    script must not accidentally connect to a path relative to the source repo.
    ``default_url`` is the embedding override (formerly ``generate.COMFY_URL``); it ranks
    after the environment variables, before the config file.
    """
    for candidate in (cli_url, *(os.environ.get(name) for name in COMFY_URL_ENV_VARS), default_url):
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


class VideoTimeoutError(TimeoutError):
    """Timeout carrying the exact ComfyUI prompt ownership information."""

    def __init__(self, message, prompt_id, queue_status=None):
        super().__init__(message)
        self.prompt_id = str(prompt_id)
        self.queue_status = queue_status or {"status": "unknown"}


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
