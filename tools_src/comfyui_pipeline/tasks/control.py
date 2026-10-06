"""角色/姿勢控制圖片 task:character_action(角色參考 + 姿勢)、pose_only(只控姿勢)、style_lock(只鎖角色/風格)。"""
from .. import image_runtime
from ..image_capabilities import validate_controlnet_union_capability
from ..image_graphs import validate_unit_interval
from ._common import validate_explore_args

TASKS = ("character_action", "pose_only", "style_lock")


def _add_character_action(sub, parents):
    p_char = sub.add_parser("character_action", help="角色動作圖(角色參考圖 + 姿勢線稿)", parents=[parents["batch_lora"]])
    p_char.add_argument("--prompt", required=True)
    p_char.add_argument("--character-ref", required=True, help="角色參考圖路徑")
    p_char.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_char.add_argument("--ip-weight", type=float, default=0.8)
    p_char.add_argument("--pose-strength", type=float, default=1.0)
    p_char.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="姿勢/構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_char.add_argument("--width", type=int, default=None)
    p_char.add_argument("--height", type=int, default=None)
    p_char.add_argument("--remove-bg", action="store_true")


def _add_pose_only(sub, parents):
    p_pose = sub.add_parser("pose_only", help="單獨用姿勢/線稿控制構圖,不鎖角色一致性", parents=[parents["batch_lora"]])
    p_pose.add_argument("--prompt", required=True)
    p_pose.add_argument("--pose-ref", required=True, help="姿勢/線稿參考圖路徑")
    p_pose.add_argument("--pose-strength", type=float, default=1.0)
    p_pose.add_argument("--control-type", choices=["canny", "pose", "depth"], default="canny",
                         help="構圖控制來源:canny=線稿邊緣(預設),pose=骨架姿勢,depth=深度圖")
    p_pose.add_argument(
        "--control-backend", choices=["verified", "union"], default="verified",
        help="ControlNet 後端；verified=既有三顆正式模型(預設)，union=實驗性 xinsir ProMax A/B",
    )
    p_pose.add_argument("--width", type=int, default=None)
    p_pose.add_argument("--height", type=int, default=None)
    p_pose.add_argument("--remove-bg", action="store_true")


def _add_style_lock(sub, parents):
    p_style = sub.add_parser("style_lock", help="單獨鎖角色/風格一致性,姿勢隨意(不需要姿勢參考圖)", parents=[parents["batch_lora"]])
    p_style.add_argument("--prompt", required=True)
    p_style.add_argument("--character-ref", required=True, help="角色/風格參考圖路徑")
    p_style.add_argument("--ip-weight", type=float, default=0.8)
    p_style.add_argument("--width", type=int, default=None)
    p_style.add_argument("--height", type=int, default=None)
    p_style.add_argument("--remove-bg", action="store_true")


_ADDERS = {
    "character_action": _add_character_action,
    "pose_only": _add_pose_only,
    "style_lock": _add_style_lock,
}


def add_parser(sub, parents, task):
    _ADDERS[task](sub, parents)


def validate(args):
    validate_explore_args(args)
    if args.task in ("character_action", "style_lock"):
        validate_unit_interval(args.ip_weight, "ip_weight")
    if args.task in ("character_action", "pose_only"):
        validate_unit_interval(args.pose_strength, "pose_strength")


def check_capabilities(ctx, args):
    if args.task == "character_action":
        image_runtime.require_sdxl_capability(ctx, "character_action (ControlNet/IPAdapter)")
    elif args.task == "pose_only":
        image_runtime.require_sdxl_capability(ctx, "pose_only (ControlNet)")
    elif args.task == "style_lock":
        image_runtime.require_sdxl_capability(ctx, "style_lock (IPAdapter)")


def preflight(args, comfy_url, request_timeout):
    """送出前確認實驗性 ControlNet Union 後端的 node/模型都在。"""
    if args.task == "pose_only" and args.control_backend == "union":
        validate_controlnet_union_capability(comfy_url, request_timeout=request_timeout)


def build_graph(ctx, args, style_checkpoint, upload):
    """組圖片 task 的 graph;``upload`` 回傳 ComfyUI 端檔名。"""
    if args.task == "character_action":
        char_fn = upload(args.character_ref)
        pose_fn = upload(args.pose_ref)
        prompt, out_id = image_runtime.build_character_action(ctx,
            args.prompt, char_fn, pose_fn, args.negative,
            width=args.width, height=args.height,
            seed=args.seed, ip_weight=args.ip_weight, pose_strength=args.pose_strength,
            batch_size=args.batch, control_type=args.control_type,
            lora_name=args.lora, lora_strength=args.lora_strength, checkpoint=style_checkpoint,
        )
    elif args.task == "pose_only":
        pose_fn = upload(args.pose_ref)
        prompt, out_id = image_runtime.build_pose_only(ctx, args.prompt, pose_fn, args.negative,
                                          width=args.width, height=args.height,
                                          seed=args.seed, pose_strength=args.pose_strength,
                                          batch_size=args.batch, control_type=args.control_type,
                                          lora_name=args.lora, lora_strength=args.lora_strength,
                                          checkpoint=style_checkpoint,
                                          control_backend=args.control_backend)
    elif args.task == "style_lock":
        char_fn = upload(args.character_ref)
        prompt, out_id = image_runtime.build_style_lock(ctx, args.prompt, char_fn, args.negative,
                                           width=args.width, height=args.height,
                                           seed=args.seed, ip_weight=args.ip_weight,
                                           batch_size=args.batch,
                                           lora_name=args.lora, lora_strength=args.lora_strength,
                                           checkpoint=style_checkpoint)
    else:
        raise ValueError(f"不是這個模組的圖片 task: {args.task}")
    return prompt, out_id
