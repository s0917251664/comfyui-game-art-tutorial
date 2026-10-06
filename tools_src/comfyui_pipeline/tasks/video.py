"""ComfyUI 影片 task:img2video、fx_loop、transition、clip_extend、camera_move、character_video、pose_drive。

每個 task 的 prepare() 只負責驗證輸入、上傳參考檔、組 graph 與輸出契約;排隊、輪詢、下載與
輸出驗證由 cli.py 的共用流程處理。
"""
import os
import sys

from ..runtime import facade as rt
from ._common import VideoPlan

TASKS = ("img2video", "fx_loop", "transition", "clip_extend", "camera_move", "character_video", "pose_drive")


def _add_img2video(sub, parents):
    p_vid = sub.add_parser(
        "img2video",
        help="讓已過關的靜幀動起來(短片)。跟圖片產線的 --style / ControlNet / IPAdapter 不相容。",
        parents=[parents["video"]],
    )
    p_vid.add_argument("--prompt", required=True, help="這段要怎麼動(鏡頭鎖定/運鏡/動作),英文較穩")
    p_vid.add_argument("--image", required=True, help="已過關的靜幀路徑,不要用文生影片賭第一幀")
    p_vid.add_argument("--duration", type=float, default=2.0,
                        help="秒數,鎖在 2~6(預設 2)。更長要拆鏡,不要一次生整部片")
    p_vid.add_argument("--width", type=int, help="輸出寬,不給就跟來源圖比例走,最長邊上限 768")
    p_vid.add_argument("--height", type=int, help="輸出高,不給就跟來源圖比例走,最長邊上限 768")
    p_vid.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_vid.add_argument("--seed", type=int)
    p_vid.add_argument("--extract-frames", action="store_true", help="順便抽 png 序列到 <mp4 檔名>_frames/")


def _add_fx_loop(sub, parents):
    p_fx = sub.add_parser(
        "fx_loop",
        help="鏡頭鎖定的循環特效/環境元素(火、法陣、旗幟)。要能接首尾幀的 backend。預設抽幀交引擎。",
        parents=[parents["video"]],
    )
    p_fx.add_argument("--prompt", required=True, help="循環怎麼動,會自動補上 seamless loop 約束")
    p_fx.add_argument("--image", required=True, help="特效/元件的靜幀")
    p_fx.add_argument("--duration", type=float, default=2.0, help="秒數,鎖在 2~6,預設 2")
    p_fx.add_argument("--width", type=int)
    p_fx.add_argument("--height", type=int)
    p_fx.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_fx.add_argument("--seed", type=int)
    p_fx.add_argument("--no-extract-frames", dest="extract_frames", action="store_false",
                      help="不要抽 png 序列(預設會抽)")
    p_fx.set_defaults(extract_frames=True)


def _add_transition(sub, parents):
    p_tr = sub.add_parser(
        "transition",
        help="內容轉場:已知 A、已知 B,模型只負責中間。要能接首尾幀的 backend。傳統硬切/疊化不要用這個。",
        parents=[parents["video"]],
    )
    p_tr.add_argument("--prompt", required=True, help="中間發生什麼")
    p_tr.add_argument("--start", required=True, help="起始靜幀")
    p_tr.add_argument("--end", required=True, help="結束靜幀")
    p_tr.add_argument("--duration", type=float, default=2.0)
    p_tr.add_argument("--width", type=int)
    p_tr.add_argument("--height", type=int)
    p_tr.add_argument("--seed", type=int)
    p_tr.add_argument("--extract-frames", action="store_true")


def _add_clip_extend(sub, parents):
    p_ext = sub.add_parser(
        "clip_extend",
        help="同一場下一鏡:吃上一支 mp4 的最後一幀(或一張靜幀)再往後生成。長片連戲用這個,不要拉長單次 duration。",
        parents=[parents["video"]],
    )
    p_ext.add_argument("--prompt", required=True, help="接下來發生什麼")
    p_ext.add_argument("--video", help="上一支 mp4,會抽最後一幀當本鏡靜幀")
    p_ext.add_argument("--image", help="若已有上一鏡尾幀靜幀,跟 --video 二選一")
    p_ext.add_argument("--duration", type=float, default=2.0)
    p_ext.add_argument("--width", type=int)
    p_ext.add_argument("--height", type=int)
    p_ext.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_ext.add_argument("--seed", type=int)
    p_ext.add_argument("--extract-frames", action="store_true")


def _add_camera_move(sub, parents):
    p_cam = sub.add_parser(
        "camera_move",
        help="攝影組運鏡:主體盡量靜止,只有攝影機在動。--camera 是鎖死枚舉。",
        parents=[parents["video"]],
    )
    p_cam.add_argument("--image", required=True, help="已過關的靜幀")
    p_cam.add_argument(
        "--camera", required=True, choices=list(rt.CAMERA_MOVES),
        help="運鏡:static/pan_up/pan_down/pan_left/pan_right/zoom_in/zoom_out/orbit_cw/orbit_ccw",
    )
    p_cam.add_argument(
        "--prompt", default="",
        help="選填場景描述。不給就當主體完全靜止;運鏡以 --camera 為準,不要在這裡另寫一種運鏡",
    )
    p_cam.add_argument("--duration", type=float, default=2.0)
    p_cam.add_argument("--width", type=int)
    p_cam.add_argument("--height", type=int)
    p_cam.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_cam.add_argument("--seed", type=int)
    p_cam.add_argument("--extract-frames", action="store_true")


def _add_character_video(sub, parents):
    p_cv = sub.add_parser(
        "character_video",
        help="角色參考生影片:參考圖鎖身份,第一幀不必是那張定稿圖。對應靜態 style_lock,不是 img2video。",
        parents=[parents["video"]],
    )
    p_cv.add_argument("--prompt", required=True, help="新鏡頭裡這個角色在做什麼(英文較穩)")
    p_cv.add_argument(
        "--character-ref", action="append", required=True,
        help="角色參考圖,可重複給最多 9 張(多角度/特寫較穩)。第一張同時決定預設畫布比例",
    )
    p_cv.add_argument("--duration", type=float, default=2.0, help="秒數,鎖在 2~6,預設 2")
    p_cv.add_argument("--width", type=int)
    p_cv.add_argument("--height", type=int)
    p_cv.add_argument("--seed", type=int)
    p_cv.add_argument("--extract-frames", action="store_true")


def _add_pose_drive(sub, parents):
    p_pd = sub.add_parser(
        "pose_drive",
        help="表演驅動:角色靜幀 + 動作參考影片。對應靜態 character_action,姿勢來源是影片不是一張 pose 圖。",
        parents=[parents["video"]],
    )
    p_pd.add_argument("--prompt", required=True, help="這段鏡頭裡角色在做什麼(英文較穩)")
    p_pd.add_argument("--image", required=True, help="角色參考靜幀(這是誰)")
    p_pd.add_argument("--motion-ref", required=True, help="動作參考影片(這段怎麼動)")
    p_pd.add_argument(
        "--control-type", choices=["canny", "pose", "depth"], default="pose",
        help="動作怎麼抽:pose=骨架(預設,表演/肢體),canny=邊緣,depth=前後景",
    )
    p_pd.add_argument("--duration", type=float, default=2.0, help="秒數,鎖在 2~6,預設 2。長過參考影片的部分控制會變弱")
    p_pd.add_argument("--width", type=int)
    p_pd.add_argument("--height", type=int)
    p_pd.add_argument("--negative", help="負向詞;用不到的 backend 會忽略")
    p_pd.add_argument("--seed", type=int)
    p_pd.add_argument("--extract-frames", action="store_true")


_ADDERS = {
    "img2video": _add_img2video,
    "fx_loop": _add_fx_loop,
    "transition": _add_transition,
    "clip_extend": _add_clip_extend,
    "camera_move": _add_camera_move,
    "character_video": _add_character_video,
    "pose_drive": _add_pose_drive,
}


def add_parser(sub, parents, task):
    _ADDERS[task](sub, parents)


def validate(args):
    if args.width is not None and args.height is not None:
        rt.validate_dimensions(args.width, args.height)
    rt._safe_identifier(getattr(args, "shot_id", None), "--shot-id")
    rt._safe_identifier(getattr(args, "name", None), "--name")
    if getattr(args, "resume", False) and not (
            getattr(args, "shot_id", None) or getattr(args, "name", None)):
        raise ValueError("--resume 需要 --name 或 --shot-id 才能精確定位輸出")


def prepare(args, upload):
    """驗證輸入、上傳參考檔並組好影片 graph,回傳 VideoPlan。"""
    continuity_refs = {}
    video_prompt = None
    if args.task == "img2video":
        backend = rt.require_video_backend(args.task, args.backend, rt.ACTIVE_VIDEO_CONFIG)
        duration = rt._require_video_duration(args.duration)
        rt._require_wh_pair(args)
        width, height = rt.video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        video_inputs = [args.image]
        continuity_refs = {"source": args.image}
        video_prefix = rt.video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = rt.run_i2v(
            backend, args.prompt, img_fn, width, height, args.seed, duration,
            filename_prefix=video_prefix, negative=args.negative,
        )
        video_contract = rt.make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "fx_loop":
        backend = rt.require_video_backend(args.task, args.backend, rt.ACTIVE_VIDEO_CONFIG)
        duration = rt._require_video_duration(args.duration)
        rt._require_wh_pair(args)
        width, height = rt.video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        loop_prompt = args.prompt if "loop" in args.prompt.lower() else f"{args.prompt}, {rt.VIDEO_LOOP_SUFFIX}"
        video_prompt = loop_prompt
        video_inputs = [args.image]
        continuity_refs = {"source": args.image}
        video_prefix = rt.video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = rt.run_i2v(
            backend, loop_prompt, img_fn, width, height, args.seed, duration,
            last_image_filename=img_fn, filename_prefix=video_prefix, negative=args.negative,
        )
        video_contract = rt.make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "transition":
        backend = rt.require_video_backend(args.task, args.backend, rt.ACTIVE_VIDEO_CONFIG)
        duration = rt._require_video_duration(args.duration)
        if (args.width is None) ^ (args.height is None):
            raise SystemExit("--width 跟 --height 要一起給,或兩個都不給。")
        try:
            rt.validate_transition_images(args.start, args.end)
        except (OSError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        width, height = rt.video_canvas(args.start, args.width, args.height)
        start_fn = upload(args.start)
        end_fn = upload(args.end)
        video_inputs = [args.start, args.end]
        continuity_refs = {"start": args.start, "end": args.end}
        video_prefix = rt.video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = rt.run_i2v(
            backend, args.prompt, start_fn, width, height, args.seed, duration,
            last_image_filename=end_fn, filename_prefix=video_prefix,
        )
        video_contract = rt.make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "clip_extend":
        if bool(args.video) == bool(args.image):
            raise SystemExit("clip_extend 要 --video 上一支 mp4,或 --image 上一鏡尾幀,只能給一個。")
        backend = rt.require_video_backend(args.task, args.backend, rt.ACTIVE_VIDEO_CONFIG)
        duration = rt._require_video_duration(args.duration)
        rt._require_wh_pair(args)
        still = args.image
        temp_still = None
        if args.video:
            if os.path.isfile(os.path.abspath(os.fspath(args.video))):
                try:
                    rt.validate_video_input(args.video, label="clip_extend --video", min_duration=rt.VIDEO_INPUT_MIN_DURATION)
                except (RuntimeError, ValueError) as exc:
                    raise SystemExit(str(exc)) from exc
            out_dir = getattr(args, "output_dir", None) or rt.OUTPUT_DIR
            temp_still = rt._make_temp_image_path(out_dir, "_clip_extend_last_")
            try:
                rt.extract_last_frame(args.video, temp_still)
                print(f"[連戲] 上一鏡尾幀 -> {temp_still}")
                still = temp_still
                width, height = rt.video_canvas(still, args.width, args.height)
                img_fn = upload(still)
            finally:
                rt._remove_temp_file(temp_still)
        else:
            width, height = rt.video_canvas(still, args.width, args.height)
            img_fn = upload(still)
        video_inputs = [args.video] if args.video else [args.image]
        continuity_refs = {"source": still} if args.image else {}
        video_prefix = rt.video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = rt.run_i2v(
            backend, args.prompt, img_fn, width, height, args.seed, duration,
            filename_prefix=video_prefix, negative=args.negative,
        )
        video_contract = rt.make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "camera_move":
        backend = rt.require_video_backend(args.task, args.backend, rt.ACTIVE_VIDEO_CONFIG)
        duration = rt._require_video_duration(args.duration)
        rt._require_wh_pair(args)
        width, height = rt.video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        video_inputs = [args.image]
        continuity_refs = {"source": args.image}
        video_prefix = rt.video_filename_prefix(args.task, args.shot_id, args.name)
        cam_prompt = rt.camera_move_prompt(args.camera, args.prompt)
        last_fn = None
        end_path = None
        try:
            if rt.backend_has(backend, "last_frame"):
                if args.camera == "static":
                    last_fn = img_fn
                elif args.camera not in ("orbit_cw", "orbit_ccw"):
                    out_dir = getattr(args, "output_dir", None) or rt.OUTPUT_DIR
                    end_path = rt._make_temp_image_path(out_dir, "_camera_end_")
                    rt.build_camera_end_still(args.image, args.camera, width, height, end_path)
                    print(f"[運鏡] 終點靜幀 -> {end_path}")
                    last_fn = upload(end_path)
            prompt, out_id = rt.run_i2v(
                backend, cam_prompt, img_fn, width, height, args.seed, duration,
                last_image_filename=last_fn, filename_prefix=video_prefix,
                negative=args.negative,
            )
        finally:
            rt._remove_temp_file(end_path)
        video_contract = rt.make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "character_video":
        backend = rt.require_video_backend(args.task, args.backend, rt.ACTIVE_VIDEO_CONFIG)
        refs = args.character_ref
        if len(refs) > rt.CHARACTER_REF_MAX:
            raise SystemExit(
                f"--character-ref 最多 {rt.CHARACTER_REF_MAX} 張,目前 {len(refs)}"
            )
        duration = rt._require_video_duration(args.duration)
        rt._require_wh_pair(args)
        width, height = rt.video_canvas(refs[0], args.width, args.height)
        ref_fns = [upload(p) for p in refs]
        video_inputs = list(refs)
        video_prefix = rt.video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = rt.run_character_video(
            backend, args.prompt, ref_fns, width, height, args.seed, duration,
            filename_prefix=video_prefix,
        )
        video_contract = rt.make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "pose_drive":
        backend = rt.require_video_backend(args.task, args.backend, rt.ACTIVE_VIDEO_CONFIG)
        duration = rt._require_video_duration(args.duration)
        rt._require_wh_pair(args)
        print(
            "[提醒] pose_drive 的角色靜幀姿勢/朝向要接近動作片第一幀;"
            "對不上(例如站姿去套走路)會雙人/重影。",
            file=sys.stderr,
        )
        try:
            # Keep the cheap FPS-specific diagnostic first; the full decode
            # preflight follows and catches empty/truncated references.
            rt.validate_motion_reference_fps(args.motion_ref)
            rt.validate_video_input(
                args.motion_ref, label="pose_drive --motion-ref",
                min_duration=duration, require_fps=rt.VIDEO_FPS,
            )
        except (RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        width, height = rt.video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        motion_fn = upload(args.motion_ref)
        video_inputs = [args.image, args.motion_ref]
        video_prefix = rt.video_filename_prefix(args.task, args.shot_id, args.name)
        prompt, out_id = rt.run_pose_drive(
            backend, args.prompt, img_fn, motion_fn, width, height, args.seed, duration,
            control_type=args.control_type, filename_prefix=video_prefix,
            negative=args.negative,
        )
        video_contract = rt.make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    else:
        raise ValueError(f"不是這個模組的影片 task: {args.task}")
    return VideoPlan(
        graph=prompt, out_id=out_id, backend=backend, inputs=video_inputs,
        continuity_refs=continuity_refs, prefix=video_prefix, contract=video_contract,
        prompt=video_prompt,
    )
