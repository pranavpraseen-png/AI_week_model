"""Ask a free local LLM (Ollama or llama.cpp) to explain the result in plain language.

The LLM never estimates haemoglobin. The regression model does that; the LLM only
turns the number into friendly advice. Both Ollama and llama.cpp's `llama-server`
speak the same OpenAI-style chat API, so one function covers both:
  Ollama:    http://localhost:11434/v1   (default)
  llama.cpp: http://localhost:8080/v1
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "llama3.2:3b")

SYSTEM_PROMPT = """You are a friendly community health educator in India.
You receive the output of a phone-photo anaemia SCREENING model. Rules:
- It is an estimate, not a diagnosis. Say so once, simply.
- Always advise a proper blood (haemoglobin) test; it is free at government health
  centres under Anemia Mukt Bharat. If severe, say to see a doctor today.
- Suggest iron-rich local foods (green leafy vegetables, jaggery, dals, eggs or meat
  if eaten) and vitamin C with meals. Do NOT give medicine names or doses.
- Use short sentences a 12-year-old can understand. Maximum 120 words.
- Reply in the language requested."""


def explain(result, language="English", base_url=DEFAULT_URL, model=DEFAULT_MODEL, timeout=120):
    """Send the screening result to the local LLM and return its reply text."""
    user_message = (
        f"Screening result: estimated haemoglobin {result['hb']:.1f} g/dL "
        f"(likely range {result['hb_low']:.1f}-{result['hb_high']:.1f}). "
        f"Anaemia cut-off for this person: {result['threshold']} g/dL. "
        f"Category: {result['severity']}. Please explain this in {language}."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "stream": False,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.load(response)
    return body["choices"][0]["message"]["content"].strip()


def fallback_explanation(result):
    """Fixed text used when no local LLM is running, so the app still works."""
    if result["severity"] == "no anaemia":
        advice = "Your photo does not suggest anaemia. Keep eating iron-rich food."
    elif result["severity"] == "severe anaemia":
        advice = "Your photo suggests severe anaemia. Please see a doctor today."
    else:
        advice = f"Your photo suggests {result['severity']}. Please get a blood test soon."
    return (f"{advice} This is a screening estimate, not a diagnosis. "
            "A free haemoglobin test is available at government health centres.")


def explain_or_fallback(result, language="English", base_url=DEFAULT_URL, model=DEFAULT_MODEL):
    try:
        return explain(result, language, base_url, model), True
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, OSError) as err:
        print(f"(Local LLM not reachable at {base_url}: {err}. Using built-in text instead.)")
        return fallback_explanation(result), False
