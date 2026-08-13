# llm-supervisor

A supervisor-orchestrator prototype that sits in front of two independently
owned, already-fine-tuned pipelines:

- **Hazard triage** (`wellington-impact-lab`) — Clarifier (ask/act) + Triage
  Classifier, for public hazard reports to Wellington City Council.
- **OIA request routing** (OIA project) — Clarifier (ask) + department/team
  Classifier, for Official Information Act requests.

Neither pipeline's code lives in this repo. This repo only orchestrates —
it calls each pipeline's own API, the same way any external caller would.
See `PLAN.md` for the build checklist.

## Getting started

> Not yet runnable — this repo currently holds only planning docs. First
> working code lands with Phase 1 in `PLAN.md`.

Once Phase 1 lands, the expected local setup will be:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # langgraph, httpx, etc.

# Router calls a hosted, un-fine-tuned Phi-3.5-mini-instruct via GitHub Models
# (see "Router model hosting" below) — needs a GitHub token with Models access.
export GITHUB_MODELS_TOKEN=...

# Where the two source pipelines are reachable (local dev or deployed).
export HAZARD_API_BASE=http://localhost:8000
export OIA_API_BASE=http://localhost:8100

python3 orchestrate.py
```

## Architecture

### Role: supervisor orchestrator

This service is a **supervisor**, not a fixed pipeline: a central node makes
a routing decision after each step, rather than the sequence being entirely
fixed in code ahead of time. Concretely:

```
                    ┌──────────────┐
        ┌──────────▶│    router    │
        │           └──────┬───────┘
        │           domain? hazard / oia
        │        ┌──────────┴──────────┐
        │        ▼                     ▼
        │  hazard_subgraph        oia_supervisor
        │  (fixed sequence:            │
        │   ask → act → aggregate  ┌───┴────┐
        │   → triage)              ▼        │
        │                     oia_clarify    │
        │                          │         │
        │                 "ready to classify"?
        │                    no │      │ yes
        │                       └──────┤
        │                  (loop, capped at 2 attempts)
        │                              ▼
        │                       oia_classify
        └──────────────────────────────┘
                        END
```

- **Router** — a single decision point upstream of both domains. Reads the
  raw public submission text and decides `hazard` vs `oia`. Deliberately
  **not** one of the four fine-tuned models (each is narrowly trained on its
  own domain's instruction contract and shouldn't be asked to do an
  unrelated classification job) — it's a zero-shot call to the plain,
  un-fine-tuned base model instead. See "Router model hosting" below.

- **`hazard_subgraph`** — the existing, fixed `wellington-impact-lab`
  pipeline (Clarifier ask → Clarifier act → deterministic aggregation →
  Triage Classifier), invoked as a single subgraph node. No "skip
  clarification" branch — the hazard project's Clarifier deliberately always
  asks, by design, to keep the two-way-channel interaction predictable. This
  orchestrator does not second-guess that design decision.

- **`oia_supervisor`** — the part that actually needs supervisor-style
  looping: an OIA request can be well-formed enough to classify immediately,
  or vague enough to need one or more follow-up questions first. The
  OIA Clarifier is called, its output is parsed, and a conditional edge
  either loops back to clarify again (capped at 2 attempts, a plain counter,
  no model judgement involved in the cap itself) or advances to the OIA
  Classifier.

- **Deterministic vs. model-inferred stays separate**, same discipline as
  both source projects: routing decisions (domain choice, loop continuation)
  are read off of parsed model output via plain code, never decided by a
  second model re-judging a first model's output.

### Router model hosting

The router needs a general-purpose, un-fine-tuned instruct model — evaluated
three hosting options before picking one (see `PLAN.md`'s completed
investigation items for the full findings):

- **Hugging Face Inference Providers** — ruled out. `Phi-3.5-mini-instruct`
  is not currently served by any Inference Provider on HF at all (confirmed
  directly on the model page), independent of the free tier's credit amount
  ($0.10/month for free accounts, tiny regardless).
- **Azure AI Foundry** — ruled out for prototype use. Phi-3.5-mini-instruct
  is in the model catalog as a pay-as-you-go serverless endpoint, but there
  is no standing free tier for it — only a general, time-limited new-account
  Azure credit, not specific to this model.
- **GitHub Models** — chosen. Hosts Phi-3.5-mini-instruct directly, free,
  no credit card, rate-limited to roughly 50-150 requests/day depending on
  tier — comfortably enough for a router that fires once per submission at
  prototype scale.

### What this repo does not own

- No model weights, no fine-tuning code, no training datasets — those stay
  in each source project's own repo.
- No frontend (yet) — see `PLAN.md`'s deferred items for why.
