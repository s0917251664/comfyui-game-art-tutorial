"""`gameart.py run <template>` 的實際執行:preflight 通過後才會呼叫 :func:`execute`。

順序:pre 檢查(讀本機媒體)→ 上傳到 ComfyUI ``input/<run_id>/``(overwrite=false)→ 用上傳回傳的
``subfolder/name`` patch graph → POST /prompt(帶 client_id)→ 輪詢 history 直到成功、失敗或逾時 →
下載 template 宣告的 output node → post 檢查 → 寫 ``run.result.json``(kind ``template_run_result``)。

任何一步失敗都會寫 ``status: failed`` 的 manifest(``failure`` 記錄步驟、prompt_id、錯誤),已下載的檔案保留。
逾時不重送、不呼叫全域 /interrupt;只有確認是自己送出、還在 pending 的 prompt 才會從 queue 刪除。
技術檢查通過不等於美術接受:``content_review`` 一律是 pending,接受與否由人用 asset_review 記錄。
"""
import datetime
import hashlib
import json
import os
import platform
import re
import sys
import time
import urllib.request
import uuid

from .. import client as _client
from .. import image_results as IR
from . import media as _media
from . import steps as S
from . import template as T

KIND = "template_run_result"
SCHEMA_VERSION = 1
BACKEND = "template-runner"
DEFAULT_TIMEOUT = 1800
POLL_INTERVAL = 1.0
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

RESULT_FILE = "run.result.json"
UPLOADS_FILE = "uploads.json"
GRAPH_FILE = "workflow_api.json"
QUEUE_FILE = "queue.json"
HISTORY_FILE = "history.json"
LOG_FILE = "run.log"
PREFLIGHT_FILE = "preflight.json"
OUTPUTS_DIR = "outputs"

ACCEPTANCE = "pending human review;技術檢查通過不等於美術接受"
SYSTEM_STATS_TIMEOUT = 10.0


class RunFailure(Exception):
    def __init__(self, step, error, **extra):
        super().__init__(error)
        self.step, self.error, self.extra = step, error, extra


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def default_output_dir(repo_root, template_id, run_id, today=None):
    today = today or datetime.date.today()
    name = f"{today:%Y%m%d}-{template_id.replace('/', '-')}-{run_id[:8]}"
    return os.path.join(repo_root, "output", "runs", name)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def directory_record(path):
    """資料夾輸入(例如遮罩 PNG 序列)的紀錄:檔案數與 ``名稱\\0sha256`` 逐行排序後的 sha256。"""
    absolute = os.path.abspath(path)
    lines = []
    for name in sorted(os.listdir(absolute)):
        full = os.path.join(absolute, name)
        if os.path.isfile(full):
            lines.append(f"{name}\0{sha256_file(full)}\n")
    digest = hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()
    return {"path": absolute, "kind": "directory", "files": len(lines), "sha256": digest}


def _derived_record(item):
    """post 步驟產生的檔案(例如貼回的 MP4 或 PNG 資料夾)。"""
    path = item.get("path")
    if path and os.path.isdir(path):
        return dict(directory_record(path), role=item["role"])
    record = {"role": item["role"], "path": path}
    if path and os.path.isfile(path):
        record.update(sha256=sha256_file(path), size_bytes=os.path.getsize(path))
    return record


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


class _Log:
    """同時印到 stdout(立即 flush)與 run.log。"""

    def __init__(self, folder, out):
        self.path, self.out = os.path.join(folder, LOG_FILE), out

    def __call__(self, line):
        print(f"[run] {line}", file=self.out, flush=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(f"{utc_now()} {line}\n")


def system_stats(comfy_url):
    """GET /system_stats(best-effort;失敗回傳 None)。"""
    try:
        with urllib.request.urlopen(f"{comfy_url.rstrip('/')}/system_stats", timeout=SYSTEM_STATS_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001 - 只是記錄環境
        return None


def _environment(comfy_url, stats):
    system = (stats or {}).get("system") or {}
    devices = (stats or {}).get("devices") or []
    return {
        "comfy_url": comfy_url,
        "comfyui_version": system.get("comfyui_version"),
        "comfyui_python": system.get("python_version"),
        "pytorch_version": system.get("pytorch_version"),
        "devices": [d.get("name") for d in devices if isinstance(d, dict)],
        "runner_python": sys.version.split()[0],
        "runner_os": platform.platform(),
    }


def execution_seconds(history_entry):
    """history 的 execution_start 到結束訊息之間的秒數(ComfyUI 記錄的毫秒時間戳)。"""
    messages = ((history_entry or {}).get("status") or {}).get("messages") or []
    start = end = None
    for message in messages:
        if not isinstance(message, (list, tuple)) or len(message) < 2 or not isinstance(message[1], dict):
            continue
        kind, data = message[0], message[1]
        if kind == "execution_start":
            start = data.get("timestamp")
        elif kind in ("execution_success", "execution_error", "execution_interrupted"):
            end = data.get("timestamp")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end >= start:
        return round((end - start) / 1000.0, 3)
    return None


def describe_execution_error(history_entry):
    """回傳 (step, 訊息):被中斷是 ``interrupted``,其他是 ``execution``。"""
    messages = ((history_entry or {}).get("status") or {}).get("messages") or []
    for message in messages:
        if not isinstance(message, (list, tuple)) or len(message) < 2 or not isinstance(message[1], dict):
            continue
        kind, data = message[0], message[1]
        if kind == "execution_interrupted":
            return "interrupted", (f"ComfyUI 端中斷了這個 prompt(node {data.get('node_id')} "
                                   f"{data.get('node_type') or ''})".rstrip() + ")")
        if kind == "execution_error":
            return "execution", (f"node {data.get('node_id')}({data.get('node_type')})執行失敗:"
                                 f"{data.get('exception_type') or ''} {data.get('exception_message') or ''}".strip())
    status = (history_entry or {}).get("status") or {}
    return "execution", f"ComfyUI 回報失敗:status_str={status.get('status_str')!r}"


def _graph_value(response):
    name, subfolder = response.get("name"), response.get("subfolder") or ""
    if not isinstance(name, str) or not name or "/" in name or "\\" in name or name in (".", ".."):
        raise RuntimeError(f"ComfyUI upload 回傳的檔名不安全: {name!r}")
    return f"{subfolder}/{name}" if subfolder else name


def _history_items(node_out):
    items = []
    if isinstance(node_out, dict):
        for key in ("images", "videos", "gifs"):
            for item in node_out.get(key) or []:
                if isinstance(item, dict):
                    items.append((key, item))
    return items


def download(template, history_entry, folder, comfy_url, client):
    """逐檔下載 template 宣告的 outputs。回傳 ({output id: [記錄]}, 問題清單);部分失敗時已下載的保留。"""
    downloaded, problems = {}, []
    outputs = (history_entry or {}).get("outputs") or {}
    for decl in template.data["outputs"]:
        node = str(decl["node"])
        items = _history_items(outputs.get(node))
        downloaded[decl["id"]] = []
        if not items:
            problems.append(f"output {decl['id']}(node {node})在 history 裡沒有任何檔案")
            continue
        expect = decl.get("expect_count")
        if expect and len(items) != expect:
            problems.append(f"output {decl['id']}(node {node})應該有 {expect} 個檔案,history 列了 {len(items)} 個")
        dest = os.path.join(folder, OUTPUTS_DIR, decl["id"])
        for key, item in items:
            try:
                paths = client.download_outputs({"outputs": {node: {key: [item]}}}, dest, node_ids=[node],
                                                comfy_url=comfy_url, allow_overwrite=False)
            except Exception as exc:  # noqa: BLE001 - 單檔失敗不影響其他檔案
                problems.append(f"output {decl['id']} 的 {item.get('filename')!r} 下載失敗:{exc}")
                continue
            downloaded[decl["id"]].append({"path": os.path.abspath(paths[0]), "item": item})
    return downloaded, problems


def _output_records(template, downloaded, measured):
    decls = {d["id"]: d for d in template.data["outputs"]}
    records = []
    for output_id, entries in downloaded.items():
        decl = decls[output_id]
        for entry in entries:
            path = entry["path"]
            record = {"role": decl["role"], "output_id": output_id, "node": str(decl["node"]), "kind": decl["kind"],
                      "path": path, "sha256": sha256_file(path), "size_bytes": os.path.getsize(path),
                      "comfy": {k: entry["item"].get(k) for k in ("filename", "subfolder", "type")}}
            info = measured.get(path) or {}
            for key in ("width", "height", "frames", "fps", "fps_rational", "pts_uniform", "has_audio", "grayscale"):
                if key in info:
                    record[key] = info[key]
            records.append(record)
    return records


def _cleanup_history(entry):
    return {k: v for k, v in (entry or {}).items() if not str(k).startswith("_")}


def execute(template, resolution, settings, preflight, folder, *, run_id, timeout=DEFAULT_TIMEOUT, out=None,
            client=None, media=None, poll_interval=None):
    """執行並寫入 manifest。回傳 (結束碼, manifest, manifest 路徑);0=完成且技術檢查通過,1=失敗。
    ``client``／``media`` 預設是 comfyui_pipeline.client 與 media.py,測試可替換。"""
    out = out or sys.stdout
    client = client or _client
    media = media or _media
    poll_interval = POLL_INTERVAL if poll_interval is None else poll_interval
    folder = os.path.abspath(os.fspath(folder))
    log = _Log(folder, out)
    comfy_url = settings["comfy_url"]
    client_id = uuid.uuid4().hex
    started = time.monotonic()
    state = {"prompt_id": None, "queue": None, "history": None, "graph": None, "upload_paths": {},
             "inputs": [], "downloaded": {}, "measured": {}, "pre_checks": [], "post_checks": [],
             "warnings": list(preflight.get("warnings") or []), "keyframes": {},
             "mask_preview": None, "timing": {"started_at": utc_now()}, "step": "pre", "environment": None,
             "derived": []}
    failure = None

    def on_queued(prompt_id, response):
        state["prompt_id"] = prompt_id
        state["timing"]["queued_at"] = utc_now()
        state["queue"] = {"prompt_id": prompt_id, "client_id": client_id, "number": response.get("number"),
                          "queued_at": state["timing"]["queued_at"], "comfy_url": comfy_url}
        _write_json(os.path.join(folder, QUEUE_FILE), state["queue"])
        log(f"已送出 prompt_id={prompt_id};等待完成(上限 {timeout:g} 秒,不會重送)")

    context = {}
    try:
        for name, path in resolution["inputs"].items():
            if os.path.isdir(path):
                state["inputs"].append(dict(directory_record(path), role=name))
                continue
            if not os.path.isfile(path):
                continue  # preflight 已列為問題
            absolute = os.path.abspath(path)
            state["inputs"].append({"role": name, "path": absolute, "sha256": sha256_file(absolute),
                                    "size_bytes": os.path.getsize(absolute)})
        if preflight.get("status") != "pass":
            state["step"] = "preflight"
            raise RunFailure("preflight", ";".join(preflight.get("problems") or ["preflight 沒有通過"]))
        state["environment"] = _environment(comfy_url, system_stats(comfy_url))

        log("檢查輸入媒體")
        pre_results, state["pre_checks"], problems, warnings = S.run_pre_checks(
            template, resolution, media, work_dir=folder, context=context)
        state["pre_results"] = pre_results
        state["warnings"] += warnings
        if problems:
            raise RunFailure("pre", ";".join(problems))
        for name, path in context["generated"].items():  # pre 步驟產生、接著要上傳的檔案
            resolution["inputs"][name] = path
            state["inputs"].append({"role": name, "path": os.path.abspath(path), "sha256": sha256_file(path),
                                    "size_bytes": os.path.getsize(path), "generated": True})
            log(f"pre 步驟產生 {name}: {path}")
        try:
            for name in T.fill_from_pre(template, resolution, pre_results):
                log(f"slot {name} = {resolution['slot_values'][name]!r}(來自 {template.slots[name]['from_pre']})")
        except T.TemplateError as exc:
            raise RunFailure("pre", str(exc)) from exc

        state["step"] = "upload"
        records = {r["role"]: r for r in state["inputs"]}
        for name in S.uploaded_slots(template.data.get("pre")):
            path = resolution["inputs"][name]
            try:
                response = client.upload_image(path, comfy_url, subfolder=run_id, overwrite=False, return_response=True)
                value = _graph_value(response)
            except Exception as exc:  # noqa: BLE001
                raise RunFailure("upload", f"上傳 {name}({path})失敗:{exc}") from exc
            state["upload_paths"][name] = value
            records[name]["upload"] = {"name": response.get("name"), "subfolder": response.get("subfolder") or "",
                                       "type": response.get("type") or "input", "graph_value": value}
            log(f"已上傳 {name} → input/{value}")
        _write_json(os.path.join(folder, UPLOADS_FILE),
                    {name: records[name]["upload"] for name in state["upload_paths"]})

        state["step"] = "patch"
        try:
            graph, _changes = T.patch(template, resolution, state["upload_paths"])
        except T.TemplateError as exc:
            raise RunFailure("patch", str(exc)) from exc
        state["graph"] = graph
        _write_json(os.path.join(folder, GRAPH_FILE), graph)

        state["step"] = "queue"
        try:
            entry = client.submit_and_wait(graph, timeout=timeout, comfy_url=comfy_url, poll_interval=poll_interval,
                                           client_id=client_id, require_success=True, on_queued=on_queued)
        except client.PromptExecutionError as exc:
            state["history"] = exc.history_entry
            step, message = describe_execution_error(exc.history_entry)
            raise RunFailure(step, message) from exc
        except client.VideoTimeoutError as exc:
            raise RunFailure("timeout", str(exc), queue_status=exc.queue_status) from exc
        except RuntimeError as exc:
            raise RunFailure("poll" if state["prompt_id"] else "queue", str(exc)) from exc
        except OSError as exc:  # 送出時連不上(URLError 是 OSError)
            raise RunFailure("queue", f"送出 /prompt 失敗:{exc}") from exc
        state["history"] = entry
        state["timing"]["finished_at"] = utc_now()
        log(f"ComfyUI 回報完成(status_str=success);ComfyUI 執行時間 {execution_seconds(entry)} 秒(history 記錄)")

        state["step"] = "download"
        state["downloaded"], problems = download(template, entry, folder, comfy_url, client)
        count = sum(len(v) for v in state["downloaded"].values())
        log(f"已下載 {count} 個檔案到 {os.path.join(folder, OUTPUTS_DIR)}")
        if problems:
            raise RunFailure("download", ";".join(problems))

        state["step"] = "post"
        outputs = {k: [e["path"] for e in v] for k, v in state["downloaded"].items()}
        checks, problems, warnings, artifacts = S.run_post_checks(template, resolution, pre_results, outputs,
                                                                  folder, media, context=context)
        state["post_checks"], state["measured"] = checks, artifacts["media"]
        state["derived"] = [_derived_record(item) for item in artifacts["derived"]]
        state["keyframes"], state["mask_preview"] = artifacts["keyframes"], artifacts["mask_preview"]
        state["warnings"] += warnings
        if problems:
            raise RunFailure("post", ";".join(problems))
    except RunFailure as exc:
        failure = {"step": exc.step, "error": exc.error, "prompt_id": state["prompt_id"], **exc.extra}
    except KeyboardInterrupt:
        failure = {"step": state["step"], "error": "使用者中斷(Ctrl+C)", "prompt_id": state["prompt_id"]}
        if state["prompt_id"] and not state["history"]:
            status = client._query_prompt_queue_status(state["prompt_id"], comfy_url, client.DEFAULT_HTTP_TIMEOUT)
            status = client._cancel_exact_pending_prompt(state["prompt_id"], comfy_url,
                                                         client.DEFAULT_HTTP_TIMEOUT, status)
            failure["queue_status"] = status
            if status.get("status") == "running":
                failure["note"] = "這個 prompt 仍在 ComfyUI 執行;runner 不會全域 interrupt,完成後輸出留在 ComfyUI 的 output 資料夾"
    except Exception as exc:  # noqa: BLE001 - 非預期錯誤也要留下 manifest(含 prompt_id)
        failure = {"step": state["step"], "error": f"非預期錯誤 {type(exc).__name__}: {exc}",
                   "prompt_id": state["prompt_id"]}
    if failure and failure.get("queue_status", {}).get("status") == "running" and "note" not in failure:
        failure["note"] = "這個 prompt 仍在 ComfyUI 執行;runner 不會全域 interrupt,也不會重送"

    if state["history"] is not None and state["prompt_id"]:
        _write_json(os.path.join(folder, HISTORY_FILE), {state["prompt_id"]: _cleanup_history(state["history"])})
    state["timing"].setdefault("finished_at", utc_now())
    state["timing"]["execution_seconds"] = execution_seconds(state["history"])
    state["timing"]["total_seconds"] = round(time.monotonic() - started, 3)

    manifest = build_manifest(template, resolution, settings, preflight, state, failure, run_id, client_id, folder)
    path = IR.write_manifest_atomic(os.path.join(folder, RESULT_FILE), manifest)
    if failure:
        log(f"失敗({failure['step']}):{failure['error']}")
        if failure.get("note"):
            log(failure["note"])
    else:
        log("技術檢查通過;美術是否接受仍待人工審查(asset_review)")
    for warning in state["warnings"]:
        log(f"提醒: {warning}")
    log(f"已寫入 {path}")
    return (1 if failure else 0), manifest, path


def build_manifest(template, resolution, settings, preflight, state, failure, run_id, client_id, folder):
    graph = state["graph"]
    platform_check = (preflight.get("checks") or {}).get("platform") or {}
    checks = state["pre_checks"] + state["post_checks"]
    if failure:
        tech_status = "fail"
    else:
        tech_status = "pass"
    models = []
    for model in template.data["models"]:
        row = {k: model.get(k) for k in ("role", "node", "input", "filename", "path", "size_bytes", "sha256")}
        if graph and str(model["node"]) in graph:
            row["graph_value"] = graph[str(model["node"])]["inputs"].get(model["input"])
        models.append(row)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "status": "failed" if failure else "completed",
        "task": template.id,
        "profile_id": None,
        "profile_sha256": None,
        "backend": BACKEND,
        "template": {"id": template.id, "version": template.version, "status": template.data["status"],
                     "graph_sha256": template.graph_sha256,
                     "graph_canonical_sha256": template.graph_canonical_sha256,
                     "template_json_sha256": template.template_json_sha256},
        "prompt_id": state["prompt_id"],
        "client_id": client_id,
        "run_id": run_id,
        "resolved_seeds": IR.resolved_seeds(graph) if graph else {},
        "seed_sources": resolution["seed_sources"],
        "graph_sha256": IR.graph_sha256(graph) if graph else None,
        "selected_models": models,
        "effective_conditioning": IR.effective_conditioning(graph) if graph else [],
        "slot_values": resolution["slot_values"],
        "options": resolution["options"],
        "inputs": state["inputs"],
        "outputs": _output_records(template, state["downloaded"], state["measured"]),
        "keyframes": {k: v["path"] for k, v in state["keyframes"].items()},
        "mask_preview": state["mask_preview"],
        "derived_outputs": state["derived"],
        "platform_key": settings.get("platform_key"),
        "platform_source": settings.get("platform_source"),
        "device_platform_key": settings.get("device_platform_key"),
        "platform_status": platform_check.get("status"),
        "allow_unverified_platform": bool(preflight.get("allow_unverified_platform")),
        "verify_hashes": bool(preflight.get("verify_hashes")),
        "environment": state["environment"],
        "timing": state["timing"],
        "technical_validation": {"status": tech_status, "checks": checks, "warnings": state["warnings"]},
        "content_review": "pending",
        "acceptance": ACCEPTANCE,
        "failure": failure,
        "files": sorted(name for name in (PREFLIGHT_FILE, UPLOADS_FILE, GRAPH_FILE, QUEUE_FILE, HISTORY_FILE, LOG_FILE)
                        if os.path.exists(os.path.join(folder, name))),
    }
