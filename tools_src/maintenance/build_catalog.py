"""Build templates/catalog.json and the capability index from template.json.

Offline. Not imported by the runner. Does not validate graphs and does not
talk to ComfyUI. The two outputs say they are generated; edit template.json
and run this script again.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

NOTE = "自動產生，勿手改。改 template.json 後重跑 tools_src/maintenance/build_catalog.py。"


def repo_root_from_here():
    return Path(__file__).resolve().parents[2]


def _media(template_id, data):
    if template_id.startswith("video/"):
        return "video"
    if template_id.startswith("image/"):
        return "image"
    kinds = set()
    for item in data.get("outputs") or []:
        if isinstance(item, dict) and item.get("kind"):
            kinds.add(item["kind"])
    if "video" in kinds:
        return "video"
    if kinds & {"image", "image_sequence"}:
        return "image"
    return None


def _models(data):
    rows = []
    for item in data.get("models") or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "role": item.get("role"),
            "filename": item.get("filename"),
            "directory": item.get("directory"),
        })
    return rows


def _gate(data):
    gate = data.get("capability_gate")
    return gate if isinstance(gate, dict) else {}


def _platforms(data):
    raw = _gate(data).get("platforms")
    if not isinstance(raw, dict):
        raw = data.get("platforms") or {}
    if not isinstance(raw, dict):
        return {}
    return {
        key: (value.get("status") if isinstance(value, dict) else None)
        for key, value in raw.items()
    }


def _nodes(data):
    rows = []
    for item in data.get("requires_custom_nodes") or []:
        if isinstance(item, dict):
            rows.append({"id": item.get("id"), "source": item.get("source")})
    return rows


def entry_from_data(template_id, data):
    if data.get("id") != template_id:
        raise SystemExit(f"{template_id}: id 是 {data.get('id')!r}，和資料夾不一致")
    upstream = data.get("provenance", {}).get("upstream") if isinstance(data.get("provenance"), dict) else None
    return {
        "id": template_id,
        "version": data.get("version"),
        "title": data.get("title"),
        "summary": data.get("summary"),
        "media": _media(template_id, data),
        "capability": _gate(data).get("capability", data.get("capability")),
        "status": data.get("status"),
        "min_comfyui_version": data.get("min_comfyui_version"),
        "requires_custom_nodes": _nodes(data),
        "platforms": _platforms(data),
        "frame_anchoring": data.get("frame_anchoring"),
        "models": _models(data),
        "upstream_kind": upstream.get("kind") if isinstance(upstream, dict) else None,
        "upstream_name": upstream.get("name") if isinstance(upstream, dict) else None,
    }


def discover_entries(templates_root):
    root = Path(templates_root)
    entries = []
    for path in sorted(root.rglob("template.json")):
        rel = path.parent.relative_to(root)
        if any(part.startswith("_") for part in rel.parts):
            continue
        template_id = rel.as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"{template_id}: 讀不到 template.json: {exc}") from exc
        entries.append(entry_from_data(template_id, data))
    entries.sort(key=lambda item: item["id"])
    return entries


def catalog_document(templates_root):
    return {
        "schema_version": 1,
        "note": NOTE,
        "generated_by": "tools_src/maintenance/build_catalog.py",
        "templates": discover_entries(templates_root),
    }


def _json_text(document):
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def _anchor_value(value):
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    return str(value)


def _platforms_text(platforms):
    if not platforms:
        return "（未列平台）"
    return "、".join(f"{key} {status}" for key, status in platforms.items())


def _models_text(models):
    if not models:
        return "（無）"
    return "、".join(
        f"{item.get('filename') or '?'}（{item.get('directory') or 'directory 未填'}，{item.get('role') or 'role 未填'}）"
        for item in models
    )


def _nodes_text(nodes):
    if not nodes:
        return "（只用 core）"
    return "、".join(f"{item.get('id')} [{item.get('source')}]" for item in nodes)


def markdown_page(document):
    lines = [
        "---",
        "type: index",
        "status: current",
        "generated: true",
        "---",
        "# Template 能力索引",
        "",
        NOTE,
        "",
        "機器可讀的同一份清單是 [templates/catalog.json](../../../templates/catalog.json)。",
        "這頁不記 graph hash，也不代替 `template.json` 的模型 pin。",
        "",
    ]
    for item in document["templates"]:
        anchoring = item.get("frame_anchoring") or {}
        if isinstance(anchoring, dict) and anchoring:
            anchor = "、".join(
                f"{key}={_anchor_value(value)}" for key, value in anchoring.items()
            )
        else:
            anchor = "（無）"
        lines.extend([
            f"## `{item['id']}`",
            "",
            f"- 用途：{item.get('title') or ''}",
            f"- 摘要：{item.get('summary') or ''}",
            f"- 媒體：{item.get('media') or '（未標）'}",
            f"- 能力：{item.get('capability') or '（未標）'}",
            f"- 狀態：{item.get('status')}（v{item.get('version')}）",
            f"- 最低 ComfyUI：{item.get('min_comfyui_version') or '（未標）'}",
            f"- 第三方節點：{_nodes_text(item.get('requires_custom_nodes') or [])}",
            f"- 平台：{_platforms_text(item.get('platforms') or {})}",
            f"- 首尾幀：{anchor}",
            f"- 模型：{_models_text(item.get('models') or [])}",
            f"- 上游：{item.get('upstream_kind') or '（無）'}"
            + (f" `{item['upstream_name']}`" if item.get("upstream_name") else ""),
            "",
        ])
    return "\n".join(lines).replace("\r\n", "\n")


def paths(repo):
    repo = Path(repo)
    return repo / "templates" / "catalog.json", repo / "docs" / "knowledge" / "maintenance" / "template-catalog.md"


def render(repo):
    repo = Path(repo)
    document = catalog_document(repo / "templates")
    return _json_text(document).encode("utf-8"), markdown_page(document).encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="從 template.json 產生 catalog（只讀 template，可寫兩個產出）")
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--write", action="store_true", help="寫回 catalog.json 與能力索引頁")
    parser.add_argument("--check", action="store_true", help="產出與已提交的檔不同就結束碼 1")
    args = parser.parse_args(argv)
    repo = args.repo or repo_root_from_here()
    catalog_bytes, page_bytes = render(repo)
    catalog_path, page_path = paths(repo)
    if args.write:
        catalog_path.write_bytes(catalog_bytes)
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_bytes(page_bytes)
        print(f"wrote {catalog_path}")
        print(f"wrote {page_path}")
        return 0
    if args.check or not args.write:
        stale = []
        for path, expected in ((catalog_path, catalog_bytes), (page_path, page_bytes)):
            actual = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else None
            if actual != expected:
                stale.append(str(path))
        if stale:
            print("catalog 不是最新。重跑：python tools_src/maintenance/build_catalog.py --write")
            for name in stale:
                print(f"  {name}")
            return 1
        print(f"catalog 是最新的（{len(json.loads(catalog_bytes)['templates'])} 份）")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
