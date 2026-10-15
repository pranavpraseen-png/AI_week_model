// The haemoglobin scale (web/js/scale.js) and the count-up text used on the opening page.
import { test } from "node:test";
import assert from "node:assert/strict";
import { scaleLayout, SCALE_MAX, SCALE_MIN } from "../../web/js/scale.js";
import { chroma, countText, nailColor, storyBand, storyStep } from "../../web/js/intro.js";

const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);

test("the scale runs from 4 to 18 g/dL", () => {
  assert.equal(SCALE_MIN, 4);
  assert.equal(SCALE_MAX, 18);
  const layout = scaleLayout({ hb: 4, threshold: 12 });
  close(layout.marker, 0);
  close(layout.tick(18), 100);
  close(layout.tick(11), 50);
});

test("WHO bands for a woman (cut-off 12): severe < 8, moderate 8-11, mild 11-12, healthy 12+", () => {
  const { bands, cutoff } = scaleLayout({ hb: 10.4, low: 10.1, high: 10.8, threshold: 12 });
  const at = (v) => ((v - 4) / 14) * 100;
  close(bands.severe.left, 0);
  close(bands.severe.width, at(8));
  close(bands.moderate.left, at(8));
  close(bands.moderate.width, at(11) - at(8));
  close(bands.mild.left, at(11));
  close(bands.mild.width, at(12) - at(11));
  close(bands.ok.left, at(12));
  close(bands.ok.left + bands.ok.width, 100);
  close(cutoff, at(12));
});

test("the 11.0 cut-off (pregnancy, young children) uses the lower band floors, as in src/evaluate.py", () => {
  const { bands } = scaleLayout({ hb: 9, threshold: 11 });
  const at = (v) => ((v - 4) / 14) * 100;
  close(bands.moderate.left, at(7));
  close(bands.mild.left, at(10));
  close(bands.ok.left, at(11));
});

test("the estimate, its range and out-of-scale values", () => {
  const layout = scaleLayout({ hb: 10.4, low: 10.1, high: 10.8, threshold: 12 });
  close(layout.marker, (6.4 / 14) * 100);
  close(layout.range.left, (6.1 / 14) * 100);
  close(layout.range.width, (0.7 / 14) * 100);
  close(scaleLayout({ hb: 2, threshold: 12 }).marker, 0); // clamped, never off the line
  close(scaleLayout({ hb: 25, threshold: 12 }).marker, 100);
  close(scaleLayout({ hb: 9, threshold: 12 }).range.width, 0); // no range given: zero width
});

test("count-up text eases from zero to the exact final value", () => {
  assert.equal(countText(57, 0, 0, "%"), "0%");
  assert.equal(countText(57, 1, 0, "%"), "57%");
  assert.equal(countText(10.4, 1, 1), "10.4");
  assert.equal(countText(0.4492, 1, 4), "0.4492");
  assert.equal(countText(10.4, 5, 1), "10.4"); // never overshoots
  assert.equal(countText(10.4, -1, 1), "0.0");
  assert.ok(Number(countText(100, 0.5)) > 50); // ease-out: past halfway at half time
});

test("scroll story colours and bands", () => {
  assert.deepEqual(nailColor(5), [238, 214, 205]);
  assert.deepEqual(nailColor(18), [214, 112, 112]);
  assert.equal(storyBand(7.9), "severe");
  assert.equal(storyBand(10.4), "moderate");
  assert.equal(storyBand(11.5), "mild");
  assert.equal(storyBand(12), "healthy");
});

test("the pinned phone's colour numbers are worked out like a photo's", () => {
  const { red, lnRG } = chroma([200, 100, 100]);
  close(red, 0.5);
  close(lnRG, Math.log(2));
  // A paler nail (lower haemoglobin) has a smaller share of red.
  assert.ok(chroma(nailColor(6)).red < chroma(nailColor(16)).red);
});

test("the four steps light up in order as you scroll", () => {
  assert.equal(storyStep(0), 1);
  assert.equal(storyStep(0.24), 1);
  assert.equal(storyStep(0.25), 2);
  assert.equal(storyStep(0.6), 3);
  assert.equal(storyStep(0.75), 4);
  assert.equal(storyStep(1), 4);
  assert.equal(storyStep(-0.2), 1);
});
