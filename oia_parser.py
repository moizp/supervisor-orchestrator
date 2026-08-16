"""Parser for the OIA Clarifier's output format + the exact system prompts
it was trained against (PLAN.md Phase 3's consistent-prompting decision —
must match `sayyah`'s `OiaFlowViewModel.svelte.ts` verbatim; drift here is
a train/serve bug, not a style nit).

Output shape: either the exact READY_SIGNAL sentinel, or a multi-line
preamble + numbered question list
("To process your OIA request, please clarify:\n1. ...\n2. ...").
"""

import re
from typing import TypedDict

SYSTEM_CLARIFICATION = (
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

READY_SIGNAL = "This request is clear enough to process — no further clarification needed."

SYSTEM_CLASSIFICATION = (
    "You are an OIA (Official Information Act) routing specialist for the New Zealand "
    "government. The OIA 1982 gives New Zealanders the right to request information from "
    "government agencies.\n\nGiven an OIA request, identify the correct New Zealand government "
    "agency that holds the requested information. Respond only in this exact format: "
    "Agency: [agency name]"
)


class ParsedClarification(TypedDict):
    ready: bool
    preamble: str
    questions: list[str]


def parse_clarification(raw: str) -> ParsedClarification:
    if raw.strip() == READY_SIGNAL:
        return {"ready": True, "preamble": "", "questions": []}

    lines = [line for line in raw.split("\n") if line.strip()]
    preamble = lines[0] if lines else ""
    questions = [re.sub(r"^\d+\.\s*", "", line).strip() for line in lines[1:]]
    questions = [q for q in questions if q]
    return {"ready": False, "preamble": preamble, "questions": questions}


def parse_agency(raw: str) -> str:
    match = re.match(r"^Agency:\s*(.+)$", raw.strip())
    return match.group(1).strip() if match else raw.strip()
