"""The whole learning journey in one script: from y = mx + b on five points to a
multi-region anaemia model, with a CHECK after every stage.

  python src/progression.py --data data/simulated/labels.csv

Every stage prints what it did and whether its check passed, and the full log is
saved to reports/progression_log.md. Docs: docs/02_full_build_explained.md.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from cross_region import fit_and_score, format_loro, leave_one_region_out
from dataset import load_table, region_counts
from evaluate import regression_metrics, screening_metrics
from features import BASIC_FEATURES, REFERENCE_FEATURES
from linear_regression import LinearRegression, fit_simple, fit_until_match
from train import correlations, split

# Five made-up photos: redness score x and lab haemoglobin y. Small enough to do by hand.
HAND_X = np.array([0.30, 0.35, 0.40, 0.45, 0.50])
HAND_Y = np.array([8.1, 9.0, 10.2, 10.9, 12.0])
HAND_M, HAND_B = 19.4, 2.28  # worked out with pen and paper in docs/02_full_build_explained.md

LIGHT_SKIN_REGIONS = ["italy", "russia"]


class Log:
    def __init__(self):
        self.lines = []
        self.checks = []

    def __call__(self, text=""):
        print(text)
        self.lines.append(text)

    def check(self, name, passed, detail):
        self.checks.append((name, passed))
        self(f"\n**CHECK — {name}: {'PASS ✅' if passed else 'FAIL ❌'}** ({detail})\n")


def stage0_by_hand(log):
    log("## Stage 0 — y = mx + b on 5 points, by hand\n")
    x_mean, y_mean = HAND_X.mean(), HAND_Y.mean()
    dx, dy = HAND_X - x_mean, HAND_Y - y_mean
    log(f"x = {HAND_X.tolist()}  (redness)\ny = {HAND_Y.tolist()}  (Hb, g/dL)\n")
    log(f"x̄ = {x_mean:.2f}, ȳ = {y_mean:.2f}")
    log(f"Σ(x−x̄)(y−ȳ) = {(dx * dy).sum():.4f},  Σ(x−x̄)² = {(dx ** 2).sum():.4f}")
    m, b = fit_simple(HAND_X, HAND_Y)
    log(f"m = {(dx * dy).sum():.4f} / {(dx ** 2).sum():.4f} = {m:.4f}")
    log(f"b = ȳ − m·x̄ = {y_mean:.2f} − {m:.2f}×{x_mean:.2f} = {b:.4f}")
    log(f"\n**Model: Hb = {m:.2f} × redness + {b:.2f}**  → a photo with redness 0.38 gives {m * 0.38 + b:.2f} g/dL")
    poly_m, poly_b = np.polyfit(HAND_X, HAND_Y, 1)
    log.check("code matches pen-and-paper and NumPy's polyfit",
              abs(m - HAND_M) < 1e-9 and abs(b - HAND_B) < 1e-9 and abs(m - poly_m) < 1e-9 and abs(b - poly_b) < 1e-9,
              f"code m={m:.4f} b={b:.4f}; hand m={HAND_M} b={HAND_B}; polyfit m={poly_m:.4f} b={poly_b:.4f}")
    return m, b


def stage1_gradient_descent(log, m_exact, b_exact):
    log("## Stage 1 — Learn the same line by gradient descent, test until it matches\n")
    log("Gradient descent starts at m = 0, b = 0 and nudges them downhill on the error. "
        "We train, compare with the exact answer, and if it doesn't match, train longer and test again.\n")
    model, attempts = fit_until_match(HAND_X, HAND_Y, learning_rate=0.1, start_epochs=5, match_within=1e-4)
    log("| attempt | epochs | largest gap vs exact (g/dL) | result |\n|---|---|---|---|")
    for i, (epochs, gap) in enumerate(attempts, 1):
        log(f"| {i} | {epochs} | {gap:.6f} | {'MATCH' if gap <= 1e-4 else 'not yet → train longer'} |")
    slopes, intercept = model.original_units()
    log(f"\nGradient descent learned: Hb = {slopes[0]:.4f} × redness + {intercept:.4f}")
    log.check("gradient descent matches the exact line",
              abs(slopes[0] - m_exact) < 0.01 and abs(intercept - b_exact) < 0.01,
              f"GD m={slopes[0]:.4f} b={intercept:.4f} vs exact m={m_exact:.4f} b={b_exact:.4f}")

    log("\n### Learning-rate experiment (100 epochs each)\n")
    best_loss = float(((m_exact * HAND_X + b_exact - HAND_Y) ** 2).mean())
    log(f"The best possible loss (the exact line's mean squared error) is {best_loss:.4f}: "
        "the 5 points are not perfectly on a line, so it can never reach 0.\n")
    log("| learning rate | loss after 100 epochs | what happened |\n|---|---|---|")
    outcomes = {}
    for lr in [0.001, 0.1, 0.9, 1.1]:
        trial = LinearRegression(lr, 100).fit(HAND_X, HAND_Y)
        loss = trial.loss_history_[-1]
        if trial.diverged_ or loss > trial.loss_history_[0]:
            verdict = "DIVERGED: steps overshoot and the error explodes"
        elif loss - best_loss > 1e-4:
            verdict = "too slow: still far from the answer"
        else:
            verdict = "converged"
        outcomes[lr] = verdict
        log(f"| {lr} | {loss:.4g} | {verdict} |")
    log.check("learning rate behaves as theory says (tiny = slow, too big = diverge)",
              outcomes[0.001].startswith("too slow") and outcomes[0.1] == "converged"
              and outcomes[1.1].startswith("DIVERGED"), "see table")


def stage2_single_feature(log, train, test):
    log("## Stage 2 — y = mx + b on photos (one colour feature)\n")
    corr = correlations(train, BASIC_FEATURES)
    log("| feature | correlation with Hb |\n|---|---|")
    for name, r in sorted(corr.items(), key=lambda kv: -abs(kv[1])):
        log(f"| {name} | {r:+.3f} |")
    best = max(corr, key=lambda k: abs(corr[k]))
    m, b = fit_simple(train[best], train["hb"])
    log(f"\nBest single feature: **{best}** → Hb = {m:.2f} × {best} + {b:.2f}\n")
    base = regression_metrics(test["hb"], np.full(len(test), train["hb"].mean()))
    simple = regression_metrics(test["hb"], m * test[best] + b)
    log(f"Test set: baseline (always guess the average) MAE {base['MAE']:.2f} g/dL → "
        f"y = mx + b MAE {simple['MAE']:.2f} g/dL")
    log.check("simple model beats guessing the average", simple["MAE"] < base["MAE"],
              f"{simple['MAE']:.2f} < {base['MAE']:.2f}")
    return simple


def stage3_multi_feature(log, train, test, simple):
    log("## Stage 3 — Many features: y = m₁x₁ + m₂x₂ + … + b\n")
    model, attempts = fit_until_match(train[BASIC_FEATURES].to_numpy(), train["hb"].to_numpy(),
                                      learning_rate=0.05, start_epochs=1000, match_within=0.01)
    log("| attempt | epochs | largest gap vs exact (g/dL) |\n|---|---|---|")
    for i, (epochs, gap) in enumerate(attempts, 1):
        log(f"| {i} | {epochs} | {gap:.4f} |")
    log("\nThe colour features overlap a lot (red_chroma and log_red_green carry similar information), "
        "which makes the error surface a long narrow valley, so gradient descent needs many epochs.")
    log.check("gradient descent matches the exact multi-feature answer", attempts[-1][1] <= 0.01,
              f"final gap {attempts[-1][1]:.4f} g/dL after {attempts[-1][0]} epochs")
    multi = regression_metrics(test["hb"], model.predict(test[BASIC_FEATURES].to_numpy()))
    log(f"Test MAE: one feature {simple['MAE']:.2f} → all basic features {multi['MAE']:.2f} g/dL")
    log.check("more features help on the same population", multi["MAE"] <= simple["MAE"],
              f"{multi['MAE']:.2f} ≤ {simple['MAE']:.2f}")


def light_to_dark(table, feature_names):
    light = table["region"].isin(LIGHT_SKIN_REGIONS)
    return {region: fit_and_score(table[light], table[table["region"] == region], feature_names)
            for region in sorted(table.loc[~light, "region"].unique())}


def stage4_cross_region(log, table):
    log("## Stage 4 — Test in a region the model has never seen\n")
    if not set(LIGHT_SKIN_REGIONS) <= set(table["region"]):
        log("(Skipped the light→dark test: needs italy and russia in the data.)")
        shift = {}
    else:
        shift = light_to_dark(table, BASIC_FEATURES)
        log(f"Train only on {LIGHT_SKIN_REGIONS} (lighter skin), test on the other regions:\n")
        log("| tested on | bias (g/dL) | MAE | sensitivity (anaemia caught) |\n|---|---|---|---|")
        for region, r in shift.items():
            log(f"| {region} | {r['bias']:+.2f} | {r['MAE']:.2f} | {r['sensitivity']:.2f} |")
        log("\nA positive bias means the model thinks people have MORE haemoglobin than they do, "
            "so anaemic people are told they are fine.")
    loro = leave_one_region_out(table, BASIC_FEATURES)
    log("\nLeave-one-region-out (train on all others):\n\n" + format_loro(loro))
    worst = max(r["MAE"] for r in shift.values()) if shift else max(r["MAE"] for r in loro.values())
    log.check("found the weakness: error grows on unseen regions", worst > 1.0,
              f"worst unseen-region MAE {worst:.2f} g/dL")
    return shift, loro


def stage5_skin_reference(log, table, shift_before, loro_before):
    log("## Stage 5 — Fix: also measure the skin around the nail, then test again\n")
    log("Skin tone and the phone's colour cast change the nail AND the surrounding skin. "
        "Giving the model the skin colour lets it subtract that shared part.\n")
    loro = leave_one_region_out(table, REFERENCE_FEATURES)
    log(format_loro(loro))
    before = np.mean([r["MAE"] for r in loro_before.values()])
    after = np.mean([r["MAE"] for r in loro.values()])
    log(f"\nAverage leave-one-region-out MAE: {before:.2f} → {after:.2f} g/dL")
    if shift_before:
        shift = light_to_dark(table, REFERENCE_FEATURES)
        log("\nLight-skin-only training, tested on darker-skin regions:\n")
        log("| tested on | MAE before | MAE after | sensitivity before | sensitivity after |\n|---|---|---|---|---|")
        for region in shift:
            log(f"| {region} | {shift_before[region]['MAE']:.2f} | {shift[region]['MAE']:.2f} | "
                f"{shift_before[region]['sensitivity']:.2f} | {shift[region]['sensitivity']:.2f} |")
        log("\nEven with the fix, a model trained only on light skin is worse on dark skin than one "
            "trained on everyone. Diverse training data matters as much as clever features.")
    log.check("skin reference reduces cross-region error", after < before, f"{after:.2f} < {before:.2f}")
    return loro


def stage6_final(log, table, model_out, data_paths):
    log("## Stage 6 — Final model: all regions, skin-reference features\n")
    train, test = split(table, 0.2, 7)
    model, attempts = fit_until_match(train[REFERENCE_FEATURES].to_numpy(), train["hb"].to_numpy(),
                                      learning_rate=0.05, start_epochs=1000, match_within=0.01)
    pred = model.predict(test[REFERENCE_FEATURES].to_numpy())
    reg = regression_metrics(test["hb"], pred)
    scr = screening_metrics(test["hb"], pred, test["threshold"].to_numpy())
    log(f"Gradient descent matched the exact answer after {attempts[-1][0]} epochs (gap {attempts[-1][1]:.4f}).")
    log(f"Held-out test: MAE {reg['MAE']:.2f} g/dL, R² {reg['R2']:.2f}, "
        f"sensitivity {scr['sensitivity']:.2f}, specificity {scr['specificity']:.2f}")
    slopes, intercept = model.original_units()
    log("\nFinal equation:\n\n```\nHb = " + "\n   + ".join(
        f"{s:9.3f} × {n}" for s, n in zip(slopes, REFERENCE_FEATURES)) + f"\n   + {intercept:.3f}\n```")
    train_rmse = regression_metrics(train["hb"], model.predict(train[REFERENCE_FEATURES].to_numpy()))["RMSE"]
    corr = correlations(train, BASIC_FEATURES)
    best = max(corr, key=lambda k: abs(corr[k]))
    simple_m, simple_b = fit_simple(train[best], train["hb"])
    Path(model_out).parent.mkdir(parents=True, exist_ok=True)
    Path(model_out).write_text(json.dumps({
        "feature_set": "reference",
        "feature_names": REFERENCE_FEATURES,
        "crop_fraction": 0.5,
        "simple": {"feature": best, "m": simple_m, "b": simple_b},
        "multi": model.to_dict(),
        "test_rmse": reg["RMSE"],
        "train_rmse": train_rmse,
        "trained_on": list(data_paths),
        "regions": sorted(table["region"].unique().tolist()),
    }, indent=2))
    log(f"\nSaved to {model_out}. Use it: `python src/predict.py photo.jpg --sex F --age 19`")
    log.check("final model screens well on held-out photos", scr["sensitivity"] >= 0.8 and reg["R2"] > 0.5,
              f"sensitivity {scr['sensitivity']:.2f}, R² {reg['R2']:.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", nargs="+", required=True)
    parser.add_argument("--model-out", default="models/model.json")
    parser.add_argument("--log", default="reports/progression_log.md")
    args = parser.parse_args()

    log = Log()
    log("# Progression log — from y = mx + b to a multi-region anaemia model\n")
    log(f"Data: {', '.join(args.data)}\n")
    if any("simulated" in d for d in args.data):
        log("> ⚠️ **SIMULATED photos.** These numbers prove the code works; they are NOT real-world accuracy.\n")

    m, b = stage0_by_hand(log)
    stage1_gradient_descent(log, m, b)

    table = load_table(args.data, verbose=False)
    log(f"Loaded {len(table)} photos: {region_counts(table)}\n")
    train, test = split(table, 0.2, 42)
    simple = stage2_single_feature(log, train, test)
    stage3_multi_feature(log, train, test, simple)
    if table["region"].nunique() >= 2:
        shift, loro = stage4_cross_region(log, table)
        stage5_skin_reference(log, table, shift, loro)
    else:
        log("(Stages 4–5 skipped: the data has only one region.)")
    stage6_final(log, table, args.model_out, args.data)

    log("## Summary\n\n| check | result |\n|---|---|")
    for name, passed in log.checks:
        log(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log).write_text("\n".join(log.lines) + "\n")
    print(f"\nLog saved to {args.log}")


if __name__ == "__main__":
    main()
