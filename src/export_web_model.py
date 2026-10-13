"""Copy the trained model into the website, keeping only what the browser needs.

  python src/export_web_model.py                       # models/model.json -> web/model.json
  python src/export_web_model.py --model models/real.json
"""
import argparse
import json
import math
from pathlib import Path

from features import REFERENCE_FEATURES


def web_model(info):
    """Validate a trained model.json and return the small dict the website loads."""
    names = info["feature_names"]
    multi = info["multi"]
    if not set(names) <= set(REFERENCE_FEATURES):
        raise ValueError(f"unknown features: {set(names) - set(REFERENCE_FEATURES)}")
    numbers = [*multi["mean"], *multi["std"], *multi["w"], multi["b"], info["test_rmse"]]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in numbers):
        raise ValueError("model contains non-finite numbers")
    if any(len(multi[k]) != len(names) for k in ("mean", "std", "w")):
        raise ValueError("model arrays do not match feature_names")
    trained_on = [str(p) for p in info.get("trained_on", [])]
    return {
        "feature_names": names,
        "crop_fraction": info["crop_fraction"],
        "multi": {k: multi[k] for k in ("mean", "std", "w", "b")},
        "test_rmse": info["test_rmse"],
        "regions": info.get("regions", []),
        "simulated": any("simulated" in p for p in trained_on),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="models/model.json")
    parser.add_argument("--out", default="web/model.json")
    args = parser.parse_args()
    exported = web_model(json.loads(Path(args.model).read_text()))
    Path(args.out).write_text(json.dumps(exported, indent=2) + "\n")
    label = "SIMULATED" if exported["simulated"] else "real"
    print(f"Wrote {args.out} ({label} model, regions: {', '.join(exported['regions']) or 'unknown'})")


if __name__ == "__main__":
    main()
