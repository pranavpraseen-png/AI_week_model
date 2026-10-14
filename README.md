# 🩸 AnaemiaLens

**Anaemia screening from a phone photo: SDG 3 (Good Health) + SDG 5 (Gender Equality).**

57% of Indian women aged 15–49 are anaemic (NFHS-5), and testing usually needs a needle or a device. AnaemiaLens estimates haemoglobin from a photo of a fingernail using **linear regression written from scratch (y = mx + b)**, checks it against WHO cut-offs, and uses a **free local LLM (Ollama / llama.cpp)** to explain the result in simple English or Hindi. It needs no hardware, works offline, and keeps data private.

> ⚠️ Screening estimate only, not a diagnosis. The included results come from **simulated** photos and test the code, not real-world accuracy. See CLAUDE.md for how to run on real data.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/make_simulated_data.py                          # simulated photos from 4 regions
python src/progression.py --data data/simulated/labels.csv # y = mx + b → ... → final model, with checks
python -m pytest -q                                        # 49 tests
npm test                                                   # JavaScript tests
streamlit run app.py                                       # demo app
```

## Website
A full mobile web app in `web/`: it runs the model **in the browser** (no server), works **offline**, in **English and Hindi**, with a strict security policy so the photo cannot leave the phone.
```bash
python scripts/serve_web.py     # http://localhost:8000
```
Research, security, design and every file: [`docs/03_website_research.md`](docs/03_website_research.md).

![Website result screen](docs/images/web_result.png)

## Desktop app
The same website as a program for **Windows, macOS and Linux** (`desktop/`, built with Electron). It shows the files in `web/` unchanged, with the same security headers, works offline, and may use only the camera.

- **Download:** open the repo's **[Releases](https://github.com/pranavpraseen-png/AI_week_model/releases)** page and pick the file for your computer:
  - **Chromebook** (Linux turned on in Settings → Advanced → Developers) or **Debian/Ubuntu:** the `.deb`. Use `amd64` for Intel/AMD chips and `arm64` for ARM chips (Settings → About ChromeOS → "Diagnostics" shows the CPU). Open it from the Files app → **Install with Linux**; AnaemiaLens then appears in the launcher.
  - **Any Linux, no install:** the `.AppImage` (`chmod +x` it, then double-click). Some systems need `libfuse2` first (`sudo apt install libfuse2`).
  - **Windows:** `…-Setup-….exe` (installer) or `…-Portable-….exe`. **Mac:** the `.dmg` (`arm64` for Apple chips, `x64` for Intel).
  - Not code-signed yet: Windows says "Windows protected your PC" (More info → Run anyway); macOS says "unidentified developer" (right-click the app → Open).
  - Every build is also kept for 30 days under **Actions → "Desktop app"** → a run → Artifacts. A maintainer makes a new release from that page: **Run workflow** with a version such as `v1.0.1`.
- **Run from the code** (Node 22):
  ```bash
  cd desktop
  npm install
  npm start            # open the app
  npm test             # 8 tests on the real app (Linux without a screen: xvfb-run -a npm test)
  npm run dist         # build an installer for this computer into desktop/dist/
  ```
How it is locked down, and why: [`docs/03_website_research.md` §12](docs/03_website_research.md#12-the-desktop-app-electron).

## Docs
- [`CLAUDE.md`](CLAUDE.md): the teaching guide (ML basics, the maths, local LLMs, running, presenting).
- [`docs/01_problem_selection.md`](docs/01_problem_selection.md): why this problem (need, competition, data).
- [`docs/02_full_build_explained.md`](docs/02_full_build_explained.md): every file and function, the full process, the formulas.
- [`docs/03_website_research.md`](docs/03_website_research.md): the website's UX and security research, design and code.

## How it works
```
photo → colour features (nail + surrounding skin) → Hb = m₁x₁ + … + m₇x₇ + b → WHO category → local LLM explanation
```
The key experiment: a model trained only on lighter-skinned regions badly overestimates Hb on darker skin (it misses anaemia). Adding skin-reference features and training on diverse regions fixes most of that. See `reports/progression_log.md` after running.

![Cross-region results](docs/images/cross_region.png)
