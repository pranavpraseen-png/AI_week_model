import { test } from "node:test";
import assert from "node:assert/strict";
import {
  addCheck, AccountError, clearHistory, createAccount, deleteAccount, loadAccounts,
  readHistory, saveAccount, unlock, waitSeconds,
} from "../../web/js/accounts.js";

const FAST = { iterations: 1000 }; // the app uses 600,000; tests don't need to be slow

class MemoryStorage {
  constructor() { this.map = new Map(); }
  getItem(k) { return this.map.has(k) ? this.map.get(k) : null; }
  setItem(k, v) { this.map.set(k, String(v)); }
}

const check = { hb: 10.44, low: 10.1, high: 10.8, threshold: 12, status: "moderate", sex: "F", ageGroup: "15-49" };

test("create, unlock with the right PIN, refuse the wrong one", async () => {
  const { account } = await createAccount({ name: "  Asha   Devi ", type: "worker", pin: "482913", pinAgain: "482913" }, FAST);
  assert.equal(account.name, "Asha Devi");
  assert.ok(!JSON.stringify(account).includes("482913"), "the PIN itself is never stored");
  assert.ok((await unlock(account, "482913")).key);
  const wrong = await unlock(account, "000000");
  assert.equal(wrong.key, null);
  assert.equal(wrong.account.failures, 1);
});

test("history is encrypted and only readable with the key", async () => {
  const { account, key } = await createAccount({ name: "Meera", type: "personal", pin: "1234", pinAgain: "1234" }, FAST);
  const updated = await addCheck(account, key, check, Date.parse("2026-10-13T10:00:00Z"));
  assert.ok(!JSON.stringify(updated).includes("moderate"), "nothing readable in storage");
  const history = await readHistory(updated, key);
  assert.equal(history.length, 1);
  assert.equal(history[0].hb, 10.4);
  assert.equal(history[0].status, "moderate");
  const other = await createAccount({ name: "X", type: "personal", pin: "9999", pinAgain: "9999" }, FAST);
  await assert.rejects(readHistory(updated, other.key));
  assert.deepEqual(await readHistory(await clearHistory(updated, key), key), []);
});

test("old entries are dropped after a year", async () => {
  const { account, key } = await createAccount({ name: "M", type: "personal", pin: "1234", pinAgain: "1234" }, FAST);
  let a = await addCheck(account, key, check, Date.parse("2025-01-01T00:00:00Z"));
  a = await addCheck(a, key, check, Date.parse("2026-10-13T00:00:00Z"));
  assert.equal((await readHistory(a, key)).length, 1);
});

test("bad input is refused with a reason", async () => {
  const cases = [
    [{ name: " ", type: "personal", pin: "1234", pinAgain: "1234" }, "name"],
    [{ name: "A", type: "admin", pin: "1234", pinAgain: "1234" }, "type"],
    [{ name: "A", type: "personal", pin: "12a4", pinAgain: "12a4" }, "pin"],
    [{ name: "A", type: "personal", pin: "123", pinAgain: "123" }, "pin"],
    [{ name: "A", type: "personal", pin: "1234", pinAgain: "1235" }, "pin_mismatch"],
  ];
  for (const [input, code] of cases) {
    await assert.rejects(createAccount(input, FAST), (err) => err instanceof AccountError && err.code === code);
  }
});

test("after 5 wrong PINs the person has to wait, and waits grow", async () => {
  let { account } = await createAccount({ name: "A", type: "personal", pin: "1234", pinAgain: "1234" }, FAST);
  const now = 1_000_000;
  for (let i = 0; i < 5; i++) ({ account } = await unlock(account, "0000", now));
  assert.equal(waitSeconds(account, now), 30);
  const blocked = await unlock(account, "1234", now + 1000); // even the right PIN waits
  assert.equal(blocked.key, null);
  ({ account } = await unlock(account, "0000", now + 31_000));
  assert.equal(waitSeconds(account, now + 31_000), 60);
  const ok = await unlock(account, "1234", now + 92_000);
  assert.ok(ok.key);
  assert.equal(ok.account.failures, 0);
});

test("accounts are saved, listed and deleted; junk in storage is ignored", async () => {
  const storage = new MemoryStorage();
  const a = (await createAccount({ name: "A", type: "personal", pin: "1234", pinAgain: "1234" }, FAST)).account;
  const b = (await createAccount({ name: "B", type: "worker", pin: "5678", pinAgain: "5678" }, FAST)).account;
  saveAccount(a, storage);
  saveAccount(b, storage);
  assert.deepEqual(loadAccounts(storage).map((x) => x.name), ["A", "B"]);
  deleteAccount(a.id, storage);
  assert.deepEqual(loadAccounts(storage).map((x) => x.name), ["B"]);
  storage.setItem("anaemialens.accounts", '[{"v":1,"id":1},"junk"]');
  assert.deepEqual(loadAccounts(storage), []);
  storage.setItem("anaemialens.accounts", "{not json");
  assert.deepEqual(loadAccounts(storage), []);
});
