"""Minimal OpenAI-compatible chat-completions endpoint wrapping the
un-fine-tuned base model (Phi-3.5-mini-instruct, Q4_K_M GGUF). This is the
router's model host — see README.md's Architecture section. Not a full
llama-cpp-python server; just the one endpoint test_router_model.py needs.
"""

import os

from fastapi import FastAPI
from llama_cpp import Llama
from pydantic import BaseModel

MODEL_PATH = os.environ.get(
    "MODEL_PATH", os.path.join(os.path.dirname(__file__), "..", "models", "router-q4km.gguf")
)

app = FastAPI()
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


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    completion = _get_llm().create_chat_completion(
        messages=[m.model_dump() for m in req.messages],
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )
    return completion
