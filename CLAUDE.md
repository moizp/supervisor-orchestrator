# llm-supervisor — Claude Code Project Instructions

## What this project is

A supervisor-orchestrator prototype, built as a learning exercise in AI
orchestration patterns (LangGraph specifically) on top of two independently
owned, already-fine-tuned LLM pipelines from other projects:

- **Hazard triage** (`wellington-impact-lab`, sibling repo) — Clarifier
  (ask/act) + Triage Classifier, for public hazard reports to Wellington
  City Council.
- **OIA request routing** (`sayyah`, branch `demo/oia-front-end`, sibling
  repo) — Clarifier + Agency Classifier, for Official Information Act
  requests. Live at
  `https://oia-server-735121956125.australia-southeast1.run.app`.

See `README.md` "Architecture" for the full router → subgraph design, and
`PLAN.md` for the phased build checklist — check `PLAN.md` before starting
work, it's the source of truth for what's done vs. still open.

## Architecture conventions (carried over from wellington-impact-lab)

- **This repo orchestrates; it does not own model code.** No model weights,
  no fine-tuning code, no training datasets live here — those stay in each
  source project's own repo. Subgraphs call each pipeline's own HTTP API,
  not their Python modules directly, so this repo never needs either source
  project's code as a dependency.
- **Deterministic vs. model-inferred, kept strictly separate.** Routing
  decisions (which domain, whether to loop) are read off of *parsed* model
  output via plain code — never a second model re-judging a first model's
  output. Loop caps (e.g. max clarify attempts) are plain counters, never a
  model judgement call.
- **The hazard pipeline's design is not up for revision here.** Its
  Clarifier deliberately always asks a question, no "skip if already
  clear" branch — that was an intentional choice in `wellington-impact-lab`
  for interaction predictability. **`oia_subgraph` is deliberately NOT the
  same shape** — it loops on a "ready" signal (checked on the first call
  too, enabling 0/1/2 clarify rounds), which requires a retrain of the OIA
  project's Clarifier that doesn't exist yet. Don't flatten `oia_subgraph`
  to match hazard's always-ask-once pattern "for consistency" — that was
  tried (2026-08-14) and was itself a mistake; see `PLAN.md` Phase 3 for
  why the loop is the actual intended design, not hazard's shape.
- **Verify claims against current reality before relying on them, don't
  trust prior research in this repo's own docs — including claims about
  the two source projects, not just external hosting.** Two real incidents
  so far: the first "chosen" router-hosting option (GitHub Models) went
  fully retired mid-build; and reading the real OIA project (`sayyah`)
  correctly revealed its current API/model shape, but that finding was
  then mis-applied to wrongly cancel a planned retrain — confusing "this
  capability doesn't exist yet" with "this capability isn't needed." Verify
  facts about a source project by reading it, but don't let a factual
  finding silently overturn an already-agreed design decision without
  re-checking the actual reasoning behind that decision first.

## Working style

- **Be specific and succinct in responses and generated docs.** Prefer
  concrete facts, file paths, and exact commands over general explanation.
  Cut hedging and restatement — say the finding/decision plainly, once.
  Docs (`README.md`, `PLAN.md`, code comments) should read as terse
  reference material, not tutorial prose — no re-explaining concepts
  covered elsewhere in the repo's own docs.

## Key commands

```bash
# Local router-model validation (current state — see PLAN.md Phase 1):
# in the myenv venv where mlx_lm is installed:
mlx_lm.server --model microsoft/Phi-3.5-mini-instruct --port 8080

# in this repo's own venv:
.venv/bin/python3 test_router_model.py
```

No orchestration graph exists yet — `test_router_model.py` is a standalone
script validating the router's prompt, not wired into any LangGraph graph.
Don't assume `orchestrate.py` (mentioned as a future entry point in
`README.md`) exists yet; check `PLAN.md`'s checked/unchecked items first.

## Constraints that matter here

- **No OIA project references belong in `wellington-impact-lab`, and no
  hazard-project internals belong hardcoded into the OIA project.** This
  repo exists specifically so cross-project orchestration logic has a home
  that isn't either source repo — keep it that way when adding code here.
- **License:** Business Source License 1.1 (see `LICENSE`) — personal and
  educational use permitted, production use requires a separate license
  from the Licensor, converts to Apache 2.0 on 2030-08-13.
- **No frontend yet, deliberately** — see `PLAN.md`'s "Deferred" section.
  Don't start frontend work without checking whether Phase 4 (end-to-end
  graph test) has actually passed first.
