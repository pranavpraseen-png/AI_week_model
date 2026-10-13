"""Turn a photo of a fingernail, palm or inner eyelid into a few numbers (features).

A regression model cannot look at a picture directly. It needs numbers, so this
file measures how red / pale the target region is, and also how the surrounding
skin looks, so the model can learn to correct for skin tone and camera colour.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# Colour of the target region (nail bed / eyelid) only.
# blue_chroma is left out on purpose: red + green + blue chroma always add up to 1,
# so it carries no new information.
BASIC_FEATURES = ["red_chroma", "green_chroma", "log_red_green", "brightness", "saturation"]

# The same target features plus the colour of the skin around it (the image border).
REFERENCE_FEATURES = BASIC_FEATURES + ["skin_red_chroma", "skin_log_red_green"]

FEATURE_SETS = {"basic": BASIC_FEATURES, "reference": REFERENCE_FEATURES}

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


def center_mask(height, width, fraction=0.5):
    """True for the middle `fraction` of the image, where the nail / eyelid usually is."""
    mask = np.zeros((height, width), dtype=bool)
    ch, cw = max(1, int(height * fraction)), max(1, int(width * fraction))
    top, left = (height - ch) // 2, (width - cw) // 2
    mask[top:top + ch, left:left + cw] = True
    return mask


def border_mask(height, width, fraction=0.12):
    """True for a thin frame around the edge of the image: the surrounding skin."""
    mask = np.zeros((height, width), dtype=bool)
    bh, bw = max(1, int(height * fraction)), max(1, int(width * fraction))
    mask[:bh, :] = mask[-bh:, :] = True
    mask[:, :bw] = mask[:, -bw:] = True
    return mask


def clean_pixels(pixels):
    """Drop shadow (too dark) and glare (blown-out white) pixels."""
    keep = (pixels.mean(axis=1) > 0.08) & (pixels.max(axis=1) < 0.98)
    return pixels[keep]


def color_stats(pixels):
    """Average colour measurements of an (N, 3) pixel array."""
    r, g = pixels[:, 0], pixels[:, 1]
    total = pixels.sum(axis=1) + EPS
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
    """Photo on disk -> dict with every feature in REFERENCE_FEATURES."""
    rgb = load_rgb(Path(image_path))
    h, w, _ = rgb.shape
    target = load_mask(Path(mask_path), h, w) if mask_path else center_mask(h, w, crop_fraction)

    target_pixels = clean_pixels(rgb[target])
    if len(target_pixels) < MIN_PIXELS:
        raise ValueError("Photo is too dark or too over-exposed to measure colour reliably.")
    features = color_stats(target_pixels)

    skin_pixels = clean_pixels(rgb[border_mask(h, w) & ~target])
    if len(skin_pixels) < MIN_PIXELS:  # e.g. the photo is a tight crop with no skin visible
        skin_pixels = target_pixels
    skin = color_stats(skin_pixels)
    features["skin_red_chroma"] = skin["red_chroma"]
    features["skin_log_red_green"] = skin["log_red_green"]
    return features
