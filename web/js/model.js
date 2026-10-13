// The trained regression model (exported from Python) and the WHO rules.
// Mirrors src/linear_regression.py (predict) and src/evaluate.py (cut-offs).

const KNOWN_FEATURES = new Set([
  "red_chroma", "green_chroma", "log_red_green", "brightness", "saturation",
  "skin_red_chroma", "skin_log_red_green",
]);

const isNum = (v) => typeof v === "number" && Number.isFinite(v);

// model.json is data we load over the network: check its shape before trusting it.
export function validateModel(m) {
  if (!m || typeof m !== "object") throw new Error("model: not an object");
  const names = m.feature_names;
  if (!Array.isArray(names) || names.length === 0 || !names.every((n) => KNOWN_FEATURES.has(n))) {
    throw new Error("model: bad feature_names");
  }
  const k = names.length;
  const multi = m.multi || {};
  for (const key of ["mean", "std", "w"]) {
    if (!Array.isArray(multi[key]) || multi[key].length !== k || !multi[key].every(isNum)) {
      throw new Error(`model: bad multi.${key}`);
    }
  }
  if (!multi.std.every((s) => s > 0)) throw new Error("model: std must be > 0");
  if (!isNum(multi.b) || !isNum(m.test_rmse) || !isNum(m.crop_fraction)) throw new Error("model: bad numbers");
  if (!(m.crop_fraction > 0 && m.crop_fraction <= 1)) throw new Error("model: bad crop_fraction");
  return m;
}

// y = m1*x1 + ... + b, with each x standardised exactly as during training.
export function predictHb(model, features) {
  const { mean, std, w, b } = model.multi;
  let hb = b;
  model.feature_names.forEach((name, i) => {
    hb += ((features[name] - mean[i]) / std[i]) * w[i];
  });
  return hb;
}

export const WHO = {
  child_6_59_months: 11.0,
  child_5_11: 11.5,
  child_12_14: 12.0,
  woman: 12.0,
  pregnant_woman: 11.0,
  man: 13.0,
};

export function whoThreshold({ sex, age, pregnant }) {
  if (pregnant) return WHO.pregnant_woman;
  if (isNum(age)) {
    if (age < 5) return WHO.child_6_59_months;
    if (age < 12) return WHO.child_5_11;
    if (age < 15) return WHO.child_12_14;
  }
  return sex === "M" ? WHO.man : WHO.woman;
}

// "none" | "mild" | "moderate" | "severe" (WHO bands)
export function severity(hb, threshold) {
  if (hb >= threshold) return "none";
  const [mildFloor, moderateFloor] = threshold === 11.0 ? [10.0, 7.0] : [11.0, 8.0];
  if (hb >= mildFloor) return "mild";
  if (hb >= moderateFloor) return "moderate";
  return "severe";
}

export function screen(model, features, person) {
  const hb = predictHb(model, features);
  const threshold = whoThreshold(person);
  return {
    hb,
    low: hb - model.test_rmse,
    high: hb + model.test_rmse,
    threshold,
    severity: severity(hb, threshold),
  };
}
