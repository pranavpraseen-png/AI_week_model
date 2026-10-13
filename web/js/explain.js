// Optional plain-language explanation from a local language model running on
// the user's own computer (Ollama or llama.cpp). It never estimates Hb; it only
// rewords a result the regression model already produced. Its reply is shown
// with textContent, never as HTML.

export const DEFAULT_ENDPOINT = "http://localhost:11434/v1";
export const DEFAULT_MODEL = "llama3.2:3b";
const MAX_REPLY_CHARS = 1500;

const SYSTEM_PROMPT = `You are a friendly community health educator in India.
You receive the output of a phone-photo anaemia SCREENING estimate. Rules:
- It is an estimate, not a diagnosis. Say so once, simply.
- Always advise a proper blood (haemoglobin) test; it is free at government health
  centres under Anemia Mukt Bharat. If severe, say to see a doctor today.
- Suggest iron-rich local foods (green leafy vegetables, jaggery, dals, eggs or meat
  if eaten) and vitamin C with meals. Do NOT give medicine names or doses.
- Use short sentences a 12-year-old can understand. Maximum 120 words.
- Plain text only, no markdown. Reply in the language requested.`;

// Only the user's own machine is allowed (the page's CSP enforces the same).
export function safeEndpoint(raw) {
  let url;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  const local = url.hostname === "localhost" || url.hostname === "127.0.0.1";
  if (!local || !["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
  return url.origin + url.pathname.replace(/\/+$/, "");
}

export async function explainLocally(result, { language, endpoint, model, timeoutMs = 90_000 }) {
  const base = safeEndpoint(endpoint);
  if (!base) throw new Error("endpoint");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${base}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "omit",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
      body: JSON.stringify({
        model,
        temperature: 0.3,
        stream: false,
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          {
            role: "user",
            content:
              `Screening result: estimated haemoglobin ${result.hb.toFixed(1)} g/dL ` +
              `(likely range ${result.low.toFixed(1)}-${result.high.toFixed(1)}). ` +
              `Anaemia cut-off for this person: ${result.threshold} g/dL. ` +
              `Category: ${result.severity === "none" ? "no anaemia" : `${result.severity} anaemia`}. ` +
              `Please explain this in ${language}.`,
          },
        ],
      }),
    });
    if (!response.ok) throw new Error(`http ${response.status}`);
    const body = await response.json();
    const text = body?.choices?.[0]?.message?.content;
    if (typeof text !== "string" || !text.trim()) throw new Error("empty");
    return text.trim().slice(0, MAX_REPLY_CHARS);
  } finally {
    clearTimeout(timer);
  }
}
