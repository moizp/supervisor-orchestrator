"""Orchestrator HTTP API — FRONTEND_PLAN.md's contract, driving Phase 4.

POST   /submit
GET    /submit/{session_id}
POST   /submit/{session_id}/answer
POST   /submit/{session_id}/switch
"""

import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel

import checkpoint_cleanup
import orchestrate
from state import Location

_app_holder: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    _app_holder["orchestrator"] = orchestrate.build_app()
    yield
    _app_holder.clear()


app = FastAPI(lifespan=lifespan)

# No auth on this API (matches wellington-impact-lab's backend and the
# other services here) — the frontend is a different origin (Vercel-style
# static host or similar), so this needs to be open the same way.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _graph():
    return _app_holder["orchestrator"].graph


def _run_cleanup_sweep() -> None:
    """Retention sweep, gated to run at most once per
    checkpoint_cleanup.MIN_INTERVAL — see that module and PLAN.md's
    Architecture section. Called on every state-mutating endpoint, not
    GET (which must stay a pure read, per the refresh-safety contract)."""
    orch = _app_holder["orchestrator"]
    checkpoint_cleanup.maybe_cleanup(orch.conn, orch.checkpointer)


class SubmitRequest(BaseModel):
    raw_text: str
    location: Optional[Location] = None


class AnswerRequest(BaseModel):
    answer: str


def _pending_interrupt(config: dict) -> Optional[dict]:
    snapshot = _graph().get_state(config)
    for task in snapshot.tasks:
        if task.interrupts:
            return task.interrupts[0].value
    return None


def _format_question(domain: Optional[str], interrupt_value: dict) -> str:
    if domain == "hazard":
        return interrupt_value["question"]
    preamble = interrupt_value.get("preamble", "")
    questions = interrupt_value.get("questions", [])
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    return f"{preamble}\n{numbered}" if preamble else numbered


def _response(session_id: str, state_values: dict, interrupt_value: Optional[dict]) -> dict:
    domain = state_values.get("domain")
    if interrupt_value is not None:
        return {
            "session_id": session_id,
            "domain": domain,
            "status": "awaiting_clarification",
            "question": _format_question(domain, interrupt_value),
        }
    return {
        "session_id": session_id,
        "domain": domain,
        "status": state_values.get("status", "complete"),
        "result": state_values.get("result"),
        "misroute_suggestion": state_values.get("misroute_suggestion"),
    }


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _require_session(session_id: str) -> dict:
    config = _config(session_id)
    snapshot = _graph().get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="session not found")
    return config


@app.post("/submit")
def submit(body: SubmitRequest):
    session_id = str(uuid.uuid4())
    config = _config(session_id)
    result = _graph().invoke({"raw_text": body.raw_text, "location": body.location}, config=config)
    interrupt_value = result["__interrupt__"][0].value if "__interrupt__" in result else None
    _run_cleanup_sweep()
    return _response(session_id, result, interrupt_value)


@app.get("/submit/{session_id}")
def get_submission(session_id: str):
    config = _require_session(session_id)
    snapshot = _graph().get_state(config)
    interrupt_value = None
    for task in snapshot.tasks:
        if task.interrupts:
            interrupt_value = task.interrupts[0].value
            break
    return _response(session_id, snapshot.values, interrupt_value)


@app.post("/submit/{session_id}/answer")
def answer(session_id: str, body: AnswerRequest):
    config = _require_session(session_id)
    if _pending_interrupt(config) is None:
        raise HTTPException(status_code=400, detail="session is not awaiting clarification")
    result = _graph().invoke(Command(resume=body.answer), config=config)
    interrupt_value = result["__interrupt__"][0].value if "__interrupt__" in result else None
    _run_cleanup_sweep()
    return _response(session_id, result, interrupt_value)


@app.post("/submit/{session_id}/switch")
def switch(session_id: str):
    config = _require_session(session_id)
    graph = _graph()
    current = graph.get_state(config).values
    domain = current.get("domain")
    if domain not in ("hazard", "oia"):
        raise HTTPException(status_code=400, detail=f"unexpected domain state: {domain!r}")
    other_domain = "oia" if domain == "hazard" else "hazard"

    # Force the checkpoint's next node to the router's own conditional edge
    # target for the other domain, resetting that domain's own fields to a
    # clean first-round state — same "always restart at the first
    # clarification step" behavior regardless of how far the original path
    # had gotten (FRONTEND_PLAN.md, README.md's Data flow).
    reset_fields = (
        {
            "hazard_event_id": None,
            "hazard_question": None,
            "hazard_answer": None,
            "hazard_actions": None,
        }
        if other_domain == "hazard"
        else {
            "oia_history": None,
            "oia_questions": None,
            "oia_preamble": None,
            "oia_answer": None,
            "oia_attempt": 0,
            "oia_ready": None,
            "oia_agency": None,
        }
    )
    graph.update_state(
        config,
        {"domain": other_domain, "status": "awaiting_clarification", "misroute_suggestion": None, **reset_fields},
        as_node="router",
    )
    result = graph.invoke(None, config=config)
    interrupt_value = result["__interrupt__"][0].value if "__interrupt__" in result else None
    _run_cleanup_sweep()
    return _response(session_id, result, interrupt_value)
