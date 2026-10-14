// Register the offline service worker. With Trusted Types enforced by the CSP,
// register() needs a TrustedScriptURL, made by a policy that only allows ./sw.js.
if ("serviceWorker" in navigator && window.isSecureContext) {
  const url = self.trustedTypes
    ? self.trustedTypes
        .createPolicy("sw-url", {
          createScriptURL: (u) => {
            if (u !== "./sw.js") throw new TypeError("blocked script URL");
            return u;
          },
        })
        .createScriptURL("./sw.js")
    : "./sw.js";
  // When a new version of the site is published, the new service worker takes over
  // (sw.js calls skipWaiting + clients.claim), but the open page still shows the old
  // files. Reload once so people see the new version, but only on the opening page,
  // so a check in progress is never interrupted, and never on the very first visit.
  const hadController = Boolean(navigator.serviceWorker.controller);
  let reloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!hadController || reloaded || !document.body.classList.contains("is-intro")) return;
    reloaded = true;
    window.location.reload();
  });
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(url, { scope: "./" }).catch(() => {
      /* offline support is a bonus; the app works without it */
    });
  });
}
