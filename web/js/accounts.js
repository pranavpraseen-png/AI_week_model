// Accounts that live only on this phone. Each account has a name, a type
// ("personal" or "worker") and a PIN. The PIN is never stored: it is stretched
// with PBKDF2 (600,000 rounds of SHA-256) into an AES-256-GCM key that exists
// only in memory while the account is unlocked. The account's history of checks
// (no names, no photos) is stored encrypted with that key.
//
// What this protects against: someone else picking up the phone and reading the
// history. A 4-digit PIN cannot stop a determined attacker who copies the phone's
// storage and tries all 10,000 PINs, so 6+ digits are encouraged.

export const ITERATIONS = 600_000;
export const PIN_PATTERN = /^\d{4,8}$/;
export const MAX_NAME = 40;
const VERIFIER = "anaemialens-account-v1";
const STORAGE_KEY = "anaemialens.accounts";
const KEEP_DAYS = 365;
const FREE_TRIES = 5;

const enc = new TextEncoder();
const dec = new TextDecoder();
const toB64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
const fromB64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

export class AccountError extends Error {
  constructor(code) {
    super(code);
    this.code = code; // "name" | "pin" | "pin_mismatch" | "type"
  }
}

async function deriveKey(pin, salt, iterations) {
  const base = await crypto.subtle.importKey("raw", enc.encode(pin), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    base,
    { name: "AES-GCM", length: 256 },
    false, // the key can never be exported or read, only used
    ["encrypt", "decrypt"],
  );
}

async function seal(key, value) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const data = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(JSON.stringify(value)));
  return { iv: toB64(iv), data: toB64(data) };
}

async function unseal(key, box) {
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: fromB64(box.iv) }, key, fromB64(box.data));
  return JSON.parse(dec.decode(plain));
}

export function cleanName(name) {
  return String(name ?? "").replace(/\s+/g, " ").trim().slice(0, MAX_NAME);
}

export async function createAccount({ name, type, pin, pinAgain }, { iterations = ITERATIONS } = {}) {
  const clean = cleanName(name);
  if (!clean) throw new AccountError("name");
  if (type !== "personal" && type !== "worker") throw new AccountError("type");
  if (!PIN_PATTERN.test(pin ?? "")) throw new AccountError("pin");
  if (pin !== pinAgain) throw new AccountError("pin_mismatch");
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key = await deriveKey(pin, salt, iterations);
  const account = {
    v: 1,
    id: toB64(crypto.getRandomValues(new Uint8Array(9))).replace(/[+/=]/g, "x"),
    name: clean,
    type,
    salt: toB64(salt),
    iterations,
    check: await seal(key, VERIFIER),
    history: await seal(key, []),
    failures: 0,
    waitUntil: 0,
  };
  return { account, key };
}

// Seconds the person must wait before the next PIN attempt (0 = may try now).
export function waitSeconds(account, now = Date.now()) {
  return Math.max(0, Math.ceil((account.waitUntil - now) / 1000));
}

// Returns { key, account } on success, or { key: null, account } with the
// failure counted. After 5 wrong PINs, waits grow: 30 s, 60 s, 2 min … up to 1 h.
export async function unlock(account, pin, now = Date.now()) {
  if (waitSeconds(account, now) > 0) return { key: null, account };
  let key = null;
  try {
    const candidate = await deriveKey(pin, fromB64(account.salt), account.iterations);
    if ((await unseal(candidate, account.check)) === VERIFIER) key = candidate;
  } catch {
    key = null; // wrong PIN: AES-GCM refuses to decrypt
  }
  if (key) return { key, account: { ...account, failures: 0, waitUntil: 0 } };
  const failures = account.failures + 1;
  const extra = failures - FREE_TRIES;
  const waitUntil = extra >= 0 ? now + Math.min(3600, 30 * 2 ** extra) * 1000 : 0;
  return { key: null, account: { ...account, failures, waitUntil } };
}

export async function readHistory(account, key) {
  return unseal(key, account.history);
}

// Adds one check to the encrypted history and drops entries older than a year.
export async function addCheck(account, key, check, now = Date.now()) {
  const history = await readHistory(account, key);
  const cutoff = now - KEEP_DAYS * 86_400_000;
  const kept = history.filter((entry) => Date.parse(entry.at) >= cutoff);
  kept.push({
    at: new Date(now).toISOString(),
    hb: Math.round(check.hb * 10) / 10,
    low: Math.round(check.low * 10) / 10,
    high: Math.round(check.high * 10) / 10,
    threshold: check.threshold,
    status: check.status,
    sex: check.sex,
    ageGroup: check.ageGroup,
  });
  return { ...account, history: await seal(key, kept) };
}

export async function clearHistory(account, key) {
  return { ...account, history: await seal(key, []) };
}

/* ---- Storage (a list of accounts in localStorage) ---- */

function isAccount(a) {
  return a && a.v === 1 && typeof a.id === "string" && typeof a.name === "string"
    && (a.type === "personal" || a.type === "worker") && typeof a.salt === "string"
    && Number.isInteger(a.iterations) && a.iterations >= 1000 && a.check?.iv && a.history?.iv;
}

export function loadAccounts(storage = globalThis.localStorage) {
  try {
    const list = JSON.parse(storage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(list) ? list.filter(isAccount) : [];
  } catch {
    return [];
  }
}

export function saveAccount(account, storage = globalThis.localStorage) {
  const list = loadAccounts(storage).filter((a) => a.id !== account.id);
  list.push(account);
  storage.setItem(STORAGE_KEY, JSON.stringify(list));
}

export function deleteAccount(id, storage = globalThis.localStorage) {
  storage.setItem(STORAGE_KEY, JSON.stringify(loadAccounts(storage).filter((a) => a.id !== id)));
}
