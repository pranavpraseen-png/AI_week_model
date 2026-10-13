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
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(url, { scope: "./" }).catch(() => {
      /* offline support is a bonus; the app works without it */
    });
  });
}
