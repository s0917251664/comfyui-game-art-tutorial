"""本機影片 task:video_concat、video_composite。只在本機用 PyAV(+numpy)組裝既有影片,不經 ComfyUI。"""
import os
import time

from ..runtime import facade as rt

TASKS = ("video_concat", "video_composite")


def _add_video_concat(sub, parents):
    p_cat = sub.add_parser(
        "video_concat",
        help="把多支已生成的短片接成一支(外部組裝,不是剪接台)。解析度跟第一支對齊。每支都有音軌才接立體聲。",
        parents=[parents["common"]],
    )
    p_cat.add_argument("--video", action="append", required=True, help="可重複給多次,順序就是播放順序")
    p_cat.add_argument("--name", default="video_concat", help="輸出檔名前綴,預設 video_concat")
    p_cat.add_argument(
        "--overwrite", action="store_true",
        help="明確允許覆寫既有輸出；預設拒絕以免重跑破壞既有素材。",
    )
    p_cat.add_argument(
        "--resize-mode", choices=["strict", "fit", "fill", "stretch"], default="strict",
        help="尺寸不一致時的明確處理；預設 strict 拒絕，fit 加黑邊，fill 裁切，stretch 拉伸。",
    )
    p_cat.add_argument(
        "--audio-policy", choices=["require-consistent", "drop", "silence-missing"],
        default="require-consistent",
        help="混合有聲/無聲的處理；預設拒絕，drop 丟掉全部音訊，silence-missing 補靜音。",
    )
    p_cat.add_argument("--shot-id", help="安全鏡號，供 concat sidecar 追溯。")
    p_cat.add_argument("--resume", action="store_true", help="驗證既有 concat sidecar 後才跳過。")


def _add_video_composite(sub, parents):
    p_comp = sub.add_parser(
        "video_composite",
        help=(
            "把綠幕前景疊到背景(影片或靜態圖)上——chroma key，純本機 PyAV+numpy 逐幀合成，"
            "不經 ComfyUI、不呼叫任何生成模型。前景必須是本產線輸出的綠幕素材(見"
            "comfyui-video-gen skill)。目前不支援 --resume。"
        ),
        parents=[parents["common"]],
    )
    p_comp.add_argument("--foreground", required=True, help="綠幕前景 mp4(產線輸出，24fps)")
    p_comp.add_argument("--background", required=True, help="背景 mp4(24fps)或靜態圖片")
    p_comp.add_argument(
        "--chroma-color", default="00FF00",
        help="去背色碼,6 碼十六進位,預設純綠 00FF00(跟這條產線的綠幕素材慣例一致)",
    )
    p_comp.add_argument(
        "--tolerance", type=float, default=60.0,
        help="判定為背景色的色距門檻,0..255,預設 60；數值越大摳得越乾淨但邊緣越容易吃色",
    )
    p_comp.add_argument(
        "--softness", type=float, default=40.0,
        help="邊緣羽化寬度,0(不含)..255,預設 40；數值越小邊緣越銳利但越容易有鋸齒/色邊",
    )
    p_comp.add_argument(
        "--resize-mode", choices=["strict", "fit", "fill", "stretch"], default="fill",
        help="背景尺寸跟前景不同時的處理；預設 fill 裁切填滿(背景本來就少有跟前景同尺寸的情況)，"
             "strict 拒絕，fit 加黑邊，stretch 拉伸。",
    )
    p_comp.add_argument("--name", default="video_composite", help="輸出檔名前綴,預設 video_composite")
    p_comp.add_argument(
        "--overwrite", action="store_true",
        help="明確允許覆寫既有輸出；預設拒絕以免重跑破壞既有素材。",
    )
    p_comp.add_argument("--shot-id", help="安全鏡號，供 sidecar 追溯。")


_ADDERS = {
    "video_concat": _add_video_concat,
    "video_composite": _add_video_composite,
}


def add_parser(sub, parents, task):
    _ADDERS[task](sub, parents)


def validate(args):
    rt._safe_identifier(args.name, "--name")
    rt._safe_identifier(getattr(args, "shot_id", None), "--shot-id")


def run_local(args, video_started):
    """完整執行本機 task;不需要 ComfyUI URL。"""
    if args.task == "video_concat":
        _run_video_concat(args, video_started)
    elif args.task == "video_composite":
        _run_video_composite(args, video_started)
    else:
        raise ValueError(f"不是本機影片 task: {args.task}")


def _run_video_concat(args, video_started):
    out_dir = getattr(args, "output_dir", None) or rt.OUTPUT_DIR
    try:
        if all(os.path.isfile(os.path.abspath(os.fspath(path))) for path in args.video):
            input_metadata = [
                rt.validate_video_input(path, label=f"video_concat input[{index}]")
                for index, path in enumerate(args.video)
            ]
        else:
            # concat_videos performs the authoritative open/decode check;
            # this fallback only keeps mocked local callers from needing
            # real media while still failing safely in production.
            input_metadata = [{
                "path": os.path.abspath(os.fspath(path)), "width": 0, "height": 0,
                "fps": rt.VIDEO_FPS, "frames": 0, "duration_seconds": 0.0, "audio": False,
            } for path in args.video]
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if args.audio_policy == "require-consistent":
        audio_flags = [bool(item["audio"]) for item in input_metadata]
        if any(audio_flags) and not all(audio_flags):
            raise SystemExit(
                "video_concat 輸入音訊不一致；預設拒絕混合有聲/無聲。"
                "請明確給 --audio-policy drop 或 silence-missing"
            )
    expected_audio = (
        False if args.audio_policy == "drop" else
        any(item["audio"] for item in input_metadata)
    )
    video_inputs = list(args.video)
    video_prefix = rt.video_filename_prefix(args.task, args.shot_id, args.name)
    total_frames = sum(item["frames"] for item in input_metadata)
    total_duration = sum(item["duration_seconds"] for item in input_metadata)
    video_contract = rt.make_video_contract(
        args.task, "local", input_metadata[0]["width"], input_metadata[0]["height"],
        duration=total_duration, audio_expected=expected_audio,
        expected_frames=total_frames, frame_tolerance=rt.VIDEO_FRAME_TOLERANCE,
        input_metadata=input_metadata,
    )
    video_contract["resize_mode"] = args.resize_mode
    video_contract["audio_policy"] = args.audio_policy
    try:
        dest = rt._safe_output_path(out_dir, f"{video_prefix}.mp4")
    except (TypeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    os.makedirs(out_dir, exist_ok=True)
    if args.resume:
        try:
            metadata = rt.resume_video_output(
                dest, args.task, "local", None, video_inputs, None, video_contract,
            )
        except (RuntimeError, rt.VideoContractError) as exc:
            raise SystemExit(str(exc)) from exc
        print(f"[恢復] {dest}")
        return
    concat_kwargs = {"allow_overwrite": args.overwrite}
    if args.resize_mode != "strict":
        concat_kwargs["resize_mode"] = args.resize_mode
    if args.audio_policy != "require-consistent":
        concat_kwargs["audio_policy"] = args.audio_policy
    rt.concat_videos(args.video, dest, **concat_kwargs)
    print(f"[完成] {dest}")
    elapsed = time.monotonic() - video_started if video_started else None
    report_contract = None if any(item["width"] == 0 for item in input_metadata) else video_contract
    metadata = rt.report_video_output(
        dest, task="video_concat", backend="local", elapsed_seconds=elapsed,
        **({"expected_contract": report_contract} if report_contract is not None else {}),
    )
    rt.write_video_sidecar(
        dest, args.task, "local", None, "", "", video_inputs, None,
        video_contract, metadata, elapsed_seconds=elapsed,
    )
    return


def _run_video_composite(args, video_started):
    out_dir = getattr(args, "output_dir", None) or rt.OUTPUT_DIR
    background_is_video = (
        os.path.splitext(args.background)[1].lower() in rt.VIDEO_COMPOSITE_BACKGROUND_EXTS
    )
    try:
        if os.path.isfile(os.path.abspath(os.fspath(args.foreground))):
            fg_metadata = rt.validate_video_input(args.foreground, label="video_composite --foreground")
        else:
            # composite_videos performs the authoritative open/decode check;
            # this fallback only keeps mocked local callers from needing
            # real media while still failing safely in production.
            fg_metadata = {
                "path": os.path.abspath(os.fspath(args.foreground)), "width": 0, "height": 0,
                "fps": rt.VIDEO_FPS, "frames": 0, "duration_seconds": 0.0, "audio": False,
            }
        if background_is_video and os.path.isfile(os.path.abspath(os.fspath(args.background))):
            rt.validate_video_input(args.background, label="video_composite --background")
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    video_inputs = [args.foreground, args.background]
    video_prefix = rt.video_filename_prefix(args.task, args.shot_id, args.name)
    video_contract = rt.make_video_contract(
        args.task, "local", fg_metadata["width"], fg_metadata["height"],
        duration=fg_metadata["duration_seconds"], audio_expected=fg_metadata["audio"],
        expected_frames=fg_metadata["frames"], frame_tolerance=rt.VIDEO_FRAME_TOLERANCE,
        input_metadata=[fg_metadata],
    )
    video_contract["resize_mode"] = args.resize_mode
    video_contract["chroma_color"] = args.chroma_color
    video_contract["tolerance"] = args.tolerance
    video_contract["softness"] = args.softness
    try:
        dest = rt._safe_output_path(out_dir, f"{video_prefix}.mp4")
    except (TypeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    os.makedirs(out_dir, exist_ok=True)
    try:
        rt.composite_videos(
            args.foreground, args.background, dest,
            chroma_color=args.chroma_color, tolerance=args.tolerance, softness=args.softness,
            resize_mode=args.resize_mode, allow_overwrite=args.overwrite,
        )
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"[完成] {dest}")
    elapsed = time.monotonic() - video_started if video_started else None
    report_contract = None if fg_metadata["width"] == 0 else video_contract
    metadata = rt.report_video_output(
        dest, task="video_composite", backend="local", elapsed_seconds=elapsed,
        **({"expected_contract": report_contract} if report_contract is not None else {}),
    )
    rt.write_video_sidecar(
        dest, args.task, "local", None, "", "", video_inputs, None,
        video_contract, metadata, elapsed_seconds=elapsed,
    )
    return
