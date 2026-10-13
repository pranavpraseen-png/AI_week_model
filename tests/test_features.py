import numpy as np
import pytest
from PIL import Image

from features import REFERENCE_FEATURES, extract_features


def save(tmp_path, array, name="img.png"):
    path = tmp_path / name
    Image.fromarray(np.clip(array, 0, 255).astype(np.uint8)).save(path)
    return path


def solid(color, size=64):
    return np.tile(np.array(color, dtype=np.float64), (size, size, 1))


def test_returns_every_feature(tmp_path):
    feats = extract_features(save(tmp_path, solid([200, 120, 120])))
    assert set(feats) == set(REFERENCE_FEATURES)


def test_redder_photo_has_higher_red_chroma(tmp_path):
    red = extract_features(save(tmp_path, solid([210, 110, 110]), "red.png"))
    pale = extract_features(save(tmp_path, solid([235, 215, 205]), "pale.png"))
    assert red["red_chroma"] > pale["red_chroma"]
    assert red["log_red_green"] > pale["log_red_green"]


def test_chroma_ignores_overall_brightness(tmp_path):
    bright = extract_features(save(tmp_path, solid([200, 120, 120]), "bright.png"))
    dim = extract_features(save(tmp_path, solid([100, 60, 60]), "dim.png"))
    assert dim["red_chroma"] == pytest.approx(bright["red_chroma"], abs=0.005)
    assert dim["brightness"] < bright["brightness"]


def test_glare_pixels_are_ignored(tmp_path):
    clean = solid([200, 120, 120])
    glare = clean.copy()
    glare[28:36, 28:36] = 255
    a = extract_features(save(tmp_path, clean, "clean.png"))
    b = extract_features(save(tmp_path, glare, "glare.png"))
    assert b["red_chroma"] == pytest.approx(a["red_chroma"], abs=1e-6)


def test_black_photo_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        extract_features(save(tmp_path, solid([5, 5, 5])))


def test_skin_features_come_from_the_border(tmp_path):
    img = solid([120, 80, 60])  # darker skin all around
    img[16:48, 16:48] = [210, 110, 110]  # red nail in the middle
    feats = extract_features(save(tmp_path, img))
    assert feats["skin_red_chroma"] == pytest.approx(120 / 260, abs=0.01)
    assert feats["red_chroma"] == pytest.approx(210 / 430, abs=0.01)


def test_mask_selects_the_region(tmp_path):
    img = solid([235, 215, 205])
    img[:, :32] = [210, 110, 110]  # left half red
    mask = np.zeros((64, 64))
    mask[:, :32] = 255
    feats = extract_features(save(tmp_path, img), save(tmp_path, mask, "mask.png"))
    assert feats["red_chroma"] == pytest.approx(210 / 430, abs=0.01)
