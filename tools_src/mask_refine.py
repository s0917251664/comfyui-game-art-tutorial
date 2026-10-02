"""Optional image-guided refinement of a user-painted selected-white mask.

Independent of SAM and the manual editor. Only the uncertain inner boundary
band is reconsidered by GrabCut; pixels outside the rough mask never expand.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter


def refine_mask(source, rough, radius=16, shrink=0, feather=1):
    import cv2  # Optional dependency: the manual editor works without OpenCV.

    for name, value, maximum in (("radius", radius, 64), ("shrink", shrink, 16), ("feather", feather, 16)):
        if isinstance(value, bool) or not isinstance(value, int) or not (1 if name == "radius" else 0) <= value <= maximum:
            raise ValueError(f"{name} must be an integer in {1 if name == 'radius' else 0}..{maximum}")
    if source.size != rough.size:
        raise ValueError("Source and rough mask dimensions differ")
    source, rough = source.convert("RGBA"), rough.convert("L")
    rough_array = np.asarray(rough)
    selected = (rough_array >= 128) & (np.asarray(source.getchannel("A")) > 0)
    if not selected.any():
        raise ValueError("請先把要保留的物件內部塗滿，再貼合邊界")
    yy, xx = np.where(selected)
    margin = radius + 8
    box = (max(0, int(xx.min()) - margin), max(0, int(yy.min()) - margin),
           min(source.width, int(xx.max()) + margin + 1), min(source.height, int(yy.max()) + margin + 1))
    x0, y0, x1, y1 = box
    if (x1 - x0) * (y1 - y0) > 4_000_000:
        raise ValueError("這次範圍太大，請分成較小區域貼合（候選區上限 400 萬像素）")
    area = selected[y0:y1, x0:x1].astype(np.uint8)
    distance = cv2.distanceTransform(np.pad(area, 1), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)[1:-1, 1:-1]
    sure = distance > radius
    # Narrow strokes get a central core, but a single-pixel outline is not a filled selection.
    if not sure.any():
        sure = distance >= max(1.5, float(distance.max()) * 0.6)
    if sure.sum() < 5 or not (area == 0).any():
        raise ValueError("請塗滿物件內部並留一些未選背景；目前沒有足夠的前景／背景線索")
    # Composite transparent source onto white before fitting color models.
    rgba = source.crop(box)
    rgb = Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba).convert("RGB")
    labels = np.where(area, cv2.GC_PR_FGD, cv2.GC_BGD).astype(np.uint8)
    labels[sure] = cv2.GC_FGD
    labels[np.asarray(rgba.getchannel("A")) == 0] = cv2.GC_BGD
    bg_model, fg_model = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.setRNGSeed(0)
    try:
        cv2.grabCut(np.asarray(rgb), labels, None, bg_model, fg_model, 5, cv2.GC_INIT_WITH_MASK)
    except cv2.error as exc:
        raise ValueError("這張圖的色彩線索不足以貼合，請縮小範圍或改用橡皮擦微調") from exc
    keep = ((labels == cv2.GC_FGD) | (labels == cv2.GC_PR_FGD)) & (area > 0)
    if shrink:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (shrink * 2 + 1, shrink * 2 + 1))
        keep = cv2.erode(keep.astype(np.uint8), kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0) > 0
    candidate = Image.new("L", source.size, 0)
    candidate.paste(Image.fromarray(keep.astype(np.uint8) * 255), (x0, y0))
    if feather:
        candidate = ImageChops.darker(candidate, candidate.filter(ImageFilter.GaussianBlur(feather)))
    candidate = ImageChops.darker(candidate, rough)
    if not candidate.getbbox():
        raise ValueError("調整後沒有選取範圍，請降低內縮或重新塗選")
    values = np.asarray(candidate)
    assert np.all(values <= rough_array)
    return candidate, {
        "method": "grabcut_inner_boundary", "radius": radius, "shrink": shrink, "feather": feather,
        "original_selected_pixels": int((rough_array > 0).sum()),
        "candidate_selected_pixels": int((values > 0).sum()),
        "expanded_pixels": 0, "status": "candidate", "processing_box": list(box),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--mask", required=True, help="Selected-white grayscale PNG, not Comfy Alpha mask")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--radius", type=int, default=16)
    parser.add_argument("--shrink", type=int, default=0)
    parser.add_argument("--feather", type=int, default=1)
    args = parser.parse_args(argv)
    from simple_mask_tool.core import build_outputs, load_source_image, normalize_editor_mask, save_png
    try:
        out = Path(args.output_dir).resolve()
        if out.exists():
            raise ValueError("Output directory already exists; choose a new destination")
        source = load_source_image(Path(args.image).read_bytes())
        rough = normalize_editor_mask(Path(args.mask).read_bytes(), source.size)
        candidate, info = refine_mask(source, rough, args.radius, args.shrink, args.feather)
        out.mkdir(parents=True, exist_ok=False)
        editor, comfy, preview = build_outputs(source, candidate)
        for image, name in ((editor, "mask_editor.png"), (comfy, "mask_comfy.png"), (preview, "preview.png")):
            save_png(image, out / name)
        info.update(source=str(Path(args.image).resolve()), rough_mask=str(Path(args.mask).resolve()),
                    dimensions=list(source.size), mask_contract="selected alpha=0; preserved alpha=255")
        (out / "manifest.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(info, ensure_ascii=False))
        return 0
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
