"""Load one or more labels.csv files and turn every photo into a row of features."""
from pathlib import Path

import pandas as pd

from evaluate import who_threshold
from features import REFERENCE_FEATURES, extract_features


def load_table(csv_paths, crop_fraction=0.5, verbose=True):
    """Read labels.csv file(s), add one column per feature plus the WHO cut-off.

    Every row needs `image` and `hb`. Optional: sex, age, pregnant, mask, region.
    If `region` is missing, the CSV's folder name is used, so data from different
    places stays labelled. Photos that cannot be read are skipped with a message.
    """
    if isinstance(csv_paths, (str, Path)):
        csv_paths = [csv_paths]

    tables = []
    for csv_path in map(Path, csv_paths):
        table = pd.read_csv(csv_path)
        if "region" not in table.columns:
            table["region"] = csv_path.parent.name
        feature_rows, keep = [], []
        for i, row in table.iterrows():
            mask = row.get("mask")
            mask_path = csv_path.parent / mask if isinstance(mask, str) and mask else None
            try:
                feature_rows.append(extract_features(csv_path.parent / row["image"], mask_path, crop_fraction))
                keep.append(i)
            except (OSError, ValueError) as err:
                if verbose:
                    print(f"  skipping {row['image']}: {err}")
        table = table.loc[keep].reset_index(drop=True)
        tables.append(pd.concat([table, pd.DataFrame(feature_rows, columns=REFERENCE_FEATURES)], axis=1))

    table = pd.concat(tables, ignore_index=True)
    table["threshold"] = [
        who_threshold(r.get("sex"), r.get("age"), is_yes(r.get("pregnant"))) for _, r in table.iterrows()
    ]
    return table


def is_yes(value):
    """True for 1 / yes / true / y; False for blanks and everything else."""
    return str(value).strip().lower() in {"1", "1.0", "true", "yes", "y"}


def region_counts(table):
    """{'ghana': 150, 'india': 150, ...} for printing."""
    return {region: int(n) for region, n in table["region"].value_counts().sort_index().items()}
