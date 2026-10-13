import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

SRC = Path(__file__).resolve().parent.parent / "src"


def test_spreadsheet_rows_are_matched_to_photos(tmp_path):
    images = tmp_path / "raw" / "photos"
    images.mkdir(parents=True)
    for name in ["IMG_001.jpg", "IMG_002.png"]:
        Image.fromarray(np.full((8, 8, 3), 200, dtype=np.uint8)).save(images / name)
    sheet = tmp_path / "raw" / "meta.xlsx"
    pd.DataFrame({
        "Photo": ["IMG_001", "IMG_002.png", "IMG_404"],  # without extension, with extension, missing
        "Hb": [9.5, 13.1, 11.0],
        "Sex": ["F", "M", "F"],
    }).to_excel(sheet, index=False)

    out = tmp_path / "ready" / "labels.csv"
    subprocess.run([sys.executable, str(SRC / "prepare_dataset.py"), "--images-dir", str(images),
                    "--sheet", str(sheet), "--image-col", "Photo", "--hb-col", "Hb", "--sex-col", "Sex",
                    "--region", "ghana", "--out", str(out)], check=True, capture_output=True)

    labels = pd.read_csv(out)
    assert list(labels["hb"]) == [9.5, 13.1]  # the missing photo is skipped
    assert set(labels["region"]) == {"ghana"}
    assert all((out.parent / p).exists() for p in labels["image"])  # paths relative to labels.csv
