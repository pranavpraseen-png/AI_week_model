"""Screen one photo: estimate haemoglobin, give a WHO category, and explain it.

  python src/predict.py photo.jpg --sex F --age 19
  python src/predict.py photo.jpg --language Hindi
  python src/predict.py photo.jpg --no-llm
"""
import argparse
import json
from pathlib import Path

import numpy as np

from evaluate import severity, who_threshold
from features import extract_features
from linear_regression import LinearRegression
from local_llm import DEFAULT_MODEL, DEFAULT_URL, explain_or_fallback, fallback_explanation


def screen(image_path, model_info, sex=None, age=None, pregnant=False, mask_path=None, simple=False):
    feats = extract_features(image_path, mask_path, model_info["crop_fraction"])
    if simple:
        s = model_info["simple"]
        hb = s["m"] * feats[s["feature"]] + s["b"]
    else:
        model = LinearRegression.from_dict(model_info["multi"])
        x = np.array([[feats[name] for name in model_info["feature_names"]]])
        hb = float(model.predict(x)[0])

    threshold = who_threshold(sex, age, pregnant)
    margin = model_info["test_rmse"]  # typical error on unseen photos
    return {
        "hb": hb,
        "hb_low": hb - margin,
        "hb_high": hb + margin,
        "threshold": threshold,
        "severity": severity(hb, threshold),
        "features": feats,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image")
    parser.add_argument("--model", default="models/model.json")
    parser.add_argument("--mask", help="optional black/white mask of the nail or eyelid")
    parser.add_argument("--sex", help="F or M")
    parser.add_argument("--age", type=float)
    parser.add_argument("--pregnant", action="store_true")
    parser.add_argument("--simple", action="store_true", help="use the one-feature y = mx + b model")
    parser.add_argument("--language", default="English")
    parser.add_argument("--no-llm", action="store_true", help="skip the local LLM explanation")
    parser.add_argument("--llm-url", default=DEFAULT_URL)
    parser.add_argument("--llm-model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    model_info = json.loads(Path(args.model).read_text())
    result = screen(args.image, model_info, args.sex, args.age, args.pregnant, args.mask, args.simple)

    print(f"Estimated haemoglobin: {result['hb']:.1f} g/dL "
          f"(likely {result['hb_low']:.1f}-{result['hb_high']:.1f})")
    print(f"WHO cut-off for this person: {result['threshold']} g/dL -> {result['severity']}")
    print("⚠ Screening estimate only. Confirm with a blood test.\n")

    if args.no_llm:
        print(fallback_explanation(result))
    else:
        text, _ = explain_or_fallback(result, args.language, args.llm_url, args.llm_model)
        print(text)


if __name__ == "__main__":
    main()
