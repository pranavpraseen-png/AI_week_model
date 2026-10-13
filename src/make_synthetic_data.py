"""Make FAKE fingernail-like photos with a known Hb value, to test the pipeline.

The real datasets have to be downloaded by hand (see CLAUDE.md). Until then, this
lets every script run end to end. Results on synthetic data prove the code works.
They say nothing about real anaemia, so never present them as real results.
"""
import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image

PALE = np.array([238, 214, 205], dtype=np.float64)  # low Hb: pale pink
RED = np.array([214, 112, 112], dtype=np.float64)  # high Hb: well-perfused red
HB_MIN, HB_MAX = 6.0, 17.0


def make_image(hb, rng, size=96):
    t = np.clip((hb - HB_MIN) / (HB_MAX - HB_MIN), 0, 1)
    color = PALE * (1 - t) + RED * t

    tone = rng.uniform(0.6, 1.0)  # darker or lighter skin around the nail
    light = rng.uniform(0.75, 1.15)  # dim room vs bright window
    tint = rng.normal(1.0, 0.04, size=3)  # warm vs cool phone camera
    color = color * tone * light * tint

    img = np.tile(color, (size, size, 1))
    img += rng.normal(0, 10, size=img.shape)  # camera sensor noise

    # One bright glare spot, which features.py should ignore.
    cy, cx = rng.integers(size // 4, 3 * size // 4, size=2)
    img[cy - 3:cy + 3, cx - 3:cx + 3] = 255
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=300, help="number of images")
    parser.add_argument("--out", default="data/synthetic", help="output folder")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)

    rows = []
    for i in range(args.n):
        hb = float(np.clip(rng.normal(11.5, 2.2), HB_MIN, HB_MAX))
        sex = rng.choice(["F", "M"], p=[0.7, 0.3])
        age = int(rng.integers(15, 50))
        name = f"images/synthetic_{i:04d}.png"
        make_image(hb, rng).save(out / name)
        rows.append({"image": name, "hb": round(hb, 1), "sex": sex, "age": age})

    with open(out / "labels.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "hb", "sex", "age"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} synthetic images and {out / 'labels.csv'}")


if __name__ == "__main__":
    main()
