"""基本圖片 task:concept(文生圖)、icon_asset(去背小圖示)、refine(圖生圖精修)。"""
from .. import image_from_template, image_runtime
from ..image_graphs import validate_unit_interval
from ._common import validate_explore_args

TASKS = ("concept", "icon_asset", "refine")


def _add_concept(sub, parents):
    p_concept = sub.add_parser("concept", help="概念圖(純文字)", parents=[parents["batch_lora"]])
    p_concept.add_argument("--prompt", required=True)
    p_concept.add_argument("--width", type=int, default=None)
    p_concept.add_argument("--height", type=int, default=None)
    p_concept.add_argument("--remove-bg", action="store_true")


def _add_icon_asset(sub, parents):
    p_icon = sub.add_parser("icon_asset", help="單一小型 UI 圖示/物件素材(不是整個 UI 畫面),永遠去背輸出透明背景", parents=[parents["batch_lora"]])
    p_icon.add_argument("--prompt", required=True)
    p_icon.add_argument("--width", type=int, default=None)
    p_icon.add_argument("--height", type=int, default=None)
    p_icon.add_argument("--structure-ref", help="這個圖示的結構/色塊配置已經有明確答案、不該讓 AI 自己瞎猜時用(例如放射狀精準等分):給一張範本圖路徑,用 img2img + Canny ControlNet 把結構跟顏色配置都鎖住,SDXL 只負責疊材質/光澤;不給就跟以前一樣純靠文字描述。範本圖從哪來見 docs/knowledge/art/structure-ref.md")
    p_icon.add_argument("--appearance-ref", help="外觀參考圖路徑(選用,例如使用者提供的一張成品圖,想讓畫面材質/質感偏向那張圖)——用 IPAdapter,不給就純靠文字描述外觀,原則同 guided_inpaint 的 --appearance-ref")
    p_icon.add_argument("--appearance-weight", type=float, default=0.8, help="外觀參考圖的貼合強度,原則同 --ip-weight")


def _add_refine(sub, parents):
    p_refine = sub.add_parser("refine", help="圖生圖:草稿精緻化 / 材質顏色變體(保留原圖構圖)", parents=[parents["prompt"]])
    p_refine.add_argument("--prompt", required=True)
    p_refine.add_argument("--image", required=True, help="來源圖路徑(草稿或要換材質的圖)")
    p_refine.add_argument("--denoise", type=float, default=0.6, help="0.3~0.4 大致保留構圖只上色;0.6~0.7 細節大幅改變;0.9+ 幾乎重畫")
    p_refine.add_argument("--remove-bg", action="store_true")


_ADDERS = {
    "concept": _add_concept,
    "icon_asset": _add_icon_asset,
    "refine": _add_refine,
}


def add_parser(sub, parents, task):
    _ADDERS[task](sub, parents)


def validate(args):
    if args.task in ("concept", "icon_asset"):
        validate_explore_args(args)
    if args.task == "icon_asset":
        validate_unit_interval(args.appearance_weight, "appearance_weight")
    if args.task == "refine":
        validate_unit_interval(args.denoise, "denoise")


def check_capabilities(ctx, args):
    if args.task == "icon_asset":
        if args.structure_ref:
            image_runtime.require_sdxl_capability(ctx, "icon_asset 的 structure-ref/ControlNet")
        if args.appearance_ref:
            image_runtime.require_sdxl_capability(ctx, "icon_asset 的 appearance-ref/IPAdapter")


def build_graph(ctx, args, style_checkpoint, upload):
    """組圖片 task 的 graph;``upload`` 回傳 ComfyUI 端檔名。

    sdxl 走 template。sd15 的 template 目錄不存在時沿用下面的 builder，graph 不變。
    """
    built = image_from_template.graph_from_template(ctx, args, style_checkpoint, upload)
    if built is not None:
        return built
    if args.task == "concept":
        prompt, out_id = image_runtime.build_concept(ctx, args.prompt, args.negative, args.width, args.height, args.seed,
                                        batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
                                        checkpoint=style_checkpoint)
    elif args.task == "icon_asset":
        structure_fn = upload(args.structure_ref) if args.structure_ref else None
        appearance_fn = upload(args.appearance_ref) if args.appearance_ref else None
        prompt, out_id = image_runtime.build_icon_asset(ctx, args.prompt, args.negative, args.width, args.height, args.seed,
                                           batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
                                           structure_ref_filename=structure_fn, checkpoint=style_checkpoint,
                                           appearance_ref_filename=appearance_fn, appearance_weight=args.appearance_weight)
    elif args.task == "refine":
        img_fn = upload(args.image)
        prompt, out_id = image_runtime.build_refine(ctx, args.prompt, img_fn, args.negative,
                                       denoise=args.denoise, seed=args.seed, checkpoint=style_checkpoint)
    else:
        raise ValueError(f"不是這個模組的圖片 task: {args.task}")
    return prompt, out_id
