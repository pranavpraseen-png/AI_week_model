// The haemoglobin number line ("gauge"): the four WHO bands for one person, the
// estimate, its likely range and the healthy cut-off as a dashed line. Used by the
// result screen, the example specimen on the opening page and the scroll story,
// so all three always draw the same scale. Positions are set with CSSOM
// (element.style), which the CSP allows; there are no style="" attributes.

export const SCALE_MIN = 4;
export const SCALE_MAX = 18;

// Where each part goes, as a percentage of the scale's width (pure maths, tested in Node).
export function scaleLayout({ hb, low = hb, high = hb, threshold }, min = SCALE_MIN, max = SCALE_MAX) {
  const pct = (v) => ((Math.min(Math.max(v, min), max) - min) / (max - min)) * 100;
  const span = (from, to) => ({ left: pct(from), width: pct(to) - pct(from) });
  // Same band floors as src/evaluate.py: the 11.0 cut-off (pregnant women, young children) has lower floors.
  const [mildFloor, moderateFloor] = threshold === 11.0 ? [10.0, 7.0] : [11.0, 8.0];
  return {
    bands: {
      severe: span(min, moderateFloor),
      moderate: span(moderateFloor, mildFloor),
      mild: span(mildFloor, threshold),
      ok: span(threshold, max),
    },
    range: span(low, high),
    marker: pct(hb),
    cutoff: pct(threshold),
    tick: pct,
  };
}

// Apply the layout to a .scale element built like the one in index.html.
export function drawScale(root, result) {
  const layout = scaleLayout(result);
  const put = (node, { left, width }) => {
    node.style.left = `${left}%`;
    node.style.width = `${width}%`;
  };
  for (const [name, part] of Object.entries(layout.bands)) put(root.querySelector(`.band-${name}`), part);
  put(root.querySelector(".scale-range"), layout.range);
  root.querySelector(".scale-marker").style.left = `${layout.marker}%`;
  root.querySelector(".scale-cutoff").style.left = `${layout.cutoff}%`;
  root.querySelectorAll("[data-tick]").forEach((tick) => {
    tick.style.left = `${layout.tick(Number(tick.dataset.tick))}%`;
  });
  return layout;
}
