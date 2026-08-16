"""Minimal OpenAI-compatible chat-completions endpoint wrapping the
un-fine-tuned base model (Phi-3.5-mini-instruct, Q4_K_M GGUF). This is the
router's model host — see README.md's Architecture section. Not a full
llama-cpp-python server; just the one endpoint test_router_model.py needs.
"""

import os

import httpx
from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llama_cpp import Llama
from pydantic import BaseModel

MODEL_PATH = os.environ.get(
    "MODEL_PATH", os.path.join(os.path.dirname(__file__), "..", "models", "router-q4km.gguf")
)

# The other 2 of the 3 backing services this orchestrator calls (this
# service, router-service, is the 3rd — already warm by definition once
# it's handling this very request, so /warmup below only pings these two).
HAZARD_API_BASE = os.environ.get(
    "HAZARD_API_BASE", "https://wellington-poller-735121956125.australia-southeast1.run.app"
)
OIA_API_BASE = os.environ.get(
    "OIA_API_BASE", "https://oia-server-735121956125.australia-southeast1.run.app"
)

app = FastAPI()

# No auth on this API (same posture as wellington-impact-lab's backend and
# the other services here) — the frontend calls /warmup directly from the
# browser, a different origin, so this needs to be open the same way.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_llm: Llama | None = None


def _get_llm() -> Llama:
    global _llm
    if _llm is None:
        _llm = Llama(model_path=MODEL_PATH, n_ctx=2048, verbose=False)
    return _llm


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message]
    max_tokens: int = 60
    temperature: float = 0.0


@app.get("/health")
def health():
    return {"status": "ok"}


def _ping(url: str) -> None:
    try:
        httpx.get(url, timeout=30)
    except httpx.HTTPError:
        pass  # best-effort — the point is to wake the container, not to report success


@app.get("/warmup")
def warmup(background_tasks: BackgroundTasks):
    """Called by the frontend on page load (PLAN.md's Architecture section)
    to hide cold-start latency behind however long the submitter spends
    filling in the form. Uses FastAPI's BackgroundTasks, not a bare
    fire-and-forget asyncio.create_task — Cloud Run only guarantees CPU
    allocation for the lifetime of request handling (default, no
    --cpu-boost/always-allocated config here), and BackgroundTasks keeps
    the request "in flight" until they finish, so the pings don't get
    frozen mid-request. Response still returns immediately to the caller;
    only Cloud Run's CPU accounting waits for the background work.
    """
    background_tasks.add_task(_ping, f"{HAZARD_API_BASE}/health")
    background_tasks.add_task(_ping, f"{OIA_API_BASE}/health")
    return {"status": "warming"}


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    completion = _get_llm().create_chat_completion(
        messages=[m.model_dump() for m in req.messages],
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )
    return completion
