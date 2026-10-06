"""驗證證據升格工具:`python gameart.py validation propose|approve|status`(只能從 repo 的 tools_src/ 執行)。

流程(見 docs/knowledge/maintenance/validation-workflow.md):
deploy → smoke → smoke record(報告進 repo)→ validation propose(唯讀,列出將升格的 task 與差異)
→ **使用者**決定 → validation approve --by <使用者>(把證據項目寫進 profile 的 validation)。

設計原則(使用者決定):沒安裝 = 未選用,不是錯誤。報告裡 not_installed / skipped 的 task 只是「沒有證據」,
中性略過,不計失敗;只有 status == pass 的 task 會被列為可升格。

**agent 不得自行執行 approve**;只有使用者在對話中明確要求,才可代為執行,--by 填使用者。
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from comfyui_pipeline import profiles as _profiles  # noqa: E402

VALIDATION_SUBDIR = Path("docs") / "knowledge" / "validation"
PROFILES_SUBDIR = Path("tools_src") / "comfyui_pipeline" / "profiles"
REPORT_KIND = "smoke_report"
PASS = "pass"


class ValidationError(Exception):
    """使用者可修正的問題(以結束碼 2 回報)。"""


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return _sha256_bytes(Path(path).read_bytes())


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- 讀取與檢查 ----------

def profile_path(repo_root, profile_id):
    return Path(repo_root) / PROFILES_SUBDIR / f"{profile_id}.json"


def load_profile_file(repo_root, profile_id):
    path = profile_path(repo_root, profile_id)
    if not path.is_file():
        raise ValidationError(f"repo 內找不到設定檔 {profile_id!r}: {path}")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
        _profiles.validate_profile(profile, expected_id=profile_id)
    except (ValueError, _profiles.ProfileError) as exc:
        raise ValidationError(f"設定檔無效: {exc}") from exc
    return path, profile


def resolve_report(repo_root, report_arg):
    """報告必須是已記錄在 <repo>/docs/knowledge/validation/ 之內的 smoke_report。回傳 (path, relpath, report)。"""
    repo_root = Path(repo_root).resolve()
    path = Path(report_arg).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path)
    path = path.resolve()
    base = (repo_root / VALIDATION_SUBDIR).resolve()
    try:
        rel = path.relative_to(repo_root)
        path.relative_to(base)
    except ValueError:
        raise ValidationError(
            f"報告不在 repo 的 {VALIDATION_SUBDIR.as_posix()}/ 內:{path}\n"
            "請先用 `smoke record <report.json> --repo-root <repo>` 記錄進 repo,再 propose/approve。") from None
    if not path.is_file():
        raise ValidationError(f"找不到報告: {path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValidationError(f"報告不是合法 JSON: {path}: {exc}") from exc
    if not isinstance(report, dict) or report.get("kind") != REPORT_KIND:
        raise ValidationError(f"{path} 不是 smoke_report")
    for key in ("platform_key", "profile_id", "profile_sha256", "tasks"):
        if not report.get(key):
            raise ValidationError(f"報告缺少 {key}")
    return path, rel.as_posix(), report


def _git_blob_content_hashes(repo_root, profile_id, raw_sha):
    """舊報告(沒有 profile_hash_scheme)用整檔雜湊:到 git 歷史找出該版本,回傳它的內容雜湊;找不到回傳 None。"""
    rel = (PROFILES_SUBDIR / f"{profile_id}.json").as_posix()
    try:
        revs = subprocess.run(["git", "-C", str(repo_root), "log", "--format=%H", "--", rel],
                              capture_output=True, text=True, timeout=30, check=True).stdout.split()
        for rev in revs:
            blob = subprocess.run(["git", "-C", str(repo_root), "show", f"{rev}:{rel}"],
                                  capture_output=True, timeout=30, check=True).stdout
            if _sha256_bytes(blob) == raw_sha:
                return _profiles.profile_content_sha256(json.loads(blob.decode("utf-8")))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return None


def check_profile_binding(repo_root, report, profile):
    """報告綁的設定檔內容必須與 repo 現在的一致。回傳 (ok, 說明)。"""
    current = _profiles.profile_content_sha256(profile)
    recorded = report["profile_sha256"]
    if report.get("profile_hash_scheme") == "content-v1":
        if recorded == current:
            return True, "設定檔內容雜湊一致"
        return False, f"報告的 profile_sha256 {recorded[:12]} 與目前設定檔內容 {current[:12]} 不一致"
    # 舊報告:整檔原始雜湊。到 git 歷史比對當時版本的內容雜湊
    legacy = _git_blob_content_hashes(repo_root, report["profile_id"], recorded)
    if legacy is None:
        return False, ("舊式報告(整檔雜湊)無法在 git 歷史找到對應版本,無法確認設定檔內容;請在目前版本重跑 smoke")
    if legacy == current:
        return True, "舊式報告(整檔雜湊):對應的歷史版本內容與目前設定檔一致(僅 validation 區塊不同)"
    return False, "舊式報告對應的設定檔版本與目前內容不同(模型/取樣/task 定義已變動);請重跑 smoke"


def promotable_tasks(report, profile):
    """回傳 (可升格 task 清單(依設定檔順序), 備註清單)。

    一個 profile task 要升格:報告中該 task 至少一筆 pass,且沒有任何 fail。
    not_installed / skipped 只代表沒有證據,中性略過。
    """
    by_task = {}
    for rec in report["tasks"]:
        by_task.setdefault(rec.get("task"), []).append(rec.get("status"))
    promote, notes = [], []
    for task in profile["tasks"]:
        statuses = by_task.get(task)
        if not statuses:
            continue
        if "fail" in statuses:
            notes.append(f"{task}: 報告中有 fail,不升格")
        elif PASS in statuses:
            promote.append(task)
    unknown = sorted(set(by_task) - set(profile["tasks"]) - {None})
    if unknown:
        notes.append(f"報告含設定檔沒有的 task(略過): {', '.join(unknown)}")
    return promote, notes


def covered_tasks(profile, platform_key):
    """該平台已有證據項目涵蓋的 task 集合(含 legacy)。"""
    covered = set()
    for entry in _profiles.validation_entries(profile, platform_key):
        if entry["status"] != "verified":
            continue
        covered.update(profile["tasks"] if entry.get("tasks") is None else entry["tasks"])
    return covered


def build_plan(repo_root, report_arg):
    path, rel, report = resolve_report(repo_root, report_arg)
    profile_file, profile = load_profile_file(repo_root, report["profile_id"])
    ok, binding_note = check_profile_binding(repo_root, report, profile)
    promote, notes = promotable_tasks(report, profile)
    platform_key = report["platform_key"]
    already = covered_tasks(profile, platform_key)
    report_sha = sha256_file(path)
    duplicate = any(e.get("report_sha256") == report_sha
                    for e in _profiles.validation_entries(profile, platform_key))
    fingerprint = report.get("fingerprint") or {}
    env = _profiles.env_from_components(fingerprint)
    device = report.get("device") or {}
    entry = {
        "report": rel, "report_sha256": report_sha, "tasks": promote,
        "profile_sha256": _profiles.profile_content_sha256(profile), "env": env,
        "min_memory_mb": device.get("usable_memory_mb"),
    }
    return {
        "path": path, "rel": rel, "report": report, "profile_file": profile_file, "profile": profile,
        "platform_key": platform_key, "binding_ok": ok, "binding_note": binding_note,
        "promote": promote, "notes": notes, "newly": [t for t in promote if t not in already],
        "already": [t for t in promote if t in already], "duplicate": duplicate, "entry": entry,
    }


def refusal_reasons(plan):
    reasons = []
    if not plan["binding_ok"]:
        reasons.append(plan["binding_note"])
    if not plan["promote"]:
        reasons.append("報告中沒有可升格的 task(需要 status == pass;not_installed/skipped 不算證據)")
    if plan["duplicate"]:
        reasons.append("這份報告已核准過(profile 內已有相同 report_sha256 的證據項目)")
    return reasons


# ---------- 寫入設定檔 ----------

def _dump(value, level=1):
    """產生與既有 profile 風格一致的 JSON:dict 多行、純量 list 單行。"""
    pad = "  " * level
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [f'{pad}  {json.dumps(k, ensure_ascii=False)}: {_dump(v, level + 1)}' for k, v in value.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(value, list):
        if all(not isinstance(v, (dict, list)) for v in value):
            return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in value) + "]"
        items = [f"{pad}  {_dump(v, level + 1)}" for v in value]
        return "[\n" + ",\n".join(items) + f"\n{pad}]"
    return json.dumps(value, ensure_ascii=False)


def append_evidence(profile_file, platform_key, entry):
    """把證據項目附加到 profile 的 validation[platform_key](舊式 dict 先轉成 legacy 項目);只改 validation 區塊。"""
    text = Path(profile_file).read_text(encoding="utf-8")
    profile = json.loads(text)
    marker = '\n  "validation":'
    idx = text.rfind(marker)
    if idx < 0 or list(profile)[-1] != "validation":
        raise ValidationError("設定檔的 validation 必須是最後一個頂層欄位,無法安全改寫")
    validation = profile["validation"]
    current = validation.get(platform_key)
    if isinstance(current, dict):
        legacy = {"legacy": True, "report": None, "status": current["status"]}
        if "tasks" in current:
            legacy["tasks"] = current["tasks"]
        if current.get("min_verified_memory_mb") is not None:
            legacy["min_memory_mb"] = current["min_verified_memory_mb"]
        if current.get("evidence"):
            legacy["evidence"] = current["evidence"]
        current = [legacy]
    validation[platform_key] = list(current or []) + [entry]
    new_text = text[:idx] + '\n  "validation": ' + _dump(validation) + "\n}\n"
    updated = json.loads(new_text)
    before = {k: v for k, v in profile.items() if k != "validation"}
    after = {k: v for k, v in updated.items() if k != "validation"}
    if before != after:
        raise ValidationError("改寫後非 validation 欄位發生變化,已中止(未寫入)")
    _profiles.validate_profile(updated, expected_id=updated["id"])
    Path(profile_file).write_text(new_text, encoding="utf-8")


# ---------- 子命令 ----------

def format_plan(plan):
    entry, report = plan["entry"], plan["report"]
    lines = [
        f"報告: {plan['rel']}  (技術檢查,不代表美術接受)",
        f"設定檔: {report['profile_id']}   平台: {plan['platform_key']}   套件: {report.get('suite', {}).get('id')}",
        f"設定檔綁定: {'通過' if plan['binding_ok'] else '不通過'} - {plan['binding_note']}",
        f"環境: comfyui {entry['env'].get('comfyui_version')}({str(entry['env'].get('comfyui_commit'))[:8]})"
        f"  models {entry['env'].get('models_hash')}  custom_nodes {entry['env'].get('custom_nodes_hash')}"
        f"  記憶體 {entry['min_memory_mb']} MB",
        "",
        f"可升格為 verified 的 task({len(plan['promote'])}): {', '.join(plan['promote']) or '(無)'}",
    ]
    if plan["already"]:
        lines.append(f"  其中已被既有證據涵蓋: {', '.join(plan['already'])}")
    lines.append(f"  新增涵蓋: {', '.join(plan['newly']) or '(無)'}")
    lines += [f"  備註: {note}" for note in plan["notes"]]
    other = [r["task"] for r in report["tasks"] if r.get("status") in ("not_installed", "skipped")]
    if other:
        lines.append(f"未列入(沒有此次證據): {', '.join(sorted(set(other)))}")
    lines += ["", "將附加到 validation 的證據項目(propose 不會寫入):",
              "  " + json.dumps({**plan["entry"], "approved_by": "<使用者>", "approved_at": "<核准時間>"},
                                 ensure_ascii=False, indent=2).replace("\n", "\n  ")]
    return "\n".join(lines)


def cmd_propose(args):
    plan = build_plan(args.repo_root, args.report)
    print(format_plan(plan))
    reasons = refusal_reasons(plan)
    print()
    if reasons:
        print("目前無法核准:")
        print("\n".join(f"  - {r}" for r in reasons))
        return 1
    print("可交由使用者決定。使用者在對話中明確同意後,才由 `validation approve <report> --by <使用者>` 寫入;agent 不得自行核准。")
    return 0


def cmd_approve(args):
    by = (args.by or "").strip()
    if not by:
        raise ValidationError("--by 必須填寫核准的人(使用者)")
    plan = build_plan(args.repo_root, args.report)
    reasons = refusal_reasons(plan)
    if reasons:
        raise ValidationError("拒絕核准:\n" + "\n".join(f"  - {r}" for r in reasons))
    entry = dict(plan["entry"], approved_by=by, approved_at=_now())
    append_evidence(plan["profile_file"], plan["platform_key"], entry)
    print(f"已核准: {plan['report']['profile_id']} @ {plan['platform_key']}: {', '.join(plan['promote'])}")
    print(f"證據: {plan['rel']}  核准者: {by}")
    print("已寫入 profile 的 validation;請檢視 git diff 並由使用者決定是否 commit。")
    return 0


def cmd_status(args):
    repo_root = Path(args.repo_root)
    ids = [args.profile] if args.profile else _profiles.list_profile_ids()
    for profile_id in ids:
        _, profile = load_profile_file(repo_root, profile_id)
        platforms = sorted(profile["validation"]) if not args.platform else [args.platform]
        print(f"設定檔 {profile_id}")
        if not platforms:
            print("  (沒有任何平台驗證紀錄:全部 unverified)")
            continue
        width = max(len(t) for t in profile["tasks"])
        print("  " + "task".ljust(width) + "  " + "  ".join(p.ljust(14) for p in platforms))
        for task in profile["tasks"]:
            cells = []
            for platform_key in platforms:
                entries = [e for e in _profiles.validation_entries(profile, platform_key)
                           if e["status"] == "verified" and (e.get("tasks") is None or task in e["tasks"])]
                if any(not e["legacy"] for e in entries):
                    cells.append("verified")
                elif entries:
                    cells.append("legacy")
                else:
                    cells.append("unverified")
            print("  " + task.ljust(width) + "  " + "  ".join(c.ljust(14) for c in cells))
        for platform_key in platforms:
            for entry in _profiles.validation_entries(profile, platform_key):
                if entry["legacy"]:
                    print(f"  證據[{platform_key}] legacy(無環境紀錄): {entry.get('evidence') or '(無連結)'}")
                else:
                    print(f"  證據[{platform_key}] {entry['report']}  核准 {entry.get('approved_by')} "
                          f"{(entry.get('approved_at') or '')[:10]}  涵蓋 {len(entry.get('tasks') or [])} 個 task")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(
        description="驗證證據升格(propose 唯讀;approve 需要使用者明確決定,agent 不得自行執行)")
    ap.add_argument("--repo-root", default=str(HERE.parent), help="repo 根目錄(預設為本檔所在的 repo)")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("propose", help="檢查已記錄的報告並列出將升格的 task(不寫任何檔案)")
    p.add_argument("report")
    p = sub.add_parser("approve", help="使用者核准:把證據項目寫進 profile 的 validation")
    p.add_argument("report")
    p.add_argument("--by", required=True, help="核准的人(必須是使用者本人的決定)")
    p = sub.add_parser("status", help="列出 task × 平台的驗證狀態與證據")
    p.add_argument("--profile")
    p.add_argument("--platform")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return {"propose": cmd_propose, "approve": cmd_approve, "status": cmd_status}[args.command](args)
    except ValidationError as exc:
        print(f"validation: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
