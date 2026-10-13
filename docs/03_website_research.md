# The AnaemiaLens website: research, decisions and how it works

A usable MVP website for the anaemia check. It runs **entirely on the phone**, works **offline**, is available in **English and Hindi**, and is locked down so the photo **cannot** leave the device.

Contents:
1. [The core decision: everything on the device](#1-the-core-decision-everything-on-the-device)
2. [UX research → what we built](#2-ux-research--what-we-built)
3. [Security research → what we built](#3-security-research--what-we-built)
4. [Visual design](#4-visual-design)
5. [Every file, explained](#5-every-file-explained)
6. [Testing: how we know it works](#6-testing-how-we-know-it-works)
7. [Running and deploying](#7-running-and-deploying)
8. [Using a local language model with the website](#8-using-a-local-language-model-with-the-website)
9. [Limits and next steps](#9-limits-and-next-steps)
10. [Sources](#10-sources)

---

## 1. The core decision: everything on the device

| Option | Security | Privacy | Works offline | Cost |
|---|---|---|---|---|
| Upload the photo to a server, which runs the model | A server to attack and patch; health photos stored somewhere | Photos leave the phone | ✗ | Hosting |
| **Run the model in the browser (chosen)** | **No server code at all; nothing to break into** | **The photo never leaves the phone** | **✓** | **Free static hosting** |

This is possible because our model is tiny: the whole "trained AI" is **8 numbers** (7 slopes + 1 intercept) in `web/model.json`. JavaScript measures the photo's colours and applies `Hb = m₁x₁ + … + m₇x₇ + b`, the same equation Python learned.

**The catch:** the browser must compute *exactly* the same features as Python, or the learned m's and b would be applied to the wrong numbers. So `web/js/features.js` is a line-by-line port of `src/features.py`, and a test (`tests/test_web_parity.py`) feeds identical pixels to both and requires the features to agree to 0.000000001 and the Hb to 0.000001.

---

## 2. UX research → what we built

Research covered existing anaemia apps (Mannino et al. 2018, Sanguina, EzeCheck, Purdue's eyelid app), risk-communication studies, low-literacy design in India, GOV.UK and NHS design systems, and WCAG 2.2. Each finding is listed with the feature it led to.

| Research finding | What we built |
|---|---|
| Low-literacy users in India find typing and dropdowns hard; picture + text works (Medhi et al., Microsoft Research; CHW studies in Chhattisgarh) | **No typing anywhere.** Big tap targets with icons + words. Age is chosen from **5 age groups**, not typed. |
| GOV.UK pattern: **one question per screen** | Sex → age group → pregnancy, each on its own screen with a Back button and "Step 1 of 3". |
| Ask only questions that apply | Pregnancy is asked **only** for women aged 15–49. "Not sure" uses the stricter non-pregnant cut-off, which flags more people rather than fewer. |
| The Mannino fingernail app has the user **tap the nail after taking the photo** | **Confirm screen:** tap the nail to move the square, use a slider to fit it, and the overlay shows exactly what is measured (nail) and what is compared (skin). |
| Bare nails, same lighting every time, no flash glare (AnemoCheck, clinical protocols) | **Illustrated tips screen** before the camera opens: daylight/no flash, bare nail, warm relaxed hand, fill the square. |
| Check photo quality and give a specific retake reason | Live **quality check**: "too dark → move to a window", "too bright", "shiny reflection → tilt your finger". Photos the model can't measure are refused, not guessed. |
| Live preview with an on-screen guide is best; always keep fallbacks (web.dev) | Live camera with a **guide square** (rear camera), plus "Use phone camera app" (`capture="environment"`) and "Choose a photo". A blocked camera gets a clear message and these alternatives. |
| Show **a number with a range** (Winton Centre: ranges don't lose trust; vague caveats do) | "**11.7 g/dL**, likely between 11.0 and 12.3". |
| A **number line with labelled bands** helps people judge how serious a result is (JMIR 2018) | A Hb scale coloured with **this person's** WHO bands (severe / moderate / mild / healthy), the estimate as a dot, the range as a bracket and the cut-off as a dashed line. |
| Never use colour alone (WCAG 1.4.1) | Every category has **colour + icon shape + words**: ✓ circle (none), ▲ triangle (borderline/mild/moderate), ⯃ octagon (severe). |
| Avoid false reassurance | "No sign" still says **"a photo check cannot rule anaemia out"**. If the likely range crosses the cut-off, the result is **"Borderline — get a blood test"**. |
| Put "screening, not diagnosis" next to the result, not only on a splash screen | "This is a quick photo check, not a blood test" is **inside the result card**. |
| NHS-style action cards that match urgency | "What to do next": free blood test (Anemia Mukt Bharat), iron foods, vitamin C, tea timing. Severe says **"see a doctor or nurse today"**. |
| Plain language, reading age 9–11 (NHS, CDC Clear Communication Index) | Short sentences, everyday words ("haemoglobin is what makes blood red"). |
| Hindi needs line-height ≥ 1.6–1.8 and body ≥ 18px (India's UX4G design system); self-host Noto Devanagari | **Noto Sans Devanagari** self-hosted, 19px body, **line-height 1.8** for Hindi, international digits ("11.7"). |
| Privacy claims must be **checkable**, not just stated (CHI 2025) | Works in **airplane mode** (tested); "the photo has been deleted" shown on the result; privacy page explains how to check it yourself. |
| No accounts for emergent users | No sign-up, no login, nothing to remember. |
| ASHA (community health worker) workflow: screen many people in a row | **"Check another person"** jumps straight back to the first question; nothing from the previous person is kept. |
| WCAG 2.2: targets ≥ 24px (we use 48px+), visible focus, status messages, reduced motion | 48–80px targets, 3px focus rings, a `role="status"` region announces the result, the fade-in is switched off with reduced motion. |
| Dark mode: follow the system, check contrast in both themes | Full dark theme; **axe-core reports 0 violations** on every screen in both themes and both languages. |
| Credibility: say who made it, show honest accuracy and limits (Stanford Web Credibility) | `privacy.html`: who made it, data used, **honest accuracy (simulated, so real accuracy is not yet known)**, limits. |
| Avoid the generic "AI look": purple gradients, sparkles, three-card grids | No gradients, no sparkles, no "AI-powered" wording. See §4. |

---

## 3. Security research → what we built

Threat model: there is no server, so the risks are **(a)** code injection in the page (XSS), **(b)** the photo or result leaking to a third party, **(c)** clickjacking (the site loaded invisibly inside another site), **(d)** malicious or broken files, **(e)** a hostile reply from the language model, and **(f)** supply-chain attacks (someone else's script turning bad).

| Risk | Defence | Where |
|---|---|---|
| Data leaving the device | **CSP `connect-src`** lists only this site and `localhost` ports for Ollama / llama.cpp. The **browser itself** blocks any other request. | `_headers`, `<meta>` in `index.html` |
| Script injection (XSS) | **CSP `script-src 'self'`**, no inline scripts, no `eval`. **Trusted Types** required: any write to `innerHTML` etc. throws. The code sets text with `textContent` only. | CSP, `js/dom.js` |
| Malicious LLM reply | Shown with `textContent` only, so HTML is never parsed. A test proves a reply containing `<img onerror>` and `<script>` shows as plain text and never runs. The length is capped and requests time out. | `js/explain.js`, `tests/test_web_e2e.py` |
| LLM address pointed at another machine | Only `localhost` / `127.0.0.1` allowed (checked in code **and** by the CSP). Only numbers are sent, never the photo. | `safeEndpoint()` |
| Clickjacking | `frame-ancestors 'none'` + `X-Frame-Options: DENY`; JS refuses to run inside a frame (for hosts without headers). | `_headers`, `app.js` |
| Malicious / huge image files ("decompression bombs") | File type checked from its **first bytes**, not its name; dimensions read from the **header before decoding**; limits of 15 MB and 40 megapixels; large photos shrunk before processing. | `js/image.js` |
| Tampered model file | `validateModel()` checks shapes, finite numbers, known feature names and positive std before use. | `js/model.js` |
| Supply-chain attacks | **Zero runtime dependencies**: no frameworks, CDNs, analytics or Google Fonts. Fonts are self-hosted (OFL). Embedding Google Fonts was ruled a GDPR breach in Germany (LG München 2022), and polyfill.io turned malicious in 2024. | whole site |
| Camera / mic / location misuse | `Permissions-Policy`: camera for this site only; microphone, location, payment, USB etc. disabled. The camera stops the moment the photo is taken (tested). | `_headers`, `camera.js` |
| Referrer and cross-origin leaks | `Referrer-Policy: no-referrer`, `nosniff`, COOP / CORP / COEP same-origin, HSTS. | `_headers` |
| Offline cache poisoning | The service worker only caches same-origin GET responses of type `basic`, never `localhost` LLM calls. The cache is versioned and old caches are deleted. | `sw.js` |

**The full header set** is in `web/_headers` (Netlify and Cloudflare Pages apply it). GitHub Pages cannot send custom headers, so each page also carries a `<meta>` CSP. `frame-ancestors`, `Permissions-Policy` and `nosniff` only work as real headers, which is why Netlify or Cloudflare Pages is the most secure place to host.

Not used, on purpose: `upgrade-insecure-requests`, which would break `http://localhost` calls in some browsers.

---

## 4. Visual design

The goal was "trustworthy health service", modelled on GOV.UK and NHS, not "tech demo".

- **Colour rules:** warm paper background (`#F7F3EC`) and near-black ink. **Teal is used only for actions**, and **green/amber/orange/red only for result severity**, so a button can never be confused with a warning.
- **Type:** *Fraunces* (a characterful serif) for English headings and the big number, *Noto Sans Devanagari* for body text and all Hindi, 19px body. Both are self-hosted (172 KB total).
- **Illustrations:** simple line drawings (research: semi-abstract pictures work better than photos for low-literacy users), drawn as inline SVG.
- **Signature element:** the Hb number line, a visual you can't get from a template.
- **Not used:** gradients, sparkles, emoji, glassmorphism, "AI-powered" wording.

| Home | Confirm the nail | Result | Result (Hindi) |
|---|---|---|---|
| ![Home](images/web_home.png) | ![Confirm](images/web_confirm.png) | ![Result](images/web_result.png) | ![Hindi result](images/web_result_hindi.png) |

All screenshots (light/dark, English/Hindi, every screen) can be regenerated by the browser tests: `SCREENSHOT_DIR=shots python -m pytest tests/test_web_e2e.py`.

---

## 5. Every file, explained

```
web/
├── index.html            the whole app: every screen is a <section>, shown one at a time
├── privacy.html          privacy, honest accuracy, limits, who made it
├── _headers              security headers for Netlify / Cloudflare Pages
├── manifest.webmanifest  makes it installable ("Add to home screen")
├── sw.js                 service worker: offline cache
├── model.json            the trained model (8 numbers + metadata), from src/export_web_model.py
├── css/styles.css        all styling, light + dark, English + Hindi
├── fonts/                self-hosted fonts + their licences
├── icons/                app icons
└── js/
    ├── app.js            screen flow, questions, photo confirm, result rendering, settings
    ├── features.js       photo pixels → 7 colour numbers (port of src/features.py)
    ├── model.js          y = m·x + b prediction, WHO cut-offs, severity, model validation
    ├── image.js          safe file checks, decoding, cropping, quality check
    ├── camera.js         live camera, guide square → photo pixels
    ├── explain.js        optional local-language-model explanation
    ├── i18n.js           every word of the interface in English and Hindi
    ├── dom.js            tiny helpers: textContent-only, safe localStorage
    └── register-sw.js    registers the service worker through a Trusted Types policy
```

### `js/features.js`: why it must match Python exactly
| Function | What / why |
|---|---|
| `centerMask`, `borderMask` | The middle 50% of the crop is "nail"; a 12% frame around the edge is "skin". These are the same regions as `src/features.py`. Python's `int()` = JS `Math.floor` for positive numbers; getting this wrong shifts the region by a pixel. |
| `colorStats` | Averages red/green chroma, log(R/G), brightness and saturation over the pixels, skipping shadow (mean < 0.08) and glare (max ≥ 0.98), with the same EPS = 1e-6 as Python. |
| `extractFeatures` | Returns the 7 features. Refuses photos with fewer than 50 usable nail pixels (`PhotoQualityError`) instead of guessing. |
| `fitWithin` | Shrinks to ≤ 512 px like PIL's `thumbnail`. |

### `js/model.js`
| Function | What / why |
|---|---|
| `validateModel` | `model.json` is data loaded over the network, so it's checked before use: feature names must be known ones, arrays must have matching lengths, and every number must be finite, with std > 0. |
| `predictHb` | `Hb = b + Σ ((x − mean)/std) × w`: exactly `LinearRegression.predict` in Python. |
| `whoThreshold`, `severity` | Copies of `src/evaluate.py` (tested against the same cases). |
| `screen` | Hb, range (± the model's test RMSE), cut-off and category. |

### `js/image.js`
| Function | What / why |
|---|---|
| `sniffType` | Reads the first bytes (`FF D8 FF` = JPEG, `89 50 4E 47` = PNG, `RIFF…WEBP`). A text file renamed `.png` is refused. |
| `readDimensions` | Reads width × height from the PNG IHDR, JPEG SOF or WebP header **without decoding**, to refuse decompression bombs. |
| `decodeFile` | Size and type checks → `createImageBitmap` (which applies the phone's EXIF rotation) → shrink to ≤ 2048 px. |
| `cropRegion` | Cuts the square around the nail (twice the guide's size, so the nail is the middle half and the skin forms the frame) and scales it to ≤ 512 px. |
| `photoQuality` | Brightness and glare on the nail area → "ok" / "dark" / "bright" / "glare". |

### `js/camera.js`
`startCamera` asks for the rear camera; a denial is reported as "denied" so the app can explain what to do. `captureFrame` works out where the on-screen guide square sits in the video's own pixels (the video uses `object-fit: cover`, so it's scaled and cropped) and returns that frame. `stopCamera` releases the camera immediately.

### `js/app.js`
- **Flow:** `show(screen)` hides all other screens, moves focus to the new heading (so screen readers announce it), and uses `history.pushState` so the phone's **Back button** works. Going "back" into a deleted photo or a finished result is blocked.
- **Confirm screen:** draws the photo on a canvas, dims everything outside the measured area, and draws the nail square (solid) and skin frame (dashed). Tapping moves the square; the slider resizes it; the quality message updates live.
- **Result:** computes the features, the Hb and the category, **then deletes the photo** (`bitmap.close()`, canvas emptied). It renders the number, range, bands, icon, next steps and the equation in "How this number was worked out".
- **Borderline rule:** if the range crosses the cut-off and the category is none or mild, show "Borderline".
- **Settings:** language, plus the optional local language model (off by default). Saved in `localStorage` (preferences only, never results).

### `js/i18n.js`
131 keys in English and Hindi, so every element names its text with `data-i18n="key"`. A test checks both languages have exactly the same keys. **The Hindi should be reviewed by a native speaker / ASHA before real use.**

---

## 6. Testing: how we know it works

| Test | What it proves |
|---|---|
| `tests/test_web_parity.py` (+ `tests/web/parity.test.js`) | Browser and Python compute **identical features** (≤ 1e-9) and **identical Hb** (≤ 1e-6) on the same photos. |
| `tests/web/model.test.js` | WHO cut-offs and severity match Python; tampered models are rejected; black photos are refused. |
| `tests/web/offline.test.js` | The offline cache lists every file the app needs, and nothing that doesn't exist. |
| `tests/test_web_e2e.py`, real Chromium, 7 tests | The full check works end to end; **the browser's result equals Python's** for the same photo; **no console errors or CSP violations**; **no request leaves the site**; exactly one correct severity icon shows; the photo is deleted; Hindi works; dark mode works; bad files are refused; the **live camera** works (Chromium's fake camera) and switches off after the shot; settings refuse non-local addresses; a **hostile LLM reply is shown as text and never runs**; only numbers are sent to the LLM; the app **works in airplane mode**; the security headers are served. |
| `scripts/audit_accessibility.py` (axe-core) | **0 WCAG 2.2 A/AA violations** on every screen, light + dark, English + Hindi. |
| `.github/workflows/ci.yml` | Runs all of the above on every pull request. It also checks that `web/model.json` matches a freshly trained model. |

Bugs these tests caught during the build:
- **The green "✓" stayed visible on a Borderline result.** SVG elements have no `.hidden` property, so the icon never hid, which is exactly the false reassurance the research warns about. Fixed, and now tested.
- **The website model was out of date.** `web/model.json` came from a different training run than the official model. The CI check caught it.
- **Two accessibility findings:** an unlabelled hidden file input, and the demo banner outside page landmarks. Both fixed.
- **The CSP is working:** it blocked Playwright's own `eval`-based waiting code during testing. Good news for security; the tests now use CSP-safe waits.

---

## 7. Running and deploying

**Locally (same security headers as production):**
```bash
python scripts/serve_web.py               # http://localhost:8000
python scripts/serve_web.py --bind 0.0.0.0  # to open it from a phone on the same Wi-Fi*
```
*Phones need HTTPS for the live camera on a network address. On plain `http://<laptop-ip>` the app falls back to "Use phone camera app" / "Choose a photo", which still works. For the full experience, deploy (below) or use your Codespace's forwarded HTTPS port.

**After retraining the model** (e.g. on real data):
```bash
python src/progression.py --data <your labels.csv files>
python src/export_web_model.py   # updates web/model.json; the demo banner disappears for a real model
# bump VERSION in web/sw.js so phones fetch the new model
```

**Deploy options:**
| Host | Security headers | How |
|---|---|---|
| **Cloudflare Pages** (recommended) | ✅ all, from `web/_headers` | Connect the repo, build command: none, output directory: `web` |
| **Netlify** | ✅ all, from `web/_headers` | Connect the repo, publish directory: `web` |
| **GitHub Pages** | ⚠️ meta CSP only (no frame-ancestors / Permissions-Policy / nosniff) | Settings → Pages → Source: **GitHub Actions**; `.github/workflows/pages.yml` publishes `web/` on each push to `main` |

---

## 8. Using a local language model with the website

The "Explain in simple words" helper is **off by default** (Settings → turn on).

- **Site opened from `http://localhost:8000`:** works with Ollama out of the box. Ollama's default CORS settings allow `localhost` origins.
- **Site opened from the internet (e.g. `https://<you>.github.io`):**
  1. Start Ollama with your site allowed: `OLLAMA_ORIGINS=https://<you>.github.io ollama serve`. Use the exact origin, never `*`.
  2. Chrome 142+ asks once for permission to **"look for and connect to devices on your local network"**. Choose Allow.
  3. Safari has had bugs with https → localhost. Test it there, or use Chrome.
- **llama.cpp:** `llama-server -m model.gguf --port 8080 --cors-origins https://<you>.github.io`, then set the address to `http://localhost:8080/v1` in Settings.
- Only numbers are sent (Hb, range, cut-off, category, language), never the photo. Keep Ollama bound to `127.0.0.1` (the default).

---

## 9. Limits and next steps
1. **The model is trained on simulated photos.** The banner says so on every screen until a real-data model is exported.
2. **Hindi text** needs review by a native speaker / health worker.
3. **Voice guidance** (pre-recorded Hindi audio for each step) would help users who can't read well. Recommended by the research, not built yet.
4. **Blur detection** isn't implemented yet (darkness, brightness and glare are).
5. **Personal calibration** (one lab value improves accuracy a lot in Mannino's study) is a strong future feature.
6. **Safari** behaviour for the local language model and the live camera in installed apps should be tested on a real iPhone.

---

## 10. Sources

**UX:** Mannino et al. 2018 / Georgia Tech news (https://www.news.gatech.edu/2018/12/10/no-bleeding-required-anemia-detection-smartphone) · Springer Nature community post on the fingernail app (https://communities.springernature.com/posts/measuring-hemoglobin-levels-by-taking-pictures-of-fingernail-beds-with-a-smartphone) · Sanguina AnemoCheck (https://www.businesswire.com/news/home/20211206005205/en) · Purdue eyelid app (https://sicklecellanemianews.com/news/smartphone-app-may-help-assess-anemia-using-eyelid-pictures/) · EzeCheck (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10894012/) · Winton Centre on uncertainty and trust (https://wintoncentre.maths.cam.ac.uk/news/being-upfront-about-your-uncertainty-doesnt-necessarily-mean-you-lose-your-audiences-trust-new-paper-published) · Number lines for test results, JMIR 2018 (https://www.jmir.org/2018/3/e98/) · CDC Clear Communication Index (https://www.cdc.gov/ccindex/) · NHS service manual: numbers, care cards, typography (https://service-manual.nhs.uk) · GOV.UK question pages and form structure (https://design-system.service.gov.uk/patterns/question-pages, https://www.gov.uk/service-manual/design/form-structure) · Medhi et al., text-free UIs for low-literate users (https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/ToCHI2711_Medhi.pdf) · CHW app study, Chhattisgarh (https://www.sciencedirect.com/science/article/abs/pii/S107158191830048X) · CommCare low-literacy guidance (https://dimagi.atlassian.net/wiki/x/-jPKfw) · ImTeCHO (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6812744/) · UX4G typography (https://www.ux4g.gov.in/foundations/typography) · WCAG 2.2 (https://www.w3.org/TR/WCAG22/) · web.dev media capture (https://web.dev/articles/media-capturing-images) · Stanford Web Credibility (https://credibility.stanford.edu/research) · On-device privacy perception, CHI EA 2025 (https://nmsl.kaist.ac.kr/pdf/CHIEA25_VP.pdf)

**Security:** OWASP Secure Headers Project (https://owasp.org/www-project-secure-headers/) · OWASP cheat sheets: HTTP headers, CSP, DOM XSS, file upload (https://github.com/OWASP/CheatSheetSeries) · web.dev strict CSP (https://web.dev/articles/strict-csp) · MDN: secure contexts, mixed content, local network access, Trusted Types, createImageBitmap (https://github.com/mdn/content) · Chrome Local Network Access (https://developer.chrome.com/blog/local-network-access) · Chromium: meta CSP ignores frame-ancestors (https://codereview.chromium.org/1835463002) · WebKit bugs 279249 / 250776 / 215884 (https://bugs.webkit.org) · Ollama CORS defaults (https://github.com/ollama/ollama/blob/main/envconfig/config.go) · llama.cpp server (https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) · Cloudflare Pages headers (https://developers.cloudflare.com/pages/configuration/headers/) · Netlify headers (https://docs.netlify.com/manage/routing/headers/) · GitHub Pages has no custom headers (https://github.com/orgs/community/discussions/54257) · Workbox storage quota (https://developer.chrome.com/docs/workbox/understanding-storage-quota) · LG München Google Fonts ruling (https://www.ihk.de/bergische/recht-und-steuern/wettbewerbsrecht/google-fonts-5646176) · polyfill.io attack (https://www.bleepingcomputer.com/news/security/polyfillio-javascript-supply-chain-attack-impacts-over-100k-sites/)

Some sources were read via search summaries or mirrors because the build environment blocked direct access; the research agents flagged uncertain points, and they are marked as such above (e.g. Safari localhost behaviour).
