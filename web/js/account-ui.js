// Screens for on-device accounts: sign in, create, and the signed-in person's
// page (history, trend, daily log). The encryption itself is in accounts.js.
import { $, el, setText } from "./dom.js";
import * as acc from "./accounts.js";

const AUTO_LOCK_MS = 10 * 60 * 1000; // lock after 10 minutes without a tap
const AWAY_LOCK_MS = 5 * 60 * 1000; // or after 5 minutes in the background
const AGE_GROUP_KEY = { 3: "q.age.0", 8: "q.age.1", 13: "q.age.2", 30: "q.age.3", 60: "q.age.4" };

export function initAccountUI({ show, tr, lang }) {
  let session = null; // { account, key } while unlocked
  let picked = null; // account chosen on the sign-in screen
  let idleTimer = 0;
  let hiddenAt = 0;
  let deleteArmed = false;

  const find = (id) => acc.loadAccounts().find((a) => a.id === id);
  const sameDay = (iso, now = new Date()) => new Date(iso).toDateString() === now.toDateString();

  function updateChip() {
    $("#account-chip").hidden = !session;
    if (session) setText($("#account-chip-name"), session.account.name);
  }

  function showFormError(box, key, vars) {
    setText(box, tr(key, vars));
    box.hidden = false;
  }

  /* ---------- Sign in ---------- */

  function renderSignin() {
    const accounts = acc.loadAccounts();
    if (picked && !find(picked)) picked = null;
    if (!picked && accounts.length === 1) picked = accounts[0].id;
    const list = $("#account-list");
    list.replaceChildren();
    for (const account of accounts) {
      const button = el("button");
      button.type = "button";
      button.className = "choice account-pick";
      button.setAttribute("aria-pressed", String(account.id === picked));
      const label = el("span", account.name);
      label.append(el("small", tr(`account.label.${account.type}`)));
      button.append(label);
      button.addEventListener("click", () => {
        picked = account.id;
        renderSignin();
        $("#unlock-pin").focus();
      });
      list.append(button);
    }
    $("#no-accounts").hidden = accounts.length > 0;
    const form = $("#unlock-form");
    form.hidden = !picked;
    if (picked) setText($("#unlock-hello"), tr("account.welcome", { name: find(picked).name }));
  }

  $("#unlock-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = $("#unlock-error");
    error.hidden = true;
    const account = find(picked);
    if (!account) return;
    const wait = acc.waitSeconds(account);
    if (wait > 0) return showFormError(error, "account.err.wait", { seconds: wait });
    const button = $("#unlock-go");
    button.disabled = true;
    setText(button, tr("account.unlocking"));
    const pinInput = $("#unlock-pin");
    const result = await acc.unlock(account, pinInput.value);
    pinInput.value = "";
    button.disabled = false;
    setText(button, tr("account.unlock"));
    acc.saveAccount(result.account);
    if (!result.key) {
      const after = acc.waitSeconds(result.account);
      return after > 0
        ? showFormError(error, "account.err.wait", { seconds: after })
        : showFormError(error, "account.err.wrong");
    }
    session = { account: result.account, key: result.key };
    picked = null;
    updateChip();
    armIdleLock();
    show("account");
  });

  $("#forgot-pin").addEventListener("click", () => {
    const box = $("#forgot-box");
    box.hidden = !box.hidden;
  });

  $("#forgot-delete").addEventListener("click", () => {
    acc.deleteAccount(picked);
    picked = null;
    $("#forgot-box").hidden = true;
    renderSignin();
  });

  /* ---------- Create ---------- */

  $("#create-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = $("#create-error");
    error.hidden = true;
    const button = $("#create-go");
    button.disabled = true;
    try {
      const { account, key } = await acc.createAccount({
        name: $("#create-name").value,
        type: document.querySelector('input[name="account-type"]:checked')?.value,
        pin: $("#create-pin").value,
        pinAgain: $("#create-pin2").value,
      });
      try {
        acc.saveAccount(account);
      } catch {
        return showFormError(error, "account.err.storage");
      }
      session = { account, key };
      $("#create-form").reset();
      updateChip();
      armIdleLock();
      show("account");
    } catch (err) {
      showFormError(error, err instanceof acc.AccountError ? `account.err.${err.code}` : "account.err.storage");
    } finally {
      $("#create-pin").value = "";
      $("#create-pin2").value = "";
      button.disabled = false;
    }
  });

  /* ---------- The signed-in person's page ---------- */

  function stat(value, label) {
    const box = el("div");
    box.className = "dash-stat";
    box.append(el("strong", value), el("span", label));
    return box;
  }

  function entryRow(entry) {
    const li = el("li");
    const dot = el("span");
    dot.className = "h-dot";
    dot.dataset.s = entry.status;
    const hb = el("span", `${entry.hb.toFixed(1)} g/dL · ${tr(`sev.${entry.status}.t`)}`);
    hb.className = "h-hb";
    const when = new Date(entry.at).toLocaleString(lang() === "hi" ? "hi-IN" : "en-IN", {
      day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
    });
    const who = [AGE_GROUP_KEY[entry.ageGroup] ? tr(AGE_GROUP_KEY[entry.ageGroup]) : "", entry.sex === "M" ? tr("q.male") : tr("q.female")];
    const meta = el("span", [when, ...who].filter(Boolean).join(" · "));
    meta.className = "h-meta";
    li.append(dot, hb, meta);
    return li;
  }

  function drawTrend(entries) {
    const svg = $("#trend-chart");
    const NS = "http://www.w3.org/2000/svg";
    svg.replaceChildren();
    const values = entries.map((e) => e.hb);
    const cut = entries.at(-1).threshold;
    const lo = Math.min(...values, cut) - 1;
    const hi = Math.max(...values, cut) + 1;
    const x = (i) => 40 + (i / (entries.length - 1)) * 520;
    const y = (v) => 190 - ((v - lo) / (hi - lo)) * 160;
    const cutLine = document.createElementNS(NS, "line");
    cutLine.setAttribute("class", "trend-cut");
    cutLine.setAttribute("x1", "40");
    cutLine.setAttribute("x2", "560");
    cutLine.setAttribute("y1", y(cut).toFixed(1));
    cutLine.setAttribute("y2", y(cut).toFixed(1));
    const path = document.createElementNS(NS, "path");
    path.setAttribute("class", "trend-line");
    path.setAttribute("d", values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" "));
    svg.append(cutLine, path);
    values.forEach((v, i) => {
      const dot = document.createElementNS(NS, "circle");
      dot.setAttribute("class", "trend-dot");
      dot.setAttribute("cx", x(i).toFixed(1));
      dot.setAttribute("cy", y(v).toFixed(1));
      dot.setAttribute("r", "6");
      svg.append(dot);
    });
    svg.setAttribute("aria-label", `${tr("account.trend")} ${values.map((v) => v.toFixed(1)).join(", ")} g/dL`);
  }

  async function renderAccount() {
    if (!session) return show("signin", { replace: true });
    const { account, key } = session;
    const worker = account.type === "worker";
    setText($("#account-title"), tr("account.hello", { name: account.name }));
    setText($("#account-type-label"), tr(`account.label.${account.type}`));
    setText($("#history-title"), tr(worker ? "account.history.worker" : "account.history.personal"));
    const history = await acc.readHistory(account, key);
    const shown = (worker ? history.filter((e) => sameDay(e.at)) : history).slice().reverse();
    const stats = $("#dash-stats");
    stats.replaceChildren();
    if (worker) {
      stats.append(
        stat(String(shown.length), tr("account.stat.today")),
        stat(String(shown.filter((e) => e.status !== "none").length), tr("account.stat.flagged")),
      );
    } else {
      stats.append(
        stat(String(history.length), tr("account.stat.total")),
        stat(history.length ? history.at(-1).hb.toFixed(1) : "–", tr("account.stat.last")),
      );
    }
    const trend = $("#trend");
    trend.hidden = worker || history.length < 2;
    if (!trend.hidden) drawTrend(history.slice(-20));
    const list = $("#history");
    list.replaceChildren(...shown.slice(0, 50).map(entryRow));
    $("#history-empty").hidden = shown.length > 0;
    setText($("#manage-status"), "");
    deleteArmed = false;
    setText($("#account-delete"), tr("account.delete"));
  }

  $("#account-lock").addEventListener("click", () => lock());

  $("#history-clear").addEventListener("click", async () => {
    session.account = await acc.clearHistory(session.account, session.key);
    acc.saveAccount(session.account);
    await renderAccount();
    setText($("#manage-status"), tr("account.cleared"));
  });

  $("#account-delete").addEventListener("click", () => {
    if (!deleteArmed) {
      deleteArmed = true;
      setText($("#account-delete"), tr("account.delete.confirm"));
      return;
    }
    acc.deleteAccount(session.account.id);
    session = null;
    updateChip();
    show("home");
  });

  /* ---------- Locking ---------- */

  function lock(notice) {
    session = null;
    clearTimeout(idleTimer);
    updateChip();
    if (notice) {
      show("signin");
      showFormError($("#unlock-error"), "account.locked");
      $("#unlock-form").hidden = false;
    } else {
      show("home");
    }
  }

  function armIdleLock() {
    clearTimeout(idleTimer);
    if (session) idleTimer = setTimeout(() => lock(true), AUTO_LOCK_MS);
  }

  for (const type of ["pointerdown", "keydown"]) document.addEventListener(type, armIdleLock, { passive: true });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) hiddenAt = Date.now();
    else if (session && Date.now() - hiddenAt > AWAY_LOCK_MS) lock(true);
  });

  $("#account-chip").addEventListener("click", () => show("account"));
  $("#skip-account").addEventListener("click", () => show("sex"));

  return {
    get signedIn() {
      return Boolean(session);
    },
    get name() {
      return session?.account.name ?? "";
    },
    // Save one finished check to the signed-in account (encrypted). Returns true if saved.
    async saveCheck(result, person, status) {
      if (!session) return false;
      session.account = await acc.addCheck(session.account, session.key, {
        ...result, status, sex: person.sex, ageGroup: person.age,
      });
      acc.saveAccount(session.account);
      return true;
    },
    onShow(name) {
      if (name === "signin") renderSignin();
      if (name === "account") renderAccount();
    },
    refresh(current) {
      updateChip();
      this.onShow(current);
    },
  };
}
