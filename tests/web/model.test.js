import { test } from "node:test";
import assert from "node:assert/strict";
import { severity, validateModel, whoThreshold, screen } from "../../web/js/model.js";
import { extractFeatures, fitWithin, PhotoQualityError } from "../../web/js/features.js";

const model = {
  feature_names: ["red_chroma"],
  crop_fraction: 0.5,
  multi: { mean: [0.4], std: [0.05], w: [1.0], b: 12.0 },
  test_rmse: 0.5,
};

test("WHO cut-offs match src/evaluate.py", () => {
  assert.equal(whoThreshold({ sex: "F", age: 25 }), 12.0);
  assert.equal(whoThreshold({ sex: "M", age: 25 }), 13.0);
  assert.equal(whoThreshold({ sex: "F", age: 25, pregnant: true }), 11.0);
  assert.equal(whoThreshold({ sex: "M", age: 3 }), 11.0);
  assert.equal(whoThreshold({ sex: "F", age: 8 }), 11.5);
  assert.equal(whoThreshold({ sex: "M", age: 13 }), 12.0);
  assert.equal(whoThreshold({}), 12.0);
});

test("severity bands match src/evaluate.py", () => {
  assert.equal(severity(12.5, 12.0), "none");
  assert.equal(severity(11.5, 12.0), "mild");
  assert.equal(severity(9.0, 12.0), "moderate");
  assert.equal(severity(7.5, 12.0), "severe");
  assert.equal(severity(10.5, 11.0), "mild");
  assert.equal(severity(7.5, 11.0), "moderate");
  assert.equal(severity(6.5, 11.0), "severe");
});

test("screen gives value, range and category", () => {
  const r = screen(model, { red_chroma: 0.45 }, { sex: "F", age: 20 });
  assert.equal(r.hb, 13.0);
  assert.deepEqual([r.low, r.high, r.threshold, r.severity], [12.5, 13.5, 12.0, "none"]);
});

test("validateModel rejects tampered or broken models", () => {
  assert.doesNotThrow(() => validateModel(model));
  const broken = [
    null,
    { ...model, feature_names: ["__proto__"] },
    { ...model, multi: { ...model.multi, w: [NaN] } },
    { ...model, multi: { ...model.multi, std: [0] } },
    { ...model, multi: { ...model.multi, mean: [0.4, 0.5] } },
    { ...model, test_rmse: "1" },
    { ...model, crop_fraction: 5 },
  ];
  for (const m of broken) assert.throws(() => validateModel(m));
});

test("a black photo is rejected, not guessed", () => {
  const data = new Uint8ClampedArray(64 * 64 * 4).fill(5);
  assert.throws(() => extractFeatures({ width: 64, height: 64, data }), PhotoQualityError);
});

test("photos are shrunk to at most 512 px like PIL thumbnail", () => {
  assert.deepEqual(fitWithin(4000, 3000), { width: 512, height: 384 });
  assert.deepEqual(fitWithin(96, 96), { width: 96, height: 96 });
});
