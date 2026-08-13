"""Phase 1 sanity check: does the plain, un-fine-tuned base model
(microsoft/Phi-3.5-mini-instruct) reliably classify a public submission as
"hazard" vs "oia" with a zero-shot prompt?

Run against a LOCAL mlx_lm.server for now (see PLAN.md — the GitHub Models
free-hosting plan is dead, retired 2026-07-30; this script targets whatever
OpenAI-compatible endpoint MODEL_SERVER_URL points at, so it can be repointed
at a real hosting choice later without changing the router logic itself).

Start the local server first (base model, no adapter):
    mlx_lm.server --model microsoft/Phi-3.5-mini-instruct --port 8080

Run: .venv/bin/python3 test_router_model.py
"""

import os

import httpx

MODEL_SERVER_URL = os.environ.get("MODEL_SERVER_URL", "http://127.0.0.1:8080/v1/chat/completions")
MODEL_ID = os.environ.get("MODEL_ID", "microsoft/Phi-3.5-mini-instruct")

ROUTER_SYSTEM_PROMPT = (
    "You are a routing classifier for Wellington City Council public submissions. "
    "Given a submission, decide whether it is a HAZARD report (an urgent safety or "
    "hazard issue happening now, e.g. flooding, a fallen tree, a road hazard) or an "
    "OIA request (a request for official records or information under the Official "
    "Information Act, e.g. asking what the council did/decided/holds about something). "
    "Respond with exactly one word: HAZARD or OIA."
)

TEST_CASES = [
    {
        "label": "clear hazard report",
        "text": "There's a fallen tree blocking half of Karori Road, cars are backing up and it looks unstable.",
        "expected": "HAZARD",
    },
    {
        "label": "clear OIA request",
        "text": "Under the Official Information Act, I would like copies of all correspondence between WCC and NZTA "
        "regarding the Karori Road closure over the past six months.",
        "expected": "OIA",
    },
    {
        "label": "ambiguous — records request about a past hazard",
        "text": "What has the council done about the flooding on my street in the past?",
        "expected": None,  # genuinely ambiguous — logged, not asserted
    },
]


def classify(text: str) -> str:
    response = httpx.post(
        MODEL_SERVER_URL,
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "max_tokens": 10,
            "temperature": 0.0,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def main():
    print(f"Router model check against {MODEL_SERVER_URL} ({MODEL_ID})\n")
    passed = 0
    for case in TEST_CASES:
        raw = classify(case["text"])
        verdict = "n/a (ambiguous by design)"
        if case["expected"] is not None:
            ok = case["expected"] in raw.upper()
            verdict = "PASS" if ok else "FAIL"
            passed += int(ok)
        print(f"[{case['label']}]")
        print(f"  input : {case['text']}")
        print(f"  output: {raw!r}  -> {verdict}")
        print()

    scored = sum(1 for c in TEST_CASES if c["expected"] is not None)
    print(f"{passed}/{scored} scored cases passed (1 unscored ambiguous case logged above for manual review)")


if __name__ == "__main__":
    main()
