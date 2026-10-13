# CLAUDE.md — AnaemiaLens (AI Week project, SDG 3 + SDG 5)

This file has two parts:
- **Part A** is short instructions for Claude Code when it works in this repo.
- **Part B** is the teaching guide: everything you need to understand, run, improve and present this project.

The full code walkthrough is in [`docs/02_full_build_explained.md`](docs/02_full_build_explained.md). Why we chose this problem is in [`docs/01_problem_selection.md`](docs/01_problem_selection.md). The website (research, security, design, every file) is in [`docs/03_website_research.md`](docs/03_website_research.md).

---

# Part A — Instructions for Claude Code

**Project:** screen for anaemia from a phone photo of a fingernail (or eyelid/palm). Colour features → **linear regression written from scratch (y = mx + b)** → haemoglobin estimate → WHO category → a free **local LLM** (Ollama / llama.cpp) explains it. The **website** (`web/`) runs the same model entirely in the browser: no server, offline, English + Hindi.

**The user is a student learning ML for an AI Week event.** Explain changes simply, show the "why", and keep the code readable for a beginner.

Rules:
1. **Keep the regression from scratch** (`src/linear_regression.py`). Do not swap in scikit-learn or a neural network; y = mx + b is the point of the project. Extra models may be added only *alongside* it, for comparison.
2. **The LLM never estimates haemoglobin.** It only explains a number produced by the regression model. Keep the safety rules in `SYSTEM_PROMPT` (screening-only, blood-test advice, no drug names or doses).
3. **Simulated data must always be labelled as simulated** in outputs, docs and slides. Never present simulated metrics as real accuracy.
4. **Every change keeps the tests green:** `python -m pytest -q` (49 tests, incl. real-browser tests), `npm test` (JavaScript), and `python src/progression.py --data data/simulated/labels.csv` (all checks PASS). Add a test for any new function.
5. When the user downloads a real dataset, inspect its folder and spreadsheet first, then adapt `src/prepare_dataset.py` (or add a small dataset-specific converter) so it produces `labels.csv` with `image, hb, sex, age, region[, mask]`.
6. Scripts in `src/` import each other by plain module name (`from features import ...`). Run them from the repo root: `python src/<script>.py`.
7. When code changes, update `docs/02_full_build_explained.md` (and `docs/03_website_research.md` for `web/`) so the explanation stays true.
8. **Website rules (`web/`):**
   - `web/js/features.js` and `web/js/model.js` must stay **identical in behaviour** to `src/features.py` / `src/linear_regression.py` / `src/evaluate.py`; `tests/test_web_parity.py` enforces it. Change both sides together.
   - After retraining, run `python src/export_web_model.py` and bump `VERSION` in `web/sw.js`. Add any new file to the `FILES` list in `web/sw.js` (`tests/web/offline.test.js` checks this).
   - **Never** use `innerHTML`, `insertAdjacentHTML`, `eval`, `new Function`, inline `<script>`/`style=""`, or third-party scripts, fonts or CDNs. Text goes in with `textContent`. The CSP + Trusted Types will break the page otherwise, on purpose.
   - Only `localhost` addresses may ever be contacted (CSP `connect-src` in `web/_headers` **and** the `<meta>` in `web/index.html`; keep them identical).
   - Every interface string lives in `web/js/i18n.js` in **both** English and Hindi.
   - The demo banner must stay while `web/model.json` has `"simulated": true`.
   - Run `python scripts/audit_accessibility.py` after UI changes (must report 0 violations).

Commands:
```bash
pip install -r requirements.txt
python src/make_simulated_data.py                         # simulated photos, 4 regions
python src/progression.py --data data/simulated/labels.csv
python src/cross_region.py --data data/simulated/labels.csv
python src/train.py --data data/simulated/labels.csv
python src/predict.py <photo> --sex F --age 19 [--language Hindi] [--no-llm]
streamlit run app.py
python -m pytest -q && npm test
npm test                                                  # JavaScript tests (Node 22)
python src/export_web_model.py                            # models/model.json -> web/model.json
python scripts/serve_web.py                               # website at http://localhost:8000
python scripts/audit_accessibility.py http://localhost:8000 data/simulated/images/india_0004.png
```

---

# Part B — Teach me everything

## Learning path (read in this order)
| # | Topic | Time |
|---|---|---|
| 1 | Where this project sits: AI vs ML vs LLM | 10 min |
| 2 | Supervised learning in one picture | 10 min |
| 3 | y = mx + b: intuition → loss → exact formula → gradient descent | 45 min |
| 4 | Testing properly: train/test split, baseline, overfitting, leakage | 20 min |
| 5 | Metrics: MAE, RMSE, R², sensitivity, specificity, bias | 20 min |
| 6 | Images as numbers | 15 min |
| 7 | Bias and fairness: why we test across regions | 20 min |
| 8 | Local LLMs: Ollama and llama.cpp from zero | 45 min |
| 9 | Running the project, step by step | 30 min |
| 10 | Presenting it and answering judges | 30 min |
| 11 | Exercises (with answers) | 30 min |
| 12 | Glossary | reference |
| 13 | The website: how a model runs in a browser, and web security | 40 min |

---

## 1. Where this project sits

```
Artificial Intelligence  (any computer doing "smart" things)
└── Machine Learning      (learns rules from examples instead of being hand-coded)
    ├── Classic ML        ← OUR MODEL: linear regression, learns m and b from photos
    └── Deep Learning     (neural networks with many layers)
        └── LLMs          ← OUR EXPLAINER: Llama / Gemma / Qwen running locally via Ollama
```
- **Our ML model** answers *"what is this person's haemoglobin?"* It is small, transparent, and fully tested, and we wrote every line.
- **The LLM** answers *"how do I explain this kindly, in Hindi?"* It is huge, pre-trained by someone else, and run on your own computer.

Using each for what it's good at is a **design decision you can explain to judges**: numbers from a model we can test, words from a model that's good with language.

---

## 2. Supervised learning in one picture

```
TRAINING (learn)                                  USING (predict)
photo ─► features x ─┐                            new photo ─► features x ─► model ─► predicted Hb
                     ├─► find m, b that make           (no lab test needed)
lab Hb (label) y ────┘   predictions ≈ labels
```
- **Feature (x):** a number we measure from the input (redness of the nail).
- **Label / target (y):** the right answer for training examples (lab-measured Hb).
- **Supervised:** we learn from examples that come *with* the right answer.
- **Model:** the rule learned. Here it's just the numbers m₁…m₇ and b, stored in `models/model.json`.
- **Regression** = predicting a number (Hb = 10.4). **Classification** = predicting a category (anaemic yes/no). We do regression and then turn the number into a category with WHO cut-offs.

---

## 3. y = mx + b, from intuition to gradient descent

### 3.1 Intuition
You know `y = mx + b` from school. **m** is the steepness and **b** is where the line crosses the y-axis. In ML:
- Plot every training photo as a dot: x = redness, y = Hb.
- The dots form a cloud that slopes upward (redder nail → more Hb).
- **Training = drawing the best straight line through the cloud.**
- **Predicting = reading Hb off the line for a new photo's redness.**

### 3.2 "Best" means smallest error
For each dot, error = (line's guess − true Hb). Square it and average over all dots:
```
MSE = average of (m·x + b − y)²
```
Squaring makes all errors positive and punishes big misses more. The best line has the **smallest MSE**.

### 3.3 The exact formula (one feature)
```
m = Σ(x − x̄)(y − ȳ) / Σ(x − x̄)²        b = ȳ − m·x̄
```
Do it by hand once; it's the best way to understand it. Data: x = [0.30, 0.35, 0.40, 0.45, 0.50], y = [8.1, 9.0, 10.2, 10.9, 12.0].
Answer: **m = 19.4, b = 2.28** (full table in docs/02 §1.3). `python src/progression.py` checks the code gets the same answer.

### 3.4 Gradient descent: learning by small steps
Most ML can't use an exact formula, so it **learns iteratively**:
```
start m = 0, b = 0
repeat many times (each pass = 1 epoch):
    predictions = m·x + b
    errors      = predictions − y
    grad_m      = 2 × average(errors × x)       ← how loss changes if m grows
    grad_b      = 2 × average(errors)           ← how loss changes if b grows
    m = m − learning_rate × grad_m              ← step downhill
    b = b − learning_rate × grad_b
```
**Why it works:** the gradient points uphill on the error surface, so subtracting it moves downhill, towards smaller error. This exact loop, scaled up to billions of numbers, is how LLMs are trained too.

**"Test, test, test until it matches":** `fit_until_match` trains, compares with the exact formula, and if the gap is too big, trains twice as long and tests again. On the 5 points: 5 → 10 → 20 → 40 → 80 epochs → **match**.

**Learning rate:** too small means slow, too big means it overshoots and explodes. Our experiment showed this: 0.001 too slow, 0.1 and 0.9 good, 1.1 exploded. Theory said anything above 1.0 explodes for this setup, and it did.

### 3.5 Many features
Real photos need more than one number:
```
Hb = m₁·red_chroma + m₂·green_chroma + … + m₇·skin_log_red_green + b
```
It is the same loop with one slope per feature. Before training, each feature is **standardised** (mean 0, spread 1) so one learning rate suits all of them. Afterwards the slopes are converted back to normal units.

**Why 256,000 epochs?** Several features measure almost the same thing (they're correlated), which makes a long flat valley that gradient descent crawls along. The exact solver (`numpy.linalg.lstsq`) is the referee that tells us when we've arrived.

---

## 4. Testing properly

| Idea | What it means | How we do it |
|---|---|---|
| **Train/test split** | Hide some photos during training and judge only on those | `split()`: 80% train, 20% test, fixed seed |
| **Baseline** | The dumbest possible model; yours must beat it | "always guess the average Hb" |
| **Overfitting** | Memorising training photos instead of learning the pattern; great on train, bad on test | compare train vs test error; a straight line rarely overfits, which is a plus |
| **Data leakage** | Accidentally letting test info into training (a form of cheating) | correlations and feature choice use **training data only** |
| **Distribution shift** | Real users differ from training data (other skin tones, phones, light) | **cross-region tests**: train in some regions, test in another |
| **Reproducibility** | Same command gives the same result | fixed random seeds everywhere |

---

## 5. Metrics, in plain words
| Metric | Plain meaning | Our simulated final model |
|---|---|---|
| **MAE** | "On average we're off by ___ g/dL" | 0.26 |
| **RMSE** | Like MAE but big misses count extra; we show it as the ± range | ~0.3 |
| **R²** | "We explain ___% of the differences between people" (1.0 = all) | 0.98 |
| **bias** | Do we guess too high (+) or too low (−) on average? Too high means missing anaemia. | ~0 |
| **Sensitivity** | Of anaemic people, % we flag. **The most important for screening.** | 0.93 |
| **Specificity** | Of healthy people, % we correctly clear | 0.93 |

(Simulated numbers. Real ones will be worse; that's normal and fine if you're honest about it.)

**Why sensitivity matters most:** a missed anaemic woman stays untreated, while a false alarm costs one free blood test. So we prefer to err towards flagging.

---

## 6. Images as numbers
- A photo is a grid of pixels. Each pixel has **R, G, B** brightness values (0–255; we scale them to 0–1).
- **Brightness changes everything:** the same nail in a dim room has smaller R, G and B values. So instead of raw R, we use **chromaticity**, R / (R+G+B), the *share* of red. It stays the same when the light gets brighter or dimmer.
- **Why redness = haemoglobin:** blood under the nail shows through. Haemoglobin absorbs green and blue light and reflects red. Less Hb means a paler, less red nail bed. Doctors already check "pallor" by eye; we just measure it with numbers.
- **Glare:** shiny nails reflect pure white spots, which we throw away (`clean_pixels`).

---

## 7. Bias and fairness: why we test across regions
The core story of this project:

1. Train only on lighter-skinned regions (Italy, Russia) → test on Ghana → the model says people have **4.7 g/dL more Hb than they really do** and catches **0%** of anaemia. A dangerous, unfair failure.
2. Why: darker skin pigment and camera colour casts shift the colours, and the model wrongly reads that as "healthy red".
3. Fix 1, **features:** also measure the skin around the nail, so the model can subtract skin tone and camera effects. Cross-region error drops from 0.85 to 0.27 g/dL.
4. Fix 2, **data:** train on **all** regions. Features alone are not enough.

This matches real research: an Indian study of 486 pregnant women found a phone-eye-photo method had only 26% specificity, and the authors suspected pigmentation. Pulse oximeters have the same well-known skin-tone problem. **SDG 5 angle:** anaemia hits women hardest (57% of Indian women aged 15–49), so a tool that fails on darker skin fails exactly the people who need it.

---

## 8. Local LLMs from zero: Ollama and llama.cpp

### 8.1 What a "local model" is
- An LLM is a big file of numbers (**weights**), billions of them (**parameters**: "3B" = 3 billion).
- "Running it locally" means your own computer does the maths. Nothing is sent to the internet, it works offline, and it's **free**. That suits health data (privacy) and rural areas (poor internet).
- **Quantisation** shrinks the weights from 16-bit to about 4-bit numbers. The file is about 4× smaller and faster, with a small quality loss. File names like `Q4_K_M` mean "4-bit, medium".
- **GGUF** is the file format llama.cpp and Ollama use.
- Rough size rule: **file size ≈ parameters × bits ÷ 8**. A 3B model at 4-bit is ≈ 2 GB and needs about 4 GB of free RAM. An 8B model is ≈ 5 GB and needs about 8 GB.

| Model (Ollama name) | Size | Good for | Laptop RAM |
|---|---|---|---|
| `llama3.2:1b` | ~1.3 GB | fastest, weakest; English | 4 GB+ |
| `llama3.2:3b` | ~2 GB | **default here**; decent English, okay Hindi | 8 GB |
| `gemma3:4b` | ~3 GB | often better at Indian languages | 8 GB |
| `qwen2.5:3b` | ~2 GB | strong multilingual | 8 GB |
| `llama3.1:8b` | ~5 GB | best quality, slower | 16 GB |
Try 2–3 of them with the same result, read the Hindi output, and pick the one that reads most naturally. That comparison makes a good slide.

### 8.2 Ollama (easiest)
**Ollama** is an app that downloads models and runs them as a little local server.
```bash
# Install
#   Linux / GitHub Codespaces:
curl -fsSL https://ollama.com/install.sh | sh
#   Mac / Windows: download the installer from https://ollama.com/download

# Start the server (the Mac/Windows app does this automatically)
ollama serve &                 # Linux/Codespaces: run in the background

# Download a model (one time) and try it
ollama pull llama3.2:3b
ollama run llama3.2:3b "Explain anaemia in 2 simple sentences in Hindi"
ollama list                    # models you have
```
Test the exact API our code uses:
```bash
curl http://localhost:11434/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "llama3.2:3b",
  "messages": [{"role": "user", "content": "Say hello in Hindi"}]
}'
```

### 8.3 llama.cpp (more control, what Ollama is built on)
```bash
# Install: Mac -> brew install llama.cpp ; Windows/Linux -> download a release from
#   https://github.com/ggml-org/llama.cpp/releases (or build from source)
# Run a server with a GGUF model (it can download one from Hugging Face with -hf):
llama-server -hf ggml-org/gemma-3-1b-it-GGUF --port 8080
# or with a file you downloaded:
llama-server -m ./models/your-model-Q4_K_M.gguf --port 8080
```
Then point our project at it:
```bash
export LLM_BASE_URL=http://localhost:8080/v1
python src/predict.py photo.jpg --language Hindi
```

### 8.4 How our code talks to it (`src/local_llm.py`)
Both servers accept the same **chat request**:
```json
{ "model": "llama3.2:3b",
  "messages": [ {"role": "system", "content": "<rules>"},
                {"role": "user",   "content": "Screening result: Hb 9.6 g/dL ... explain in Hindi"} ],
  "temperature": 0.3 }
```
- **System message:** the rules the model must follow (our guardrails).
- **User message:** the actual question, with the number from our regression model.
- **Temperature:** randomness. 0 is very predictable, 1 is creative. For health advice we keep it low (0.3).
- **Hallucination:** LLMs can state false things confidently. That's why the LLM **never** decides the Hb, and why the rules say "no medicine names or doses".
- **Fallback:** if no server is running, the app shows fixed safe text instead of crashing, which is a lifesaver during a live demo.

### 8.5 In a GitHub Codespace
- Use a **4-core / 16 GB** machine type if you can (Codespaces → "Change machine type"). The default 2-core works with `llama3.2:1b` or `3b`, just more slowly.
- Install Ollama with the Linux command above, and run `ollama serve &` each time the codespace starts.
- `streamlit run app.py` and Codespaces will offer to open port 8501 in your browser.

---

## 9. Running the project, step by step

```bash
# 0. Setup
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Make simulated photos (4 regions × 150)
python src/make_simulated_data.py

# 2. Watch the whole journey, stage by stage (writes reports/progression_log.md)
python src/progression.py --data data/simulated/labels.csv

# 3. Cross-region heat map (reports/cross_region.png)
python src/cross_region.py --data data/simulated/labels.csv

# 4. Run all tests (49 Python incl. browser tests + JavaScript)
python -m pytest -q && npm test

# 5. Try one photo
python src/predict.py data/simulated/images/ghana_0003.png --sex F --age 20 --no-llm

# 6. With the LLM (Ollama running, model pulled)
python src/predict.py data/simulated/images/ghana_0003.png --sex F --age 20 --language Hindi

# 7. The demo app
streamlit run app.py
```

**Then switch to real data** (docs/02 §5):
```bash
python src/download_data.py --list
python src/download_data.py --get ghana_nails      # or manual download
python src/prepare_dataset.py ...                  # → data/<name>/labels.csv
python src/progression.py --data data/ghana_nails/labels.csv data/<other region>/labels.csv
```
Tip: once downloaded, ask Claude Code: *"I downloaded the dataset into data/raw/X, make labels.csv for it"*. Part A tells it how.

### Suggested AI-week plan
| Day | Goal |
|---|---|
| 1 | Run steps 0–5 on simulated data. Do the exercises in §11 by hand. |
| 2 | Download at least 2 real datasets (2+ regions). Convert them with `prepare_dataset.py`. |
| 3 | Run `progression.py` and `cross_region.py` on **real** data. Write down the real numbers honestly. |
| 4 | Install Ollama, compare 2–3 models for Hindi explanations, polish the app. |
| 5 | Slides + rehearse the demo (with and without internet; the fallback text covers you). |

---

## 10. Presenting it

**5-minute pitch structure:**
1. **Problem (30 s):** 57% of Indian women are anaemic (NFHS-5). Testing needs a needle or a device.
2. **Gap (30 s):** existing phone-photo research fails across skin tones (the Indian study with 26% specificity); EzeCheck needs hardware.
3. **Our solution (60 s):** photo → colour numbers → y = mx + b regression we built from scratch → Hb → WHO category → local LLM explains it in Hindi. No hardware, no internet, no data leaves the phone or laptop.
4. **The science (90 s):** show `fit_line.png`, the "test until it matches" table, then the **cross-region heat map**: "trained on light skin it fails on dark skin; here's how we found it and fixed it."
5. **Live demo (60 s):** `streamlit run app.py`.
6. **Honesty + next steps (30 s):** screening, not diagnosis; next we'd test with real camp data and compare against a CNN.

**Questions judges may ask:**
| Question | Good answer |
|---|---|
| "Why linear regression and not deep learning?" | Small datasets (hundreds of photos) suit simple models. It's explainable (we can show the equation), runs on any phone, and we could test every step. A CNN is future work, for comparison. |
| "How accurate is it?" | Give the real-data numbers with region breakdown; say what's simulated. Mention sensitivity first, since it's what matters for screening. |
| "Does it work on dark skin?" | That's our main experiment: Stage 4 found the failure and Stage 5 reduced it. Show the heat map. |
| "What's the AI part, really?" | ML: the model learns m₁…m₇ and b from labelled photos by gradient descent. LLM: a local language model turns the number into advice. |
| "Why a local LLM?" | Privacy (health data never leaves the device), works offline in villages, free, and no API key. |
| "Could it harm someone?" | A wrong "you're fine" is the risk. That's why we optimise sensitivity, show a range not one number, always advise a blood test, and never give medicine advice. |
| "How is it different from EzeCheck?" | No extra device: any phone camera. |
| "Where does your data come from?" | Public datasets from Ghana, India, Italy and Russia, cited on the slide. |

---

## 11. Exercises (answers below)
1. With m = 19.4, b = 2.28, what Hb is predicted for redness 0.42?
2. If every training photo had redness 0.40, why can't we find m?
3. Gradient descent's loss goes 50 → 80 → 200 → 900. What's wrong and how do you fix it?
4. A model has MAE 0.5 but sensitivity 0.40. Is it a good screening tool? Why?
5. Why must the test set never be used to choose features?
6. Why do we use R/(R+G+B) instead of plain R?
7. Why does the LLM receive the Hb number instead of the photo?
8. A model trained in Italy has bias +3 g/dL in Ghana. What does that mean for a Ghanaian child with Hb 8?

<details><summary>Answers</summary>

1. 19.4 × 0.42 + 2.28 = **10.43 g/dL**.
2. The formula divides by Σ(x−x̄)², which would be 0. You can't tell how Hb changes with redness if redness never changes.
3. The loss is growing, so it's **diverging**: the learning rate is too big. Make it smaller (e.g. 10×).
4. **No.** Small average error, but it misses 60% of anaemic people. For screening, catching cases matters most.
5. Then the test result is no longer a fair "exam on unseen questions". It's **data leakage**, and it makes results look better than reality.
6. It removes overall **brightness**: dim and bright photos of the same nail give the same value.
7. The LLM isn't trained or tested for medical image reading and can hallucinate. Our regression model is tested; the LLM only explains it.
8. The model predicts ~11 g/dL, above the 11.0 child cut-off, so it says "no anaemia" for a child who is moderately anaemic. **A dangerous miss.** That's why we test across regions.
</details>

---

## 12. Glossary
| Term | Meaning |
|---|---|
| **Feature (x)** | A number measured from the input (e.g. red_chroma) |
| **Label / target (y)** | The correct answer for a training example (lab Hb) |
| **Slope (m) / weight** | How much y changes per unit of x |
| **Intercept (b) / bias term** | y when all x are 0; shifts the line up/down (not the same as the "bias" metric) |
| **Loss / MSE** | Average squared error, the thing training makes small |
| **Gradient** | Direction in which the loss increases fastest; we step the opposite way |
| **Learning rate (α)** | Step size in gradient descent |
| **Epoch** | One full pass of updates over the training data |
| **Converge / diverge** | Settle at the answer / blow up |
| **Closed form / least squares** | The exact formula for the best line |
| **Standardisation** | Rescaling a feature to mean 0, spread 1 |
| **Correlation** | −1…+1, how strongly two things move together |
| **Train / test split** | Learn on one part, judge on the hidden part |
| **Baseline** | The simplest model to beat (guess the average) |
| **Overfitting** | Memorising instead of learning; good on train, bad on test |
| **Data leakage** | Test information sneaking into training |
| **Distribution shift** | Real-world data differs from training data |
| **MAE / RMSE / R²** | Error size / error size punishing big misses / share explained |
| **Sensitivity / specificity** | % of sick people caught / % of healthy people cleared |
| **Chromaticity** | A colour's share of R, G, B regardless of brightness |
| **Haemoglobin (Hb)** | Oxygen-carrying protein in blood, measured in g/dL |
| **WHO cut-off** | Hb below which someone counts as anaemic (12 women, 13 men, 11 pregnant women and young children) |
| **LLM** | Large Language Model: predicts text, trained on huge amounts of writing |
| **Parameters** | The numbers inside a model (ours: 8; Llama 3.2 3B: 3 billion) |
| **Quantisation** | Storing weights with fewer bits to save memory |
| **GGUF** | Model file format used by llama.cpp / Ollama |
| **System prompt** | Hidden instructions that set the LLM's rules |
| **Temperature** | How random the LLM's wording is |
| **Hallucination** | An LLM confidently stating something false |
| **Simulated data** | Data we generated with known rules, to test code. Not evidence about the real world. |

---

## 13. The website: how a model runs in a browser, and web security

Full details: [`docs/03_website_research.md`](docs/03_website_research.md). The key ideas:

**Why no server?** Our trained model is just 8 numbers. JavaScript can do `Hb = m₁x₁ + … + b` instantly on any phone. No server means nothing to hack, no photos stored anywhere, no hosting costs, and it works offline. This is called **on-device inference**.

**Two implementations, one answer.** Python trains; JavaScript predicts. If they measured colours even slightly differently, the learned m's and b would be applied to the wrong numbers. So `web/js/features.js` copies `src/features.py` line by line, and a **parity test** feeds both the same pixels and demands the same answer to 9 decimal places. *Exercise:* why does Python's `int(h * 0.5)` become `Math.floor(h * 0.5)` in JavaScript, and when would `Math.round` give a different region?

**Web security in five ideas:**
| Idea | Plain meaning | In our site |
|---|---|---|
| **CSP** (Content Security Policy) | A rule list the browser enforces: "only run scripts from here, only talk to there" | Scripts only from our site; network only to our site + `localhost` (so data physically cannot be sent elsewhere) |
| **XSS** (cross-site scripting) | Tricking a page into running someone else's code, usually via HTML in text | We never insert HTML; **Trusted Types** makes the browser throw an error if anyone tries |
| **Clickjacking** | Loading a site invisibly inside another to trick taps | `frame-ancestors 'none'` + the app refuses to run in a frame |
| **Supply chain** | A library or CDN you include gets hacked | Zero third-party code; fonts self-hosted |
| **Least privilege** | Ask only for what you need | Camera only on this site, mic and location blocked, camera off right after the photo |

**PWA (progressive web app):** a website that can be installed and work offline. `sw.js` (a *service worker*) saves the app's files on the phone the first time; afterwards it opens with no signal. Test: load once, switch on airplane mode, do a check.

**Accessibility:** the site passes the automated WCAG 2.2 AA audit (axe-core) on every screen: big tap targets, visible focus, results announced to screen readers, colour never the only signal, contrast checked in light and dark.

**Judge questions for the website:**
| Question | Answer |
|---|---|
| "Where does the photo go?" | Nowhere. It's measured in the browser and deleted when the result shows. The browser's CSP blocks any other destination. Try it in airplane mode. |
| "How do you know the website gives the same answer as your Python model?" | A parity test plus a real-browser test compare them on the same photos, automatically, on every change. |
| "Is it secure?" | No server, strict CSP, Trusted Types, no third-party code, validated inputs, and tests that attack it (malicious files, a hostile language-model reply). |
| "Can people with low literacy use it?" | No typing, pictures + short words, one question per screen, Hindi, big buttons. Voice guidance is the next step. |
