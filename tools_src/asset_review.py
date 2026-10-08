"""素材候選 → 人工決定紀錄工具(stdlib only,可直接部署)。

技術 manifest(`*.result.json`,由 generate.py 或 `gameart.py run <template>` 產生)永不被修改;人工決定另存於同資料夾的
`<manifest 檔名去掉 .result.json>.decisions.json`,以 append-only 方式記錄。決定綁定輸出檔的
SHA-256:同名檔被重新生成(內容變了)就不會繼承舊決定,會顯示為 mismatch(視同 pending)。

重要:accept / reject 只能在使用者於對話中明確給出決定後才執行,agent 不可自行呼叫;
`--by` 必須是做決定的人。技術 pass 不等於美術接受。
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

MANIFEST_SUFFIX = ".result.json"
DECISIONS_SUFFIX = ".decisions.json"
SCHEMA_VERSION = 1
# generate.py 的圖片結果,以及 `gameart.py run <template>` 的 run.result.json
RESULT_KINDS = ("image_generation_result", "template_run_result")
# template run 的輸出放在 manifest 所在資料夾底下的 outputs/<id>/,往上找幾層
OUTPUT_SEARCH_DEPTH = 3


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _decisions_path(manifest_path):
    if manifest_path.endswith(MANIFEST_SUFFIX):
        return manifest_path[:-len(MANIFEST_SUFFIX)] + DECISIONS_SUFFIX
    return os.path.splitext(manifest_path)[0] + DECISIONS_SUFFIX


def _is_result_manifest(path):
    try:
        return _load_json(path).get("kind") in RESULT_KINDS
    except (OSError, ValueError, AttributeError):
        return False


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _find_manifests(target):
    target = os.path.abspath(target)
    if os.path.isdir(target):
        found = []
        for root, _dirs, files in os.walk(target):
            found.extend(os.path.join(root, n) for n in files if n.endswith(MANIFEST_SUFFIX))
        return sorted(found)
    if target.lower().endswith(".json") and os.path.isfile(target):
        # 預設 *.result.json,或 --result-json 指定的任意檔名
        return [target] if _is_result_manifest(target) else []
    if os.path.isfile(target):  # 輸出檔:找同資料夾(或往上幾層)中記錄了它的 manifest
        folder = os.path.dirname(target)
        for _ in range(OUTPUT_SEARCH_DEPTH + 1):
            found = [m for m in _manifests_in(folder)
                     if any(os.path.abspath(o.get("path", "")) == target
                            for o in _read_manifest(m).get("outputs", []))]
            if found:
                return found
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent
    return []


def _manifests_in(folder):
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(os.path.join(folder, n) for n in names
                  if n.endswith(MANIFEST_SUFFIX) and os.path.isfile(os.path.join(folder, n)))


def _read_manifest(path):
    try:
        data = _load_json(path)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("kind") in RESULT_KINDS else {}


def _read_decisions(manifest_path):
    path = _decisions_path(manifest_path)
    if not os.path.isfile(path):
        return []
    try:
        data = _load_json(path)
    except (OSError, ValueError):
        raise SystemExit(f"decisions 紀錄無法讀取,拒絕猜測: {path}")
    entries = data.get("decisions") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise SystemExit(f"decisions 紀錄格式不符: {path}")
    return entries


def _status(entries, output_path, current_sha):
    """回傳 (decision, entry):decision 為 accepted/rejected/pending/mismatch。"""
    same_path = [e for e in entries if e.get("output_path") == output_path]
    for entry in reversed(same_path):
        if entry.get("sha256") == current_sha:
            return entry["decision"], entry
    return ("mismatch" if same_path else "pending"), None


def collect(target):
    """彙整候選清單;每筆含技術狀態、檔案現況與人工決定狀態。"""
    rows = []
    for manifest_path in _find_manifests(target):
        manifest = _read_manifest(manifest_path)
        if not manifest:
            continue
        entries = _read_decisions(manifest_path)
        for output in manifest.get("outputs", []):
            path = output.get("path", "")
            recorded = output.get("sha256")
            exists = os.path.isfile(path)
            current = _sha256(path) if exists else None
            if not exists:
                file_state = "missing"
            elif current != recorded:
                file_state = "modified"
            else:
                file_state = "intact"
            decision, entry = _status(entries, path, current)
            rows.append({
                "id": (current or recorded or "")[:12], "manifest": manifest_path,
                "output_path": path, "task": manifest.get("task"),
                "technical": manifest.get("technical_validation", {}).get("status"),
                "file_state": file_state, "sha256": current or recorded,
                "decision": decision, "entry": entry,
            })
    return rows


def cmd_list(args):
    rows = collect(args.target)
    if not rows:
        print("沒有找到候選(需有 *.result.json 技術 manifest)")
        return 0
    for row in rows:
        note = f" by={row['entry']['by']}" if row["entry"] else ""
        print(f"{row['id']}  {row['decision']:<8} 技術={row['technical']} 檔案={row['file_state']}"
              f"{note}  {row['output_path']}")
    return 0


def cmd_show(args):
    matches = [r for r in collect(args.in_) if args.id and (
        r["sha256"].startswith(args.id) or r["output_path"] == os.path.abspath(args.id))]
    if len(args.id) < 6 or not matches:
        print(f"找不到候選 {args.id!r}(id 至少 6 碼 sha256 前綴,或輸出檔路徑)", file=sys.stderr)
        return 1
    if len({m["sha256"] for m in matches}) > 1 or len(matches) > 1:
        print("id 不唯一,請給更長的前綴", file=sys.stderr)
        return 1
    row = matches[0]
    history = [e for e in _read_decisions(row["manifest"])
               if e.get("output_path") == row["output_path"]]
    print(json.dumps({**{k: v for k, v in row.items() if k != "entry"},
                      "decision_history": history}, ensure_ascii=False, indent=2))
    return 0


def _decide(args, decision):
    if not args.by or not args.by.strip():
        raise SystemExit("必須以 --by 指定做決定的人(使用者本人,非 agent 自行決定)")
    manifests = _find_manifests(args.target)
    if len(manifests) != 1:
        raise SystemExit("需指定單一 manifest 或其輸出檔(目前找到 %d 個)" % len(manifests))
    manifest_path = manifests[0]
    manifest = _read_manifest(manifest_path)
    if decision == "accepted" and manifest.get("status") == "failed":
        raise SystemExit("這次執行的技術檢查沒有通過(status=failed),不能 accept;要記錄可以用 reject")
    outputs = manifest.get("outputs", [])
    target = os.path.abspath(args.target)
    chosen = [o for o in outputs if os.path.abspath(o.get("path", "")) == target]
    if args.output:
        chosen = [o for o in outputs if os.path.abspath(o.get("path", "")) == os.path.abspath(args.output)]
    elif not chosen:
        if len(outputs) != 1:
            raise SystemExit("manifest 有多個輸出,請以 --output 指定要決定哪一個")
        chosen = outputs
    if len(chosen) != 1:
        raise SystemExit("找不到要決定的輸出檔")
    output = chosen[0]
    path = output["path"]
    if not os.path.isfile(path):
        raise SystemExit(f"輸出檔不存在,無法記錄決定: {path}")
    current = _sha256(path)
    if current != output.get("sha256"):
        raise SystemExit("輸出檔內容與 manifest 記錄不符(已被改動或重新生成),拒絕記錄決定")
    entries = _read_decisions(manifest_path)
    entries.append({
        "output_path": path, "sha256": current, "decision": decision, "by": args.by.strip(),
        "note": args.note or "",
        "decided_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    })
    dest = _decisions_path(manifest_path)
    payload = {"schema_version": SCHEMA_VERSION, "kind": "asset_decisions",
               "manifest": os.path.basename(manifest_path), "decisions": entries}
    tmp = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, dest)
    print(f"[{decision}] {path} (sha256={current[:12]}, by={args.by.strip()})")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="素材候選的人工決定紀錄(accept/reject 僅限使用者明確決定後)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="列出候選與決定狀態")
    p.add_argument("target", help="資料夾、*.result.json 或 --result-json 指定的 manifest")
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("show", help="顯示單一候選與決定歷史")
    p.add_argument("id", help="sha256 前綴(>=6 碼)或輸出檔路徑")
    p.add_argument("--in", dest="in_", default=".", help="搜尋的資料夾或 manifest(預設目前資料夾)")
    p.set_defaults(func=cmd_show)
    for name in ("accept", "reject"):
        p = sub.add_parser(name, help=f"記錄使用者的 {name} 決定")
        p.add_argument("target", help="*.result.json 或輸出檔")
        p.add_argument("--by", required=True, help="做決定的人(必填)")
        p.add_argument("--note", help="理由,忠實摘要使用者所述")
        p.add_argument("--output", help="manifest 有多個輸出時指定哪一個")
        p.set_defaults(func=lambda a, n=name: _decide(a, "accepted" if n == "accept" else "rejected"))
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
