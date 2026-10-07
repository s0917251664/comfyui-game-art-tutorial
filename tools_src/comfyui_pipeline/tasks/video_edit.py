"""ComfyUI 影片 task:video_inpaint(Wan2.1 VACE 遮罩局部重繪,只改遮罩內,貼回原片)。

流程:讀來源片與 SAM 遮罩(白色=重畫)→ 擴張遮罩、算工作區、縮到 VACE 1.3B 的 480P 像素上限 →
控制片段與遮罩編成無損 FFV1 上傳 → 固定 graph 生成工作區影片(原始 mp4 走一般契約與 sidecar)→
finalize 把結果縮回、只在擴張+羽化遮罩內貼回原片,驗證遮罩外逐 byte 不變,寫 PNG 序列、MP4 與 result.json。
"""
import json
import os
import tempfile

from ..client import OUTPUT_DIR
from ..video_builders import build_video_inpaint_wan
from ..video_catalog import VIDEO_FPS
from ..video_config import require_video_backend
from ..video_contract import _safe_identifier, _sha256_file, make_video_contract, video_filename_prefix
from .. import video_edit_media as media
from ._common import VideoPlan

TASKS = ("video_inpaint",)


def add_parser(sub, parents, task):
    p = sub.add_parser(
        task,
        help="影片局部重繪(VACE):只重畫遮罩內,遮罩外貼回原片且逐 byte 不變。遮罩來自 video_layers segment(白色=重畫)。",
        parents=[parents["video"]],
    )
    p.add_argument("--video", required=True, help="來源影片(24 FPS,最多 81 幀)")
    p.add_argument("--masks", required=True,
                   help="逐幀遮罩:白色=重畫的 L PNG 資料夾,或 video_layers segment 的 layers.zip")
    p.add_argument("--mask-object", type=int, default=1, help="--masks 是 layers.zip 時取哪個物件 id,預設 1")
    p.add_argument("--prompt", required=True, help="描述整個畫面、特別是遮罩內要變成什麼(英文較穩)")
    p.add_argument("--mode", choices=["keep", "replace"], default="keep",
                   help="keep=保留遮罩內原內容當引導(改顏色/光效/材質,造型較能保住);"
                        "replace=遮罩內清空重畫(換成新物件,官方模板做法)")
    p.add_argument("--grow", type=int, default=8, help="遮罩向外擴張像素,預設 8")
    p.add_argument("--feather", type=int, default=4, help="貼回時邊緣羽化像素,預設 4;0=硬邊")
    p.add_argument("--pad", type=int, default=48, help="自動工作區在遮罩外留的邊,預設 48")
    p.add_argument("--crop", help="手動工作區 x0,y0,x1,y1(來源像素座標);不給就依遮罩自動算")
    p.add_argument("--strength", type=float, default=1.0, help="VACE 控制強度,預設 1.0")
    p.add_argument("--negative", help="負向詞;不給就用官方模板的預設負向詞")
    p.add_argument("--seed", type=int)


def _parse_crop(value):
    if value is None:
        return None
    parts = [p.strip() for p in str(value).split(",")]
    if len(parts) != 4:
        raise ValueError("--crop 格式是 x0,y0,x1,y1")
    try:
        return tuple(int(p) for p in parts)
    except ValueError as exc:
        raise ValueError("--crop 必須是 4 個整數") from exc


def validate(args):
    _safe_identifier(getattr(args, "shot_id", None), "--shot-id")
    _safe_identifier(getattr(args, "name", None), "--name")
    if getattr(args, "resume", False) and not (getattr(args, "shot_id", None) or getattr(args, "name", None)):
        raise ValueError("--resume 需要 --name 或 --shot-id 才能精確定位輸出")
    for label, value, upper in (("--grow", args.grow, 64), ("--feather", args.feather, 32), ("--pad", args.pad, 512)):
        if not 0 <= value <= upper:
            raise ValueError(f"{label} 必須介於 0..{upper}")
    if not 0.0 < args.strength <= 10.0:
        raise ValueError("--strength 必須介於 (0, 10]")
    if not 1 <= args.mask_object <= 999:
        raise ValueError("--mask-object 必須介於 1..999")
    _parse_crop(args.crop)


def _mask_input_paths(masks):
    if os.path.isdir(masks):
        return [os.path.join(masks, n) for n in sorted(os.listdir(masks)) if n.lower().endswith(".png")]
    return [masks]


def prepare(ctx, args, upload):
    backend = require_video_backend(args.task, args.backend, ctx.active_video_config)
    try:
        frames, fps = media.read_video_frames(args.video)
        media.validate_source(frames, fps)
        height, width = frames[0].shape[:2]
        masks = media.read_masks(args.masks, len(frames), (width, height), args.mask_object)
        grown = media.grow_masks(masks, args.grow)
        crop = media.compute_crop(grown, (width, height), args.pad, _parse_crop(args.crop))
        size = media.processing_size(crop[2] - crop[0], crop[3] - crop[1])
        controls, mask_clip = media.build_work_clips(frames, grown, crop, size, args.mode)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    length = media.vace_length(len(frames))
    out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    temp_paths = []
    try:
        for kind, clip in (("control", controls), ("mask", mask_clip)):
            fd, path = tempfile.mkstemp(prefix=f"_video_inpaint_{kind}_", suffix=".mkv", dir=out_dir)
            os.close(fd)
            temp_paths.append(path)
            media.write_lossless_video(clip, path)
        control_fn, mask_fn = upload(temp_paths[0]), upload(temp_paths[1])
    finally:
        for path in temp_paths:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
    prefix = video_filename_prefix(args.task, args.shot_id, args.name)
    graph, out_id = build_video_inpaint_wan(
        args.prompt, control_fn, mask_fn, size[0], size[1], length, seed=args.seed,
        negative=args.negative, strength=args.strength, filename_prefix=prefix,
        video_config=ctx.active_video_config,
    )
    contract = make_video_contract(args.task, backend, size[0], size[1], audio_expected=False,
                                   expected_frames=length)
    print(f"[工作區] crop={list(crop)} 處理尺寸={size[0]}x{size[1]} 幀={len(frames)}→length {length} mode={args.mode}")

    def finalize(raw_path):
        return finalize_paste_back(args, raw_path, frames, grown, crop, size, length)

    return VideoPlan(
        graph=graph, out_id=out_id, backend=backend,
        inputs=[args.video, *_mask_input_paths(args.masks)],
        prefix=prefix, contract=contract, finalize=finalize,
    )


def finalize_paste_back(args, raw_path, frames, grown, crop, size, length):
    """Paste the VACE work-area output back into the source; outside the mask stays byte-exact."""
    from PIL import Image
    raw, _ = media.read_video_frames(raw_path)
    stem = os.path.splitext(os.path.basename(raw_path))[0].rstrip("_")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(raw_path)), stem + "_composited")
    if os.path.lexists(out_dir):
        raise RuntimeError(f"拒絕覆寫既有貼回輸出: {out_dir}")
    composed, per_frame = media.paste_back(frames, raw[:len(frames)], crop, grown, args.feather)
    staging = tempfile.mkdtemp(prefix=f".{stem}_composited.", dir=os.path.dirname(out_dir))
    try:
        frame_dir = os.path.join(staging, "frames")
        os.makedirs(frame_dir)
        for i, f in enumerate(composed):
            Image.fromarray(f).save(os.path.join(frame_dir, f"{i:05d}.png"))
        media.encode_mp4(composed, os.path.join(staging, "composited.mp4"))
        report = {
            "schema_version": 1, "kind": "video_inpaint_paste_back", "status": "candidate",
            "raw_output": {"path": os.path.abspath(raw_path), "sha256": _sha256_file(raw_path),
                           "frames": len(raw), "used_frames": len(frames)},
            "source": {"path": os.path.abspath(args.video), "sha256": _sha256_file(args.video),
                       "frames": len(frames), "size": [int(frames[0].shape[1]), int(frames[0].shape[0])]},
            "masks": os.path.abspath(args.masks), "mask_object": args.mask_object,
            "mode": args.mode, "grow": args.grow, "feather": args.feather, "crop": list(crop),
            "processing_size": list(size), "vace_length": length, "seed": args.seed,
            "outside_changed_pixels_total": sum(r["outside_changed_pixels"] for r in per_frame),
            "per_frame": per_frame, "fps": VIDEO_FPS, "audio": "dropped",
            "outputs": {"frames_dir": "frames/ (PNG, lossless master)",
                        "mp4": "composited.mp4 (H.264 crf 18, re-encoded, not lossless)"},
            "acceptance": "pending human review; outside-mask preservation does not judge the edit",
        }
        with open(os.path.join(staging, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        os.replace(staging, out_dir)
    except Exception:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(f"[貼回] {len(composed)} 幀 -> {out_dir}（遮罩外變動 0）")
    return out_dir
