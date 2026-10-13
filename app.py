"""AnaemiaLens demo app.  Run:  streamlit run app.py"""
import json
import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from local_llm import DEFAULT_MODEL, DEFAULT_URL, explain_or_fallback, fallback_explanation  # noqa: E402
from predict import screen  # noqa: E402

MODEL_PATH = Path("models/model.json")
SEVERITY_STYLE = {
    "no anaemia": st.success,
    "mild anaemia": st.warning,
    "moderate anaemia": st.warning,
    "severe anaemia": st.error,
}

st.set_page_config(page_title="AnaemiaLens", page_icon="🩸")
st.title("🩸 AnaemiaLens")
st.caption("Anaemia screening from a phone photo · SDG 3 & 5 · "
           "**A screening estimate, not a diagnosis. Always confirm with a blood test.**")

if not MODEL_PATH.exists():
    st.error("No trained model yet. In a terminal run:\n\n"
             "`python src/make_simulated_data.py` then `python src/progression.py --data data/simulated/labels.csv`")
    st.stop()
model_info = json.loads(MODEL_PATH.read_text())
if any("simulated" in str(path) for path in model_info.get("trained_on", [])):
    st.info("This model was trained on SIMULATED photos. Retrain on real data before trusting results.")

with st.sidebar:
    st.header("About the person")
    sex = st.radio("Sex", ["F", "M"], horizontal=True)
    age = st.number_input("Age (years)", min_value=1, max_value=100, value=20)
    pregnant = st.checkbox("Pregnant", disabled=sex == "M")
    st.header("Explanation")
    language = st.selectbox("Language", ["English", "Hindi", "Malayalam", "Tamil", "Bengali", "Marathi"])
    use_llm = st.checkbox("Use local LLM (Ollama / llama.cpp)", value=True)
    llm_url = st.text_input("LLM URL", DEFAULT_URL, disabled=not use_llm)
    llm_model = st.text_input("LLM model", DEFAULT_MODEL, disabled=not use_llm)

camera_tab, upload_tab = st.tabs(["📷 Take photo", "📁 Upload photo"])
with camera_tab:
    photo = st.camera_input("Fingernail close-up, in daylight, no nail polish")
with upload_tab:
    uploaded = st.file_uploader("Photo of a fingernail", type=["jpg", "jpeg", "png"])
photo = photo or uploaded

if photo is not None:
    with tempfile.NamedTemporaryFile(suffix=Path(photo.name).suffix or ".png", delete=False) as f:
        f.write(photo.getvalue())
        image_path = f.name
    try:
        result = screen(image_path, model_info, sex=sex, age=age, pregnant=pregnant)
    except ValueError as err:
        st.error(f"Could not read this photo: {err} Try again in better light.")
        st.stop()

    left, right = st.columns([1, 1])
    left.image(photo, use_container_width=True)
    right.metric("Estimated haemoglobin", f"{result['hb']:.1f} g/dL",
                 help=f"Likely range {result['hb_low']:.1f}–{result['hb_high']:.1f} g/dL")
    right.write(f"Likely range: **{result['hb_low']:.1f} – {result['hb_high']:.1f} g/dL**")
    right.write(f"WHO anaemia cut-off for this person: **{result['threshold']} g/dL**")
    SEVERITY_STYLE[result["severity"]](result["severity"].capitalize())

    st.subheader("What this means")
    if use_llm:
        with st.spinner("Asking the local language model..."):
            text, used_llm = explain_or_fallback(result, language, llm_url, llm_model)
        if not used_llm:
            st.caption(f"Local LLM not reachable at {llm_url}; showing built-in advice.")
    else:
        text = fallback_explanation(result)
    st.write(text)

    with st.expander("How the model decided (the numbers)"):
        st.write("Colour features measured from the photo:")
        st.json({k: round(v, 4) for k, v in result["features"].items()})
        s = model_info["simple"]
        st.latex(rf"\text{{Hb}} = {s['m']:.2f} \times \text{{{s['feature'].replace('_', ' ')}}} + {s['b']:.2f}"
                 r"\quad\text{(simple model)}")
        st.write("The estimate above uses the multi-feature version: y = m₁x₁ + m₂x₂ + … + b.")
