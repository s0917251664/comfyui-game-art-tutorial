import io
import re
from pathlib import Path

from PIL import Image


TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
MAX_IMAGE_BYTES = 40 * 1024 * 1024
MAX_SIDE = 16384
MAX_PIXELS = 80_000_000


def validate_token(token):
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        raise ValueError("invalid session token")
    return token


def load_source_image(data):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("image is empty or exceeds 40 MiB")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise ValueError("unsupported or damaged image") from exc
    if image.width < 1 or image.height < 1:
        raise ValueError("image has invalid dimensions")
    if image.width > MAX_SIDE or image.height > MAX_SIDE or image.width * image.height > MAX_PIXELS:
        raise ValueError("image dimensions exceed the safety limit")
    return image.convert("RGBA")


def normalize_editor_mask(mask_data, expected_size):
    if not mask_data or len(mask_data) > MAX_IMAGE_BYTES:
        raise ValueError("mask is empty or exceeds 40 MiB")
    try:
        mask = Image.open(io.BytesIO(mask_data))
        mask.load()
    except Exception as exc:
        raise ValueError("mask is not a valid PNG") from exc
    if mask.size != tuple(expected_size):
        raise ValueError(f"mask size {mask.size} does not match source {tuple(expected_size)}")
    if mask.mode == "RGBA":
        # The editor exports white paint on an opaque black canvas. Alpha is
        # deliberately ignored so browsers cannot silently invert semantics.
        mask = mask.convert("RGB").convert("L")
    else:
        mask = mask.convert("L")
    return mask


def selected_ratio(mask):
    histogram = mask.histogram()
    weighted = sum(value * count for value, count in enumerate(histogram))
    return weighted / (255.0 * mask.width * mask.height)


def build_outputs(source, editor_mask):
    source = source.convert("RGBA")
    mask = editor_mask.convert("L")
    if source.size != mask.size:
        raise ValueError("source and mask dimensions differ")

    # Existing generate.py inpaint/layer_split contract: selected pixels must
    # have alpha=0, unselected pixels alpha=255.
    inverse_alpha = mask.point(lambda value: 255 - value)
    comfy_mask = Image.new("RGBA", source.size, (255, 255, 255, 255))
    comfy_mask.putalpha(inverse_alpha)

    red = Image.new("RGBA", source.size, (255, 48, 48, 0))
    red.putalpha(mask.point(lambda value: round(value * 0.55)))
    preview = Image.alpha_composite(source, red)
    return mask, comfy_mask, preview


def save_png(image, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path

