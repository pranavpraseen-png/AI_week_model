"""Does a model trained in one place still work somewhere else?

  python src/cross_region.py --data data/simulated/labels.csv
  python src/cross_region.py --data data/ghana_nails/labels.csv data/eyes_defy_anemia/labels.csv

Two tests, for each feature set:
  * leave-one-region-out: train on every region except one, test on the one left out
  * region matrix: train on region A only, test on region B (every pair)
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from dataset import load_table, region_counts
from evaluate import regression_metrics, screening_metrics
from features import FEATURE_SETS
from linear_regression import LinearRegression


def fit_and_score(train, test, feature_names):
    model = LinearRegression.from_exact(train[feature_names].to_numpy(), train["hb"].to_numpy())
    pred = model.predict(test[feature_names].to_numpy())
    return {**regression_metrics(test["hb"], pred),
            **screening_metrics(test["hb"], pred, test["threshold"].to_numpy())}


def leave_one_region_out(table, feature_names):
    results = {}
    for region in sorted(table["region"].unique()):
        held_out = table["region"] == region
        results[region] = fit_and_score(table[~held_out], table[held_out], feature_names)
    return results


def region_matrix(table, feature_names, seed=0):
    """MAE when training on one region (rows) and testing on another (columns).
    On the diagonal, the region is split 80/20 so the model is never tested on its own training photos."""
    regions = sorted(table["region"].unique())
    rng = np.random.default_rng(seed)
    mae = np.zeros((len(regions), len(regions)))
    for i, a in enumerate(regions):
        rows_a = table[table["region"] == a]
        order = rng.permutation(len(rows_a))
        cut = int(len(rows_a) * 0.8)
        train_a, test_a = rows_a.iloc[order[:cut]], rows_a.iloc[order[cut:]]
        for j, b in enumerate(regions):
            test = test_a if a == b else table[table["region"] == b]
            mae[i, j] = fit_and_score(train_a, test, feature_names)["MAE"]
    return regions, mae


def format_loro(results):
    lines = ["| held-out region | bias (g/dL) | MAE | R² | sensitivity | specificity |",
             "|---|---|---|---|---|---|"]
    for region, r in results.items():
        lines.append(f"| {region} | {r['bias']:+.2f} | {r['MAE']:.2f} | {r['R2']:+.2f} | "
                     f"{r['sensitivity']:.2f} | {r['specificity']:.2f} |")
    return "\n".join(lines)


def format_matrix(regions, mae):
    lines = ["| train ↓ / test → | " + " | ".join(regions) + " |", "|---" * (len(regions) + 1) + "|"]
    for i, a in enumerate(regions):
        lines.append(f"| **{a}** | " + " | ".join(f"{v:.2f}" for v in mae[i]) + " |")
    return "\n".join(lines)


def plot_matrices(matrices, path):
    fig, axes = plt.subplots(1, len(matrices), figsize=(5.2 * len(matrices), 4.4), layout="constrained")
    axes = np.atleast_1d(axes)
    vmax = max(m.max() for _, (_, m) in matrices.items())
    for ax, (name, (regions, mae)) in zip(axes, matrices.items()):
        im = ax.imshow(mae, cmap="Reds", vmin=0, vmax=vmax)
        ax.set_xticks(range(len(regions)), regions)
        ax.set_yticks(range(len(regions)), regions)
        ax.set_xlabel("tested on")
        if ax is axes[0]:
            ax.set_ylabel("trained on")
        ax.set_title(f"MAE (g/dL), features: {name}")
        for i in range(len(regions)):
            for j in range(len(regions)):
                color = "white" if mae[i, j] > 0.55 * vmax else "black"
                ax.text(j, i, f"{mae[i, j]:.2f}", ha="center", va="center", fontsize=9, color=color)
    fig.colorbar(im, ax=axes.tolist(), shrink=0.8)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", nargs="+", required=True)
    parser.add_argument("--crop", type=float, default=0.5)
    parser.add_argument("--reports", default="reports")
    args = parser.parse_args()

    table = load_table(args.data, args.crop)
    if table["region"].nunique() < 2:
        raise SystemExit("Need photos from at least two regions (add a `region` column or use several CSVs).")
    print(f"{len(table)} photos from regions: {region_counts(table)}\n")

    output, matrices = {}, {}
    for name, feature_names in FEATURE_SETS.items():
        loro = leave_one_region_out(table, feature_names)
        regions, mae = region_matrix(table, feature_names)
        matrices[name] = (regions, mae)
        output[name] = {"leave_one_region_out": loro, "matrix_regions": regions, "matrix_mae": mae.tolist()}
        print(f"=== features: {name} ===\nLeave one region out:\n{format_loro(loro)}\n")
        print(f"Train on one region, test on another (MAE):\n{format_matrix(regions, mae)}\n")

    reports = Path(args.reports)
    reports.mkdir(parents=True, exist_ok=True)
    plot_matrices(matrices, reports / "cross_region.png")
    (reports / "cross_region.json").write_text(json.dumps(output, indent=2))
    print(f"Saved {reports / 'cross_region.png'} and {reports / 'cross_region.json'}")


if __name__ == "__main__":
    main()
