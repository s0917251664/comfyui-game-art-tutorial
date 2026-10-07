"""影片 graph 的 backend 入口(run_*)與 Wan/H3 graph builder。

從 generate.py 抽出,graph 內容未改動。
"""
from .image_graphs import build_control_preprocessor, seed_or_random
from .video_catalog import (
    CHARACTER_REF_MAX, VACE_CFG, VACE_NEGATIVE_DEFAULT, VACE_SHIFT, VACE_STEPS, VIDEO_FPS,
    VIDEO_NEG_DEFAULT, VIDEO_STEPS,
)
from .video_config import _video_model_file_name
from .video_graphs import h3_frame_count, h3_pose_drive_prompt, h3_ref_prompt, wan_frame_count


def run_i2v(backend, prompt, image_filename, width, height, seed, duration,
            last_image_filename=None, filename_prefix="img2video", negative=None,
            video_config=None):
    """I2V 的 backend 入口。main() 不要自己挑 graph。"""
    if backend == "wan":
        return build_img2video_wan(
            prompt, image_filename, negative=negative,
            width=width, height=height, seed=seed, duration=duration,
            filename_prefix=filename_prefix, video_config=video_config,
        )
    if backend == "h3":
        return build_img2video_h3(
            prompt, image_filename, width=width, height=height,
            seed=seed, duration=duration, last_image_filename=last_image_filename,
            filename_prefix=filename_prefix, video_config=video_config,
        )
    raise SystemExit(f"未知 --backend {backend!r}")


def run_character_video(backend, prompt, ref_filenames, width, height, seed, duration,
                        filename_prefix="character_video",
                        video_config=None):
    if backend == "h3":
        return build_character_video_h3(
            prompt, ref_filenames, width=width, height=height,
            seed=seed, duration=duration, filename_prefix=filename_prefix, video_config=video_config,
        )
    raise SystemExit(f"character_video 目前沒有 {backend} 實作")


def run_pose_drive(backend, prompt, image_filename, motion_filename, width, height, seed,
                   duration, control_type="pose", filename_prefix="pose_drive", negative=None,
                   video_config=None):
    if backend == "h3":
        return build_pose_drive_h3(
            prompt, image_filename, motion_filename, width=width, height=height,
            seed=seed, duration=duration, control_type=control_type,
            filename_prefix=filename_prefix, video_config=video_config,
        )
    if backend == "wan":
        return build_pose_drive_wan(
            prompt, image_filename, motion_filename, width=width, height=height,
            seed=seed, duration=duration, control_type=control_type,
            filename_prefix=filename_prefix, negative=negative, video_config=video_config,
        )
    raise SystemExit(f"pose_drive 目前沒有 {backend} 實作")


def build_img2video_wan(prompt, image_filename, negative=None, width=832, height=480,
                        seed=None, duration=2.0, filename_prefix="img2video",
                        video_config=None):
    seed = seed_or_random(seed)
    length = wan_frame_count(duration)
    negative = negative or VIDEO_NEG_DEFAULT
    g = {
        "37": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("wan", "i2v_unet", video_config), "weight_dtype": "default"}},
        "38": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("wan", "clip", video_config), "type": "wan", "device": "default"}},
        "39": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("wan", "vae", video_config)}},
        "48": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["37", 0], "shift": 8.0}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["38", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["38", 0]}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "55": {"class_type": "Wan22ImageToVideoLatent", "inputs": {
            "vae": ["39", 0], "start_image": ["56", 0],
            "width": width, "height": height, "length": length, "batch_size": 1}},
        "3": {"class_type": "KSampler", "inputs": {
            "model": ["48", 0], "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["55", 0], "seed": seed, "steps": VIDEO_STEPS, "cfg": 5.0,
            "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["39", 0]}},
        "57": {"class_type": "CreateVideo", "inputs": {"images": ["8", 0], "fps": float(VIDEO_FPS)}},
        "58": {"class_type": "SaveVideo", "inputs": {
            "video": ["57", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "58"


def build_pose_drive_wan(prompt, image_filename, motion_filename, width=768, height=768,
                         seed=None, duration=2.0, control_type="pose",
                         filename_prefix="pose_drive", negative=None,
                         video_config=None):
    """pose_drive 的 wan 實作:Fun Control 5B,角色靜幀當 ref_image,動作影片抽幀後走 canny/pose/depth。
    跟 I2V 用的 TI2V 5B 是不同 UNET,task 層不要寫這個檔名。"""
    seed = seed_or_random(seed)
    length = wan_frame_count(duration)
    negative = negative or VIDEO_NEG_DEFAULT
    g = {
        "37": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("wan", "control_unet", video_config), "weight_dtype": "default"}},
        "38": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("wan", "clip", video_config), "type": "wan", "device": "default"}},
        "39": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("wan", "vae", video_config)}},
        "48": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["37", 0], "shift": 8.0}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["38", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["38", 0]}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "80": {"class_type": "LoadVideo", "inputs": {"file": motion_filename}},
        "81": {"class_type": "GetVideoComponents", "inputs": {"video": ["80", 0]}},
        "82": build_control_preprocessor(control_type, "81"),
        "55": {"class_type": "Wan22FunControlToVideo", "inputs": {
            "positive": ["6", 0], "negative": ["7", 0], "vae": ["39", 0],
            "width": width, "height": height, "length": length, "batch_size": 1,
            "ref_image": ["56", 0], "control_video": ["82", 0]}},
        "3": {"class_type": "KSampler", "inputs": {
            "model": ["48", 0], "positive": ["55", 0], "negative": ["55", 1],
            "latent_image": ["55", 2], "seed": seed, "steps": VIDEO_STEPS, "cfg": 5.0,
            "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["39", 0]}},
        "57": {"class_type": "CreateVideo", "inputs": {"images": ["8", 0], "fps": float(VIDEO_FPS)}},
        "58": {"class_type": "SaveVideo", "inputs": {
            "video": ["57", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "58"


def build_img2video_h3(prompt, image_filename, width=768, height=768, seed=None, duration=2.0,
                       last_image_filename=None, filename_prefix="img2video",
                       video_config=None):
    seed = seed_or_random(seed)
    length = h3_frame_count(duration)
    g = {
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("h3", "i2v_unet", video_config), "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("h3", "clip", video_config), "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "video_vae", video_config)}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "audio_vae", video_config)}},
        "shift": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "104": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["13", 0], "vae": ["11", 0], "first_frame": ["56", 0],
            "prompt": prompt, "width": width, "height": height, "length": length}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {
            "model": ["shift", 0], "scheduler": "simple", "steps": VIDEO_STEPS, "denoise": 1.0}},
        "16": {"class_type": "BasicGuider", "inputs": {
            "model": ["shift", 0], "conditioning": ["104", 0]}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
            "sigmas": ["9", 0], "latent_image": ["104", 1]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["11", 0]}},
        "23": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["24", 0]}},
        "91": {"class_type": "CreateVideo", "inputs": {
            "images": ["10", 0], "audio": ["23", 0], "fps": float(VIDEO_FPS), "bit_depth": 8}},
        "92": {"class_type": "SaveVideo", "inputs": {
            "video": ["91", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    if last_image_filename:
        g["56b"] = {"class_type": "LoadImage", "inputs": {"image": last_image_filename}}
        g["104"]["inputs"]["last_frame"] = ["56b", 0]
    return g, "92"


def build_character_video_h3(prompt, ref_filenames, width=768, height=768, seed=None, duration=2.0,
                             filename_prefix="character_video",
                             video_config=None):
    """character_video 的 h3 實作(Ref2VA)。task 契約見 run_character_video,不要從 main 直接叫這個。
    ref_image_size 鎖 match;官方 max 保身份更好但每個 step 都帶參考 token,16GB 上沒實測過不開旗標。
    """
    if not (1 <= len(ref_filenames) <= CHARACTER_REF_MAX):
        raise ValueError(
            f"character_video 要 1~{CHARACTER_REF_MAX} 張參考圖,目前 {len(ref_filenames)}"
        )
    seed = seed_or_random(seed)
    length = h3_frame_count(duration)
    prompt = h3_ref_prompt(prompt, len(ref_filenames))
    g = {
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("h3", "ref_unet", video_config), "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("h3", "clip", video_config), "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "video_vae", video_config)}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "audio_vae", video_config)}},
        "shift": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "104": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
            "clip": ["13", 0], "vae": ["11", 0], "audio_vae": ["24", 0],
            "prompt": prompt, "width": width, "height": height, "length": length,
            "ref_image_size": "match"}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {
            "model": ["shift", 0], "scheduler": "simple", "steps": VIDEO_STEPS, "denoise": 1.0}},
        "16": {"class_type": "BasicGuider", "inputs": {
            "model": ["shift", 0], "conditioning": ["104", 0]}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
            "sigmas": ["9", 0], "latent_image": ["104", 1]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["11", 0]}},
        "23": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["24", 0]}},
        "91": {"class_type": "CreateVideo", "inputs": {
            "images": ["10", 0], "audio": ["23", 0], "fps": float(VIDEO_FPS), "bit_depth": 8}},
        "92": {"class_type": "SaveVideo", "inputs": {
            "video": ["91", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    for i, fn in enumerate(ref_filenames):
        nid = f"56r{i}"
        g[nid] = {"class_type": "LoadImage", "inputs": {"image": fn}}
        g["104"]["inputs"][f"ref_images.ref_image_{i}"] = [nid, 0]
    return g, "92"


def build_pose_drive_h3(prompt, image_filename, motion_filename, width=768, height=768,
                        seed=None, duration=2.0, control_type="pose",
                        filename_prefix="pose_drive",
                        video_config=None):
    """pose_drive 的 h3 實作:同一顆 Ref2VA,角色靜幀當 ref_image_0,動作片抽幀後走 pose/canny/depth 當 ref_video_0。
    ComfyUI 0.34.0 沒有 MiniMaxH3FunControlNetApply(PR #15860 還沒進),所以不是真正的 ControlNet Union;
    預處理動作片是為了不要把動作片裡那個人的臉漏進輸出。身份鎖比 wan Fun Control 穩,但仍不是像素鎖臉。
    負向詞這顆沒入口,呼叫端給了也忽略。"""
    seed = seed_or_random(seed)
    length = h3_frame_count(duration)
    prompt = h3_pose_drive_prompt(prompt)
    g = {
        "6": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("h3", "ref_unet", video_config), "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("h3", "clip", video_config), "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "video_vae", video_config)}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("h3", "audio_vae", video_config)}},
        "shift": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "56": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "80": {"class_type": "LoadVideo", "inputs": {"file": motion_filename}},
        "81": {"class_type": "GetVideoComponents", "inputs": {"video": ["80", 0]}},
        "82": build_control_preprocessor(control_type, "81"),
        "104": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
            "clip": ["13", 0], "vae": ["11", 0], "audio_vae": ["24", 0],
            "prompt": prompt, "width": width, "height": height, "length": length,
            "ref_image_size": "match",
            "ref_images.ref_image_0": ["56", 0],
            "ref_videos.ref_video_0": ["82", 0]}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "9": {"class_type": "BasicScheduler", "inputs": {
            "model": ["shift", 0], "scheduler": "simple", "steps": VIDEO_STEPS, "denoise": 1.0}},
        "16": {"class_type": "BasicGuider", "inputs": {
            "model": ["shift", 0], "conditioning": ["104", 0]}},
        "14": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
            "sigmas": ["9", 0], "latent_image": ["104", 1]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["11", 0]}},
        "23": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["24", 0]}},
        "91": {"class_type": "CreateVideo", "inputs": {
            "images": ["10", 0], "audio": ["23", 0], "fps": float(VIDEO_FPS), "bit_depth": 8}},
        "92": {"class_type": "SaveVideo", "inputs": {
            "video": ["91", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "92"


def build_video_inpaint_wan(prompt, control_filename, mask_filename, width, height, length, seed=None,
                            negative=None, strength=1.0, filename_prefix="video_inpaint",
                            video_config=None):
    """video_inpaint 的 wan 實作:Wan2.1 VACE 遮罩局部重繪。

    取樣參數照官方 ComfyUI 模板 video_wan_vace_inpainting.json(非 turbo 分支)。control/mask 都是
    task 端在本機裁好、縮好、編成無損影片後上傳的同尺寸片段,節點內不再縮放裁切;mask 白色=重畫。
    """
    seed = seed_or_random(seed)
    negative = negative or VACE_NEGATIVE_DEFAULT
    g = {
        "37": {"class_type": "UNETLoader", "inputs": {
            "unet_name": _video_model_file_name("wan", "vace_unet", video_config), "weight_dtype": "default"}},
        "38": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _video_model_file_name("wan", "clip", video_config), "type": "wan", "device": "default"}},
        "39": {"class_type": "VAELoader", "inputs": {"vae_name": _video_model_file_name("wan", "vace_vae", video_config)}},
        "48": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["37", 0], "shift": VACE_SHIFT}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["38", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["38", 0]}},
        "80": {"class_type": "LoadVideo", "inputs": {"file": control_filename}},
        "81": {"class_type": "GetVideoComponents", "inputs": {"video": ["80", 0]}},
        "82": {"class_type": "LoadVideo", "inputs": {"file": mask_filename}},
        "83": {"class_type": "GetVideoComponents", "inputs": {"video": ["82", 0]}},
        "84": {"class_type": "ImageToMask", "inputs": {"image": ["83", 0], "channel": "red"}},
        "55": {"class_type": "WanVaceToVideo", "inputs": {
            "positive": ["6", 0], "negative": ["7", 0], "vae": ["39", 0],
            "width": width, "height": height, "length": length, "batch_size": 1, "strength": float(strength),
            "control_video": ["81", 0], "control_masks": ["84", 0]}},
        "3": {"class_type": "KSampler", "inputs": {
            "model": ["48", 0], "positive": ["55", 0], "negative": ["55", 1],
            "latent_image": ["55", 2], "seed": seed, "steps": VACE_STEPS, "cfg": VACE_CFG,
            "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "56": {"class_type": "TrimVideoLatent", "inputs": {"samples": ["3", 0], "trim_amount": ["55", 3]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["56", 0], "vae": ["39", 0]}},
        "57": {"class_type": "CreateVideo", "inputs": {"images": ["8", 0], "fps": float(VIDEO_FPS)}},
        "58": {"class_type": "SaveVideo", "inputs": {
            "video": ["57", 0], "filename_prefix": filename_prefix,
            "format": "mp4", "codec": "h264"}},
    }
    return g, "58"
