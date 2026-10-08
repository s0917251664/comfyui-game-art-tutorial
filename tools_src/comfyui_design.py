"""本機 Pillow 合成：物件場景、圖樣重複、檢視表。

不組 ComfyUI graph，不上傳，不排隊。生成仍走既有 generate.py task。
這裡只擺已提供的圖，不推論遮罩、打光或美術驗收。輸出是不透明 RGB。
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
from PIL import Image, ImageDraw
from image_edit_tools import file_record, load_image, new_directory, save_json


def positive(value, name, minimum=1, maximum=4096):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be integer {minimum}..{maximum}")
    return value


def rgb_color(value):
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise ValueError("background must be #RRGGBB")
    try:
        return int(value[1:], 16)
    except ValueError as exc:
        raise ValueError("background must be #RRGGBB") from exc


def _rgb(value):
    packed = rgb_color(value)
    return (packed >> 16) & 255, (packed >> 8) & 255, packed & 255


def check_image(path, transparent=False):
    image = load_image(path)
    if image.width * image.height > 16_777_216:
        raise ValueError("Input image exceeds 16 megapixels")
    alpha = image.getchannel("A")
    if not alpha.getbbox():
        raise ValueError("Fully transparent image cannot be placed")
    if transparent and alpha.getextrema()[0] == 255:
        raise ValueError("Object/motif requires transparency; run existing remove-bg first")
    return image


def _ascii_title(text):
    if text and (len(text) > 200 or any(ord(c) > 126 or (ord(c) < 32 and c != "\n") for c in text)):
        raise ValueError("Printable ASCII titles only; use external typography for Chinese")


def _center_crop_resize(image, width, height):
    """對齊 ComfyUI ``common_upscale(..., crop='center')`` 的裁切，再 LANCZOS。"""
    old_w, old_h = image.size
    old_aspect = old_w / old_h
    new_aspect = width / height
    x = y = 0
    if old_aspect > new_aspect:
        x = round((old_w - old_w * (new_aspect / old_aspect)) / 2)
    elif old_aspect < new_aspect:
        y = round((old_h - old_h * (old_aspect / new_aspect)) / 2)
    cropped = image.crop((x, y, old_w - x, old_h - y))
    return cropped.resize((width, height), Image.Resampling.LANCZOS)


def _fit_object(image, target_w, target_h):
    """依 alpha bbox 裁切後等比縮放。RGB 用 LANCZOS，alpha 用 BILINEAR。不裁成填滿。"""
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("Fully transparent image cannot be placed")
    x0, y0, x1, y1 = bbox
    cropped = image.crop(bbox)
    scale = min(target_w / (x1 - x0), target_h / (y1 - y0))
    tw, th = max(1, round((x1 - x0) * scale)), max(1, round((y1 - y0) * scale))
    rgb = cropped.convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
    alpha = cropped.getchannel("A").resize((tw, th), Image.Resampling.BILINEAR)
    return rgb, alpha, (tw, th)


def _paste(dest, rgb, alpha, x, y):
    """alpha 是來源權重：255 換成物件色，0 留下背景。"""
    src = np.asarray(rgb)
    weight = np.asarray(alpha).astype(np.float32)[..., None] / 255.0
    h, w = src.shape[:2]
    view = dest[y:y + h, x:x + w]
    view[:] = np.round(src.astype(np.float32) * weight + view.astype(np.float32) * (1.0 - weight)).astype(np.uint8)


def _paint_label(image, text, top):
    if not text:
        return
    draw = ImageDraw.Draw(image)
    bbox = draw.multiline_textbbox((0, 0), text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = max(0, (image.width - tw) // 2)
    y = 8 if top else max(0, image.height - th - 8)
    draw.multiline_text((x, y), text, fill=(0x20, 0x3B, 0x38))


def compose(mode, images, *, background=None, x=0, y=0, width=512, height=512,
            cell=256, columns=3, padding=24, rows=3, color="#f5f0e5",
            title="", caption="", canvas_width=None, canvas_height=None):
    """合成並回傳 (RGB Image, (寬, 高), placements)。placements 的 box 是 [x, y, 寬, 高]。"""
    if not images or len(images) > 16:
        raise ValueError("Requires 1..16 images")
    placements = []
    if mode == "scene":
        if len(images) != 1 or background is None:
            raise ValueError("scene needs one object and one opaque background")
        positive(width, "width")
        positive(height, "height")
        positive(x, "x", 0)
        positive(y, "y", 0)
        canvas = background.convert("RGB")
        if canvas_width is not None or canvas_height is not None:
            if canvas_width is None or canvas_height is None:
                raise ValueError("Both canvas dimensions are required")
            positive(canvas_width, "canvas_width", 64)
            positive(canvas_height, "canvas_height", 64)
            if x + width > canvas_width or y + height > canvas_height:
                raise ValueError("Object box exceeds output canvas")
            canvas = _center_crop_resize(canvas, canvas_width, canvas_height)
        elif x + width > canvas.width or y + height > canvas.height:
            raise ValueError("Object box exceeds background; no implicit cropping")
        rgb, alpha, fitted = _fit_object(images[0], width, height)
        px, py = x + (width - fitted[0]) // 2, y + (height - fitted[1]) // 2
        dest = np.array(canvas)
        _paste(dest, rgb, alpha, px, py)
        placements.append({"input": 0, "box": [px, py, *fitted]})
    elif mode in {"sheet", "pattern"}:
        positive(cell, "cell", 64, 512)
        positive(columns, "columns", 1, 8)
        positive(padding, "padding", 0, cell // 3)
        if mode == "pattern":
            if len(images) != 1:
                raise ValueError("pattern repeats one approved motif only")
            positive(rows, "rows", 1, 8)
            sequence = [0] * (rows * columns)
        else:
            sequence = list(range(len(images)))
            rows = math.ceil(len(sequence) / columns)
        canvas = Image.new("RGB", (cell * columns, cell * rows), _rgb(color))
        inner = cell - 2 * padding
        fitted_by_index = {index: _fit_object(images[index], inner, inner) for index in set(sequence)}
        dest = np.array(canvas)
        for n, index in enumerate(sequence):
            rgb, alpha, fitted = fitted_by_index[index]
            px = (n % columns) * cell + (cell - fitted[0]) // 2
            py = (n // columns) * cell + (cell - fitted[1]) // 2
            _paste(dest, rgb, alpha, px, py)
            placements.append({"input": index, "box": [px, py, *fitted]})
    else:
        raise ValueError("Unknown design mode")
    _ascii_title(title)
    _ascii_title(caption)
    image = Image.fromarray(dest, "RGB")
    _paint_label(image, title, top=True)
    _paint_label(image, caption, top=False)
    return image, image.size, placements


def run(args):
    records = [file_record(p) for p in args.images]
    images = [check_image(p, True) for p in args.images]
    background = None
    if args.command == "scene":
        records.append(file_record(args.background))
        background = check_image(args.background)
        if background.getchannel("A").getextrema() != (255, 255):
            raise ValueError("Background must be opaque; helper output is opaque RGB")
    if any(file_record(r["path"]) != r for r in records):
        raise ValueError("Input changed during validation")
    image, size, placements = compose(
        args.command, images, background=background, x=args.x, y=args.y, width=args.width, height=args.height,
        cell=args.cell, columns=args.columns, padding=args.padding, rows=args.rows, color=args.color,
        title=args.title, caption=args.caption, canvas_width=args.canvas_width, canvas_height=args.canvas_height)
    out = new_directory(args.output_dir)
    target = out / f"design_{args.command}.png"
    image.save(target, format="PNG")
    report = {
        "schema_version": 1, "kind": "pillow_design", "mode": args.command, "status": "candidate",
        "inputs": records, "output": file_record(target), "dimensions": list(size), "placements": placements,
        "acceptance": "pending human review", "model_generation": False,
    }
    save_json(out / "manifest.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for mode in ("scene", "sheet", "pattern"):
        command = sub.add_parser(mode)
        command.add_argument("--images", nargs="+", required=True)
        command.add_argument("--background", required=mode == "scene")
        command.add_argument("--output-dir", required=True)
        command.add_argument("--comfy-url")
        command.add_argument("--config")
        command.add_argument("--timeout", type=float, default=180)
        command.add_argument("--x", type=int, default=0)
        command.add_argument("--y", type=int, default=0)
        command.add_argument("--width", type=int, default=512)
        command.add_argument("--height", type=int, default=512)
        command.add_argument("--canvas-width", type=int)
        command.add_argument("--canvas-height", type=int)
        command.add_argument("--cell", type=int, default=256)
        command.add_argument("--columns", type=int, default=3)
        command.add_argument("--rows", type=int, default=3)
        command.add_argument("--padding", type=int, default=24)
        command.add_argument("--color", default="#f5f0e5")
        command.add_argument("--title", default="")
        command.add_argument("--caption", default="")
    args = parser.parse_args(argv)
    try:
        report = run(args)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
