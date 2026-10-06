"""實驗性 FLUX.2 圖片 task:flux2_concept、flux2_edit。不走 SDXL 的 --style/--rating/LoRA,也不走模型設定檔。"""
from .. import image_runtime
from ..image_capabilities import validate_flux2_capability
from ..image_graphs import validate_flux2_dimensions

TASKS = ("flux2_concept", "flux2_edit")


def _add_flux2_concept(sub, parents):
    # Experimental FLUX.2 tasks are deliberately separate from the model parent:
    # --style/--rating/SDXL LoRA and negative prompts are not compatible with
    # this backend and must not appear to be supported by parser inheritance.
    p_flux2_concept = sub.add_parser(
        "flux2_concept",
        help="實驗性 FLUX.2 Klein 4B 蒸餾版概念圖(4 steps；不取代 SDXL concept)",
        parents=[parents["common"]],
    )
    p_flux2_concept.add_argument("--prompt", required=True)
    p_flux2_concept.add_argument("--width", type=int, default=1024)
    p_flux2_concept.add_argument("--height", type=int, default=1024)
    p_flux2_concept.add_argument("--seed", type=int)


def _add_flux2_edit(sub, parents):
    p_flux2_edit = sub.add_parser(
        "flux2_edit",
        help="實驗性 FLUX.2 Klein 4B base 單參考圖語意編輯(輸出約一百萬像素)",
        parents=[parents["common"]],
    )
    p_flux2_edit.add_argument("--prompt", required=True, help="要如何修改來源圖")
    p_flux2_edit.add_argument("--image", required=True, help="來源／參考圖路徑")
    p_flux2_edit.add_argument("--seed", type=int)


_ADDERS = {
    "flux2_concept": _add_flux2_concept,
    "flux2_edit": _add_flux2_edit,
}


def add_parser(sub, parents, task):
    _ADDERS[task](sub, parents)


def validate(args):
    if args.task == "flux2_concept":
        validate_flux2_dimensions(args.width, args.height)


def preflight(args, comfy_url, request_timeout):
    """送出前確認 ComfyUI 有 FLUX.2 需要的 node 與模型。"""
    validate_flux2_capability(args.task, comfy_url, request_timeout=request_timeout)


def build_graph(ctx, args, style_checkpoint, upload):
    """組圖片 task 的 graph;``upload`` 回傳 ComfyUI 端檔名。"""
    if args.task == "flux2_concept":
        prompt, out_id = image_runtime.build_flux2_concept(ctx,
            args.prompt, width=args.width, height=args.height, seed=args.seed,
        )
    elif args.task == "flux2_edit":
        img_fn = upload(args.image)
        prompt, out_id = image_runtime.build_flux2_edit(ctx, args.prompt, img_fn, seed=args.seed)
    else:
        raise ValueError(f"不是這個模組的圖片 task: {args.task}")
    return prompt, out_id
