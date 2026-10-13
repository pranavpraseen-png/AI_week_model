"""How good is the model? Regression errors plus the anaemia screening view."""
import math

import numpy as np

# WHO haemoglobin cut-offs in g/dL (WHO 2024 guideline). Below the cut-off = anaemic.
WHO_THRESHOLDS = {
    "child_6_59_months": 11.0,
    "child_5_11": 11.5,
    "child_12_14": 12.0,
    "woman": 12.0,
    "pregnant_woman": 11.0,
    "man": 13.0,
}


def _missing(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


def who_threshold(sex=None, age=None, pregnant=False):
    """Pick the right anaemia cut-off for this person. Defaults to adult woman (12.0)."""
    if pregnant:
        return WHO_THRESHOLDS["pregnant_woman"]
    if not _missing(age):
        age = float(age)
        if age < 5:
            return WHO_THRESHOLDS["child_6_59_months"]
        if age < 12:
            return WHO_THRESHOLDS["child_5_11"]
        if age < 15:
            return WHO_THRESHOLDS["child_12_14"]
    if not _missing(sex) and str(sex).strip().lower() in {"m", "male", "man", "boy"}:
        return WHO_THRESHOLDS["man"]
    return WHO_THRESHOLDS["woman"]


def severity(hb, threshold):
    """WHO severity band for a haemoglobin value."""
    if hb >= threshold:
        return "no anaemia"
    # Children under 5 and pregnant women (cut-off 11.0) use lower bands.
    mild_floor, moderate_floor = (10.0, 7.0) if threshold == 11.0 else (11.0, 8.0)
    if hb >= mild_floor:
        return "mild anaemia"
    if hb >= moderate_floor:
        return "moderate anaemia"
    return "severe anaemia"


def regression_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    error = y_pred - y_true
    ss_res = (error ** 2).sum()
    ss_tot = ((y_true - y_true.mean()) ** 2).sum()
    return {
        "MAE": float(np.abs(error).mean()),
        "RMSE": float(np.sqrt((error ** 2).mean())),
        "R2": float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
    }


def screening_metrics(y_true, y_pred, thresholds):
    """Treat 'Hb below cut-off' as a yes/no test and count hits and misses."""
    actual = np.asarray(y_true) < np.asarray(thresholds)
    flagged = np.asarray(y_pred) < np.asarray(thresholds)
    tp = int((actual & flagged).sum())
    fn = int((actual & ~flagged).sum())
    tn = int((~actual & ~flagged).sum())
    fp = int((~actual & flagged).sum())
    return {
        "true_positive": tp,
        "false_negative": fn,
        "true_negative": tn,
        "false_positive": fp,
        "sensitivity": tp / (tp + fn) if tp + fn else float("nan"),
        "specificity": tn / (tn + fp) if tn + fp else float("nan"),
        "accuracy": (tp + tn) / len(actual) if len(actual) else float("nan"),
    }
