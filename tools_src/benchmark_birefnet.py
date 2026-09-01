"""Reproducible BiRefNet variant benchmark for existing RGBA game-art assets.

This is deliberately a benchmark utility, not a production remove-bg backend.
It keeps model selection out of generate.py until a fixed A/B demonstrates that
changing the verified ComfyUI path is worthwhile.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

# Transformers copies audited local `trust_remote_code` modules into a cache
# before importing them. Keep that generated cache machine-local and writable;
# do not require access to the operator's global Hugging Face cache.
os.environ.setdefault("HF_MODULES_CACHE", str(Path(tempfile.gettempdir()) / "comfyui_birefnet_hf_modules"))
from transformers import AutoModelForImageSegmentation


VARIANTS = {
    "general": ("BiRefNet", 1024),
    "hr": ("BiRefNet_HR", 2048),
    "hr-matting": ("BiRefNet_HR-matting", 2048),
    # The dynamic model was trained without a fixed resize. The benchmark cases
    # are bounded to 2048 so all candidates see the same source information.
    "dynamic": ("BiRefNet_dynamic", None),
}
BACKGROUNDS = {
    "light": (232, 231, 225),
    "dark": (24, 27, 33),
}


def validate_case_size(value: int | str) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("case size must be an integer") from exc
    if value < 256 or value > 2304 or value % 32:
        raise argparse.ArgumentTypeError("case size must be 256..2304 and divisible by 32")
    return value


def fit_rgba_to_square(image: Image.Image, size: int) -> Image.Image:
    image = image.convert("RGBA")
    scale = min(size / image.width, size / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas


def composite_case(rgba: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    bg = Image.new("RGBA", rgba.size, (*background, 255))
    return Image.alpha_composite(bg, rgba).convert("RGB")


def invert_alpha(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    corrected = image.copy()
    corrected.putalpha(Image.fromarray(255 - alpha))
    return corrected


def normalize_image(image: Image.Image, inference_size: int | None, device: torch.device) -> torch.Tensor:
    if inference_size is not None:
        image = image.resize((inference_size, inference_size), Image.Resampling.BILINEAR)
    array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
    return ((tensor - mean) / std).to(device=device, dtype=torch.float16)


def alpha_metrics(predicted: np.ndarray, expected: np.ndarray) -> dict[str, float]:
    predicted = predicted.astype(np.float32) / 255.0
    expected = expected.astype(np.float32) / 255.0
    mae = float(np.abs(predicted - expected).mean())
    pred_binary = predicted >= 0.5
    expected_binary = expected >= 0.5
    intersection = int(np.logical_and(pred_binary, expected_binary).sum())
    union = int(np.logical_or(pred_binary, expected_binary).sum())
    iou = intersection / union if union else 1.0
    edge = (expected > 0.02) & (expected < 0.98)
    if not edge.any():
        # Include a narrow band around the binary boundary when the source alpha
        # has no soft matte pixels.
        expected_tensor = torch.from_numpy(expected)[None, None]
        dilated = F.max_pool2d(expected_tensor, 5, 1, 2)
        eroded = -F.max_pool2d(-expected_tensor, 5, 1, 2)
        edge = ((dilated - eroded)[0, 0].numpy() > 0.01)
    boundary_mae = float(np.abs(predicted[edge] - expected[edge]).mean()) if edge.any() else mae
    return {"alpha_mae": mae, "iou_0_5": iou, "boundary_mae": boundary_mae}


def load_variant(model_dir: Path, device: torch.device):
    model = AutoModelForImageSegmentation.from_pretrained(
        str(model_dir), trust_remote_code=True, local_files_only=True
    )
    return model.eval().to(device=device, dtype=torch.float16)


def infer_mask(model, image: Image.Image, inference_size: int | None, device: torch.device) -> tuple[Image.Image, float, int]:
    tensor = normalize_image(image, inference_size, device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
        torch.cuda.synchronize(device)
    started = time.perf_counter()
    with torch.inference_mode():
        logits = model(tensor)[-1]
        mask = logits.sigmoid()
        mask = F.interpolate(mask, size=(image.height, image.width), mode="bilinear", align_corners=False)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
        peak = int(torch.cuda.max_memory_allocated(device) / (1024 * 1024))
    else:
        peak = 0
    elapsed = time.perf_counter() - started
    pixels = (mask[0, 0].float().cpu().clamp(0, 1).numpy() * 255.0).round().astype(np.uint8)
    return Image.fromarray(pixels), elapsed, peak


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="A/B benchmark official BiRefNet variants")
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--rgba-source", required=True, action="append", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--case-size", type=validate_case_size, default=2048)
    parser.add_argument("--variant", action="append", choices=sorted(VARIANTS), dest="variants")
    parser.add_argument(
        "--invert-source-alpha",
        action="store_true",
        help="invert legacy RGBA sources created before the pipeline alpha-direction fix",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    variants = args.variants or list(VARIANTS)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("This benchmark requires CUDA; CPU results are not comparable to this pipeline")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cases = []
    for source in args.rgba_source:
        source_rgba = Image.open(source)
        if args.invert_source_alpha:
            source_rgba = invert_alpha(source_rgba)
        rgba = fit_rgba_to_square(source_rgba, args.case_size)
        expected = np.asarray(rgba.getchannel("A"))
        for background_name, colour in BACKGROUNDS.items():
            case_name = f"{source.stem}_{background_name}"
            rgb = composite_case(rgba, colour)
            rgb.save(args.output_dir / f"{case_name}_input.png")
            rgba.getchannel("A").save(args.output_dir / f"{case_name}_expected.png")
            cases.append((case_name, rgb, expected))

    records = []
    for variant in variants:
        directory_name, inference_size = VARIANTS[variant]
        model_dir = args.model_root / directory_name
        if not (model_dir / "model.safetensors").is_file():
            raise FileNotFoundError(f"missing model: {model_dir / 'model.safetensors'}")
        model = load_variant(model_dir, device)
        for case_name, rgb, expected in cases:
            mask, elapsed, peak_mib = infer_mask(model, rgb, inference_size, device)
            mask_path = args.output_dir / f"{case_name}_{variant}_mask.png"
            cutout_path = args.output_dir / f"{case_name}_{variant}_cutout.png"
            mask.save(mask_path)
            cutout = rgb.convert("RGBA")
            cutout.putalpha(mask)
            cutout.save(cutout_path)
            metrics = alpha_metrics(np.asarray(mask), expected)
            records.append({
                "variant": variant,
                "case": case_name,
                "inference_size": inference_size or args.case_size,
                "elapsed_seconds": round(elapsed, 4),
                "peak_cuda_allocated_mib": peak_mib,
                **{key: round(value, 8) for key, value in metrics.items()},
                "mask": str(mask_path),
                "cutout": str(cutout_path),
            })
        del model
        torch.cuda.empty_cache()

    summary = {}
    for variant in variants:
        rows = [row for row in records if row["variant"] == variant]
        summary[variant] = {
            "cases": len(rows),
            "mean_alpha_mae": round(sum(row["alpha_mae"] for row in rows) / len(rows), 8),
            "mean_iou_0_5": round(sum(row["iou_0_5"] for row in rows) / len(rows), 8),
            "mean_boundary_mae": round(sum(row["boundary_mae"] for row in rows) / len(rows), 8),
            "mean_elapsed_seconds": round(sum(row["elapsed_seconds"] for row in rows) / len(rows), 4),
            "max_peak_cuda_allocated_mib": max(row["peak_cuda_allocated_mib"] for row in rows),
        }
    report = {
        "case_size": args.case_size,
        "device": torch.cuda.get_device_name(device),
        "ground_truth_note": "Source alpha is an existing pipeline asset, not a manually refined independent matte.",
        "source_alpha_inverted": args.invert_source_alpha,
        "summary": summary,
        "records": records,
    }
    report_path = args.output_dir / "benchmark.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
