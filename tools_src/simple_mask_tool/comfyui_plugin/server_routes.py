import base64
import io
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web
from PIL import Image

import folder_paths
from server import PromptServer

from ..core import build_outputs, load_source_image, normalize_editor_mask, save_png, selected_ratio, validate_token


PLUGIN_DIR = Path(__file__).resolve().parent
WEB_DIR = PLUGIN_DIR / "web"
SESSION_ROOT = Path(folder_paths.get_temp_directory()) / "simple-mask-tool"


def _session_dir(token):
    return SESSION_ROOT / validate_token(token)


def _read_meta(token):
    path = _session_dir(token) / "session.json"
    if not path.is_file():
        raise web.HTTPNotFound(text="mask session not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_meta(token, meta):
    (_session_dir(token) / "session.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _data_url_bytes(value):
    prefix = "data:image/png;base64,"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ValueError("mask_png must be a PNG data URL")
    try:
        return base64.b64decode(value[len(prefix):], validate=True)
    except Exception as exc:
        raise ValueError("mask_png contains invalid base64") from exc


_registered = False


def register_routes():
    global _registered
    if _registered:
        return
    _registered = True
    routes = PromptServer.instance.routes

    @routes.get("/simple-mask/{token}")
    async def editor_page(request):
        _read_meta(request.match_info["token"])
        return web.FileResponse(WEB_DIR / "index.html")

    @routes.post("/simple-mask/api/sessions")
    async def create_session(request):
        reader = await request.multipart()
        purpose = ""
        image_data = None
        async for field in reader:
            if field.name == "purpose":
                purpose = (await field.text())[:500]
            elif field.name == "image":
                image_data = await field.read(decode=False)
        try:
            source = load_source_image(image_data)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        token = secrets.token_urlsafe(24)
        directory = _session_dir(token)
        directory.mkdir(parents=True, exist_ok=False)
        save_png(source, directory / "source.png")
        now = datetime.now(timezone.utc).isoformat()
        meta = {
            "session_id": token,
            "purpose": purpose,
            "width": source.width,
            "height": source.height,
            "status": "pending",
            "selected_ratio": 0.0,
            "created_at": now,
            "completed_at": None,
        }
        _write_meta(token, meta)
        origin = f"{request.scheme}://{request.host}"
        return web.json_response({**meta, "editor_url": f"{origin}/simple-mask/{token}"})

    @routes.get("/simple-mask/api/sessions/{token}")
    async def session_status(request):
        return web.json_response(_read_meta(request.match_info["token"]))

    @routes.get("/simple-mask/api/sessions/{token}/source")
    async def session_source(request):
        token = request.match_info["token"]
        _read_meta(token)
        return web.FileResponse(_session_dir(token) / "source.png")

    @routes.post("/simple-mask/api/sessions/{token}/save")
    async def save_session(request):
        token = request.match_info["token"]
        meta = _read_meta(token)
        try:
            payload = await request.json()
            mask_data = _data_url_bytes(payload.get("mask_png"))
            mask = normalize_editor_mask(mask_data, (meta["width"], meta["height"]))
            ratio = selected_ratio(mask)
            if ratio <= 0.000001:
                raise ValueError("遮罩是空的，請先塗紅要修改的範圍")
            if ratio >= 0.98 and not payload.get("confirm_near_full"):
                return web.json_response(
                    {"error": "near_full", "selected_ratio": ratio}, status=409
                )
            source = Image.open(_session_dir(token) / "source.png").convert("RGBA")
            editor, comfy, preview = build_outputs(source, mask)
            save_png(editor, _session_dir(token) / "mask_editor.png")
            save_png(comfy, _session_dir(token) / "mask_comfy.png")
            save_png(preview, _session_dir(token) / "preview.png")
        except (ValueError, json.JSONDecodeError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        meta["status"] = "completed"
        meta["selected_ratio"] = ratio
        meta["completed_at"] = datetime.now(timezone.utc).isoformat()
        _write_meta(token, meta)
        return web.json_response(meta)

    @routes.get("/simple-mask/api/sessions/{token}/result/{kind}")
    async def session_result(request):
        token = request.match_info["token"]
        meta = _read_meta(token)
        if meta.get("status") != "completed":
            raise web.HTTPConflict(text="mask session is not completed")
        names = {
            "editor": "mask_editor.png",
            "comfy": "mask_comfy.png",
            "preview": "preview.png",
        }
        filename = names.get(request.match_info["kind"])
        if not filename:
            raise web.HTTPNotFound(text="unknown result kind")
        return web.FileResponse(_session_dir(token) / filename)
