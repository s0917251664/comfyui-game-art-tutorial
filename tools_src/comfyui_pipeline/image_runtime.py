"""圖片 builder 的 context 轉接層。

``image_graphs`` 的 builder 讀模組層級的 ``DEVICE`` / ``CKPT`` / ``ACTIVE_PROFILE_ID``(一份 940 行的 graph
模組,內部很多處直接讀);這裡的 wrapper 在每次呼叫前依 ``RunContext`` 把這三個值同步過去,
所以呼叫端只要明確傳 ctx,不必自己碰 image_graphs 的全域。這是剩下唯一的模組層級可變狀態,
且只在這個檔案寫入。
"""
from . import image_graphs as _image_graphs

_DEFAULT_CKPT = _image_graphs.CKPT


def sync_image_runtime(ctx):
    """把 ctx 的機器資料與選用設定檔同步給 image_graphs。"""
    _image_graphs.DEVICE = ctx.device
    _image_graphs.CKPT = ctx.device.get("checkpoint", _DEFAULT_CKPT)
    _image_graphs.ACTIVE_PROFILE_ID = ctx.active_image_profile


def require_sdxl_capability(ctx, *args, **kwargs):
    sync_image_runtime(ctx)
    return _image_graphs.require_sdxl_capability(*args, **kwargs)


def _image_builder(name):
    def call(ctx, *args, **kwargs):
        sync_image_runtime(ctx)
        return getattr(_image_graphs, name)(*args, **kwargs)
    call.__name__ = name
    return call


build_concept = _image_builder("build_concept")
build_icon_asset = _image_builder("build_icon_asset")
build_character_action = _image_builder("build_character_action")
build_inpaint = _image_builder("build_inpaint")
build_guided_inpaint = _image_builder("build_guided_inpaint")
build_pose_only = _image_builder("build_pose_only")
build_style_lock = _image_builder("build_style_lock")
build_refine = _image_builder("build_refine")
build_upscale = _image_builder("build_upscale")
build_layer_split = _image_builder("build_layer_split")
build_flux2_concept = _image_builder("build_flux2_concept")
build_flux2_edit = _image_builder("build_flux2_edit")
