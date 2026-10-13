import math

import pytest

from evaluate import regression_metrics, screening_metrics, severity, who_threshold


@pytest.mark.parametrize("sex, age, pregnant, expected", [
    ("F", 25, False, 12.0),
    ("M", 25, False, 13.0),
    ("male", 30, False, 13.0),
    ("F", 25, True, 11.0),
    ("M", 3, False, 11.0),
    ("F", 8, False, 11.5),
    ("M", 13, False, 12.0),
    (None, None, False, 12.0),
    (float("nan"), float("nan"), False, 12.0),
])
def test_who_thresholds(sex, age, pregnant, expected):
    assert who_threshold(sex, age, pregnant) == expected


@pytest.mark.parametrize("hb, threshold, expected", [
    (12.5, 12.0, "no anaemia"),
    (11.5, 12.0, "mild anaemia"),
    (9.0, 12.0, "moderate anaemia"),
    (7.5, 12.0, "severe anaemia"),
    (10.5, 11.0, "mild anaemia"),
    (7.5, 11.0, "moderate anaemia"),
    (6.5, 11.0, "severe anaemia"),
])
def test_severity_bands(hb, threshold, expected):
    assert severity(hb, threshold) == expected


def test_perfect_prediction_metrics():
    m = regression_metrics([10, 12, 14], [10, 12, 14])
    assert m["MAE"] == 0 and m["RMSE"] == 0 and m["R2"] == 1 and m["bias"] == 0


def test_bias_sign():
    assert regression_metrics([10, 12], [11, 13])["bias"] == pytest.approx(1.0)


def test_screening_counts():
    # true Hb:      9 (anaemic), 10 (anaemic), 13 (fine), 14 (fine)
    # predicted:   10 (caught), 12.5 (missed), 11 (false alarm), 14 (correct)
    s = screening_metrics([9, 10, 13, 14], [10, 12.5, 11, 14], [12, 12, 12, 12])
    assert (s["true_positive"], s["false_negative"], s["false_positive"], s["true_negative"]) == (1, 1, 1, 1)
    assert s["sensitivity"] == 0.5 and s["specificity"] == 0.5


def test_screening_with_no_anaemic_people_gives_nan_sensitivity():
    assert math.isnan(screening_metrics([13, 14], [13, 14], [12, 12])["sensitivity"])
