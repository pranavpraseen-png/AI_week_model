"""Train the haemoglobin regression model and report how well it works.

  python src/train.py --data data/synthetic/labels.csv
  python src/train.py --data data/ghana_nails/labels.csv --test-data data/india/labels.csv
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files; no screen needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate import regression_metrics, screening_metrics, who_threshold
from features import FEATURE_NAMES, extract_features
from linear_regression import LinearRegression, fit_least_squares, fit_simple


def load_table(csv_path, crop_fraction):
    """Read labels.csv and add one column per feature. Unreadable photos are skipped."""
    csv_path = Path(csv_path)
    table = pd.read_csv(csv_path)
    feature_rows, keep = [], []
    for i, row in table.iterrows():
        mask = row.get("mask")
        mask_path = csv_path.parent / mask if isinstance(mask, str) and mask else None
        try:
            feature_rows.append(extract_features(csv_path.parent / row["image"], mask_path, crop_fraction))
            keep.append(i)
        except (OSError, ValueError) as err:
            print(f"  skipping {row['image']}: {err}")
    table = table.loc[keep].reset_index(drop=True)
    features = pd.DataFrame(feature_rows, columns=FEATURE_NAMES)
    table = pd.concat([table, features], axis=1)
    table["threshold"] = [
        who_threshold(r.get("sex"), r.get("age"), bool(r.get("pregnant", False))) for _, r in table.iterrows()
    ]
    return table


def split(table, test_size, seed):
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(table))
    n_test = max(1, int(len(table) * test_size))
    return table.iloc[order[n_test:]].reset_index(drop=True), table.iloc[order[:n_test]].reset_index(drop=True)


def print_metrics(name, reg, scr):
    print(f"  {name:<28} MAE {reg['MAE']:.2f}  RMSE {reg['RMSE']:.2f}  R² {reg['R2']:.3f}  "
          f"sensitivity {scr['sensitivity']:.2f}  specificity {scr['specificity']:.2f}")


def save_plots(train, test, best, m, b, model, reports):
    reports.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.scatter(train[best], train["hb"], s=12, alpha=0.5, label="train")
    ax.scatter(test[best], test["hb"], s=12, alpha=0.8, label="test")
    xs = np.linspace(min(train[best].min(), test[best].min()), max(train[best].max(), test[best].max()), 100)
    ax.plot(xs, m * xs + b, color="black", label=f"Hb = {m:.2f}·x + {b:.2f}")
    ax.axhline(12.0, color="gray", linestyle="--", linewidth=1, label="WHO cut-off (women) 12 g/dL")
    ax.set_xlabel(best)
    ax.set_ylabel("haemoglobin (g/dL)")
    ax.set_title("Simple regression: y = mx + b")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(reports / "fit_line.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(model.loss_history_)
    ax.set_yscale("log")
    ax.set_xlabel("epoch")
    ax.set_ylabel("mean squared error (log scale)")
    ax.set_title("Gradient descent: loss going down = model learning")
    fig.tight_layout()
    fig.savefig(reports / "loss_curve.png", dpi=120)
    plt.close(fig)

    pred = model.predict(test[FEATURE_NAMES].to_numpy())
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(test["hb"], pred, s=14)
    lo, hi = float(min(test["hb"].min(), pred.min())), float(max(test["hb"].max(), pred.max()))
    ax.plot([lo, hi], [lo, hi], color="black", linewidth=1, label="perfect prediction")
    ax.set_xlabel("true Hb (lab)")
    ax.set_ylabel("predicted Hb (photo)")
    ax.set_title("Test set: predicted vs true")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(reports / "pred_vs_true.png", dpi=120)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, help="labels.csv to train on")
    parser.add_argument("--test-data", help="optional labels.csv from a DIFFERENT population to test on")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=3000)
    parser.add_argument("--crop", type=float, default=0.5, help="centre crop fraction when no mask is given")
    parser.add_argument("--model-out", default="models/model.json")
    parser.add_argument("--reports", default="reports")
    args = parser.parse_args()

    print("1. Extracting colour features from photos...")
    table = load_table(args.data, args.crop)
    if args.test_data:
        train = table
        test = load_table(args.test_data, args.crop)
        print(f"   cross-population test: train on {args.data}, test on {args.test_data}")
    else:
        train, test = split(table, args.test_size, args.seed)
    print(f"   {len(train)} training photos, {len(test)} test photos")
    if len(train) < 5 or len(test) < 2:
        raise SystemExit("Not enough usable photos to train and test.")

    print("\n2. How strongly does each feature move with Hb? (correlation, -1 to +1, training set only)")
    correlations = {name: float(np.corrcoef(train[name], train["hb"])[0, 1]) for name in FEATURE_NAMES}
    for name, r in sorted(correlations.items(), key=lambda kv: -abs(kv[1])):
        print(f"   {name:<15} {r:+.3f}")
    best = max(correlations, key=lambda k: abs(correlations[k]))

    print(f"\n3. Simple regression on the best single feature ({best}):")
    m, b = fit_simple(train[best], train["hb"])
    print(f"   Hb = {m:.3f} × {best} + {b:.3f}")

    print("\n4. Multi-feature regression with gradient descent:")
    X_train = train[FEATURE_NAMES].to_numpy()
    model = LinearRegression(args.learning_rate, args.epochs).fit(X_train, train["hb"].to_numpy())
    slopes, intercept = model.original_units()
    terms = " + ".join(f"({s:.3f} × {n})" for s, n in zip(slopes, FEATURE_NAMES))
    print(f"   Hb = {terms} + {intercept:.3f}")
    print(f"   loss: {model.loss_history_[0]:.2f} at start -> {model.loss_history_[-1]:.4f} at the end")

    exact_slopes, exact_intercept = fit_least_squares(X_train, train["hb"].to_numpy())
    gap = float(np.abs(model.predict(X_train) - (X_train @ exact_slopes + exact_intercept)).max())
    print(f"   check against NumPy exact solution: largest difference {gap:.4f} g/dL "
          f"({'OK' if gap < 0.05 else 'not converged - try more --epochs'})")

    print("\n5. Test-set results (photos the model never saw):")
    y_test = test["hb"].to_numpy()
    candidates = {
        "baseline (always guess mean)": np.full(len(test), train["hb"].mean()),
        f"simple y=mx+b ({best})": m * test[best].to_numpy() + b,
        "multi-feature": model.predict(test[FEATURE_NAMES].to_numpy()),
    }
    results = {}
    for name, pred in candidates.items():
        reg = regression_metrics(y_test, pred)
        scr = screening_metrics(y_test, pred, test["threshold"].to_numpy())
        print_metrics(name, reg, scr)
        results[name] = {"regression": reg, "screening": scr}

    train_rmse = regression_metrics(train["hb"], model.predict(X_train))["RMSE"]
    test_rmse = results["multi-feature"]["regression"]["RMSE"]

    model_path = Path(args.model_out)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(json.dumps({
        "feature_names": FEATURE_NAMES,
        "crop_fraction": args.crop,
        "simple": {"feature": best, "m": m, "b": b},
        "multi": model.to_dict(),
        "test_rmse": test_rmse,
        "train_rmse": train_rmse,
        "trained_on": args.data,
    }, indent=2))

    reports = Path(args.reports)
    save_plots(train, test, best, m, b, model, reports)
    (reports / "metrics.json").write_text(json.dumps({"correlations": correlations, "test": results}, indent=2))
    train.to_csv(reports / "train_features.csv", index=False)
    print(f"\nSaved model to {model_path} and plots + metrics to {reports}/")


if __name__ == "__main__":
    main()
