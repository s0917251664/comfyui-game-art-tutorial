"""video_inpaint 的本機媒體處理(薄轉接)。

實作在 PR 3.3 搬到 ``comfyui_pipeline/runner/vace_media.py``,讓 template runner 的
``vace_work_area``／``paste_back``／``qa_outside_mask_unchanged`` 步驟和 ``generate.py video_inpaint``
共用同一份程式。這裡只重新匯出原本的名稱,行為不變;新程式請直接用 ``runner.vace_media``。
"""
from .runner.vace_media import (  # noqa: F401 - 重新匯出給既有呼叫端
    ALIGN, MIN_SIDE, _fit_span, _gray_mask, _np, build_work_clips, compute_crop, encode_mp4, grow_masks,
    paste_back, paste_weight, processing_size, read_masks, read_video_frames, validate_source, vace_length,
    write_composited, write_lossless_video,
)
