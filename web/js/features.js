// Photo pixels -> colour features. A line-by-line port of src/features.py:
// the numbers must match the Python version exactly, or the model's m and b
// (learned in Python) would be applied to the wrong inputs.
// tests/web/parity.test.js checks this on real model inputs.

export const MIN_PIXELS = 50;
const EPS = 1e-6;

export class PhotoQualityError extends Error {
  constructor(code) {
    super(code);
    this.code = code; // "too_dark_or_bright"
  }
}

// Python's int() on a positive float = Math.floor.
function centerMask(height, width, fraction) {
  const mask = new Uint8Array(height * width);
  const ch = Math.max(1, Math.floor(height * fraction));
  const cw = Math.max(1, Math.floor(width * fraction));
  const top = Math.floor((height - ch) / 2);
  const left = Math.floor((width - cw) / 2);
  for (let y = top; y < top + ch; y++) mask.fill(1, y * width + left, y * width + left + cw);
  return mask;
}

function borderMask(height, width, fraction = 0.12) {
  const mask = new Uint8Array(height * width);
  const bh = Math.max(1, Math.floor(height * fraction));
  const bw = Math.max(1, Math.floor(width * fraction));
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (y < bh || y >= height - bh || x < bw || x >= width - bw) mask[y * width + x] = 1;
    }
  }
  return mask;
}

// Average colour measurements over the pixels where `select` is true,
// skipping shadow (too dark) and glare (blown-out white) pixels.
function colorStats(data, select) {
  let n = 0;
  let red = 0, green = 0, logRG = 0, bright = 0, sat = 0;
  for (let i = 0, p = 0; p < select.length; p++, i += 4) {
    if (!select[p]) continue;
    const r = data[i] / 255, g = data[i + 1] / 255, b = data[i + 2] / 255;
    const mean = (r + g + b) / 3;
    const max = Math.max(r, g, b);
    if (!(mean > 0.08 && max < 0.98)) continue;
    const min = Math.min(r, g, b);
    const total = r + g + b + EPS;
    red += r / total;
    green += g / total;
    logRG += Math.log((r + EPS) / (g + EPS));
    bright += mean;
    sat += (max - min) / (max + EPS);
    n++;
  }
  if (n === 0) return { n };
  return {
    n,
    red_chroma: red / n,
    green_chroma: green / n,
    log_red_green: logRG / n,
    brightness: bright / n,
    saturation: sat / n,
  };
}

// image: { width, height, data } where data is RGBA bytes (canvas ImageData).
export function extractFeatures(image, cropFraction = 0.5) {
  const { width, height, data } = image;
  const target = centerMask(height, width, cropFraction);
  const stats = colorStats(data, target);
  if (stats.n < MIN_PIXELS) throw new PhotoQualityError("too_dark_or_bright");

  const border = borderMask(height, width);
  for (let p = 0; p < border.length; p++) if (target[p]) border[p] = 0;
  let skin = colorStats(data, border);
  if (skin.n < MIN_PIXELS) skin = stats; // tight crop with no skin visible

  return {
    red_chroma: stats.red_chroma,
    green_chroma: stats.green_chroma,
    log_red_green: stats.log_red_green,
    brightness: stats.brightness,
    saturation: stats.saturation,
    skin_red_chroma: skin.red_chroma,
    skin_log_red_green: skin.log_red_green,
  };
}

// Python uses PIL's thumbnail((512, 512)): shrink so the longest side is <= 512.
export function fitWithin(width, height, maxSide = 512) {
  const scale = Math.min(1, maxSide / Math.max(width, height));
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}
