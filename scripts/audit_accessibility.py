"""Run the axe-core accessibility checker on every screen (light + dark, English + Hindi).

  npm install                                   # fetches axe-core (dev dependency)
  python scripts/serve_web.py --port 8611 &      # serve the site
  python scripts/audit_accessibility.py http://localhost:8611 data/simulated/images/india_0004.png

Prints every WCAG 2.2 A/AA (+ best-practice) violation, or "no violations".
CSP is bypassed only inside this audit browser, so axe can be injected.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
AXE = ROOT / "node_modules" / "axe-core" / "axe.min.js"
CHROMIUM = Path("/opt/pw-browsers/chromium")


def audit(page, label, axe):
    page.wait_for_timeout(300)
    page.evaluate(axe)
    result = page.evaluate("axe.run(document, {runOnly: ['wcag2a','wcag2aa','wcag21aa','wcag22aa','best-practice']})")
    for v in result["violations"]:
        print(f"[{label}] {v['impact']}: {v['id']} — {v['help']} ({len(v['nodes'])}) e.g. {v['nodes'][0]['target']}")
    if not result["violations"]:
        print(f"[{label}] no violations ({len(result['passes'])} rules passed)")
    return len(result["violations"])


def main():
    site, photo = sys.argv[1], sys.argv[2]
    axe = AXE.read_text()
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": str(CHROMIUM)} if CHROMIUM.exists() else {}))
        for scheme in ["light", "dark"]:
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, color_scheme=scheme, bypass_csp=True)
            page = ctx.new_page()
            page.goto(site, wait_until="networkidle")
            failures += audit(page, f"{scheme} home", axe)
            page.click("#start")
            failures += audit(page, f"{scheme} question", axe)
            page.click('[data-answer="sex"][data-value="F"]')
            page.click('[data-answer="age"][data-value="30"]')
            page.click('[data-answer="pregnant"][data-value="no"]')
            failures += audit(page, f"{scheme} tips", axe)
            page.set_input_files("#file-gallery", photo)
            page.wait_for_selector('[data-screen="confirm"]:not([hidden])')
            failures += audit(page, f"{scheme} confirm", axe)
            page.click("#use-photo")
            page.wait_for_selector('[data-screen="result"]:not([hidden])')
            failures += audit(page, f"{scheme} result", axe)
            page.click("#lang-toggle")
            failures += audit(page, f"{scheme} result (Hindi)", axe)
            page.click("#open-settings")
            failures += audit(page, f"{scheme} settings", axe)
            ctx.close()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, bypass_csp=True)
        page = ctx.new_page()
        page.goto(f"{site}/privacy.html", wait_until="networkidle")
        failures += audit(page, "privacy", axe)
        browser.close()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
