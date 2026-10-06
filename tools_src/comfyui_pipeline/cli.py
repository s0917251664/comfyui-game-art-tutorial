"""generate.py 的 CLI 流程:組 argparse、共用驗證、解析設定檔/底模、送出、下載與結果檢查。

task 專屬的參數、驗證與 graph 組裝都在 ``tasks/`` 各模組;這裡只跑「每個 task 都一樣」的流程。
機器相關的執行期狀態(device、選用的圖片設定檔 / 影片 capability config)放在 ``context.RunContext``,
由 ``run()`` 建立(或由呼叫端傳入)後明確往下傳,不讀任何模組層級的可變全域。
"""
import argparse
import os
import sys
import time

from . import fingerprint as _fingerprint
from . import image_results as _image_results
from . import profiles as _profiles
from . import tasks
from .context import RunContext
from .client import (
    DEFAULT_HTTP_TIMEOUT, DEFAULT_TIMEOUT, OUTPUT_DIR, VideoTimeoutError, download_outputs,
    resolve_comfy_url, submit_and_wait, upload_image, validate_timeout,
)
from .image_capabilities import (
    IMAGE_GRAPH_TASKS, IMAGE_PROFILE_TASKS, load_image_capabilities, resolve_image_profile,
)
from .image_graphs import (
    DEVICE_CONFIG_PATH, RATING_TAGS, STYLE_CHECKPOINTS, attach_bg_removal, seed_or_random,
)
from .image_runtime import sync_image_runtime
from .video_catalog import DEFAULT_VIDEO_TIMEOUT, VIDEO_TASK_CAPS
from .video_config import configure_video_capability
from .video_contract import (
    VideoContractError, _find_named_video_output, report_video_output, resume_video_output,
    video_filename_prefix, write_video_sidecar, write_video_timeout_record,
)
from .video_media import extract_video_frames
from .tasks._common import add_runtime_arguments, build_parents


def build_parser():
    ap = argparse.ArgumentParser(description="穩定產圖核心腳本")
    add_runtime_arguments(ap)
    sub = ap.add_subparsers(dest="task", required=True)
    tasks.register_parsers(sub, build_parents())
    return ap


def validate_cli_args(args):
    default_timeout = (
        DEFAULT_VIDEO_TIMEOUT if args.task in VIDEO_TASK_CAPS else DEFAULT_TIMEOUT
    )
    args.timeout = getattr(args, "timeout", default_timeout)
    validate_timeout(args.timeout)
    tasks.validate_args(args)


def validate_task_capabilities(ctx, args):
    try:
        tasks.check_capabilities(ctx, args)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


def _resolve_style_checkpoint(ctx, args):
    """依 --style / 圖片設定檔 / 機器 tier 決定底模 checkpoint,並套用 --rating(會改 args.prompt)。"""
    style_checkpoint = None
    if getattr(args, "style", None) and ctx.active_image_profile is not None:
        active_profile = _profiles.load_profile(ctx.active_image_profile)
        if args.style not in active_profile.get("variants", {}):
            raise SystemExit(
                f"--style {args.style} 不在模型設定檔 {ctx.active_image_profile!r}（{active_profile['family']}）的風格清單；"
                f"這幾個風格 checkpoint 都是 SDXL 架構，跟非 SDXL 設定檔的 ControlNet/IPAdapter 對不上。"
            )
        style_checkpoint = active_profile["variants"][args.style]["checkpoint"]
    elif getattr(args, "style", None):
        if ctx.device.get("tier") not in ("sdxl_high", "sdxl", "sdxl_light"):
            raise SystemExit(
                f"--style 目前只支援 SDXL 家族機器(sdxl_high/sdxl/sdxl_light),"
                f"這台機器偵測到的 tier 是 {ctx.device.get('tier')!r}。"
                f"這幾個風格 checkpoint 都是 SDXL 架構,跟 sd15 tier 的 ControlNet/IPAdapter 對不上,"
                f"直接送出去 ComfyUI 執行期會 shape mismatch。"
            )
        style_checkpoint = STYLE_CHECKPOINTS[args.style]

    if getattr(args, "rating", None):
        if args.style not in RATING_TAGS:
            raise SystemExit(
                f"--rating 只在 --style anime/illustration 時有意義(這兩顆底模訓練資料本身用分級標籤"
                f"控制內容尺度),目前 --style={args.style!r} 沒有這個標籤慣例,加了也沒效果,直接擋下來。"
            )
        args.prompt = f"{RATING_TAGS[args.style][args.rating]}, {args.prompt}"
    return style_checkpoint


def _image_result_inputs(args):
    """--result-json 要記錄的輸入檔案(role + 路徑 + 雜湊)。"""
    result_inputs = []
    for role in ("image", "mask", "character_ref", "pose_ref", "structure_ref",
                 "appearance_ref", "control_ref"):
        value = getattr(args, role, None)
        if role == "control_ref" and not value and args.task == "guided_inpaint" \
                and getattr(args, "control_type", None):
            value = getattr(args, "image", None)
        if isinstance(value, (list, tuple)):
            result_inputs.extend({"role": role, "path": path} for path in value)
        elif value:
            result_inputs.append({"role": role, "path": value})
    try:
        return _image_results.input_records(result_inputs)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


def _write_image_result(ctx, args, paths, history, result_graph, result_input_records):
    """驗證圖片輸出並寫 --result-json manifest。"""
    flux2_task = args.task in tasks.flux2.TASKS
    result_warnings = []
    try:
        expected_dimensions = _image_results.graph_output_dimensions(result_graph)
        result_outputs = _image_results.validate_png_outputs(
            paths,
            expected_dimensions=(None if flux2_task else expected_dimensions),
            require_alpha=(args.task == "layer_split" or args.task == "icon_asset"
                           or bool(getattr(args, "remove_bg", False))),
            require_transparency=(args.task == "icon_asset"
                                  or bool(getattr(args, "remove_bg", False))),
        )
        if flux2_task and expected_dimensions:
            for output in result_outputs:
                if (output["width"], output["height"]) != (
                        expected_dimensions["width"], expected_dimensions["height"]):
                    result_warnings.append(
                        "FLUX.2 output dimensions differ from graph request: "
                        f"requested={expected_dimensions['width']}x{expected_dimensions['height']}, "
                        f"actual={output['width']}x{output['height']}"
                    )
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    selected_backend = "flux2" if flux2_task else "comfyui"
    manifest = _image_results.make_manifest(
        task=args.task,
        profile_id=None if selected_backend == "flux2" else ctx.active_image_profile,
        backend=selected_backend,
        prompt_id=history.get("_prompt_id") if isinstance(history, dict) else None,
        graph=result_graph,
        inputs=result_input_records,
        outputs=result_outputs,
        args=args,
        technical_warnings=result_warnings,
    )
    try:
        _image_results.write_manifest_atomic(args.result_json, manifest)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


def default_manifest_path(paths):
    """未指定 --result-json 時的預設 manifest 路徑:<第一個 PNG 輸出>.result.json 同資料夾。"""
    pngs = [p for p in paths if str(p).lower().endswith(".png")]
    if not pngs:
        return None
    base = os.path.splitext(os.path.abspath(pngs[0]))[0]
    return base + ".result.json"


def _write_default_image_result(ctx, args, paths, history, result_graph, result_input_records):
    """預設一律寫技術 manifest;盡力而為,失敗只在 stderr 警告,不影響生成結果與 stdout。"""
    dest = default_manifest_path(paths)
    if dest is None or result_input_records is None:
        return
    if os.path.lexists(dest):
        print(f"[manifest] 略過,已存在: {dest}", file=sys.stderr)
        return
    previous = getattr(args, "result_json", None)
    args.result_json = dest
    try:
        _write_image_result(ctx, args, paths, history, result_graph, result_input_records)
    except SystemExit as exc:
        print(f"[manifest] 未寫入預設技術 manifest: {exc}", file=sys.stderr)
    finally:
        args.result_json = previous


def _verify_video_output(ctx, args, plan, path, history, video_started, video_prompt, video_negative):
    """影片輸出契約驗證、sidecar 與(選用)抽幀。"""
    elapsed = time.monotonic() - video_started if video_started else None
    try:
        metadata = report_video_output(
            path, task=args.task, backend=args.backend,
            elapsed_seconds=elapsed, expected_contract=plan.contract,
            continuity_refs=plan.continuity_refs,
        )
    except VideoContractError as exc:
        # Persist the decoded evidence even for a failed contract so
        # operators can diagnose a bad render without treating it as success.
        write_video_sidecar(
            path, args.task, args.backend, args.seed, video_prompt, video_negative,
            plan.inputs, ctx.active_video_config, plan.contract,
            exc.metadata or {"validation": {"status": "fail", "errors": exc.errors}},
            prompt_id=history.get("_prompt_id") if isinstance(history, dict) else None,
            elapsed_seconds=elapsed, warnings=exc.warnings,
        )
        raise
    write_video_sidecar(
        path, args.task, args.backend, args.seed, video_prompt, video_negative,
        plan.inputs, ctx.active_video_config, plan.contract, metadata,
        prompt_id=history.get("_prompt_id") if isinstance(history, dict) else None,
        elapsed_seconds=elapsed,
    )
    if getattr(args, "extract_frames", False):
        frame_paths, frame_dir = extract_video_frames(
            path, getattr(args, "output_dir", None)
        )
        if len(frame_paths) != metadata["frames"]:
            raise RuntimeError(
                f"抽幀數量與影片不一致: video={metadata['frames']}, "
                f"frames={len(frame_paths)}, dir={frame_dir}"
            )
        print(f"[幀驗證] task={args.task} backend={args.backend} frames={len(frame_paths)} dir={frame_dir}")


def run(argv=None, context=None):
    """CLI 主流程。``context`` 可由測試/嵌入端傳入;預設用這台機器的 device_config.json。"""
    ctx = context if context is not None else RunContext.default()
    # A process may invoke run() more than once in tests or an embedding. Do
    # not let a previous machine config leak into a later task.
    ctx.active_video_config = None
    ctx.active_image_profile = None
    ap = build_parser()

    args = ap.parse_args(argv)
    if getattr(args, "prompt", None) is not None:
        # Keep the user's actual CLI text even when --rating later decorates the
        # effective conditioning prompt for the graph.
        args.requested_prompt = args.prompt
    try:
        validate_cli_args(args)
        if getattr(args, "result_json", None) is not None:
            if args.task not in IMAGE_GRAPH_TASKS:
                raise ValueError("--result-json 只支援圖片 task；影片與本機影片工具不支援")
            args.result_json = _image_results.validate_manifest_path(args.result_json)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    except FileExistsError as exc:
        raise SystemExit(str(exc)) from exc

    try:
        capabilities, capabilities_source = None, None
        if args.task in IMAGE_PROFILE_TASKS and not getattr(args, "profile_id", None):
            capabilities, capabilities_source = load_image_capabilities(
                getattr(args, "config_path", None), getattr(args, "image_config_path", None),
            )
        ctx.active_image_profile = resolve_image_profile(
            args.task, ctx.device, getattr(args, "profile_id", None), capabilities, capabilities_source,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    sync_image_runtime(ctx)
    # 只在 sidecar 存在且過期時印一行 stderr 提醒;不阻擋、不影響結束碼。
    _fingerprint.reminder_if_stale(os.path.dirname(os.path.abspath(DEVICE_CONFIG_PATH)))

    style_checkpoint = _resolve_style_checkpoint(ctx, args)

    validate_task_capabilities(ctx, args)
    # video_concat/video_composite 只在本機用 PyAV(+numpy)組裝既有影片，不會上傳、排程或
    # 下載 ComfyUI output；因此不能因為共用 parser 就強迫它們先解析 ComfyUI URL。
    comfy_url = None
    if args.task not in tasks.LOCAL_TASKS:
        comfy_url = resolve_comfy_url(
            getattr(args, "comfy_url", None), getattr(args, "config_path", None),
            default_url=ctx.comfy_url,
        )
    request_timeout = min(DEFAULT_HTTP_TIMEOUT, float(args.timeout))

    try:
        tasks.preflight(args, comfy_url, request_timeout)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    if args.task in tasks.VIDEO_TASKS:
        try:
            args.backend = configure_video_capability(
                ctx, args.task,
                requested_backend=getattr(args, "backend", None),
                runtime_config_path=getattr(args, "config_path", None),
                video_config_path=getattr(args, "video_config_path", None),
                comfy_url=comfy_url,
                request_timeout=request_timeout,
                control_type=getattr(args, "control_type", None),
            )
        except (RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc

    # Resolve randomness exactly once before any video graph is built. Every
    # builder receives this integer, and the same value is persisted in the
    # output sidecar for reproducibility/resume checks.
    if args.task in tasks.VIDEO_TASKS:
        args.seed = seed_or_random(getattr(args, "seed", None))

    video_started = (
        time.monotonic()
        if args.task in tasks.VIDEO_TASKS or args.task in tasks.LOCAL_TASKS
        else None
    )
    plan = None
    video_prompt = getattr(args, "prompt", "")
    video_negative = getattr(args, "negative", None)
    result_graph = None
    result_input_records = None

    def upload(path):
        return upload_image(path, comfy_url=comfy_url, request_timeout=request_timeout)

    if args.task in tasks.IMAGE_TASKS:
        try:
            result_input_records = _image_result_inputs(args)
        except SystemExit:
            if getattr(args, "result_json", None):
                raise
            result_input_records = None  # 預設 manifest 為盡力而為,不擋生成
        if args.task in IMAGE_PROFILE_TASKS:
            try:
                tasks.preflight_image_task(ctx, args, style_checkpoint, comfy_url, request_timeout=request_timeout)
            except RuntimeError as exc:
                raise SystemExit(str(exc)) from exc
        prompt, out_id = tasks.build_image_task_graph(ctx, args, style_checkpoint, upload)
        result_graph = prompt
    elif args.task in tasks.VIDEO_TASKS:
        plan = tasks.owner(args.task).prepare(ctx, args, upload)
        prompt, out_id = plan.graph, plan.out_id
        if plan.prompt is not None:
            video_prompt = plan.prompt
    elif args.task in tasks.LOCAL_TASKS:
        tasks.owner(args.task).run_local(args, video_started)
        return
    else:
        raise SystemExit(f"未知 task: {args.task}")

    if plan is not None:
        if plan.contract is None or plan.prefix is None:
            raise RuntimeError(f"影片 task {args.task} 沒有建立輸出契約或安全命名")
        if args.resume:
            out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
            candidate = _find_named_video_output(out_dir, plan.prefix)
            if candidate is None:
                raise SystemExit(
                    f"--resume 找不到唯一的 {plan.prefix!r} mp4 + sidecar；"
                    "不確定狀態不會猜測或重新送出工作"
                )
            try:
                metadata = resume_video_output(
                    candidate, args.task, args.backend, args.seed, plan.inputs,
                    ctx.active_video_config, plan.contract,
                )
            except (RuntimeError, VideoContractError) as exc:
                raise SystemExit(str(exc)) from exc
            print(f"[恢復] {candidate}")
            return

    target_output_id = None
    if args.task == "icon_asset" or getattr(args, "remove_bg", False):
        target_output_id = attach_bg_removal(prompt, out_id)

    print(f"[送出] task={args.task}")
    try:
        history = submit_and_wait(prompt, timeout=args.timeout, comfy_url=comfy_url)
    except VideoTimeoutError as exc:
        if plan is not None:
            out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
            prefix = plan.prefix or video_filename_prefix(args.task)
            write_video_timeout_record(
                out_dir, prefix, args.task, getattr(args, "backend", None),
                getattr(args, "seed", None), video_prompt, video_negative,
                plan.inputs, ctx.active_video_config, plan.contract, exc,
            )
        raise
    paths = download_outputs(
        history,
        output_dir=getattr(args, "output_dir", None),
        node_ids=[target_output_id] if target_output_id else None,
        comfy_url=comfy_url,
        request_timeout=request_timeout,
        allow_overwrite=(getattr(args, "overwrite", False) if plan is not None else True),
    )
    if getattr(args, "result_json", None):
        _write_image_result(ctx, args, paths, history, result_graph, result_input_records)
    elif args.task in tasks.IMAGE_TASKS:
        _write_default_image_result(ctx, args, paths, history, result_graph, result_input_records)
    if plan is not None:
        video_paths = [path for path in paths if path.lower().endswith(".mp4")]
        if not video_paths:
            raise RuntimeError(f"影片 task {args.task} 沒有產生 mp4 output，已拒絕把錯誤輸出當成成功")
    for p in paths:
        print(f"[完成] {p}")
        if p.lower().endswith(".mp4") and plan is not None:
            _verify_video_output(ctx, args, plan, p, history, video_started, video_prompt, video_negative)
