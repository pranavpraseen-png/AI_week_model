"""End to end: simulated photos -> features -> training -> screening one photo."""
import subprocess
import sys
from pathlib import Path

import pytest

from cross_region import leave_one_region_out
from dataset import load_table
from features import BASIC_FEATURES, REFERENCE_FEATURES
from local_llm import explain_or_fallback
from predict import screen
from train import evaluate_models, split, train_models

SRC = Path(__file__).resolve().parent.parent / "src"


@pytest.fixture(scope="module")
def simulated(tmp_path_factory):
    out = tmp_path_factory.mktemp("simulated")
    subprocess.run([sys.executable, str(SRC / "make_simulated_data.py"), "--n-per-region", "40",
                    "--regions", "ghana", "italy", "--out", str(out)], check=True, capture_output=True)
    return out


def test_load_table_reads_every_photo(simulated):
    table = load_table(simulated / "labels.csv", verbose=False)
    assert len(table) == 80
    assert set(table["region"]) == {"ghana", "italy"}
    assert table[REFERENCE_FEATURES].notna().all().all()


def test_model_beats_baseline_and_screen_works(simulated):
    table = load_table(simulated / "labels.csv", verbose=False)
    train, test = split(table, 0.25, 0)
    models = train_models(train, REFERENCE_FEATURES)
    results = evaluate_models(models, test)
    assert results["multi-feature"]["regression"]["MAE"] < results["baseline (always guess mean)"]["regression"]["MAE"]

    model_info = {
        "feature_names": REFERENCE_FEATURES, "crop_fraction": 0.5, "test_rmse": 0.5,
        "simple": {"feature": models["best"], "m": models["m"], "b": models["b"]},
        "multi": models["multi"].to_dict(),
    }
    result = screen(simulated / table["image"][0], model_info, sex="F", age=20)
    assert 3 < result["hb"] < 20
    assert result["hb_low"] < result["hb"] < result["hb_high"]
    assert result["severity"] in {"no anaemia", "mild anaemia", "moderate anaemia", "severe anaemia"}


def test_skin_reference_helps_across_regions(simulated):
    table = load_table(simulated / "labels.csv", verbose=False)
    basic = leave_one_region_out(table, BASIC_FEATURES)
    reference = leave_one_region_out(table, REFERENCE_FEATURES)
    assert sum(r["MAE"] for r in reference.values()) < sum(r["MAE"] for r in basic.values())


def test_llm_falls_back_when_nothing_is_running():
    result = {"hb": 9.0, "hb_low": 8.0, "hb_high": 10.0, "threshold": 12.0, "severity": "moderate anaemia"}
    text, used_llm = explain_or_fallback(result, base_url="http://127.0.0.1:9/v1")
    assert not used_llm
    assert "blood test" in text
