// Browser code vs Python code on the same pixels: features and Hb must agree.
// The fixture is written by tests/test_web_parity.py (it runs this file).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { extractFeatures } from "../../web/js/features.js";
import { predictHb, validateModel } from "../../web/js/model.js";

const fixturePath = process.env.PARITY_FIXTURE;

test("JS features and Hb match Python exactly", { skip: !fixturePath && "run via pytest" }, () => {
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
  const model = validateModel(fixture.model);
  assert.ok(fixture.cases.length > 0);
  for (const c of fixture.cases) {
    const data = new Uint8ClampedArray(Buffer.from(c.rgba_base64, "base64"));
    const features = extractFeatures({ width: c.width, height: c.height, data }, model.crop_fraction);
    for (const [name, expected] of Object.entries(c.features)) {
      assert.ok(Math.abs(features[name] - expected) < 1e-9, `${c.name} ${name}: js ${features[name]} vs py ${expected}`);
    }
    const hb = predictHb(model, features);
    assert.ok(Math.abs(hb - c.hb) < 1e-6, `${c.name} hb: js ${hb} vs py ${c.hb}`);
  }
});
