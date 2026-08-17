"""
設備能力偵測。不依賴 torch(可能還沒裝),只用系統指令跟標準庫判斷。
輸出 device_config.json,給安裝流程(見 skills/comfyui-install/SKILL.md)跟 generate.py 共用讀取。

Usage: python detect_device.py [--out device_config.json]
"""
import argparse
import json
import platform
import re
import shutil
import subprocess

# 依 VRAM 分級,對應教學.md 第 0.5 章 B 段的表
TIERS = [
    # (min_vram_mb, tier_name, checkpoint, default_width, default_height, torch_index)
    (24000, "sdxl_high", "sd_xl_base_1.0.safetensors", 1024, 1024, "cu130"),
    (12000, "sdxl", "sd_xl_base_1.0.safetensors", 1024, 1024, "cu130"),
    (8000, "sdxl_light", "sd_xl_base_1.0.safetensors", 768, 768, "cu126"),
    (0, "sd15", "dreamshaper_8.safetensors", 512, 512, "cu126"),
]


def get_nvidia_gpu():
    """回傳 (gpu_name, vram_mb) 或 None(沒有 NVIDIA GPU / nvidia-smi 不存在)"""
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        line = out.splitlines()[0]
        name, vram = [x.strip() for x in line.split(",")]
        return name, int(vram)
    except Exception:
        return None


def get_nvidia_driver_cuda_hint():
    """粗略從 driver 版本猜合理的 torch cuda index(driver 太舊選舊一點的 index 比較安全)"""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        major = int(out.split(".")[0])
        return "cu130" if major >= 550 else "cu126"
    except Exception:
        return "cu126"


def detect():
    os_name = platform.system()  # Windows / Darwin / Linux
    machine = platform.machine().lower()

    gpu = get_nvidia_gpu()
    if gpu:
        gpu_name, vram_mb = gpu
        backend = "cuda"
    elif os_name == "Darwin" and machine in ("arm64", "aarch64"):
        gpu_name, vram_mb, backend = "Apple Silicon (MPS)", None, "mps"
    else:
        gpu_name, vram_mb, backend = None, 0, "cpu"

    if backend == "cuda":
        effective_vram = vram_mb
    elif backend == "mps":
        # Mac 統一記憶體沒有獨立 VRAM 概念,粗估成一個中高階等級,不強求精準
        effective_vram = 16000
    else:
        effective_vram = 0

    tier_name = checkpoint = torch_index = None
    width = height = None
    for min_vram, name, ckpt, w, h, default_idx in TIERS:
        if effective_vram >= min_vram:
            tier_name, checkpoint, width, height = name, ckpt, w, h
            torch_index = get_nvidia_driver_cuda_hint() if backend == "cuda" else default_idx
            break

    return {
        "os": os_name,
        "machine": machine,
        "backend": backend,  # cuda / mps / cpu
        "gpu_name": gpu_name,
        "vram_mb": vram_mb,
        "tier": tier_name,
        "checkpoint": checkpoint,
        "default_width": width,
        "default_height": height,
        "torch_index_url": (
            f"https://download.pytorch.org/whl/{torch_index}" if backend == "cuda" else None
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="device_config.json")
    args = ap.parse_args()

    config = detect()
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"偵測結果 → {args.out}")
    print(json.dumps(config, ensure_ascii=False, indent=2))

    if config["backend"] == "cpu":
        print("\n[警告] 沒偵測到可用 GPU,ComfyUI 會退回 CPU 運算,生成速度會非常慢(以分鐘甚至十分鐘計)。")
    elif config["tier"] == "sd15":
        print("\n[注意] VRAM 偏低,自動選用 SD1.5 等級的設定,畫質會低於 SDXL。")


if __name__ == "__main__":
    main()
