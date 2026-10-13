"""Convert a downloaded dataset (photos + a spreadsheet) into the labels.csv format we train on.

labels.csv columns: image, hb, and optionally sex, age, region, mask. Paths are relative to labels.csv.

Example (column names depend on the dataset; open its spreadsheet and check):
  python src/prepare_dataset.py --images-dir data/raw/ghana_nails/images \
      --sheet data/raw/ghana_nails/metadata.xlsx --image-col "IMAGE_ID" --hb-col "Hb" \
      --sex-col "Sex" --age-col "Age" --region ghana --out data/ghana_nails/labels.csv
"""
import argparse
import os
from pathlib import Path

import pandas as pd

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def index_images(images_dir):
    """Map file name and file stem (name without extension) to the full path."""
    index = {}
    for path in Path(images_dir).rglob("*"):
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            index.setdefault(path.name.lower(), path)
            index.setdefault(path.stem.lower(), path)
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images-dir", required=True)
    parser.add_argument("--sheet", required=True, help=".csv or .xlsx with one row per photo")
    parser.add_argument("--image-col", required=True, help="column holding the photo file name or ID")
    parser.add_argument("--hb-col", required=True, help="column holding haemoglobin in g/dL")
    parser.add_argument("--sex-col")
    parser.add_argument("--age-col")
    parser.add_argument("--region", help="where the photos come from, e.g. ghana, india, italy")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    sheet = Path(args.sheet)
    table = pd.read_excel(sheet) if sheet.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(sheet)
    print("Columns found in the sheet:", list(table.columns))

    index = index_images(args.images_dir)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows, missing = [], 0
    for _, row in table.iterrows():
        key = str(row[args.image_col]).strip().lower()
        path = index.get(key) or index.get(Path(key).stem)
        hb = pd.to_numeric(row[args.hb_col], errors="coerce")
        if path is None or pd.isna(hb):
            missing += 1
            continue
        record = {"image": os.path.relpath(path, out.parent), "hb": float(hb)}
        if args.sex_col:
            record["sex"] = row[args.sex_col]
        if args.age_col:
            record["age"] = row[args.age_col]
        if args.region:
            record["region"] = args.region
        rows.append(record)

    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Wrote {len(rows)} rows to {out} ({missing} rows skipped: photo not found or Hb missing)")


if __name__ == "__main__":
    main()
