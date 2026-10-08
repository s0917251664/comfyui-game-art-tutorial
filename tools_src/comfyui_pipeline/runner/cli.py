"""`gameart.py run`:固定 API graph template 的 list／show／--dry-run／--preflight／實際執行。

    python tools_src/gameart.py run list [--json]
    python tools_src/gameart.py run show <template> [--json]
    python tools_src/gameart.py run <template> --dry-run [--set NAME=VALUE ...] [--values FILE.json]
        [--option NAME] [--no-option NAME] [--output-dir DIR] [--json]
    python tools_src/gameart.py run <template> --preflight [--config local_config.json] [--comfy-url URL]
        [--verify-hashes] [--allow-unverified-platform] [--platform-key KEY] [--set ...] [--output-dir DIR] [--json]
    python tools_src/gameart.py run <template> --set ... [--config ...] [--timeout 秒] [--output-dir DIR] [--json]

--dry-run 不連 ComfyUI;上傳欄位在 graph 裡顯示為 ``<upload:slot>``。--preflight 只讀(GET /object_info、
讀模型檔),不上傳、不 queue,檢查內容見 preflight.py。不加這兩個旗標(實際執行)時先跑同樣的 preflight,
通過才上傳、queue、下載並寫 run.result.json(見 run.py);preflight 擋下時也會寫 status=failed 的 manifest。
"""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from .. import runtime_config as rc
from . import preflight as P
from . import run as R
from . import template as T

TOOLS_SRC = Path(__file__).resolve().parents[2]

DRYRUN_GRAPH = "workflow_api.dryrun.json"
DRYRUN_SUMMARY = "dryrun.json"
PREFLIGHT_FILE = "preflight.json"


class CliError(Exception):
    """使用者可修正的錯誤(結束碼 2)。"""


def _utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def default_templates_root():
    repo_root = rc.find_repo_root(TOOLS_SRC)
    if not repo_root:
        raise CliError("run 只能從 repo 的 tools_src/gameart.py 執行(templates/ 不會部署)")
    return T.templates_root(repo_root)


def _load(root, template_id):
    # 證據文件以 repo 根目錄解析;測試會把 templates 根目錄換成暫存資料夾,所以不用 root.parent
    return T.load_template(root, template_id, repo_root=rc.find_repo_root(TOOLS_SRC) or Path(root).parent)


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ---------- list / show ----------

def cmd_list(args, root, out):
    rows = []
    for tid in T.discover(root):
        try:
            template = _load(root, tid)
        except T.TemplateError as exc:
            rows.append({"id": tid, "error": str(exc)})
            continue
        rows.append({"id": tid, "version": template.version, "status": template.data["status"],
                     "title": template.data["title"], "platforms": T.platform_summary(template)})
    if args.json:
        print(_dump(rows), file=out)
    else:
        for row in rows:
            if "error" in row:
                print(f"{row['id']}  [無法載入] {row['error']}", file=out)
                continue
            platforms = "、".join(f"{k}={v}" for k, v in row["platforms"].items())
            print(f"{row['id']}  v{row['version']}  {row['status']}  {row['title']}  ({platforms})", file=out)
    return 1 if any("error" in row for row in rows) else 0


def _slot_line(name, slot):
    parts = [slot["type"]]
    if slot.get("required"):
        parts.append("必填")
    if "default" in slot:
        parts.append(f"預設 {json.dumps(slot['default'], ensure_ascii=False)}")
    if "default_from" in slot:
        parts.append(f"預設同 {slot['default_from']}")
    if slot.get("validate"):
        parts.append("規則 " + json.dumps(slot["validate"], ensure_ascii=False))
    if slot.get("tested_values"):
        parts.append(f"實測過 {slot['tested_values']}")
    targets = "、".join(f"{t['node']}.{t['input']}" for t in slot["targets"])
    line = f"  {name}: {'；'.join(parts)} → {targets}"
    if slot.get("help"):
        line += f"\n      {slot['help']}"
    return line


def cmd_show(args, root, out):
    template = _load(root, args.template)
    data = template.data
    if args.json:
        payload = dict(data, graph_sha256=template.graph_sha256, graph_canonical_sha256=template.graph_canonical_sha256,
                       template_json_sha256=template.template_json_sha256)
        print(_dump(payload), file=out)
        return 0
    print(f"{template.id}  v{template.version}  {data['status']}", file=out)
    print(f"{data['title']}\n{data['summary']}", file=out)
    if data.get("status_note"):
        print(f"狀態說明: {data['status_note']}", file=out)
    print(f"graph: {data['graph']['file']}  sha256 {template.graph_sha256[:16]}…  canonical {template.graph_canonical_sha256[:16]}…",
          file=out)
    print("\nslots:", file=out)
    for name, slot in data["slots"].items():
        if slot["type"] == "output_prefix":
            print(f"  {name}: 由 runner 產生(gameart/<template>/<run_id>)", file=out)
        else:
            print(_slot_line(name, slot), file=out)
    if template.options:
        print("\noptions:", file=out)
        for name, option in template.options.items():
            print(f"  {name}: 預設 {str(option['default']).lower()}  {option.get('help', '')}", file=out)
    for rule in data.get("constraints") or []:
        print(f"constraint: {rule['rule']} {rule['slot']} 在 {rule['width']}×{rule['height']} 內", file=out)
    if data.get("fixed_notes"):
        print(f"\n固定參數: {data['fixed_notes']}", file=out)
    anchor = data["frame_anchoring"]
    print(f"首尾幀: first={anchor['first']} last={anchor['last']}  參考圖用途={anchor['reference_role']}  "
          f"時間對齊={anchor['time_alignment']}" + ("  接縫=第 " + "/".join(map(str, anchor["continuity"]["seam_frames"])) + " 幀" if anchor["continuity"] else ""),
          file=out)
    print("\nmodels:", file=out)
    for model in data["models"]:
        pin = "sha256 " + model["sha256"][:12] + "…" if model.get("sha256") else f"pin 未補齊: {model.get('pin_status')}"
        size = f"{model['size_bytes']:,} bytes" if model.get("size_bytes") else "大小未知"
        auto = "；節點缺檔會自動下載,preflight 會先確認檔案在本機" if model.get("auto_download") else ""
        print(f"  {model['role']}: {model['filename']}  ({model.get('path') or '路徑未確認'}, {size}, {pin}{auto})", file=out)
    print("\n平台:", file=out)
    for key, value in data["capability_gate"]["platforms"].items():
        extra = value.get("evidence") or value.get("notes") or ""
        print(f"  {key}: {value['status']}  {extra}", file=out)
    print("\noutputs: " + "、".join(f"{o['id']}(node {o['node']}, {o['kind']}, {o['role']})" for o in data["outputs"]),
          file=out)
    return 0


# ---------- dry-run ----------

def _read_text_file(path):
    with open(path, encoding="utf-8-sig") as handle:
        return handle.read().rstrip("\r\n")


def parse_sets(items):
    values = {}
    for item in items or []:
        if "=" not in item:
            raise CliError(f"--set 要寫成 NAME=VALUE,收到 {item!r}")
        name, value = item.split("=", 1)
        name = name.strip()
        if value.startswith("@"):
            path = value[1:]
            try:
                value = _read_text_file(path)
            except OSError as exc:
                raise CliError(f"--set {name}=@{path}: 讀不到檔案: {exc}") from exc
        values[name] = value
    return values


def load_values_file(path):
    if not path:
        return {}
    try:
        data = T.read_json(path)
    except (OSError, ValueError) as exc:
        raise CliError(f"--values 讀取失敗: {exc}") from exc
    if not isinstance(data, dict):
        raise CliError("--values 必須是 JSON object({slot: 值})")
    return data


def _prepare_output_dir(path):
    out = Path(os.path.abspath(os.path.expanduser(path)))
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise CliError(f"--output-dir 必須是不存在或空的資料夾: {out}")
    out.mkdir(parents=True, exist_ok=True)
    return out


def _collect_values(args):
    values = load_values_file(args.values)
    values.update(parse_sets(args.set))  # --set 優先
    options = {name: True for name in args.option or []}
    for name in args.no_option or []:
        if name in options:
            raise CliError(f"--option 與 --no-option 同時指定了 {name}")
        options[name] = False
    return values, options


def _dry_run_summary(template, resolution, run_id, graph, changes, warnings):
    return {
        "kind": "template_dry_run", "template": {"id": template.id, "version": template.version,
                                                 "status": template.data["status"],
                                                 "graph_sha256": template.graph_sha256,
                                                 "graph_canonical_sha256": template.graph_canonical_sha256,
                                                 "template_json_sha256": template.template_json_sha256},
        "run_id": run_id, "slot_values": resolution["slot_values"], "seed_sources": resolution["seed_sources"],
        "options": resolution["options"],
        "inputs": {name: os.path.abspath(path) for name, path in resolution["inputs"].items()},
        "changed_inputs": changes, "patched_graph_sha256": T.canonical_sha256(graph) if graph else None,
        "platforms": T.platform_summary(template), "warnings": warnings,
        "note": "dry-run:沒有連線 ComfyUI、沒有上傳、沒有 queue;上傳欄位以 <upload:slot> 表示",
    }


def _input_file_warnings(resolution, mode):
    warnings, problems = [], []
    for name, path in resolution["inputs"].items():
        if not os.path.isfile(path):
            if mode == "run":
                problems.append(f"slot {name} 的檔案不存在: {os.path.abspath(path)}")
            else:
                warnings.append(f"slot {name} 的檔案不存在: {path}({mode} 不上傳,只提醒)")
    return warnings, problems


def _eprint(message, out, err):
    # stdout 可能有緩衝:先 flush,stderr 的訊息才不會跑到前面的輸出之前
    out.flush()
    print(message, file=err, flush=True)


def _hash_cache_path(args, settings, folder=None):
    if folder:
        return os.path.join(os.path.dirname(os.fspath(folder)), P.HASH_CACHE_NAME)
    if args.output_dir:
        return os.path.join(os.path.dirname(os.path.abspath(os.path.expanduser(args.output_dir))), P.HASH_CACHE_NAME)
    if settings.get("repo_root"):
        return os.path.join(settings["repo_root"], "output", "runs", P.HASH_CACHE_NAME)
    return None


def cmd_run(args, root, out, err, rng=None, fetch_object_info=None):
    """``--dry-run``:只產生 graph。``--preflight``:加上平台、ComfyUI 與模型檔檢查。
    兩者都沒有(實際執行):先做和 --preflight 相同的檢查,通過後才上傳、queue、下載(見 run.py)。"""
    mode = "dry-run" if args.dry_run else "preflight" if args.preflight else "run"
    if mode == "dry-run" and (args.verify_hashes or args.allow_unverified_platform):
        raise CliError("--verify-hashes／--allow-unverified-platform 要搭配 --preflight(dry-run 不連線)")
    if args.timeout is not None and mode != "run":
        raise CliError("--timeout 只用在實際執行(--dry-run／--preflight 不會 queue)")
    if args.timeout is not None and not args.timeout > 0:
        raise CliError(f"--timeout 必須大於 0,收到 {args.timeout:g}")
    if args.run_id and not R.RUN_ID_RE.match(args.run_id):
        raise CliError(f"--run-id 只能用英數字、- 和 _(最多 64 字):{args.run_id!r}")
    template = _load(root, args.template)
    values, options = _collect_values(args)
    run_id = args.run_id or (uuid.uuid4().hex if mode == "run" else uuid.uuid4().hex[:12])
    resolution = T.resolve(template, values, options, run_id=run_id, dry_run=(mode != "run"), rng=rng,
                           allow_missing=(mode == "preflight"))
    graph, changes = None, []
    if not resolution["missing"]:
        graph, changes = T.patch(template, resolution, require_uploads=False)
    file_warnings, file_problems = _input_file_warnings(resolution, mode)
    warnings = list(resolution["warnings"]) + file_warnings
    summary = _dry_run_summary(template, resolution, run_id, graph, changes, warnings)
    if mode == "run":
        return _cmd_execute(args, template, resolution, run_id, warnings, file_problems, summary, out, err,
                            fetch_object_info)
    folder = _prepare_output_dir(args.output_dir) if args.output_dir else None

    if mode == "dry-run":
        if folder:
            (folder / DRYRUN_GRAPH).write_text(_dump(graph) + "\n", encoding="utf-8")
            (folder / DRYRUN_SUMMARY).write_text(_dump(summary) + "\n", encoding="utf-8")
            summary["files"] = {"graph": str(folder / DRYRUN_GRAPH), "summary": str(folder / DRYRUN_SUMMARY)}
        if args.json:
            print(_dump(dict(summary, graph=graph)), file=out)
        else:
            if not folder:
                print(_dump(graph), file=out)
            out.flush()
            for line in _summary_lines(summary):
                print(line, file=err)
        return 0

    settings = _resolve_settings(args)
    report = _preflight(args, template, settings, warnings, file_problems, fetch_object_info, err,
                        _hash_cache_path(args, settings))
    report["run_id"] = run_id
    report["slot_values"] = resolution["slot_values"]
    report["options"] = resolution["options"]
    report["patched_graph_sha256"] = summary["patched_graph_sha256"]
    if folder:
        if graph:
            (folder / DRYRUN_GRAPH).write_text(_dump(graph) + "\n", encoding="utf-8")
        (folder / PREFLIGHT_FILE).write_text(_dump(report) + "\n", encoding="utf-8")
        report["files"] = {"preflight": str(folder / PREFLIGHT_FILE)}
        if graph:
            report["files"]["graph"] = str(folder / DRYRUN_GRAPH)
    if args.json:
        print(_dump(report), file=out)
    else:
        for line in P.summary_lines(report):
            print(line, file=out)
        for name in ("preflight", "graph"):
            if name in report.get("files", {}):
                print(f"[preflight] 已寫入 {report['files'][name]}", file=out)
    out.flush()
    return 0 if report["status"] == P.PASS else 1


def _resolve_settings(args):
    try:
        return P.resolve_settings(args.config, args.comfy_url, args.snapshot_dir, args.platform_key,
                                  script_dir=TOOLS_SRC)
    except P.PreflightConfigError as exc:
        raise CliError(str(exc)) from exc


def _preflight(args, template, settings, warnings, file_problems, fetch_object_info, err, hash_cache_path):
    report = P.run_preflight(template, settings, verify_hashes=args.verify_hashes,
                             allow_unverified=args.allow_unverified_platform,
                             hash_cache_path=hash_cache_path if args.verify_hashes else None,
                             fetch_object_info=fetch_object_info,
                             progress=lambda line: print(f"[preflight] {line}", file=err, flush=True))
    report["problems"] = file_problems + report["problems"]
    report["warnings"] = warnings + report["warnings"]
    if report["problems"]:
        report["status"] = P.BLOCKED
    return report


def _cmd_execute(args, template, resolution, run_id, warnings, file_problems, summary, out, err, fetch_object_info):
    """實際執行:preflight → run.execute。preflight 擋下也寫 failed manifest(結束碼 1)。"""
    settings = _resolve_settings(args)
    if args.output_dir:
        folder = _prepare_output_dir(args.output_dir)
    else:
        if not settings.get("repo_root"):
            raise CliError("找不到 repo 根目錄,請用 --output-dir 指定輸出資料夾")
        folder = _prepare_output_dir(R.default_output_dir(settings["repo_root"], template.id, run_id))
    progress = err if args.json else out
    report = _preflight(args, template, settings, warnings, file_problems, fetch_object_info, err,
                        _hash_cache_path(args, settings, folder))
    report.update(run_id=run_id, slot_values=resolution["slot_values"], options=resolution["options"],
                  patched_graph_sha256=summary["patched_graph_sha256"], note="實際執行前的 preflight(只讀)")
    (folder / PREFLIGHT_FILE).write_text(_dump(report) + "\n", encoding="utf-8")
    for line in P.summary_lines(report):
        print(line, file=progress)
    progress.flush()
    code, manifest, path = R.execute(template, resolution, settings, report, folder, run_id=run_id,
                                     timeout=args.timeout or R.DEFAULT_TIMEOUT, out=progress)
    if args.json:
        print(_dump({"status": manifest["status"], "exit_code": code, "result": path,
                     "prompt_id": manifest["prompt_id"], "failure": manifest["failure"],
                     "outputs": [o["path"] for o in manifest["outputs"]]}), file=out)
    out.flush()
    return code


def _summary_lines(summary):
    lines = [f"[run] dry-run {summary['template']['id']} v{summary['template']['version']}  run_id={summary['run_id']}"]
    for name, source in summary["seed_sources"].items():
        lines.append(f"[run] {name} = {summary['slot_values'][name]}({source})")
    if summary["options"]:
        lines.append("[run] options: " + "、".join(f"{k}={str(v).lower()}" for k, v in summary["options"].items()))
    lines.append(f"[run] 改到的欄位({len(summary['changed_inputs'])}): {', '.join(summary['changed_inputs'])}")
    lines.append("[run] 平台: " + "、".join(f"{k}={v}" for k, v in summary["platforms"].items()))
    for warning in summary["warnings"]:
        lines.append(f"[run] 提醒: {warning}")
    if "files" in summary:
        lines.append(f"[run] 已寫入 {summary['files']['graph']}")
        lines.append(f"[run] 已寫入 {summary['files']['summary']}")
    lines.append(f"[run] {summary['note']}")
    return lines


# ---------- 進入點 ----------

def build_list_parser():
    p = argparse.ArgumentParser(prog="gameart.py run list", description="列出 templates")
    p.add_argument("--json", action="store_true")
    return p


def build_show_parser():
    p = argparse.ArgumentParser(prog="gameart.py run show", description="顯示 template 的 slots、models、平台狀態")
    p.add_argument("template", help="template id,例如 video/wan-animate/mix")
    p.add_argument("--json", action="store_true")
    return p


def build_run_parser():
    p = argparse.ArgumentParser(
        prog="gameart.py run",
        description="依 template 執行固定 graph。--dry-run 不連線;--preflight 檢查平台、ComfyUI 與模型檔;"
                    "不加這兩個旗標時先 preflight,通過才上傳、queue、下載並寫 run.result.json。"
                    "子命令: run list、run show <template>",
        epilog="結束碼:0 通過(實際執行時=完成且技術檢查通過,美術接受仍待人工);1 preflight 擋下或執行失敗"
               "(仍會寫 status=failed 的 run.result.json);2 參數、設定或 template 錯誤")
    p.add_argument("template", help="template id,例如 video/wan-animate/mix")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只驗證並輸出 patched graph,不連線")
    mode.add_argument("--preflight", action="store_true",
                      help="檢查平台、ComfyUI 節點與模型檔;不上傳、不 queue(slot 沒給齊時只檢查環境)")
    p.add_argument("--set", action="append", metavar="NAME=VALUE",
                   help="指定 slot 值,可重複;VALUE 以 @ 開頭表示從 UTF-8 檔讀取(可帶 BOM)")
    p.add_argument("--values", metavar="FILE.json", help="一次給多個 slot 的 JSON 檔;--set 優先")
    p.add_argument("--option", action="append", metavar="NAME", help="啟用 option(例如 keep_audio)")
    p.add_argument("--no-option", action="append", metavar="NAME", help="停用 option")
    p.add_argument("--output-dir", help="dry-run／preflight 寫入 workflow_api.dryrun.json 與 dryrun.json／preflight.json;"
                                        "實際執行寫入所有紀錄與輸出(預設 <repo>/output/runs/<日期>-<template>-<run_id>)。"
                                        "必須不存在或是空資料夾")
    p.add_argument("--config", help="local_config.json(相對路徑以 repo 根目錄解析;從 repo 執行時預設用 <repo>/local_config.json)")
    p.add_argument("--comfy-url", help="覆寫 ComfyUI URL(優先順序:--comfy-url > COMFY_URL/COMFYUI_URL > 設定檔)")
    p.add_argument("--snapshot-dir", help="機器快照資料夾(device_config.json);預設 <comfyui_path>/tools")
    p.add_argument("--platform-key", help="明確指定平台(例如 windows-cuda、macos-mps);預設讀 device_config.json")
    p.add_argument("--verify-hashes", action="store_true", help="完整計算模型檔 sha256(有快取;預設只核對大小)")
    p.add_argument("--allow-unverified-platform", action="store_true",
                   help="平台狀態不是 technical_pass(或 graph 寫死 cuda)時仍放行;結果只能當技術試驗")
    p.add_argument("--timeout", type=float, help=f"實際執行時等待 ComfyUI 完成的秒數(預設 {R.DEFAULT_TIMEOUT});"
                                                 "逾時不重送,只會刪除自己還在 pending 的 prompt")
    p.add_argument("--run-id", help=argparse.SUPPRESS)  # 測試與比對用:固定 output prefix
    p.add_argument("--json", action="store_true",
                   help="stdout 只輸出一個 JSON(dry-run:摘要＋graph;preflight:報告;實際執行:狀態與 manifest 路徑)")
    return p


def main(argv=None, *, root=None, out=None, err=None, rng=None, fetch_object_info=None):
    _utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    out, err = out or sys.stdout, err or sys.stderr
    try:
        root = Path(root) if root else default_templates_root()
        if argv and argv[0] == "list":
            return cmd_list(build_list_parser().parse_args(argv[1:]), root, out)
        if argv and argv[0] == "show":
            return cmd_show(build_show_parser().parse_args(argv[1:]), root, out)
        return cmd_run(build_run_parser().parse_args(argv), root, out, err, rng=rng,
                       fetch_object_info=fetch_object_info)
    except (CliError, T.TemplateError) as exc:
        _eprint(f"run: {exc}", out, err)
        return 2
