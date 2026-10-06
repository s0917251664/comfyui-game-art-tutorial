"""局部重繪圖片 task:inpaint、guided_inpaint(可選結構鎖定/外觀參考)。"""
from .. import image_runtime
from ..image_graphs import validate_unit_interval

TASKS = ("inpaint", "guided_inpaint")


def _add_inpaint(sub, parents):
    p_inpaint = sub.add_parser("inpaint", help="局部調整(需要來源圖 + 遮罩圖)", parents=[parents["prompt"]])
    p_inpaint.add_argument("--prompt", required=True)
    p_inpaint.add_argument("--image", required=True, help="來源圖路徑")
    p_inpaint.add_argument("--mask", required=True, help="遮罩圖路徑(需帶 alpha 通道,要重畫的區域 alpha=0/透明,其餘 alpha=255/不透明——用 ComfyUI MaskEditor 存的檔案格式一定對)")
    p_inpaint.add_argument("--denoise", type=float, default=1.0)


def _add_guided_inpaint(sub, parents):
    p_guided = sub.add_parser(
        "guided_inpaint",
        help="局部重繪 + 結構鎖定/外觀參考圖(遮罩範圍內可選擇鎖住結構、可選擇用一張圖決定外觀,而不是只能靠文字描述;用於換武器/道具但要保持握姿、套用美術自畫材質紋理這類需求)",
        parents=[parents["prompt"]],
    )
    p_guided.add_argument("--prompt", required=True)
    p_guided.add_argument("--image", required=True, help="來源圖路徑")
    p_guided.add_argument("--mask", required=True, help="遮罩圖路徑(同 inpaint,需帶 alpha 通道,要重畫的區域 alpha=0)")
    p_guided.add_argument("--control-ref", help="結構引導來源圖路徑,不給就用 --image 本身(從同一張圖抽取結構);沒給 --control-type 的話這個參數沒作用")
    p_guided.add_argument("--control-type", choices=["canny", "pose", "depth"],
                           help="要鎖定的結構類型(選用,不給就不鎖結構):pose=骨架關節(手部/肢體動作類需求),canny=輪廓邊緣、depth=立體起伏(材質/紋路類需求)")
    p_guided.add_argument("--control-strength", type=float, default=1.0)
    p_guided.add_argument("--appearance-ref", help="外觀參考圖路徑(選用,例如美術自己畫的材質/紋理圖)——不給就純靠文字描述外觀。建議用乾淨的材質特寫,不要整張場景圖,不然背景/光影會一起被帶進來")
    p_guided.add_argument("--appearance-weight", type=float, default=0.8, help="外觀參考圖的貼合強度,原則同 --ip-weight")
    p_guided.add_argument("--denoise", type=float, default=1.0)


_ADDERS = {
    "inpaint": _add_inpaint,
    "guided_inpaint": _add_guided_inpaint,
}


def add_parser(sub, parents, task):
    _ADDERS[task](sub, parents)


def validate(args):
    validate_unit_interval(args.denoise, "denoise")
    if args.task == "guided_inpaint":
        validate_unit_interval(args.control_strength, "control_strength")
        validate_unit_interval(args.appearance_weight, "appearance_weight")


def check_capabilities(ctx, args):
    if args.task == "guided_inpaint":
        if args.control_type:
            image_runtime.require_sdxl_capability(ctx, "guided_inpaint 的 ControlNet")
        if args.appearance_ref:
            image_runtime.require_sdxl_capability(ctx, "guided_inpaint 的 IPAdapter")


def build_graph(ctx, args, style_checkpoint, upload):
    """組圖片 task 的 graph;``upload`` 回傳 ComfyUI 端檔名。"""
    if args.task == "inpaint":
        img_fn = upload(args.image)
        mask_fn = upload(args.mask)
        prompt, out_id = image_runtime.build_inpaint(ctx, args.prompt, img_fn, mask_fn, args.negative,
                                        denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint)
    elif args.task == "guided_inpaint":
        img_fn = upload(args.image)
        mask_fn = upload(args.mask)
        control_fn = None
        if args.control_type:
            control_fn = upload(args.control_ref) if args.control_ref else img_fn
        appearance_fn = upload(args.appearance_ref) if args.appearance_ref else None
        prompt, out_id = image_runtime.build_guided_inpaint(ctx,
            args.prompt, img_fn, mask_fn, args.negative,
            control_ref_filename=control_fn, control_type=args.control_type, control_strength=args.control_strength,
            appearance_ref_filename=appearance_fn, appearance_weight=args.appearance_weight,
            denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint,
        )
    else:
        raise ValueError(f"不是這個模組的圖片 task: {args.task}")
    return prompt, out_id
