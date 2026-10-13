// Offline support: the whole app is a handful of static files, so cache them
// once and the screening works with no signal at all.
// Bump VERSION whenever any file below changes, so old caches are replaced.
const VERSION = "anaemialens-v1";
const FILES = [
  "./",
  "./index.html",
  "./privacy.html",
  "./css/styles.css",
  "./js/app.js",
  "./js/camera.js",
  "./js/dom.js",
  "./js/explain.js",
  "./js/features.js",
  "./js/i18n.js",
  "./js/image.js",
  "./js/model.js",
  "./js/register-sw.js",
  "./model.json",
  "./manifest.webmanifest",
  "./icons/icon.svg",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./fonts/fraunces-latin-600-normal.woff2",
  "./fonts/noto-sans-devanagari-devanagari-400-normal.woff2",
  "./fonts/noto-sans-devanagari-devanagari-700-normal.woff2",
  "./fonts/noto-sans-devanagari-latin-400-normal.woff2",
  "./fonts/noto-sans-devanagari-latin-700-normal.woff2",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Only our own files, only GET. Calls to a local language model pass straight through.
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  event.respondWith(
    caches.match(event.request, { ignoreSearch: true }).then((hit) => {
      if (hit) return hit;
      return fetch(event.request).then((response) => {
        if (response.ok && response.type === "basic") {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put(event.request, copy));
        }
        return response;
      });
    }),
  );
});
