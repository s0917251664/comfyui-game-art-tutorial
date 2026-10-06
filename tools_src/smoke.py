"""固定煙霧測試套件:`python gameart.py smoke --output-dir DIR [--suite image-core] [--tasks a,b] [--profile ID]`。

依 ``comfyui_pipeline/smoke_suites/<suite>.json`` 的固定提示詞/種子/尺寸,逐一以子程序呼叫同資料夾的
``generate.py``(各 task 都帶明確 ``--result-json``),收集結果後寫 ``<output-dir>/smoke-report.json``
與總覽圖 ``smoke-contact-sheet.jpg``。可從 repo 的 tools_src/ 或部署後的 <ComfyUI>/tools/ 執行。

狀態語意(設計原則:模型/節點由使用者選裝,沒裝不是錯誤):
- pass:     task 實際執行成功。
- fail:     capability 判定可用、卻在執行時出錯(或逾時)。唯一會讓整個套件失敗的狀態。
- not_installed: 使用者未選用(缺模型檔/節點);不算失敗,也不納入套件整體判定。
- skipped:  其他原因略過(設定檔不提供此 task、平台不適用、上游 task 沒有輸出、未被 --tasks 選中的依賴等)。
報告只記錄技術事實,不含任何美術接受判斷。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from comfyui_pipeline import fingerprint as fp  # noqa: E402
from comfyui_pipeline import profiles as _profiles  # noqa: E402

REPORT_SCHEMA_VERSION = 1
REPORT_KIND = "smoke_report"
REPORT_NAME = "smoke-report.json"
SHEET_NAME = "smoke-contact-sheet.jpg"
SUITE_DIR = HERE / "comfyui_pipeline" / "smoke_suites"
DEFAULT_SUITE = "image-core"
DEFAULT_TASK_TIMEOUT = 1800.0
TAIL_CHARS = 4000

PASS, FAIL, SKIPPED, NOT_INSTALLED = "pass", "fail", "skipped", "not_installed"
NOT_INSTALLED_WORDING = "未安裝(使用者未選用)"
TECHNICAL_ONLY_NOTE = "僅技術檢查(能否執行、輸出可讀、尺寸/hash 記錄),不代表美術接受;content_review 未進行。"


class SmokeError(Exception):
    """使用者可修正的設定錯誤(以結束碼 2 回報)。"""


# ---------- 套件定義 ----------

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_suite(suite_id, suite_dir=SUITE_DIR):
    path = Path(suite_dir) / f"{suite_id}.json"
    if not path.is_file():
        raise SmokeError(f"找不到套件 {suite_id!r}: {path}")
    try:
        suite = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SmokeError(f"套件不是合法 JSON: {path}: {exc}") from exc
    validate_suite(suite, suite_id)
    suite["_path"] = str(path)
    suite["_sha256"] = sha256_file(path)
    return suite


def validate_suite(suite, expected_id=None):
    if not isinstance(suite, dict) or suite.get("schema_version") != 1:
        raise SmokeError("套件 schema_version 必須是 1")
    if expected_id and suite.get("id") != expected_id:
        raise SmokeError(f"套件 id {suite.get('id')!r} 與檔名 {expected_id!r} 不符")
    tasks = suite.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise SmokeError("套件 tasks 必須是非空清單")
    seen = set()
    for entry in tasks:
        tid = entry.get("id")
        if not tid or tid in seen:
            raise SmokeError(f"task id 缺少或重複: {tid!r}")
        if not entry.get("task") or not isinstance(entry.get("args"), list):
            raise SmokeError(f"{tid}: 需要 task 與 args 清單")
        if "seed" not in entry:
            raise SmokeError(f"{tid}: 必須明確寫 seed(沒有種子的 task 寫 null)")
        for need in entry.get("needs", []):
            if need not in seen:
                raise SmokeError(f"{tid}: needs {need!r} 必須是排在前面的 task id")
        seen.add(tid)


def select_tasks(suite, wanted=None):
    """回傳 (依套件順序的 entry 清單, {自動補入的依賴 id})。未知 id 丟 SmokeError。"""
    entries = {e["id"]: e for e in suite["tasks"]}
    if not wanted:
        return list(suite["tasks"]), set()
    unknown = [w for w in wanted if w not in entries]
    if unknown:
        raise SmokeError(f"套件 {suite['id']} 沒有 task: {', '.join(unknown)}(可用: {', '.join(entries)})")
    need = set()

    def add(tid):
        if tid in need:
            return
        need.add(tid)
        for dep in entries[tid].get("needs", []):
            add(dep)

    for tid in wanted:
        add(tid)
    return [e for e in suite["tasks"] if e["id"] in need], need - set(wanted)


# ---------- 環境與 capability 判定 ----------

def read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def resolve_environment(snapshot_dir=HERE, comfyui_path=None, profile_id=None):
    """讀機器快照,回傳 env dict(device / capabilities / profile_id / comfyui_path / model_roots)。"""
    snapshot_dir = Path(snapshot_dir)
    device = read_json(snapshot_dir / "device_config.json")
    if device is None:
        import detect_device  # 沒有快照時直接偵測(只讀硬體資訊)
        device = detect_device.detect()
    caps = read_json(snapshot_dir / "image_capabilities.json")
    sidecar = fp.read_fingerprint(str(snapshot_dir / fp.FINGERPRINT_FILENAME)) or {}
    if not comfyui_path:
        comfyui_path = (caps or {}).get("comfyui_path") or sidecar.get("comfyui_path")
    if not comfyui_path and snapshot_dir.name == "tools":
        comfyui_path = str(snapshot_dir.parent)
    model_roots = (caps or {}).get("model_roots") or sidecar.get("model_roots")
    if not model_roots and comfyui_path:
        model_roots = [os.path.join(comfyui_path, "models")]
    chosen = profile_id or (caps or {}).get("default_profile") or _profiles.profile_id_for_tier(device.get("tier"))
    return {
        "device": device, "capabilities": caps, "profile_id": chosen, "profile_requested": bool(profile_id),
        "comfyui_path": comfyui_path, "model_roots": model_roots or [],
    }


def plan_task(entry, env):
    """決定 task 能不能跑:回傳 (status 或 None=可執行, reason, missing)。純函式,不連 ComfyUI。

    not_installed 只來自「profile 提供、平台適用,但 capability 快照說缺模型/節點」;
    其他不能跑的原因一律是 skipped。
    """
    task, pid = entry["task"], env.get("profile_id")
    if not pid:
        return SKIPPED, "找不到可用的圖片模型設定檔(沒有 --profile、default_profile 或 tier 對應)", []
    try:
        profile = _profiles.load_profile(pid)
    except Exception as exc:  # ProfileError 等
        return SKIPPED, f"無法載入模型設定檔 {pid!r}: {exc}", []
    if task not in profile["tasks"]:
        return SKIPPED, f"模型設定檔 {pid} 不提供 {task}", []
    reasons = _profiles.platform_eligibility(profile, env.get("device") or {})
    if reasons:
        return SKIPPED, f"模型設定檔 {pid} 不適用這台機器: " + ";".join(reasons), []
    caps = env.get("capabilities") or {}
    info = ((caps.get("profiles") or {}).get(pid) or {}).get("tasks", {}).get(task)
    if info is not None and not info.get("available", True):
        missing = list(info.get("missing_files") or info.get("missing_models") or []) + \
            [f"node:{name}" for name in info.get("missing_nodes") or []]
        return NOT_INSTALLED, f"{NOT_INSTALLED_WORDING}: " + (", ".join(missing) or "必要元件"), missing
    return None, None, []


def classify_preflight_missing(stderr_text):
    """沒有 capability 快照時的備援:generate 的送出前檢查回報缺模型/節點 = 未安裝,不是 fail。"""
    for line in (stderr_text or "").splitlines():
        if "ComfyUI 缺少" in line and "已在上傳/排隊前停止" in line:
            return f"{NOT_INSTALLED_WORDING}: {line.strip()}"
    return None


# ---------- 輸入產生與指令 ----------

def make_mask(path, spec):
    """中央矩形遮罩:矩形內 alpha=0,其餘 alpha=255(inpaint/layer_split 慣例)。"""
    from PIL import Image
    width, height = spec.get("size", [768, 768])
    x0, y0, x1, y1 = spec.get("rect", [0.25, 0.25, 0.75, 0.75])
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    hole = Image.new("RGBA", (round((x1 - x0) * width), round((y1 - y0) * height)), (255, 255, 255, 0))
    image.paste(hole, (round(x0 * width), round(y0 * height)))
    image.save(path, "PNG")
    return path


def build_command(entry, out_dir, outputs_by_id, mask_path, *, generate=None, profile_id=None,
                  comfy_url=None, config_path=None, python=None):
    """組出 generate.py 的完整 argv;seed 一律明確傳入(null 的 task 不傳)。"""
    generate = generate or HERE / "generate.py"
    cmd = [python or sys.executable, str(generate)]
    if profile_id:
        cmd += ["--profile", profile_id]
    if comfy_url:
        cmd += ["--comfy-url", comfy_url]
    if config_path:
        cmd += ["--config", config_path]
    cmd += ["--result-json", str(Path(out_dir) / f"{entry['id']}.result.json"), entry["task"]]
    for arg in entry["args"]:
        if arg == "{mask}":
            arg = str(mask_path)
        elif arg.startswith("{out:") and arg.endswith("}"):
            arg = str(outputs_by_id[arg[5:-1]])
        cmd.append(arg)
    cmd += ["--output-dir", str(Path(out_dir) / entry["id"])]
    if entry["seed"] is not None:
        cmd += ["--seed", str(entry["seed"])]
    return cmd


def default_runner(cmd, timeout, cwd):
    """實際呼叫子程序;回傳 (exit_code, stdout, stderr, timed_out)。"""
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                              encoding="utf-8", errors="replace")
        return done.returncode, done.stdout, done.stderr, False
    except subprocess.TimeoutExpired as exc:
        def text(value):
            return value.decode("utf-8", "replace") if isinstance(value, bytes) else (value or "")
        return None, text(exc.stdout), text(exc.stderr), True


def _tail(text):
    return text if len(text) <= TAIL_CHARS else "...(前略)\n" + text[-TAIL_CHARS:]


def _outputs_from_manifest(manifest, base):
    outputs = []
    for item in manifest.get("outputs", []):
        path = item.get("path")
        size = os.path.getsize(path) if path and os.path.isfile(path) else None
        outputs.append({
            "path": os.path.relpath(path, base) if path and path.startswith(str(base)) else path,
            "abs_path": path, "sha256": item.get("sha256"), "size": size, "mode": item.get("mode"),
            "width": item.get("width"), "height": item.get("height"),
        })
    return outputs


def run_task(entry, env, out_dir, outputs_by_id, mask_path, results, *, runner=default_runner,
             task_timeout=DEFAULT_TASK_TIMEOUT, comfy_url=None, config_path=None, generate=None):
    """執行單一 task,回傳報告用的 task 紀錄 dict。"""
    out_dir = Path(out_dir)
    record = {
        "id": entry["id"], "task": entry["task"], "status": None, "reason": None, "duration_s": None,
        "seed_requested": entry["seed"], "seeds_resolved": None, "seed_note": entry.get("seed_note"),
        "command": None, "exit_code": None, "log": None, "outputs": [], "result_json": None,
        "missing": [], "dependency_only": False,
    }
    for need in entry.get("needs", []):
        if need not in outputs_by_id:
            upstream = results.get(need, {}).get("status")
            record.update(status=SKIPPED, reason=f"上游 task {need} 沒有可用輸出(狀態: {upstream or '未執行'})")
            return record
    status, reason, missing = plan_task(entry, env)
    if status is not None:
        record.update(status=status, reason=reason, missing=missing)
        return record
    cmd = build_command(entry, out_dir, outputs_by_id, mask_path, generate=generate,
                        profile_id=env.get("profile_id"), comfy_url=comfy_url, config_path=config_path)
    record["command"] = cmd
    (out_dir / entry["id"]).mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    code, stdout, stderr, timed_out = runner(cmd, task_timeout, str(HERE))
    record["duration_s"] = round(time.monotonic() - started, 2)
    record["exit_code"] = code
    log_dir = out_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{entry['id']}.log"
    log_path.write_text(
        f"$ {' '.join(cmd)}\nexit_code={code} timed_out={timed_out} duration_s={record['duration_s']}\n"
        f"--- stdout (tail) ---\n{_tail(stdout)}\n--- stderr (tail) ---\n{_tail(stderr)}\n", encoding="utf-8")
    record["log"] = os.path.relpath(log_path, out_dir)
    result_path = out_dir / f"{entry['id']}.result.json"
    if timed_out:
        record.update(status=FAIL, reason=f"逾時(>{task_timeout:g}s)")
        return record
    if code != 0:
        not_installed = classify_preflight_missing(stderr)
        if not_installed:
            record.update(status=NOT_INSTALLED, reason=not_installed)
        else:
            last = next((ln for ln in reversed((stderr or stdout).strip().splitlines()) if ln.strip()), "")
            record.update(status=FAIL, reason=f"exit code {code}: {last[:300]}")
        return record
    manifest = read_json(result_path)
    if manifest is None or manifest.get("kind") != "image_generation_result":
        record.update(status=FAIL, reason=f"結束碼 0 但沒有有效的 result manifest: {result_path.name}")
        return record
    record["result_json"] = os.path.relpath(result_path, out_dir)
    record["outputs"] = _outputs_from_manifest(manifest, out_dir)
    record["seeds_resolved"] = manifest.get("resolved_seeds")
    record["technical_validation"] = (manifest.get("technical_validation") or {}).get("status")
    record["profile_id_in_result"] = manifest.get("profile_id")
    record["profile_sha256_in_result"] = manifest.get("profile_sha256")
    flat = [v for node in (record["seeds_resolved"] or {}).values() for v in node.values()]
    if entry["seed"] is not None and flat and any(v != entry["seed"] for v in flat):
        record["seed_note"] = f"manifest 解析出的種子 {sorted(set(flat))} 與要求的 {entry['seed']} 不同"
    if not record["outputs"] or record["technical_validation"] != "pass":
        record.update(status=FAIL, reason="manifest 沒有輸出或 technical_validation 非 pass")
        return record
    first_png = next((o["abs_path"] for o in record["outputs"] if o["abs_path"]), None)
    if first_png:
        outputs_by_id[entry["id"]] = first_png
    record.update(status=PASS)
    return record


# ---------- 彙整 ----------

def summarize(task_records):
    counts = {PASS: 0, FAIL: 0, SKIPPED: 0, NOT_INSTALLED: 0}
    for rec in task_records:
        counts[rec["status"]] += 1
    runnable = counts[PASS] + counts[FAIL]  # 只有實際跑過的 task 納入整體判定
    if counts[FAIL]:
        overall = FAIL
    elif counts[PASS]:
        overall = PASS
    else:
        overall = "no_runnable_tasks"
    return {"overall": overall, "counts": counts, "runnable": runnable,
            "note": "整體判定只看實際執行的 task;not_installed/skipped 不計入失敗。"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def device_summary(device):
    return {key: device.get(key) for key in (
        "platform_key", "os", "machine", "backend", "gpu_name", "vram_mb", "unified_memory_mb",
        "usable_memory_mb", "tier")}


def build_report(suite, env, task_records, started, finished, selection=None):
    profile_id = env.get("profile_id")
    try:
        profile_sha = _profiles_sha(profile_id)
    except OSError:
        profile_sha = None
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "kind": REPORT_KIND,
        "technical_only": True,
        "note": TECHNICAL_ONLY_NOTE,
        "content_review": "not_performed",
        "suite": {"id": suite["id"], "sha256": suite["_sha256"], "selected_tasks": selection},
        "started": started,
        "finished": finished,
        "platform_key": (env.get("device") or {}).get("platform_key"),
        "device": device_summary(env.get("device") or {}),
        "fingerprint": fp.compute_components(env.get("comfyui_path"), env.get("model_roots"), include_hardware=False),
        "profile_id": profile_id,
        "profile_sha256": profile_sha,
        "summary": summarize(task_records),
        "tasks": task_records,
    }


def _profiles_sha(profile_id):
    if not profile_id:
        return None
    return sha256_file(os.path.join(_profiles.PROFILES_DIR, f"{profile_id}.json"))


def write_report(out_dir, report):
    path = Path(out_dir) / REPORT_NAME
    clean = json.loads(json.dumps(report, ensure_ascii=False))
    for rec in clean["tasks"]:
        for out in rec.get("outputs", []):
            out.pop("abs_path", None)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


# ---------- 總覽圖 ----------

def _font(size):
    from PIL import ImageFont
    for candidate in ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
                      "C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/msyh.ttc",
                      "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        if os.path.isfile(candidate):
            try:
                return ImageFont.truetype(candidate, size), True
            except OSError:
                continue
    return ImageFont.load_default(), False


def make_contact_sheet(report, out_dir, path=None, thumb=256):
    """所有輸出縮圖 + 各 task 狀態。沒有 Pillow 回傳 None(不影響報告)。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    path = Path(path) if path else Path(out_dir) / SHEET_NAME
    font, cjk = _font(14)
    wording = {
        PASS: "pass", FAIL: "FAIL",
        SKIPPED: "skipped" if not cjk else "略過",
        NOT_INSTALLED: NOT_INSTALLED_WORDING if cjk else "not installed (not selected by user)",
    }
    header = ("技術檢查,非美術驗收" if cjk else "technical check only, not art acceptance")
    summary = report["summary"]
    counts = summary["counts"]
    title = (f"{report['suite']['id']} / {report['profile_id']} / {report['platform_key']}  "
             f"overall={summary['overall']}  pass={counts[PASS]} fail={counts[FAIL]} "
             f"not_installed={counts[NOT_INSTALLED]} skipped={counts[SKIPPED]}  -- {header}")
    tiles = []
    for rec in report["tasks"]:
        label = f"{rec['id']}: {wording[rec['status']]}"
        images = [Path(out_dir) / o["path"] if not os.path.isabs(o["path"]) else Path(o["path"])
                  for o in rec.get("outputs", []) if o.get("path")]
        tiles.append((label, images[:1], rec))
    cols = 4
    rows = max(1, (len(tiles) + cols - 1) // cols)
    label_h = 22
    cell_w, cell_h = thumb + 8, thumb + label_h + 8
    sheet = Image.new("RGB", (cols * cell_w, 30 + rows * cell_h), (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    draw.text((6, 6), title[:200], fill=(235, 235, 235), font=font)
    for index, (label, images, rec) in enumerate(tiles):
        x, y = (index % cols) * cell_w + 4, 30 + (index // cols) * cell_h + 4
        draw.text((x, y), label[:48], fill={PASS: (130, 220, 130), FAIL: (255, 110, 110)}.get(
            rec["status"], (200, 200, 120)), font=font)
        box = (x, y + label_h, x + thumb, y + label_h + thumb)
        draw.rectangle(box, outline=(80, 80, 80))
        shown = False
        for img_path in images:
            try:
                with Image.open(img_path) as img:
                    img = img.convert("RGBA")
                    img.thumbnail((thumb, thumb))
                    bg = Image.new("RGBA", img.size, (64, 64, 64, 255))
                    sheet.paste(Image.alpha_composite(bg, img).convert("RGB"), (x, y + label_h))
                    shown = True
            except OSError:
                pass
        if not shown and rec.get("reason"):
            reason = rec["reason"] if cjk else (wording[rec["status"]])
            for line_no, start in enumerate(range(0, min(len(reason), 150), 26)):
                draw.text((x + 4, y + label_h + 4 + line_no * 16), reason[start:start + 26],
                          fill=(170, 170, 170), font=font)
    sheet.save(path, "JPEG", quality=85)
    return path


# ---------- 記錄到 repo ----------

def record_path(repo_root, report, ext=".json"):
    started = report["started"][:10]
    pid = report.get("profile_id") or "no-profile"
    name = f"{started}-{report['suite']['id']}-{pid}{ext}"
    return Path(repo_root) / "docs" / "knowledge" / "validation" / (report.get("platform_key") or "unknown-platform") / name


def record_report(repo_root, report_path, sheet_path, report, with_images=False):
    """把報告(選用:總覽圖)複製進 repo 知識庫;同名已存在時加 -2、-3,不覆寫。回傳寫入的路徑清單。"""
    target = record_path(repo_root, report)
    n = 1
    while target.exists():
        n += 1
        target = target.with_name(f"{record_path(repo_root, report).stem}-{n}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    written = []
    shutil.copyfile(report_path, target)
    written.append(target)
    if with_images and sheet_path and Path(sheet_path).is_file():
        jpg = target.with_suffix(".jpg")
        shutil.copyfile(sheet_path, jpg)
        written.append(jpg)
    return written


# ---------- 主流程 ----------

def run_suite(suite, env, out_dir, wanted=None, *, runner=default_runner, task_timeout=DEFAULT_TASK_TIMEOUT,
              comfy_url=None, config_path=None, generate=None, log=print):
    out_dir = Path(out_dir)
    entries, auto = select_tasks(suite, wanted)
    started = utc_now()
    mask_path = None
    outputs_by_id, results, records = {}, {}, []
    for entry in entries:
        if any(a == "{mask}" for a in entry["args"]) and mask_path is None:
            try:
                mask_path = make_mask(out_dir / "smoke-mask.png", suite.get("mask", {}))
            except ImportError as exc:
                mask_path = None
                log(f"[smoke] 沒有 Pillow,無法產生遮罩: {exc}")
        if any(a == "{mask}" for a in entry["args"]) and mask_path is None:
            rec = {"id": entry["id"], "task": entry["task"], "status": SKIPPED,
                   "reason": "沒有 Pillow,無法產生遮罩", "duration_s": None, "seed_requested": entry["seed"],
                   "seeds_resolved": None, "seed_note": entry.get("seed_note"), "outputs": [],
                   "result_json": None, "missing": [], "dependency_only": False}
        else:
            rec = run_task(entry, env, out_dir, outputs_by_id, mask_path, results, runner=runner,
                           task_timeout=task_timeout, comfy_url=comfy_url, config_path=config_path,
                           generate=generate)
        rec["dependency_only"] = entry["id"] in auto
        results[entry["id"]] = rec
        records.append(rec)
        log(f"[smoke] {entry['id']}: {rec['status']}" + (f" ({rec['reason']})" if rec.get("reason") else ""))
    return build_report(suite, env, records, started, utc_now(),
                        selection=list(wanted) if wanted else None)


def build_parser():
    ap = argparse.ArgumentParser(description="固定煙霧測試套件(技術檢查,不評美術)")
    ap.add_argument("--output-dir", required=True, help="本次執行的輸出資料夾(報告、各 task 輸出、log 都在這裡)")
    ap.add_argument("--suite", default=DEFAULT_SUITE, help=f"套件 id(預設 {DEFAULT_SUITE})")
    ap.add_argument("--tasks", help="只跑這些 task id(逗號分隔;其依賴的上游 task 會自動補入)")
    ap.add_argument("--profile", dest="profile_id", help="明確指定圖片模型設定檔;預設用快照 default_profile")
    ap.add_argument("--comfyui-path", help="ComfyUI 路徑(算環境指紋用);預設從快照推得")
    ap.add_argument("--comfy-url", help="轉給 generate.py 的 ComfyUI URL")
    ap.add_argument("--config", help="轉給 generate.py 的 runtime config")
    ap.add_argument("--task-timeout", type=float, default=DEFAULT_TASK_TIMEOUT, help="單一 task 子程序秒數上限")
    ap.add_argument("--record", metavar="REPO_ROOT",
                    help="把報告複製到 <REPO_ROOT>/docs/knowledge/validation/<platform_key>/<日期>-<suite>-<profile>.json")
    ap.add_argument("--record-images", action="store_true", help="--record 時一併複製總覽圖 JPG(不複製原圖)")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    out_dir = Path(os.path.abspath(os.path.expanduser(args.output_dir)))
    try:
        suite = load_suite(args.suite)
        wanted = [t.strip() for t in args.tasks.split(",") if t.strip()] if args.tasks else None
        select_tasks(suite, wanted)  # 先驗證 id
        if (out_dir / REPORT_NAME).exists():
            raise SmokeError(f"{out_dir / REPORT_NAME} 已存在;請換一個 --output-dir,不覆寫舊報告")
        env = resolve_environment(HERE, args.comfyui_path, args.profile_id)
    except SmokeError as exc:
        print(f"smoke: {exc}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    report = run_suite(suite, env, out_dir, wanted, task_timeout=args.task_timeout,
                       comfy_url=args.comfy_url, config_path=args.config,
                       log=lambda msg: print(msg, flush=True))
    sheet = make_contact_sheet(report, out_dir)
    report["contact_sheet"] = SHEET_NAME if sheet else None
    report_path = write_report(out_dir, report)
    print(f"[smoke] 報告: {report_path}" + (f"\n[smoke] 總覽圖: {sheet}" if sheet else "\n[smoke] 沒有 Pillow,略過總覽圖"))
    summary = report["summary"]
    print(f"[smoke] 整體 {summary['overall']}: {summary['counts']}  ({TECHNICAL_ONLY_NOTE})")
    if args.record:
        for path in record_report(args.record, report_path, sheet, report, args.record_images):
            print(f"[smoke] 已記錄: {path}")
    return 1 if summary["overall"] == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
