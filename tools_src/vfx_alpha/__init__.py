"""VFX alpha 套件。CLI 與對外名稱在 ``vfx_alpha_tools``。"""
from .media import (
    file_record, new_directory, read_frames, read_webm_alpha, save_json, sprite_sheet,
    write_apng, write_sequence, write_webm_alpha,
)
from .pixel import birefnet_alpha, chroma_alpha, luma_alpha, masked_hue_rotate, over, parse_hex
from .qa import (
    DARK_BG, EDGE_HIGH, EDGE_LOW, LIGHT_BG, VISIBLE, alpha_metrics, comparison_board,
    frame_difference, loop_metrics, outside_mask_drift, subject_roi,
)
from .mask import (
    SEGMENT_MAX_WIDTH, SEGMENT_MIN_WIDTH, editor_mask_to_l, gray_mask_array, green_screen,
    mask_composite, mask_overlay_strip, prop_paste, read_masks, sam_to_edit_mask,
    segment_plan, working_size,
)

__all__ = [
    "DARK_BG", "EDGE_HIGH", "EDGE_LOW", "LIGHT_BG", "SEGMENT_MAX_WIDTH", "SEGMENT_MIN_WIDTH",
    "VISIBLE", "alpha_metrics", "birefnet_alpha", "chroma_alpha", "comparison_board",
    "editor_mask_to_l", "file_record", "frame_difference", "gray_mask_array", "green_screen",
    "loop_metrics", "luma_alpha", "mask_composite", "mask_overlay_strip", "masked_hue_rotate",
    "new_directory", "outside_mask_drift", "over", "parse_hex", "prop_paste", "read_frames",
    "read_masks", "read_webm_alpha", "sam_to_edit_mask", "save_json", "segment_plan",
    "sprite_sheet", "subject_roi", "working_size", "write_apng", "write_sequence",
    "write_webm_alpha",
]
