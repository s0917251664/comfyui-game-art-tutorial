"""
穩定產圖核心腳本(不吃自然語言,只吃結構化參數)。

設計原則:
- 每個 task 對應一組鎖死大部分參數的 ComfyUI graph,只有明確列出的欄位可調
- 不靠 LLM 每次臨場組 JSON,參數集固定、行為可預期、可重複
- 上層(Skill/agent)的工作只是把自然語言整理成這裡要的結構化參數,不做生成邏輯本身

Usage:
    python generate.py --config local_config.json concept --prompt "a female game character concept art, fantasy armor" [--negative ...] [--seed N] [--width 1024] [--height 1024] [--remove-bg]
    python generate.py --config local_config.json flux2_concept --prompt "a readable game item concept" [--seed N] [--width 1024] [--height 1024]
    python generate.py --config local_config.json flux2_edit --prompt "turn the armor silver" --image path.png [--seed N]
    python generate.py --comfy-url http://127.0.0.1:8188 character_action --prompt "..." --character-ref path.png --pose-ref path.png [--pose-strength 1.0] [--remove-bg]
    python generate.py --config local_config.json inpaint --prompt "..." --image path.png --mask path.png [--denoise 1.0]
    python generate.py --config local_config.json img2video --image still.png --prompt "camera locked, idle motion" [--backend h3|wan] [--duration 2] [--timeout 1800]
    python generate.py --comfy-url http://127.0.0.1:8188 character_video --character-ref char.png --prompt "the same character running through a corridor" [--duration 2]
    python generate.py --config local_config.json camera_move --image still.png --camera zoom_in [--duration 2]
    python generate.py --config local_config.json pose_drive --image char.png --motion-ref motion.mp4 --prompt "the character performs the motion"
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
import mimetypes
import ntpath
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

try:
    from PIL import Image as PILImage, ImageDraw, ImageFilter
except ImportError:  # Pillow is only needed by the local template/mask helpers.
    PILImage = None
    ImageDraw = None
    ImageFilter = None

# The deployment copy can live outside this repository.  Do not infer a URL from
# the source tree; callers must provide one explicitly, through the CLI, an
# environment variable, an explicitly named config file, or this compatibility
# override when embedding the module.
COMFY_URL = None
ACTIVE_VIDEO_CONFIG = None  # 本次 main() 選用的影片 capability config;由 configure_video_capability 設定
from comfyui_pipeline import image_graphs as _image_graphs
from comfyui_pipeline import image_results as _image_results
from comfyui_pipeline import profiles as _profiles
from comfyui_pipeline import video_catalog as _video_catalog
from comfyui_pipeline import video_graphs as _video_graphs

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")
DEFAULT_NEGATIVE = _image_graphs.DEFAULT_NEGATIVE
DEVICE_CONFIG_PATH = _image_graphs.DEVICE_CONFIG_PATH
SDXL_TIERS = _image_graphs.SDXL_TIERS
_require_pillow = _image_graphs._require_pillow
validate_batch = _image_graphs.validate_batch
validate_dimensions = _image_graphs.validate_dimensions
validate_unit_interval = _image_graphs.validate_unit_interval
validate_lora_strength = _image_graphs.validate_lora_strength
validate_scale = _image_graphs.validate_scale
validate_flux2_dimensions = _image_graphs.validate_flux2_dimensions
CONTROLNET_MODELS = _image_graphs.CONTROLNET_MODELS
STYLE_CHECKPOINTS = _image_graphs.STYLE_CHECKPOINTS
RATING_TAGS = _image_graphs.RATING_TAGS
load_device_config = _image_graphs.load_device_config
DEVICE = _image_graphs.DEVICE
CKPT = _image_graphs.CKPT
UPSCALE_MODEL = _image_graphs.UPSCALE_MODEL

# 本次 main() 選用的圖片模型設定檔 id;None = 沿用 device_config.json 的 tier 對應。
ACTIVE_IMAGE_PROFILE = None


def _sync_image_runtime():
    """Keep legacy facade assignments visible to the extracted image module."""
    _image_graphs.DEVICE = DEVICE
    _image_graphs.CKPT = DEVICE.get("checkpoint", CKPT)
    _image_graphs.ACTIVE_PROFILE_ID = ACTIVE_IMAGE_PROFILE


def require_sdxl_capability(*args, **kwargs):
    _sync_image_runtime()
    return _image_graphs.require_sdxl_capability(*args, **kwargs)


def _image_builder(name):
    def call(*args, **kwargs):
        _sync_image_runtime()
        return getattr(_image_graphs, name)(*args, **kwargs)
    return call


build_control_preprocessor = _image_builder("build_control_preprocessor")
seed_or_random = _image_builder("seed_or_random")
model_clip_refs = _image_builder("model_clip_refs")
build_concept = _image_builder("build_concept")
build_wheel_segment_template = _image_builder("build_wheel_segment_template")
build_wheel_layer_masks = _image_builder("build_wheel_layer_masks")
build_icon_asset = _image_builder("build_icon_asset")
build_character_action = _image_builder("build_character_action")
build_inpaint = _image_builder("build_inpaint")
build_guided_inpaint = _image_builder("build_guided_inpaint")
build_pose_only = _image_builder("build_pose_only")
build_style_lock = _image_builder("build_style_lock")
build_refine = _image_builder("build_refine")
build_upscale = _image_builder("build_upscale")
build_layer_split = _image_builder("build_layer_split")
attach_bg_removal = _image_builder("attach_bg_removal")
build_flux2_concept = _image_builder("build_flux2_concept")
build_flux2_edit = _image_builder("build_flux2_edit")

CHARACTER_REF_MAX = _video_catalog.CHARACTER_REF_MAX
VIDEO_WAN_UNET = _video_catalog.VIDEO_WAN_UNET
VIDEO_WAN_FUN_UNET = _video_catalog.VIDEO_WAN_FUN_UNET
VIDEO_WAN_CLIP = _video_catalog.VIDEO_WAN_CLIP
VIDEO_WAN_VAE = _video_catalog.VIDEO_WAN_VAE
VIDEO_H3_UNET = _video_catalog.VIDEO_H3_UNET
VIDEO_H3_REF_UNET = _video_catalog.VIDEO_H3_REF_UNET
VIDEO_H3_CLIP = _video_catalog.VIDEO_H3_CLIP
VIDEO_H3_VAE = _video_catalog.VIDEO_H3_VAE
VIDEO_H3_AUDIO_VAE = _video_catalog.VIDEO_H3_AUDIO_VAE
VIDEO_MAX_SIDE = _video_catalog.VIDEO_MAX_SIDE
VIDEO_STEPS = _video_catalog.VIDEO_STEPS
VIDEO_FPS = _video_catalog.VIDEO_FPS
VIDEO_FPS_TOLERANCE = _video_catalog.VIDEO_FPS_TOLERANCE
VIDEO_DURATION_MIN = _video_catalog.VIDEO_DURATION_MIN
VIDEO_DURATION_MAX = _video_catalog.VIDEO_DURATION_MAX
DEFAULT_VIDEO_TIMEOUT = _video_catalog.DEFAULT_VIDEO_TIMEOUT
VIDEO_CAPABILITY_SCHEMA_VERSION = _video_catalog.VIDEO_CAPABILITY_SCHEMA_VERSION
VIDEO_SIDECAR_SCHEMA_VERSION = _video_catalog.VIDEO_SIDECAR_SCHEMA_VERSION
VIDEO_CONTRACT_SCHEMA_VERSION = _video_catalog.VIDEO_CONTRACT_SCHEMA_VERSION
VIDEO_DURATION_TOLERANCE = _video_catalog.VIDEO_DURATION_TOLERANCE
VIDEO_FRAME_TOLERANCE = _video_catalog.VIDEO_FRAME_TOLERANCE
VIDEO_SEAM_WARNING_THRESHOLD = _video_catalog.VIDEO_SEAM_WARNING_THRESHOLD
VIDEO_INPUT_MIN_DURATION = _video_catalog.VIDEO_INPUT_MIN_DURATION
VIDEO_AUDIO_DRIFT_TOLERANCE = _video_catalog.VIDEO_AUDIO_DRIFT_TOLERANCE
VIDEO_CAPABILITY_CONFIG_ENV_VARS = _video_catalog.VIDEO_CAPABILITY_CONFIG_ENV_VARS
VIDEO_CAPABILITY_CONFIG_FILENAME = _video_catalog.VIDEO_CAPABILITY_CONFIG_FILENAME
VIDEO_NEG_DEFAULT = _video_catalog.VIDEO_NEG_DEFAULT
VIDEO_LOOP_SUFFIX = _video_catalog.VIDEO_LOOP_SUFFIX
CAMERA_MOVES = _video_catalog.CAMERA_MOVES
CAMERA_STILL_SUFFIX = _video_catalog.CAMERA_STILL_SUFFIX
CAMERA_ZOOM = _video_catalog.CAMERA_ZOOM
CAMERA_PAN_CROP = _video_catalog.CAMERA_PAN_CROP
VIDEO_BACKEND_SPECS = _video_catalog.VIDEO_BACKEND_SPECS
VIDEO_BACKENDS = _video_catalog.VIDEO_BACKENDS
VIDEO_BACKEND_CAPS = _video_catalog.VIDEO_BACKEND_CAPS
VIDEO_TASK_CAPS = _video_catalog.VIDEO_TASK_CAPS
VIDEO_TASK_EXTRA_CAPS = _video_catalog.VIDEO_TASK_EXTRA_CAPS
VIDEO_CONTROL_NODES = _video_catalog.VIDEO_CONTROL_NODES
VIDEO_TASKS = _video_catalog.VIDEO_TASKS
DEFAULT_VIDEO_BACKEND = _video_catalog.DEFAULT_VIDEO_BACKEND

wan_frame_count = _video_graphs.wan_frame_count
h3_frame_count = _video_graphs.h3_frame_count
camera_move_prompt = _video_graphs.camera_move_prompt
build_camera_end_still = _video_graphs.build_camera_end_still
h3_ref_prompt = _video_graphs.h3_ref_prompt
h3_pose_drive_prompt = _video_graphs.h3_pose_drive_prompt

# --- 拆到 comfyui_pipeline/ 的實作,這裡原名再匯出(舊呼叫端與測試仍用 generate.<名稱>) ---
from comfyui_pipeline.client import (
    COMFY_URL_ENV_VARS, COMFY_CONFIG_ENV_VARS, DEFAULT_TIMEOUT, DEFAULT_HTTP_TIMEOUT,
    DEFAULT_POLL_TIMEOUT, DEFAULT_POLL_INTERVAL, DEFAULT_POLL_RETRIES, _normalise_comfy_url,
    _read_runtime_config, resolve_comfy_url, _comfy_endpoint, validate_timeout,
    VideoTimeoutError, _runtime_config_path_from_env, _relative_config_path,
    _fetch_comfy_object_info, upload_image, _is_transient_poll_error, _poll_error_text,
    _query_prompt_queue_status, _cancel_exact_pending_prompt, submit_and_wait,
    _safe_output_path, download_outputs,
)
from comfyui_pipeline.video_config import (
    _video_task_capabilities, _normalise_video_capabilities, load_video_capabilities,
    _configured_backend_spec, _configured_capabilities, _video_model_file_name,
    _video_model_roots, _video_model_path, _required_video_model_keys, _validate_video_models,
    _required_video_nodes, _node_schema_fingerprint, validate_comfy_video_nodes,
    _runtime_versions_for_video, validate_video_runtime, configure_video_capability,
    backend_has, require_video_backend,
)
from comfyui_pipeline.image_capabilities import (
    FLUX2_REQUIRED_NODES, FLUX2_EDIT_REQUIRED_NODES, _node_combo_values, IMAGE_GRAPH_TASKS,
    IMAGE_PROFILE_TASKS, PREFLIGHT_IMAGE_PLACEHOLDER, IMAGE_MODEL_INPUTS, _object_info_options,
    check_image_graph_against_object_info, IMAGE_CAPABILITY_CONFIG_FILENAME,
    load_image_capabilities, resolve_image_profile, preflight_image_task,
    validate_flux2_capability, validate_controlnet_union_capability,
)
from comfyui_pipeline.video_builders import (
    run_i2v, run_character_video, run_pose_drive, build_img2video_wan, build_pose_drive_wan,
    build_img2video_h3, build_character_video_h3, build_pose_drive_h3,
)
from comfyui_pipeline.video_media import (
    _require_video_duration, _require_wh_pair, video_canvas, _image_size,
    validate_transition_images, _make_temp_image_path, _remove_temp_file, _video_streams,
    _fps_fraction, _read_motion_fps, validate_motion_reference_fps, validate_video_input,
    extract_video_frames, extract_last_frame, _resize_video_image, concat_videos,
    VIDEO_COMPOSITE_BACKGROUND_EXTS, composite_videos,
)
from comfyui_pipeline.video_contract import (
    VideoContractError, _sha256_file, _safe_identifier, video_filename_prefix,
    _video_expected_frames, make_video_contract, _digest_json, _config_digest,
    _video_model_records, _input_records, _continuity_metric, _first_last_video_images,
    _continuity_warnings, inspect_video_output, _validate_video_contract, report_video_output,
    _sidecar_path, _write_json_atomic, _json_safe, write_video_sidecar, _resume_signature,
    resume_video_output, _find_named_video_output, write_video_timeout_record,
)
from comfyui_pipeline import cli as _cli
from comfyui_pipeline import runtime as _runtime
from comfyui_pipeline import tasks as _tasks
from comfyui_pipeline.tasks._common import add_runtime_arguments as _add_runtime_arguments

_build_image_task_graph = _tasks.build_image_task_graph
_validate_cli_args = _cli.validate_cli_args
_validate_task_capabilities = _cli.validate_task_capabilities

# 拆出去的模組透過 runtime.facade 讀這個模組的命名空間,測試對 generate.<名稱> 打補丁/改值才會生效。
_runtime.bind(globals())


def main(argv=None):
    _runtime.bind(globals())
    _cli.run(argv)


if __name__ == "__main__":
    main()
