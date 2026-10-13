// The opening page ("Night Desk"): a dim live bloodstream behind the headline, an
// example specimen panel (one simulated photo, measured by this app's model),
// the 57-in-100 grid, a scroll story where the fingernail's colour follows
// haemoglobin, and the fitted line. Everything is drawn on this device with
// plain canvas, SVG and CSS; nothing is downloaded. With "reduce motion"
// switched on, every effect shows its finished, still state instead.
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

/* ---------------- Bloodstream ---------------- */

// Draw one red blood cell, seen face-on, into its own small canvas: a darker rim
// and a paler dimple in the middle (red cells are biconcave discs).
function cellSprite(size, shade) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  const r = size / 2;
  const body = g.createRadialGradient(r, r, r * 0.05, r, r, r);
  body.addColorStop(0, `rgba(${246 - shade * 20}, ${150 - shade * 40}, ${140 - shade * 45}, 1)`);
  body.addColorStop(0.45, `rgba(${214 - shade * 30}, ${62 - shade * 25}, ${58 - shade * 25}, 1)`);
  body.addColorStop(0.82, `rgba(${170 - shade * 40}, ${28 - shade * 12}, ${32 - shade * 14}, 1)`);
  body.addColorStop(1, "rgba(90, 10, 16, 0)");
  g.fillStyle = body;
  g.beginPath();
  g.arc(r, r, r, 0, Math.PI * 2);
  g.fill();
  const shine = g.createRadialGradient(r * 0.7, r * 0.6, 0, r * 0.7, r * 0.6, r * 0.6);
  shine.addColorStop(0, "rgba(255, 220, 210, 0.35)");
  shine.addColorStop(1, "rgba(255, 220, 210, 0)");
  g.fillStyle = shine;
  g.fill();
  return c;
}

class Bloodstream {
  constructor(canvas, { still }) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.still = still;
    this.sprites = [0, 0.5, 1].map((shade) => cellSprite(160, shade));
    this.pointer = { x: -1e4, y: -1e4 };
    this.running = false;
    this.time = 0;
    this.resize();
    window.addEventListener("resize", () => this.resize(), { passive: true });
    canvas.parentElement.addEventListener("pointermove", (e) => {
      const rect = canvas.getBoundingClientRect();
      this.pointer.x = e.clientX - rect.left;
      this.pointer.y = e.clientY - rect.top;
    }, { passive: true });
    canvas.parentElement.addEventListener("pointerleave", () => { this.pointer.x = this.pointer.y = -1e4; });
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, rect.width < 700 ? 1.5 : 2);
    this.w = rect.width;
    this.h = rect.height;
    this.canvas.width = Math.round(rect.width * dpr);
    this.canvas.height = Math.round(rect.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.round(Math.min(110, Math.max(30, (this.w * this.h) / 14000)));
    this.cells = Array.from({ length: count }, (_, i) => this.makeCell(i, true));
    this.cells.sort((a, b) => a.z - b.z); // far cells first, near cells on top
    if (this.still || !this.running) this.draw(0);
  }

  makeCell(i, anywhere) {
    const z = 0.25 + Math.random() * 0.95; // depth: small and faint far away, big and sharp up close
    return {
      x: anywhere ? Math.random() * this.w : -80,
      y: Math.random() * this.h,
      z,
      r: (10 + Math.random() * 10) * z * (this.w < 700 ? 1.6 : 2.2),
      speed: (14 + Math.random() * 18) * z,
      spin: Math.random() * Math.PI * 2,
      spinRate: (Math.random() - 0.5) * 0.6,
      tumble: Math.random() * Math.PI * 2,
      tumbleRate: 0.3 + Math.random() * 0.7,
      wave: Math.random() * Math.PI * 2,
      sprite: this.sprites[i % 3],
      vx: 0,
      vy: 0,
    };
  }

  step(dt) {
    this.time += dt;
    for (const c of this.cells) {
      // Flow: left to right, with a slow sway like blood in a capillary.
      const sway = Math.sin(this.time * 0.6 + c.wave + c.x * 0.004) * 10 * c.z;
      const dx = c.x - this.pointer.x;
      const dy = c.y - this.pointer.y;
      const d2 = dx * dx + dy * dy;
      if (d2 < 22000) { // cells drift around your finger
        const push = (1 - d2 / 22000) * 120 * c.z;
        const d = Math.sqrt(d2) || 1;
        c.vx += (dx / d) * push * dt;
        c.vy += (dy / d) * push * dt;
      }
      c.vx *= 0.94;
      c.vy *= 0.94;
      c.x += (c.speed + c.vx) * dt;
      c.y += (sway * 0.6 + c.vy) * dt;
      c.spin += c.spinRate * dt;
      c.tumble += c.tumbleRate * dt;
      if (c.x - c.r > this.w + 40) { // re-enter on the left at a new height, same depth
        c.x = -c.r - 20;
        c.y = Math.random() * this.h;
      }
      if (c.y < -c.r * 2) c.y = this.h + c.r;
      if (c.y > this.h + c.r * 2) c.y = -c.r;
    }
  }

  draw() {
    const { ctx, w, h } = this;
    ctx.clearRect(0, 0, w, h);
    for (const c of this.cells) {
      const flat = 0.32 + 0.68 * Math.abs(Math.cos(c.tumble)); // a disc seen edge-on looks thin
      ctx.save();
      ctx.globalAlpha = Math.min(1, 0.18 + c.z * 0.75);
      ctx.translate(c.x, c.y);
      ctx.rotate(c.spin);
      ctx.scale(1, flat);
      ctx.drawImage(c.sprite, -c.r, -c.r, c.r * 2, c.r * 2);
      ctx.restore();
    }
  }

  start() {
    if (this.running || this.still) return;
    this.running = true;
    let last = performance.now();
    const frame = (now) => {
      if (!this.running) return;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      this.step(dt);
      this.draw();
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

/* ---------------- Scroll story: nail colour follows haemoglobin ---------------- */

function storyUpdater(root, onBand) {
  const stage = root.querySelector(".story-stage");
  const nail = root.querySelector("#story-nail");
  const value = root.querySelector("#story-hb");
  const scale = root.querySelector("#story-scale");
  let lastBand = null;
  return () => {
    const rect = root.getBoundingClientRect();
    const travel = rect.height - window.innerHeight;
    const p = travel > 0 ? Math.min(1, Math.max(0, -rect.top / travel)) : 1;
    const hb = 6 + p * 10; // 6 → 16 g/dL as you scroll
    const [r, g, b] = nailColor(hb);
    nail.style.setProperty("fill", `rgb(${r}, ${g}, ${b})`);
    value.textContent = hb.toFixed(1);
    drawScale(scale, { hb, threshold: 12 }); // WHO bands for a non-pregnant woman
    stage.style.setProperty("--p", p.toFixed(3));
    const band = storyBand(hb);
    if (band !== lastBand) {
      lastBand = band;
      root.dataset.band = band;
      onBand(band);
    }
  };
}

/* ---------------- Wiring ---------------- */

export function initIntro(root, { onBand = () => {} } = {}) {
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hero = root.querySelector(".hero");
  const stream = new Bloodstream(root.querySelector("#bloodstream"), { still });

  root.querySelectorAll("[data-split]").forEach(splitWords);
  buildHundred(root.querySelector("#hundred"));
  buildDemoTrend(root.querySelector("#demo-trend"));

  // The example specimen: its numbers count up and the needle travels to 10.4
  // while the scan line passes over the photo. Still: drawn at once.
  const example = { hb: 10.43, low: 10.1, high: 10.76, threshold: 12 }; // india_0062.png, this model
  const specimenScale = root.querySelector("#specimen-scale");
  drawScale(specimenScale, still ? example : { ...example, hb: 4, low: 4, high: 4 });
  root.querySelectorAll(".specimen [data-count]").forEach((el, i) => countUp(el, still, 700 + i * 70));
  requestAnimationFrame(() => {
    hero.classList.add("is-in");
    if (!still) setTimeout(() => drawScale(specimenScale, example), 900);
  });

  // Run the bloodstream only while the hero is on screen and the page is visible.
  let heroVisible = true;
  const heroWatch = new IntersectionObserver(([entry]) => {
    heroVisible = entry.isIntersecting;
    if (heroVisible && !document.hidden) stream.start();
    else stream.stop();
  });
  heroWatch.observe(hero);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stream.stop();
    else if (heroVisible) stream.start();
  });

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
    });
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  update();

  return {
    // After a language change, split the new words again and keep them shown.
    refreshText() {
      root.querySelectorAll("[data-split]").forEach(splitWords);
      update();
      lastBandRefresh(story, onBand);
    },
    pause() { stream.stop(); },
    resume() {
      if (heroVisible && !document.hidden) stream.start();
      onScroll();
    },
  };
}

function lastBandRefresh(story, onBand) {
  if (story.dataset.band) onBand(story.dataset.band);
}
