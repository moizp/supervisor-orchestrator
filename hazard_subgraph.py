"""Hazard pipeline subgraph (PLAN.md Phase 2) — wraps
`wellington-impact-lab`'s real API, not the originally-planned 4-endpoint
shape. Confirmed from its `main.py`: only `/clarify` (ask) and
`/clarification-answer` (act) exist; the answer call triggers
aggregate+triage internally, fire-and-forget. Completion is only
detectable by polling `GET /events` and filtering client-side by ID.

No "skip clarification" branch — `ask` always runs, matching
`wellington-impact-lab`'s own Clarifier design (README.md's Architecture
section; not revised here per CLAUDE.md).
"""

import os
import time

import httpx
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from state import SupervisorState

HAZARD_API_BASE = os.environ.get(
    "HAZARD_API_BASE", "https://wellington-poller-735121956125.australia-southeast1.run.app"
)

# PLAN.md Phase 2 open item, decided here: 3s poll interval, 90s timeout.
# 90s comfortably covers the ~15s observed triage latency in
# test_live_interfaces.py with margin for cold starts; 3s keeps
# GET /events call volume low (at most ~30 polls per submission).
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 90


def ask(state: SupervisorState) -> dict:
    location = state.get("location") or {}
    response = httpx.post(
        f"{HAZARD_API_BASE}/events/community-report/clarify",
        json={
            "raw_text": state["raw_text"],
            "suburb": location.get("suburb"),
            "lat": location.get("lat"),
            "lon": location.get("lon"),
        },
        timeout=60,
    )
    response.raise_for_status()
    event = response.json()

    answer = interrupt({"question": event["clarification_question"]})

    return {
        "hazard_event_id": event["id"],
        "hazard_question": event["clarification_question"],
        "hazard_answer": answer,
    }


def act(state: SupervisorState) -> dict:
    response = httpx.post(
        f"{HAZARD_API_BASE}/events/{state['hazard_event_id']}/clarification-answer",
        json={"answer": state["hazard_answer"]},
        timeout=60,
    )
    response.raise_for_status()
    event = response.json()
    return {"hazard_actions": event.get("actions")}


def poll_for_triage(state: SupervisorState) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{HAZARD_API_BASE}/events", timeout=30)
            response.raise_for_status()
        except httpx.HTTPError:
            # Transient network/cold-start hiccup — keep polling until the
            # deadline rather than failing the whole submission on one blip.
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        match = next((e for e in response.json() if e.get("id") == state["hazard_event_id"]), None)
        if match and match.get("status") == "triaged":
            return {
                "status": "complete",
                "result": {
                    "severity": match.get("severity"),
                    "rationale": match.get("rationale"),
                    "hazard_type": match.get("hazard_type"),
                    "actions": state.get("hazard_actions"),
                },
            }
        time.sleep(POLL_INTERVAL_SECONDS)

    # Timed out — surface what's known rather than hang the submitter forever.
    return {
        "status": "complete",
        "result": {
            "severity": None,
            "rationale": "Triage is taking longer than expected — check back shortly.",
            "hazard_type": None,
            "actions": state.get("hazard_actions"),
        },
    }


def build_graph():
    graph = StateGraph(SupervisorState)
    graph.add_node("ask", ask)
    graph.add_node("act", act)
    graph.add_node("poll_for_triage", poll_for_triage)
    graph.set_entry_point("ask")
    graph.add_edge("ask", "act")
    graph.add_edge("act", "poll_for_triage")
    graph.add_edge("poll_for_triage", END)
    return graph.compile()
