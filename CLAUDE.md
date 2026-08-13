# llm-supervisor — Claude Code Project Instructions

## What this project is

A supervisor-orchestrator prototype, built as a learning exercise in AI
orchestration patterns (LangGraph specifically) on top of two independently
owned, already-fine-tuned LLM pipelines from other projects:

- **Hazard triage** (`wellington-impact-lab`, sibling repo) — Clarifier
  (ask/act) + Triage Classifier, for public hazard reports to Wellington
  City Council.
- **OIA request routing** (OIA project, sibling repo) — Clarifier (ask) +
  department/team Classifier, for Official Information Act requests.

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
  for interaction predictability. Don't add a skip/loop branch to
  `hazard_subgraph` to make it symmetrical with `oia_supervisor` — the two
  are different by design, not by omission.
- **Verify hosting/pricing claims against current reality before relying on
  them, don't trust prior research in this repo's own docs.** This project
  already had its first "chosen" router-hosting option (GitHub Models) go
  fully retired mid-build. Before resuming Phase 5 hosting work, re-check
  whatever option `PLAN.md` currently points at is still real.

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
