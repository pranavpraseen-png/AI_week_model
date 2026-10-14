// AnaemiaLens desktop app: the SAME website from ../web, in its own window.
//
// Electron = a copy of the Chromium browser + Node.js. This file is the "main
// process": it opens the window and decides what the page may do. The page
// itself (web/) runs in a locked-down "renderer" with no Node.js at all.
//
// Security idea: the page gets exactly what it gets on the real website, and
// nothing more. Same files, same security headers (read from web/_headers),
// no access to your files, no internet, camera only.
// Why each setting is here: docs/03_website_research.md, "The desktop app".
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow, Menu, protocol, session, shell } = require("electron");

// Where the website lives. In development: the repo's web/ folder (the ONE copy).
// In the installed app: electron-builder copied it next to the app (extraResources).
const WEB_DIR = app.isPackaged ? path.join(process.resourcesPath, "web") : path.join(__dirname, "..", "web");

// The page's address. A custom scheme gives the site a real "origin", which ES
// modules, localStorage and the browser's crypto (used by accounts) all need.
// file:// would not work: browsers treat every file:// page as a stranger.
// (Ollama already accepts requests from app:// pages, so the explainer works.)
const SCHEME = "app";
const HOST = "anaemialens";
const ORIGIN = `${SCHEME}://${HOST}`;

// Must run before the app is ready. "standard" + "secure" make app://anaemialens
// behave like an https:// site. Service workers are NOT allowed: every file is
// already on disk, so an offline cache would only be a second copy that could go stale.
protocol.registerSchemesAsPrivileged([
  { scheme: SCHEME, privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, codeCache: true } },
]);

// Every renderer runs in Chromium's sandbox (no Node.js, no file access).
app.enableSandbox();

/* ---------------- Security headers: one source of truth ---------------- */

// Read the "/*" block of web/_headers (the file Netlify / Cloudflare Pages use),
// exactly like scripts/serve_web.py does, so the desktop app sends the same headers.
function readHeaders(file) {
  const headers = {};
  let active = false;
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    if (!/^\s/.test(line)) {
      active = line.trim() === "/*";
      continue;
    }
    const colon = line.indexOf(":");
    if (active && colon > 0) headers[line.slice(0, colon).trim()] = line.slice(colon + 1).trim();
  }
  // HSTS only means something for https:// sites (serve_web.py drops it too).
  delete headers["Strict-Transport-Security"];
  headers["Cache-Control"] = "no-cache";
  return headers;
}

const SECURITY_HEADERS = readHeaders(path.join(WEB_DIR, "_headers"));
const CSP = SECURITY_HEADERS["Content-Security-Policy"] || "";
if (!CSP.includes("default-src 'none'") || !CSP.includes("frame-ancestors 'none'")) {
  throw new Error("web/_headers is missing its Content-Security-Policy");
}

// The only other places the page may talk to: the user's own computer (Ollama,
// llama.cpp), taken from the CSP's connect-src so the two can never disagree.
const LOCAL_ORIGINS = (CSP.match(/connect-src([^;]*)/)?.[1] || "")
  .trim()
  .split(/\s+/)
  .filter((source) => /^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(source));

/* ---------------- Serving web/ on app://anaemialens/ ---------------- */

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".webmanifest": "application/manifest+json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};

function reply(status, body, type = "text/plain; charset=utf-8") {
  return new Response(body, { status, headers: { ...SECURITY_HEADERS, "Content-Type": type } });
}

// Turn app://anaemialens/js/app.js into <web>/js/app.js, or null if the address
// tries to step outside web/ (for example app://anaemialens/..%2F..%2Fsecret).
function fileFor(url) {
  let pathname;
  try {
    pathname = decodeURIComponent(url.pathname);
  } catch {
    return null; // broken %-encoding
  }
  if (pathname.includes("\0")) return null;
  if (pathname.endsWith("/")) pathname += "index.html";
  const file = path.resolve(WEB_DIR, "." + pathname);
  return file.startsWith(WEB_DIR + path.sep) ? file : null;
}

async function serve(request) {
  const url = new URL(request.url);
  if (url.host !== HOST) return reply(404, "Not found");
  if (request.method !== "GET" && request.method !== "HEAD") return reply(405, "Method not allowed");
  const file = fileFor(url);
  const type = file && MIME[path.extname(file).toLowerCase()];
  if (!type) return reply(404, "Not found"); // outside web/, or a kind of file the site never uses
  try {
    return reply(200, await fs.promises.readFile(file), type);
  } catch {
    return reply(404, "Not found");
  }
}

/* ---------------- Guards for every window ---------------- */

// Is this address one of our own pages? (Node's URL gives "null" as the origin
// of a custom scheme, so compare the scheme and host instead.)
const isAppUrl = (url) => {
  try {
    const u = new URL(url);
    return u.protocol === `${SCHEME}:` && u.host === HOST;
  } catch {
    return false;
  }
};

// Links to the outside world (e.g. "Source code" on GitHub) open in the normal
// browser, and only if they are https. Everything else is ignored.
function openOutside(url) {
  try {
    if (new URL(url).protocol === "https:") shell.openExternal(url);
  } catch {
    /* not a valid address: ignore it */
  }
}

app.on("web-contents-created", (_event, contents) => {
  // The window may only ever show our own pages.
  const guard = (event, url) => {
    if (isAppUrl(url)) return;
    event.preventDefault();
    openOutside(url);
  };
  contents.on("will-navigate", guard);
  contents.on("will-redirect", guard);
  // No pop-up windows, ever. External https links go to the system browser.
  contents.setWindowOpenHandler(({ url }) => {
    if (!isAppUrl(url)) openOutside(url);
    return { action: "deny" };
  });
  // <webview> could load anything inside the app: never allowed.
  contents.on("will-attach-webview", (event) => event.preventDefault());
});

function lockDownSession(ses) {
  // Camera ("media", video only) for the photo step; every other permission is refused:
  // location, notifications, microphone, clipboard, USB, MIDI...
  ses.setPermissionRequestHandler((_contents, permission, callback, details) => {
    const videoOnly = !(details.mediaTypes || []).includes("audio");
    callback(permission === "media" && videoOnly && isAppUrl(details.requestingUrl));
  });
  ses.setPermissionCheckHandler((_contents, permission, origin) => permission === "media" && isAppUrl(origin));
  ses.setDevicePermissionHandler(() => false); // USB / serial / HID devices

  // A second lock behind the CSP: Electron itself cancels any request that is
  // not our own files or the user's local language model (same list as connect-src).
  ses.webRequest.onBeforeRequest((details, callback) => {
    let allowed = false; // fail closed: anything we cannot understand is cancelled
    try {
      const { protocol: scheme, origin } = new URL(details.url);
      allowed =
        isAppUrl(details.url) ||
        LOCAL_ORIGINS.includes(origin) ||
        scheme === "blob:" ||
        scheme === "data:" ||
        (scheme === "devtools:" && !app.isPackaged);
    } catch {
      /* not a valid address */
    }
    callback({ cancel: !allowed });
  });

  // Electron's spell checker downloads dictionaries from the internet: off.
  ses.setSpellCheckerEnabled(false);
}

/* ---------------- Window and menu ---------------- */

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 380,
    minHeight: 640,
    title: "AnaemiaLens",
    backgroundColor: "#080B11", // the site's ink colour: no white flash while loading
    icon: path.join(WEB_DIR, "icons", "icon-512.png"),
    show: false,
    webPreferences: {
      contextIsolation: true, // the page cannot reach Electron's internals
      sandbox: true, // ...and runs in Chromium's sandbox
      nodeIntegration: false, // no Node.js (files, programs) inside the page
      webSecurity: true, // normal browser rules (same-origin policy) stay on
      webviewTag: false,
      spellcheck: false,
      devTools: !app.isPackaged, // developer tools only while developing
    },
  });
  win.once("ready-to-show", () => win.show());
  win.loadURL(`${ORIGIN}/`);
  return win;
}

function buildMenu() {
  const mac = process.platform === "darwin";
  const template = [
    ...(mac ? [{ role: "appMenu" }] : []),
    { label: "File", submenu: [mac ? { role: "close" } : { role: "quit" }] },
    { role: "editMenu" }, // Cut / Copy / Paste / Select all, with the usual shortcuts
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
        ...(app.isPackaged ? [] : [{ role: "toggleDevTools" }]),
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

/* ---------------- Start ---------------- */

// One copy at a time: two windows would fight over the camera and the accounts storage.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const win = BrowserWindow.getAllWindows()[0];
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.whenReady().then(() => {
    protocol.handle(SCHEME, serve);
    lockDownSession(session.defaultSession);
    buildMenu();
    createWindow();
    // macOS: clicking the Dock icon with no window open makes a new one.
    app.on("activate", () => BrowserWindow.getAllWindows().length === 0 && createWindow());
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
}
