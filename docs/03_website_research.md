# The AnaemiaLens website: research, decisions and how it works

A usable MVP website for the anaemia check. It runs **entirely on the phone**, works **offline**, is available in **12 Indian languages** (English and Hindi built in, 10 more loaded when chosen), and is locked down so the photo **cannot** leave the device.

**Version 2** added an animated opening page, optional on-device accounts protected by a PIN, 10 more languages (including right-to-left Urdu) and a two-column layout for wide screens. All of that is explained in [§11](#11-version-2-the-opening-page-accounts-languages-and-landscape-layout); sections 1–10 describe the base app and have been corrected where version 2 changed them.

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
11. [Version 2: the opening page, accounts, languages and landscape layout](#11-version-2-the-opening-page-accounts-languages-and-landscape-layout)

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
| Low-literacy users in India find typing and dropdowns hard; picture + text works (Medhi et al., Microsoft Research; CHW studies in Chhattisgarh) | **No typing anywhere in a check.** Big tap targets with icons + words. Age is chosen from **5 age groups**, not typed. (Only the optional account asks for a name and a PIN.) |
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
| No accounts for emergent users | A check **never** needs sign-up or login. Version 2 adds **optional** accounts for people who want a history (§11.7); "Start a check" still skips them entirely. |
| ASHA (community health worker) workflow: screen many people in a row | **"Check another person"** jumps straight back to the first question; nothing from the previous person is kept. |
| WCAG 2.2: targets ≥ 24px (we use 48px+), visible focus, status messages, reduced motion | 48–80px targets, 3px focus rings, a `role="status"` region announces the result, and with reduced motion every animation shows its finished, still state (§11.6). |
| Dark mode: follow the system, check contrast in both themes | Full dark theme; **axe-core reports 0 violations** on every screen in both themes, in English and Hindi. |
| Credibility: say who made it, show honest accuracy and limits (Stanford Web Credibility) | `privacy.html`: who made it, data used, **honest accuracy (simulated, so real accuracy is not yet known)**, limits. |
| Avoid the generic "AI look": purple gradients, sparkles, three-card grids | No sparkles, no purple, no "AI-powered" wording. The few gradients on the opening page are blood-red or deep teal and carry meaning (§11.3). See §4. |

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
| Saved history read by someone else on the phone (version 2) | Accounts are optional. History is encrypted with **AES-256-GCM**; the key is made from the PIN with **PBKDF2-SHA256, 600,000 rounds** and is non-extractable; the PIN is never stored; growing waits after 5 wrong PINs; auto-lock. Honest limit: a short PIN can be brute-forced from a copy of the storage. | `js/accounts.js`, `js/account-ui.js`, §11.7 |
| Offline cache poisoning | The service worker only caches same-origin GET responses of type `basic`, never `localhost` LLM calls. The cache is versioned and old caches are deleted. | `sw.js` |

**The full header set** is in `web/_headers` (Netlify and Cloudflare Pages apply it). GitHub Pages cannot send custom headers, so each page also carries a `<meta>` CSP. `frame-ancestors`, `Permissions-Policy` and `nosniff` only work as real headers, which is why Netlify or Cloudflare Pages is the most secure place to host.

Not used, on purpose: `upgrade-insecure-requests`, which would break `http://localhost` calls in some browsers.

---

## 4. Visual design

The goal was "trustworthy health service", modelled on GOV.UK and NHS, not "tech demo".

- **Colour rules:** warm paper background (`#F7F3EC`) and near-black ink. **Teal is used only for actions**, and **green/amber/orange/red only for result severity**, so a button can never be confused with a warning.
- **Type:** *Fraunces* (a characterful serif, plus its italic for the opening headline) for English headings and the big number, *Noto Sans Devanagari* for body text, Hindi and Marathi, 19px body. All are self-hosted (about 166 KB total). The other Indian scripts and Urdu use the phone's own fonts (§11.8).
- **Illustrations:** simple line drawings (research: semi-abstract pictures work better than photos for low-literacy users), drawn as inline SVG.
- **Signature element:** the Hb number line, a visual you can't get from a template.
- **Not used:** sparkles, emoji, purple, "AI-powered" wording. Version 2's opening page does use a dark blood-red background, a red gradient inside the big "57%", a teal privacy band and frosted ("glass") buttons over the moving cells, so the buttons stay readable; the app screens after it keep the calm paper style.

Screenshots below are from version 1; the home screen is now the opening page described in §11.

| Home (version 1) | Confirm the nail | Result | Result (Hindi) |
|---|---|---|---|
| ![Home](images/web_home.png) | ![Confirm](images/web_confirm.png) | ![Result](images/web_result.png) | ![Hindi result](images/web_result_hindi.png) |

All screenshots (light/dark, English/Hindi, every screen) can be regenerated by the browser tests: `SCREENSHOT_DIR=shots python -m pytest tests/test_web_e2e.py`.

---

## 5. Every file, explained

```
web/
├── index.html            the whole app: every screen is a <section>, shown one at a time
├── privacy.html          privacy, accounts, languages, honest accuracy, limits, who made it
├── _headers              security headers for Netlify / Cloudflare Pages
├── manifest.webmanifest  makes it installable ("Add to home screen")
├── sw.js                 service worker: offline cache
├── model.json            the trained model (8 numbers + metadata), from src/export_web_model.py
├── css/styles.css        all styling, light + dark, every language, opening-page animations
├── fonts/                self-hosted fonts + their licences
├── icons/                app icons
└── js/
    ├── app.js            screen flow, questions, photo confirm, result rendering, settings
    ├── intro.js          the opening page: bloodstream, scroll story, reveals, chart (§11)
    ├── accounts.js       on-device accounts: PIN → key, encrypted history, wrong-PIN waits
    ├── account-ui.js     sign-in, create-account and "your checks" screens, auto-lock
    ├── features.js       photo pixels → 7 colour numbers (port of src/features.py)
    ├── model.js          y = m·x + b prediction, WHO cut-offs, severity, model validation
    ├── image.js          safe file checks, decoding, cropping, quality check
    ├── camera.js         live camera, guide square → photo pixels
    ├── explain.js        optional local-language-model explanation
    ├── i18n.js           every word of the interface in English and Hindi, + the language list
    ├── lang/             the other 10 languages, one file each (bn, mr, te, ta, gu, ur, kn, or, ml, pa)
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
- **Flow:** the first screen is the opening page (`home`, run by `intro.js`). `show(screen)` hides all other screens, moves focus to the new heading (so screen readers announce it), and uses `history.pushState` so the phone's **Back button** works. Going "back" into a deleted photo or a finished result is blocked.
- **Confirm screen:** draws the photo on a canvas, dims everything outside the measured area, and draws the nail square (solid) and skin frame (dashed). Tapping moves the square; the slider resizes it; the quality message updates live.
- **Result:** computes the features, the Hb and the category, **then deletes the photo** (`bitmap.close()`, canvas emptied). It renders the number, range, bands, icon, next steps and the equation in "How this number was worked out".
- **Borderline rule:** if the range crosses the cut-off and the category is none or mild, show "Borderline".
- **Settings:** language, plus the optional local language model (off by default). Saved in `localStorage` as plain preferences. Results are **never** saved in plain text: if someone is signed in, the finished check is added to their **encrypted** history (`accounts.saveCheck`, §11.7) and the result shows "Saved to …'s history, encrypted on this phone". Without an account nothing is saved, exactly as before.

### `js/i18n.js`
226 keys in English and Hindi (every element names its text with `data-i18n="key"`), plus the list of 12 languages and the loader for the other 10 (§11.8). A browser test switches through every available language and fails if any key shows up raw or any visible text is empty. **The Hindi should be reviewed by a native speaker / ASHA before real use, and so should the other 10 languages, which were AI-assisted translations.**

---

## 6. Testing: how we know it works

| Test | What it proves |
|---|---|
| `tests/test_web_parity.py` (+ `tests/web/parity.test.js`) | Browser and Python compute **identical features** (≤ 1e-9) and **identical Hb** (≤ 1e-6) on the same photos. |
| `tests/web/model.test.js` | WHO cut-offs and severity match Python; tampered models are rejected; black photos are refused. |
| `tests/web/offline.test.js` | The offline cache lists every file the app needs, and nothing that doesn't exist. |
| `tests/web/accounts.test.js` | Accounts: right PIN unlocks, wrong PIN refused; history unreadable without the key; entries older than a year dropped; bad names/PINs refused with a reason; waits after 5 wrong PINs; junk in storage ignored. |
| `tests/test_web_e2e.py`, real Chromium, 7 tests | The full check works end to end; **the browser's result equals Python's** for the same photo; **no console errors or CSP violations**; **no request leaves the site**; exactly one correct severity icon shows; the photo is deleted; Hindi works; dark mode works; bad files are refused; the **live camera** works (Chromium's fake camera) and switches off after the shot; settings refuse non-local addresses; a **hostile LLM reply is shown as text and never runs**; only numbers are sent to the LLM; the app **works in airplane mode**; the security headers are served. |
| `tests/test_web_e2e.py`, version 2 tests | A full account life cycle in a real browser (the PIN and the results never appear in storage); PIN mismatch and short PINs refused; the wait after too many wrong PINs; the bloodstream draws and moves; the scroll story goes from a pale nail and "Severe" to a red nail and "Healthy"; the 57% counts up; reduced motion shows everything at once; every available language translates the page and sets `dir` correctly; the two-column layout on wide screens. See §11.10. |
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
1. **The model is trained on simulated photos.** The banner says so on every screen (on the opening page, as a note under the buttons) until a real-data model is exported.
2. **Translations:** the Hindi needs review by a native speaker / health worker, and the other 10 languages were written with AI-assisted translation and have **not** been reviewed by native speakers yet (§11.8).
3. **Voice guidance** (pre-recorded Hindi audio for each step) would help users who can't read well. Recommended by the research, not built yet.
4. **Blur detection** isn't implemented yet (darkness, brightness and glare are).
5. **Personal calibration** (one lab value improves accuracy a lot in Mannino's study) is a strong future feature.
6. **Safari** behaviour for the local language model and the live camera in installed apps should be tested on a real iPhone.
7. **Accounts** live in one browser on one phone: no backup, no transfer to a new phone, and a forgotten PIN cannot be reset. A short PIN can be brute-forced by someone who copies the phone's storage (§11.7).

---

## 10. Sources

**UX:** Mannino et al. 2018 / Georgia Tech news (https://www.news.gatech.edu/2018/12/10/no-bleeding-required-anemia-detection-smartphone) · Springer Nature community post on the fingernail app (https://communities.springernature.com/posts/measuring-hemoglobin-levels-by-taking-pictures-of-fingernail-beds-with-a-smartphone) · Sanguina AnemoCheck (https://www.businesswire.com/news/home/20211206005205/en) · Purdue eyelid app (https://sicklecellanemianews.com/news/smartphone-app-may-help-assess-anemia-using-eyelid-pictures/) · EzeCheck (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10894012/) · Winton Centre on uncertainty and trust (https://wintoncentre.maths.cam.ac.uk/news/being-upfront-about-your-uncertainty-doesnt-necessarily-mean-you-lose-your-audiences-trust-new-paper-published) · Number lines for test results, JMIR 2018 (https://www.jmir.org/2018/3/e98/) · CDC Clear Communication Index (https://www.cdc.gov/ccindex/) · NHS service manual: numbers, care cards, typography (https://service-manual.nhs.uk) · GOV.UK question pages and form structure (https://design-system.service.gov.uk/patterns/question-pages, https://www.gov.uk/service-manual/design/form-structure) · Medhi et al., text-free UIs for low-literate users (https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/ToCHI2711_Medhi.pdf) · CHW app study, Chhattisgarh (https://www.sciencedirect.com/science/article/abs/pii/S107158191830048X) · CommCare low-literacy guidance (https://dimagi.atlassian.net/wiki/x/-jPKfw) · ImTeCHO (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6812744/) · UX4G typography (https://www.ux4g.gov.in/foundations/typography) · WCAG 2.2 (https://www.w3.org/TR/WCAG22/) · web.dev media capture (https://web.dev/articles/media-capturing-images) · Stanford Web Credibility (https://credibility.stanford.edu/research) · On-device privacy perception, CHI EA 2025 (https://nmsl.kaist.ac.kr/pdf/CHIEA25_VP.pdf)

**Security:** OWASP Secure Headers Project (https://owasp.org/www-project-secure-headers/) · OWASP cheat sheets: HTTP headers, CSP, DOM XSS, file upload (https://github.com/OWASP/CheatSheetSeries) · web.dev strict CSP (https://web.dev/articles/strict-csp) · MDN: secure contexts, mixed content, local network access, Trusted Types, createImageBitmap (https://github.com/mdn/content) · Chrome Local Network Access (https://developer.chrome.com/blog/local-network-access) · Chromium: meta CSP ignores frame-ancestors (https://codereview.chromium.org/1835463002) · WebKit bugs 279249 / 250776 / 215884 (https://bugs.webkit.org) · Ollama CORS defaults (https://github.com/ollama/ollama/blob/main/envconfig/config.go) · llama.cpp server (https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) · Cloudflare Pages headers (https://developers.cloudflare.com/pages/configuration/headers/) · Netlify headers (https://docs.netlify.com/manage/routing/headers/) · GitHub Pages has no custom headers (https://github.com/orgs/community/discussions/54257) · Workbox storage quota (https://developer.chrome.com/docs/workbox/understanding-storage-quota) · LG München Google Fonts ruling (https://www.ihk.de/bergische/recht-und-steuern/wettbewerbsrecht/google-fonts-5646176) · polyfill.io attack (https://www.bleepingcomputer.com/news/security/polyfillio-javascript-supply-chain-attack-impacts-over-100k-sites/)

Some sources were read via search summaries or mirrors because the build environment blocked direct access; the research agents flagged uncertain points, and they are marked as such above (e.g. Safari localhost behaviour).

---

## 11. Version 2: the opening page, accounts, languages and landscape layout

Version 2 keeps everything in sections 1–10 (same model, same privacy, same security rules) and adds four things:

| What | In one line | Files |
|---|---|---|
| **Opening page** | An animated page that explains the project before the check starts: a live bloodstream, a scroll story where the nail turns red as haemoglobin rises, numbers, the regression line drawing itself, and the privacy promise. | `js/intro.js`, "Opening page" in `css/styles.css`, the `home` section of `index.html` |
| **Accounts (optional)** | Keep your own history, or a health worker's daily log, encrypted on this phone with a key made from a PIN. | `js/accounts.js`, `js/account-ui.js`, "Accounts" in `css/styles.css` |
| **12 languages** | English and Hindi built in; Bengali, Marathi, Telugu, Tamil, Gujarati, Urdu (right to left), Kannada, Odia, Malayalam and Punjabi loaded only when chosen. | `js/i18n.js`, `js/lang/*.js`, "Languages" in `css/styles.css` |
| **Landscape layout** | On wide screens the question sits on the left and the answers on the right. | "App screens" in `css/styles.css`, `screen-head` / `screen-body` in `index.html` |

The model, the maths, the CSP and "the photo never leaves the phone" did not change.

### 11.1 The opening page, top to bottom

1. **Hero:** a dark blood-red screen with red blood cells drifting across it. The headline "Read your blood / through a fingernail." slides in word by word. Below it: one sentence, "Start a check", "Sign in", and (while the model is simulated) a yellow note saying it is a demo model. That note replaces the usual demo banner on this page, so the simulated-data warning is still visible.
2. **Scroll story:** a drawing of a finger stays still in the middle of the screen while you scroll. As you scroll, haemoglobin rises from 6.0 to 16.0 g/dL, the nail goes from pale to red, a dot moves along a coloured WHO scale and a label changes: Severe → Moderate → Mild → Healthy (WHO bands for a non-pregnant woman: below 8, 8–11, 11–12, 12 and over).
3. **Why it matters:** "57%" of women aged 15–49 in India have anaemia, and 59% of girls aged 15–19 (NFHS-5). The numbers count up when they appear.
4. **How it works:** dots pop onto a chart, the best-fit line draws itself, and "Hb = m × redness + b" appears, next to four short steps.
5. **Privacy:** a phone in the middle; dashed lines try to leave it towards a document, a cloud and a picture, and red crosses stop each one.
6. **Accounts:** two cards ("For yourself", "For health workers") with "Create an account" and "Sign in".
7. **Final call:** "Ready? It takes about a minute." and "Start a check" again.

The chart on this page is an **illustration**: its 26 dots are generated by the code around the hand-worked example line Hb = 19.4 × redness + 2.28 (CLAUDE.md §3.3). They are not real patients and not the model's training data. If a judge asks, say so. (The screen-reader label of the chart, `howi.chart` in `i18n.js`, currently says "Dots are photos with lab-measured haemoglobin"; it should be reworded to say the dots are an example.)

### 11.2 Every animation, how it works, and where the idea comes from

| # | What you see | How it is built | Where the technique comes from |
|---|---|---|---|
| 1 | **Red blood cells drifting** behind the headline, big and sharp up close, small and faint far away | A `<canvas>` with the 2D API. Each cell is drawn **once** into a small 160 × 160 canvas (a "sprite"): a radial gradient with a darker rim, a **paler centre** and a soft highlight. Three sprites in three shades are made at start. Every frame (`requestAnimationFrame`), each cell's position is updated and its sprite is copied with `drawImage`. Each cell has a depth `z` (0.25–1.2) that sets its size, speed and transparency. Cells are sorted far-to-near, so near ones are painted on top. A cell that leaves on the right comes back on the left at a new height. | **Particle systems**, a classic computer-graphics and game technique (William Reeves, "Particle Systems", 1983, made for the "Genesis effect" in *Star Trek II*). **Pre-rendering** repeated shapes to an off-screen canvas is a standard canvas speed-up (MDN, "Optimizing canvas"). Drawing far things first is the **painter's algorithm**; depth-based speed is **parallax**, as in side-scrolling games. The cell's shape comes from **biology**: a red blood cell is a biconcave disc, thinner in the middle, so under a microscope its centre looks paler ("central pallor"). |
| 2 | Cells **tumble** like coins and **sway** | Each cell is rotated (`spin`) and squashed vertically by `0.32 + 0.68 × |cos(tumble)|`, so a disc seen edge-on looks thin. A slow sine wave moves cells up and down, like blood in a capillary. | Basic trigonometry used in game animation: a circle squashed by cos(angle) is how a turning disc looks in 2D. |
| 3 | Cells **move away from your finger or mouse** | On `pointermove`, cells closer than about 148 px (distance² < 22,000) get pushed away, harder the closer they are. The push decays each frame (velocity × 0.94), so they drift back into the flow. | A simple **repulsion force with damping**, common in particle demos and games. |
| 4 | The **headline appears word by word**, each word sliding up from behind an invisible edge | `splitWords()` wraps every word in two `<span>`s. The outer one has `overflow: hidden` (the "mask"). The inner one starts at `transform: translateY(105%) rotate(4deg)` and transitions to `none` over 1.1 s. Each word gets a CSS custom property `--i` (its number), and the delay is `--i × 70 ms` (+ 260 ms for the second line), so the words arrive one after another. The words stay real text (not an image), so translation, search and screen readers still work. | **Word-by-word mask reveals** are common on modern editorial and design-agency sites (tools like GreenSock's SplitText made them popular; here it is done by hand with no library). The curve `cubic-bezier(0.16, 1, 0.3, 1)` is the "ease-out-expo" curve from Robert Penner's easing equations. |
| 5 | The sentence, buttons and demo note **fade up** after the headline | CSS `opacity` + `translateY(14px)` transitions with fixed delays (750, 900, 1050 ms), started by adding the class `is-in` on the next animation frame. | Ordinary CSS transitions; the stagger makes the eye read headline → sentence → button. |
| 6 | A **"Scroll" cue** whose line keeps growing and fading | CSS `@keyframes cue`: `scaleY(0 → 1)` then `opacity → 0`, every 2.2 s, `transform-origin: top`. Tapping it smooth-scrolls to the story. | A common "scroll down" hint on long-form pages. |
| 7 | The **top bar** floats see-through over the hero, then turns solid | The same `IntersectionObserver` that watches the hero toggles a `past-hero` class on `<body>`; CSS transitions the colours over 300 ms and adds `backdrop-filter: blur()`. | Standard "sticky header that changes on scroll", done with an observer instead of a scroll listener. |
| 8 | **Scroll story:** the finger stays put while you scroll; the nail colour, the Hb number, the dot on the scale and the band label all follow your scroll | The `.story` section is 320% of the screen height (280% on phones). Inside it, `.story-stage` is `position: sticky; top: 0; height: 100svh`, so it stays pinned while the tall section scrolls past. On scroll, the code works out **progress p** = how far through the section you are (0 to 1), and sets **Hb = 6 + 10p**. `nailColor(hb)` mixes linearly between a pale nail `rgb(238, 214, 205)` and a red nail `rgb(214, 112, 112)` (the **same colours `src/make_simulated_data.py` uses**), and sets the SVG nail's `fill`. The scale marker moves to `(Hb − 5)/12` of the width. `storyBand(hb)` picks the WHO band and the label changes only when the band changes. The scroll listener is `passive` and runs at most once per frame (it queues one `requestAnimationFrame`). | **Scrollytelling**: a graphic that stays pinned while text or data changes with scroll. Popularised by news sites, most famously *The New York Times*' "Snow Fall" (2012), and developed further by visual-essay sites such as **The Pudding**, which wrote openly about the "sticky graphic" pattern. Mike Bostock's essay "How To Scroll" (2014) discusses when scroll-driven graphics work. CSS `position: sticky` now does the pinning without a library. |
| 9 | The **band label** changes colour; the hint "Keep scrolling" **fades out** | The label's colours come from `[data-band="…"]` rules with a 250 ms colour transition. The hint's `opacity` is `calc(1 − p × 2.5)`, driven by the same `--p` custom property. | A CSS custom property set from JavaScript, then used in CSS maths (`calc`). |
| 10 | A **dashed frame "marches"** around the nail | SVG `stroke-dasharray: 14 10` (14 px dash, 10 px gap) and `@keyframes march` moving `stroke-dashoffset` to −24 (one dash + one gap) every 1.4 s, `linear`, forever, so the loop is seamless. | The **"marching ants"** selection border that image-editing programs have used since early Mac paint programs. |
| 11 | Sections **fade up** as they scroll into view, one child after another | Each section has `data-reveal`. One `IntersectionObserver` (threshold 0.25) adds `is-visible` the first time a quarter of it is on screen, then stops watching it. CSS fades each child up from `translateY(28px)` with delays 0, 90, 180, 270, 360 ms (`:nth-child`). | The **"reveal on scroll"** pattern, once done with scroll-event libraries; browsers have offered the `IntersectionObserver` API since about 2016, which tells the page when something enters the screen without checking on every scroll. |
| 12 | **57%, 59%, 0 and 1 count up** from zero | `countUp()`: `requestAnimationFrame` for 1.6 s, value = target × (1 − (1 − t)³) (an "ease-out cubic" curve: fast, then slowing down). The real number is already in the HTML, so without JavaScript it is still right. | A common infographic/dashboard effect; the curve is one of Robert Penner's easing equations. |
| 13 | The big **"57%" is filled with a pale-pink-to-deep-red gradient** | `background: linear-gradient(…)` + `background-clip: text` + `color: transparent`: the gradient shows only through the letter shapes. | **Gradient text** with `background-clip: text`, which started as a WebKit-only feature and is now standard CSS. |
| 14 | **Dots pop onto the chart** one by one, slightly overshooting | The 26 dots come from a seeded pseudo-random generator (`seed × 16807 mod (2³¹ − 1)`, the Park–Miller "minimal standard" generator), so the picture is the same every time. Each `<circle>` gets `--i`, and CSS transitions `scale(0) → none` with delay `--i × 45 ms` and the springy curve `cubic-bezier(0.34, 1.56, 0.64, 1)` ("ease-out-back", which goes past 1 and settles back). | A **scatter plot with a best-fit line**: least squares goes back to Legendre (1805) and Gauss; the word "regression" comes from Francis Galton (1880s). The springy curve is another Penner easing. |
| 15 | **The line draws itself**, then the formula appears | The `<line>` has `stroke-dasharray: 720; stroke-dashoffset: 720` (one dash longer than the line, pushed fully out of view). When the section is visible, `stroke-dashoffset` transitions to 0 over 1.5 s after a 1.5 s delay, so the line seems to be drawn from left to right. The formula fades in at 2.6 s. | **SVG line drawing with `stroke-dashoffset`**, a well-known technique described by Jake Archibald ("Animated line drawing in SVG", 2013) and on CSS-Tricks ("How SVG Line Animation Works"). |
| 16 | **Privacy picture:** dashed lines flow out of the phone, then a red cross stops each one | Each line fades in (`@keyframes ray`) and its dashes keep flowing (`@keyframes flow`, `stroke-dashoffset` → −30), staggered by 150 ms. The crosses scale in with the springy curve at 1.1, 1.3 and 1.5 s. | Dashed moving lines are the usual way network diagrams show data flowing; the crosses show the CSP blocking it (§3). |

Not animated, but new: a **3-part progress bar** above "Step 1 of 3" on each question screen (a `::before` element with a gradient fill and a repeating mask that cuts it into three segments; `--fill` is ⅓, ⅔ or 1). The words "Step 1 of 3" stay, so the bar is never the only signal.

### 11.3 Why each animation is about the subject, not decoration

| Animation | What it teaches |
|---|---|
| Bloodstream | Haemoglobin lives inside red blood cells. The paler centre of each cell is the same "pallor" idea the app measures; in iron-deficiency anaemia that pale centre gets bigger (doctors call the cells "hypochromic"). |
| Cells avoid your finger | Invites the visitor to touch the screen, which is what they'll do next with the camera. |
| Word-by-word headline | Slows the reader down on the one sentence that explains the whole idea. |
| Scroll story | The core science in one gesture: **more haemoglobin → redder nail bed**. The colours are the same as our simulated photos, and the bands are the real WHO cut-offs, so the story is the model's own logic, not a cartoon. |
| Marching frame | Matches the guide square on the camera screen: "this square is what we measure". |
| Counting numbers and red "57%" | Makes the scale of the problem (SDG 3 and SDG 5) land before the visitor is asked to do anything. |
| Dots, then line, then formula | Shows supervised learning in the order it happens: examples first, then the best line through them, then the equation y = mx + b. |
| Privacy rays and crosses | Shows what the CSP does: requests to anywhere else are blocked by the browser. |

### 11.4 Performance: why it stays smooth on a cheap phone

- **The bloodstream only runs when you can see it.** An `IntersectionObserver` stops the loop when the hero scrolls off screen; `visibilitychange` stops it when the tab or app is in the background; and `pause()` stops it when you leave the home screen for a check. No hidden work drains the battery.
- **Capped cell count:** one cell per 11,000 px² of screen, never fewer than 36 or more than 150.
- **Capped pixel ratio:** the canvas uses at most 1.5× the screen's CSS pixels on narrow screens (< 700 px) and 2× on wider ones, even if the phone reports 3× or more. Drawing 9× the pixels (3 × 3) for moving blobs would waste battery for no visible gain.
- **Sprites, not live gradients:** building a radial gradient is expensive; copying a ready-made picture with `drawImage` is cheap. Only three sprites are ever made.
- **Capped time step:** each frame moves cells by at most 0.05 s worth, so after a stutter they don't jump across the screen.
- **Scroll work once per frame:** the story's scroll handler is `passive` and batches updates into one `requestAnimationFrame`.
- **CSS does the rest:** reveals, the word slide, the line drawing and the dots are CSS transitions on `transform` and `opacity` (or SVG stroke properties), which browsers handle efficiently.

### 11.5 What changed in the security picture

Nothing is loaded from outside: the canvas, sprites, SVG and fonts are all made or stored locally, so the CSP is unchanged. The new scripts set text with `textContent` only (`splitWords` builds `<span>`s with `createElement`), and the per-word delay is set with `style.setProperty("--i", …)`, which the CSP allows, unlike a `style=""` attribute in the HTML. Language files are same-origin JavaScript modules, which `script-src 'self'` already allows.

### 11.6 Accessibility and "reduce motion"

Some people get dizzy or sick from movement on screen, and phones have a "reduce motion" setting for them (WCAG 2.2 success criterion 2.3.3, "Animation from Interactions").

- `intro.js` reads `matchMedia("(prefers-reduced-motion: reduce)")`. If it's on, the bloodstream draws **one still frame** and never starts its loop, all sections are marked visible straight away, and the numbers show their final value.
- `styles.css` has a reduced-motion block that forces the **finished state** of every effect: words in place, sections visible, dots shown, line drawn (`stroke-dashoffset: 0`), formula and privacy lines visible, and the marching frame and scroll cue stopped. The older global rule also switches off every other animation and transition.
- The scroll story still follows your scroll with reduce motion on, because you are the one moving it; it only changes colours and numbers, and the marching frame stops.
- A browser test opens the page with reduce motion on and checks that every section is visible without scrolling.
- The bloodstream canvas and the decorative drawings are `aria-hidden`, so screen readers skip them. The story's band label is a polite live region, and it only changes when the band changes (three times over the whole story), so screen-reader users hear "Moderate anaemia" etc. without being flooded.

### 11.7 Accounts without a server

**Why accounts at all?** Two real needs came up: a woman who wants to see whether her haemoglobin is improving after starting iron-rich food, and a health worker (ASHA) who screens many people at a camp and wants a count of who needs a blood test. Both need **history**, and history needs somewhere to live. Accounts stay **optional**: "Start a check" never asks you to sign in, and without an account nothing is saved, exactly as in version 1.

**Why no server?** A server would mean a password database that can leak, health data in someone's cloud, hosting costs, and an internet connection in places that often don't have one. Keeping everything on the phone keeps the version 1 promise: nothing leaves the device.

#### Threat model: what we protect against, and what we don't

| Threat | Protected? | How |
|---|---|---|
| Someone else on a **shared family phone** opens the app and reads your history | **Yes** | The history is encrypted; without the PIN it is random-looking bytes. |
| Someone **guesses PINs in the app** | **Slowed** | After 5 wrong PINs the waits grow: 30 s, 60 s, 2 min, 4 min … up to 1 hour per try. |
| You leave the app **open and walk away** | **Yes** | It locks after 10 minutes without a tap or key press, and when you come back after more than 5 minutes in the background. Locking throws the key away. |
| A **server or cloud breach** | **Nothing to breach** | There is no server and no copy anywhere else. |
| Someone **copies the phone's storage** (developer tools, a backup, a stolen unlocked phone) and tries every PIN on their own computer | **No, for short PINs** | The waits are stored with the account, so a copy doesn't have them. A 4-digit PIN has only 10,000 possibilities; even at 600,000 rounds each, an ordinary computer gets through them in minutes to about an hour. 6 digits takes 100× longer, 8 digits 10,000× longer. That is why the app says "use 6 digits or more". |
| Someone with the storage sees **that** you have an account | **Yes, they can see it** | The account name, its type, and the wrong-PIN counter are stored unencrypted so the sign-in screen can list accounts. The name field asks for a nickname, and that's all it needs. |

#### Design, step by step

1. **Create:** you type a name (up to 40 characters), choose "For yourself" or "For health workers", and a PIN of 4–8 digits, twice.
2. **PIN → key:** the browser's built-in Web Crypto API runs **PBKDF2 with SHA-256, 600,000 times**, mixing the PIN with a random 16-byte **salt** (different for every account). The result is an **AES-256-GCM key**.
   - *Why 600,000?* It is the figure the OWASP Password Storage Cheat Sheet recommends for PBKDF2-SHA256. Each guess costs a noticeable fraction of a second on a phone, which you notice once at sign-in, but an attacker pays it 10,000 or 1,000,000 times.
   - *Why a salt?* So two people with the same PIN get different keys, and an attacker can't pre-compute a table of keys.
   - *Why PBKDF2 and not something newer?* It is built into every browser's Web Crypto API. Newer recipes (like Argon2) would need a third-party library, which breaks our "no third-party code" rule (§3).
   - The iteration count is saved with each account, so it can be raised later without locking out older accounts.
3. **Non-extractable key:** the key is created with `extractable: false`. JavaScript can ask the browser to encrypt or decrypt with it, but can never read the key's bytes, not even our own code. It exists only in memory while you are signed in.
4. **The verifier:** at creation the app encrypts a known sentence (`"anaemialens-account-v1"`) and stores the result as `check`. To sign in, it makes a key from the typed PIN and tries to decrypt `check`. **AES-GCM is "authenticated" encryption**: with the wrong key it refuses to decrypt at all (instead of producing garbage), so a wrong PIN simply fails, and any tampering with stored data is detected. The PIN itself is never stored anywhere; the input box is emptied straight after.
5. **Encrypted history:** each finished check adds an entry: **time, Hb estimate, low and high of the range, the healthy level (cut-off), the category, sex and age group**. Never a photo, never the name of the person checked. The whole list is encrypted again with a **fresh random 12-byte IV** every time (reusing an IV with the same key would weaken AES-GCM). Entries older than a year are dropped.
6. **Storage:** all accounts are one JSON list in `localStorage` under `anaemialens.accounts`. One account looks like this (values shortened):
   ```json
   { "v": 1, "id": "k3Jx…", "name": "Asha", "type": "worker",
     "salt": "q9F…", "iterations": 600000,
     "check":   { "iv": "…", "data": "…encrypted…" },
     "history": { "iv": "…", "data": "…encrypted…" },
     "failures": 0, "waitUntil": 0 }
   ```
   When loading, anything that doesn't have this shape is ignored, so junk in storage can't break the app.
7. **Two kinds of account:**
   - **Personal:** "checks saved", "latest estimate", a **trend chart** of the last 20 checks with your healthy level as a dashed line (once there are 2 or more), and your last 50 checks.
   - **Health worker:** **today's checks** only, "checked today" and "need a blood test" (every result except "no sign of anaemia"), with age group and sex but **no names**. The worker taps "Check another person" between people as before.
8. **Forgot PIN:** it cannot be reset, because the PIN *is* the key. The only way out is to delete that account and its history and make a new one.
9. **Delete:** "Delete this account" asks twice ("Tap again to delete for good"), then removes it from storage. "Clear history" empties the history but keeps the account.

**Limits to say out loud:** a short PIN can be brute-forced by someone who copies the storage (above); there is no backup or transfer to a new phone; clearing the browser's site data deletes all accounts; and some browsers delete a website's stored data after a period without use (Safari is known to do this for sites that aren't added to the home screen), so installing the app to the home screen is safer.

### 11.8 Languages

**The 12 languages:** English, Hindi, Bengali, Marathi, Telugu, Tamil, Gujarati, Urdu, Kannada, Odia, Malayalam and Punjabi, which together cover most people in India.

- **Built in vs on demand:** English and Hindi are inside `i18n.js`. The other 10 are separate files in `web/js/lang/<code>.js`, each exporting one object of strings. `loadLanguage(code)` fetches a file with `import()` **only when someone chooses that language**, so nobody downloads ten languages they don't read.
- **Choosing:** on the first visit the app picks the first of the browser's preferred languages that it knows (`navigator.languages`), otherwise English, and remembers your choice. The globe button opens a grid with every language written **in its own script** (বাংলা, தமிழ், اردو …). Each button carries its own `lang` and `dir` attributes, so screen readers pronounce it correctly and Urdu shows right-to-left even inside the English page. Settings has the same list.
- **Fallbacks:** if a key is missing in a language, that string shows in English. If you are offline and a language has never been downloaded, the app falls back to English instead of breaking. Each language file must be listed in `FILES` in `sw.js` so it is cached for offline use (CLAUDE.md rule 8).
- **Fonts and spacing:** Hindi and Marathi use the self-hosted Noto Sans Devanagari. The other scripts use the phone's own fonts (most Android phones ship fonts for Indian scripts), which keeps the download small. Indian scripts get `line-height: 1.8` because their vowel signs reach above and below the line; Urdu gets 2.1 and prefers a Nastaliq font if the phone has one. Fraunces only has Latin letters, so every non-English language uses its own bold body font for headings.
- **Right to left (Urdu):** `applyLanguage()` sets `<html dir="rtl">`, so text, grids and flex rows flip automatically. A few things are fixed by hand in CSS: coloured side borders on the verdict and alerts move to the right; list indents and the privacy ticks move to the right; the back arrow "←" is mirrored; and the hero's dark shade is mirrored so it stays behind the text. **Numbers do not flip:** the Hb scale, the story scale, the big result number, the formula and the PIN box stay `direction: ltr`, because a number line runs low → high from left to right, and Urdu writes numbers left to right anyway.
- **Honest note on quality:** the English is the original. The Hindi was written for the app but has not yet been checked by a native-speaking health worker. **The other 10 languages were written with AI-assisted translation and have NOT been reviewed by native speakers.** Health wording matters ("screening, not diagnosis", "get a blood test"), so each language needs a native speaker, ideally a health worker, to review it before real use. The privacy page says this too.
- **Test:** a browser test opens the language picker, checks there are exactly 12 options, then switches to every language whose file exists and fails if `<html lang>` or `dir` is wrong, if any visible element is empty, or if a raw key like `story.title` leaks onto the page.

### 11.9 Landscape layout

Every app screen (all screens except the opening page) is split into two parts in `index.html`:
- `screen-head`: Back button, step and progress bar, the question (`h1`) and the "why" sentence;
- `screen-body`: the answers, form, photo or result details.

**On a phone** (under 1000 px wide) they stack: question on top, answers below, as in version 1.

**On a wide screen** (1000 px or more: a laptop, a tablet held sideways, or a projector at a judging table) each screen becomes a CSS grid with two columns (0.85 : 1.15). The question goes on the left in a much larger heading and stays put (`position: sticky`) while the right side scrolls. Answer buttons go into two columns and get taller; the four photo tips become a 2 × 2 grid; the camera view becomes 4 : 3; on the result screen the result card sits on the left and "What to do next" on the right. The page width is capped at 1120 px so lines don't get too long to read.

*Why:* a single phone-width column on a laptop leaves most of the screen empty and pushes the buttons below the fold. Question-left, answers-right reads like a paper form and keeps everything in view. A browser test checks both layouts: side by side at 1440 × 900, stacked at 390 × 844.

App screens also got a quiet warm background (two very soft radial gradients over the paper colour) so they feel connected to the opening page without its drama.

### 11.10 How version 2 is tested

| Test | What it proves |
|---|---|
| `tests/web/accounts.test.js` (Node) | Create and unlock; wrong PIN refused; history can't be read without the key; entries older than a year are dropped; bad name, type and PIN are refused with a reason; waits start after 5 wrong PINs and grow; accounts are saved, listed and deleted, and junk in storage is ignored. (These tests use 1,000 rounds to run fast; the app uses 600,000.) |
| `test_account_full_lifecycle` (real browser) | Create a health-worker account → do a check → it appears in the history → **the PIN, the Hb value and the category never appear in storage** → lock → a wrong PIN is refused → the right PIN opens the same history → clear → delete (asks twice) → storage is empty. |
| `test_account_pin_mismatch_and_short_pin_are_refused`, `test_too_many_wrong_pins_make_you_wait` | Different PINs and too-short PINs create nothing; after 5 wrong PINs even the right PIN must wait. |
| `test_opening_page_animates_and_story_follows_scroll` | The bloodstream canvas is drawn and changes over time; the story starts pale at ≤ 7 g/dL with "Severe" and ends red at ≥ 15 g/dL with "Healthy"; "57%" counts up and finishes on 57%. |
| `test_reduced_motion_shows_everything_without_scrolling` | With reduce motion on, every section is visible straight away. |
| `test_every_available_language_translates_the_page` | 12 languages offered; each available one sets `lang` and `dir` correctly and leaves no raw keys or empty text. |
| `test_wide_screens_put_question_and_answers_side_by_side` | Two columns at 1440 px wide, stacked at 390 px. |

Every browser test also fails on any console error, CSP violation or request that leaves the site.

### 11.11 Sources for version 2

Named in the text above and listed here without links where we did not check an exact address:
- William T. Reeves, "Particle Systems — A Technique for Modeling a Class of Fuzzy Objects", ACM SIGGRAPH / Transactions on Graphics, 1983.
- MDN Web Docs, "Optimizing canvas" (pre-rendering to an off-screen canvas) and the `IntersectionObserver`, `requestAnimationFrame`, `position: sticky`, `background-clip` and `prefers-reduced-motion` reference pages (https://github.com/mdn/content).
- *The New York Times*, "Snow Fall: The Avalanche at Tunnel Creek" (2012); The Pudding's writing on scrollytelling and sticky graphics; Mike Bostock, "How To Scroll" (2014).
- Jake Archibald, "Animated line drawing in SVG" (2013); CSS-Tricks, "How SVG Line Animation Works".
- Robert Penner's easing equations (the source of named curves such as ease-out-expo and ease-out-back).
- S. K. Park and K. W. Miller, "Random number generators: good ones are hard to find", *Communications of the ACM*, 1988 (the 16807 generator).
- OWASP Password Storage Cheat Sheet (PBKDF2-HMAC-SHA256 at 600,000 iterations) (https://github.com/OWASP/CheatSheetSeries).
- W3C Web Cryptography API (PBKDF2, AES-GCM, non-extractable keys); NIST SP 800-38D (AES-GCM, why an IV must never repeat with the same key).
- WCAG 2.2 success criterion 2.3.3, Animation from Interactions (https://www.w3.org/TR/WCAG22/).
- Red blood cell shape and central pallor: any standard haematology textbook (biconcave disc; enlarged central pallor in hypochromic, iron-deficient cells).
- Anaemia figures: National Family Health Survey 5 (2019–21), Government of India.
