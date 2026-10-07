"""Local edit preservation, pixel diagnostics, and bounded existing-task sweeps.

No generation graphs or model defaults are introduced here. Mask alpha follows
the pipeline contract: 0 = edited region, 255 = preserve source. Measurements
include all RGBA bytes (also hidden RGB), and are not perceptual/art acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import time
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageOps


COMMON = {"prompt", "negative", "seed", "style", "rating"}
TASK_FIELDS = {
    "refine": COMMON | {"image", "denoise"},
    "inpaint": COMMON | {"image", "mask", "denoise"},
    "guided_inpaint": COMMON | {"image", "mask", "denoise", "control_ref",
                                  "control_type", "control_strength",
                                  "appearance_ref", "appearance_weight"},
    "character_action": COMMON | {"character_ref", "pose_ref", "ip_weight",
                                    "pose_strength", "control_type", "width", "height"},
}
REQUIRED = {"refine": {"image"}, "inpaint": {"image", "mask"},
            "guided_inpaint": {"image", "mask"},
            "character_action": {"character_ref", "pose_ref"}}
PATH_FIELDS = {"image", "mask", "control_ref", "appearance_ref", "character_ref", "pose_ref"}
SWEEP_FIELDS = {"denoise", "control_strength", "appearance_weight", "ip_weight", "pose_strength"}
MAX_RUNS = 16


def file_record(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_image(path):
    with Image.open(path) as im:
        if getattr(im, "n_frames", 1) != 1:
            raise ValueError("Only single-frame images are supported")
        if im.getexif().get(274, 1) != 1:
            raise ValueError("Normalize EXIF orientation before using this tool")
        im.load()
        return im.convert("RGBA")


def load_mask(path, size):
    with Image.open(path) as im:
        if im.format != "PNG" or "A" not in im.getbands():
            raise ValueError("Mask must be PNG with an Alpha channel; alpha=0 edits, alpha=255 preserves")
        if im.size != size or getattr(im, "n_frames", 1) != 1:
            raise ValueError("Mask dimensions/frame count must match the source")
        if im.getexif().get(274, 1) != 1:
            raise ValueError("Normalize mask EXIF orientation before using this tool")
        alpha = im.getchannel("A")
        alpha.load()
    return alpha


def new_directory(path):
    path = Path(path).resolve()
    # An existing empty directory is rejected as well, preventing mixed runs.
    path.mkdir(parents=True, exist_ok=False)
    return path


def save_json(path, payload):
    # Used only inside this process's newly reserved output directory.
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def aligned_pair(source, edited):
    a, b = load_image(source), load_image(edited)
    if a.size != b.size:
        raise ValueError("Source and edited dimensions must match; automatic resizing is not allowed")
    return a, b


def composite(source, edited, mask, output_dir, keep_source_alpha=False):
    a, b = aligned_pair(source, edited)
    alpha = load_mask(mask, a.size)
    # Selection blend, not foreground alpha-over: fully selected pixels must
    # reproduce the edited RGBA bytes, including transparent edited pixels.
    result = Image.composite(a, b, alpha)
    if keep_source_alpha:
        result.putalpha(a.getchannel("A"))
    preserved = np.asarray(alpha) == 255
    before, after = np.asarray(a), np.asarray(result)
    if np.any(before[preserved] != after[preserved]):
        raise RuntimeError("Preserved-region pixel invariant failed")
    out = new_directory(output_dir)
    target = out / "composited.png"
    result.save(target, format="PNG")
    report = {"schema_version": 1, "kind": "masked_image_composite", "status": "candidate",
              "inputs": {"source": file_record(source), "edited": file_record(edited), "mask": file_record(mask)},
              "mask_contract": "alpha=0 edited; alpha=255 source; intermediate values blend RGBA bytes",
              "dimensions": list(a.size), "preserved_pixels": int(preserved.sum()),
              "outside_changed_pixels": 0, "output": file_record(target),
              "keep_source_alpha": keep_source_alpha,
              "acceptance": "pending human review; pixel preservation does not judge edit quality"}
    save_json(out / "result.json", report)
    return report


def recolor(source, mask, output_dir, from_hue, to_hue, hue_range=45, min_saturation=0.12):
    """Rotate an existing hue within an explicit selection; never invent texture.

    Hue is in degrees. HSV saturation/value are retained before RGB quantization;
    this is not a physical lighting or perceptual luminance preservation operation.
    Source Alpha and unselected RGBA bytes are preserved exactly.
    """
    for name, value, upper in (("from_hue", from_hue, 360), ("to_hue", to_hue, 360),
                               ("hue_range", hue_range, 180), ("min_saturation", min_saturation, 1)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= upper:
            raise ValueError(f"{name} must be finite and between 0 and {upper}")
    a = load_image(source)
    preserve = np.asarray(load_mask(mask, a.size))
    rgba = np.asarray(a)
    hsv = np.asarray(a.convert("RGB").convert("HSV")).copy()
    degrees = hsv[:, :, 0].astype(float) * (360 / 255)
    distance = np.abs((degrees - from_hue + 180) % 360 - 180)
    selected = (preserve < 255) & (rgba[:, :, 3] > 0) & (distance <= hue_range) & (hsv[:, :, 1] / 255 >= min_saturation)
    if not selected.any():
        raise ValueError("No visible chromatic pixels match the selected hue and mask")
    # Only matching pixels undergo the HSV round trip; all others retain exact bytes.
    shifted = np.round(((degrees + to_hue - from_hue) % 360) * (255 / 360)).astype(np.uint8)
    hsv[:, :, 0][selected] = shifted[selected]
    rgb = np.asarray(Image.frombytes("HSV", a.size, hsv.tobytes()).convert("RGB"))
    edited = rgba.copy()
    edited[:, :, :3][selected] = rgb[selected]
    result = Image.composite(a, Image.fromarray(edited), Image.fromarray(preserve))
    result.putalpha(a.getchannel("A"))
    after = np.asarray(result)
    if not np.array_equal(after[:, :, 3], rgba[:, :, 3]) or not np.array_equal(after[~selected], rgba[~selected]):
        raise RuntimeError("Recolor preservation invariant failed")
    out = new_directory(output_dir)
    result.save(out / "recolored.png")
    contact_sheet([a, result], ["SOURCE", "LOCAL HUE ROTATION"], out / "comparison.png", 480)
    report = {"schema_version": 1, "kind": "local_hue_recolor", "status": "candidate",
              "inputs": {"source": file_record(source), "mask": file_record(mask)},
              "parameters": {"from_hue": from_hue, "to_hue": to_hue, "hue_range": hue_range, "min_saturation": min_saturation},
              "dimensions": list(a.size), "matched_pixels": int(selected.sum()),
              "changed_pixels": int(np.any(after != rgba, axis=2).sum()),
              "outside_changed_pixels": 0, "alpha_changed_pixels": 0,
              "model_generation": False, "output": file_record(out / "recolored.png"),
              "limitations": ["HSV hue rotation only; no material change or exact target RGB guarantee",
                              "Saturation and HSV value retained before quantization; not physical relighting",
                              "Neutral/low-saturation pixels and hues outside range remain unchanged"],
              "acceptance": "pending human review"}
    save_json(out / "result.json", report)
    return report


def region_stats(delta, selection):
    selected = delta[selection]
    count = int(selection.sum())
    if not count:
        return {"pixels": 0, "changed_pixels": 0, "changed_fraction": None,
                "mean_absolute_rgba_byte_difference": None, "max_byte_difference": None}
    changed = int(np.any(selected > 0, axis=1).sum())
    return {"pixels": count, "changed_pixels": changed, "changed_fraction": changed / count,
            "mean_absolute_rgba_byte_difference": float(selected.mean()),
            "max_byte_difference": int(selected.max())}


def contact_sheet(images, labels, target, thumb=320):
    lines = [textwrap.wrap(label, width=max(12, thumb // 7)) for label in labels]
    header = 16 + 14 * max(len(parts) for parts in lines)
    columns = min(4, len(images))
    rows = math.ceil(len(images) / columns)
    canvas = Image.new("RGB", (thumb * columns, (thumb + header) * rows), "#e5e5e5")
    draw = ImageDraw.Draw(canvas)
    for i, (im, label) in enumerate(zip(images, labels)):
        rgba = ImageOps.contain(im.convert("RGBA"), (thumb, thumb))
        # Checkerboard makes actual alpha visible rather than hiding it on white.
        tile = Image.new("RGBA", (thumb, thumb), "#dddddd")
        squares = ImageDraw.Draw(tile)
        for y in range(0, thumb, 16):
            for x in range(0, thumb, 16):
                if (x // 16 + y // 16) % 2:
                    squares.rectangle((x, y, x + 15, y + 15), fill="#bbbbbb")
        tile.alpha_composite(rgba, ((thumb - rgba.width) // 2, (thumb - rgba.height) // 2))
        x, y = (i % columns) * thumb, (i // columns) * (thumb + header)
        canvas.paste(tile.convert("RGB"), (x, y + header))
        draw.multiline_text((x + 6, y + 8), "\n".join(lines[i]), fill="black", spacing=3)
    canvas.save(target, format="PNG")


def compare(source, edited, output_dir, mask=None):
    a, b = aligned_pair(source, edited)
    alpha = load_mask(mask, a.size) if mask else None
    delta = np.abs(np.asarray(a).astype(np.int16) - np.asarray(b).astype(np.int16))
    maximum = delta.max(axis=2).astype(np.uint8)
    # Red intensity is raw max RGBA difference, without a hidden threshold.
    heat = np.zeros((*maximum.shape, 3), dtype=np.uint8)
    heat[:, :, 0] = maximum
    heat_image = Image.fromarray(heat)
    out = new_directory(output_dir)
    heat_image.save(out / "difference.png")
    contact_sheet([a, b, heat_image], ["SOURCE", "EDITED", "RAW RGBA DIFF"], out / "comparison.png")
    regions = {"whole": region_stats(delta, np.ones(maximum.shape, dtype=bool))}
    if alpha is not None:
        values = np.asarray(alpha)
        regions.update({"edited": region_stats(delta, values == 0),
                        "transition": region_stats(delta, (values > 0) & (values < 255)),
                        "preserved": region_stats(delta, values == 255)})
        bbox = ImageOps.invert(alpha).getbbox()
        if bbox:
            x0, y0, x1, y1 = bbox
            box = (max(0, x0 - 16), max(0, y0 - 16), min(a.width, x1 + 16), min(a.height, y1 + 16))
            contact_sheet([a.crop(box), b.crop(box), heat_image.crop(box)],
                          ["SOURCE REGION", "EDITED REGION", "REGION DIFF"], out / "detail.png", 480)
    report = {"schema_version": 1, "kind": "image_edit_comparison", "dimensions": list(a.size),
              "inputs": {"source": file_record(source), "edited": file_record(edited)},
              "measurement": "Exact decoded RGBA bytes, including RGB of transparent pixels; no alignment/resize",
              "regions": regions, "art_acceptance": "not assessed",
              "outputs": [file_record(p) for p in sorted(out.glob("*.png"))]}
    if mask:
        report["inputs"]["mask"] = file_record(mask)
    save_json(out / "comparison.json", report)
    return report


def validate_value(key, value):
    if key in SWEEP_FIELDS:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number")
        if not 0 <= value <= 1:
            raise ValueError(f"{key} outside the supported range")
    elif key in {"seed", "width", "height"}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
        if key == "seed" and not 0 <= value < 2**64:
            raise ValueError("seed must fit an unsigned 64-bit integer")
        if key != "seed" and (value < 64 or value > 4096 or value % 8):
            raise ValueError("dimensions must be multiples of 8 between 64 and 4096")
    elif not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a nonempty string")
    if key == "style" and value not in {"anime", "illustration", "realistic"}:
        raise ValueError("Unsupported style")
    if key == "rating" and value not in {"safe", "questionable", "explicit"}:
        raise ValueError("Unsupported rating")
    if key == "control_type" and value not in {"canny", "pose", "depth"}:
        raise ValueError("Unsupported control_type")


def expand_plan(plan, base_dir):
    if not isinstance(plan, dict) or set(plan) - {"task", "base", "sweep", "preserve_outside"}:
        raise ValueError("Plan fields: task, base, sweep, optional preserve_outside")
    task, base, axes = plan.get("task"), plan.get("base"), plan.get("sweep")
    if not isinstance(task, str) or task not in TASK_FIELDS or not isinstance(base, dict) or not isinstance(axes, dict):
        raise ValueError("Plan needs a supported task and base/sweep objects")
    if not {"prompt", "seed"}.union(REQUIRED[task]) <= set(base):
        raise ValueError("base must contain prompt, fixed seed, and all task inputs")
    if set(base) - TASK_FIELDS[task] or set(axes) - (SWEEP_FIELDS & TASK_FIELDS[task]):
        raise ValueError("Unsupported task parameters or sweep axes (seed/prompt/references stay fixed)")
    preserve = plan.get("preserve_outside", False)
    if not isinstance(preserve, bool) or preserve and task not in {"inpaint", "guided_inpaint"}:
        raise ValueError("preserve_outside is a boolean available only for inpaint/guided_inpaint")
    count = 1
    for key, values in axes.items():
        if not isinstance(values, list) or not values:
            raise ValueError("Each sweep axis must be a nonempty list")
        count *= len(values)
        for value in values:
            validate_value(key, value)
        if len(set(values)) != len(values):
            raise ValueError("Duplicate sweep values would repeat the same experiment")
    if count > MAX_RUNS:
        raise ValueError(f"Sweep exceeds the {MAX_RUNS}-run limit")
    normalized = dict(base)
    for key, value in normalized.items():
        validate_value(key, value)
        if key in PATH_FIELDS:
            path = (Path(base_dir) / value).resolve()
            load_image(path)
            normalized[key] = str(path)
    if "mask" in normalized:
        load_mask(normalized["mask"], load_image(normalized["image"]).size)
    keys = list(axes)
    runs = []
    for values in itertools.product(*(axes[key] for key in keys)):
        settings = dict(normalized, **dict(zip(keys, values)))
        if settings.get("rating") and settings.get("style") not in {"anime", "illustration"}:
            raise ValueError("rating requires anime/illustration style")
        if ("control_ref" in settings or "control_strength" in settings) and not settings.get("control_type"):
            raise ValueError("control_ref/control_strength require control_type")
        if "appearance_weight" in settings and not settings.get("appearance_ref"):
            raise ValueError("appearance_weight requires appearance_ref")
        runs.append(settings)
    return task, runs, preserve


def generation_command(config, config_path, task, settings, folder, timeout):
    command = [config["python_exe"], config["generate_script"], task,
               "--config", str(config_path), "--comfy-url", config["comfyui_url"],
               "--output-dir", str(folder), "--result-json", str(folder / "generation.json"),
               "--timeout", str(timeout)]
    for key, value in settings.items():
        command.extend(["--" + key.replace("_", "-"), str(value)])
    return command


def check_runtime(config, task, profile=None, allow_unverified=False):
    for key in ("python_exe", "generate_script", "comfyui_url", "comfyui_path"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise ValueError(f"Config missing {key}")
    if not Path(config["python_exe"]).is_file() or not Path(config["generate_script"]).is_file():
        raise ValueError("Configured Python/generate.py is missing")
    cap_path = Path(config.get("image_config", Path(config["comfyui_path"]) / "tools/image_capabilities.json"))
    caps = json.loads(cap_path.read_text(encoding="utf-8-sig"))
    selected = profile or caps["default_profile"]
    capability = caps["profiles"][selected]["tasks"][task]
    if not capability.get("available"):
        raise ValueError(f"Task unavailable in capability snapshot: {capability}")
    validation = capability.get("validation")
    if validation not in {"verified", "verified_other_env", "experimental", "unverified"}:
        raise ValueError(f"Unsupported task validation state: {validation}")
    if validation != "verified" and not allow_unverified:
        raise ValueError("Task is not verified; explicit approved trial needs --allow-unverified")
    url = config["comfyui_url"].rstrip("/")
    with urllib.request.urlopen(url + "/queue", timeout=10) as response:
        queue = json.load(response)
    if queue.get("queue_running") or queue.get("queue_pending"):
        raise ValueError("ComfyUI queue occupied; no sweep submissions made")
    return {"snapshot": file_record(cap_path), "profile": selected, "task": capability}


def sweep(plan_path, config_path, output_dir, *, profile=None, timeout=240,
          dry_run=False, allow_unverified=False):
    plan_path, config_path = Path(plan_path).resolve(), Path(config_path).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    task, runs, preserve = expand_plan(plan, plan_path.parent)
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("Config must be an object")
    for key in ("python_exe", "generate_script", "comfyui_path", "image_config"):
        if key in config:
            if not isinstance(config[key], str) or not config[key].strip():
                raise ValueError(f"Config {key} must be a nonempty path string")
            config[key] = str((config_path.parent / config[key]).resolve())
    runtime = None if dry_run else check_runtime(config, task, profile, allow_unverified)
    out = new_directory(output_dir)
    save_json(out / "plan.json", plan)
    inputs = {key: file_record(value) for key, value in runs[0].items() if key in PATH_FIELDS}
    report = {"schema_version": 1, "kind": "image_parameter_sweep", "status": "planned" if dry_run else "running",
              "task": task, "plan": file_record(plan_path), "config": file_record(config_path),
              "inputs": inputs, "runtime": runtime, "preserve_outside": preserve,
              "art_acceptance": "all outputs are candidates; pending human review", "runs": []}
    save_json(out / "sweep.json", report)
    images, labels = [], []
    try:
        for index, settings in enumerate(runs, 1):
            folder = out / f"run_{index:02d}"
            folder.mkdir()
            command = generation_command(config, config_path, task, settings, folder, timeout)
            selected_profile = profile or (runtime["profile"] if runtime else None)
            if selected_profile:
                command.extend(["--profile", selected_profile])
            entry = {"id": index, "parameters": settings, "argv": command,
                     "status": "planned" if dry_run else "running"}
            report["runs"].append(entry)
            save_json(out / "sweep.json", report)
            if dry_run:
                continue
            # Refuse an input modified between candidates: this is a fixed-input experiment.
            for key, expected in inputs.items():
                if file_record(settings[key])["sha256"] != expected["sha256"]:
                    raise ValueError(f"Input changed during sweep: {key}")
            print(f"START {index}/{len(runs)}", flush=True)
            started = time.perf_counter()
            env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            proc = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", env=env)
            entry.update({"exit_code": proc.returncode, "wall_seconds": time.perf_counter() - started})
            (folder / "stdout.log").write_text(proc.stdout, encoding="utf-8")
            (folder / "stderr.log").write_text(proc.stderr, encoding="utf-8")
            if proc.returncode:
                raise RuntimeError(f"Generation failed at run {index}; inspect logs/queue before any new submission")
            for key, expected in inputs.items():
                if file_record(settings[key])["sha256"] != expected["sha256"]:
                    raise ValueError(f"Input changed during generation: {key}; comparison stopped")
            generation = json.loads((folder / "generation.json").read_text(encoding="utf-8"))
            outputs = generation.get("outputs", [])
            if len(outputs) != 1:
                raise ValueError("Expected exactly one traced image per candidate")
            image = Path(outputs[0]["path"])
            # Verify the manifest points into this run and the bytes still agree.
            if image.resolve().parent != folder or file_record(image)["sha256"] != outputs[0]["sha256"]:
                raise ValueError("Unexpected output path or output hash mismatch")
            load_image(image)
            entry["generation_manifest"] = file_record(folder / "generation.json")
            if "image" in settings:
                raw = compare(settings["image"], image, folder / "raw_comparison", settings.get("mask"))
                entry["raw_regions"] = raw["regions"]
            if preserve:
                composite(settings["image"], image, settings["mask"], folder / "composite")
                image = folder / "composite/composited.png"
                final = compare(settings["image"], image, folder / "final_comparison", settings["mask"])
                entry["final_regions"] = final["regions"]
            entry.update({"status": "candidate", "output": file_record(image)})
            images.append(load_image(image))
            labels.append(f"RUN {index:02d} " + " ".join(f"{k}={settings[k]}" for k in plan["sweep"]))
            contact_sheet(images, labels, out / "candidates.png", thumb=300)
            save_json(out / "sweep.json", report)
            print(f"DONE {index}/{len(runs)}", flush=True)
        report["status"] = "planned" if dry_run else "complete"
    except BaseException as exc:
        report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        report["error"] = str(exc) or type(exc).__name__
        if report["runs"] and report["runs"][-1]["status"] == "running":
            report["runs"][-1]["status"] = report["status"]
        raise
    finally:
        save_json(out / "sweep.json", report)
    return report


def checker_preview(image, background="checker"):
    """Flatten for inspection only; never modify the source asset."""
    base = Image.new("RGBA", image.size, background if background != "checker" else "#dddddd")
    if background == "checker":
        draw = ImageDraw.Draw(base)
        for y in range(0, image.height, 24):
            for x in range(0, image.width, 24):
                if (x // 24 + y // 24) % 2:
                    draw.rectangle((x, y, x + 23, y + 23), fill="#999999")
    return Image.alpha_composite(base, image).convert("RGB")


def asset_audit(image, output_dir):
    record = file_record(image)
    with Image.open(image) as original:
        has_alpha = "A" in original.getbands() or "transparency" in original.info
        original_mode = original.mode
    rgba = load_image(image)
    alpha = np.asarray(rgba.getchannel("A"))
    bbox = rgba.getchannel("A").getbbox()
    edge = np.concatenate((alpha[0], alpha[-1], alpha[:, 0], alpha[:, -1]))
    findings = []
    if not has_alpha:
        findings.append("no_alpha_channel")
    if not (alpha == 0).any():
        findings.append("no_fully_transparent_pixels")
    if bbox is None:
        findings.append("fully_transparent_image")
    if (edge > 0).any():
        findings.append("visible_pixels_touch_canvas_edge")
    if file_record(image) != record:
        raise ValueError("Input changed during audit")
    out = new_directory(output_dir)
    for bg in ("white", "black", "checker"):
        preview = rgba.copy()
        preview.thumbnail((1200, 1200))
        checker_preview(preview, bg).save(out / f"preview_{bg}.png")
    result = {"schema_version": 1, "kind": "asset_alpha_audit", "status": "observed",
              "input": record, "original_mode": original_mode, "has_alpha": has_alpha,
              "dimensions": list(rgba.size), "visible_bbox": list(bbox) if bbox else None,
              "transparent_pixels": int((alpha == 0).sum()),
              "partial_alpha_pixels": int(((alpha > 0) & (alpha < 255)).sum()),
              "opaque_pixels": int((alpha == 255).sum()),
              "findings": findings, "acceptance": "pending human review; alpha statistics cannot judge cutout quality"}
    save_json(out / "audit.json", result)
    return result


def reference_board(plan, output_dir):
    plan = Path(plan).resolve()
    plan_record = file_record(plan)
    specification = json.loads(plan.read_text(encoding="utf-8-sig"))
    if not isinstance(specification, dict) or set(specification) != {"items"}:
        raise ValueError("Reference plan must contain only items")
    items = specification["items"]
    if not isinstance(items, list) or not 1 <= len(items) <= 12:
        raise ValueError("Reference board needs 1..12 items")
    roles = {"source", "character", "pose", "appearance", "mask-preview", "candidate"}
    images, records = [], []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict) or set(item) != {"path", "label", "role"}:
            raise ValueError("Each reference needs path, label and role")
        if not all(isinstance(item[k], str) and item[k].strip() for k in item):
            raise ValueError("Reference fields must be nonempty strings")
        if item["role"] not in roles or len(item["label"]) > 120:
            raise ValueError("Invalid reference role or label longer than 120 characters")
        path = (plan.parent / item["path"]).resolve()
        record = file_record(path)
        image = load_image(path)
        records.append({"index": index, "role": item["role"], "label": item["label"],
                        "input": record, "dimensions": list(image.size)})
        images.append(image)
    if file_record(plan) != plan_record or any(file_record(r["input"]["path"]) != r["input"] for r in records):
        raise ValueError("Input changed during board preparation")
    columns = min(3, len(items))
    cell_w, cell_h = 360, 420
    board = Image.new("RGB", (columns * cell_w, math.ceil(len(items) / columns) * cell_h), "#192231")
    draw = ImageDraw.Draw(board)
    # Pillow's bundled font may not cover CJK: a local Windows font is optional.
    from PIL import ImageFont
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 16)
    except OSError:
        font = ImageFont.load_default()
    for i, (image, record) in enumerate(zip(images, records)):
        x, y = (i % columns) * cell_w, (i // columns) * cell_h
        image.thumbnail((336, 336))
        thumb = checker_preview(image)
        board.paste(thumb, (x + (cell_w - thumb.width) // 2, y + 72 + (336 - thumb.height) // 2))
        draw.text((x + 12, y + 8), f"{record['index']:02d} | {record['role']}", font=font, fill="white")
        # Fit labels with pixel-aware wrapping; the full label remains in JSON.
        line, lines = "", []
        for char in record["label"].replace("\n", " "):
            if draw.textlength(line + char, font=font) > 336:
                lines.append(line)
                line = char
            else:
                line += char
        lines.append(line)
        draw.text((x + 12, y + 30), "\n".join(lines[:2]), font=font, fill="#c9d5e6", spacing=2)
    out = new_directory(output_dir)
    board.save(out / "reference_board.png")
    result = {"schema_version": 1, "kind": "reference_board", "status": "candidate",
              "plan": plan_record, "items": records,
              "usage": "Human review only; pass original files to supported tasks, not this board"}
    save_json(out / "references.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("composite", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--source", required=True)
        p.add_argument("--edited", required=True)
        p.add_argument("--mask", required=name == "composite")
        p.add_argument("--output-dir", required=True, help="New directory; existing directories are rejected")
        if name == "composite":
            p.add_argument("--keep-source-alpha", action="store_true", help="Keep the source silhouette Alpha exactly")
    p = sub.add_parser("recolor", help="Local hue rotation in an explicit mask; not AI generation")
    p.add_argument("--source", required=True)
    p.add_argument("--mask", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--from-hue", type=float, required=True)
    p.add_argument("--to-hue", type=float, required=True)
    p.add_argument("--hue-range", type=float, default=45)
    p.add_argument("--min-saturation", type=float, default=0.12)
    p = sub.add_parser("sweep")
    p.add_argument("--plan", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--profile")
    p.add_argument("--timeout", type=float, default=240)
    p.add_argument("--dry-run", action="store_true", help="Validate plan/write commands; do not submit generation")
    p.add_argument("--allow-unverified", action="store_true", help="Only for a user-approved unverified/experimental trial")
    p = sub.add_parser("asset-audit", help="Inspect Alpha and previews; does not repair or grade the asset")
    p.add_argument("--image", required=True)
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("reference-board", help="Role-labelled human preview of original references")
    p.add_argument("--plan", required=True)
    p.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "composite":
            result = composite(args.source, args.edited, args.mask, args.output_dir, args.keep_source_alpha)
        elif args.command == "recolor":
            result = recolor(args.source, args.mask, args.output_dir, args.from_hue, args.to_hue,
                             args.hue_range, args.min_saturation)
        elif args.command == "compare":
            result = compare(args.source, args.edited, args.output_dir, args.mask)
        elif args.command == "asset-audit":
            result = asset_audit(args.image, args.output_dir)
        elif args.command == "reference-board":
            result = reference_board(args.plan, args.output_dir)
        else:
            if not math.isfinite(args.timeout) or args.timeout <= 0:
                raise ValueError("timeout must be positive and finite")
            result = sweep(args.plan, args.config, args.output_dir, profile=args.profile,
                           timeout=args.timeout, dry_run=args.dry_run, allow_unverified=args.allow_unverified)
        print(json.dumps({"status": result.get("status", "complete"),
                          "output_dir": str(Path(args.output_dir).resolve())}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
