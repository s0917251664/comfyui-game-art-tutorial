import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def _base_url(value):
    return value.rstrip("/")


def _multipart(fields, file_field, file_path):
    boundary = "----SimpleMask" + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode("utf-8"), b"\r\n",
        ])
    path = Path(file_path)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(),
        path.read_bytes(), b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _json_request(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def create_session(args):
    image = Path(args.image).resolve()
    if not image.is_file():
        raise SystemExit(f"image not found: {image}")
    body, content_type = _multipart({"purpose": args.purpose or ""}, "image", image)
    request = urllib.request.Request(
        _base_url(args.comfy_url) + "/simple-mask/api/sessions",
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"cannot create mask session: {exc}") from exc
    payload["source_path"] = str(image)
    payload["comfy_url"] = _base_url(args.comfy_url)
    output = Path(args.output_dir).resolve() / "mask_sessions" / payload["session_id"]
    output.mkdir(parents=True, exist_ok=False)
    record = output / "session.json"
    record.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SESSION_ID={payload['session_id']}")
    print(f"EDITOR_URL={payload['editor_url']}")
    print(f"SESSION_RECORD={record}")


def status_session(args):
    payload = _json_request(
        _base_url(args.comfy_url) + f"/simple-mask/api/sessions/{args.session_id}",
        timeout=args.timeout,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def fetch_session(args):
    base = _base_url(args.comfy_url)
    status = _json_request(base + f"/simple-mask/api/sessions/{args.session_id}", args.timeout)
    if status.get("status") != "completed":
        raise SystemExit(f"mask session is not completed: {status.get('status')}")
    output = Path(args.output_dir).resolve() / "mask_sessions" / args.session_id
    output.mkdir(parents=True, exist_ok=True)
    names = {
        "editor": "mask_editor.png",
        "comfy": "mask_comfy.png",
        "preview": "preview.png",
    }
    for kind, filename in names.items():
        url = base + f"/simple-mask/api/sessions/{args.session_id}/result/{kind}"
        with urllib.request.urlopen(url, timeout=args.timeout) as response:
            (output / filename).write_bytes(response.read())
    (output / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"MASK={output / 'mask_comfy.png'}")
    print(f"PREVIEW={output / 'preview.png'}")


def build_parser():
    parser = argparse.ArgumentParser(description="Create and retrieve local ComfyUI mask sessions")
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    parser.add_argument("--timeout", type=float, default=30)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--image", required=True)
    create.add_argument("--purpose", default="")
    create.add_argument("--output-dir", required=True)
    create.set_defaults(func=create_session)
    status = sub.add_parser("status")
    status.add_argument("--session-id", required=True)
    status.set_defaults(func=status_session)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--session-id", required=True)
    fetch.add_argument("--output-dir", required=True)
    fetch.set_defaults(func=fetch_session)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    args.func(args)


if __name__ == "__main__":
    main()

