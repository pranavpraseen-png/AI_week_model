// Safe handling of the user's photo: validate, decode, crop, read pixels.
// The photo only ever lives in memory on this device; nothing is uploaded.
import { fitWithin } from "./features.js";

export const MAX_FILE_BYTES = 15 * 1024 * 1024;
const MAX_PIXELS = 40_000_000; // a small file can declare a huge image ("decompression bomb")
const DECODE_MAX_SIDE = 2048; // plenty for a nail crop, gentle on cheap phones' memory

// The model measures the middle 50% of the crop (the nail) and a thin outer frame
// (the skin around it). So the crop is twice the size of the on-screen guide
// square that the user fills with their nail.
export const GUIDE_TO_CROP = 1 / 0.5;

export class ImageInputError extends Error {
  constructor(code) {
    super(code);
    this.code = code; // "too_big" | "not_image" | "unreadable" | "too_small"
  }
}

// Identify the format from the file's first bytes. The file name and the
// browser-reported type can both be wrong; the bytes cannot.
export function sniffType(b) {
  if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "jpeg";
  if (b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) return "png";
  const ascii = (from, to) => String.fromCharCode(...b.subarray(from, to));
  if (ascii(0, 4) === "RIFF" && ascii(8, 12) === "WEBP") return "webp";
  return null;
}

// Read width/height from the file header without decoding the image.
export function readDimensions(b, type) {
  const u16be = (i) => (b[i] << 8) | b[i + 1];
  const u32be = (i) => ((b[i] << 24) >>> 0) + (b[i + 1] << 16) + (b[i + 2] << 8) + b[i + 3];
  const u16le = (i) => b[i] | (b[i + 1] << 8);
  const u24le = (i) => b[i] | (b[i + 1] << 8) | (b[i + 2] << 16);
  if (type === "png") return { width: u32be(16), height: u32be(20) };
  if (type === "jpeg") {
    let i = 2;
    while (i + 9 < b.length) {
      if (b[i] !== 0xff) { i++; continue; }
      const marker = b[i + 1];
      // Start-of-frame markers carry the size (C0-CF except C4 DHT, C8 JPG, CC DAC).
      if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) {
        return { width: u16be(i + 7), height: u16be(i + 5) };
      }
      if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) { i += 2; continue; }
      i += 2 + u16be(i + 2);
    }
    return null;
  }
  if (type === "webp") {
    const chunk = String.fromCharCode(...b.subarray(12, 16));
    if (chunk === "VP8X") return { width: 1 + u24le(24), height: 1 + u24le(27) };
    if (chunk === "VP8L") {
      const bits = b[21] | (b[22] << 8) | (b[23] << 16) | (b[24] << 24);
      return { width: 1 + (bits & 0x3fff), height: 1 + ((bits >> 14) & 0x3fff) };
    }
    if (chunk === "VP8 ") return { width: u16le(26) & 0x3fff, height: u16le(28) & 0x3fff };
  }
  return null;
}

export async function decodeFile(file) {
  if (!file) throw new ImageInputError("not_image");
  if (file.size > MAX_FILE_BYTES) throw new ImageInputError("too_big");
  // JPEG headers can sit after a large EXIF block (thumbnails), so read generously.
  const head = new Uint8Array(await file.slice(0, 256 * 1024).arrayBuffer());
  const type = sniffType(head);
  if (!type) throw new ImageInputError("not_image");
  const dims = readDimensions(head, type);
  if (!dims || !dims.width || !dims.height) throw new ImageInputError("unreadable");
  if (dims.width * dims.height > MAX_PIXELS) throw new ImageInputError("too_big");
  if (Math.min(dims.width, dims.height) < 64) throw new ImageInputError("too_small");

  // EXIF rotation can swap width and height, so decode once at full orientation
  // (imageOrientation defaults to "from-image"), then shrink if needed.
  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new ImageInputError("unreadable");
  }
  if (Math.max(bitmap.width, bitmap.height) > DECODE_MAX_SIDE) {
    const size = fitWithin(bitmap.width, bitmap.height, DECODE_MAX_SIDE);
    const small = await createImageBitmap(bitmap, { resizeWidth: size.width, resizeHeight: size.height, resizeQuality: "high" });
    bitmap.close();
    bitmap = small;
  }
  return bitmap;
}

// Square crop centred on (cx, cy) with side `side` (source pixels), clamped to
// the image, scaled down to at most 512 px like the Python pipeline.
export function cropRegion(source, cx, cy, side) {
  const sw = source.width;
  const sh = source.height;
  const s = Math.max(16, Math.min(side, sw, sh));
  const x = Math.min(Math.max(cx - s / 2, 0), sw - s);
  const y = Math.min(Math.max(cy - s / 2, 0), sh - s);
  const size = fitWithin(Math.round(s), Math.round(s));
  const canvas = document.createElement("canvas");
  canvas.width = size.width;
  canvas.height = size.height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, x, y, s, s, 0, 0, size.width, size.height);
  return ctx.getImageData(0, 0, size.width, size.height);
}

// Capture-quality signals, measured on the nail area (middle half of the crop).
export function photoQuality(imageData) {
  const { width, height, data } = imageData;
  const x0 = Math.floor(width / 4), x1 = Math.ceil((width * 3) / 4);
  const y0 = Math.floor(height / 4), y1 = Math.ceil((height * 3) / 4);
  let sum = 0, glare = 0, n = 0;
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const i = (y * width + x) * 4;
      const r = data[i], g = data[i + 1], b = data[i + 2];
      sum += (r + g + b) / 3;
      if (Math.max(r, g, b) >= 250) glare++;
      n++;
    }
  }
  const mean = sum / n / 255;
  if (mean < 0.18) return "dark";
  if (mean > 0.92) return "bright";
  if (glare / n > 0.12) return "glare";
  return "ok";
}
