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
    assert page.locator("#demo-banner").is_visible()  # simulated model must be labelled
    shot(page, "1-home")

    page.click("#start")
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

    page.click("#lang-toggle")
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
