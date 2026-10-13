"""The website re-implements feature extraction in JavaScript. This test feeds the
same pixels to both versions and requires identical features and Hb."""
import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from export_web_model import web_model
from features import extract_features, load_rgb
from linear_regression import LinearRegression

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def simulated(tmp_path_factory):
    out = tmp_path_factory.mktemp("sim")
    subprocess.run([sys.executable, str(ROOT / "src" / "make_simulated_data.py"), "--n-per-region", "6",
                    "--out", str(out)], check=True, capture_output=True)
    return out


def trained_model(images):
    """A real trained model (so parity is checked with realistic weights)."""
    from dataset import load_table
    table = load_table(images / "labels.csv", verbose=False)
    from features import REFERENCE_FEATURES
    model = LinearRegression.from_exact(table[REFERENCE_FEATURES].to_numpy(), table["hb"].to_numpy())
    return {"feature_names": REFERENCE_FEATURES, "crop_fraction": 0.5, "multi": model.to_dict(),
            "test_rmse": 0.5, "trained_on": [str(images)], "regions": []}


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_javascript_matches_python(simulated, tmp_path):
    info = trained_model(simulated)
    model = LinearRegression.from_dict(info["multi"])
    cases = []
    for path in sorted((simulated / "images").glob("*.png")):
        rgb = load_rgb(path)
        rgba = np.concatenate([np.round(rgb * 255).astype(np.uint8),
                               np.full(rgb.shape[:2] + (1,), 255, np.uint8)], axis=2)
        feats = extract_features(path)
        x = np.array([[feats[n] for n in info["feature_names"]]])
        cases.append({"name": path.name, "width": rgb.shape[1], "height": rgb.shape[0],
                      "rgba_base64": base64.b64encode(rgba.tobytes()).decode(),
                      "features": feats, "hb": float(model.predict(x)[0])})
    fixture = tmp_path / "parity.json"
    fixture.write_text(json.dumps({"model": web_model(info), "cases": cases}))

    test_files = [str(p) for p in sorted((ROOT / "tests" / "web").glob("*.test.js"))]
    result = subprocess.run(["node", "--test", *test_files], capture_output=True, text=True,
                            env={**os.environ, "PARITY_FIXTURE": str(fixture)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "# fail 0" in result.stdout and "# skipped 0" in result.stdout


def test_export_rejects_broken_models():
    good = {"feature_names": ["red_chroma"], "crop_fraction": 0.5, "test_rmse": 0.3,
            "multi": {"mean": [0.4], "std": [0.1], "w": [1.0], "b": 12.0}}
    assert web_model(good)["simulated"] is False
    with pytest.raises(ValueError):
        web_model({**good, "feature_names": ["evil"]})
    with pytest.raises(ValueError):
        web_model({**good, "multi": {**good["multi"], "w": [float("nan")]}})
    with pytest.raises(ValueError):
        web_model({**good, "multi": {**good["multi"], "mean": [0.4, 0.5]}})
