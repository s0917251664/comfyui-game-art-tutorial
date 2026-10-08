"""Compare a template's recorded upstream blob with the file on GitHub.

Read-only. Needs the network. Not part of the runner. Does not write files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/{rev}/templates/{name}.json"


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def load_upstream(repo: Path, template_id: str) -> dict:
    path = repo / "templates" / template_id / "template.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    upstream = data.get("provenance", {}).get("upstream")
    if not isinstance(upstream, dict):
        raise SystemExit(f"{template_id} 沒有 provenance.upstream")
    return upstream


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "gameart-upstream-diff"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.URLError as exc:
        raise SystemExit(f"無法下載 {url}: {exc}") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="比對 template 記錄的上游 blob（只讀，需連網）")
    parser.add_argument("--template", required=True, help="template id，例如 video/wan-vace/inpaint")
    parser.add_argument("--rev", default="main", help="workflow_templates 的 git revision，預設 main")
    parser.add_argument("--repo", type=Path, default=None, help="repo 根目錄，預設是此檔的上兩層")
    parser.add_argument("--file", type=Path, default=None, help="改比對本機檔，不連網（測試用）")
    args = parser.parse_args(argv)
    repo = args.repo or Path(__file__).resolve().parents[2]
    upstream = load_upstream(repo, args.template)
    if upstream.get("kind") != "workflow_templates" or not upstream.get("name") or not upstream.get("blob"):
        raise SystemExit("這份 template 的 upstream 不是帶 blob 的 workflow_templates，沒有可比的官方檔")
    if args.file:
        data = args.file.read_bytes()
        url = str(args.file)
    else:
        url = RAW.format(rev=args.rev, name=upstream["name"])
        data = fetch(url)
    actual = git_blob_sha1(data)
    expected = upstream["blob"]
    print(f"template: {args.template}")
    print(f"upstream: {upstream['name']}")
    print(f"source: {url}")
    print(f"recorded blob: {expected}")
    print(f"fetched blob:  {actual}")
    if actual == expected:
        print("結果: 與記錄的 blob 相同")
        return 0
    print("結果: blob 不同。上游可能已更新，或 --rev 不是當初記錄的那一版。此腳本不改 template。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
