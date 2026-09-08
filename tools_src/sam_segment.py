"""SAM 2.1 automatic mask candidates for the local game-art pipeline.

This is intentionally a standalone tool rather than a ComfyUI graph node.
It emits the same mask contract used by inpaint/guided_inpaint/layer_split:
selected pixels have alpha=0 and unselected pixels have alpha=255.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from simple_mask_tool.core import build_outputs, save_png, selected_ratio


MODEL_ID = "facebook/sam2.1-hiera-small"
DEFAULT_MAX_CANDIDATES = 12


def tensor_mask_to_l(mask, expected_size):
    """Convert a SAM torch/numpy mask to an 8-bit selected-white PIL mask."""
    if hasattr(mask, "detach"):
        mask = mask.detach().to("cpu").numpy()
    while getattr(mask, "ndim", 0) > 2:
        mask = mask[0]
    image = Image.fromarray((mask > 0).astype("uint8") * 255, mode="L")
    if image.size != tuple(expected_size):
        image = image.resize(tuple(expected_size), Image.Resampling.NEAREST)
    return image


def normalize_candidates(masks, scores, expected_size, max_candidates=DEFAULT_MAX_CANDIDATES):
    candidates = []
    for source_index, (mask, score) in enumerate(zip(masks, scores), start=1):
        editor_mask = tensor_mask_to_l(mask, expected_size)
        ratio = selected_ratio(editor_mask)
        if ratio < 0.001 or ratio > 0.98:
            continue
        score_value = float(score.item() if hasattr(score, "item") else score)
        candidates.append(
            {
                "source_index": source_index,
                "score": score_value,
                "selected_ratio": ratio,
                "editor_mask": editor_mask,
            }
        )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:max_candidates]


def build_cutout(source, editor_mask):
    cutout = source.convert("RGBA").copy()
    cutout.putalpha(editor_mask)
    return cutout


def build_contact_sheet(previews, labels, thumb_width=300):
    if not previews:
        raise ValueError("no previews to compose")
    columns = 3
    rows = math.ceil(len(previews) / columns)
    source_width, source_height = previews[0].size
    thumb_height = round(source_height * thumb_width / source_width)
    label_height = 42
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (preview, label) in enumerate(zip(previews, labels)):
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + label_height)
        thumb = preview.convert("RGB").resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))
        draw.text((x + 8, y + thumb_height + 8), label, fill="black", font=font)
    return sheet


def save_candidates(source_path, output_dir, candidates, model_id=MODEL_ID):
    source_path = Path(source_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(source_path).convert("RGBA")
    previews = []
    labels = []
    manifest_items = []

    for index, candidate in enumerate(candidates, start=1):
        prefix = f"candidate_{index:02d}"
        editor, comfy, preview = build_outputs(source, candidate["editor_mask"])
        cutout = build_cutout(source, editor)
        save_png(editor, output_dir / f"{prefix}_mask_editor.png")
        save_png(comfy, output_dir / f"{prefix}_mask_comfy.png")
        save_png(preview, output_dir / f"{prefix}_preview.png")
        save_png(cutout, output_dir / f"{prefix}_cutout.png")
        previews.append(preview)
        labels.append(
            f"#{index:02d} score={candidate['score']:.4f} area={candidate['selected_ratio']:.1%}"
        )
        manifest_items.append(
            {
                "candidate": index,
                "source_index": candidate["source_index"],
                "score": round(candidate["score"], 6),
                "selected_ratio": round(candidate["selected_ratio"], 6),
                "mask_comfy": f"{prefix}_mask_comfy.png",
                "preview": f"{prefix}_preview.png",
                "cutout": f"{prefix}_cutout.png",
            }
        )

    contact_sheet = build_contact_sheet(previews, labels)
    save_png(contact_sheet, output_dir / "contact_sheet.png")
    shutil.copy2(source_path, output_dir / "source.png")
    manifest = {
        "tool": "sam_segment",
        "model": model_id,
        "source": str(source_path),
        "width": source.width,
        "height": source.height,
        "mask_contract": "selected alpha=0; unselected alpha=255",
        "candidate_count": len(manifest_items),
        "candidates": manifest_items,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def run_auto(image_path, output_dir, max_candidates):
    import torch
    from transformers import pipeline

    source = Image.open(image_path).convert("RGB")
    # float16 currently fails inside torchvision NMS with mismatched dtypes in
    # the verified Windows runtime. Keep float32 locked until upstream changes.
    device = 0 if torch.cuda.is_available() else -1
    generator = pipeline(
        "mask-generation",
        model=MODEL_ID,
        device=device,
        dtype=torch.float32,
    )
    result = generator(source, points_per_batch=64)
    candidates = normalize_candidates(
        result["masks"], result["scores"], source.size, max_candidates=max_candidates
    )
    if not candidates:
        raise RuntimeError("SAM produced no usable mask candidates")
    return save_candidates(image_path, output_dir, candidates)


def build_parser():
    parser = argparse.ArgumentParser(description="Generate SAM 2.1 automatic mask candidates")
    parser.add_argument("--image", required=True, help="Source image")
    parser.add_argument("--output-dir", required=True, help="New or empty output directory")
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=DEFAULT_MAX_CANDIDATES,
        choices=range(1, 25),
        metavar="1..24",
    )
    return parser


def main():
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty output directory: {output_dir}")
    manifest = run_auto(args.image, output_dir, args.max_candidates)
    print(f"CANDIDATES={manifest['candidate_count']}")
    print(f"CONTACT_SHEET={output_dir.resolve() / 'contact_sheet.png'}")
    print(f"MANIFEST={output_dir.resolve() / 'manifest.json'}")


if __name__ == "__main__":
    main()

