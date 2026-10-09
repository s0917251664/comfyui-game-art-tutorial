"""圖片 task 的 context 轉接層。

``image_graphs`` 的參數解析讀模組層級的 ``DEVICE`` / ``CKPT`` / ``ACTIVE_PROFILE_ID``
（底模、預設解析度、取樣參數）;這裡在每次要用之前依 ``RunContext`` 把這三個值同步過去,
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
