"""template 送出前的 preflight(PR 2.2):只讀,不上傳、不 queue。

檢查項目(任何一項不通過就擋下,不會往上傳／queue 走):

1. 設定:``--config`` 依 runtime_config 解析(相對路徑以 repo 根目錄為準),URL 沿用
   ``client.resolve_comfy_url`` 的優先順序(--comfy-url > COMFY_URL/COMFYUI_URL > 設定檔)。
2. 平台(D6):平台名稱來自機器快照 ``device_config.json`` 的 ``platform_key``(或 ``--platform-key``)。
   template 的 ``capability_gate.platforms`` 裡狀態不是 ``technical_pass`` 的平台(含沒列出的)預設拒絕,
   加 ``--allow-unverified-platform`` 才放行並記錄;``unsupported`` 一律拒絕。
3. graph 寫死 ``device: "cuda"`` 的節點(Mix 的 node 108):非 CUDA 平台預設拒絕,
   ``--allow-unverified-platform`` 時降為警告。graph 不改(D6)。
4. ComfyUI 連得上,``/object_info`` 有 graph 用到的每個 node class 與 model 對應的 input;
   選項是清單的 input,清單裡要有 template 寫的檔名。
5. 模型檔:``<comfyui_path>/<path>`` 存在且大小相符(D5);``--verify-hashes`` 才完整計算 sha256,
   以 (路徑, 大小, mtime) 快取。``auto_download: true`` 的模型(SAM2 下載器、DWPose)缺檔時節點會自己下載,
   所以一定要先確認檔案已在本機。
6. ComfyUI 版本(PR 3.2):``/system_stats`` 的 ``system.comfyui_version`` 低於 template 的
   ``min_comfyui_version`` 就擋下;讀不到或認不出版本只提醒,不擋。

結果的 ``status`` 是 ``pass`` 或 ``blocked``;``problems`` 是擋下的原因(每條都寫檢查了哪個路徑、怎麼修),
``warnings`` 不擋。實際執行(run.py)會先呼叫 :func:`run_preflight`,通過才上傳。
"""
import json
import os
import time
import urllib.request

from .. import client as _client
from .. import runtime_config as rc
from . import template as T

PASS = "pass"
BLOCKED = "blocked"
HASH_CACHE_NAME = ".hash-cache.json"
OBJECT_INFO_TIMEOUT = 15.0
SYSTEM_STATS_TIMEOUT = 10.0
ALLOW_FLAG = "--allow-unverified-platform"


class PreflightConfigError(RuntimeError):
    """設定本身有錯(結束碼 2),例如 --config 指到不存在的檔案。"""


# ---------- 設定 ----------

def resolve_settings(config=None, comfy_url=None, snapshot_dir=None, platform_key=None, *, script_dir,
                     cwd=None, isfile=os.path.isfile, pathmod=os.path, read_json=None):
    """決定設定檔、ComfyUI URL、comfyui_path、平台。設定錯誤丟 PreflightConfigError;
    找不到平台資訊時不丟錯,而是在結果的 ``platform_problem`` 說明(preflight 會擋下)。"""
    read_json = read_json or _read_json_or_none
    repo_root = rc.find_repo_root(script_dir, isfile=isfile, pathmod=pathmod)
    config_path, config_source = rc.choose_config_path(config, repo_root, cwd, isfile=isfile, pathmod=pathmod)
    if config_path and not isfile(config_path):
        relative = bool(config) and not pathmod.isabs(os.fspath(config))
        raise PreflightConfigError(f"設定檔不存在: {config_path}" + (
            f"(相對路徑以 repo 根目錄 {repo_root} 解析)" if relative and repo_root else ""))
    data = (read_json(config_path) or {}) if config_path else {}
    if config_path and not isinstance(data, dict):
        raise PreflightConfigError(f"設定檔不是 JSON object: {config_path}")
    try:
        url = _client.resolve_comfy_url(comfy_url, config_path)
    except (RuntimeError, ValueError) as exc:
        raise PreflightConfigError(str(exc)) from exc
    url_source = "--comfy-url" if comfy_url else next(
        (name for name in _client.COMFY_URL_ENV_VARS if os.environ.get(name)), "config")
    comfyui_path = rc.comfyui_path_from_config(data, config_path, pathmod=pathmod)
    settings = {
        "repo_root": repo_root, "config_path": config_path, "config_source": config_source,
        "comfy_url": url, "comfy_url_source": url_source, "comfyui_path": comfyui_path,
        "snapshot_dir": None, "platform_key": None, "platform_source": None, "device": {},
        "platform_problem": None, "device_platform_key": None, "platform_mismatch": None,
    }
    try:
        found, source = rc.find_snapshot_dir(script_dir, snapshot_dir, repo_root, comfyui_path, cwd,
                                             isfile=isfile, pathmod=pathmod)
        settings["snapshot_dir"] = found
        device = read_json(pathmod.join(found, rc.DEVICE_CONFIG_NAME)) or {}
        settings["device"] = device if isinstance(device, dict) else {}
    except rc.SnapshotNotFound as exc:
        if not platform_key:
            settings["platform_problem"] = (f"無法判斷平台:{exc}\n也可以用 --platform-key 明確指定"
                                            "(例如 windows-cuda、macos-mps)")
    settings["device_platform_key"] = settings["device"].get("platform_key")
    if platform_key:
        settings["platform_key"], settings["platform_source"] = platform_key, "--platform-key"
        if settings["device_platform_key"] and settings["device_platform_key"] != platform_key:
            settings["platform_mismatch"] = (
                f"--platform-key {platform_key} 與這台機器快照 "
                f"{pathmod.join(settings['snapshot_dir'], rc.DEVICE_CONFIG_NAME)} 的 platform_key "
                f"{settings['device_platform_key']} 不同;本次以 --platform-key 為準")
    elif settings["device"].get("platform_key"):
        settings["platform_key"] = settings["device"]["platform_key"]
        settings["platform_source"] = pathmod.join(settings["snapshot_dir"], rc.DEVICE_CONFIG_NAME)
    elif not settings["platform_problem"]:
        settings["platform_problem"] = (
            f"{pathmod.join(settings['snapshot_dir'], rc.DEVICE_CONFIG_NAME)} 沒有 platform_key(舊版快照);"
            "請在這台機器重跑 `gameart.py doctor --refresh`,或用 --platform-key 指定")
    return settings


def _read_json_or_none(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def platform_backend(platform_key):
    return platform_key.rsplit("-", 1)[-1] if platform_key and "-" in platform_key else None


# ---------- 平台 ----------

def check_platform(template, settings, allow_unverified=False):
    """回傳 (problems, warnings, info)。"""
    problems, warnings = [], []
    key = settings.get("platform_key")
    platforms = template.data["capability_gate"]["platforms"]
    info = {"platform_key": key, "source": settings.get("platform_source"), "status": None,
            "device_platform_key": settings.get("device_platform_key"), "allowed_by_flag": False}
    status = template.data["status"]
    if status == "retired":
        problems.append(f"template {template.id} 已 retired,不能再執行")
    elif status == "draft":
        warnings.append(f"template {template.id} 是 draft" + (
            f":{template.data['status_note']}" if template.data.get("status_note") else ""))
    if settings.get("platform_mismatch"):
        warnings.append(settings["platform_mismatch"])
    if not key:
        problems.append(settings.get("platform_problem") or "無法判斷平台")
        return problems, warnings, info
    entry = platforms.get(key)
    platform_status = entry["status"] if entry else "untested"
    info["status"] = platform_status
    known = "、".join(f"{k}={v['status']}" for k, v in platforms.items())
    if platform_status == "unsupported":
        problems.append(f"平台 {key} 對 {template.id} 標為 unsupported({known}),不能執行")
    elif platform_status != "technical_pass":
        note = f"(說明:{entry['notes']})" if entry and entry.get("notes") else ""
        reason = (f"平台 {key} 對 {template.id} 是 {platform_status}" if entry
                  else f"template {template.id} 沒有列出平台 {key}(視為 untested)")
        if allow_unverified:
            info["allowed_by_flag"] = True
            warnings.append(f"{reason}{note};因為加了 {ALLOW_FLAG} 才放行,結果只能當技術試驗")
        else:
            problems.append(f"{reason}{note}。各平台狀態:{known}。這個平台還沒有實測證據,預設不執行;"
                            f"確定要試就加 {ALLOW_FLAG}")
    mem = template.data["capability_gate"].get("min_memory_mb")
    usable = settings.get("device", {}).get("usable_memory_mb")
    if mem and isinstance(usable, (int, float)) and usable < mem:
        problems.append(f"可用記憶體 {usable} MB 少於 template 要求的 {mem} MB")
    elif mem and not isinstance(usable, (int, float)):
        warnings.append(f"template 要求至少 {mem} MB,但快照沒有 usable_memory_mb,無法檢查")
    return problems, warnings, info


def cuda_device_nodes(graph):
    """graph 裡 ``device`` input 寫死為 ``cuda`` 的節點 [(node_id, class_type)]。"""
    found = []
    for node_id in sorted(graph, key=lambda n: (len(n), n)):
        node = graph[node_id]
        if node.get("inputs", {}).get("device") == "cuda":
            found.append((node_id, node.get("class_type")))
    return found


def check_cuda_device(template, settings, allow_unverified=False):
    problems, warnings = [], []
    nodes = cuda_device_nodes(template.graph)
    backend = platform_backend(settings.get("platform_key"))
    if not nodes or backend in (None, "cuda"):
        return problems, warnings, [{"node": n, "class_type": c} for n, c in nodes]
    listed = "、".join(f"node {n}({c})" for n, c in nodes)
    message = (f"{listed} 在 graph 裡寫死 device=cuda,這台平台是 {settings['platform_key']}(沒有 CUDA)。"
               "graph 不會為平台臨時修改(D6);")
    if allow_unverified:
        warnings.append(message + f"因為加了 {ALLOW_FLAG} 才放行,這個節點很可能失敗")
    else:
        problems.append(message + f"預設不執行。要在這台機器實測請加 {ALLOW_FLAG},並記錄結果")
    return problems, warnings, [{"node": n, "class_type": c} for n, c in nodes]


# ---------- ComfyUI /object_info ----------

def required_classes(template):
    classes = {node["class_type"] for node in template.graph.values()}
    classes.update(template.data["capability_gate"].get("extra_nodes") or [])
    return sorted(classes)


def _input_spec(payload, class_type, field):
    """回傳 (input 是否存在, 選項清單或 None)。支援舊格式 [[...]] 與新格式 ["COMBO", {"options": [...]}]。"""
    try:
        inputs = payload[class_type]["input"]
    except (KeyError, TypeError):
        return False, None
    for section in ("required", "optional"):
        spec = (inputs.get(section) or {}).get(field) if isinstance(inputs, dict) else None
        if spec is None:
            continue
        if isinstance(spec, (list, tuple)) and spec:
            if isinstance(spec[0], list):
                return True, spec[0]
            if spec[0] == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict) \
                    and isinstance(spec[1].get("options"), list):
                return True, spec[1]["options"]
        return True, None
    return False, None


def check_object_info(template, payload):
    """回傳 (problems, warnings, info)。"""
    problems, warnings = [], []
    missing = [name for name in required_classes(template) if name not in payload]
    if missing:
        problems.append("ComfyUI 沒有這些 node class: " + "、".join(missing)
                        + "。請確認對應的 custom node 已安裝並重啟 ComfyUI(/object_info 看不到就不能送出)")
    selectors = []
    for model in template.data["models"]:
        class_type = template.graph[model["node"]]["class_type"]
        row = {"node": model["node"], "class_type": class_type, "input": model["input"],
               "filename": model["filename"], "result": None}
        selectors.append(row)
        if class_type in missing:
            row["result"] = "class_missing"
            continue
        exists, options = _input_spec(payload, class_type, model["input"])
        if not exists:
            row["result"] = "input_missing"
            problems.append(f"ComfyUI 的 {class_type} 沒有 input {model['input']!r}(node {model['node']});"
                            "custom node 版本可能和 template 實測時不同")
        elif options is None:
            row["result"] = "not_a_list"
        elif model["filename"] in options:
            row["result"] = "ok"
        else:
            row["result"] = "not_listed"
            problems.append(f"ComfyUI 的 {class_type}.{model['input']}(node {model['node']})選項裡沒有 "
                            f"{model['filename']}(共 {len(options)} 個選項)。檔案可能不在 ComfyUI 掃描的資料夾,"
                            "或放好後還沒重新整理/重啟 ComfyUI")
    return problems, warnings, {"classes": len(required_classes(template)), "missing_classes": missing,
                                "selectors": selectors}


# ---------- ComfyUI 版本 ----------

def fetch_system_stats(url):
    """GET /system_stats;失敗時丟例外(由 check 轉成提醒)。"""
    with urllib.request.urlopen(f"{url.rstrip('/')}/system_stats", timeout=SYSTEM_STATS_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_comfyui_version(template, stats, error=None):
    """回傳 (problems, warnings, info)。版本低於 min_comfyui_version 擋下;讀不到只提醒。"""
    required = template.data["min_comfyui_version"]
    system = stats.get("system") if isinstance(stats, dict) else None
    actual = system.get("comfyui_version") if isinstance(system, dict) else None
    info = {"required": required, "actual": actual, "result": None}
    parsed = T.parse_version(actual)
    if parsed is None:
        info["result"] = "unknown"
        reason = f"讀取 /system_stats 失敗:{error}" if error else f"/system_stats 沒有可辨識的 comfyui_version({actual!r})"
        return [], [f"無法確認 ComfyUI 版本({reason});template 需要 {required} 以上,這次不擋"], info
    if parsed < T.parse_version(required):
        info["result"] = "too_old"
        return [f"ComfyUI 版本 {actual} 低於 template 需要的 {required}(min_comfyui_version);"
                "graph 用到的節點或參數可能不存在或行為不同。請更新 ComfyUI,或改用支援這個版本的 template"], [], info
    info["result"] = "ok"
    return [], [], info


# ---------- 模型檔 ----------

def model_file_path(comfyui_path, relative, pathmod=os.path):
    return pathmod.normpath(pathmod.join(comfyui_path, *relative.split("/")))


class HashCache:
    """sha256 快取:鍵是正規化後的絕對路徑,值記錄 size、mtime_ns 與 sha256(D5)。"""

    def __init__(self, path=None):
        self.path = path
        self.entries = {}
        self.dirty = False
        if path:
            data = _read_json_or_none(path)
            if isinstance(data, dict) and isinstance(data.get("entries"), dict):
                self.entries = data["entries"]

    @staticmethod
    def key(path, pathmod=os.path):
        return pathmod.normcase(pathmod.abspath(path))

    def get(self, path, size, mtime_ns):
        entry = self.entries.get(self.key(path))
        if entry and entry.get("size") == size and entry.get("mtime_ns") == mtime_ns:
            return entry.get("sha256")
        return None

    def put(self, path, size, mtime_ns, sha256):
        self.entries[self.key(path)] = {"size": size, "mtime_ns": mtime_ns, "sha256": sha256}
        self.dirty = True

    def save(self):
        if not self.path or not self.dirty:
            return
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = f"{self.path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "entries": self.entries}, handle, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        self.dirty = False


def check_models(template, comfyui_path, verify_hashes=False, cache=None, progress=None):
    """回傳 (problems, warnings, files)。不改任何模型檔。"""
    problems, warnings, files = [], [], []
    if not comfyui_path:
        problems.append("設定檔沒有 comfyui_path,無法檢查模型檔;請在 local_config.json 設定 comfyui_path"
                        "(或用 --config 指定含 comfyui_path 的設定檔)")
        return problems, warnings, files
    if not os.path.isdir(comfyui_path):
        problems.append(f"comfyui_path 不存在或不是資料夾: {comfyui_path}")
        return problems, warnings, files
    for model in template.data["models"]:
        row = {"role": model["role"], "node": model["node"], "filename": model["filename"],
               "path": None, "expected_size": model.get("size_bytes"), "actual_size": None,
               "sha256": "skipped", "auto_download": bool(model.get("auto_download"))}
        files.append(row)
        auto = (f";node {model['node']} 缺檔時會自動下載,runner 不允許這種隱性下載,請先依 template 的 source "
                "手動放好檔案") if row["auto_download"] else ""
        if not model.get("path"):
            row["sha256"] = "no_pin"
            message = f"{model['role']}({model['filename']})沒有記錄路徑,無法確認檔案在本機"
            (problems if row["auto_download"] else warnings).append(message + auto)
            continue
        path = model_file_path(comfyui_path, model["path"])
        row["path"] = path
        try:
            stat = os.stat(path)
        except OSError:
            problems.append(f"找不到模型檔 {path}({model['role']},node {model['node']} {model['input']}){auto}")
            continue
        row["actual_size"] = stat.st_size
        if model.get("size_bytes") is not None and stat.st_size != model["size_bytes"]:
            problems.append(f"模型檔大小不符 {path}:實際 {stat.st_size:,} bytes,template 記錄 "
                            f"{model['size_bytes']:,} bytes;可能是下載不完整或版本不同")
            continue
        if not model.get("sha256"):
            row["sha256"] = "no_pin"
            warnings.append(f"{path} 沒有 sha256 pin({model.get('pin_status') or '未記錄'})")
            continue
        if not verify_hashes:
            continue
        cached = cache.get(path, stat.st_size, stat.st_mtime_ns) if cache else None
        if cached:
            digest, row["sha256_source"] = cached, "cache"
        else:
            if progress:
                progress(f"計算 sha256: {path}({stat.st_size / 2**30:.1f} GiB)")
            started = time.monotonic()
            digest = T.file_sha256(path)
            row["sha256_seconds"] = round(time.monotonic() - started, 1)
            row["sha256_source"] = "computed"
            if cache:
                cache.put(path, stat.st_size, stat.st_mtime_ns, digest)
        if digest == model["sha256"]:
            row["sha256"] = "match"
        else:
            row["sha256"] = "mismatch"
            problems.append(f"模型檔 sha256 不符 {path}:實際 {digest},template 記錄 {model['sha256']}")
    return problems, warnings, files


# ---------- 整合 ----------

def run_preflight(template, settings, *, verify_hashes=False, allow_unverified=False, hash_cache_path=None,
                  fetch_object_info=None, fetch_stats=None, progress=None):
    """依序執行所有檢查,回傳報告 dict(``status`` 為 pass／blocked)。不會在第一個問題就停,方便一次修完。"""
    fetch_object_info = fetch_object_info or (
        lambda url: _client._fetch_comfy_object_info(url, request_timeout=OBJECT_INFO_TIMEOUT))
    fetch_stats = fetch_stats or fetch_system_stats
    problems, warnings, checks = [], [], {}

    p, w, checks["platform"] = check_platform(template, settings, allow_unverified)
    problems += p
    warnings += w
    p, w, checks["cuda_device_nodes"] = check_cuda_device(template, settings, allow_unverified)
    problems += p
    warnings += w

    url = settings["comfy_url"]
    try:
        payload = fetch_object_info(url)
        checks["comfyui"] = {"url": url, "reachable": True}
    except Exception as exc:  # noqa: BLE001 - 連線錯誤種類很多,一律轉成可讀訊息
        payload = None
        checks["comfyui"] = {"url": url, "reachable": False, "error": str(exc)}
        reason = exc.__cause__ or exc
        problems.append(f"無法取得 {url}/object_info(URL 來源:{settings.get('comfy_url_source')}):{reason}。"
                        "請確認 ComfyUI 已啟動、URL 與 port 正確")
    if payload is not None:
        p, w, checks["object_info"] = check_object_info(template, payload)
        problems += p
        warnings += w
    try:
        stats, stats_error = fetch_stats(url), None
    except Exception as exc:  # noqa: BLE001 - 讀不到版本只提醒
        stats, stats_error = None, exc.__cause__ or exc
    p, w, checks["comfyui_version"] = check_comfyui_version(template, stats, stats_error)
    problems += p
    warnings += w

    cache = HashCache(hash_cache_path) if verify_hashes and hash_cache_path else None
    p, w, checks["models"] = check_models(template, settings.get("comfyui_path"), verify_hashes, cache, progress)
    problems += p
    warnings += w
    if cache:
        try:
            cache.save()
        except OSError as exc:
            warnings.append(f"sha256 快取寫入失敗 {hash_cache_path}: {exc}")

    return {
        "kind": "template_preflight", "status": BLOCKED if problems else PASS,
        "template": {"id": template.id, "version": template.version, "status": template.data["status"],
                     "graph_sha256": template.graph_sha256,
                     "graph_canonical_sha256": template.graph_canonical_sha256,
                     "template_json_sha256": template.template_json_sha256},
        "settings": {k: settings.get(k) for k in ("config_path", "config_source", "comfy_url", "comfy_url_source",
                                                  "comfyui_path", "snapshot_dir", "platform_key", "platform_source",
                                                  "device_platform_key")},
        "verify_hashes": bool(verify_hashes), "allow_unverified_platform": bool(allow_unverified),
        "checks": checks, "problems": problems, "warnings": warnings,
        "note": "preflight 只讀:沒有上傳、沒有 queue",
    }


def summary_lines(report):
    s, c = report["settings"], report["checks"]
    lines = [f"[preflight] {report['template']['id']} v{report['template']['version']}"
             f"({report['template']['status']})",
             f"[preflight] 設定檔: {s['config_path'] or '(沒有)'}({s['config_source'] or '-'})",
             f"[preflight] ComfyUI: {s['comfy_url']}({s['comfy_url_source']})  comfyui_path: {s['comfyui_path'] or '(沒有)'}",
             f"[preflight] 平台: {s['platform_key'] or '(未知)'}({s['platform_source'] or '-'})"
             f" → template 狀態 {c['platform'].get('status') or '-'}"]
    if s.get("device_platform_key") and s["device_platform_key"] != s["platform_key"]:
        lines[-1] += f"  [機器快照記錄的是 {s['device_platform_key']}]"
    version = c.get("comfyui_version")
    if version:
        lines.append(f"[preflight] ComfyUI 版本: {version['actual'] or '(未知)'}(需要 {version['required']} 以上)")
    if "object_info" in c:
        info = c["object_info"]
        ok = sum(1 for row in info["selectors"] if row["result"] in ("ok", "not_a_list"))
        lines.append(f"[preflight] node class: {info['classes'] - len(info['missing_classes'])}/{info['classes']}"
                     f"  模型選項: {ok}/{len(info['selectors'])}")
    files = c.get("models") or []
    if files:
        found = sum(1 for row in files if row["actual_size"] is not None)
        sized = sum(1 for row in files if row["actual_size"] is not None
                    and row["expected_size"] in (None, row["actual_size"]))
        line = f"[preflight] 模型檔: 存在 {found}/{len(files)},大小相符 {sized}/{len(files)}"
        if found - sized:
            line += f"({found - sized} 個檔案存在但大小不符,見下方問題)"
        if report["verify_hashes"]:
            line += f",sha256 相符 {sum(1 for row in files if row['sha256'] == 'match')}/{len(files)}"
        lines.append(line)
    for warning in report["warnings"]:
        lines.append(f"[preflight] 提醒: {warning}")
    for problem in report["problems"]:
        lines.append(f"[preflight] 問題: {problem}")
    verdict = "通過" if report["status"] == PASS else f"擋下({len(report['problems'])} 個問題)"
    lines.append(f"[preflight] 結果: {verdict};{report['note']}")
    return lines
