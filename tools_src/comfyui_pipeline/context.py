"""一次執行(``cli.run``)的明確狀態,取代原本散在 generate 模組全域的可變值。

``RunContext`` 由 cli 建立並往下傳給 task / builder;每次 ``run()`` 都會重設
``active_image_profile`` 與 ``active_video_config``,不讓前一次的機器設定漏到下一次。
測試或嵌入端可自己建一個傳進 ``cli.run(argv, context=ctx)``。
"""
from dataclasses import dataclass
from typing import Optional

from . import image_graphs

# 匯入時從 device_config.json 載入的機器資料(image_graphs 載入時只讀一次);
# 之後 image_graphs.DEVICE 會被 image_runtime.sync_image_runtime 覆寫,所以這裡另外留住原始值。
_DEFAULT_DEVICE = image_graphs.DEVICE


@dataclass
class RunContext:
    # 機器資料(device_config.json 的內容,tier / checkpoint / default_width ...)。
    device: dict
    # 嵌入時的預設 ComfyUI URL(排在環境變數之後、--config 之前);CLI 用法留 None。
    comfy_url: Optional[str] = None
    # 本次選用的圖片模型設定檔 id;None = 沿用 device tier 對應。
    active_image_profile: Optional[str] = None
    # 本次選用的影片 capability config;由 configure_video_capability 設定。
    active_video_config: Optional[dict] = None

    @classmethod
    def default(cls):
        return cls(device=_DEFAULT_DEVICE)
