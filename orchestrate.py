"""Parent supervisor graph entry point (README.md's Architecture section).

Phase 1 scope only: `router_node` wired into a real LangGraph graph, reusing
the prompt/parsing validated in `test_router_model.py`. `hazard_subgraph` and
`oia_subgraph` don't exist yet (PLAN.md Phase 2/3) — the graph is currently
just `router_node -> END`; nothing branches on the routing decision yet.
"""

from typing import TypedDict

import httpx
from langgraph.graph import END, StateGraph

from test_router_model import MODEL_ID, MODEL_SERVER_URL, ROUTER_SYSTEM_PROMPT


class SupervisorState(TypedDict):
    raw_text: str
    domain: str | None  # "hazard" | "oia" | None (unparsed/unexpected model output)


def router_node(state: SupervisorState) -> dict:
    response = httpx.post(
        MODEL_SERVER_URL,
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": state["raw_text"]},
            ],
            "max_tokens": 10,
            "temperature": 0.0,
        },
        timeout=60,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip().upper()
    domain = "hazard" if "HAZARD" in raw else "oia" if "OIA" in raw else None
    return {"domain": domain}


def build_graph():
    graph = StateGraph(SupervisorState)
    graph.add_node("router", router_node)
    graph.set_entry_point("router")
    graph.add_edge("router", END)
    return graph.compile()


if __name__ == "__main__":
    app = build_graph()
    result = app.invoke(
        {"raw_text": "There's a fallen tree blocking half of Karori Road.", "domain": None}
    )
    print(result)
