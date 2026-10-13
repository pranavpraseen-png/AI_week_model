"""Make SIMULATED fingernail photos from several regions, each with a known Hb value.

Why: the real datasets must be downloaded by hand (see src/download_data.py), and
this lets every script run and be tested before that. Each simulated region has its
own skin-tone range, phone-camera colour cast and typical Hb level, to imitate how
data from Ghana, India, Italy and Russia differ.

Results on simulated photos prove the CODE works. They say nothing about how well
real anaemia detection works, so never present them as real results.
"""
import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image

PALE_NAIL = np.array([238, 214, 205], dtype=np.float64)  # low Hb: pale pink
RED_NAIL = np.array([214, 112, 112], dtype=np.float64)  # high Hb: well-perfused red
LIGHT_SKIN = np.array([236, 200, 180], dtype=np.float64)
HB_MIN, HB_MAX = 5.0, 18.0

# Melanin absorbs blue and green light more than red, so darker skin both darkens
# and shifts the colour. The nail bed is only lightly affected; the skin a lot.
MELANIN_ABSORPTION = np.array([0.6, 1.0, 1.4])
NAIL_MELANIN_SHARE = 0.25

REGIONS = {
    # melanin: skin pigment range; camera: typical phone colour cast; hb: mean, sd; people
    "ghana": {"melanin": (0.9, 1.6), "camera": (1.03, 1.00, 0.95), "hb": (10.2, 1.8), "group": "child"},
    "india": {"melanin": (0.5, 1.2), "camera": (1.00, 1.00, 1.00), "hb": (11.0, 2.0), "group": "woman"},
    "italy": {"melanin": (0.0, 0.5), "camera": (0.97, 1.00, 1.04), "hb": (12.6, 1.8), "group": "adult"},
    "russia": {"melanin": (0.0, 0.4), "camera": (1.00, 1.01, 1.03), "hb": (13.2, 1.7), "group": "adult"},
}


def nail_color(hb):
    t = np.clip((hb - HB_MIN) / (HB_MAX - HB_MIN), 0, 1)
    return PALE_NAIL * (1 - t) + RED_NAIL * t


def make_image(hb, region, rng, size=96):
    cfg = REGIONS[region]
    melanin = rng.uniform(*cfg["melanin"])
    camera = np.array(cfg["camera"]) * rng.normal(1.0, 0.02, size=3)  # this phone, this room
    light = rng.uniform(0.75, 1.15)  # dim room vs bright window

    skin = LIGHT_SKIN * np.exp(-melanin * MELANIN_ABSORPTION)
    nail = nail_color(hb) * np.exp(-NAIL_MELANIN_SHARE * melanin * MELANIN_ABSORPTION)

    yy, xx = np.mgrid[0:size, 0:size]
    inside_nail = ((yy - size / 2) / (size * 0.37)) ** 2 + ((xx - size / 2) / (size * 0.36)) ** 2 <= 1
    img = np.where(inside_nail[..., None], nail, skin) * camera * light
    img = img + rng.normal(0, 8, size=img.shape)  # camera sensor noise

    # One bright glare spot on the nail, which features.py should ignore.
    cy, cx = rng.integers(int(size * 0.4), int(size * 0.6), size=2)
    img[cy - 3:cy + 3, cx - 3:cx + 3] = 255
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def person(region, rng):
    group = REGIONS[region]["group"]
    if group == "child":
        return str(rng.choice(["F", "M"])), int(rng.integers(1, 5))
    if group == "woman":
        return "F", int(rng.integers(15, 50))
    return str(rng.choice(["F", "M"])), int(rng.integers(18, 70))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--regions", nargs="+", default=list(REGIONS), choices=list(REGIONS))
    parser.add_argument("--n-per-region", type=int, default=150)
    parser.add_argument("--out", default="data/simulated")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)

    rows = []
    for region in args.regions:
        mean, sd = REGIONS[region]["hb"]
        for i in range(args.n_per_region):
            hb = float(np.clip(rng.normal(mean, sd), HB_MIN + 1, HB_MAX - 1))
            sex, age = person(region, rng)
            name = f"images/{region}_{i:04d}.png"
            make_image(hb, region, rng).save(out / name)
            rows.append({"image": name, "hb": round(hb, 1), "sex": sex, "age": age, "region": region})

    with open(out / "labels.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "hb", "sex", "age", "region"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} SIMULATED images ({', '.join(args.regions)}) and {out / 'labels.csv'}")


if __name__ == "__main__":
    main()
