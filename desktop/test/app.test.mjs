// Desktop app tests: launch the REAL Electron app and use it like a person would.
//
//   cd desktop && npm test                 (Windows / macOS)
//   cd desktop && xvfb-run -a npm test     (Linux with no screen, e.g. CI)
//
// Needs the simulated photos (python src/make_simulated_data.py) and Python with
// requirements.txt installed: the expected Hb is computed by src/features.py, the
// same reference tests/test_web_e2e.py uses for the website.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { _electron as electron } from "playwright-core";

const DESKTOP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = path.resolve(DESKTOP, "..");
const PHOTO = path.join(ROOT, "data", "simulated", "images", "india_0004.png");
const ORIGIN = "app://anaemialens";

let app; // the running Electron app
let page; // its window
let llm; // a fake "local language model" on 127.0.0.1:8080
let llmRequests = [];
const problems = []; // console errors and page crashes

/* ---------------- Helpers ---------------- */

function findPython() {
  const candidates = [
    process.env.PYTHON,
    path.join(ROOT, ".venv", "bin", "python"),
    path.join(ROOT, ".venv", "Scripts", "python.exe"),
    "python3",
    "python",
  ].filter(Boolean);
  for (const exe of candidates) {
    try {
      execFileSync(exe, ["-c", "import numpy, PIL"], { stdio: "ignore" });
      return exe;
    } catch {
      /* try the next one */
    }
  }
  throw new Error("Python with numpy + pillow not found (pip install -r requirements.txt, or set PYTHON=...)");
}

// What the Python model says for this photo: the number the app must show.
function pythonHb(image) {
  const code = `
import json, sys
sys.path.insert(0, ${JSON.stringify(path.join(ROOT, "src"))})
from features import extract_features
model = json.load(open(${JSON.stringify(path.join(ROOT, "web", "model.json"))}))
feats, m = extract_features(sys.argv[1]), model["multi"]
z = [(feats[n] - mu) / sd for n, mu, sd in zip(model["feature_names"], m["mean"], m["std"])]
print(sum(a * b for a, b in zip(z, m["w"])) + m["b"])`;
  return Number(execFileSync(findPython(), ["-c", code, image], { encoding: "utf8" }).trim());
}

// The "/*" block of web/_headers: what every response must carry.
function expectedHeaders() {
  const headers = {};
  let active = false;
  for (const line of fs.readFileSync(path.join(ROOT, "web", "_headers"), "utf8").split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    if (!/^\s/.test(line)) active = line.trim() === "/*";
    else if (active) {
      const [name, ...rest] = line.trim().split(":");
      headers[name.trim().toLowerCase()] = rest.join(":").trim();
    }
  }
  delete headers["strict-transport-security"]; // https-only, dropped like scripts/serve_web.py
  return headers;
}

// Re-run a page.evaluate until ok(value) (waitForFunction uses eval, which the CSP blocks).
async function poll(script, ok, timeout = 8000) {
  const start = Date.now();
  let value = await page.evaluate(script);
  while (!ok(value) && Date.now() - start < timeout) {
    await page.waitForTimeout(50);
    value = await page.evaluate(script);
  }
  return value;
}

async function goHome() {
  await page.goto(`${ORIGIN}/`);
  await page.locator("#start").waitFor();
}

// Answer the questions and pick the photo, as in tests/test_web_e2e.py.
async function checkPhoto(image) {
  await page.click("#start");
  await page.click('[data-answer="sex"][data-value="F"]');
  await page.click('[data-answer="age"][data-value="30"]');
  await page.click('[data-answer="pregnant"][data-value="no"]');
  await page.setInputFiles("#file-gallery", image);
  await page.waitForSelector('[data-screen="confirm"]:not([hidden])');
  // Measure the whole simulated photo, like the Python reference does.
  await page.$eval("#guide-size", (el) => {
    el.value = "50";
    el.dispatchEvent(new Event("input"));
  });
  await page.click("#use-photo");
  await page.waitForSelector('[data-screen="result"]:not([hidden])');
  return Number(await page.innerText("#hb-value"));
}

/* ---------------- Start and stop the app ---------------- */

before(async () => {
  if (process.getuid?.() === 0) {
    throw new Error("Electron's sandbox will not run as root (that is a good thing): run the tests as a normal user.");
  }
  assert.ok(fs.existsSync(PHOTO), `missing ${PHOTO}: run  python src/make_simulated_data.py  first`);

  llm = http.createServer((req, res) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    if (req.method === "OPTIONS") return res.writeHead(204).end();
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      llmRequests.push({ origin: req.headers.origin, body });
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ choices: [{ message: { content: "Please get a blood test at a health centre." } }] }));
    });
  });
  await new Promise((resolve) => {
    llm.once("error", () => {
      llm = null; // port 8080 is busy: the explainer test is skipped
      resolve();
    });
    llm.listen(8080, "127.0.0.1", resolve);
  });

  app = await electron.launch({
    cwd: DESKTOP,
    args: [
      // A throwaway profile, so tests never touch your real accounts or history.
      `--user-data-dir=${fs.mkdtempSync(path.join(os.tmpdir(), "anaemialens-test-"))}`,
      // Chromium's built-in fake camera stands in for a webcam.
      "--use-fake-device-for-media-stream",
      path.join(DESKTOP, "main.js"),
    ],
  });
  page = await app.firstWindow();
  page.on("console", (m) => m.type() === "error" && problems.push(`console: ${m.text()}`));
  page.on("pageerror", (e) => problems.push(`pageerror: ${e}`));
  await page.locator("#start").waitFor();

  // Never really open a browser during tests: record what WOULD be opened.
  await app.evaluate(({ shell }) => {
    globalThis.opened = [];
    shell.openExternal = async (url) => {
      globalThis.opened.push(url);
    };
  });
});

after(async () => {
  await app?.close();
  llm?.close();
});

/* ---------------- Tests ---------------- */

test("the window opens on the home screen, locked down", async () => {
  assert.equal(page.url(), `${ORIGIN}/`);
  assert.match(await page.title(), /^AnaemiaLens/);
  assert.match(await page.innerText("#home-title"), /Read your blood/);
  // The label appears once the model file has loaded, so wait for it rather than check instantly.
  await page.locator("#hero-demo").waitFor({ state: "visible", timeout: 5000 }); // simulated model must be labelled

  const win = await app.evaluate(({ BrowserWindow }) => {
    const w = BrowserWindow.getAllWindows()[0];
    const prefs = w.webContents.getLastWebPreferences();
    return {
      count: BrowserWindow.getAllWindows().length,
      size: w.getSize(),
      background: w.getBackgroundColor(),
      contextIsolation: prefs.contextIsolation,
      sandbox: prefs.sandbox,
      nodeIntegration: prefs.nodeIntegration,
      webSecurity: prefs.webSecurity,
      preload: prefs.preload ?? null,
    };
  });
  assert.deepEqual(win, {
    count: 1,
    size: [1280, 800],
    background: "#080B11",
    contextIsolation: true,
    sandbox: true,
    nodeIntegration: false,
    webSecurity: true,
    preload: null,
  });
  // The page is an ordinary web page: no Node.js inside it.
  assert.equal(await page.evaluate("typeof require + typeof process"), "undefinedundefined");
  // The site's anti-framing check did not fire (the window is top-level).
  assert.equal(await page.evaluate("window.top === window.self"), true);

  await page.click("#start");
  assert.ok(await page.locator("#demo-banner").isVisible(), "the demo banner must show on app screens");
  assert.deepEqual(problems, []);
});

test("a full check gives the same Hb as the Python model", async () => {
  await goHome();
  const shown = await checkPhoto(PHOTO);
  const expected = pythonHb(PHOTO);
  assert.ok(Math.abs(shown - expected) <= 0.051, `app shows ${shown}, Python says ${expected}`);
  assert.ok((await page.innerText("#verdict-title")).length > 0);
  assert.equal(await page.evaluate("document.getElementById('confirm-canvas').width"), 0, "photo deleted");
  assert.deepEqual(problems, []);
});

test("the explanation can reach a language model on this computer (localhost)", async (t) => {
  if (!llm) return t.skip("port 8080 is busy");
  await goHome();
  await page.click("#open-settings");
  await page.check("#explain-enabled");
  await page.fill("#explain-endpoint", "http://127.0.0.1:8080/v1");
  await page.click('#settings button[value="close"]');
  await checkPhoto(PHOTO);
  await page.click("#explain-go");
  await page.locator("#explain-text", { hasText: "blood test" }).waitFor();
  assert.equal(llmRequests.length, 1);
  assert.equal(llmRequests[0].origin, ORIGIN); // Ollama allows app:// pages by default
  assert.ok(!llmRequests[0].body.includes("data:image"), "only numbers are sent, never the photo");
  assert.deepEqual(problems, []);
});

test("every response carries the security headers from web/_headers", async () => {
  const want = expectedHeaders();
  assert.match(want["content-security-policy"], /frame-ancestors 'none'/);
  assert.match(want["content-security-policy"], /connect-src 'self' http:\/\/localhost:11434/);
  for (const file of ["/", "/js/app.js", "/model.json", "/privacy.html", "/no-such-file.js"]) {
    const got = await page.evaluate(async (url) => {
      const r = await fetch(url);
      return { status: r.status, headers: Object.fromEntries(r.headers) };
    }, file);
    for (const [name, value] of Object.entries(want)) {
      assert.equal(got.headers[name], value, `${file}: ${name}`);
    }
    assert.equal(got.status, file === "/no-such-file.js" ? 404 : 200, file);
  }
});

test("files outside web/ cannot be read", async () => {
  for (const attempt of ["/../desktop/main.js", "/..%2F..%2Fdesktop%2Fmain.js", "/%2e%2e/desktop/package.json",
    "/js/..%5C..%5Cdesktop%5Cmain.js", "/_headers"]) {
    const status = await page.evaluate((url) => fetch(url).then((r) => r.status), attempt);
    assert.equal(status, 404, attempt);
  }
});

test("the CSP is enforced: nothing can be sent to the internet", async () => {
  const result = await page.evaluate(() => fetch("https://example.com/").then(() => "sent", () => "blocked"));
  assert.equal(result, "blocked");
  // Trusted Types: inserting HTML is refused by the browser.
  const html = await page.evaluate(() => {
    try {
      document.createElement("div").innerHTML = "<b>x</b>";
      return "allowed";
    } catch {
      return "refused";
    }
  });
  assert.equal(html, "refused");
});

test("pop-ups and navigation away from the app are blocked", async () => {
  await goHome();
  await app.evaluate(() => (globalThis.opened = []));
  const popups = await page.evaluate(() =>
    ["https://example.com/a", "http://example.com/b", "privacy.html", "file:///etc/passwd"].map((u) => window.open(u)),
  );
  assert.deepEqual(popups, [null, null, null, null]);
  assert.equal(app.windows().length, 1);

  // (Clicks and address changes are done by the page itself: Playwright's own
  // click would wait forever for a navigation the app has cancelled.)
  // The footer's "Source code" link goes to the system browser, not into the app.
  await page.evaluate(() => document.querySelector('footer a[href^="https://github.com/"]').click());
  await page.evaluate(() => {
    location.href = "https://example.org/";
  });
  await page.evaluate(() => {
    location.href = "file:///etc/passwd";
  });
  await page.waitForTimeout(500);
  assert.equal(page.url(), `${ORIGIN}/`);
  assert.ok(await page.locator("#start").isVisible(), "still on the app's home screen");

  const opened = await app.evaluate(() => globalThis.opened);
  // Only https addresses ever reach the system browser.
  assert.deepEqual(opened, [
    "https://example.com/a",
    "https://github.com/pranavpraseen-png/AI_week_model",
    "https://example.org/",
  ]);
});

test("only the camera is allowed; every other permission is denied", async () => {
  await goHome();
  const results = await page.evaluate(async () => {
    const outcome = (p) => p.then(() => "allowed", (e) => e.name);
    return {
      notifications: await Notification.requestPermission(),
      clipboard: await outcome(navigator.clipboard.readText()),
      microphone: await outcome(navigator.mediaDevices.getUserMedia({ audio: true })),
      midi: await outcome(navigator.requestMIDIAccess({ sysex: true })),
    };
  });
  assert.equal(results.notifications, "denied");
  for (const name of ["clipboard", "microphone", "midi"]) assert.notEqual(results[name], "allowed", name);

  // The real camera step works (with Chromium's fake camera).
  await page.click("#start");
  await page.click('[data-answer="sex"][data-value="M"]');
  await page.click('[data-answer="age"][data-value="8"]');
  await page.click("#open-camera");
  await page.waitForSelector("#shutter:not([disabled])", { timeout: 10000 });
  assert.ok((await page.evaluate("document.getElementById('video').videoWidth")) > 0);
  await page.click("#shutter");
  await page.waitForSelector('[data-screen="confirm"]:not([hidden])');
  assert.equal(await page.evaluate("document.getElementById('video').srcObject"), null, "camera switched off");
});

test("with the network switched off, the whole app still works", async () => {
  problems.length = 0; // earlier tests trigger blocked requests on purpose; start clean
  // Airplane mode for the app's browser session, plus a recorder for every request that
  // goes out over the network (http/https). The app's own files use app:// and never do.
  await app.evaluate(({ session }) => {
    globalThis.networkRequests = [];
    session.defaultSession.enableNetworkEmulation({ offline: true });
    session.defaultSession.webRequest.onSendHeaders((details) => {
      if (/^https?:/.test(details.url)) globalThis.networkRequests.push(details.url);
    });
  });
  try {
    await goHome(); // reload the app from scratch while offline
    await page.locator("#hero-demo").waitFor({ state: "visible", timeout: 5000 });
    const shown = await checkPhoto(PHOTO);
    const expected = pythonHb(PHOTO);
    assert.ok(Math.abs(shown - expected) <= 0.051, `offline app shows ${shown}, Python says ${expected}`);

    // A language that is loaded only when picked must come from the app's own files.
    await page.click("#lang-toggle");
    await page.click('#lang-dialog .lang-option[data-lang="ta"]');
    await page.locator('html[lang="ta"]').waitFor({ state: "attached" });
    assert.match(await page.innerText('[data-screen="result"]'), /ஹீமோகுளோபின்/);

    await page.goto(`${ORIGIN}/privacy.html`);
    assert.ok(await page.locator("h1").isVisible());
    // The whole run needed the network zero times.
    assert.deepEqual(await app.evaluate(() => globalThis.networkRequests), []);
  } finally {
    await app.evaluate(({ session }) => {
      session.defaultSession.webRequest.onSendHeaders(null);
      session.defaultSession.disableNetworkEmulation();
    });
  }
  assert.deepEqual(problems, []);
});
