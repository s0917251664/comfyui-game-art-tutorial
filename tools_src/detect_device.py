"""
設備能力偵測。不依賴 torch(可能還沒裝),只用系統指令跟標準庫判斷。
輸出 device_config.json,給安裝流程(見 skills/comfyui-install/SKILL.md)跟 generate.py 共用讀取。

Usage: python detect_device.py [--out device_config.json]
"""
import argparse
import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys

# 依 VRAM 分級,對應教學.md 第 0.5 章 B 段的表
TIERS = [
    # (min_vram_mb, tier_name, checkpoint, default_width, default_height, torch_index)
    (24000, "sdxl_high", "sd_xl_base_1.0.safetensors", 1024, 1024, "cu130"),
    (12000, "sdxl", "sd_xl_base_1.0.safetensors", 1024, 1024, "cu130"),
    (8000, "sdxl_light", "sd_xl_base_1.0.safetensors", 768, 768, "cu126"),
    (0, "sd15", "dreamshaper_8.safetensors", 512, 512, "cu126"),
]

NVIDIA_SMI = "nvidia-smi"
APPLE_MEMORY_COMMAND = ("sysctl", "-n", "hw.memsize")
# Unified memory is shared with macOS and other processes.  Treating only half
# of it as available to the diffusion workload keeps tier selection conservative
# (36 GB, for example, remains in the regular SDXL tier rather than the high tier).
APPLE_DIFFUSION_MEMORY_RATIO = 0.5
DEFAULT_DEVICE_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "device_config.json")


def _diagnostic_warning(message):
    """把可診斷的硬體偵測問題送到 stderr,不把它偽裝成「沒有 GPU」。"""
    print(f"[警告] {message}", file=sys.stderr)


def _run_nvidia_smi(args, purpose):
    """執行 nvidia-smi; 工具缺失可安靜 fallback,其他錯誤要留下警告。"""
    if shutil.which(NVIDIA_SMI) is None:
        return None
    try:
        result = subprocess.run(
            [NVIDIA_SMI, *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return result.stdout or ""
    except Exception as exc:
        detail = f": {exc}" if str(exc) else ""
        _diagnostic_warning(f"nvidia-smi {purpose}失敗{detail}")
        return None


def _parse_memory_mb(value):
    """解析 nvidia-smi 的 memory.total 欄位(通常是整數 MB)。"""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:MiB|MB)?\s*", str(value), re.IGNORECASE)
    if match is None:
        raise ValueError(f"無法解析記憶體數值 {value!r}")
    memory_mb = int(float(match.group(1)))
    if memory_mb < 0:
        raise ValueError(f"記憶體數值不可為負數 {value!r}")
    return memory_mb


def _parse_driver_versions(value):
    """從 nvidia-smi 輸出擷取完整 driver version tuple。"""
    versions = []
    for match in re.finditer(r"(?<!\d)\d+(?:\.\d+){0,3}(?!\d)", str(value)):
        versions.append(tuple(int(part) for part in match.group(0).split(".")))
    return versions


def get_nvidia_gpu():
    """回傳 VRAM 最大的 (gpu_name, vram_mb),或 None。"""
    out = _run_nvidia_smi(
        ["--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
        "GPU 資訊查詢",
    )
    if out is None:
        return None

    gpus = []
    try:
        rows = csv.reader(out.splitlines(), skipinitialspace=True)
        for row_number, row in enumerate(rows, start=1):
            if not row or not any(field.strip() for field in row):
                continue
            if len(row) < 2:
                _diagnostic_warning(f"nvidia-smi GPU 資訊第 {row_number} 行欄位不足: {row!r}")
                continue

            # GPU 名稱若本身含逗號,正規 CSV 會保留在同一欄；未加引號的輸出
            # 則把除最後一欄外的部分接回來,避免錯誤截斷名稱。
            name = ", ".join(field.strip() for field in row[:-1]).strip()
            if not name:
                _diagnostic_warning(f"nvidia-smi GPU 資訊第 {row_number} 行名稱為空")
                continue
            try:
                vram_mb = _parse_memory_mb(row[-1])
            except ValueError as exc:
                _diagnostic_warning(f"nvidia-smi GPU 資訊第 {row_number} 行解析失敗: {exc}")
                continue
            gpus.append((name, vram_mb))
    except Exception as exc:
        _diagnostic_warning(f"nvidia-smi GPU 資訊解析失敗: {exc}")
        return None

    if not gpus:
        _diagnostic_warning("nvidia-smi 沒有可解析的 GPU 資訊")
        return None
    return max(gpus, key=lambda item: item[1])


def get_apple_unified_memory_mb():
    """讀取 Apple Silicon 的 unified memory,讀不到時回傳 None。"""
    try:
        result = subprocess.run(
            list(APPLE_MEMORY_COMMAND),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        raw_value = (result.stdout or "").strip()
        match = re.search(r"(?<!\d)\d+(?!\d)", raw_value)
        if match is None:
            raise ValueError(f"無法解析 hw.memsize 輸出 {raw_value!r}")
        memory_bytes = int(match.group(0))
        if memory_bytes <= 0:
            raise ValueError(f"hw.memsize 必須為正數,得到 {memory_bytes}")
        return memory_bytes // (1024 * 1024)
    except Exception as exc:
        detail = f": {exc}" if str(exc) else ""
        _diagnostic_warning(f"無法讀取 Apple Silicon unified memory{detail}")
        return None


def get_nvidia_driver_cuda_hint():
    """依完整 driver version 選 CUDA wheel; CUDA 13 需要 driver >= 580。"""
    out = _run_nvidia_smi(
        ["--query-gpu=driver_version", "--format=csv,noheader"],
        "driver version 查詢",
    )
    if out is None:
        # 沒有工具或查詢失敗時,cu126 是相容性較寬的安全選擇。
        return "cu126"

    versions = _parse_driver_versions(out)
    if not versions:
        _diagnostic_warning(f"nvidia-smi driver version 無法解析: {out!r}")
        return "cu126"

    # 多張卡通常共用同一 driver,但若輸出不一致要以最低版本判斷,
    # 避免選到某張卡不支援的 CUDA runtime。
    oldest_driver = min(versions)
    return "cu130" if oldest_driver[0] >= 580 else "cu126"


def detect():
    os_name = platform.system()  # Windows / Darwin / Linux
    machine = platform.machine().lower()

    gpu = get_nvidia_gpu()
    unified_memory_mb = None
    if gpu:
        gpu_name, vram_mb = gpu
        backend = "cuda"
    elif os_name == "Darwin" and machine in ("arm64", "aarch64"):
        unified_memory_mb = get_apple_unified_memory_mb()
        gpu_name, vram_mb, backend = "Apple Silicon (MPS)", None, "mps"
    else:
        gpu_name, vram_mb, backend = None, 0, "cpu"

    if backend == "cuda":
        effective_vram = vram_mb
    elif backend == "mps":
        # 統一記憶體要留一半給 macOS/其他程序；讀不到時以 0 選最低 tier,
        # 避免在未知容量的機器上預設較大的 SDXL 工作流造成 OOM。
        effective_vram = (
            int(unified_memory_mb * APPLE_DIFFUSION_MEMORY_RATIO)
            if unified_memory_mb is not None
            else 0
        )
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
        "unified_memory_mb": unified_memory_mb,
        "tier": tier_name,
        "checkpoint": checkpoint,
        "default_width": width,
        "default_height": height,
        "torch_index_url": (
            f"https://download.pytorch.org/whl/{torch_index}" if backend == "cuda" else None
        ),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_DEVICE_CONFIG_PATH)
    args = ap.parse_args(argv)

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
