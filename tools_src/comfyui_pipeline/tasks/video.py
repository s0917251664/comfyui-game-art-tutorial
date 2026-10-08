"""ComfyUI 影片 task:img2video、fx_loop、transition、clip_extend、camera_move、character_video、pose_drive。

每個 task 的 prepare() 只負責驗證輸入、上傳參考檔、用固定 template 填 graph 與輸出契約;排隊、輪詢、下載與
輸出驗證由 cli.py 的共用流程處理。模型檔名用 template pin，不跟 video_capabilities.json。
"""
import os
import sys
from pathlib import Path

from ..client import OUTPUT_DIR
from ..image_graphs import seed_or_random, validate_dimensions
from ..runner import template as runner_template
from ..video_catalog import (
    CAMERA_MOVES, CHARACTER_REF_MAX, VIDEO_FPS, VIDEO_INPUT_MIN_DURATION, VIDEO_LOOP_SUFFIX,
)
from ..video_config import backend_has, require_video_backend
from ..video_contract import _safe_identifier, make_video_contract, video_filename_prefix
from ..video_graphs import (
    build_camera_end_still, camera_move_prompt, h3_frame_count, h3_pose_drive_prompt,
    h3_ref_prompt, wan_frame_count,
)
from ..video_media import (
    _make_temp_image_path, _remove_temp_file, _require_video_duration, _require_wh_pair,
    extract_last_frame, validate_motion_reference_fps, validate_transition_images,
    validate_video_input, video_canvas,
)
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
        help="鏡頭鎖定的循環特效/環境元素/角色 Idle 循環。H3 會把 --image 同時當首幀與尾幀。預設抽幀交引擎。",
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
        help="內容轉場:已知 A、已知 B,模型只負責中間;--start 與 --end 可同一張 Idle 做「Idle→動作→Idle」。傳統硬切/疊化不要用這個。",
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
        "--camera", required=True, choices=list(CAMERA_MOVES),
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
        help="角色參考生影片:參考圖鎖身份,第一幀不保證是那張定稿圖。對應靜態 style_lock,不是 img2video。",
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
        help="表演驅動:角色靜幀 + 動作參考影片。靜幀只當身份參考,第一幀不保證是它。對應靜態 character_action。",
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
        validate_dimensions(args.width, args.height)
    _safe_identifier(getattr(args, "shot_id", None), "--shot-id")
    _safe_identifier(getattr(args, "name", None), "--name")
    if getattr(args, "resume", False) and not (
            getattr(args, "shot_id", None) or getattr(args, "name", None)):
        raise ValueError("--resume 需要 --name 或 --shot-id 才能精確定位輸出")


def _repo_with_video_templates():
    """從這個檔案往上找含影片 template 的 repo 根目錄。部署到 ComfyUI/tools 時還沒有 templates/。"""
    for parent in Path(__file__).resolve().parents:
        marker = parent / "templates" / "video" / "wan" / "img2video" / "template.json"
        if marker.is_file():
            return parent
    raise SystemExit(
        "影片 task 的 graph 在 templates/video（固定 template，由 runner 填值）。"
        "請從 repo 執行 python tools_src/generate.py <task>。"
        "部署到 ComfyUI/tools 的複本要等 templates 納入部署後才找得到這些 template。"
    )


def _load_video_template(template_id):
    root = _repo_with_video_templates()
    return runner_template.load_template(
        runner_template.templates_root(root), template_id, repo_root=root)


def _frame_count(backend, duration):
    if backend == "wan":
        return wan_frame_count(duration)
    if backend == "h3":
        return h3_frame_count(duration)
    raise SystemExit(f"未知 --backend {backend!r}")


def _patch_loaded(template, values, uploads):
    """本機路徑給 resolve；已上傳檔名只放 upload_paths。不跑 template 的 pre，也不 queue。"""
    filled = dict(values)
    if "negative" in filled and (not filled["negative"] or "negative" not in template.slots):
        del filled["negative"]
    resolution = runner_template.resolve(template, filled, run_id="video-task")
    graph, _changes = runner_template.patch(template, resolution, uploads)
    return graph, template.data["outputs"][0]["node"]


def _graph_from_template(template_id, values, uploads):
    return _patch_loaded(_load_video_template(template_id), values, uploads)


def _common_slots(backend, prompt, width, height, seed, duration, filename_prefix):
    return {
        "prompt": prompt,
        "width": width,
        "height": height,
        "length": _frame_count(backend, duration),
        "seed": seed_or_random(seed),
        "filename_prefix": filename_prefix,
    }


def _i2v_graph(backend, prompt, image_path, image_upload, width, height, seed, duration,
               filename_prefix, negative=None, last_path=None, last_upload=None):
    """Wan 一律 video/wan/img2video（忽略尾幀）。H3 有尾幀才用 video/h3/img2video-last。"""
    if backend == "wan":
        template_id = "video/wan/img2video"
        use_last = False
    elif backend == "h3":
        use_last = bool(last_upload)
        template_id = "video/h3/img2video-last" if use_last else "video/h3/img2video"
    else:
        raise SystemExit(f"未知 --backend {backend!r}")
    values = _common_slots(backend, prompt, width, height, seed, duration, filename_prefix)
    values["start_image"] = image_path
    uploads = {"start_image": image_upload}
    if use_last:
        if not last_path:
            raise SystemExit("有尾幀時必須有本機尾幀路徑")
        values["last_image"] = last_path
        uploads["last_image"] = last_upload
    if negative:
        values["negative"] = negative
    return _graph_from_template(template_id, values, uploads)


def _character_graph(backend, prompt, ref_paths, ref_uploads, width, height, seed, duration,
                     filename_prefix):
    if backend != "h3":
        raise SystemExit(f"character_video 目前沒有 {backend} 實作")
    template_id = f"video/h3/character-video-{len(ref_paths)}"
    template = _load_video_template(template_id)
    image_slots = [
        name for name, slot in template.slots.items()
        if slot.get("upload") and slot.get("type") == "image"
    ]
    if len(image_slots) != len(ref_paths):
        raise SystemExit(
            f"{template_id} 圖片 slot 是 {', '.join(image_slots) or '無'}，參考圖有 {len(ref_paths)} 張"
        )
    values = _common_slots(
        backend, h3_ref_prompt(prompt, len(ref_paths)), width, height, seed, duration, filename_prefix)
    uploads = {}
    for name, path, uploaded in zip(image_slots, ref_paths, ref_uploads):
        values[name] = path
        uploads[name] = uploaded
    return _patch_loaded(template, values, uploads)


def _pose_graph(backend, prompt, image_path, image_upload, motion_path, motion_upload,
                width, height, seed, duration, control_type, filename_prefix, negative=None):
    if backend not in ("wan", "h3"):
        raise SystemExit(f"pose_drive 目前沒有 {backend} 實作")
    text = h3_pose_drive_prompt(prompt) if backend == "h3" else prompt
    values = _common_slots(backend, text, width, height, seed, duration, filename_prefix)
    values["start_image"] = image_path
    values["motion_video"] = motion_path
    if negative:
        values["negative"] = negative
    uploads = {"start_image": image_upload, "motion_video": motion_upload}
    return _graph_from_template(f"video/{backend}/pose-drive-{control_type}", values, uploads)


def prepare(ctx, args, upload):
    """驗證輸入、上傳參考檔並用 template 填好影片 graph,回傳 VideoPlan。"""
    continuity_refs = {}
    video_prompt = None
    if args.task == "img2video":
        backend = require_video_backend(args.task, args.backend, ctx.active_video_config)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        video_inputs = [args.image]
        continuity_refs = {"source": args.image}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        graph, out_id = _i2v_graph(
            backend, args.prompt, args.image, img_fn, width, height, args.seed, duration,
            video_prefix, negative=args.negative,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "fx_loop":
        backend = require_video_backend(args.task, args.backend, ctx.active_video_config)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        loop_prompt = args.prompt if "loop" in args.prompt.lower() else f"{args.prompt}, {VIDEO_LOOP_SUFFIX}"
        video_prompt = loop_prompt
        video_inputs = [args.image]
        continuity_refs = {"source": args.image}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        graph, out_id = _i2v_graph(
            backend, loop_prompt, args.image, img_fn, width, height, args.seed, duration,
            video_prefix, negative=args.negative, last_path=args.image, last_upload=img_fn,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "transition":
        backend = require_video_backend(args.task, args.backend, ctx.active_video_config)
        duration = _require_video_duration(args.duration)
        if (args.width is None) ^ (args.height is None):
            raise SystemExit("--width 跟 --height 要一起給,或兩個都不給。")
        try:
            validate_transition_images(args.start, args.end)
        except (OSError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        width, height = video_canvas(args.start, args.width, args.height)
        start_fn = upload(args.start)
        end_fn = upload(args.end)
        video_inputs = [args.start, args.end]
        continuity_refs = {"start": args.start, "end": args.end}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        graph, out_id = _i2v_graph(
            backend, args.prompt, args.start, start_fn, width, height, args.seed, duration,
            video_prefix, last_path=args.end, last_upload=end_fn,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "clip_extend":
        if bool(args.video) == bool(args.image):
            raise SystemExit("clip_extend 要 --video 上一支 mp4,或 --image 上一鏡尾幀,只能給一個。")
        backend = require_video_backend(args.task, args.backend, ctx.active_video_config)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        still = args.image
        temp_still = None
        if args.video:
            if os.path.isfile(os.path.abspath(os.fspath(args.video))):
                try:
                    validate_video_input(args.video, label="clip_extend --video", min_duration=VIDEO_INPUT_MIN_DURATION)
                except (RuntimeError, ValueError) as exc:
                    raise SystemExit(str(exc)) from exc
            out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
            temp_still = _make_temp_image_path(out_dir, "_clip_extend_last_")
            try:
                extract_last_frame(args.video, temp_still)
                print(f"[連戲] 上一鏡尾幀 -> {temp_still}")
                still = temp_still
                width, height = video_canvas(still, args.width, args.height)
                img_fn = upload(still)
            finally:
                _remove_temp_file(temp_still)
        else:
            width, height = video_canvas(still, args.width, args.height)
            img_fn = upload(still)
        video_inputs = [args.video] if args.video else [args.image]
        continuity_refs = {"source": still} if args.image else {}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        graph, out_id = _i2v_graph(
            backend, args.prompt, still, img_fn, width, height, args.seed, duration,
            video_prefix, negative=args.negative,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "camera_move":
        backend = require_video_backend(args.task, args.backend, ctx.active_video_config)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        video_inputs = [args.image]
        continuity_refs = {"source": args.image}
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        cam_prompt = camera_move_prompt(args.camera, args.prompt)
        last_fn = None
        last_path = None
        end_path = None
        try:
            if backend_has(backend, "last_frame", ctx.active_video_config):
                if args.camera == "static":
                    last_fn = img_fn
                    last_path = args.image
                elif args.camera not in ("orbit_cw", "orbit_ccw"):
                    out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
                    end_path = _make_temp_image_path(out_dir, "_camera_end_")
                    build_camera_end_still(args.image, args.camera, width, height, end_path)
                    print(f"[運鏡] 終點靜幀 -> {end_path}")
                    last_fn = upload(end_path)
                    last_path = end_path
            graph, out_id = _i2v_graph(
                backend, cam_prompt, args.image, img_fn, width, height, args.seed, duration,
                video_prefix, negative=args.negative, last_path=last_path, last_upload=last_fn,
            )
        finally:
            _remove_temp_file(end_path)
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "character_video":
        backend = require_video_backend(args.task, args.backend, ctx.active_video_config)
        refs = args.character_ref
        if len(refs) > CHARACTER_REF_MAX:
            raise SystemExit(
                f"--character-ref 最多 {CHARACTER_REF_MAX} 張,目前 {len(refs)}"
            )
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        width, height = video_canvas(refs[0], args.width, args.height)
        ref_fns = [upload(p) for p in refs]
        video_inputs = list(refs)
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        graph, out_id = _character_graph(
            backend, args.prompt, refs, ref_fns, width, height, args.seed, duration, video_prefix,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    elif args.task == "pose_drive":
        backend = require_video_backend(args.task, args.backend, ctx.active_video_config)
        duration = _require_video_duration(args.duration)
        _require_wh_pair(args)
        print(
            "[提醒] pose_drive 的角色靜幀姿勢/朝向要接近動作片第一幀;"
            "對不上(例如站姿去套走路)會雙人/重影。",
            file=sys.stderr,
        )
        try:
            # Keep the cheap FPS-specific diagnostic first; the full decode
            # preflight follows and catches empty/truncated references.
            validate_motion_reference_fps(args.motion_ref)
            validate_video_input(
                args.motion_ref, label="pose_drive --motion-ref",
                min_duration=duration, require_fps=VIDEO_FPS,
            )
        except (RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        width, height = video_canvas(args.image, args.width, args.height)
        img_fn = upload(args.image)
        motion_fn = upload(args.motion_ref)
        video_inputs = [args.image, args.motion_ref]
        video_prefix = video_filename_prefix(args.task, args.shot_id, args.name)
        graph, out_id = _pose_graph(
            backend, args.prompt, args.image, img_fn, args.motion_ref, motion_fn,
            width, height, args.seed, duration, args.control_type, video_prefix,
            negative=args.negative,
        )
        video_contract = make_video_contract(args.task, backend, width, height, duration,
                                             audio_expected=(backend == "h3"))
    else:
        raise ValueError(f"不是這個模組的影片 task: {args.task}")
    return VideoPlan(
        graph=graph, out_id=out_id, backend=backend, inputs=video_inputs,
        continuity_refs=continuity_refs, prefix=video_prefix, contract=video_contract,
        prompt=video_prompt,
    )
