"""Train the haemoglobin regression model and report how well it works.

  python src/train.py --data data/simulated/labels.csv
  python src/train.py --data data/ghana_nails/labels.csv --test-data data/india/labels.csv
  python src/train.py --data data/simulated/labels.csv --features basic
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files; no screen needed
import matplotlib.pyplot as plt
import numpy as np

from dataset import load_table
from evaluate import regression_metrics, screening_metrics
from features import FEATURE_SETS
from linear_regression import fit_simple, fit_until_match


def split(table, test_size, seed):
    """Shuffle, then keep `test_size` of the rows aside as the test set."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(table))
    n_test = max(1, int(len(table) * test_size))
    return table.iloc[order[n_test:]].reset_index(drop=True), table.iloc[order[:n_test]].reset_index(drop=True)


def correlations(train, feature_names):
    """How strongly each feature moves with Hb (-1 to +1), measured on training data only."""
    return {name: float(np.corrcoef(train[name], train["hb"])[0, 1]) for name in feature_names}


def train_models(train, feature_names, learning_rate=0.05, match_within=0.01):
    """Fit the simple y = mx + b model and the multi-feature model."""
    corr = correlations(train, feature_names)
    best = max(corr, key=lambda k: abs(corr[k]))
    m, b = fit_simple(train[best], train["hb"])
    model, attempts = fit_until_match(
        train[feature_names].to_numpy(), train["hb"].to_numpy(), learning_rate, match_within=match_within
    )
    return {"correlations": corr, "best": best, "m": m, "b": b, "multi": model, "attempts": attempts,
            "feature_names": feature_names, "train_mean_hb": float(train["hb"].mean())}


def predictions(models, table):
    """Predicted Hb for every row, from each of the three approaches."""
    return {
        "baseline (always guess mean)": np.full(len(table), models["train_mean_hb"]),
        f"simple y=mx+b ({models['best']})": models["m"] * table[models["best"]].to_numpy() + models["b"],
        "multi-feature": models["multi"].predict(table[models["feature_names"]].to_numpy()),
    }


def evaluate_models(models, test):
    y = test["hb"].to_numpy()
    return {
        name: {"regression": regression_metrics(y, pred),
               "screening": screening_metrics(y, pred, test["threshold"].to_numpy())}
        for name, pred in predictions(models, test).items()
    }


def print_results(results):
    for name, r in results.items():
        reg, scr = r["regression"], r["screening"]
        print(f"  {name:<34} MAE {reg['MAE']:.2f}  RMSE {reg['RMSE']:.2f}  R² {reg['R2']:+.3f}  "
              f"sensitivity {scr['sensitivity']:.2f}  specificity {scr['specificity']:.2f}")


def save_plots(train, test, models, reports):
    reports.mkdir(parents=True, exist_ok=True)
    best, m, b, model = models["best"], models["m"], models["b"], models["multi"]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.scatter(train[best], train["hb"], s=10, alpha=0.4, label="train")
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

    pred = model.predict(test[models["feature_names"]].to_numpy())
    fig, ax = plt.subplots(figsize=(5, 5))
    for region, group in test.groupby("region"):
        ax.scatter(group["hb"], pred[group.index], s=14, label=region)
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
    parser.add_argument("--data", nargs="+", required=True, help="labels.csv file(s) to train on")
    parser.add_argument("--test-data", nargs="+", help="labels.csv from a DIFFERENT population to test on")
    parser.add_argument("--features", choices=list(FEATURE_SETS), default="reference")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--crop", type=float, default=0.5, help="centre crop fraction when no mask is given")
    parser.add_argument("--model-out", default="models/model.json")
    parser.add_argument("--reports", default="reports")
    args = parser.parse_args()
    feature_names = FEATURE_SETS[args.features]

    print("1. Extracting colour features from photos...")
    table = load_table(args.data, args.crop)
    if args.test_data:
        train, test = table, load_table(args.test_data, args.crop)
        print(f"   cross-population test: train on {args.data}, test on {args.test_data}")
    else:
        train, test = split(table, args.test_size, args.seed)
    print(f"   {len(train)} training photos, {len(test)} test photos, "
          f"regions: {sorted(train['region'].unique())} -> {sorted(test['region'].unique())}")
    if len(train) < 5 or len(test) < 2:
        raise SystemExit("Not enough usable photos to train and test.")

    models = train_models(train, feature_names, args.learning_rate)

    print("\n2. How strongly does each feature move with Hb? (correlation, training set only)")
    for name, r in sorted(models["correlations"].items(), key=lambda kv: -abs(kv[1])):
        print(f"   {name:<20} {r:+.3f}")

    print(f"\n3. Simple regression on the best single feature ({models['best']}):")
    print(f"   Hb = {models['m']:.3f} × {models['best']} + {models['b']:.3f}")

    print("\n4. Multi-feature regression with gradient descent, tested against the exact answer:")
    for epochs, gap in models["attempts"]:
        print(f"   {epochs:>8} epochs -> largest gap {gap:.4f} g/dL {'MATCH' if gap <= 0.01 else 'keep training'}")
    slopes, intercept = models["multi"].original_units()
    terms = "\n     + ".join(f"({s:9.3f} × {n})" for s, n in zip(slopes, feature_names))
    print(f"   Hb =   {terms}\n     + {intercept:.3f}")

    print("\n5. Test-set results (photos the model never saw):")
    results = evaluate_models(models, test)
    print_results(results)

    model = models["multi"]
    train_rmse = regression_metrics(train["hb"], model.predict(train[feature_names].to_numpy()))["RMSE"]
    model_path = Path(args.model_out)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(json.dumps({
        "feature_set": args.features,
        "feature_names": feature_names,
        "crop_fraction": args.crop,
        "simple": {"feature": models["best"], "m": models["m"], "b": models["b"]},
        "multi": model.to_dict(),
        "test_rmse": results["multi-feature"]["regression"]["RMSE"],
        "train_rmse": train_rmse,
        "trained_on": args.data,
        "regions": sorted(train["region"].unique().tolist()),
    }, indent=2))

    reports = Path(args.reports)
    save_plots(train, test, models, reports)
    (reports / "metrics.json").write_text(json.dumps(
        {"correlations": models["correlations"], "test": results}, indent=2))
    print(f"\nSaved model to {model_path} and plots + metrics to {reports}/")


if __name__ == "__main__":
    main()
