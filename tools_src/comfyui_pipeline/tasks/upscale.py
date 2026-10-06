"""放大精修圖片 task:upscale(放大模型 + 二次取樣補細節)。"""
from .. import image_runtime
from ..image_graphs import validate_scale, validate_unit_interval

TASKS = ("upscale",)


def _add_upscale(sub, parents):
    p_upscale = sub.add_parser("upscale", help="放大精修(放大模型 + 二次取樣補細節,不是單純拉大)", parents=[parents["prompt"]])
    p_upscale.add_argument("--prompt", required=True, help="用來引導二次取樣補細節,通常沿用原本生成這張圖時的 prompt")
    p_upscale.add_argument("--image", required=True, help="來源圖路徑(要放大的圖)")
    p_upscale.add_argument("--scale", type=float, default=2.0, help="相對原圖的放大倍率(預設 2 倍),最高 4 倍")
    p_upscale.add_argument("--denoise", type=float, default=0.4, help="二次取樣補細節的強度:太低細節補不夠,太高會偏離原圖構圖")


_ADDERS = {
    "upscale": _add_upscale,
}


def add_parser(sub, parents, task):
    _ADDERS[task](sub, parents)


def validate(args):
    validate_unit_interval(args.denoise, "denoise")
    validate_scale(args.scale)


def build_graph(ctx, args, style_checkpoint, upload):
    """組圖片 task 的 graph;``upload`` 回傳 ComfyUI 端檔名。"""
    if args.task == "upscale":
        img_fn = upload(args.image)
        prompt, out_id = image_runtime.build_upscale(ctx, args.prompt, img_fn, args.negative,
                                        scale=args.scale, denoise=args.denoise, seed=args.seed,
                                        checkpoint=style_checkpoint)
    else:
        raise ValueError(f"不是這個模組的圖片 task: {args.task}")
    return prompt, out_id
