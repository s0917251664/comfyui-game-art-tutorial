"""環境指紋:判斷三份機器快照(device/image/video capabilities)是否可能已過期。

只用標準庫、不起子程序、不連網,所以生成流程可以安全地呼叫(見 ``reminder_if_stale``)。
指紋存在獨立的 sidecar ``capability_fingerprint.json``(與快照同目錄),不改既有快照 schema。
指紋成分(``components``):
- platform:作業系統與 CPU 架構(``platform.system()`` / ``platform.machine()``)
- hardware:GPU 名稱與記憶體(只有 doctor 會填,需要 nvidia-smi/sysctl,生成流程不計算也不比對)
- comfyui:ComfyUI 的 git HEAD 與 comfyui_version.py 版本字串(直接讀檔,不呼叫 git)
- custom_nodes:custom_nodes 目錄第一層的名稱清單雜湊
- models:各 model root 底下所有檔案的相對路徑與大小雜湊(不讀檔案內容)
比對只看兩邊都有的成分,缺的成分不算差異。
"""
import hashlib
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone

FINGERPRINT_FILENAME = "capability_fingerprint.json"
SCHEMA_VERSION = 1
SNAPSHOT_FILES = {
    "device": "device_config.json",
    "image": "image_capabilities.json",
    "video": "video_capabilities.json",
}
REFRESH_COMMAND = "python gameart.py doctor --refresh"


def _hash_lines(lines):
    digest = hashlib.sha256()
    for line in sorted(lines):
        digest.update(line.encode("utf-8", "surrogateescape"))
        digest.update(b"\n")
    return digest.hexdigest()[:16]


def comfyui_info(comfyui_path):
    """讀 ComfyUI 的 git commit 與版本字串;讀不到的欄位是 None。"""
    info = {"commit": None, "version": None}
    if not comfyui_path:
        return info
    git_dir = os.path.join(comfyui_path, ".git")
    try:
        if os.path.isfile(git_dir):  # worktree/submodule:`gitdir: <path>`
            with open(git_dir, encoding="utf-8") as handle:
                text = handle.read().strip()
            if text.startswith("gitdir:"):
                git_dir = os.path.join(comfyui_path, text.split(":", 1)[1].strip())
        with open(os.path.join(git_dir, "HEAD"), encoding="utf-8") as handle:
            head = handle.read().strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            ref_path = os.path.join(git_dir, *ref.split("/"))
            if os.path.isfile(ref_path):
                with open(ref_path, encoding="utf-8") as handle:
                    head = handle.read().strip()
            else:
                head = None
                with open(os.path.join(git_dir, "packed-refs"), encoding="utf-8") as handle:
                    for line in handle:
                        parts = line.split()
                        if len(parts) == 2 and parts[1] == ref:
                            head = parts[0]
                            break
        info["commit"] = head or None
    except OSError:
        pass
    try:
        with open(os.path.join(comfyui_path, "comfyui_version.py"), encoding="utf-8") as handle:
            match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", handle.read())
        info["version"] = match.group(1) if match else None
    except OSError:
        pass
    return info


def custom_nodes_info(comfyui_path):
    if not comfyui_path:
        return None
    root = os.path.join(comfyui_path, "custom_nodes")
    try:
        names = [n for n in os.listdir(root) if n != "__pycache__" and not n.startswith(".")]
    except OSError:
        return None
    return {"count": len(names), "hash": _hash_lines(names)}


def models_info(model_roots):
    lines = []
    seen = False
    for root in model_roots or ():
        if not os.path.isdir(root):
            continue
        seen = True
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                if name.startswith("."):
                    continue
                path = os.path.join(current, name)
                try:
                    size = os.stat(path).st_size
                except OSError:
                    continue
                lines.append(f"{os.path.relpath(path, root)}\t{size}")
    return {"count": len(lines), "hash": _hash_lines(lines)} if seen else None


def hardware_info():
    """GPU/記憶體(會呼叫 nvidia-smi 或 sysctl,只供 doctor 使用)。"""
    import detect_device  # 與 doctor.py 同目錄;此處才載入,避免生成流程多一個相依
    device = detect_device.detect()
    return {key: device.get(key) for key in ("platform_key", "gpu_name", "vram_mb", "usable_memory_mb")}


def compute_components(comfyui_path, model_roots, include_hardware=False):
    components = {
        "platform": {"os": platform.system(), "machine": platform.machine().lower()},
        "comfyui": comfyui_info(comfyui_path),
        "custom_nodes": custom_nodes_info(comfyui_path),
        "models": models_info(model_roots),
    }
    if include_hardware:
        components["hardware"] = hardware_info()
    return components


def build_fingerprint(comfyui_path, model_roots, snapshot_dir, include_hardware=True):
    snapshots = {}
    for name, filename in SNAPSHOT_FILES.items():
        path = os.path.join(snapshot_dir, filename)
        snapshots[name] = {"file": filename, "exists": os.path.isfile(path)}
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "comfyui_path": comfyui_path,
        "model_roots": list(model_roots or ()),
        "components": compute_components(comfyui_path, model_roots, include_hardware),
        "snapshots": snapshots,
    }


def write_fingerprint(path, fingerprint):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(fingerprint, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_fingerprint(path):
    """讀 sidecar;不存在或壞掉回傳 None(壞檔視同沒有指紋)。"""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("components"), dict):
        return None
    return data


def compare_components(recorded, current):
    """回傳差異清單 [{"component", "recorded", "current"}];只比兩邊都有(非 None)的成分。"""
    diffs = []
    for name, old in recorded.items():
        new = current.get(name)
        if old is None or new is None:
            continue
        if name == "comfyui":
            # 版本/commit 各自只在兩邊都讀得到時才比
            old = {k: v for k, v in old.items() if v is not None and new.get(k) is not None}
            new = {k: new[k] for k in old}
        if old != new:
            diffs.append({"component": name, "recorded": old, "current": new})
    return diffs


def check_staleness(fingerprint, include_hardware=False):
    """用 sidecar 記錄的路徑重算目前指紋並比對,回傳差異清單。"""
    recorded = fingerprint["components"]
    current = compute_components(
        fingerprint.get("comfyui_path"), fingerprint.get("model_roots"),
        include_hardware and recorded.get("hardware") is not None,
    )
    return compare_components(recorded, current)


_reminded = False


def reminder_if_stale(snapshot_dir, stream=None):
    """生成前的一行提醒:有 sidecar 且過期才印到 stderr。永不拋例外、不改結束碼、每個行程最多一次。"""
    global _reminded
    if _reminded:
        return False
    try:
        fingerprint = read_fingerprint(os.path.join(snapshot_dir, FINGERPRINT_FILENAME))
        if fingerprint is None:
            return False
        diffs = check_staleness(fingerprint)
        if not diffs:
            return False
        names = "、".join(d["component"] for d in diffs)
        print(
            f"[提醒] 機器環境自上次偵測後已變動({names});能力快照可能過期,建議執行 {REFRESH_COMMAND}。",
            file=stream or sys.stderr,
        )
        _reminded = True
        return True
    except Exception:
        return False
