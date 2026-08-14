# llm-supervisor

Supervisor-orchestrator prototype in front of two independently owned,
already-fine-tuned pipelines:

- **Hazard triage** (`wellington-impact-lab`) — Clarifier (ask/act) + Triage
  Classifier, for public hazard reports to Wellington City Council.
- **OIA request routing** (OIA project) — Clarifier (ask) + department/team
  Classifier, for Official Information Act requests.

Neither pipeline's code lives here. This repo orchestrates only — subgraphs
call each pipeline's own HTTP API. See `PLAN.md` for build steps/status.

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Base model, served locally (needs mlx_lm; production hosting is TBD — see PLAN.md Phase 5):
mlx_lm.server --model microsoft/Phi-3.5-mini-instruct --port 8080

# Sanity-check the router prompt against it:
python3 test_router_model.py
```

## Architecture

A **supervisor**, not a fixed pipeline: a central node decides the next
step after each stage, rather than the sequence being entirely fixed ahead
of time.

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

- **Router** — decides `hazard` vs `oia` from raw submission text. Not one
  of the four fine-tunes (each trained narrowly on its own domain) — a
  zero-shot call to the plain, un-fine-tuned base model instead.
- **`hazard_subgraph`** — `wellington-impact-lab`'s existing fixed sequence,
  invoked as one subgraph node. No "skip clarification" branch — its
  Clarifier always asks, by design; not revised here.
- **`oia_supervisor`** — loops `oia_clarify` (capped at 2 attempts, plain
  counter) until the request reads as ready, then advances to
  `oia_classify`.
- **Deterministic vs. model-inferred stays separate** — routing decisions
  read parsed model output via plain code, never a second model judging a
  first model's output.

**Router model hosting:** self-hosted on Google Cloud Run (project
`supervisor-orchestrator`), same pattern as the other four models —
`Phi-3.5-mini-instruct` converted to GGUF, quantized (Q4_K_M), served via
`llama-cpp-python` (`router_service/`). HF Inference Providers doesn't serve
this model at all; Azure AI Foundry has no real free tier for it; GitHub
Models (originally chosen) was fully retired 2026-07-30 — see `PLAN.md`
Phase 0 for the full evaluation. Deploy status: see `PLAN.md` Phase 5.

**What this repo does not own:** model weights, fine-tuning code, training
datasets (stay in each source project's repo); no frontend yet.

**License:** Business Source License 1.1 — see `LICENSE`.
