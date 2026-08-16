"""OIA pipeline subgraph (PLAN.md Phase 3). Deliberately NOT the same shape
as hazard_subgraph — loops `clarify` on a parsed "ready" signal, checked on
the first call too, enabling 0/1/2 clarify rounds (README.md's Architecture
section; don't flatten to hazard's always-ask-once pattern, see CLAUDE.md).

Known issue (PLAN.md, 2026-08-16): the deployed Clarifier's ready signal
doesn't reliably fire even on training data — this subgraph is built against
the documented contract regardless, so it's ready once the retrain lands.
"""

import os
from typing import Optional

import httpx
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from oia_parser import SYSTEM_CLARIFICATION, SYSTEM_CLASSIFICATION, parse_agency, parse_clarification
from state import SupervisorState

OIA_API_BASE = os.environ.get(
    "OIA_API_BASE", "https://oia-server-735121956125.australia-southeast1.run.app"
)

MAX_CLARIFY_ATTEMPTS = 2


def build_user_message(request_text: str, prior_question: str = "", prior_answer: str = "") -> str:
    """Mirrors sayyah's prepare_oia_clarification_data.py build_user_message()
    exactly — must match the training data's assembly or the model sees an
    out-of-distribution prompt shape on follow-up rounds."""
    prior_question = (prior_question or "").strip()
    prior_answer = (prior_answer or "").strip()
    if prior_question:
        return f"{request_text}\n\nPrevious question: {prior_question}\nAnswer: {prior_answer}"
    return request_text


def clarify(state: SupervisorState) -> dict:
    attempt = state.get("oia_attempt", 0) + 1
    user_message = state.get("oia_history") or state["raw_text"]

    response = httpx.post(
        f"{OIA_API_BASE}/v1/chat/completions",
        json={
            "model": "clarification",
            "messages": [
                {"role": "system", "content": SYSTEM_CLARIFICATION},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 300,
            "temperature": 0.5,
        },
        timeout=60,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()
    parsed = parse_clarification(raw)

    if parsed["ready"] or attempt >= MAX_CLARIFY_ATTEMPTS:
        return {
            "oia_attempt": attempt,
            "oia_ready": True,  # forced true past the cap too — advance regardless (README's Data flow)
            "oia_questions": [],
            "oia_preamble": "",
        }

    answer = interrupt({"preamble": parsed["preamble"], "questions": parsed["questions"]})

    return {
        "oia_attempt": attempt,
        "oia_ready": False,
        "oia_questions": parsed["questions"],
        "oia_preamble": parsed["preamble"],
        "oia_answer": answer,
        "oia_history": build_user_message(state["raw_text"], raw, answer),
    }


def route_after_clarify(state: SupervisorState) -> str:
    return "classify" if state.get("oia_ready") else "clarify"


def classify(state: SupervisorState) -> dict:
    response = httpx.post(
        f"{OIA_API_BASE}/v1/chat/completions",
        json={
            "model": "classification",
            "messages": [
                {"role": "system", "content": SYSTEM_CLASSIFICATION},
                {"role": "user", "content": state["raw_text"]},
            ],
            "max_tokens": 50,
            "temperature": 0.1,
        },
        timeout=60,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()
    agency = parse_agency(raw)
    return {"oia_agency": agency, "status": "complete", "result": {"agency": agency}}


def build_graph():
    graph = StateGraph(SupervisorState)
    graph.add_node("clarify", clarify)
    graph.add_node("classify", classify)
    graph.set_entry_point("clarify")
    graph.add_conditional_edges("clarify", route_after_clarify, {"classify": "classify", "clarify": "clarify"})
    graph.add_edge("classify", END)
    return graph.compile()
