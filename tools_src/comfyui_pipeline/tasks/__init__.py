"""generate.py 的 task 註冊表:一個模組負責一組相關的 task。

每個 task 模組提供(``validate``/``check_capabilities``/``preflight`` 可省略):

- ``TASKS``:這個模組負責的 task 名稱。
- ``add_parser(sub, parents, task)``:註冊該 task 的子命令與參數。
- ``validate(args)``:CLI 參數範圍驗證,失敗丟 ValueError。
- ``check_capabilities(args)``:依機器能力(SDXL 家族等)擋下不支援的組合,失敗丟 RuntimeError。
- ``preflight(args, comfy_url, request_timeout)``:送出前查 ComfyUI node/模型,失敗丟 RuntimeError。
- 圖片 task:``build_graph(args, style_checkpoint, upload)`` 回傳 ``(graph, output_node_id)``。
- ComfyUI 影片 task:``prepare(args, upload)`` 回傳 ``_common.VideoPlan``。
- 本機影片 task:``run_local(args, video_started)`` 自己跑完整個流程。

新增 task:加一個模組(或放進既有模組)、列進 ``MODULES`` 與 ``TASK_ORDER``;
``generate.py`` 與 ``cli.py`` 不用改。
"""
from . import control, flux2, image_basic, inpaint, layer, upscale, video, video_local

MODULES = (image_basic, flux2, control, inpaint, upscale, layer, video, video_local)

# CLI 子命令的順序(--help 的列表順序由這裡決定,跟模組分組無關)。
TASK_ORDER = (
    "concept", "flux2_concept", "flux2_edit", "icon_asset", "character_action", "inpaint",
    "guided_inpaint", "pose_only", "style_lock", "refine", "upscale", "layer_split",
    "img2video", "fx_loop", "transition", "clip_extend", "video_concat", "video_composite",
    "camera_move", "character_video", "pose_drive",
)

_OWNERS = {}
for _module in MODULES:
    for _task in _module.TASKS:
        assert _task not in _OWNERS, f"task {_task} 被兩個模組註冊"
        _OWNERS[_task] = _module
assert set(_OWNERS) == set(TASK_ORDER), "TASK_ORDER 與各模組 TASKS 不一致"

IMAGE_TASKS = frozenset(task for task, module in _OWNERS.items() if hasattr(module, "build_graph"))
VIDEO_TASKS = frozenset(task for task, module in _OWNERS.items() if hasattr(module, "prepare"))
LOCAL_TASKS = frozenset(task for task, module in _OWNERS.items() if hasattr(module, "run_local"))


def owner(task):
    """回傳負責這個 task 的模組;未知 task 回傳 None。"""
    return _OWNERS.get(task)


def register_parsers(sub, parents):
    for task in TASK_ORDER:
        _OWNERS[task].add_parser(sub, parents, task)


def validate_args(args):
    module = _OWNERS.get(args.task)
    if module is not None and hasattr(module, "validate"):
        module.validate(args)


def check_capabilities(args):
    module = _OWNERS.get(args.task)
    if module is not None and hasattr(module, "check_capabilities"):
        module.check_capabilities(args)


def preflight(args, comfy_url, request_timeout):
    module = _OWNERS.get(args.task)
    if module is not None and hasattr(module, "preflight"):
        module.preflight(args, comfy_url, request_timeout)


def build_image_task_graph(args, style_checkpoint, upload):
    """組圖片 task 的 graph;``upload`` 回傳 ComfyUI 端檔名。

    main() 用真正的上傳函式呼叫;preflight_image_task() 用佔位檔名先空組一次,
    讓送出前檢查與實際送出的 graph 來自同一份 dispatch,不會各自維護一套規則。
    """
    if args.task not in IMAGE_TASKS:
        raise ValueError(f"不是圖片 graph task: {args.task}")
    return _OWNERS[args.task].build_graph(args, style_checkpoint, upload)
