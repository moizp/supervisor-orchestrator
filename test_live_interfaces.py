"""Integration check: are the three live deployed services actually
reachable and behaving as PLAN.md documents, right now?

Not a substitute for Phase 2/3's subgraph code — this only exercises the
raw HTTP interfaces this repo's subgraphs will eventually call:

- router-service   (supervisor-orchestrator project) — the router model
- oia-server        (oia-llm-server project) — OIA Clarifier + Classifier
- wellington-poller (oia-llm-server project) — hazard ask/act/poll flow

Run: .venv/bin/python3 test_live_interfaces.py
"""

import os
import time

import httpx

ROUTER_URL = os.environ.get(
    "MODEL_SERVER_URL",
    "https://router-service-716627644300.australia-southeast1.run.app/v1/chat/completions",
)
OIA_API_BASE = os.environ.get(
    "OIA_API_BASE", "https://oia-server-735121956125.australia-southeast1.run.app"
)
HAZARD_API_BASE = os.environ.get(
    "HAZARD_API_BASE", "https://wellington-poller-735121956125.australia-southeast1.run.app"
)

# Exact strings the retrained/trained models expect — must match sayyah's
# OiaFlowViewModel.svelte.ts verbatim (PLAN.md Phase 3's consistent-prompting
# decision; drift here is a train/serve bug, not a style nit).
OIA_SYSTEM_CLARIFICATION = (
    "You are an OIA (Official Information Act) analyst for the New Zealand government. "
    "The OIA 1982 gives New Zealanders the right to request information from government "
    "agencies, which must respond within 20 working days.\n\n"
    "When an OIA request is unclear or too broad, the agency needs clarifying questions to "
    "identify exactly what information is being sought before the response deadline.\n\n"
    "Given an OIA request, generate 1-3 concise clarifying questions that help establish the "
    "specific time period or date range, the exact scope or subject matter, and the preferred "
    'format or level of detail needed. If the request already provides enough detail to '
    "identify the correct agency, time period, and scope without further input, respond only "
    'with: "This request is clear enough to process — no further clarification needed." '
    "Otherwise, ask only the questions that are genuinely needed."
)
OIA_READY_SIGNAL = "This request is clear enough to process — no further clarification needed."
OIA_SYSTEM_CLASSIFICATION = (
    "You are an OIA (Official Information Act) routing specialist for the New Zealand "
    "government. The OIA 1982 gives New Zealanders the right to request information from "
    "government agencies.\n\nGiven an OIA request, identify the correct New Zealand government "
    "agency that holds the requested information. Respond only in this exact format: "
    "Agency: [agency name]"
)

results = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# --- router-service (supervisor-orchestrator) -------------------------------
section("router-service")
try:
    r = httpx.get(ROUTER_URL.replace("/v1/chat/completions", "/health"), timeout=30)
    check("router-service /health", r.status_code == 200, r.text)
except Exception as e:
    check("router-service /health", False, repr(e))

try:
    r = httpx.post(
        ROUTER_URL,
        json={
            "model": "microsoft/Phi-3.5-mini-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a routing classifier for Wellington City Council public "
                        "submissions. Given a submission, decide whether it is a HAZARD report "
                        "(an urgent safety or hazard issue happening now, e.g. flooding, a "
                        "fallen tree, a road hazard) or an OIA request (a request for official "
                        "records or information under the Official Information Act, e.g. asking "
                        "what the council did/decided/holds about something). Respond with "
                        "exactly one word: HAZARD or OIA."
                    ),
                },
                {"role": "user", "content": "There's a fallen tree blocking Karori Road."},
            ],
            "max_tokens": 10,
            "temperature": 0.0,
        },
        timeout=60,
    )
    raw = r.json()["choices"][0]["message"]["content"].strip().upper()
    check("router-service classify (hazard text)", "HAZARD" in raw, raw)
except Exception as e:
    check("router-service classify (hazard text)", False, repr(e))


# --- oia-server (oia-llm-server) --------------------------------------------
section("oia-server")
try:
    r = httpx.get(f"{OIA_API_BASE}/health", timeout=30)
    check("oia-server /health", r.status_code == 200, r.text)
except Exception as e:
    check("oia-server /health", False, repr(e))

try:
    r = httpx.post(
        f"{OIA_API_BASE}/v1/chat/completions",
        json={
            "model": "clarification",
            "messages": [
                {"role": "system", "content": OIA_SYSTEM_CLARIFICATION},
                {"role": "user", "content": "I want information about the council."},
            ],
            "max_tokens": 300,
            "temperature": 0.5,
        },
        timeout=60,
    )
    content = r.json()["choices"][0]["message"]["content"].strip()
    check(
        "oia-server clarification (vague request -> asks questions)",
        content != OIA_READY_SIGNAL and len(content) > 0,
        content[:120],
    )
except Exception as e:
    check("oia-server clarification (vague request)", False, repr(e))

try:
    r = httpx.post(
        f"{OIA_API_BASE}/v1/chat/completions",
        json={
            "model": "clarification",
            "messages": [
                {"role": "system", "content": OIA_SYSTEM_CLARIFICATION},
                {
                    "role": "user",
                    "content": (
                        "Under the OIA, I request all emails sent by WCC's Transport "
                        "Planning team between 1 January 2026 and 31 March 2026 that mention "
                        "the Karori Road closure, as PDF copies."
                    ),
                },
            ],
            "max_tokens": 300,
            "temperature": 0.5,
        },
        timeout=60,
    )
    content = r.json()["choices"][0]["message"]["content"].strip()
    check(
        "oia-server clarification (well-scoped -> ready signal)",
        content == OIA_READY_SIGNAL,
        content[:120],
    )
except Exception as e:
    check("oia-server clarification (well-scoped)", False, repr(e))

try:
    r = httpx.post(
        f"{OIA_API_BASE}/v1/chat/completions",
        json={
            "model": "classification",
            "messages": [
                {"role": "system", "content": OIA_SYSTEM_CLASSIFICATION},
                {
                    "role": "user",
                    "content": "I want all information about police misconduct investigations.",
                },
            ],
            "max_tokens": 50,
            "temperature": 0.1,
        },
        timeout=60,
    )
    content = r.json()["choices"][0]["message"]["content"].strip()
    check("oia-server classification", content.startswith("Agency:"), content[:120])
except Exception as e:
    check("oia-server classification", False, repr(e))


# --- wellington-poller (hazard pipeline) ------------------------------------
section("wellington-poller")
try:
    r = httpx.get(f"{HAZARD_API_BASE}/health", timeout=30)
    check("wellington-poller /health", r.status_code == 200, r.text)
except Exception as e:
    check("wellington-poller /health", False, repr(e))

event_id = None
try:
    r = httpx.post(
        f"{HAZARD_API_BASE}/events/community-report/clarify",
        json={
            "raw_text": "There's a fallen tree blocking half of Karori Road, cars backing up.",
            "suburb": "Karori",
        },
        timeout=60,
    )
    r.raise_for_status()
    event = r.json()
    event_id = event.get("id")
    check(
        "wellington-poller POST /clarify (ask)",
        bool(event.get("clarification_question")) and event.get("status") == "awaiting_clarification",
        f"id={event_id} question={event.get('clarification_question')!r}",
    )
except Exception as e:
    check("wellington-poller POST /clarify (ask)", False, repr(e))

if event_id:
    try:
        r = httpx.post(
            f"{HAZARD_API_BASE}/events/{event_id}/clarification-answer",
            json={"answer": "It's a large pine tree, fell about 10 minutes ago, one lane blocked."},
            timeout=60,
        )
        r.raise_for_status()
        event = r.json()
        check(
            "wellington-poller POST /clarification-answer (act)",
            bool(event.get("actions")) and event.get("status") == "new",
            f"actions={event.get('actions')}",
        )
    except Exception as e:
        check("wellington-poller POST /clarification-answer (act)", False, repr(e))

    triaged = None
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{HAZARD_API_BASE}/events", timeout=30)
            r.raise_for_status()
            match = next((e for e in r.json() if e.get("id") == event_id), None)
            if match and match.get("status") == "triaged":
                triaged = match
                break
        except Exception:
            pass
        time.sleep(3)
    check(
        "wellington-poller GET /events poll (triage completes)",
        triaged is not None,
        f"severity={triaged.get('severity')} hazard_type={triaged.get('hazard_type')}"
        if triaged
        else "timed out after 60s",
    )
else:
    check("wellington-poller POST /clarification-answer (act)", False, "skipped, no event_id")
    check("wellington-poller GET /events poll (triage completes)", False, "skipped, no event_id")


# --- summary ------------------------------------------------------------
section("summary")
passed = sum(1 for _, ok, _ in results if ok)
print(f"{passed}/{len(results)} checks passed")
if passed != len(results):
    raise SystemExit(1)
