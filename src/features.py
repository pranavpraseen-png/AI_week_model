"""Turn a photo of a fingernail, palm or inner eyelid into a few numbers (features).

A regression model cannot look at a picture directly. It needs numbers, so this
file measures how red / pale the skin region is.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# blue_chroma is left out on purpose: red + green + blue chroma always add up to 1,
# so it carries no new information and would confuse multi-feature regression.
FEATURE_NAMES = ["red_chroma", "green_chroma", "log_red_green", "brightness", "saturation"]

MIN_PIXELS = 50
EPS = 1e-6


def load_rgb(path, max_side=512):
    """Open an image as an (H, W, 3) array of floats between 0 and 1."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # phone photos store their rotation in EXIF
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))  # smaller = faster, colour averages barely change
    return np.asarray(img, dtype=np.float64) / 255.0


def load_mask(path, height, width):
    """Open a black/white mask and resize it to match the photo. White = use this pixel."""
    mask = Image.open(path).convert("L").resize((width, height), Image.NEAREST)
    return np.asarray(mask) > 127


def center_crop(rgb, fraction=0.5):
    """Keep the middle `fraction` of the image, where the nail / eyelid usually is."""
    h, w, _ = rgb.shape
    ch, cw = max(1, int(h * fraction)), max(1, int(w * fraction))
    top, left = (h - ch) // 2, (w - cw) // 2
    return rgb[top:top + ch, left:left + cw]


def region_pixels(rgb, mask=None, crop_fraction=0.5):
    """Return the (N, 3) list of pixels we trust: inside the region, not shadow, not glare."""
    if mask is not None:
        pixels = rgb[mask]
    else:
        pixels = center_crop(rgb, crop_fraction).reshape(-1, 3)

    brightness = pixels.mean(axis=1)
    keep = (brightness > 0.08) & (pixels.max(axis=1) < 0.98)
    if keep.sum() < MIN_PIXELS:
        raise ValueError("Photo is too dark or too over-exposed to measure colour reliably.")
    return pixels[keep]


def features_from_pixels(pixels):
    """Compute the colour features from an (N, 3) pixel array."""
    r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    total = r + g + b + EPS
    max_c = pixels.max(axis=1)
    min_c = pixels.min(axis=1)
    return {
        "red_chroma": float((r / total).mean()),
        "green_chroma": float((g / total).mean()),
        "log_red_green": float(np.log((r + EPS) / (g + EPS)).mean()),
        "brightness": float(pixels.mean()),
        "saturation": float(((max_c - min_c) / (max_c + EPS)).mean()),
    }


def extract_features(image_path, mask_path=None, crop_fraction=0.5):
    """Photo on disk -> dict of feature name -> number."""
    rgb = load_rgb(Path(image_path))
    mask = None
    if mask_path:
        mask = load_mask(Path(mask_path), rgb.shape[0], rgb.shape[1])
    return features_from_pixels(region_pixels(rgb, mask, crop_fraction))
