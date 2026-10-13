// AnaemiaLens app: screen flow, photo handling and result display.
// Everything runs on this device. The photo is deleted from memory as soon as
// the result is shown.
import { $, $$, el, prefs, setText } from "./dom.js";
import { STRINGS, t } from "./i18n.js";
import { validateModel, screen as screenResult } from "./model.js";
import { extractFeatures, PhotoQualityError } from "./features.js";
import { cropRegion, decodeFile, GUIDE_TO_CROP, ImageInputError, photoQuality } from "./image.js";
import { CameraError, captureFrame, startCamera, stopCamera } from "./camera.js";
import { DEFAULT_ENDPOINT, DEFAULT_MODEL, explainLocally, safeEndpoint } from "./explain.js";

// Refuse to run inside someone else's frame (clickjacking), even where the
// host cannot send the frame-ancestors header (e.g. GitHub Pages).
if (window.top !== window.self) {
  document.documentElement.hidden = true;
  throw new Error("framed");
}

const SCALE_MIN = 4;
const SCALE_MAX = 18;
const CONFIRM_MAX_SIDE = 1024;

const state = {
  lang: prefs.get("lang", navigator.language?.startsWith("hi") ? "hi" : "en"),
  model: null,
  person: {},
  source: null, // ImageBitmap of the photo, only while needed
  cx: 0,
  cy: 0,
  guide: 0, // nail square side, in source pixels
  current: "home",
  result: null,
  features: null,
  explain: {
    enabled: prefs.get("explain.enabled", false),
    endpoint: prefs.get("explain.endpoint", DEFAULT_ENDPOINT),
    model: prefs.get("explain.model", DEFAULT_MODEL),
  },
};

const tr = (key, vars) => t(state.lang, key, vars);
const fmt = (n) => n.toFixed(1);

/* ---------------- Language ---------------- */

function applyLanguage(lang) {
  state.lang = STRINGS[lang] ? lang : "en";
  prefs.set("lang", state.lang);
  document.documentElement.lang = state.lang;
  $$("[data-i18n]").forEach((node) => setText(node, tr(node.dataset.i18n)));
  $$("[data-i18n-label]").forEach((node) => node.setAttribute("aria-label", tr(node.dataset.i18nLabel)));
  const other = state.lang === "en" ? "hi" : "en";
  const toggle = $("#lang-toggle");
  setText(toggle, STRINGS[other]["lang.name"]);
  toggle.lang = other;
  $$('input[name="lang"]').forEach((r) => { r.checked = r.value === state.lang; });
  document.title = `AnaemiaLens · ${tr("home.kicker").split("·")[0].trim()}`;
  if (state.result) renderResult();
  if (state.current === "confirm" && state.source) updateQuality();
}

/* ---------------- Screens & history ---------------- */

function show(name, { push = true } = {}) {
  if (state.current === "camera" && name !== "camera") stopCamera($("#video"));
  $$("[data-screen]").forEach((s) => { s.hidden = s.dataset.screen !== name; });
  state.current = name;
  if (push) history.pushState({ screen: name }, "");
  window.scrollTo(0, 0);
  const heading = $(`[data-screen="${name}"] h1`);
  if (heading && name !== "home") {
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
  }
}

window.addEventListener("popstate", (event) => {
  const target = event.state?.screen ?? "home";
  // Never step "back" into a finished result or a photo that has been deleted.
  if ((target === "confirm" && !state.source) || (target === "result" && !state.result)) {
    show("home", { push: false });
    return;
  }
  show(target, { push: false });
  if (target === "camera") openCamera();
});

function showError(key) {
  const box = $(`[data-screen="${state.current}"] [data-error]`);
  if (!box) return;
  setText(box, tr(key));
  box.hidden = false;
}

function clearErrors() {
  $$("[data-error]").forEach((box) => { box.hidden = true; });
}

/* ---------------- Questions ---------------- */

function markChoice(answer, value) {
  $$(`[data-answer="${answer}"]`).forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.value === value)));
}

$$("[data-answer]").forEach((button) => {
  button.addEventListener("click", () => {
    const { answer, value } = button.dataset;
    markChoice(answer, value);
    if (answer === "sex") {
      state.person.sex = value;
      show("age");
    } else if (answer === "age") {
      state.person.age = Number(value);
      const askPregnancy = state.person.sex === "F" && state.person.age >= 15 && state.person.age < 50;
      if (!askPregnancy) state.person.pregnant = false;
      show(askPregnancy ? "pregnant" : "tips");
    } else if (answer === "pregnant") {
      // "Not sure" uses the non-pregnant cut-off, which flags more people, not fewer.
      state.person.pregnant = value === "yes";
      show("tips");
    }
  });
});

/* ---------------- Photo: camera, file, confirm ---------------- */

async function openCamera() {
  clearErrors();
  const shutter = $("#shutter");
  shutter.disabled = true;
  const status = $("#camera-status");
  status.hidden = false;
  setText(status, tr("camera.starting"));
  try {
    await startCamera($("#video"));
    status.hidden = true;
    shutter.disabled = false;
  } catch (err) {
    status.hidden = true;
    showError(err instanceof CameraError && err.code === "denied" ? "camera.denied" : "camera.unavailable");
  }
}

$("#open-camera").addEventListener("click", () => {
  show("camera");
  openCamera();
});

$("#shutter").addEventListener("click", async () => {
  const shot = await captureFrame($("#video"), $("#guide"));
  stopCamera($("#video"));
  usePhoto(shot.bitmap, shot.cx, shot.cy, shot.side);
});

for (const input of [$("#file-gallery"), $("#file-camera")]) {
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    input.value = ""; // allow choosing the same file again
    if (!file) return;
    clearErrors();
    try {
      const bitmap = await decodeFile(file);
      const short = Math.min(bitmap.width, bitmap.height);
      usePhoto(bitmap, bitmap.width / 2, bitmap.height / 2, short * 0.22);
    } catch (err) {
      showError(`error.${err instanceof ImageInputError ? err.code : "unreadable"}`);
    }
  });
}

function usePhoto(bitmap, cx, cy, side) {
  state.source?.close?.();
  state.source = bitmap;
  state.cx = cx;
  state.cy = cy;
  const short = Math.min(bitmap.width, bitmap.height);
  state.guide = Math.min(Math.max(side, short * 0.04), short * 0.5);
  $("#guide-size").value = String(Math.round((state.guide / short) * 100));
  show("confirm");
  drawConfirm();
  updateQuality();
}

const confirmCanvas = $("#confirm-canvas");

function drawConfirm() {
  const src = state.source;
  if (!src) return;
  const scale = Math.min(1, CONFIRM_MAX_SIDE / Math.max(src.width, src.height));
  confirmCanvas.width = Math.round(src.width * scale);
  confirmCanvas.height = Math.round(src.height * scale);
  const ctx = confirmCanvas.getContext("2d");
  ctx.drawImage(src, 0, 0, confirmCanvas.width, confirmCanvas.height);

  const styles = getComputedStyle(document.documentElement);
  const nail = state.guide * scale;
  const crop = nail * GUIDE_TO_CROP;
  const x = state.cx * scale, y = state.cy * scale;
  const line = Math.max(2, confirmCanvas.width / 200);

  // Dim everything outside the area the model will look at.
  ctx.save();
  ctx.fillStyle = "rgba(10, 12, 13, 0.55)";
  ctx.beginPath();
  ctx.rect(0, 0, confirmCanvas.width, confirmCanvas.height);
  ctx.rect(x - crop / 2, y - crop / 2, crop, crop);
  ctx.fill("evenodd");
  ctx.restore();

  ctx.lineWidth = line;
  ctx.setLineDash([line * 3, line * 2]);
  ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
  ctx.strokeRect(x - crop / 2, y - crop / 2, crop, crop);
  ctx.setLineDash([]);
  ctx.lineWidth = line * 1.5;
  ctx.strokeStyle = styles.getPropertyValue("--accent").trim() || "#0b6e69";
  ctx.beginPath();
  ctx.roundRect(x - nail / 2, y - nail / 2, nail, nail, nail * 0.12);
  ctx.stroke();
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = line * 0.6;
  ctx.stroke();
  confirmCanvas.setAttribute("aria-label", tr("confirm.title"));
}

function cropForModel() {
  return cropRegion(state.source, state.cx, state.cy, state.guide * GUIDE_TO_CROP);
}

let qualityFrame = 0;
function updateQuality() {
  cancelAnimationFrame(qualityFrame);
  qualityFrame = requestAnimationFrame(() => {
    if (!state.source) return;
    const quality = photoQuality(cropForModel());
    const box = $("#quality");
    box.dataset.state = quality === "ok" ? "ok" : quality === "glare" ? "warn" : "bad";
    setText(box, tr(`quality.${quality}`));
  });
}

confirmCanvas.addEventListener("click", (event) => {
  const rect = confirmCanvas.getBoundingClientRect();
  state.cx = ((event.clientX - rect.left) / rect.width) * state.source.width;
  state.cy = ((event.clientY - rect.top) / rect.height) * state.source.height;
  drawConfirm();
  updateQuality();
});

$("#guide-size").addEventListener("input", (event) => {
  const short = Math.min(state.source.width, state.source.height);
  state.guide = (Number(event.target.value) / 100) * short;
  drawConfirm();
  updateQuality();
});

$("#retake").addEventListener("click", () => {
  forgetPhoto();
  history.back();
});

$("#use-photo").addEventListener("click", () => {
  clearErrors();
  let features;
  try {
    features = extractFeatures(cropForModel(), state.model.crop_fraction);
  } catch (err) {
    showError(`error.${err instanceof PhotoQualityError ? err.code : "unreadable"}`);
    return;
  }
  state.features = features;
  state.result = screenResult(state.model, features, state.person);
  forgetPhoto();
  show("result");
  renderResult();
  if (state.explain.enabled) setText($("#explain-text"), "");
});

function forgetPhoto() {
  state.source?.close?.();
  state.source = null;
  confirmCanvas.width = confirmCanvas.height = 0;
}

/* ---------------- Result ---------------- */

const pct = (v) => `${((Math.min(Math.max(v, SCALE_MIN), SCALE_MAX) - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)) * 100}%`;

function place(node, from, to) {
  node.style.left = pct(from);
  node.style.width = `calc(${pct(to)} - ${pct(from)})`;
}

function status(result) {
  const crosses = result.low < result.threshold && result.high >= result.threshold;
  if (crosses && (result.severity === "none" || result.severity === "mild")) return "borderline";
  return result.severity;
}

function renderResult() {
  const r = state.result;
  if (!r) return;
  const s = status(r);
  $("#result-card").dataset.severity = s;
  setText($("#hb-value"), fmt(r.hb));
  setText($("#hb-range"), tr("result.range", { low: fmt(r.low), high: fmt(r.high) }));
  setText($("#hb-cutoff"), tr("result.cutoff", { threshold: fmt(r.threshold) }));
  setText($("#verdict-title"), tr(`sev.${s}.t`));
  setText($("#verdict-text"), tr(`sev.${s}.d`));
  const icon = s === "none" ? "none" : s === "severe" ? "severe" : "warn";
  // SVG elements have no .hidden property, so set the attribute itself.
  $$(".verdict-icon").forEach((svg) => svg.toggleAttribute("hidden", svg.dataset.icon !== icon));

  // Number line: the four WHO bands for THIS person, the estimate and its range.
  const [mildFloor, moderateFloor] = r.threshold === 11.0 ? [10.0, 7.0] : [11.0, 8.0];
  place($("#band-severe"), SCALE_MIN, moderateFloor);
  place($("#band-moderate"), moderateFloor, mildFloor);
  place($("#band-mild"), mildFloor, r.threshold);
  place($("#band-ok"), r.threshold, SCALE_MAX);
  place($("#scale-range"), r.low, r.high);
  $("#scale-marker").style.left = pct(r.hb);
  $("#scale-cutoff").style.left = pct(r.threshold);
  $$("[data-tick]").forEach((tick) => { tick.style.left = pct(Number(tick.dataset.tick)); });
  setText($("#scale-caption"), tr("result.scale.cutoff", { threshold: fmt(r.threshold) }));
  $("#scale").setAttribute("aria-label",
    `${tr("result.scale")}: ${tr("result.scale.you")} ${fmt(r.hb)} g/dL. ${tr("result.scale.cutoff", { threshold: fmt(r.threshold) })} g/dL.`);

  // The numbers behind it, for the curious (and for judges).
  const list = $("#feature-list");
  list.replaceChildren();
  for (const name of state.model.feature_names) {
    list.append(el("dt", name), el("dd", state.features[name].toFixed(4)));
  }
  const { mean, std, w, b } = state.model.multi;
  let intercept = b;
  const terms = state.model.feature_names.map((name, i) => {
    const slope = w[i] / std[i];
    intercept -= (w[i] * mean[i]) / std[i];
    return `${slope >= 0 ? "+" : "−"} ${Math.abs(slope).toFixed(2)} × ${name}`;
  });
  setText($("#formula"), `Hb = ${intercept.toFixed(2)} ${terms.join(" ")}`);

  $("#explain").hidden = !state.explain.enabled;
  setText($("#announcer"), `${tr("result.estimate")} ${fmt(r.hb)} g/dL. ${tr(`sev.${s}.t`)}.`);
}

$("#explain-go").addEventListener("click", async () => {
  const out = $("#explain-text");
  const button = $("#explain-go");
  button.disabled = true;
  setText(out, tr("explain.working"));
  try {
    const text = await explainLocally(state.result, {
      language: tr("lang.llm"),
      endpoint: state.explain.endpoint,
      model: state.explain.model,
    });
    setText(out, text); // plain text only, never HTML
  } catch {
    setText(out, tr("explain.failed"));
  } finally {
    button.disabled = false;
  }
});

$("#again").addEventListener("click", () => {
  state.person = {};
  state.result = null;
  state.features = null;
  $$("[data-answer]").forEach((b) => b.removeAttribute("aria-pressed"));
  setText($("#explain-text"), "");
  show("sex");
});

/* ---------------- Settings & dialogs ---------------- */

const settings = $("#settings");
$("#open-settings").addEventListener("click", () => {
  $("#explain-enabled").checked = state.explain.enabled;
  $("#explain-endpoint").value = state.explain.endpoint;
  $("#explain-model").value = state.explain.model;
  $("#endpoint-error").hidden = true;
  settings.showModal();
});

$$('input[name="lang"]').forEach((radio) => radio.addEventListener("change", () => applyLanguage(radio.value)));

settings.addEventListener("close", () => {
  const endpoint = safeEndpoint($("#explain-endpoint").value.trim());
  state.explain.enabled = $("#explain-enabled").checked;
  if (endpoint) state.explain.endpoint = endpoint;
  state.explain.model = $("#explain-model").value.trim().slice(0, 100) || DEFAULT_MODEL;
  prefs.set("explain.enabled", state.explain.enabled);
  prefs.set("explain.endpoint", state.explain.endpoint);
  prefs.set("explain.model", state.explain.model);
  if (state.result) $("#explain").hidden = !state.explain.enabled;
});

$("#explain-endpoint").addEventListener("input", (event) => {
  $("#endpoint-error").hidden = Boolean(safeEndpoint(event.target.value.trim()));
});

$$("[data-open]").forEach((button) => button.addEventListener("click", () => $(`#${button.dataset.open}`).showModal()));
$$("[data-back]").forEach((button) => button.addEventListener("click", () => history.back()));
$("#lang-toggle").addEventListener("click", () => applyLanguage(state.lang === "en" ? "hi" : "en"));

/* ---------------- Start ---------------- */

$("#start").addEventListener("click", () => show("sex"));

async function init() {
  history.replaceState({ screen: "home" }, "");
  applyLanguage(state.lang);
  try {
    const response = await fetch("model.json", { cache: "no-cache" });
    state.model = validateModel(await response.json());
  } catch {
    const start = $("#start");
    start.disabled = true;
    setText(start, tr("error.model"));
    return;
  }
  $("#demo-banner").hidden = !state.model.simulated;
}

init();
