"""Where to get REAL anaemia photos from different regions, and a helper to fetch them.

  python src/download_data.py --list             # show every dataset and how to get it
  python src/download_data.py --get ghana_nails  # try an automatic download

Most hosts need a browser click or a login, so automatic download may fail. When it
does, this script prints the manual steps. Put the unzipped files in data/raw/<name>/
and then run src/prepare_dataset.py to make a labels.csv.
"""
import argparse
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

DATASETS = {
    "ghana_nails": {
        "region": "ghana",
        "body_part": "fingernail",
        "people": "children under 5, 10 hospitals in Ghana",
        "page": "https://data.mendeley.com/datasets/2xx4j3kjg2/1",
        "zip": "https://prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com/2xx4j3kjg2-1.zip",
        "cite": "Asare, Appiahene, Donkoh (2022). Mendeley Data, doi:10.17632/2xx4j3kjg2.1",
    },
    "ghana_palm": {
        "region": "ghana",
        "body_part": "palm",
        "people": "children under 5, Ghana",
        "page": "https://data.mendeley.com/datasets/ccr8cm22vz/1",
        "zip": "https://prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com/ccr8cm22vz-1.zip",
        "cite": "Asare, Appiahene, Donkoh (2022). Mendeley Data, doi:10.17632/ccr8cm22vz.1",
    },
    "ghana_eyelid": {
        "region": "ghana",
        "body_part": "conjunctiva (inner eyelid)",
        "people": "children under 5, Ghana (710 images)",
        "page": "https://data.mendeley.com/datasets/nt7r8hv2pz/1",
        "zip": "https://prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com/nt7r8hv2pz-1.zip",
        "cite": "Asare et al. (2022). Mendeley Data, doi:10.17632/nt7r8hv2pz.1",
    },
    "eyes_defy_anemia": {
        "region": "india + italy (two sub-folders)",
        "body_part": "conjunctiva (inner eyelid), with hand-drawn masks",
        "people": "95 Indian + 123 Italian patients",
        "page": "https://ieee-dataport.org/documents/eyes-defy-anemia",
        "kaggle": "harshwardhanfartale/eyes-defy-anemia",
        "cite": "Dimauro et al. (2023). IEEE DataPort, Eyes-defy-anemia",
    },
    "russia_nails_skin": {
        "region": "russia",
        "body_part": "fingernail + hand skin",
        "people": "adults, Moscow (Yakimov et al., Scientific Data 2024)",
        "page": "https://www.nature.com/articles/s41597-024-03895-9",
        "cite": "Yakimov et al. (2024). Scientific Data 11, doi:10.1038/s41597-024-03895-9",
    },
}

MANUAL_STEPS = """Manual download for {name}:
  1. Open {page} in a browser (log in / accept terms if asked).
  2. Click "Download All" (Mendeley) / "Download" (IEEE, Kaggle) / follow the "Data availability" link (Nature).
  3. Unzip into: {target}
  4. Run src/prepare_dataset.py on it (see CLAUDE.md, "Getting real data")."""


def list_datasets():
    for name, d in DATASETS.items():
        print(f"{name}\n  region:    {d['region']}\n  body part: {d['body_part']}\n  people:    {d['people']}")
        print(f"  page:      {d['page']}")
        if "kaggle" in d:
            print(f"  kaggle:    kaggle datasets download -d {d['kaggle']} -p data/raw/{name} --unzip")
        print(f"  cite:      {d['cite']}\n")


def try_download(name, raw_dir):
    d = DATASETS[name]
    target = raw_dir / name
    manual = MANUAL_STEPS.format(name=name, page=d["page"], target=target)
    if "zip" not in d:
        print(manual)
        return False

    target.mkdir(parents=True, exist_ok=True)
    zip_path = target / f"{name}.zip"
    print(f"Downloading {d['zip']} ...")
    try:
        with urllib.request.urlopen(d["zip"], timeout=120) as response, open(zip_path, "wb") as f:
            shutil.copyfileobj(response, f)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(target)
    except (urllib.error.URLError, zipfile.BadZipFile, TimeoutError, OSError) as err:
        print(f"Automatic download failed ({err}).\n")
        zip_path.unlink(missing_ok=True)
        print(manual)
        return False
    zip_path.unlink()
    print(f"Done: files are in {target}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--get", choices=list(DATASETS))
    parser.add_argument("--raw-dir", default="data/raw")
    args = parser.parse_args()
    if args.get:
        try_download(args.get, Path(args.raw_dir))
    else:
        list_datasets()


if __name__ == "__main__":
    main()
