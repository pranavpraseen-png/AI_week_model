"""End-to-end: a real browser uses the website like a person would.

Checks: no console errors or security-policy violations, nothing is requested
from any other origin, the full flow works, the browser's result matches the
Python model for the same photo, bad files are refused, Hindi works.
Skipped when Playwright / Chromium are not installed.
"""
import functools
import http.server
import json
import os
import re
import socket
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

from features import extract_features  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import serve_web  # noqa: E402

CHROMIUM = Path("/opt/pw-browsers/chromium")


@pytest.fixture(scope="module")
def site():
    serve_web.Handler.extra_headers = serve_web.read_headers(ROOT / "web" / "_headers")
    handler = functools.partial(serve_web.Handler, directory=str(ROOT / "web"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://localhost:{port}"
    server.shutdown()


@pytest.fixture(scope="module")
def photos(tmp_path_factory):
    out = tmp_path_factory.mktemp("sim")
    subprocess.run([sys.executable, str(ROOT / "src" / "make_simulated_data.py"), "--n-per-region", "2",
                    "--out", str(out)], check=True, capture_output=True)
    return out


@pytest.fixture(scope="module")
def pw():
    with playwright_api.sync_playwright() as p:
        yield p


def launch(pw, **kwargs):
    if CHROMIUM.exists():
        kwargs["executable_path"] = str(CHROMIUM)
    try:
        return pw.chromium.launch(**kwargs)
    except Exception as err:  # no browser available in this environment
        pytest.skip(f"Chromium not available: {err}")


@pytest.fixture(scope="module")
def browser(pw):
    b = launch(pw)
    yield b
    b.close()


def open_page(browser, site, problems, requests, **context):
    page = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, **context).new_page()
    page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.on("request", lambda r: requests.append(r.url))
    page.add_init_script("document.addEventListener('securitypolicyviolation',"
                         " e => console.error('CSP violation: ' + e.violatedDirective + ' ' + e.blockedURI))")
    page.goto(site, wait_until="networkidle")
    return page


def python_hb(image_path):
    model = json.loads((ROOT / "web" / "model.json").read_text())
    feats = extract_features(image_path)
    m = model["multi"]
    z = [(feats[n] - mu) / sd for n, mu, sd in zip(model["feature_names"], m["mean"], m["std"])]
    return float(np.dot(z, m["w"]) + m["b"])


def shot(page, name):
    folder = os.environ.get("SCREENSHOT_DIR")
    if folder:
        page.wait_for_timeout(350)  # let the screen's fade-in finish
        page.screenshot(path=str(Path(folder) / f"{name}.png"), full_page=True)


def test_full_check_matches_python_and_stays_private(browser, site, photos):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests)
    assert page.locator("#hero-demo").is_visible()  # simulated model must be labelled on the opening page
    shot(page, "1-home")

    page.click("#start")
    assert page.locator("#demo-banner").is_visible()  # ...and on every app screen
    page.click('[data-answer="sex"][data-value="F"]')
    page.click('[data-answer="age"][data-value="30"]')
    assert page.locator('[data-screen="pregnant"]').is_visible()
    shot(page, "2-question")
    page.click('[data-answer="pregnant"][data-value="no"]')
    shot(page, "3-tips")

    image = photos / "images" / "ghana_0001.png"
    page.set_input_files("#file-gallery", str(image))
    page.wait_for_selector('[data-screen="confirm"]:not([hidden])')
    page.eval_on_selector("#guide-size", "el => { el.value = '50'; el.dispatchEvent(new Event('input')); }")
    page.wait_for_timeout(100)
    shot(page, "4-confirm")
    page.click("#use-photo")
    page.wait_for_selector('[data-screen="result"]:not([hidden])')
    shot(page, "5-result")

    shown = float(page.inner_text("#hb-value"))
    assert abs(shown - python_hb(image)) <= 0.051, (shown, python_hb(image))
    assert page.inner_text("#verdict-title")
    # Exactly one severity icon is visible, and it matches the category (no green tick on a warning).
    severity = page.get_attribute("#result-card", "data-severity")
    visible = page.eval_on_selector_all(".verdict-icon", "els => els.filter(e => e.getClientRects().length).map(e => e.dataset.icon)")
    expected = {"none": "none", "severe": "severe"}.get(severity, "warn")
    assert visible == [expected], (severity, visible)
    assert page.locator("#announcer").inner_text().startswith("Estimated haemoglobin")
    assert page.evaluate("document.getElementById('confirm-canvas').width") == 0  # photo deleted

    page.click("#lang-toggle")  # opens the language menu
    page.click('#lang-dialog .lang-option[data-lang="hi"]')
    page.locator('html[lang="hi"]').wait_for(state="attached")
    assert "अनुमानित हीमोग्लोबिन" in page.inner_text('[data-screen="result"]')
    assert page.evaluate("document.documentElement.lang") == "hi"
    shot(page, "6-result-hindi")

    assert page.evaluate("navigator.serviceWorker.ready.then(r => Boolean(r.active))")
    assert not problems, problems
    assert all(url.startswith(site) for url in requests), [u for u in requests if not u.startswith(site)]


def test_bad_files_are_refused(browser, site, tmp_path):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests)
    page.click("#start")
    page.click('[data-answer="sex"][data-value="M"]')
    page.click('[data-answer="age"][data-value="60"]')

    fake = tmp_path / "not-a-photo.png"
    fake.write_text("<script>alert(1)</script>")
    page.set_input_files("#file-gallery", str(fake))
    alert = page.locator('[data-screen="tips"] [data-error]')
    alert.wait_for()
    assert "not a photo" in alert.inner_text()
    assert page.locator('[data-screen="tips"]').is_visible()
    assert not problems, problems


def test_dark_mode_and_reduced_motion_render(browser, site):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests, color_scheme="dark", reduced_motion="reduce")
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg == "rgb(19, 23, 26)"
    shot(page, "7-home-dark")
    assert not problems, problems


def test_security_headers_are_served(site):
    import urllib.request
    with urllib.request.urlopen(site) as response:
        headers = response.headers
    csp = headers["Content-Security-Policy"]
    for directive in ["default-src 'none'", "script-src 'self'", "frame-ancestors 'none'",
                      "require-trusted-types-for 'script'", "object-src 'none'", "base-uri 'none'"]:
        assert directive in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert "camera=(self)" in headers["Permissions-Policy"]


def test_live_camera_flow(pw, site):
    """Chromium's built-in fake camera stands in for a phone camera."""
    problems, requests = [], []
    b = launch(pw, args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
    try:
        page = open_page(b, site, problems, requests, permissions=["camera"])
        page.click("#start")
        page.click('[data-answer="sex"][data-value="M"]')
        page.click('[data-answer="age"][data-value="8"]')
        page.click("#open-camera")
        page.wait_for_selector("#shutter:not([disabled])", timeout=10000)
        assert page.evaluate("document.getElementById('video').videoWidth") > 0
        shot(page, "8-camera")
        page.click("#shutter")
        page.wait_for_selector('[data-screen="confirm"]:not([hidden])')
        # The camera is switched off as soon as the photo is taken.
        assert page.evaluate("document.getElementById('video').srcObject") is None
        assert page.evaluate("document.getElementById('confirm-canvas').width") > 0
    finally:
        b.close()
    assert not problems, problems


class _FakeLLM(http.server.BaseHTTPRequestHandler):
    """A 'local language model' that replies with hostile HTML."""
    reply = '<img src=x onerror="window.__pwned=1">Get a blood test. <script>window.__pwned=1</script>'

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeLLM.last_request = body
        payload = json.dumps({"choices": [{"message": {"content": self.reply}}]}).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def test_settings_and_local_explanation_are_safe(browser, site, photos):
    try:
        llm = http.server.ThreadingHTTPServer(("127.0.0.1", 8080), _FakeLLM)
    except OSError:
        pytest.skip("port 8080 is busy")
    threading.Thread(target=llm.serve_forever, daemon=True).start()
    try:
        problems, requests = [], []
        page = open_page(browser, site, problems, requests)
        page.click("#open-settings")
        page.check("#explain-enabled")
        page.fill("#explain-endpoint", "https://evil.example.com/v1")
        assert page.locator("#endpoint-error").is_visible()  # other computers are refused
        page.fill("#explain-endpoint", "http://127.0.0.1:8080/v1")
        assert page.locator("#endpoint-error").is_hidden()
        shot(page, "9-settings")
        page.click('#settings button[value="close"]')
        assert not page.evaluate("document.getElementById('settings').open")

        page.click("#start")
        page.click('[data-answer="sex"][data-value="F"]')
        page.click('[data-answer="age"][data-value="60"]')
        page.set_input_files("#file-gallery", str(photos / "images" / "india_0000.png"))
        page.wait_for_selector('[data-screen="confirm"]:not([hidden])')
        page.click("#use-photo")
        page.wait_for_selector("#explain:not([hidden])")
        page.click("#explain-go")
        # (Playwright's wait_for_function uses eval, which this site's CSP rightly blocks.)
        page.locator("#explain-text", has_text="blood test").wait_for()

        # The reply is shown as text: the tags appear literally and never run.
        assert "<img" in page.inner_text("#explain-text")
        assert page.evaluate("document.querySelectorAll('#explain-text *').length") == 0
        assert page.evaluate("window.__pwned") is None
        # Only numbers were sent, never the photo.
        sent = json.dumps(_FakeLLM.last_request)
        assert "base64" not in sent and "data:image" not in sent and "g/dL" in sent
        assert not problems, problems
    finally:
        llm.shutdown()


def test_works_in_airplane_mode(browser, site):
    """After one visit, the whole check works with no network at all."""
    problems, requests = [], []
    page = open_page(browser, site, problems, requests)
    assert page.evaluate("navigator.serviceWorker.ready.then(r => Boolean(r.active))")
    page.reload(wait_until="networkidle")  # now controlled by the service worker
    page.context.set_offline(True)
    page.reload()
    page.locator("#start:not([disabled])").wait_for()
    page.click("#start")
    page.click('[data-answer="sex"][data-value="F"]')
    assert page.locator('[data-screen="age"]').is_visible()
    page.context.set_offline(False)
    assert not problems, problems


# ---------------------------------------------------------------------------
# Accounts, opening page, languages and layout
# ---------------------------------------------------------------------------

I18N = (ROOT / "web" / "js" / "i18n.js").read_text(encoding="utf-8")
EN_BLOCK = I18N.split("  en: {", 1)[1].split("\n  },", 1)[0]
EN = dict(re.findall(r'^\s*"([^"]+)":\s*"((?:[^"\\]|\\.)*)",?\s*$', EN_BLOCK, flags=re.M))
LANGUAGE_LIST = re.findall(r'\{ code: "(\w+)", name: "[^"]+"(?:, dir: "(\w+)")? \}',
                           I18N.split("export const LANGUAGES", 1)[1].split("];", 1)[0])
PIN = "482913"
ACCOUNTS_KEY = "anaemialens.accounts"


def poll(page, script, ok, timeout=6000):
    """Re-run a page.evaluate until ok(value) (wait_for_function is blocked by the CSP)."""
    waited = 0
    value = page.evaluate(script)
    while not ok(value) and waited < timeout:
        page.wait_for_timeout(50)
        waited += 50
        value = page.evaluate(script)
    return value


def stored_accounts(page):
    return page.evaluate(f"localStorage.getItem('{ACCOUNTS_KEY}')")


def create_account(page, name, kind="personal", pin=PIN, pin2=None):
    page.locator('[data-screen="home"] [data-go="create"]').first.click()
    page.wait_for_selector('[data-screen="create"]:not([hidden])')
    page.fill("#create-name", name)
    page.check(f'input[name="account-type"][value="{kind}"]')
    page.fill("#create-pin", pin)
    page.fill("#create-pin2", pin if pin2 is None else pin2)
    page.click("#create-go")


def do_check(page, image):
    page.click('[data-answer="sex"][data-value="F"]')
    page.click('[data-answer="age"][data-value="30"]')
    page.click('[data-answer="pregnant"][data-value="no"]')
    page.set_input_files("#file-gallery", str(image))
    page.wait_for_selector('[data-screen="confirm"]:not([hidden])')
    page.click("#use-photo")
    page.wait_for_selector('[data-screen="result"]:not([hidden])')


def submit_unlock(page, pin):
    """Type a PIN on the sign-in screen and return the message shown (or None if it unlocked)."""
    page.fill("#unlock-pin", pin)
    page.click("#unlock-go")  # the submit handler hides the old message synchronously
    page.wait_for_selector('#unlock-error:not([hidden]), [data-screen="account"]:not([hidden])', timeout=15000)
    if page.locator('[data-screen="account"]').is_visible():
        return None
    return page.inner_text("#unlock-error")


def test_account_full_lifecycle(browser, site, photos):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests)

    create_account(page, "Asha Didi", kind="worker")
    page.wait_for_selector('[data-screen="account"]:not([hidden])', timeout=15000)
    assert page.locator("#account-chip").is_visible()
    assert page.inner_text("#account-chip-name") == "Asha Didi"
    assert page.locator("#history-empty").is_visible()

    page.click("#account-start")
    do_check(page, photos / "images" / "india_0001.png")
    note = page.locator("#saved-note")
    note.wait_for(state="visible")
    assert "Asha Didi" in note.inner_text()
    shown_hb = page.inner_text("#hb-value").strip()
    shown_status = page.get_attribute("#result-card", "data-severity")

    page.click("#account-chip")
    page.wait_for_selector('[data-screen="account"]:not([hidden])')
    page.locator("#history li").first.wait_for()
    assert page.locator("#history li").count() == 1
    assert shown_hb in page.inner_text("#history")
    assert page.locator("#dash-stats .dash-stat strong").first.inner_text() == "1"  # checked today

    # Only the name and the encryption envelope are readable in storage.
    raw = stored_accounts(page)
    assert raw and "Asha Didi" in raw
    assert PIN not in raw
    assert shown_hb not in raw and '"hb"' not in raw and '"status"' not in raw
    for word in {"none", "mild", "moderate", "severe", "borderline", shown_status}:
        assert not re.search(rf"(?<![A-Za-z0-9+/=]){word}(?![A-Za-z0-9+/=])", raw), word

    # Lock, then sign in again: a wrong PIN is refused, the right one opens the same history.
    page.click("#account-lock")
    page.wait_for_selector('[data-screen="home"]:not([hidden])')
    assert page.locator("#account-chip").is_hidden()
    page.locator('[data-screen="home"] [data-go="signin"]').first.click()
    page.wait_for_selector("#unlock-form:not([hidden])")
    assert submit_unlock(page, "000000") == EN["account.err.wrong"]
    assert page.locator('[data-screen="signin"]').is_visible()
    assert submit_unlock(page, PIN) is None
    assert page.locator("#account-chip").is_visible()
    page.locator("#history li").first.wait_for()
    assert page.locator("#history li").count() == 1

    # Manage: clear the history, then delete the account (it asks twice).
    page.click('[data-screen="account"] .danger-zone summary')
    page.click("#history-clear")
    page.locator("#history-empty").wait_for(state="visible")
    assert page.locator("#history li").count() == 0
    assert page.inner_text("#manage-status") == EN["account.cleared"]
    page.click("#account-delete")
    assert page.inner_text("#account-delete") == EN["account.delete.confirm"]
    assert page.locator('[data-screen="account"]').is_visible()
    page.click("#account-delete")
    page.wait_for_selector('[data-screen="home"]:not([hidden])')
    assert json.loads(stored_accounts(page)) == []
    assert page.locator("#account-chip").is_hidden()
    assert not problems, problems


def test_account_pin_mismatch_and_short_pin_are_refused(browser, site):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests)

    create_account(page, "Meena", pin=PIN, pin2="482914")
    error = page.locator("#create-error")
    error.wait_for(state="visible")
    assert error.inner_text() == EN["account.err.pin_mismatch"]
    assert page.locator('[data-screen="create"]').is_visible()

    page.fill("#create-pin", "12")
    page.fill("#create-pin2", "12")
    page.click("#create-go")
    page.locator("#create-error", has_text=EN["account.err.pin"]).wait_for()
    assert page.locator('[data-screen="create"]').is_visible()
    assert page.locator('[data-screen="account"]').is_hidden()
    assert page.locator("#account-chip").is_hidden()
    assert json.loads(stored_accounts(page) or "[]") == []
    assert not problems, problems


def test_too_many_wrong_pins_make_you_wait(browser, site):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests)
    create_account(page, "Ravi")
    page.wait_for_selector('[data-screen="account"]:not([hidden])', timeout=15000)
    page.click("#account-lock")
    page.locator('[data-screen="home"] [data-go="signin"]').first.click()
    page.wait_for_selector("#unlock-form:not([hidden])")

    messages = [submit_unlock(page, "000000") for _ in range(5)]
    assert messages[:4] == [EN["account.err.wrong"]] * 4, messages
    wait_prefix = EN["account.err.wait"].split("{seconds}")[0]
    sixth = submit_unlock(page, "000000")
    assert sixth.startswith(wait_prefix), sixth
    seconds = int(re.search(r"\d+", sixth).group())
    assert 0 < seconds <= 30, sixth

    # Even the right PIN is refused until the wait is over.
    assert submit_unlock(page, PIN).startswith(wait_prefix)
    assert page.locator('[data-screen="account"]').is_hidden()
    assert page.locator("#account-chip").is_hidden()
    assert json.loads(stored_accounts(page))[0]["failures"] == 5
    assert not problems, problems


def test_opening_page_animates_and_story_follows_scroll(browser, site):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests)

    # The live bloodstream behind the headline is sized and drawn.
    size = page.evaluate("(() => { const c = document.getElementById('bloodstream'); return [c.width, c.height]; })()")
    assert size[0] > 0 and size[1] > 0, size
    ink = ("(() => { const c = document.getElementById('bloodstream');"
           " const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;"
           " let n = 0, s = 0; for (let i = 3; i < d.length; i += 4) { if (d[i]) { n++; s += d[i] * (i % 9973); } }"
           " return [n, s]; })()")
    first = poll(page, ink, lambda v: v[0] > 0)
    assert first[0] > 0, "the bloodstream canvas is empty"
    moved = poll(page, ink, lambda v: v != first, timeout=3000)
    assert moved != first, "the bloodstream does not move"

    # Scroll story: pale nail and low Hb at the start, red nail and healthy Hb at the end.
    read = ("(() => [Number(document.getElementById('story-hb').textContent),"
            " getComputedStyle(document.getElementById('story-nail')).fill,"
            " document.getElementById('story-band').textContent])()")
    page.evaluate("window.scrollTo(0, document.getElementById('story').offsetTop)")
    start = poll(page, read, lambda v: v[0] <= 7)
    assert start[0] <= 7, start
    assert start[2] == EN["story.band.severe"], start
    page.evaluate("(() => { const s = document.getElementById('story');"
                  " window.scrollTo(0, s.offsetTop + s.offsetHeight - innerHeight); })()")
    end = poll(page, read, lambda v: v[0] >= 15 and v[2] == EN["story.band.healthy"])
    assert end[0] >= 15, end
    assert end[1] != start[1], (start, end)
    assert end[2] == EN["story.band.healthy"], end

    # The big number counts up once it scrolls into view, and finishes on 57%.
    stat = page.locator('[data-count="57"]')
    stat.scroll_into_view_if_needed()
    page.locator(".intro-stats.is-visible").wait_for(state="attached")
    final = poll(page, "document.querySelector('[data-count=\"57\"]').textContent", lambda v: v == "57%")
    assert final == "57%", final
    assert not problems, problems


def test_reduced_motion_shows_everything_without_scrolling(browser, site):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests, reduced_motion="reduce")
    page.locator(".hero.is-in").wait_for(state="attached")
    states = page.evaluate("[...document.querySelectorAll('[data-reveal]')].map(e => e.classList.contains('is-visible'))")
    assert states and all(states), states
    assert page.evaluate("scrollY") == 0
    assert not problems, problems


def test_every_available_language_translates_the_page(browser, site):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests)
    page.click("#lang-toggle")
    assert page.evaluate("document.getElementById('lang-dialog').open")
    assert page.locator("#lang-dialog .lang-option").count() == 12 == len(LANGUAGE_LIST)

    lang_dir = ROOT / "web" / "js" / "lang"
    available = [(code, d or "ltr") for code, d in LANGUAGE_LIST
                 if code in ("en", "hi") or (lang_dir / f"{code}.js").exists()]
    assert {"en", "hi"} <= {code for code, _ in available}
    keys = sorted(EN)
    find_raw = """(keys) => {
      const known = new Set(keys), bad = [];
      for (const node of document.querySelectorAll('[data-i18n]')) {
        const key = node.dataset.i18n, text = node.textContent.trim();
        const visible = node.getClientRects().length > 0;
        const leaked = (text.match(/[a-z][a-z0-9_]*(?:\\.[a-z0-9_]+)+/g) || []).filter(w => known.has(w));
        if (text === key || leaked.length || (visible && !text)) bad.push([key, text.slice(0, 60)]);
      }
      return bad;
    }"""
    for code, direction in available:
        if not page.evaluate("document.getElementById('lang-dialog').open"):
            page.click("#lang-toggle")
        page.click(f'#lang-dialog .lang-option[data-lang="{code}"]')
        page.locator(f'html[lang="{code}"]').wait_for(state="attached", timeout=5000)
        assert page.evaluate("document.documentElement.lang") == code
        assert page.evaluate("document.documentElement.dir") == direction, code
        assert page.evaluate(find_raw, keys) == [], code
        assert page.locator(f'#lang-dialog .lang-option[data-lang="{code}"]').get_attribute("aria-pressed") == "true"
    assert not problems, problems


def test_wide_screens_put_question_and_answers_side_by_side(browser, site):
    problems, requests = [], []
    page = open_page(browser, site, problems, requests)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.click("#start")
    page.wait_for_selector('[data-screen="sex"]:not([hidden])')
    head = page.locator('[data-screen="sex"] .screen-head').bounding_box()
    body = page.locator('[data-screen="sex"] .screen-body').bounding_box()
    assert head["x"] + head["width"] <= body["x"] + 0.5, (head, body)
    shot(page, "10-landscape")

    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(100)
    head = page.locator('[data-screen="sex"] .screen-head').bounding_box()
    body = page.locator('[data-screen="sex"] .screen-body').bounding_box()
    assert body["y"] >= head["y"] + head["height"] - 0.5, (head, body)
    assert not problems, problems
