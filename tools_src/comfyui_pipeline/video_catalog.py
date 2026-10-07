"""Video model/catalog constants and shared schema fingerprinting."""

import hashlib
import json


def node_schema_fingerprint(payload, classes=None):
    """Ignore uploaded-file inventory while retaining node interface changes."""
    if not isinstance(payload, dict):
        raise ValueError("ComfyUI /object_info response is not a JSON object")
    selected = {}
    for name in sorted(payload if classes is None else classes):
        info = payload.get(name)
        if not isinstance(info, dict):
            continue
        schema = json.loads(json.dumps({
            key: info[key]
            for key in ("input", "output", "output_name", "display_name", "name")
            if key in info
        }))
        inputs = schema.get("input", {})
        if isinstance(inputs, dict):
            for fields in inputs.values():
                if not isinstance(fields, dict):
                    continue
                for field in fields.values():
                    if not isinstance(field, list) or len(field) < 2 or not isinstance(field[1], dict):
                        continue
                    options = field[1]
                    if options.get("image_upload") or options.get("video_upload") or options.get("audio_upload"):
                        if isinstance(field[0], list):
                            field[0] = []
                        if "options" in options:
                            options["options"] = []
        selected[name] = schema
    encoded = json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

CHARACTER_REF_MAX = 9
VIDEO_WAN_UNET = "wan2.2_ti2v_5B_fp16.safetensors"
VIDEO_WAN_FUN_UNET = "wan2.2_fun_control_5B_bf16.safetensors"
VIDEO_WAN_CLIP = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VIDEO_WAN_VAE = "wan2.2_vae.safetensors"
# video_inpaint (VACE masked edit) is a Wan2.1-family model: it needs the Wan2.1 VAE, not the 2.2 one.
VIDEO_WAN_VACE_UNET = "wan2.1_vace_1.3B_fp16.safetensors"
VIDEO_WAN21_VAE = "wan_2.1_vae.safetensors"
VIDEO_H3_UNET = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
VIDEO_H3_REF_UNET = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
VIDEO_H3_CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_H3_VAE = "minimax_h3_video_vae_fp16.safetensors"
VIDEO_H3_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
VIDEO_MAX_SIDE = 768
VIDEO_STEPS = 20
VIDEO_FPS = 24
VIDEO_FPS_TOLERANCE = 0.5
VIDEO_DURATION_MIN = 2
VIDEO_DURATION_MAX = 6
DEFAULT_VIDEO_TIMEOUT = 1800.0
VIDEO_CAPABILITY_SCHEMA_VERSION = 1
VIDEO_SIDECAR_SCHEMA_VERSION = 1
VIDEO_CONTRACT_SCHEMA_VERSION = 1
VIDEO_DURATION_TOLERANCE = 0.40
VIDEO_FRAME_TOLERANCE = 2
VIDEO_SEAM_WARNING_THRESHOLD = 0.12
VIDEO_INPUT_MIN_DURATION = 0.05
VIDEO_AUDIO_DRIFT_TOLERANCE = 0.25
VIDEO_CAPABILITY_CONFIG_ENV_VARS = ("VIDEO_CONFIG", "COMFY_VIDEO_CONFIG")
VIDEO_CAPABILITY_CONFIG_FILENAME = "video_capabilities.json"
VIDEO_NEG_DEFAULT = (
    "blurry, low quality, morphing face, extra limbs, camera movement, "
    "zoom, pan, text, watermark, still image, frozen"
)
# VACE masked edit: sampling follows the official ComfyUI template
# video_wan_vace_inpainting.json (non-turbo branch); 1.3B is a 480P model.
VACE_SHIFT = 5.0
VACE_STEPS = 20
VACE_CFG = 6.0
VACE_MAX_FRAMES = 81
VACE_MAX_PIXELS = 832 * 480
VACE_NEGATIVE_DEFAULT = (
    "过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
    "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，"
    "背景人很多，倒着走,过曝，"
)
VIDEO_LOOP_SUFFIX = (
    "seamless looping animation, cyclical motion that returns to the first frame, "
    "camera locked, subject stays in place"
)

# camera_move 的運鏡枚舉(task 契約)。有 last_frame 能力的 backend 會再餵幾何終點靜幀;
# 沒有的 backend 只靠下面這組英文運鏡句。orbit 平面裁切做不出繞拍終點,一律只走 prompt。
CAMERA_MOVES = {
    "static": "locked static camera, no camera movement",
    "pan_up": "slow camera pan up",
    "pan_down": "slow camera pan down",
    "pan_left": "slow camera pan left",
    "pan_right": "slow camera pan right",
    "zoom_in": "slow camera zoom in toward the subject",
    "zoom_out": "slow camera zoom out from the subject",
    "orbit_cw": "slow camera orbit clockwise around the subject",
    "orbit_ccw": "slow camera orbit counter-clockwise around the subject",
}
CAMERA_STILL_SUFFIX = (
    "the subject stays completely still, no character animation, no morphing, "
    "only the camera moves, keep identity and framing except for the camera move"
)
CAMERA_ZOOM = 1.35       # zoom_in 終點是來源中心 1/1.35 再拉回畫布
CAMERA_PAN_CROP = 0.82   # pan_* 終點保留這個比例、往運鏡方向裁

# 這是「程式知道怎麼組 graph」的 implementation catalog，不是「這台機器
# 一定有這些模型」的能力宣告。真正執行影片 task 前，main() 必須載入由
# detect_video_capabilities.py 產生的 machine-specific config，重新檢查檔案、
# runtime 與 ComfyUI nodes；沒有 config 不會使用下面的檔名猜測可用 backend。
# 保留這份 catalog 是為了讓離線 graph builder 與 detector 共用明確的 task/backend
# 契約；模型檔名本身仍會由 active config 覆蓋。
VIDEO_BACKEND_SPECS = {
    "h3": {
        "capabilities": frozenset({"i2v", "last_frame", "character_ref", "control_video", "audio"}),
        "models": {
            "i2v_unet": VIDEO_H3_UNET,
            "ref_unet": VIDEO_H3_REF_UNET,
            "clip": VIDEO_H3_CLIP,
            "video_vae": VIDEO_H3_VAE,
            "audio_vae": VIDEO_H3_AUDIO_VAE,
        },
        "required_models": {
            "i2v": ("i2v_unet", "clip", "video_vae", "audio_vae"),
            "last_frame": ("i2v_unet", "clip", "video_vae", "audio_vae"),
            "character_ref": ("ref_unet", "clip", "video_vae", "audio_vae"),
            "control_video": ("ref_unet", "clip", "video_vae", "audio_vae"),
        },
        "required_nodes": {
            "i2v": (
                "UNETLoader", "CLIPLoader", "VAELoader", "MiniMaxH3SigmaShift",
                "MiniMaxH3ImageToVideo", "LoadImage", "RandomNoise", "KSamplerSelect",
                "BasicScheduler", "BasicGuider", "SamplerCustomAdvanced", "VAEDecode",
                "VAEDecodeAudio", "CreateVideo", "SaveVideo",
            ),
            "last_frame": ("MiniMaxH3ImageToVideo",),
            "character_ref": (
                "UNETLoader", "CLIPLoader", "VAELoader", "MiniMaxH3SigmaShift",
                "MiniMaxH3ReferenceToVideo", "LoadImage", "RandomNoise",
                "KSamplerSelect", "BasicScheduler", "BasicGuider",
                "SamplerCustomAdvanced", "VAEDecode", "VAEDecodeAudio",
                "CreateVideo", "SaveVideo",
            ),
            "control_video": (
                "UNETLoader", "CLIPLoader", "VAELoader", "MiniMaxH3SigmaShift",
                "MiniMaxH3ReferenceToVideo", "LoadImage", "LoadVideo",
                "GetVideoComponents", "RandomNoise", "KSamplerSelect",
                "BasicScheduler", "BasicGuider", "SamplerCustomAdvanced",
                "VAEDecode", "VAEDecodeAudio", "CreateVideo", "SaveVideo",
            ),
        },
    },
    "wan": {
        "capabilities": frozenset({"i2v", "control_video", "masked_edit"}),
        "models": {
            "i2v_unet": VIDEO_WAN_UNET,
            "control_unet": VIDEO_WAN_FUN_UNET,
            "clip": VIDEO_WAN_CLIP,
            "vae": VIDEO_WAN_VAE,
            "vace_unet": VIDEO_WAN_VACE_UNET,
            "vace_vae": VIDEO_WAN21_VAE,
        },
        "required_models": {
            "i2v": ("i2v_unet", "clip", "vae"),
            "control_video": ("control_unet", "clip", "vae"),
            "masked_edit": ("vace_unet", "clip", "vace_vae"),
        },
        "required_nodes": {
            "i2v": (
                "UNETLoader", "CLIPLoader", "VAELoader", "ModelSamplingSD3",
                "CLIPTextEncode", "LoadImage", "Wan22ImageToVideoLatent", "KSampler",
                "VAEDecode", "CreateVideo", "SaveVideo",
            ),
            "control_video": (
                "Wan22FunControlToVideo", "LoadVideo", "GetVideoComponents",
            ),
            "masked_edit": (
                "UNETLoader", "CLIPLoader", "VAELoader", "ModelSamplingSD3", "CLIPTextEncode",
                "LoadVideo", "GetVideoComponents", "ImageToMask", "WanVaceToVideo", "KSampler",
                "TrimVideoLatent", "VAEDecode", "CreateVideo", "SaveVideo",
            ),
        },
    },
}

# This remains a static implementation lookup for backwards-compatible graph
# builders. It is deliberately not a default selection. Runtime code uses the
# machine config loaded by configure_video_capability().
VIDEO_BACKENDS = tuple(VIDEO_BACKEND_SPECS)
DEFAULT_VIDEO_BACKEND = None
VIDEO_BACKEND_CAPS = {
    backend: spec["capabilities"] for backend, spec in VIDEO_BACKEND_SPECS.items()
}
VIDEO_TASK_CAPS = {
    "img2video": "i2v",
    "clip_extend": "i2v",
    "camera_move": "i2v",
    "fx_loop": "last_frame",
    "transition": "last_frame",
    "character_video": "character_ref",
    "pose_drive": "control_video",
    "video_inpaint": "masked_edit",
}
VIDEO_TASK_EXTRA_CAPS = {
    "fx_loop": ("i2v",),
    "transition": ("i2v",),
}
VIDEO_CONTROL_NODES = {
    "canny": "Canny",
    "pose": "OpenposePreprocessor",
    "depth": "DepthAnythingV2Preprocessor",
}
VIDEO_TASKS = frozenset(VIDEO_TASK_CAPS)
