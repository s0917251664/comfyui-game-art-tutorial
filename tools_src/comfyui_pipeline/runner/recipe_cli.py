"""`gameart.py recipe`:多步驟 recipe 的 list／show／run／resume。

    python tools_src/gameart.py recipe list [--draft] [--json]
    python tools_src/gameart.py recipe show <id> [--draft] [--json]
    python tools_src/gameart.py recipe run <id> [--draft] --dry-run [--set KEY=VALUE ...] [--output-dir DIR] [--json]
    python tools_src/gameart.py recipe run <id> [--draft] --set KEY=VALUE --output-dir DIR [--json]
    python tools_src/gameart.py recipe resume DIR [--confirm] [--json]

``--dry-run`` 不連 ComfyUI。沒有 ``--confirm`` 的 resume 不會執行確認點之後的步驟。
``_drafts/`` 要加 ``--draft``。實際執行時,template 步驟交給 ``gameart.py run``(同一個 runner,先 preflight);
local 步驟目前不執行(只有 ``_drafts`` 的 recipe 用到),會停下並說明。
"""
import argparse
import json
import sys
from pathlib import Path

from .. import runtime_config as rc
from . import recipe as R

TOOLS_SRC = Path(__file__).resolve().parents[2]


class CliError(Exception):
    """使用者可修正的參數錯誤(結束碼 2)。"""


def _utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def default_roots():
    repo = rc.find_repo_root(TOOLS_SRC)
    if not repo:
        raise CliError("recipe 只能從 repo 的 tools_src/gameart.py 執行(templates/ 不會部署)")
    templates = Path(repo) / "templates"
    return templates / "recipes", templates


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def parse_sets(items):
    values = {}
    for item in items or []:
        if "=" not in item:
            raise CliError(f"--set 要寫成 NAME=VALUE,收到 {item!r}")
        name, value = item.split("=", 1)
        values[name.strip()] = value
    return values


def _eprint(message, out, err):
    out.flush()
    print(message, file=err, flush=True)


def cmd_list(args, recipes_root, templates_root, out):
    rows = []
    for recipe_id in R.discover(recipes_root, include_drafts=args.draft):
        recipe = R.load_recipe(recipes_root, recipe_id, include_drafts=args.draft, templates_root=templates_root)
        rows.append({"id": recipe.id, "version": recipe.version, "status": recipe.data["status"],
                     "title": recipe.data["title"], "draft": recipe.draft})
    if args.json:
        print(_dump(rows), file=out)
    else:
        for row in rows:
            draft = "  (_drafts,需 --draft)" if row["draft"] else ""
            print(f"{row['id']}  v{row['version']}  {row['status']}  {row['title']}{draft}", file=out)
    return 0


def cmd_show(args, recipes_root, templates_root, out):
    recipe = R.load_recipe(recipes_root, args.recipe, include_drafts=args.draft, templates_root=templates_root)
    payload = R.plan(recipe, templates_root)
    if args.json:
        print(_dump(payload), file=out)
    else:
        print(R.format_plan(payload, heading="show"), file=out)
    return 0


def cmd_run(args, recipes_root, templates_root, out, *, executor, clock):
    recipe = R.load_recipe(recipes_root, args.recipe, include_drafts=args.draft, templates_root=templates_root)
    values = parse_sets(args.set)
    if args.dry_run:
        if values:
            R.coerce_inputs(recipe, values, require=False)
        payload = R.plan(recipe, templates_root)
        if args.output_dir:
            folder = R.prepare_output_dir(args.output_dir)
            path = folder / "recipe.dryrun.json"
            path.write_text(_dump(payload) + "\n", encoding="utf-8", newline="\n")
            payload = dict(payload, file=str(path))
        if args.json:
            print(_dump(payload), file=out)
        else:
            print(R.format_plan(payload, heading="dry-run"), file=out)
            if payload.get("file"):
                print(f"[recipe] 已寫入 {payload['file']}", file=out)
        return 0
    if not args.output_dir:
        raise CliError("recipe run 要給 --output-dir(確認點的 state 寫在那裡)")
    code = R.start_run(recipe, args.output_dir, values, templates_root=templates_root,
                       executor=executor, clock=clock, out=None if args.json else out)
    if args.json:
        directory = Path(args.output_dir).expanduser().resolve()
        state = R.load_state(directory)
        notice = "等待確認" if state["status"] == "waiting_confirm" else None
        print(_dump({"exit_code": code, "state": str(directory / R.STATE_FILE), "status": state["status"],
                     "next_index": state["next_index"], "content_review": state["content_review"],
                     "notice": notice}), file=out)
        if notice:
            print(notice, file=out)
    return code


def cmd_resume(args, recipes_root, templates_root, out, *, executor, clock):
    directory = Path(args.directory).expanduser().resolve()
    code = R.resume_run(directory, recipes_root=recipes_root, templates_root=templates_root, confirm=args.confirm,
                        executor=executor, clock=clock, out=out)
    if args.json:
        state = R.load_state(directory)
        print(_dump({"exit_code": code, "state": str(directory / R.STATE_FILE), "status": state["status"],
                     "next_index": state["next_index"], "content_review": state["content_review"]}), file=out)
    return code


def build_list_parser():
    parser = argparse.ArgumentParser(prog="gameart.py recipe list", description="列出 recipe。_drafts 要加 --draft")
    parser.add_argument("--draft", action="store_true", help="連 templates/recipes/_drafts/ 一起列")
    parser.add_argument("--json", action="store_true")
    return parser


def build_show_parser():
    parser = argparse.ArgumentParser(prog="gameart.py recipe show", description="顯示 recipe 的輸入與步驟")
    parser.add_argument("recipe", help="recipe id,例如 object-mark-inpaint")
    parser.add_argument("--draft", action="store_true", help="允許 _drafts 裡的 recipe")
    parser.add_argument("--json", action="store_true")
    return parser


def build_run_parser():
    parser = argparse.ArgumentParser(
        prog="gameart.py recipe run",
        description="展開或執行 recipe。--dry-run 不連線;否則跑到下一個確認點就停。")
    parser.add_argument("recipe", help="recipe id,例如 object-mark-inpaint")
    parser.add_argument("--draft", action="store_true", help="允許 _drafts 裡的 recipe")
    parser.add_argument("--dry-run", action="store_true", help="只展開每一步的 template 與確認點,不執行")
    parser.add_argument("--set", action="append", metavar="KEY=VALUE", help="指定 recipe 輸入,可重複")
    parser.add_argument("--output-dir", help="state 與步驟產物的資料夾;實際執行時必填,必須不存在或是空的")
    parser.add_argument("--json", action="store_true")
    return parser


def build_resume_parser():
    parser = argparse.ArgumentParser(
        prog="gameart.py recipe resume",
        description="從 recipe.state.json 續跑。沒有 --confirm 不會做確認點之後的步驟。")
    parser.add_argument("directory", help="先前 recipe run 的 --output-dir")
    parser.add_argument("--confirm", action="store_true", help="確認目前這個確認點,然後才繼續")
    parser.add_argument("--json", action="store_true")
    return parser


USAGE = """\
用法:
  python tools_src/gameart.py recipe list [--draft]
  python tools_src/gameart.py recipe show <id> [--draft]
  python tools_src/gameart.py recipe run <id> [--draft] --dry-run [--set KEY=VALUE ...] [--output-dir DIR]
  python tools_src/gameart.py recipe run <id> [--draft] --set KEY=VALUE --output-dir DIR
  python tools_src/gameart.py recipe resume DIR [--confirm]

確認點沒有 --confirm 就不會往下做。_drafts 要加 --draft。結束碼:0 展開成功、停在確認點或步驟跑完(內容審查仍是 pending);2 參數或 recipe 錯誤。
"""


def main(argv=None, *, recipes_root=None, templates_root=None, out=None, err=None, executor=None, clock=None):
    _utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    out, err = out or sys.stdout, err or sys.stderr
    try:
        if recipes_root is None:
            recipes_root, templates_root = default_roots()
        elif templates_root is None:
            templates_root = Path(recipes_root).parent
        recipes_root, templates_root = Path(recipes_root), Path(templates_root)
        if not argv or argv[0] in ("-h", "--help"):
            print(USAGE, file=out)
            return 0 if argv and argv[0] in ("-h", "--help") else 2
        command, rest = argv[0], argv[1:]
        if command == "list":
            return cmd_list(build_list_parser().parse_args(rest), recipes_root, templates_root, out)
        if command == "show":
            return cmd_show(build_show_parser().parse_args(rest), recipes_root, templates_root, out)
        if command == "run":
            return cmd_run(build_run_parser().parse_args(rest), recipes_root, templates_root, out,
                           executor=executor or R.TemplateExecutor(templates_root, out=out, err=err), clock=clock)
        if command == "resume":
            return cmd_resume(build_resume_parser().parse_args(rest), recipes_root, templates_root, out,
                              executor=executor or R.TemplateExecutor(templates_root, out=out, err=err), clock=clock)
        raise CliError(f"未知子命令 {command!r}。可用 list、show、run、resume")
    except (CliError, R.RecipeError, argparse.ArgumentError) as exc:
        _eprint(f"recipe: {exc}", out, err)
        return 2
