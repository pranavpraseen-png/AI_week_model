// Tiny DOM helpers. Text is only ever set with textContent: no HTML strings
// anywhere, which (with Trusted Types in the CSP) rules out script injection.

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export function setText(el, text) {
  el.textContent = text;
}

export function el(tag, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}

// Safe per-viewer preferences. Storage can be missing or blocked (private mode).
export const prefs = {
  get(key, fallback) {
    try {
      const raw = localStorage.getItem(`anaemialens.${key}`);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(`anaemialens.${key}`, JSON.stringify(value));
    } catch {
      /* not saved; the app works without it */
    }
  },
};
