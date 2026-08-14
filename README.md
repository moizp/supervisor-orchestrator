# llm-supervisor

Supervisor-orchestrator prototype in front of two independently owned,
already-fine-tuned pipelines:

- **Hazard triage** (`wellington-impact-lab`) — Clarifier (ask/act) + Triage
  Classifier, for public hazard reports to Wellington City Council.
- **OIA request routing** (`sayyah`, branch `demo/oia-front-end`) —
  Clarifier (`model: "clarification"`) + Agency Classifier
  (`model: "classification"`), for Official Information Act requests.
  Live at `https://oia-server-735121956125.australia-southeast1.run.app`.

Neither pipeline's code lives here. This repo orchestrates only — subgraphs
call each pipeline's own HTTP API. See `PLAN.md` for build steps/status,
`FRONTEND_PLAN.md` for the UI design.

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Base model, served locally (needs mlx_lm; production hosting is the
# deployed router-service — see Architecture below):
mlx_lm.server --model microsoft/Phi-3.5-mini-instruct --port 8080

# Sanity-check the router prompt against it:
python3 test_router_model.py
```

## Architecture

A **supervisor**, not a fixed pipeline: a central node decides the next
step after each stage, rather than the sequence being entirely fixed ahead
of time.

- **Router** — decides `hazard` vs `oia` from raw submission text. Not one
  of the four fine-tunes (each trained narrowly on its own domain) — a
  zero-shot call to the plain, un-fine-tuned base model instead. Self-hosted
  on Google Cloud Run (project `supervisor-orchestrator`,
  `router_service/`) — `Phi-3.5-mini-instruct` converted to GGUF, quantized
  (Q4_K_M), served via `llama-cpp-python`. HF Inference Providers doesn't
  serve this model; Azure AI Foundry has no real free tier for it; GitHub
  Models (originally chosen) was fully retired 2026-07-30 — see `PLAN.md`
  Phase 0 for the full evaluation. `min-instances=0`: idles down after
  **15 minutes** with no requests (Cloud Run's documented figure, not a
  hard guarantee), so cold starts recur after any gap that long, not just
  on first-ever use.
- **`hazard_subgraph`** — `wellington-impact-lab`'s existing fixed sequence
  (`ask → act → aggregate → triage`), invoked as one subgraph node. No
  "skip clarification" branch — its Clarifier always asks, by design; not
  revised here.
- **`oia_subgraph`** — deliberately **not** symmetrical with
  `hazard_subgraph`. Loops `clarify` (capped at 2 attempts, plain counter)
  until the request reads as ready, then advances to `classify` — unlike
  hazard's always-ask-exactly-once Clarifier, OIA's can signal readiness
  on the *first* call too, so a well-scoped request can skip clarification
  entirely (0 rounds), same as originally designed. Requires a retrain of
  the OIA project's Clarifier (`sayyah`) to add that readiness signal — it
  doesn't exist in the current model yet, confirmed by reading the real
  training data and frontend (`PLAN.md` Phase 3). The retrain's target
  output should extend the model's real existing style (multi-line
  preamble + numbered list), not a generic invented format.
- **Misroute recheck** — a second, advisory-only router call, run in
  parallel with each subgraph's final step (`triage` / `classify`),
  using the extra information gathered by then (clarified text/answers).
  Never auto-switches domains — surfaces a suggestion only (*"this looks
  like it might fit better as [other domain]"*). See Data flow below for
  why suggest-only beats auto-switching.
- **Deterministic vs. model-inferred stays separate** — routing decisions
  read parsed model output via plain code, never a second model judging a
  first model's output.

**What this repo does not own:** model weights, fine-tuning code, training
datasets (stay in each source project's repo).

**License:** Business Source License 1.1 — see `LICENSE`.

## Data flow

**Hazard path** (fixed, no branching):
```
raw_text → ask (1 question, always) → act (answer → actions, clarified_text)
   → [triage ∥ router call 2 (advisory)] → result + switch suggestion?
```

**OIA path** (loops on a parsed "ready" flag, checked on every call
including the first — enables 0, 1, or 2 clarify rounds):
```
raw_text ──▶ clarify ──▶ ready, or attempt == 2 (cap)? ──▶ yes ──▶ [classify ∥ router call 2 (advisory)] ──▶ result + switch suggestion?
                 ▲                    │
                 └── no, attempt < 2 ─┘
              (loop back to clarify with raw_text + prior Q&A)
```

Both paths converge on the same final shape: the subgraph's own result
computed in parallel with an advisory router call 2 (misroute recheck),
feeding a single response with an optional switch suggestion attached.

- **Router call 2 runs in parallel with the subgraph's final step**, not
  sequentially before it — its latency is hidden behind `triage`'s /
  `classify`'s own latency rather than adding a second round-trip. Cost
  is still doubled (two router calls per submission), latency mostly isn't.
- **Suggest, never auto-switch.** If call 2 disagrees with call 1, the
  frontend shows *"This looks like it might fit better as a hazard
  report/OIA request"* with a **"Submit as hazard report" / "Submit as OIA
  request"** button — the result already computed is shown either way; the
  suggestion doesn't block it. Auto-switching was considered and rejected:
  a second zero-shot call disagreeing doesn't mean it's *right*, and
  silently overriding call 1 risks overriding a correct classification with
  a wrong one. Matches `wellington-impact-lab`'s own rule: never present
  anything this system infers as confirmed fact — here, that means keeping
  the human as the actual decision-maker on a domain switch.
- **No cap or cycle needed for the misroute suggestion itself** (separate
  from OIA's own clarify-loop cap above). Because it's suggestion-only, not
  an automatic re-route, there's no ping-pong risk between domains, unlike
  an auto-switch design would have needed (which was the original
  proposal, reconsidered for this reason).
- **Clicking the switch button always restarts at the *other* pipeline's
  first clarification step** (`ask` or `clarify`) — never jumps
  straight to that pipeline's final result, regardless of how much
  information was already gathered on the original path. Keeps the restart
  behavior uniform and simple rather than trying to carry over partial
  state across two differently-shaped subgraphs.
