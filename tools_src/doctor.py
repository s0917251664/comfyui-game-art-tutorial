"""機器快照健檢:`python gameart.py doctor [--refresh] [--json]`。

預設唯讀:列出 device_config.json / image_capabilities.json / video_capabilities.json 是否存在、
多久前偵測、與目前環境指紋(見 comfyui_pipeline/fingerprint.py)比對是否過期,
並摘要 unverified / 缺模型的能力。不連網、不啟動 ComfyUI、不下載任何東西。
`--refresh` 依序重跑三個 detector(只掃描、不下載),成功後寫 capability_fingerprint.json。
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from comfyui_pipeline import fingerprint as fp  # noqa: E402


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def resolve_context(args):
    """決定 (config, comfyui_path, snapshot_dir)。找不到設定檔時退回 doctor.py 所在目錄。"""
    config_path = args.config
    if not config_path:
        for candidate in (os.path.join(os.path.dirname(HERE), "local_config.json"),
                          os.path.join(HERE, "local_config.json")):
            if os.path.isfile(candidate):
                config_path = candidate
                break
    config = _read_json(config_path) if config_path else None
    comfyui_path = args.comfyui_path or (config or {}).get("comfyui_path")
    if comfyui_path:
        comfyui_path = os.path.abspath(os.path.expanduser(comfyui_path))
    if args.snapshot_dir:
        snapshot_dir = os.path.abspath(args.snapshot_dir)
    elif comfyui_path:
        snapshot_dir = os.path.join(comfyui_path, "tools")
    else:
        snapshot_dir = HERE
    return config or {}, comfyui_path, snapshot_dir


def _age(snapshot, path, now):
    stamp = None
    if snapshot and snapshot.get("captured_at"):
        try:
            stamp = datetime.fromisoformat(snapshot["captured_at"])
        except ValueError:
            stamp = None
    if stamp is None:
        stamp = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.isoformat(), max(0, int((now - stamp).total_seconds()))


def _human_age(seconds):
    if seconds < 3600:
        return f"{seconds // 60} 分鐘前"
    if seconds < 86400:
        return f"{seconds // 3600} 小時前"
    return f"{seconds // 86400} 天前"


def summarize_image(snap):
    result = {"default_profile": snap.get("default_profile"), "profiles": {}}
    for pid, profile in (snap.get("profiles") or {}).items():
        if not profile.get("eligible"):
            continue
        tasks = profile.get("tasks") or {}
        result["profiles"][pid] = {
            "installed": bool(profile.get("installed")),
            "available": sorted(t for t, v in tasks.items() if v.get("available")),
            "missing": {t: v.get("missing_files") or v.get("missing_nodes")
                        for t, v in tasks.items() if not v.get("available")},
            "unverified": sorted(t for t, v in tasks.items() if v.get("validation") == "unverified"),
        }
    return result


def summarize_video(snap):
    backends = {}
    for name, backend in (snap.get("backends") or {}).items():
        backends[name] = {
            "available": bool(backend.get("available")),
            "capabilities": backend.get("capabilities") or [],
            "unavailable": backend.get("reasons") or {},
        }
    return {"default_backend": snap.get("default_backend"), "backends": backends}


def collect_status(args):
    config, comfyui_path, snapshot_dir = resolve_context(args)
    now = datetime.now(timezone.utc)
    status = {
        "comfyui_path": comfyui_path,
        "snapshot_dir": snapshot_dir,
        "snapshots": {},
        "fingerprint": {"exists": False, "stale": None, "diffs": []},
        "notes": [],
    }
    loaded = {}
    for name, filename in fp.SNAPSHOT_FILES.items():
        path = os.path.join(snapshot_dir, filename)
        entry = {"file": path, "exists": os.path.isfile(path)}
        if entry["exists"]:
            snap = _read_json(path)
            loaded[name] = snap
            entry["valid_json"] = snap is not None
            entry["captured_at"], entry["age_seconds"] = _age(snap, path, now)
        status["snapshots"][name] = entry

    # 快照自身記錄的平台 vs 目前平台(不需要 sidecar 也能判斷換機)
    device = loaded.get("device")
    if device and device.get("os") and device.get("machine"):
        live = (fp.compute_components(None, None)["platform"])
        if (device["os"], device["machine"]) != (live["os"], live["machine"]):
            status["notes"].append(
                f"device_config.json 記錄的平台是 {device['os']}/{device['machine']},"
                f"目前是 {live['os']}/{live['machine']}:換機後需要重新偵測。"
            )
            status["snapshots"]["device"]["stale"] = True

    sidecar = fp.read_fingerprint(os.path.join(snapshot_dir, fp.FINGERPRINT_FILENAME))
    if sidecar is None:
        status["notes"].append(
            f"沒有 {fp.FINGERPRINT_FILENAME}:無法判斷快照是否過期;執行 `{fp.REFRESH_COMMAND}` 建立基準。"
        )
    else:
        diffs = fp.check_staleness(sidecar, include_hardware=True)
        status["fingerprint"] = {
            "exists": True, "captured_at": sidecar.get("captured_at"),
            "stale": bool(diffs), "diffs": diffs,
        }
        if diffs:
            status["notes"].append(f"環境已變動({'、'.join(d['component'] for d in diffs)});建議 `{fp.REFRESH_COMMAND}`。")

    image = loaded.get("image")
    if image:
        status["image"] = summarize_image(image)
    else:
        status["notes"].append("沒有 image_capabilities.json:圖片 task 沿用 device_config.json 的 tier 對應。")
    video = loaded.get("video")
    if video:
        status["video"] = summarize_video(video)
    else:
        status["notes"].append("沒有 video_capabilities.json:影片 task 不可用,且不能從圖片 tier 推定影片 backend。")
    if not loaded.get("device"):
        status["notes"].append("沒有 device_config.json:請先執行 detect_device.py(或 doctor --refresh)。")
    return status


def format_status(status):
    lines = [f"ComfyUI: {status['comfyui_path'] or '(未設定)'}", f"快照目錄: {status['snapshot_dir']}", ""]
    for name, entry in status["snapshots"].items():
        if not entry["exists"]:
            lines.append(f"[缺少] {name}: {os.path.basename(entry['file'])}")
            continue
        flag = "過期?" if entry.get("stale") else "存在"
        lines.append(f"[{flag}] {name}: {os.path.basename(entry['file'])}  偵測於 {_human_age(entry['age_seconds'])}")
    fpr = status["fingerprint"]
    lines.append("")
    if fpr["exists"]:
        lines.append(f"環境指紋: {'已變動' if fpr['stale'] else '一致'}(基準 {fpr['captured_at']})")
        for diff in fpr["diffs"]:
            lines.append(f"  - {diff['component']}: {json.dumps(diff['recorded'], ensure_ascii=False)} -> "
                         f"{json.dumps(diff['current'], ensure_ascii=False)}")
    else:
        lines.append("環境指紋: 無")
    if "image" in status:
        image = status["image"]
        lines += ["", f"圖片能力(預設設定檔: {image['default_profile'] or '無'})"]
        for pid, p in image["profiles"].items():
            lines.append(f"  {pid}: 底模{'已裝' if p['installed'] else '未裝'};可用 {len(p['available'])} 個 task;"
                         f"unverified {len(p['unverified'])} 個")
            if p["unverified"]:
                lines.append(f"    unverified: {', '.join(p['unverified'])}")
            if p["missing"] and not p["installed"]:
                lines.append(f"    缺少能力的 task: {', '.join(p['missing'])}")
    if "video" in status:
        video = status["video"]
        lines += ["", f"影片能力(預設 backend: {video['default_backend'] or '無'})"]
        for name, b in video["backends"].items():
            lines.append(f"  {name}: {'可用 ' + ','.join(b['capabilities']) if b['available'] else '不可用'}")
            for cap, reason in b["unavailable"].items():
                lines.append(f"    {cap}: {json.dumps(reason, ensure_ascii=False)}")
    if status["notes"]:
        lines.append("")
        lines += [f"[提醒] {note}" for note in status["notes"]]
    return "\n".join(lines)


def _run_detector(label, script, extra, stream):
    path = os.path.join(HERE, script)
    if not os.path.isfile(path):
        print(f"[略過] {label}: 找不到 {script}", file=stream)
        return None
    proc = subprocess.run([sys.executable, path, *extra], capture_output=True, text=True)
    ok = proc.returncode == 0
    print(f"[{'完成' if ok else '失敗'}] {label}", file=stream)
    if not ok:
        print((proc.stderr or proc.stdout).strip()[-800:], file=stream)
    return ok


def refresh(args):
    config, comfyui_path, snapshot_dir = resolve_context(args)
    log = sys.stderr if args.json else sys.stdout
    if not comfyui_path:
        print("doctor: 找不到 comfyui_path;請用 --config 或 --comfyui-path 指定。", file=sys.stderr)
        return 2
    os.makedirs(snapshot_dir, exist_ok=True)
    device_path = os.path.join(snapshot_dir, fp.SNAPSHOT_FILES["device"])
    previous = _read_json(os.path.join(snapshot_dir, fp.SNAPSHOT_FILES["image"])) or {}
    model_roots = previous.get("model_roots") or [os.path.join(comfyui_path, "models")]
    common = ["--comfyui-path", comfyui_path, "--device-config", device_path, "--overwrite"]
    for root in model_roots:
        common += ["--model-root", root]
    if config.get("comfyui_url"):
        common += ["--comfy-url", config["comfyui_url"], "--http-timeout", "3"]
    results = [
        _run_detector("device", "detect_device.py", ["--out", device_path], log),
    ]
    if results[0]:
        results.append(_run_detector(
            "image", "detect_image_capabilities.py",
            [*common, "--out", os.path.join(snapshot_dir, fp.SNAPSHOT_FILES["image"])], log))
        results.append(_run_detector(
            "video", "detect_video_capabilities.py",
            [*common, "--out", os.path.join(snapshot_dir, fp.SNAPSHOT_FILES["video"])], log))
    if any(r is False for r in results) or results[0] is None:
        print("doctor: 有 detector 失敗,未更新指紋。", file=sys.stderr)
        return 1
    fp.write_fingerprint(
        os.path.join(snapshot_dir, fp.FINGERPRINT_FILENAME),
        fp.build_fingerprint(comfyui_path, model_roots, snapshot_dir, include_hardware=True),
    )
    print(f"已更新 {fp.FINGERPRINT_FILENAME}", file=log)
    status = collect_status(args)
    print(json.dumps(status, ensure_ascii=False, indent=2) if args.json else format_status(status))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="檢查機器能力快照是否存在/過期;--refresh 重跑 detector。")
    ap.add_argument("--refresh", action="store_true", help="重跑三個 detector 並更新指紋(只掃描,不下載)")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    ap.add_argument("--config", help="local_config.json 路徑;預設 repo 根目錄的 local_config.json")
    ap.add_argument("--comfyui-path", help="覆寫設定檔的 comfyui_path")
    ap.add_argument("--snapshot-dir", help="快照所在目錄;預設 <comfyui_path>/tools")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.refresh:
        return refresh(args)
    status = collect_status(args)
    print(json.dumps(status, ensure_ascii=False, indent=2) if args.json else format_status(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
