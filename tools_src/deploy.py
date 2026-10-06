"""把 repo 的 tools_src/ 部署到 <ComfyUI>/tools/(及已安裝的 custom_nodes/)。

預設只顯示計畫(dry run);加 `--yes` 才寫入。檔案對應來自 deploy_manifest.py,與
verify_portable_install.py 共用。寫入前會把所有將被覆蓋/移除的檔案備份到
<ComfyUI>/tools/.deploy-backups/<時間戳>/,寫入後在行程內跑 verify 的 source sync 檢查,
部署檔案有 FAIL 就自動還原並以非零結束碼離開。機器快照與 generated/ 輸出永遠不碰。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import verify_portable_install as verify  # noqa: E402
from deploy_manifest import PROTECTED_NAMES, deploy_manifest, stale_deployed_files  # noqa: E402

BACKUP_DIRNAME = Path("tools/.deploy-backups")
DEFAULT_KEEP = 5


class DeployError(RuntimeError):
    pass


def _same_content(a, b):
    try:
        return verify._normalize_source_text(a) == verify._normalize_source_text(b)
    except (UnicodeDecodeError, verify.VerificationError):
        return a.read_bytes() == b.read_bytes()


def _guard(rel):
    if rel.name in PROTECTED_NAMES or (rel.parts and rel.parts[0] == "generated"):
        raise DeployError(f"拒絕觸碰受保護檔案: {rel.as_posix()}")


def build_plan(repo_root, comfyui_path):
    """回傳 dict:items=[{action,label,src,dst}], skipped=[(label, reason)]。

    action: new / changed / unchanged / remove。custom_nodes 目標資料夾不存在就略過
    (安裝 custom node 是安裝決策,不是部署)。
    """
    repo_root, comfyui_path = Path(repo_root), Path(comfyui_path)
    items, skipped = [], []
    for entry in deploy_manifest(repo_root):
        _guard(entry.dst)
        node_dir = entry.custom_node_dir
        if node_dir is not None and not (comfyui_path / node_dir).is_dir():
            skipped.append((entry.label, f"未安裝 {node_dir.as_posix()}"))
            continue
        src = repo_root / entry.src
        if not src.is_file():
            raise DeployError(f"repo source 不存在: {entry.src.as_posix()}")
        dst = comfyui_path / entry.dst
        if not dst.is_file():
            action = "new"
        else:
            action = "unchanged" if _same_content(src, dst) else "changed"
        items.append({"action": action, "label": entry.label, "src": entry.src, "dst": entry.dst})
    for rel in stale_deployed_files(repo_root, comfyui_path):
        _guard(rel)
        items.append({"action": "remove", "label": rel.as_posix(), "src": None, "dst": rel})
    return {"items": items, "skipped": skipped}


def print_plan(plan, stream=None):
    stream = stream or sys.stdout
    counts = {k: 0 for k in ("new", "changed", "unchanged", "remove")}
    for item in plan["items"]:
        counts[item["action"]] += 1
        if item["action"] != "unchanged":
            print(f"  [{item['action']:<7}] {item['dst'].as_posix()}", file=stream)
    for label, reason in plan["skipped"]:
        print(f"  [skip   ] {label}（{reason}）", file=stream)
    print(f"計畫: new={counts['new']} changed={counts['changed']} unchanged={counts['unchanged']} "
          f"stale-to-remove={counts['remove']} skipped={len(plan['skipped'])}", file=stream)
    return counts


def _backup_root(comfyui_path):
    return Path(comfyui_path) / BACKUP_DIRNAME


def _new_backup_dir(comfyui_path):
    root = _backup_root(comfyui_path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate, n = root / stamp, 1
    while candidate.exists():
        n += 1
        candidate = root / f"{stamp}-{n}"
    candidate.mkdir(parents=True)
    return candidate


def _restore(comfyui_path, backup_dir):
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    comfyui_path = Path(comfyui_path)
    for action in manifest["actions"]:
        rel = Path(action["path"])
        _guard(rel)
        target = comfyui_path / rel
        if action["action"] == "new":
            if target.is_file():
                target.unlink()
        else:  # changed / remove:還原備份
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(backup_dir / rel, target)
    return manifest


def _prune_empty_dirs(comfyui_path, rels):
    for rel in rels:
        parent = (Path(comfyui_path) / rel).parent
        while parent != Path(comfyui_path) and parent.is_dir():
            if any(parent.iterdir()):
                break
            parent.rmdir()
            parent = parent.parent


def _deploy_related_failures(results, skipped_labels):
    skipped_names = {f"{label} source sync" for label in skipped_labels}
    return [r for r in results if r[0] == "fail" and r[1].endswith(" source sync") and r[1] not in skipped_names]


def apply_plan(repo_root, comfyui_path, plan, config_path, keep=DEFAULT_KEEP, stream=None):
    """套用計畫。回傳結束碼:0 成功、1 驗證失敗已還原。"""
    stream = stream or sys.stdout
    repo_root, comfyui_path = Path(repo_root), Path(comfyui_path)
    todo = [i for i in plan["items"] if i["action"] != "unchanged"]
    if not todo:
        print("沒有需要部署的變更。", file=stream)
        return 0
    backup_dir = _new_backup_dir(comfyui_path)
    actions = []
    for item in todo:
        rel = item["dst"]
        if item["action"] in ("changed", "remove"):
            dest = backup_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(comfyui_path / rel, dest)
        actions.append({"action": item["action"], "path": rel.as_posix()})
    (backup_dir / "manifest.json").write_text(json.dumps({
        "created": datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(repo_root),
        "actions": actions,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"備份: {backup_dir}", file=stream)

    for item in todo:
        target = comfyui_path / item["dst"]
        if item["action"] == "remove":
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo_root / item["src"], target)
    _prune_empty_dirs(comfyui_path, [i["dst"] for i in todo if i["action"] == "remove"])

    try:
        results, passed, failed = verify.verify_install(repo_root, config_path)
    except verify.VerificationError as exc:
        print(f"[WARN] 無法執行 verify（與部署檔案無關，不還原）: {exc}", file=stream)
        results, failed = [], 0
    bad = _deploy_related_failures(results, [label for label, _ in plan["skipped"]])
    for kind, name, *detail in results:
        if kind == "fail":
            tag = "FAIL(部署相關)" if (kind, name, *detail) in bad else "FAIL(與部署無關,僅回報)"
            print(f"[{tag}] {name}: {detail[0] if detail else ''}", file=stream)
    if bad:
        _restore(comfyui_path, backup_dir)
        print("驗證失敗,已自動從備份還原。", file=stream)
        return 1

    counts = {k: sum(1 for i in todo if i["action"] == k) for k in ("new", "changed", "remove")}
    print(f"部署完成: new={counts['new']} changed={counts['changed']} removed={counts['remove']}", file=stream)
    if any(i["dst"].parts[0] == "custom_nodes" for i in todo):
        print("注意: custom_nodes 有變更,必須重啟 ComfyUI 才會生效。", file=stream)
    pruned = prune_backups(comfyui_path, keep)
    if pruned:
        print(f"已清除舊備份: {', '.join(pruned)}", file=stream)
    return 0


def list_backups(comfyui_path):
    root = _backup_root(comfyui_path)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "manifest.json").is_file())


def prune_backups(comfyui_path, keep):
    names = list_backups(comfyui_path)
    old = names[:-keep] if keep > 0 else names
    for name in old:
        shutil.rmtree(_backup_root(comfyui_path) / name)
    return old


def rollback(comfyui_path, which, apply, stream=None):
    stream = stream or sys.stdout
    names = list_backups(comfyui_path)
    if not names:
        raise DeployError("沒有任何備份")
    name = names[-1] if which in (None, "latest") else which
    if name not in names:
        raise DeployError(f"找不到備份 {name!r};可用: {', '.join(names)}")
    backup_dir = _backup_root(comfyui_path) / name
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    for action in manifest["actions"]:
        verb = {"new": "刪除(該次新增)", "changed": "還原", "remove": "還原(該次移除)"}[action["action"]]
        print(f"  [{verb}] {action['path']}", file=stream)
    if not apply:
        print(f"以上為備份 {name} 的還原內容(dry run);加 --yes 才會實際還原。", file=stream)
        return 0
    _restore(comfyui_path, backup_dir)
    print(f"已還原備份 {name}。", file=stream)
    if any(a["path"].startswith("custom_nodes/") for a in manifest["actions"]):
        print("注意: custom_nodes 有變更,必須重啟 ComfyUI 才會生效。", file=stream)
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="把 repo 的 tools_src/ 部署到 ComfyUI 安裝路徑；預設只顯示計畫，加 --yes 才寫入。")
    p.add_argument("--repo-root", default=Path(__file__).resolve().parents[1], help="repo 根目錄")
    p.add_argument("--config", default="local_config.json", help="local_config.json 路徑（取 comfyui_path）")
    p.add_argument("--yes", action="store_true", help="實際寫入（含 --rollback 實際還原）")
    p.add_argument("--rollback", nargs="?", const="latest", metavar="TIMESTAMP|latest", help="還原備份（預設 latest）")
    p.add_argument("--list-backups", action="store_true", help="列出備份")
    p.add_argument("--keep", type=int, default=DEFAULT_KEEP, help=f"保留最近 N 份備份（預設 {DEFAULT_KEEP}）")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve(strict=False)
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (repo_root / config_path).resolve(strict=False)
    try:
        config = verify._load_json_object(config_path, "local_config")
        if not config.get("comfyui_path"):
            raise DeployError("local_config 缺少 comfyui_path")
        comfyui_path = verify._resolve_path(config["comfyui_path"], config_path.parent)
        if not comfyui_path.is_dir():
            raise DeployError("local_config.comfyui_path 指向的目錄不存在")
        if args.list_backups:
            names = list_backups(comfyui_path)
            for name in names:
                manifest = json.loads((_backup_root(comfyui_path) / name / "manifest.json").read_text(encoding="utf-8"))
                print(f"{name}  {len(manifest['actions'])} 個檔案")
            if not names:
                print("沒有備份。")
            return 0
        if args.rollback is not None:
            return rollback(comfyui_path, args.rollback, args.yes)
        plan = build_plan(repo_root, comfyui_path)
        print(f"部署目標: {comfyui_path}")
        print_plan(plan)
        if not args.yes:
            print("這是 dry run;確認計畫後加 --yes 才會寫入。")
            return 0
        return apply_plan(repo_root, comfyui_path, plan, config_path, keep=args.keep)
    except (DeployError, verify.VerificationError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
