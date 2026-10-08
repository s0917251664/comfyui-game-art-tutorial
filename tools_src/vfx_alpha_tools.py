"""Local VFX alpha extraction, packing, video object marking/paste-back and Idle loop measurements.

Pure Pillow/NumPy pixel operations; PyAV is only needed to read MP4 input or to
write WebM. No ComfyUI server, no model download, no generation graph. BiRefNet
per-frame matting reuses ``benchmark_birefnet`` and needs the local CUDA runtime
plus already-installed weights.

Alpha conventions:
- RGBA outputs are *straight* (unpremultiplied) alpha, 0 = transparent.
- SAM / video_layers masks are ``L`` images, white = selected.
- image_edit_tools masks are PNG alpha, 0 = edited, 255 = preserve.
  ``sam-to-edit-mask`` converts the former into the latter.

Every output directory must not exist yet; nothing is overwritten. Numbers are
technical diagnostics, not art acceptance.

實作在 ``vfx_alpha`` 套件。這個檔是 ``gameart.py vfx`` 的門面，子命令與函式名稱不變。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

from vfx_alpha.mask import (
    SEGMENT_MAX_WIDTH, SEGMENT_MIN_WIDTH, _posix, editor_mask_to_l, gray_mask_array,
    green_screen, mask_composite, mask_overlay_strip, prop_paste, read_masks,
    sam_to_edit_mask, segment_plan, working_size,
)
from vfx_alpha.media import (
    _png_paths, file_record, new_directory, read_frames, read_webm_alpha, save_json,
    sprite_sheet, write_apng, write_sequence, write_webm_alpha,
)
from vfx_alpha.pixel import (
    _check_unit, birefnet_alpha, chroma_alpha, luma_alpha, masked_hue_rotate, over, parse_hex,
)
from vfx_alpha.qa import (
    DARK_BG, EDGE_HIGH, EDGE_LOW, LIGHT_BG, VISIBLE, _finite, _label_tile, alpha_metrics,
    comparison_board, frame_difference, loop_metrics, outside_mask_drift, subject_roi,
)

# ---------------------------------------------------------------- CLI

def _cmd_alpha(args):
    frames, fps = read_frames(args.input)
    started = time.perf_counter()
    if args.command == "luma-alpha":
        rgba = [luma_alpha(f, args.black_point, args.white_point, args.gamma) for f in frames]
        params = {"black_point": args.black_point, "white_point": args.white_point, "gamma": args.gamma}
        key = None
    elif args.command == "chroma-alpha":
        rgba = [chroma_alpha(f, args.key, args.tolerance, args.softness, args.despill, args.unmix) for f in frames]
        params = {"key": args.key, "tolerance": args.tolerance, "softness": args.softness,
                  "despill": args.despill, "unmix": args.unmix}
        key = args.key
    else:
        rgba, _ = birefnet_alpha(frames, args.model_root, args.variant)
        params = {"variant": args.variant, "model_root": str(args.model_root), "temporal_model": False}
        key = args.key
    seconds = time.perf_counter() - started
    out = new_directory(args.output_dir)
    write_sequence(rgba, out / "frames")
    reference = read_frames(args.reference_alpha, mode="RGBA")[0] if args.reference_alpha else None
    report = {"schema_version": 1, "kind": f"vfx_{args.command.replace('-', '_')}", "status": "candidate",
              "input": file_record(args.input) if Path(args.input).is_file() else {"path": str(Path(args.input).resolve())},
              "parameters": params, "fps": fps or args.fps, "frames": len(rgba),
              "processing_seconds_total": round(seconds, 3),
              "processing_seconds_per_frame": round(seconds / len(rgba), 4),
              "metrics": alpha_metrics(rgba, key=key,
                                       reference_alpha=[r[..., 3] for r in reference] if reference else None),
              "alpha": "straight", "acceptance": "pending human review"}
    comparison_board(frames[len(frames) // 2], [(args.command.upper(), rgba[len(rgba) // 2])], out / "board_mid.png")
    save_json(out / "result.json", report)
    return report


def _cmd_metrics(args):
    frames, _ = read_frames(args.input, mode="RGBA")
    report = alpha_metrics(frames, key=args.key)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _cmd_board(args):
    original, _ = read_frames(args.original)
    index = args.frame if args.frame >= 0 else len(original) // 2
    candidates = []
    for item in args.candidate:
        label, _, path = item.partition("=")
        if not path:
            raise ValueError("--candidate must be LABEL=DIR")
        frames, _ = read_frames(path, mode="RGBA")
        candidates.append((label, frames[index]))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    if Path(args.output).exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")
    comparison_board(original[index], candidates, args.output, args.thumb)
    return {"status": "complete", "output": str(Path(args.output).resolve()), "frame": index}


def _cmd_pack(args):
    frames, _ = read_frames(args.input, mode="RGBA")
    out = new_directory(args.output_dir)
    result = {"schema_version": 1, "kind": "vfx_pack", "status": "candidate", "frames": len(frames), "outputs": {}}
    meta = sprite_sheet(frames, out / "sheet.png", args.columns, args.fps)
    result["outputs"]["sprite_sheet"] = {**file_record(out / "sheet.png"), "columns": meta["columns"], "rows": meta["rows"]}
    if args.apng:
        write_apng(frames, out / "anim.png", args.fps)
        result["outputs"]["apng"] = file_record(out / "anim.png")
    if args.webm:
        write_webm_alpha(frames, out / "anim.webm", args.fps, args.crf)
        decoded = read_webm_alpha(out / "anim.webm")
        alpha_err = [float(np.abs(d[..., 3].astype(np.int16) - f[..., 3].astype(np.int16)).mean())
                     for d, f in zip(decoded, frames)]
        result["outputs"]["webm_vp9_alpha"] = {**file_record(out / "anim.webm"), "decoded_frames": len(decoded),
                                               "decoded_alpha_mean_abs_error": float(np.mean(alpha_err)) if alpha_err else None,
                                               "note": "lossy yuva420p; decode with libvpx-vp9 to keep alpha"}
    save_json(out / "result.json", result)
    return result


def _cmd_sam_to_edit(args):
    out = new_directory(args.output_dir)
    for p in _png_paths(args.masks):
        with Image.open(p) as im:
            Image.fromarray(sam_to_edit_mask(np.asarray(im.convert("L"))), "RGBA").save(out / p.name)
    return {"status": "complete", "output_dir": str(out)}


def _cmd_mask_recolor(args):
    frames, fps = read_frames(args.input)
    masks = read_masks(args.masks, len(frames), (frames[0].shape[1], frames[0].shape[0]))
    edited, hits = [], []
    for f, m in zip(frames, masks):
        e, n = masked_hue_rotate(f, m >= args.threshold, args.from_hue, args.to_hue, args.hue_range, args.min_saturation)
        edited.append(e)
        hits.append(n)
    composed, per_frame = mask_composite(frames, edited, masks, args.feather)
    out = new_directory(args.output_dir)
    write_sequence(composed, out / "frames")
    report = {"schema_version": 1, "kind": "vfx_mask_recolor", "status": "candidate", "model_generation": False,
              "fps": fps, "frames": len(composed), "matched_pixels_per_frame": hits,
              "outside_changed_pixels_total": sum(r["outside_changed_pixels"] for r in per_frame),
              "per_frame": per_frame, "acceptance": "pending human review"}
    save_json(out / "result.json", report)
    return report


def _cmd_mask_composite(args):
    original, fps = read_frames(args.original)
    edited, _ = read_frames(args.edited)
    masks = read_masks(args.masks, len(original), (original[0].shape[1], original[0].shape[0]))
    if len(edited) != len(original):
        raise ValueError(f"edited has {len(edited)} frames, original has {len(original)}")
    if edited[0].shape != original[0].shape:
        raise ValueError(f"edited frame size {edited[0].shape} differs from original {original[0].shape}")
    drift = outside_mask_drift(original, edited, masks)
    composed, per_frame = mask_composite(original, edited, masks, args.feather)
    out = new_directory(args.output_dir)
    write_sequence(composed, out / "frames")
    report = {"schema_version": 1, "kind": "vfx_mask_composite", "status": "candidate", "fps": fps,
              "frames": len(composed), "feather": args.feather,
              "edited_outside_mask_drift_before_composite": drift,
              "outside_changed_pixels_total": sum(r["outside_changed_pixels"] for r in per_frame),
              "per_frame": per_frame, "acceptance": "pending human review"}
    save_json(out / "result.json", report)
    return report


def _cmd_loop(args):
    frames, fps = read_frames(args.video)
    reference = np.asarray(Image.open(args.reference).convert("RGB")) if args.reference else None
    report, ref = loop_metrics(frames, reference, args.key)
    out = new_directory(args.output_dir)
    Image.fromarray(frames[0]).save(out / "first.png")
    Image.fromarray(frames[-1]).save(out / "last.png")
    if ref is not None:
        Image.fromarray(ref).save(out / "reference_canvas.png")
    report = {"schema_version": 1, "kind": "vfx_loop_metrics", "video": file_record(args.video),
              "reference": file_record(args.reference) if args.reference else None, "fps": fps, **report,
              "note": "Pixel metrics locate candidate seams; they do not judge identity or motion quality"}
    save_json(out / "loop_metrics.json", report)
    return report


def _frame_list(text, count):
    picks = sorted({int(x) for x in text.split(",") if x.strip()})
    for i in picks:
        if not 0 <= i < count:
            raise ValueError(f"frame {i} is outside 0..{count - 1}")
    return picks


def _cmd_keyframes(args):
    frames, fps = read_frames(args.video)
    h, w = frames[0].shape[:2]
    work = working_size(w, h, args.width)
    picks = _frame_list(args.frames, len(frames))
    out = new_directory(args.output_dir)
    written = []
    for i in picks:
        im = Image.fromarray(frames[i])
        if im.size != work:
            im = im.resize(work, Image.Resampling.LANCZOS)
        im.save(out / f"frame_{i:05d}.png")
        written.append(str(out / f"frame_{i:05d}.png"))
    report = {"status": "complete", "video": str(Path(args.video).resolve()), "frames": len(frames), "fps": fps,
              "working_size": list(work), "keyframes": written,
              "next": "open each keyframe with mask_session.py create; paint the object white"}
    save_json(out / "keyframes.json", report)
    return report


def _cmd_segment_plan(args):
    frames, fps = read_frames(args.video)
    h, w = frames[0].shape[:2]
    work = working_size(w, h, args.width)
    out = new_directory(args.output_dir)
    masks = {}
    for item in args.mask:
        frame, _, path = item.partition("=")
        if not path:
            raise ValueError("--mask must be FRAME=PATH")
        frame = int(frame)
        with Image.open(path) as im:
            converted = editor_mask_to_l(im, work)
        if not np.asarray(converted).any():
            raise ValueError(f"mask for frame {frame} is empty")
        target = out / f"seed_mask_{frame:05d}.png"
        converted.save(target)
        masks[frame] = target
    plan = segment_plan(args.video, masks, len(frames), fps or 24.0, work, args.object_id)
    (out / "segment_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "complete", "plan": str(out / "segment_plan.json"), "working_size": list(work)}


def _cmd_unpack_masks(args):
    import io
    import zipfile
    source = Path(args.segment_dir)
    zpath = source / "layers.zip" if source.is_dir() else source
    prefix = f"masks/object-{args.object_id:03d}/"
    size = None
    if args.video:
        frames, _ = read_frames(args.video)
        size = (frames[0].shape[1], frames[0].shape[0])
    out = new_directory(args.output_dir)
    with zipfile.ZipFile(zpath) as archive:
        names = sorted(n for n in archive.namelist() if n.startswith(prefix) and n.lower().endswith(".png"))
        if not names:
            raise ValueError(f"no masks for object {args.object_id} in {zpath}")
        for k, n in enumerate(names):
            with Image.open(io.BytesIO(archive.read(n))) as im:
                m = im.convert("L")
            if size and m.size != size:
                m = m.resize(size, Image.Resampling.NEAREST)
            m.save(out / f"{k:05d}.png")
    return {"status": "complete", "output": str(out), "masks": len(names)}


def _cmd_mask_preview(args):
    frames, _ = read_frames(args.video)
    masks = read_masks(args.masks, len(frames), (frames[0].shape[1], frames[0].shape[0]))
    n = len(frames)
    picks = _frame_list(args.frames, n) if args.frames else sorted({0, n // 4, n // 2, 3 * n // 4, n - 1})
    if Path(args.output).exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    mask_overlay_strip(frames, masks, picks, args.output)
    return {"status": "complete", "output": str(Path(args.output).resolve()), "frames": picks}



def _cmd_prop_paste(args):
    def rgb(path):
        with Image.open(path) as im:
            return np.asarray(im.convert("RGB"))
    with Image.open(args.mask) as im:
        painted = np.asarray(im.convert("RGB").convert("L"))  # editor export: white paint on black, alpha ignored
    out, weight, stats = prop_paste(rgb(args.source), rgb(args.edited), painted, args.grow, args.near,
                                    args.key, args.tolerance, args.softness)
    directory = new_directory(args.output_dir)
    Image.fromarray(out).save(directory / "composited.png")
    Image.fromarray(weight).save(directory / "selection.png")
    report = {"schema_version": 1, "kind": "vfx_prop_paste", "status": "candidate",
              "inputs": {"source": file_record(args.source), "edited": file_record(args.edited), "mask": file_record(args.mask)},
              "parameters": {"grow": args.grow, "near": args.near, "tolerance": args.tolerance, "softness": args.softness},
              **stats, "outputs": [file_record(directory / "composited.png"), file_record(directory / "selection.png")],
              "acceptance": "pending human review; this only replaces the prop region, it does not judge the design"}
    save_json(directory / "result.json", report)
    return report


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def alpha_common(p):
        p.add_argument("--input", required=True, help="MP4 or directory of PNG frames")
        p.add_argument("--output-dir", required=True, help="New directory; existing directories are rejected")
        p.add_argument("--reference-alpha", help="Optional PNG RGBA sequence directory with ground-truth alpha")
        p.add_argument("--fps", type=float, default=24.0, help="FPS recorded for PNG-directory input")

    p = sub.add_parser("luma-alpha", help="Black-background effect -> straight RGBA PNG sequence")
    alpha_common(p)
    p.add_argument("--black-point", type=float, default=0.0, help="0..1; background level mapped to alpha 0")
    p.add_argument("--white-point", type=float, default=1.0)
    p.add_argument("--gamma", type=float, default=1.0)
    p = sub.add_parser("chroma-alpha", help="Green-screen key (video_composite ramp) -> RGBA PNG sequence")
    alpha_common(p)
    p.add_argument("--key", default="00FF00")
    p.add_argument("--tolerance", type=float, default=60.0)
    p.add_argument("--softness", type=float, default=40.0)
    p.add_argument("--despill", action="store_true")
    p.add_argument("--unmix", action="store_true", help="Remove key colour from semi-transparent pixels")
    p = sub.add_parser("birefnet-alpha", help="Per-frame BiRefNet matte (CUDA, local weights only)")
    alpha_common(p)
    p.add_argument("--model-root", required=True, type=Path)
    p.add_argument("--variant", default="general")
    p.add_argument("--key", help="Optional key colour used only for the fringe diagnostic")
    p = sub.add_parser("metrics", help="Print alpha metrics for an RGBA PNG sequence")
    p.add_argument("--input", required=True)
    p.add_argument("--key")
    p = sub.add_parser("board", help="Original vs RGBA candidates on alpha/dark/light")
    p.add_argument("--original", required=True)
    p.add_argument("--candidate", action="append", required=True, help="LABEL=RGBA_PNG_DIR")
    p.add_argument("--frame", type=int, default=-1, help="Frame index; default middle")
    p.add_argument("--thumb", type=int, default=320)
    p.add_argument("--output", required=True)
    p = sub.add_parser("pack", help="RGBA PNG sequence -> sprite sheet (+JSON), optional APNG/WebM VP9 alpha")
    p.add_argument("--input", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--columns", type=int)
    p.add_argument("--fps", type=float, default=24.0)
    p.add_argument("--apng", action="store_true")
    p.add_argument("--webm", action="store_true")
    p.add_argument("--crf", type=int, default=18)
    p = sub.add_parser("sam-to-edit-mask", help="SAM white=selected L masks -> image_edit alpha masks (0=edit)")
    p.add_argument("--masks", required=True)
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("mask-recolor", help="Hue rotation inside SAM masks; outside stays byte-exact")
    p.add_argument("--input", required=True)
    p.add_argument("--masks", required=True, help="Directory of L masks, white=selected, one per frame")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--from-hue", type=float, required=True)
    p.add_argument("--to-hue", type=float, required=True)
    p.add_argument("--hue-range", type=float, default=45.0)
    p.add_argument("--min-saturation", type=float, default=0.12)
    p.add_argument("--threshold", type=int, default=128)
    p.add_argument("--feather", type=int, default=0)
    p = sub.add_parser("mask-composite", help="Paste an edited video inside SAM masks over the original")
    p.add_argument("--original", required=True)
    p.add_argument("--edited", required=True)
    p.add_argument("--masks", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--feather", type=int, default=0)
    p = sub.add_parser("loop-metrics", help="First frame vs reference, last vs first, loop seam")
    p.add_argument("--video", required=True)
    p.add_argument("--reference")
    p.add_argument("--key", help="Background key colour used to crop a subject ROI, e.g. 00FF00")
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("keyframes", help="Extract frames (video_layers working size) for hand-painted object masks")
    p.add_argument("--video", required=True)
    p.add_argument("--frames", default="0", help="Comma list, e.g. 0,24 (frame 0 is required later)")
    p.add_argument("--width", type=int, help="Working width (even, 256..1280); default source width capped at 1280")
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("segment-plan", help="Hand-painted masks -> video_layers segment plan (mask prompts)")
    p.add_argument("--video", required=True)
    p.add_argument("--mask", action="append", required=True, help="FRAME=PATH of a painted mask (white = object)")
    p.add_argument("--object-id", type=int, default=1)
    p.add_argument("--width", type=int)
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("unpack-masks", help="video_layers layers.zip -> per-frame L masks (optionally at source size)")
    p.add_argument("--segment-dir", required=True, help="video_layers run output dir or its layers.zip")
    p.add_argument("--object-id", type=int, default=1)
    p.add_argument("--video", help="Resize masks (nearest) to this video's size")
    p.add_argument("--output-dir", required=True)
    p = sub.add_parser("mask-preview", help="Magenta mask overlay strip for human confirmation")
    p.add_argument("--video", required=True)
    p.add_argument("--masks", required=True)
    p.add_argument("--frames", help="Comma list; default 5 evenly spaced frames")
    p.add_argument("--output", required=True)
    p = sub.add_parser("prop-paste", help="Paste a re-designed prop from an edited still onto the source green screen")
    p.add_argument("--source", required=True, help="Original still (green screen)")
    p.add_argument("--edited", required=True, help="AI-edited still with the new prop (e.g. flux2_edit output)")
    p.add_argument("--mask", required=True, help="Painted prop mask, white = prop (mask_session mask_editor.png)")
    p.add_argument("--grow", type=int, default=6)
    p.add_argument("--near", type=int, default=30, help="How far (px) the new prop may extend beyond the painting")
    p.add_argument("--key", default="auto", help="Edited still's green, RRGGBB or auto (median)")
    p.add_argument("--tolerance", type=float, default=40.0)
    p.add_argument("--softness", type=float, default=40.0)
    p.add_argument("--output-dir", required=True)
    return parser


COMMANDS = {"luma-alpha": _cmd_alpha, "chroma-alpha": _cmd_alpha, "birefnet-alpha": _cmd_alpha,
            "metrics": _cmd_metrics, "board": _cmd_board, "pack": _cmd_pack,
            "sam-to-edit-mask": _cmd_sam_to_edit, "mask-recolor": _cmd_mask_recolor,
            "mask-composite": _cmd_mask_composite, "loop-metrics": _cmd_loop,
            "keyframes": _cmd_keyframes, "segment-plan": _cmd_segment_plan,
            "unpack-masks": _cmd_unpack_masks, "mask-preview": _cmd_mask_preview,
            "prop-paste": _cmd_prop_paste}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = COMMANDS[args.command](args)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.command != "metrics":
        print(json.dumps({"status": result.get("status", "complete"),
                          "output": result.get("output") or getattr(args, "output_dir", None)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
