"""研究用：在記憶體裡改 template graph 的固定參數，再交給正式 runner 執行（不是產線入口）。

用法（ComfyUI venv 的 python，從 repo 根目錄執行）：
    python ab_run.py video/h3/img2video-last --patch 17.sampler_name=euler -- \
        --set start_image=a.png --set last_image=a.png --set prompt=... --set seed=3001 \
        --allow-unverified-platform --output-dir output/experiments/.../e1_euler

--patch NODE.INPUT=VALUE 可重複；VALUE 先試 JSON 解析（數字、布林），失敗就當字串。
template 檔案不變；runner 照常做 preflight、上傳、queue、下載並寫 run.result.json。
改了哪些參數另外寫進 <output-dir>/experiment_patch.json，patched graph 的 sha256 會和 template 原值不同。
"""
import argparse
import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO / "tools_src"))

from comfyui_pipeline.runner import cli  # noqa: E402


def parse_patch(text):
    target, _, raw = text.partition("=")
    node, _, key = target.partition(".")
    if not node or not key or not _:
        raise SystemExit(f"--patch 格式要是 NODE.INPUT=VALUE：{text!r}")
    if raw.startswith("@link:"):  # @link:NODE:OUTPUT → 連線到別的節點
        src, _, out = raw[len("@link:"):].partition(":")
        return node, key, [src, int(out)]
    try:
        value = json.loads(raw)
    except ValueError:
        value = raw
    return node, key, value


def parse_add_node(text):
    node, _, raw = text.partition("=")
    data = json.loads(raw)
    if not node or "class_type" not in data or "inputs" not in data:
        raise SystemExit(f"--add-node 格式要是 ID={{\"class_type\":...,\"inputs\":{{...}}}}：{text!r}")
    return node, data


def main():
    argv = sys.argv[1:]
    if "--" not in argv:
        raise SystemExit("要用 -- 分隔 ab_run 參數與 gameart run 參數")
    split = argv.index("--")
    parser = argparse.ArgumentParser()
    parser.add_argument("template")
    parser.add_argument("--patch", action="append", default=[])
    parser.add_argument("--add-node", action="append", default=[])
    args = parser.parse_args(argv[:split])
    run_args = argv[split + 1:]
    patches = [parse_patch(p) for p in args.patch]
    added = [parse_add_node(a) for a in args.add_node]

    original_load = cli._load
    applied = []

    def patched_load(root, template_id):
        template = original_load(root, template_id)
        graph = copy.deepcopy(template.graph)
        for node, data in added:
            if node in graph:
                raise SystemExit(f"--add-node 的 id {node} 已存在")
            graph[node] = data
            applied.append({"node": node, "added": data})
        for node, key, value in patches:
            if node not in graph:
                raise SystemExit(f"graph 沒有節點 {node}")
            before = graph[node]["inputs"].get(key)
            if isinstance(before, list) and not isinstance(value, list):
                raise SystemExit(f"{node}.{key} 是連線，只能用 @link: 改")
            graph[node]["inputs"][key] = value
            applied.append({"node": node, "input": key, "before": before, "after": value})
        template.graph = graph
        return template

    cli._load = patched_load
    code = cli.main([args.template] + run_args)
    out_dir = None
    if "--output-dir" in run_args:
        out_dir = Path(run_args[run_args.index("--output-dir") + 1])
    if out_dir and out_dir.is_dir():
        (out_dir / "experiment_patch.json").write_text(
            json.dumps({"template": args.template, "patches": applied}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
