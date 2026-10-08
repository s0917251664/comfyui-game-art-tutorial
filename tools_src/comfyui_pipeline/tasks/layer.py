"""圖層拆分 task:layer_split(依遮罩從定稿圖切出單一圖層,不重新生成)。"""
from .. import image_from_template

TASKS = ("layer_split",)


def _add_layer_split(sub, parents):
    p_layer = sub.add_parser(
        "layer_split",
        help="把一張已定稿的完成圖依遮罩切出單一圖層(不重新生成內容,純粹裁切透明度)——用於複合式 UI 元件想事後拆出幾個大塊可疊放區域,拆一層呼叫一次",
        parents=[parents["common"]],
    )
    p_layer.add_argument("--image", required=True, help="來源圖路徑(已定稿的完成圖)")
    p_layer.add_argument("--mask", required=True, help="這一層的遮罩圖路徑(同 inpaint 慣例,需帶 alpha 通道,要保留進這一層的區域 alpha=0)")
    p_layer.add_argument("--layer-name", required=True, help="這一層的名稱,用來組輸出檔名前綴(例如 border、center_hub)")


_ADDERS = {
    "layer_split": _add_layer_split,
}


def add_parser(sub, parents, task):
    _ADDERS[task](sub, parents)


def build_graph(ctx, args, style_checkpoint, upload):
    """組圖片 task 的 graph;``upload`` 回傳 ComfyUI 端檔名。

    不分家族，一律走 template。找不到 template 就停止，不改走 builder。
    """
    if args.task != "layer_split":
        raise ValueError(f"不是這個模組的圖片 task: {args.task}")
    return image_from_template.graph_from_template(ctx, args, style_checkpoint, upload)
