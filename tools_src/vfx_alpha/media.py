"""讀幀、寫 PNG 序列，以及 sprite sheet／APNG／WebM。"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image

import local_pixels


def file_record(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

def new_directory(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=False)
    return path

def save_json(path, payload):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)

def _png_paths(directory):
    paths = sorted(p for p in Path(directory).iterdir() if p.suffix.lower() == ".png")
    if not paths:
        raise ValueError(f"No PNG frames in {directory}")
    return paths

def read_frames(source, mode="RGB"):
    """Return (frames, fps). ``source`` is a video file or a directory of PNG frames."""
    source = Path(source)
    if source.is_dir():
        frames = []
        for p in _png_paths(source):
            with Image.open(p) as im:
                frames.append(np.asarray(im.convert(mode)))
        return frames, None
    frames, fps = local_pixels.decode_video_frames(source, mode)
    if not frames:
        raise ValueError(f"No decodable video frames in {source}")
    return frames, fps

def write_sequence(frames, directory):
    directory = new_directory(directory)
    for i, frame in enumerate(frames):
        Image.fromarray(frame).save(directory / f"{i:05d}.png")
    return directory

def sprite_sheet(rgba_frames, target, columns=None, fps=24):
    n = len(rgba_frames)
    h, w = rgba_frames[0].shape[:2]
    if any(f.shape[:2] != (h, w) for f in rgba_frames):
        raise ValueError("All frames must have the same size")
    columns = columns or math.ceil(math.sqrt(n))
    if columns < 1:
        raise ValueError("columns must be >= 1")
    rows = math.ceil(n / columns)
    sheet = Image.new("RGBA", (columns * w, rows * h), (0, 0, 0, 0))
    rects = []
    for i, frame in enumerate(rgba_frames):
        x, y = (i % columns) * w, (i // columns) * h
        sheet.paste(Image.fromarray(frame, "RGBA"), (x, y))
        rects.append({"index": i, "x": x, "y": y, "w": w, "h": h})
    sheet.save(target, format="PNG")
    meta = {"image": Path(target).name, "frame_width": w, "frame_height": h, "columns": columns,
            "rows": rows, "frame_count": n, "fps": fps, "alpha": "straight", "frames": rects}
    save_json(Path(target).with_suffix(".json"), meta)
    return meta

def write_apng(rgba_frames, target, fps=24):
    images = [Image.fromarray(f, "RGBA") for f in rgba_frames]
    images[0].save(target, format="PNG", save_all=True, append_images=images[1:],
                   duration=round(1000 / fps), loop=0, disposal=1, blend=0)
    return target

def write_webm_alpha(rgba_frames, target, fps=24, crf=18):
    """VP9 + alpha (yuva420p). Chroma is subsampled and lossy; PNG stays the master."""
    h, w = rgba_frames[0].shape[:2]
    if w % 2 or h % 2:
        raise ValueError("WebM yuva420p needs even width and height")
    local_pixels.encode_video_frames(
        rgba_frames, target, codec="libvpx-vp9", pix_fmt="yuva420p", ndarray_format="rgba",
        fps=fps, container_format="webm", options={"crf": str(crf), "b": "0", "auto-alt-ref": "0"},
        contiguous=True)
    return target

def read_webm_alpha(path):
    """Decode a VP9 alpha WebM with libvpx (FFmpeg's native vp9 decoder drops alpha)."""
    import av
    frames = []
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        decoder = av.CodecContext.create("libvpx-vp9", "r")
        # demux() ends with an empty packet, which also flushes the decoder.
        for packet in container.demux(stream):
            for frame in decoder.decode(packet):
                frames.append(frame.to_ndarray(format="rgba"))
    return frames
