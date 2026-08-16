"""Shared graph state — one schema across the parent graph and both
subgraphs (README.md's Architecture). Subgraphs added as nodes to the
parent share state channels with it, so one schema avoids a state-mapping
layer at the subgraph boundary.
"""

from typing import Optional, TypedDict


class Location(TypedDict, total=False):
    suburb: Optional[str]
    lat: Optional[float]
    lon: Optional[float]


class SupervisorState(TypedDict, total=False):
    # Intake
    raw_text: str
    location: Optional[Location]

    # Router (call 1)
    domain: Optional[str]  # "hazard" | "oia"

    # hazard_subgraph
    hazard_event_id: Optional[str]
    hazard_question: Optional[str]
    hazard_answer: Optional[str]
    hazard_actions: Optional[list]

    # oia_subgraph
    oia_history: str  # raw_text + accumulated prior Q&A, built incrementally
    oia_questions: Optional[list[str]]
    oia_preamble: Optional[str]
    oia_answer: Optional[str]
    oia_attempt: int
    oia_ready: Optional[bool]
    oia_agency: Optional[str]

    # Misroute recheck (call 2, advisory only — README's Data flow)
    misroute_suggestion: Optional[str]  # the other domain's name, or None if call 2 agreed

    # Surfaced to the frontend (FRONTEND_PLAN.md's API contract)
    status: str  # "awaiting_clarification" | "complete"
    question: Optional[str]
    result: Optional[dict]
