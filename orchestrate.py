"""Parent supervisor graph (README.md's Architecture, PLAN.md Phase 4):
`router_node` -> conditional edge -> {hazard_subgraph, oia_subgraph} ->
`misroute_recheck` -> END.

Compiled with a durable (SQLite-backed) checkpointer — PLAN.md's Phase 4
audit finding: `MemorySaver` doesn't survive the orchestrator running as a
real multi-instance Cloud Run service (min-instances=0, no instance
affinity across requests).

Misroute recheck implementation note (deviates from the "runs in parallel
with the final step" optimization in README's Data flow / the Phase 4
"Resolved design decisions" entry): implemented here as a **sequential**
step after the domain subgraph completes, not parallel with its last node.
Parallelizing it correctly would need `triage`/`classify` pulled out of
their subgraphs into the parent (to fan out alongside a same-superstep
misroute call), which breaks the subgraphs' encapsulation for a latency
optimization only. Kept sequential — same, real clarified-text
information, correctness preserved, latency-hiding deferred.
"""

import os
from typing import NamedTuple

import httpx
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from hazard_subgraph import build_graph as build_hazard_subgraph
from oia_subgraph import build_graph as build_oia_subgraph
from state import SupervisorState
from test_router_model import MODEL_ID, MODEL_SERVER_URL, ROUTER_SYSTEM_PROMPT


def _classify_with_router(text: str) -> str | None:
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
    raw = response.json()["choices"][0]["message"]["content"].strip().upper()
    return "hazard" if "HAZARD" in raw else "oia" if "OIA" in raw else None


def router_node(state: SupervisorState) -> dict:
    domain = _classify_with_router(state["raw_text"])
    # Unrecognized model output: default to the OIA path (no active hazard
    # left unrouted; a wrongly-routed OIA request just asks an odd
    # clarifying question, recoverable via the misroute-suggestion path).
    return {"domain": domain or "oia", "status": "awaiting_clarification"}


def route_after_router(state: SupervisorState) -> str:
    return "hazard" if state["domain"] == "hazard" else "oia"


def _enriched_text(state: SupervisorState) -> str:
    if state["domain"] == "hazard":
        answer = state.get("hazard_answer") or ""
        return f"{state['raw_text']}\n\n{answer}".strip()
    return state.get("oia_history") or state["raw_text"]


def misroute_recheck(state: SupervisorState) -> dict:
    recheck_domain = _classify_with_router(_enriched_text(state))
    original = state["domain"]
    suggestion = recheck_domain if recheck_domain and recheck_domain != original else None
    return {"misroute_suggestion": suggestion}


def build_graph():
    graph = StateGraph(SupervisorState)
    graph.add_node("router", router_node)
    graph.add_node("hazard", build_hazard_subgraph())
    graph.add_node("oia", build_oia_subgraph())
    graph.add_node("misroute_recheck", misroute_recheck)

    graph.set_entry_point("router")
    graph.add_conditional_edges("router", route_after_router, {"hazard": "hazard", "oia": "oia"})
    graph.add_edge("hazard", "misroute_recheck")
    graph.add_edge("oia", "misroute_recheck")
    graph.add_edge("misroute_recheck", END)
    return graph


CHECKPOINT_DB_PATH = os.environ.get("CHECKPOINT_DB_PATH", "orchestrator_checkpoints.sqlite")


class OrchestratorApp(NamedTuple):
    graph: object  # CompiledStateGraph
    checkpointer: object  # SqliteSaver — checkpoint_cleanup.maybe_cleanup() needs this directly
    conn: object  # sqlite3.Connection — same DB file, used for the cleanup sweep's own bookkeeping table


def build_app() -> OrchestratorApp:
    """Durable-checkpointer entry point (PLAN.md Phase 4 audit finding —
    not MemorySaver, doesn't survive multi-instance Cloud Run). Takes a raw
    sqlite3.Connection directly rather than SqliteSaver.from_conn_string()'s
    context manager — that CM closes the connection as soon as its
    generator is garbage-collected, which happens immediately if nothing
    keeps the CM object itself alive for the app's lifetime.
    """
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph().compile(checkpointer=checkpointer)
    return OrchestratorApp(graph=graph, checkpointer=checkpointer, conn=conn)


if __name__ == "__main__":
    import uuid

    app = build_app().graph
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = app.invoke(
        {"raw_text": "There's a fallen tree blocking half of Karori Road."}, config=config
    )
    print("first response:", {k: result.get(k) for k in ("domain", "status", "question")} | {"__interrupt__": result.get("__interrupt__")})
    if "__interrupt__" in result:
        result = app.invoke(Command(resume="It's blocking one lane, no injuries."), config=config)
        print("final:", {k: result.get(k) for k in ("status", "result", "misroute_suggestion")})
