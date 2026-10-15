// The opening page ("Kinetic Reveal"): the word HAEMOGLOBIN running behind a
// cluster of live red cells, a phone showing one finished check of a simulated
// photo (measured by this app's model), the 57-in-100 grid, a pinned phone that
// runs a check while the nail's colour follows haemoglobin as you scroll, the
// fitted line, and privacy / accounts / languages panels that slide sideways on
// wide screens. Everything is drawn on this device with plain SVG and CSS;
// nothing is downloaded. With "reduce motion" switched on, every effect shows its
// finished, still state instead, and the panels simply stack.
import { drawScale } from "./scale.js";

const SVG_NS = "http://www.w3.org/2000/svg";

const PALE = [238, 214, 205]; // same nail colours as src/make_simulated_data.py
const RED = [214, 112, 112];
const HB_MIN = 5;
const HB_MAX = 18;

export function nailColor(hb) {
  const t = Math.min(1, Math.max(0, (hb - HB_MIN) / (HB_MAX - HB_MIN)));
  return PALE.map((p, i) => Math.round(p * (1 - t) + RED[i] * t));
}

// WHO bands for a non-pregnant woman (cut-off 12 g/dL).
export function storyBand(hb) {
  if (hb < 8) return "severe";
  if (hb < 11) return "moderate";
  if (hb < 12) return "mild";
  return "healthy";
}

/* ---------------- Live red cells ---------------- */

// A cluster of red cells behind the phone, drawn as SVG circles that melt into one
// another (a blur + contrast filter, the "goo" in index.html). Each cell drifts on
// its own slow loop and moves aside for your finger or mouse. A paler middle on the
// bigger cells hints at the dimple of a real red blood cell.
const SVG_CELLS = [
  { dx: -170, dy: -30, r: 98, ax: 46, ay: 30, f: 0.42, ph: 0.2 },
  { dx: 40, dy: -90, r: 122, ax: 38, ay: 42, f: 0.33, ph: 1.7 },
  { dx: 215, dy: 30, r: 90, ax: 54, ay: 34, f: 0.38, ph: 3.1 },
  { dx: -20, dy: 105, r: 80, ax: 60, ay: 22, f: 0.47, ph: 4.4 },
  { dx: 170, dy: 140, r: 50, ax: 46, ay: 30, f: 0.56, ph: 2.4 },
  { dx: -270, dy: 110, r: 42, ax: 40, ay: 36, f: 0.61, ph: 5.2 },
  { dx: 310, dy: -150, r: 38, ax: 30, ay: 44, f: 0.52, ph: 0.9 },
  { dx: -130, dy: -200, r: 30, ax: 50, ay: 30, f: 0.7, ph: 3.8 },
  { dx: 90, dy: 60, r: 22, ax: 120, ay: 80, f: 0.5, ph: 1.1 },
  { dx: -90, dy: 40, r: 18, ax: 110, ay: 90, f: 0.44, ph: 2.9 },
];

const easeOut = (t) => 1 - (1 - Math.min(1, Math.max(0, t))) ** 3;

class Cells {
  constructor(svg, hero, anchor, { still }) {
    this.svg = svg;
    this.hero = hero;
    this.anchor = anchor; // the cells gather around this element (the phone)
    this.still = still;
    const goo = svg.querySelector(".cells-goo");
    const circle = (fill) => {
      const node = document.createElementNS(SVG_NS, "circle");
      node.setAttribute("fill", fill);
      goo.append(node);
      return node;
    };
    this.cells = SVG_CELLS.map((c, i) => ({
      ...c,
      body: circle("url(#cell-fill)"),
      pale: c.r > 40 ? circle("#e66a66") : null,
      ox: 0,
      oy: 0,
      delay: 0.08 * i,
    }));
    this.follower = { body: circle("url(#cell-fill)"), pale: circle("#e66a66"), x: 0, y: 0, r: 0 };
    this.pointer = { x: 0, y: 0, in: false };
    this.t0 = performance.now();
    this.running = false;
    hero.addEventListener("pointermove", (e) => {
      const rect = svg.getBoundingClientRect();
      this.pointer.x = e.clientX - rect.left;
      this.pointer.y = e.clientY - rect.top;
      this.pointer.in = true;
    }, { passive: true });
    hero.addEventListener("pointerleave", () => { this.pointer.in = false; });
    this.layout();
    window.addEventListener("resize", () => this.layout(), { passive: true });
  }

  layout() {
    const box = this.svg.getBoundingClientRect();
    const at = this.anchor.getBoundingClientRect();
    const narrow = box.width < 900;
    this.cx = at.left - box.left + at.width / 2;
    this.cy = at.top - box.top + at.height * (narrow ? 0.3 : 0.4);
    this.scale = narrow ? Math.min(0.5, Math.max(0.3, box.width / 1100)) : Math.min(1.1, Math.max(0.6, Math.min(box.width / 1440, box.height / 860)));
    this.draw(this.still ? 1e3 : performance.now());
  }

  draw(now) {
    const t = this.still ? 7.3 : (now - this.t0) / 1000;
    const s = this.scale;
    const put = (node, x, y, r) => {
      node.setAttribute("cx", x.toFixed(1));
      node.setAttribute("cy", y.toFixed(1));
      node.setAttribute("r", Math.max(0, r).toFixed(1));
    };
    for (const c of this.cells) {
      const grow = this.still ? 1 : easeOut((t - 0.25 - c.delay) / 1.1);
      let x = this.cx + (c.dx + Math.sin(t * c.f + c.ph) * c.ax) * s;
      let y = this.cy + (c.dy + Math.cos(t * c.f * 0.83 + c.ph * 1.3) * c.ay) * s;
      let tx = 0;
      let ty = 0;
      if (this.pointer.in && !this.still) { // the pointer gently parts the cells
        const dx = x - this.pointer.x;
        const dy = y - this.pointer.y;
        const d = Math.hypot(dx, dy) || 1;
        const reach = (220 + c.r) * s;
        if (d < reach) {
          const k = (1 - d / reach) * 70 * s;
          tx = (dx / d) * k;
          ty = (dy / d) * k;
        }
      }
      c.ox += (tx - c.ox) * 0.08;
      c.oy += (ty - c.oy) * 0.08;
      x += c.ox;
      y += c.oy;
      const r = c.r * s * grow;
      put(c.body, x, y, r);
      if (c.pale) put(c.pale, x, y, r * 0.4);
    }
    // One cell rests inside the cluster and follows the pointer when it comes near.
    const f = this.follower;
    const restX = this.cx + (-60 + Math.sin(t * 0.5) * 40) * s;
    const restY = this.cy + (20 + Math.cos(t * 0.4) * 30) * s;
    const goX = this.pointer.in && !this.still ? this.pointer.x : restX;
    const goY = this.pointer.in && !this.still ? this.pointer.y : restY;
    if (this.still || !f.r) { f.x = goX; f.y = goY; } else { f.x += (goX - f.x) * 0.07; f.y += (goY - f.y) * 0.07; }
    const fr = 58 * s * (this.still ? 1 : easeOut((t - 0.6) / 1.2));
    f.r += (fr - f.r) * (this.still ? 1 : 0.2);
    put(f.body, f.x, f.y, f.r);
    put(f.pale, f.x, f.y, f.r * 0.4);
  }

  start() {
    if (this.running || this.still) return;
    this.running = true;
    const frame = (now) => {
      if (!this.running) return;
      this.draw(now);
      this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.raf);
  }
}

/* ---------------- The HAEMOGLOBIN marquee ---------------- */

// Each row is one word repeated wide enough to cover the screen twice, moved
// sideways a little every frame (faster while you scroll). Still: it just stands.
class Marquee {
  constructor(root, { still }) {
    this.still = still;
    this.rows = [...root.querySelectorAll(".marquee-row")].map((row) => ({
      track: row.querySelector(".marquee-track"),
      speed: Number(row.dataset.speed) || 0.4,
      w: 1,
      x: 0,
    }));
    this.running = false;
    this.lastY = window.scrollY;
    this.boost = 0;
  }

  layout() {
    const width = document.documentElement.clientWidth;
    for (const row of this.rows) {
      const unit = row.track.firstElementChild;
      while (row.track.childElementCount > 1) row.track.lastElementChild.remove();
      row.w = unit.getBoundingClientRect().width || 1;
      const copies = Math.ceil((width * 2) / row.w) + 1;
      for (let i = 0; i < copies; i++) row.track.append(unit.cloneNode(true));
      row.x = row.speed < 0 ? 0 : -row.w;
      row.track.style.setProperty("--mx", `${row.x.toFixed(1)}px`);
    }
  }

  step(dt) {
    const y = window.scrollY;
    this.boost += (Math.min(Math.abs(y - this.lastY), 80) - this.boost) * 0.2;
    this.lastY = y;
    for (const row of this.rows) {
      row.x += row.speed * 120 * dt * (1 + this.boost * 0.12);
      if (row.x <= -row.w) row.x += row.w;
      if (row.x > 0) row.x -= row.w;
      row.track.style.setProperty("--mx", `${row.x.toFixed(1)}px`);
    }
  }

  start() {
    if (this.running || this.still) return;
    this.running = true;
    let last = performance.now();
    const frame = (now) => {
      if (!this.running) return;
      this.step(Math.min(0.05, (now - last) / 1000));
      last = now;
      this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.raf);
  }
}

/* ---------------- Text and reveals ---------------- */

// Wrap each word in two spans so CSS can slide it up from behind a mask.
export function splitWords(el) {
  const words = el.textContent.trim().split(/\s+/);
  el.replaceChildren();
  el.style.setProperty("--n", String(words.length)); // lets CSS shade each word along the line
  words.forEach((word, i) => {
    const outer = document.createElement("span");
    outer.className = "word";
    const inner = document.createElement("span");
    inner.textContent = word;
    inner.style.setProperty("--i", String(i));
    outer.append(inner);
    el.append(outer, document.createTextNode(" "));
  });
}

// Count a number up from zero (ease-out cubic). data-dp = decimal places.
export function countText(target, t, dp = 0, suffix = "") {
  const eased = 1 - (1 - Math.min(1, Math.max(0, t))) ** 3;
  return `${(target * eased).toFixed(dp)}${suffix}`;
}

function countUp(el, still, delay = 0) {
  const target = Number(el.dataset.count);
  const dp = Number(el.dataset.dp ?? 0);
  const suffix = el.dataset.suffix ?? "";
  if (still) {
    el.textContent = countText(target, 1, dp, suffix);
    return;
  }
  el.textContent = countText(target, 0, dp, suffix);
  const begin = performance.now() + delay;
  const tick = (now) => {
    const t = (now - begin) / 1600;
    el.textContent = countText(target, t, dp, suffix);
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/* ---------------- 57 in every 100 women ---------------- */

function buildHundred(grid) {
  const filled = Number(grid.dataset.filled);
  grid.replaceChildren();
  for (let i = 0; i < 100; i++) {
    const dot = document.createElement("i");
    if (i < filled) dot.className = "on";
    dot.style.setProperty("--i", String(i));
    grid.append(dot);
  }
}

/* ---------------- Example trend on the accounts card ---------------- */

const svgEl = (tag, attrs, parent) => {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  parent.append(node);
  return node;
};

function buildDemoTrend(svg) {
  const values = [9.4, 9.8, 10.1, 10.4, 10.9, 11.3, 11.8]; // an example, not anyone's data
  const cut = 12;
  const x = (i) => 8 + (i / (values.length - 1)) * 440;
  const y = (v) => 12 + (1 - (v - 8.5) / 4.3) * 118;
  svg.replaceChildren();
  svgEl("line", { class: "trend-cut", x1: 8, x2: 470, y1: y(cut), y2: y(cut) }, svg);
  svgEl("text", { class: "trend-t trend-t-cut", x: 478, y: y(cut) + 4 }, svg).textContent = "12.0";
  const d = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  svgEl("path", { class: "trend-area", d: `${d} L${x(values.length - 1)} 138 L${x(0)} 138 Z` }, svg);
  svgEl("path", { class: "trend-line", d }, svg);
  values.forEach((v, i) => {
    svgEl("circle", { class: i === values.length - 1 ? "trend-dot trend-dot-last" : "trend-dot", cx: x(i), cy: y(v), r: i === values.length - 1 ? 6 : 4.5 }, svg);
  });
  svgEl("text", { class: "trend-t", x: x(values.length - 1) + 12, y: y(values.at(-1)) + 18 }, svg).textContent = "11.8";
}

/* ---------------- Regression chart ---------------- */

// A fixed, believable cloud of points around Hb = 19.4 x + 2.28 (the hand-worked example).
function chartPoints() {
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  return Array.from({ length: 26 }, () => {
    const x = 0.28 + rand() * 0.26;
    return { x, y: 19.4 * x + 2.28 + (rand() - 0.5) * 2.2 };
  });
}

function buildChart(svg) {
  const sx = (x) => 48 + ((x - 0.26) / 0.3) * 520;
  const sy = (y) => 296 - ((y - 6) / 10) * 260;
  // Hairline grid, number labels and the WHO cut-off for women (12 g/dL), dashed.
  const grid = svg.querySelector(".fit-grid");
  grid.replaceChildren();
  for (const v of [8, 10, 14]) {
    svgEl("line", { class: "fit-gridline", x1: 48, x2: 584, y1: sy(v), y2: sy(v) }, grid);
  }
  for (const v of [8, 10, 12, 14]) {
    svgEl("text", { class: "fit-t", x: 38, y: sy(v) + 5, "text-anchor": "end" }, grid).textContent = String(v);
  }
  for (const v of [0.3, 0.4, 0.5]) {
    svgEl("line", { class: "fit-axis-tick", x1: sx(v), x2: sx(v), y1: 296, y2: 302 }, grid);
    svgEl("text", { class: "fit-t", x: sx(v), y: 322, "text-anchor": "middle" }, grid).textContent = v.toFixed(2);
  }
  svgEl("text", { class: "fit-t fit-t-axis", x: 52, y: 14 }, grid).textContent = "Hb g/dL";
  svgEl("text", { class: "fit-t fit-t-axis", x: 584, y: 284, "text-anchor": "end" }, grid).textContent = "R/(R+G+B)"; // above the axis, in the empty corner
  svgEl("line", { class: "fit-cut", x1: 48, x2: 584, y1: sy(12), y2: sy(12) }, grid);
  svgEl("text", { class: "fit-t fit-t-cut", x: 58, y: sy(12) - 8 }, grid).textContent = "WHO 12.0"; // left: low redness never reaches 12
  const dots = svg.querySelector(".fit-dots");
  dots.replaceChildren();
  chartPoints().forEach((p, i) => {
    const dot = svgEl("circle", { cx: sx(p.x).toFixed(1), cy: sy(p.y).toFixed(1), r: 6 }, dots);
    if (p.y < 12) dot.setAttribute("class", "low");
    dot.style.setProperty("--i", String(i));
  });
  const line = svg.querySelector(".fit-line");
  line.setAttribute("x1", sx(0.26).toFixed(1));
  line.setAttribute("y1", sy(19.4 * 0.26 + 2.28).toFixed(1));
  line.setAttribute("x2", sx(0.56).toFixed(1));
  line.setAttribute("y2", sy(19.4 * 0.56 + 2.28).toFixed(1));
}

/* ---------------- The reveal: the phone runs a check as you scroll ---------------- */

// The colour numbers of a plain colour, worked out the same way as for a photo.
export function chroma([r, g, b]) {
  return { red: r / (r + g + b), lnRG: Math.log(r / g) };
}

// Which of the four steps is lit at scroll progress p (0 → 1).
export function storyStep(p) {
  return Math.min(4, 1 + Math.floor(Math.max(0, p) * 4));
}

function storyUpdater(root, onBand) {
  const stage = root.querySelector(".story-stage");
  const nail = root.querySelector("#story-nail");
  const value = root.querySelector("#story-hb");
  const scale = root.querySelector("#story-scale");
  const chromaRed = root.querySelector("#story-chroma-r");
  const chromaLn = root.querySelector("#story-chroma-l");
  const steps = [...root.querySelectorAll("#story-steps li")];
  let lastBand = null;
  let lastStep = 0;
  return () => {
    const rect = root.getBoundingClientRect();
    const travel = rect.height - window.innerHeight;
    const p = travel > 0 ? Math.min(1, Math.max(0, -rect.top / travel)) : 1;
    const hb = 6 + p * 10; // 6 → 16 g/dL as you scroll
    const rgb = nailColor(hb);
    nail.style.setProperty("fill", `rgb(${rgb.join(", ")})`);
    const c = chroma(rgb);
    chromaRed.textContent = c.red.toFixed(3);
    chromaLn.textContent = c.lnRG.toFixed(3);
    value.textContent = hb.toFixed(1);
    drawScale(scale, { hb, threshold: 12 }); // WHO bands for a non-pregnant woman
    stage.style.setProperty("--p", p.toFixed(3));
    // The hint disappears outright once you start scrolling: half-faded text would be unreadable.
    stage.classList.toggle("is-scrolled", p > 0.08);
    const step = storyStep(p);
    if (step !== lastStep) {
      lastStep = step;
      stage.dataset.step = String(step);
      steps.forEach((li) => li.classList.toggle("is-on", Number(li.dataset.step) <= step));
      steps.forEach((li) => {
        if (Number(li.dataset.step) === step) li.setAttribute("aria-current", "step");
        else li.removeAttribute("aria-current");
      });
    }
    const band = storyBand(hb);
    if (band !== lastBand) {
      lastBand = band;
      root.dataset.band = band;
      onBand(band);
    }
  };
}

/* ---------------- Privacy, accounts, languages: sideways on wide screens ---------------- */

// On a wide, tall screen (and with motion allowed) the three panels sit side by
// side and scrolling down slides them left. If any panel's content would not fit
// the screen, or anything else is off, they simply stack as normal sections.
class Panels {
  constructor(root, { still }) {
    this.root = root;
    this.still = still;
    this.track = root.querySelector(".panels-track");
    this.panels = [...this.track.children];
    this.rail = [...root.querySelectorAll(".panels-rail li")];
    this.wide = window.matchMedia("(min-width: 1100px) and (min-height: 700px)");
    this.on = false;
    this.top = 0;
    this.step = 0;
    this.track.addEventListener("focusin", (event) => {
      if (!this.on) return;
      const i = this.panels.findIndex((panel) => panel.contains(event.target));
      if (i >= 0 && Math.round(this.offset() / this.step) !== i) {
        this.track.scrollLeft = 0;
        window.scrollTo({ top: this.scrollFor(i) });
      }
    });
  }

  measure() {
    const want = this.wide.matches && !this.still;
    this.root.classList.toggle("is-sideways", want);
    this.on = want;
    if (want) {
      const height = window.innerHeight;
      // Every panel must fit the screen; otherwise fall back to stacked sections.
      this.root.classList.add("is-measuring");
      const fits = this.panels.every((panel) => panel.offsetHeight <= height + 1);
      this.root.classList.remove("is-measuring");
      if (!fits) {
        this.on = false;
        this.root.classList.remove("is-sideways");
      }
    }
    if (this.on) {
      this.step = document.documentElement.clientWidth;
      this.root.style.setProperty("--travel", `${(this.panels.length - 1) * this.step}px`);
    } else {
      this.root.style.removeProperty("--travel");
      this.track.style.removeProperty("--x");
    }
    this.top = this.root.getBoundingClientRect().top + window.scrollY;
    this.update();
  }

  offset() {
    // Measured fresh each time: anything above can change height (fonts, language).
    this.top = this.root.getBoundingClientRect().top + window.scrollY;
    const max = (this.panels.length - 1) * this.step;
    return Math.min(max, Math.max(0, window.scrollY - this.top));
  }

  scrollFor(i) {
    this.top = this.root.getBoundingClientRect().top + window.scrollY;
    return this.on ? this.top + i * this.step : this.panels[i].getBoundingClientRect().top + window.scrollY;
  }

  update() {
    const i = this.on ? Math.round(this.offset() / this.step) : -1;
    if (this.on) this.track.style.setProperty("--x", `${(-this.offset()).toFixed(1)}px`);
    this.rail.forEach((li, n) => li.classList.toggle("is-on", n === i));
  }

  // Jump to a panel by its id (used by the top bar's links).
  scrollTo(id, behavior) {
    const i = this.panels.findIndex((panel) => panel.id === id);
    if (i < 0) return false;
    window.scrollTo({ top: this.scrollFor(i), behavior });
    return true;
  }
}

/* ---------------- Wiring ---------------- */

export function initIntro(root, { onBand = () => {}, words = () => ({ en: "", local: "" }) } = {}) {
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hero = root.querySelector(".hero");
  const device = root.querySelector(".device-hero");
  const marquee = new Marquee(root.querySelector(".marquee"), { still });
  const cells = new Cells(root.querySelector("#cells"), hero, device, { still });
  const panels = new Panels(root.querySelector("#panels"), { still });

  const fillWords = () => {
    const w = words();
    root.querySelectorAll('[data-word="en"]').forEach((el) => { el.textContent = w.en.toLocaleUpperCase("en"); });
    root.querySelectorAll('[data-word="local"]').forEach((el) => { el.textContent = w.local; });
    marquee.layout();
  };

  root.querySelectorAll("[data-split]").forEach(splitWords);
  buildHundred(root.querySelector("#hundred"));
  buildDemoTrend(root.querySelector("#demo-trend"));

  // The example check on the phone: its numbers count up and the needle travels
  // to 10.4 while the scan line passes over the photo. Still: drawn at once.
  const example = { hb: 10.43, low: 10.1, high: 10.76, threshold: 12 }; // india_0062.png, this model
  const specimenScale = root.querySelector("#specimen-scale");
  drawScale(specimenScale, still ? example : { ...example, hb: 4, low: 4, high: 4 });
  root.querySelectorAll(".specimen [data-count]").forEach((el, i) => countUp(el, still, 900 + i * 70));
  requestAnimationFrame(() => {
    hero.classList.add("is-in");
    if (!still) setTimeout(() => drawScale(specimenScale, example), 1100);
  });

  // The phone leans a little towards your pointer (desktop only, motion allowed).
  if (!still) {
    hero.addEventListener("pointermove", (e) => {
      if (e.pointerType !== "mouse") return;
      const rect = hero.getBoundingClientRect();
      device.style.setProperty("--lean-x", ((e.clientX - rect.left) / rect.width - 0.5).toFixed(3));
      device.style.setProperty("--lean-y", ((e.clientY - rect.top) / rect.height - 0.5).toFixed(3));
    }, { passive: true });
    hero.addEventListener("pointerleave", () => {
      device.style.setProperty("--lean-x", "0");
      device.style.setProperty("--lean-y", "0");
    });
  }

  // The marquee and the cells move only while the opening is on screen and the tab is visible.
  let heroVisible = true;
  const play = () => {
    if (heroVisible && !document.hidden && !root.hidden) {
      marquee.start();
      cells.start();
    } else {
      marquee.stop();
      cells.stop();
    }
  };
  new IntersectionObserver(([entry]) => {
    heroVisible = entry.isIntersecting;
    play();
  }).observe(hero);
  document.addEventListener("visibilitychange", play);

  // Reveal sections, count numbers and draw the chart as they scroll into view.
  const chart = root.querySelector("#fit-chart");
  buildChart(chart);
  const reveal = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add("is-visible");
      entry.target.querySelectorAll("[data-count]").forEach((el) => countUp(el, still));
      reveal.unobserve(entry.target);
    }
  }, { threshold: 0.1 }); // low, so even a long section in a long language is revealed on a small phone
  root.querySelectorAll("[data-reveal]").forEach((el) => {
    if (still) el.classList.add("is-visible");
    reveal.observe(el);
  });

  const story = root.querySelector(".story");
  const update = storyUpdater(story, onBand);
  let queued = false;
  const onScroll = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      update();
      panels.update();
    });
  };
  const onResize = () => {
    fillWords();
    cells.layout();
    panels.measure();
    onScroll();
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onResize, { passive: true });
  fillWords();
  panels.measure();
  update();
  // Fonts change the size of everything; measure again once they have loaded.
  document.fonts?.ready.then(onResize);

  return {
    // After a language change, split the new words again and keep them shown.
    refreshText() {
      root.querySelectorAll("[data-split]").forEach(splitWords);
      onResize();
      lastBandRefresh(story, onBand);
    },
    pause() {
      marquee.stop();
      cells.stop();
    },
    resume() {
      play();
      onResize();
    },
    scrollTo(id, behavior) {
      return panels.scrollTo(id, behavior);
    },
  };
}

function lastBandRefresh(story, onBand) {
  if (story.dataset.band) onBand(story.dataset.band);
}
