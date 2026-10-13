# Step 1: Choosing the problem (SDG 3 / SDG 5)

**Constraints:** software only (no hardware we build ourselves), about one week of work, a working AI model plus demo at the end.
**Assumed context:** India. Change this if your event is somewhere else, because the need data would change.

## How candidates were scored

Each idea is scored 1–5 on:

| Criterion | Question |
|---|---|
| **Need** | How many people does it hurt, and is that backed by real statistics? |
| **Gap** | Is there room left by existing products or research, or is it already solved? |
| **Data** | Is there an open, labelled dataset we can download today? |
| **Feasible** | Can a student train it and build a demo in about a week, without hardware? |
| **Originality** | Will judges have seen this ten times already? |

## Shortlist

| # | Idea | SDG | Need | Gap | Data | Feasible | Originality | **Total /25** |
|---|---|---|---|---|---|---|---|---|
| 1 | **Anaemia screening from a phone photo (fingernail, palm or inner eyelid), checked across skin tones** | 3 + 5 | 5 | 4 | 4 | 4 | 4 | **21** |
| 2 | Hinglish (code-mixed) misogyny and online-harassment detector | 5 | 4 | 3 | 4 | 5 | 3 | 19 |
| 3 | Women's-health myth checker for Hindi/Hinglish WhatsApp forwards | 3 + 5 | 4 | 5 | 1 | 3 | 5 | 18 |
| 4 | Cough-sound TB screening | 3 | 5 | 3 | 3 (gated) | 2 | 4 | 17 |
| 5 | Gender-biased job-ad detector and rewriter | 5 | 3 | 2 | 3 | 5 | 2 | 15 |
| 6 | Skin-condition classifier that is fair to darker skin | 3 | 4 | 3 | 3 | 3 | 2 | 15 |
| 7 | Postpartum depression risk predictor | 3 + 5 | 4 | 3 | 2 | 4 | 2 | 15 |
| ✗ | PCOS / UCI maternal-risk / breast-cancer classifiers | 3 + 5 | — | 1 | 5 | 5 | 1 | avoid |

## Recommended: #1, phone-photo anaemia screening

### Need
- **57% of Indian women aged 15–49 are anaemic** (NFHS-5, 2019–21), up from 53.1% in NFHS-4. Among adolescent girls aged 15–19 it is 59.1%, and in some states it is above 65% (Assam 65.9%, Tripura 67.2%).
- Anaemia is a women's issue as much as a health one (SDG 5), because of menstruation, pregnancy and unequal access to food. It also drives maternal deaths and low birth weight (SDG 3.1 and 3.2).
- Screening today needs a blood draw or a device: a lab test, HemoCue, or Sahli's method. Many women in rural areas never get tested.

### Competition, and the gap we fill
| Existing approach | Limitation |
|---|---|
| Lab blood test / HemoCue | Needle, consumables, needs a trained worker |
| **EzeCheck** (Indian, non-invasive) | A separate **hardware device** must be bought for each health worker |
| Smartphone eyelid-photo studies | A **UCL study of 486 pregnant women in India** found 89.6% sensitivity but **only 26.1% specificity**, which the authors called *not clinically useful*. They suspected skin/sclera pigmentation. |
| US-built nail-photo app tested in rural Bihar | Only performed well **after retraining on Indian data** |
| Most published models (90%+ accuracy) | Trained and tested on a **single small dataset from one country**. They are rarely tested on a different population. |

**Our angle:** the gap is not "detect anaemia from a photo"; papers already do that. The gap is that **these models break when the skin tone, phone or lighting changes**. We will:
1. Train on one population and **test on a different one** (for example, train on Ghana, test on India/Italy). We report that honestly, which most student projects skip.
2. Add **colour normalisation and lighting augmentation**, then measure whether the cross-population gap shrinks.
3. Frame the output as **triage** ("likely anaemic, please get a blood test"), never as a diagnosis, with a confidence level and a "photo quality too poor" option.

### Data (open, no hardware)
| Dataset | What it contains | Where |
|---|---|---|
| Ghana fingernail images | Nail photos + Hb value, age, sex, anaemic label; 10 hospitals | Mendeley Data, DOI 10.17632/2xx4j3kjg2.1 |
| Ghana palm images | Palm photos, same labels | Mendeley Data, DOI 10.17632/ccr8cm22vz.1 |
| Ghana conjunctiva (eyelid) | 710 images (426 anaemic / 284 not), children | Mendeley Data, DOI 10.17632/nt7r8hv2pz.1 |
| Eyes-defy-anemia | 218 smartphone eye photos + lab Hb, **India + Italy** | IEEE DataPort |
| Girija et al. | Conjunctiva + palm + nail from **1,485 Indian participants**, Hb 6–18.7 g/dL | IEEE DataPort (access may need a free login) |

> ⚠️ Licences were not checked: this container cannot reach Mendeley or IEEE DataPort. Read each dataset's licence page before using it and cite it in the presentation.

### Rough build plan (step 2 onward)
1. Download the Ghana nail + palm sets and Eyes-defy-anemia; explore class balance and Hb distribution.
2. Baseline: hand-crafted colour features (mean R/G/B, a*/b* in LAB) + logistic regression / random forest.
3. Main model: fine-tune a small pretrained CNN (MobileNetV3 / EfficientNet-B0) in Colab or this Codespace on CPU.
4. Robustness: colour-constancy normalisation + brightness/white-balance augmentation; evaluate within-dataset and **cross-dataset**.
5. Explainability: Grad-CAM heatmap showing which pixels drove the prediction.
6. Demo: Streamlit/Gradio app. Upload or take a photo, get a risk level, a confidence, and advice to get a blood test.

### Risks and how we handle them
- **Small datasets:** use transfer learning plus augmentation, report confidence intervals, and don't overclaim.
- **Medical tool ethics:** add a clear disclaimer, call it screening only, and point users to a free government Hb test (Anemia Mukt Bharat).
- **Bias:** report results per sex, age group and dataset; this analysis *is* the project's selling point.

## Runner-up: #2, Hinglish misogyny detector
Pick this if you would rather do NLP than images. It is easier to build (fine-tune MuRIL / IndicBERT), and labelled data exists: a 17k-comment Hinglish misogyny set (2026), TRAC and ICHCL shared-task data. Need: NCRB reports a sharp rise in cybercrime against women, and a survey found 28% of harassed women deliberately reduced their time online. Its weakness is that "hate-speech classifier" is a common student project, so it would need a strong angle, such as explaining *why* a comment was flagged or running as a browser extension.

## Why not the others
- **PCOS / maternal-risk (UCI) / breast cancer:** hundreds of near-identical Kaggle notebooks report about 93% accuracy on the same ~540-row dataset. Judges have seen these too often.
- **Cough TB:** a strong cause, but the data is behind an access agreement and the best global teams only reached AUROC of about 0.74.
- **Myth checker:** a great idea but no real dataset exists (the only government set has 27 items), so most of the week would go into labelling.
- **Job-ad bias:** Textio and Gender Decoder already exist and are free.

## Sources
- NFHS-5 anaemia figures: [Lok Sabha reply](https://eparlib.nic.in/bitstream/123456789/2974925/1/AU1307.pdf), [Down To Earth](https://www.downtoearth.org.in/news/health/anaemia-in-women-and-children-on-the-rise-assam-fares-worst-nfhs-5-80357), [PMC10860231](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10860231/)
- EzeCheck: [PMC11078411](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11078411/), [PMC11617121](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11617121/)
- Smartphone screening in India: [Communications Medicine 2023 (Bihar)](https://doaj.org/article/976bd898c6ff47b4a9a61c7c27d73b2e), [UCL pregnant-women study](https://discovery.ucl.ac.uk/cgi/export/eprint/10204534/BibTeX/discovery-eprint-10204534.bib)
- Conjunctiva AI review: [PMC11854623](https://pmc.ncbi.nlm.nih.gov/articles/PMC11854623), [MIT Solve](https://solve.mit.edu/solutions/72256)
- Datasets: [Ghana fingernails](https://data.mendeley.com/datasets/2xx4j3kjg2/1), [Ghana palm](https://data.mendeley.com/datasets/ccr8cm22vz), [Ghana conjunctiva](https://data.mendeley.com/datasets/nt7r8hv2pz/1), [CP-AnemiC](https://data.mendeley.com/datasets/m53vz6b7fx/1), [Eyes-defy-anemia](https://ieee-dataport.org/documents/eyes-defy-anemia), [Girija et al.](https://ieee-dataport.org/documents/dataset-non-invasive-anemia-screening-using-conjunctiva-palm-and-nail-bed-images-0)
- Misogyny: [Hinglish misogyny dataset 2026](https://journals.riverpublishers.com/index.php/JRSS/article/view/30547), [arXiv 2403.09709](https://arxiv.org/html/2403.09709v1), [IDR on cybercrime against women](https://idronline.org/article/gender/cybercrime-and-women-what-gets-counted/), [2016 survey](https://counterview.in/2016/11/online-abuse-affects-50-plus-indian.html?m=0)
- TB: [CODA TB DREAM results](https://www.medrxiv.org/content/10.1101/2024.03.27.24304980v1), [dataset](https://hyfe.ai/publication/coda-tb-dream-challenge-dataset)
- Skin-tone bias: [Fitzpatrick17k paper](https://ar5iv.labs.arxiv.org/html/2104.09957), [RCSI review](https://rcsismj.com/skin-tone-bias-in-ai-dermatology-tools-are-we-building-inclusive-systems-sadie-badrie/)
- PCOS saturation: [medRxiv 2025](https://www.medrxiv.org/content/10.1101/2025.07.13.25331465.full.pdf)
- Health myths data: [AIKOSH](https://aikosh.indiaai.gov.in/home/datasets/details/health_message_verifiers.html)
- PPD: [PMC7564708](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7564708/)
- Job ads: [Jobs.ie decoder / Gaucher et al. 2011](https://www.jobs.ie/recruiters/recruitment-news/news/introducing-the-jobs-ie-gender-bias-decoder)
