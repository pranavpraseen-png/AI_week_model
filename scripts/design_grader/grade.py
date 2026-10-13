"""The design exam: grade website layouts the way the MT5 bot grades a dial change.

Same three-step idea as tools/exam.py + tools/upgrade_review.py in the MT5
project:
  1. MEASURE   every candidate is opened in a real browser at laptop size
               (1440x900) and phone size (390x844) and screenshotted while
               scrolling, frame by frame.
  2. HARD GATES  a script (not an opinion) checks things that must never break:
               no console errors, no horizontal scroll on a phone, and no
               serious/critical accessibility violations (axe-core).
  3. AI JUDGE  `claude -p`, restricted to the Read tool, looks at the
               screenshots of the BASELINE and the CANDIDATE side by side and
               scores both on the rubric in rubric.txt. Grading is RELATIVE:
               a candidate passes only if every gate passes AND it beats the
               baseline's average score.

Usage (serve the pages first, e.g. python scripts/serve_web.py --port 8611):
  python scripts/design_grader/grade.py \
      --baseline current=http://localhost:8611 \
      --candidate night-desk=http://localhost:8701/a-night-desk/ [--candidate ...]
      [--runs 2] [--no-ai]

Writes reports/design_grades.md, plus screenshots in reports/design_grades/<name>/.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RUBRIC = Path(__file__).with_name("rubric.txt")
AXE = ROOT / "node_modules" / "axe-core" / "axe.min.js"
CHROMIUM = Path("/opt/pw-browsers/chromium")
OUT = ROOT / "reports" / "design_grades"
SIZES = {"desktop": (1440, 900), "phone": (390, 844)}
FRAMES = {"desktop": 7, "phone": 5}  # screenshots taken while scrolling down
CRITERIA = ["first_impression", "identity", "landscape", "typography", "clarity", "trust", "phone", "craft"]


def capture(name: str, url: str) -> dict:
    """Screenshots + hard gates for one page. Returns {"shots": [...], "gates": {...}}."""
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    shots, errors, gates = [], [], {}
    axe = AXE.read_text() if AXE.exists() else None
    with sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": str(CHROMIUM)} if CHROMIUM.exists() else {}))
        for size, (w, h) in SIZES.items():
            ctx = browser.new_context(viewport={"width": w, "height": h}, bypass_csp=True)
            page = ctx.new_page()
            # Failed loads are recorded once, with their URL, by the "response" handler.
            page.on("console", lambda m: errors.append(m.text)
                    if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
            # A missing favicon is the browser's own request, not the page's fault.
            page.on("response", lambda r: errors.append(f"{r.status} {r.url}")
                    if r.status >= 400 and not r.url.endswith("favicon.ico") else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(2500)  # let entrance animations settle
            total = page.evaluate("document.documentElement.scrollHeight")
            for i in range(FRAMES[size]):
                y = min(i * h, max(0, total - h))
                page.evaluate(f"window.scrollTo(0, {y})")
                page.wait_for_timeout(900)  # scroll-triggered reveals
                path = folder / f"{size}-{i}.png"
                page.screenshot(path=str(path))
                shots.append(path)
                if y >= total - h:
                    break
            if size == "phone":
                gates["no_sideways_scroll"] = page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth + 1")
                if axe:
                    page.evaluate(axe)
                    found = page.evaluate(
                        "axe.run(document, {runOnly: ['wcag2a','wcag2aa']})"
                        ".then(r => r.violations.filter(v => ['serious','critical'].includes(v.impact))"
                        ".map(v => v.id + ' x' + v.nodes.length))")
                    gates["accessibility"] = not found
                    gates["accessibility_detail"] = found
            ctx.close()
        browser.close()
    gates["no_console_errors"] = not errors
    gates["console_detail"] = errors[:5]
    return {"shots": shots, "gates": gates}


def passed(gates: dict) -> bool:
    return all(v for k, v in gates.items() if not k.endswith("_detail"))


def judge(baseline: dict, candidate: dict, runs: int) -> dict:
    """Ask a read-only Claude to score baseline and candidate. Averages `runs` replies."""
    def listing(label, item):
        lines = [f"{label} hard gates: {json.dumps(item['gates'])}", f"{label} screenshots:"]
        lines += [f"  {p}" for p in item["shots"]]
        return "\n".join(lines)

    prompt = "\n\n".join([RUBRIC.read_text(), listing("BASELINE", baseline), listing("CANDIDATE", candidate)])
    replies = []
    for _ in range(runs):
        result = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", "Read"],
            capture_output=True, text=True, timeout=900, cwd=ROOT,
        )
        text = result.stdout
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
        if not match:
            raise RuntimeError(f"judge gave no JSON block:\n{text[-2000:]}")
        replies.append({"text": text, "scores": json.loads(match.group(1))})
    avg = {side: {c: mean(r["scores"][side][c] for r in replies) for c in CRITERIA}
           for side in ("baseline", "candidate")}
    return {"scores": avg, "report": replies[0]["text"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", required=True, help="name=url of the current site")
    parser.add_argument("--candidate", action="append", required=True, help="name=url (repeat for more)")
    parser.add_argument("--runs", type=int, default=1, help="judge replies to average per candidate")
    parser.add_argument("--no-ai", action="store_true", help="only screenshots and hard gates")
    args = parser.parse_args()

    base_name, base_url = args.baseline.split("=", 1)
    baseline = capture(base_name, base_url)
    rows, sections, captured = [], [], []
    for spec in args.candidate:
        name, url = spec.split("=", 1)
        print(f"capturing {name} …", flush=True)
        captured.append((name, capture(name, url)))
    verdicts = {}
    if not args.no_ai:  # the judges are independent, so they run side by side
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {name: pool.submit(judge, baseline, cand, args.runs) for name, cand in captured}
            verdicts = {name: job.result() for name, job in jobs.items()}
    for name, cand in captured:
        row = {"name": name, "gates": passed(cand["gates"]), "gate_detail": cand["gates"]}
        if not args.no_ai:
            verdict = verdicts[name]
            row["base"] = mean(verdict["scores"]["baseline"].values())
            row["score"] = mean(verdict["scores"]["candidate"].values())
            row["criteria"] = verdict["scores"]["candidate"]
            row["passes"] = row["gates"] and row["score"] > row["base"]
            sections.append(f"## {name}\n\n{verdict['report'].strip()}\n")
        rows.append(row)

    lines = ["# Design exam", "",
             f"Baseline: `{base_name}` ({base_url}); gates {'PASS' if passed(baseline['gates']) else 'FAIL'}.",
             "A candidate passes only if every hard gate passes AND its AI-judge average beats the baseline's.", ""]
    if args.no_ai:
        lines += ["| Candidate | Hard gates |", "|---|---|"]
        lines += [f"| {r['name']} | {'PASS' if r['gates'] else 'FAIL ' + json.dumps(r['gate_detail'])} |" for r in rows]
    else:
        head = " | ".join(c.replace("_", " ") for c in CRITERIA)
        lines += [f"| Candidate | Gates | Avg | Baseline avg | {head} | Result |",
                  "|---|---|---|---|" + "---|" * len(CRITERIA) + "---|"]
        for r in sorted(rows, key=lambda r: -r["score"]):
            cells = " | ".join(f"{r['criteria'][c]:.1f}" for c in CRITERIA)
            lines.append(f"| {r['name']} | {'PASS' if r['gates'] else 'FAIL'} | {r['score']:.2f} | "
                         f"{r['base']:.2f} | {cells} | {'PASS' if r['passes'] else 'FAIL'} |")
    report = "\n".join(lines) + "\n\n" + "\n".join(sections)
    (ROOT / "reports" / "design_grades.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
