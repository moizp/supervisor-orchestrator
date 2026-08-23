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
- **`hazard_subgraph`** (`hazard_subgraph.py`) — `ask` (calls
  `wellington-impact-lab`'s `/clarify`, then pauses via LangGraph's
  `interrupt()`) → `act` (resumes with the answer, calls
  `/clarification-answer`) → `poll_for_triage` (polls `GET /events`,
  filters client-side by ID, until `status == "triaged"` or a 90s timeout;
  3s poll interval). Not `ask → act → aggregate → triage` as originally
  planned — `wellington-impact-lab` has no separate `aggregate`/`triage`
  endpoints; the answer call triggers both internally, fire-and-forget, so
  completion is only observable by polling (PLAN.md Phase 2's audit
  finding). No "skip clarification" branch — its Clarifier always asks, by
  design; not revised here.
- **`oia_subgraph`** (`oia_subgraph.py`, parser in `oia_parser.py`) —
  deliberately **not** symmetrical with `hazard_subgraph`. `clarify` (calls
  the OIA Clarifier, parses the response) advances straight to `classify`
  if ready **or** `attempt >= 2` (checked on the first call too — enables
  0, 1, or 2 clarify rounds), otherwise pauses via `interrupt()` with the
  parsed questions and loops back to `clarify` on resume, with the next
  round's prompt built via `build_user_message()` (mirrors `sayyah`'s own
  training-data assembly exactly, not an invented format). Unlike hazard's
  always-ask-exactly-once Clarifier, OIA's can signal readiness on the
  *first* call too, so a well-scoped request can skip clarification
  entirely. **Known live issue (2026-08-16):** the deployed Clarifier's
  ready signal doesn't currently fire, even on its own training data
  (confirmed 4 independent ways — see `PLAN.md`'s Phase 3 regression
  entry) — every session hits the attempt-2 cap and is forced to
  `classify`. `oia_subgraph` is built and tested against the *documented*
  contract regardless; a retrain is the open fix (`PLAN.md`'s open design
  decisions).
- **Misroute recheck** (`misroute_recheck` node in `orchestrate.py`) — a
  second, advisory-only router call, using the enriched/clarified text
  gathered by the domain subgraph. Never auto-switches domains — surfaces
  a suggestion only (*"this looks like it might fit better as [other
  domain]"*). See Data flow below for why suggest-only beats auto-switching.
  **Implementation note:** runs sequentially, right after the domain
  subgraph completes — not in parallel with its final step as originally
  designed. True parallelism would mean pulling `poll_for_triage`/`classify`
  out of their subgraphs into the parent graph to fan out alongside a
  same-superstep call, breaking subgraph encapsulation for a latency
  optimization only. Kept sequential: same real clarified-text information,
  correctness preserved, the latency-hiding optimization deferred.
- **Deterministic vs. model-inferred stays separate** — routing decisions
  read parsed model output via plain code, never a second model judging a
  first model's output.

**What this repo does not own:** model weights, fine-tuning code, training
datasets (stay in each source project's repo).

**License:** Business Source License 1.1 — see `LICENSE`.

## Components

- **`state.py`** — `SupervisorState`, one `TypedDict` shared by the parent
  graph and both subgraphs. Subgraphs added as nodes share state channels
  with their parent directly, so one schema avoids a mapping layer at the
  subgraph boundary.
- **`orchestrate.py`** — the parent graph (assembled per the bullets
  above) and `build_app()`, which opens the SQLite checkpoint file at
  `CHECKPOINT_DB_PATH` (default `orchestrator_checkpoints.sqlite`) and
  returns an `OrchestratorApp` namedtuple (`graph`, `checkpointer`,
  `conn`) — `api.py` needs all three, not just the compiled graph.
  `orchestrate.py`'s own `__main__` block (manual standalone testing) and
  `api.py` (real requests) both call this same `build_app()` function —
  **there is exactly one checkpoint database, not one per file.** Don't
  run both processes against the same `CHECKPOINT_DB_PATH` at once outside
  of dev/testing — SQLite's WAL mode tolerates one writer at a time, not
  two independent OS processes writing concurrently.
- **`hazard_subgraph.py`** / **`oia_subgraph.py`** — each a
  standalone-compilable `StateGraph`. Their clarify-style nodes (`ask`,
  `clarify`) call LangGraph's dynamic `interrupt()` function from inside
  the node body, not the compile-time `interrupt_before` node list — that
  list can't target node names nested inside a subgraph (confirmed
  empirically: raises `ValueError` at compile time). Dynamic `interrupt()`
  propagates correctly across the subgraph boundary instead.
- **`oia_parser.py`** — parsing + the exact system prompts, kept separate
  from graph logic so both `oia_subgraph.py` and the frontend's own
  display logic can depend on it without pulling in HTTP/graph code.
- **`api.py`** — FastAPI app exposing `FRONTEND_PLAN.md`'s 4 endpoints
  (`POST /submit`, `GET /submit/{id}`, `POST /submit/{id}/answer`,
  `POST /submit/{id}/switch`). Holds the `OrchestratorApp` in a
  module-level dict populated once per process via a `lifespan` handler.
  Deployed (Cloud Run, `orchestrator-api`, project
  `supervisor-orchestrator`, `australia-southeast1`) —
  `https://orchestrator-api-r5t2pyegva-ts.a.run.app`. `Dockerfile.api` +
  `cloudbuild.api.yaml` at repo root (needs `python:3.12-slim` or newer —
  a plain `typing.TypedDict` used as a Pydantic v2 field type
  (`state.py`'s `Location`) crashes on startup under 3.11, a gotcha that
  only showed up once actually deployed, not locally). See "The
  checkpointer" below for what deploying this actually means for
  durability (nothing new implemented there yet, deliberately).
- **`checkpoint_cleanup.py`** — the retention sweep, see below.
- **`router_service/main.py`** — separately deployed (Cloud Run, project
  `supervisor-orchestrator`), not part of this repo's own graph process.
  Also hosts `GET /warmup` — see below.
- **`frontend/`** — plain Vite + Svelte 5 (runes) + TypeScript + Tailwind
  v4 SPA, `FRONTEND_PLAN.md`'s UX flow. Mirrors `sayyah/apps/client`'s
  tooling (not SvelteKit — a single-flow app doesn't need routing), not
  `wellington-impact-lab`'s. Deployed to Vercel production (decided
  2026-08-16 — native env-var handling for the backend base URLs, matches
  `sayyah`'s own hosting) —
  `https://frontend-vert-rho-86.vercel.app`, `VITE_API_BASE_URL` set on
  Vercel's Production environment (not a local `.env` file) pointing at
  the live `orchestrator-api` URL above. `frontend/vercel.json` pins
  `buildCommand`/`outputDirectory`/`framework: null` explicitly — Vercel's
  auto-detection guessed SvelteKit purely from `svelte` being a dependency
  (expects a `build/` output dir; this is a plain Vite app that outputs
  `dist/`), which failed the first deploy attempt even though the build
  itself succeeded.
  - `src/lib/api.ts` — typed client for all 4 endpoints, plus
    `checkBackendHealth()` (probes `GET /submit/__health_probe__`; a 404
    counts as "reachable", only a network-level failure means offline —
    `api.py` has no dedicated health endpoint) and fire-and-forget
    `warmupRouter()` (calls `router-service`'s `/warmup` directly,
    cross-origin).
  - `src/lib/SubmissionFlow.svelte.ts` — the whole flow as a runes-based
    state class: intake → submit → clarify loop → complete → optional
    switch. Reflects `session_id` in the URL (`?session=`) for
    refresh-safety, matching `GET /submit/{id}`'s no-mutation contract.
    Implements "communicate system state, not a bare spinner" (see the
    Front-end Developer agent's own guidelines,
    `~/.claude/agents/front-end-developer.md`, for the general
    principle): staged, timed status messages per call
    (`/submit`'s messages stay domain-generic since the domain isn't
    known yet; `/answer`'s are domain-tailored, since hazard's poll-based
    triage is genuinely much slower than OIA's direct classify — staging
    delays were calibrated against real observed latency, ~49s/~83s on a
    cold hazard submission/answer, not guessed), plus a 30s-interval
    backend-health poll surfaced via a small status badge.
  - `src/components/` — `IntakeForm`, `DomainReveal`, `ClarificationStep`
    (one combined free-text answer per round, question rendered
    preserving the numbered-list formatting), `ResultPanel`
    (domain-specific result rendering + the misroute-suggestion switch
    button), `StatusMessage`, `BackendHealthBadge`.
  - Tested against the real local `api.py` (not mocked): both domain
    flows end-to-end, `/switch`, and `GET`'s refresh-safety idempotency.
  - **Visual design (2026-08-24):** follows the [New Zealand Government
    Design System (alpha)](https://design-system-alpha.digital.govt.nz/basics/colours/)'s
    colour palette — Slate `#2A2A2A` (text), Primary `#23CBA5`/`#24A882`/
    `#078766` (brand teal, three WCAG-tiered variants), Link `#005DBB`
    (underlined by default), and the alert palette (Error `#B10E1E`,
    Warning `#D47500`, Success `#088A20`, Info `#1F1BFB`) driving
    `StatusMessage`/`BackendHealthBadge`/error states — all pre-verified
    WCAG 2.1 AA by the design system itself, used as published rather than
    re-shaded. Tokens defined once in `src/app.css`'s Tailwind v4 `@theme`
    block. Dark-mode variants (`-dark` suffixed tokens) are this project's
    own adaptation, not part of NZGDS (which is light-first and doesn't
    define a dark theme yet). **This app is not an official NZ Government
    or Wellington City Council product** — adopting the openly-published
    design language is deliberate, adding any government logo/wordmark
    implying official authorship was deliberately avoided.

### The checkpointer

`SqliteSaver` (`langgraph-checkpoint-sqlite`) is not a "current state"
table — it's a **write-ahead log of the whole execution**. LangGraph
writes a row to its `checkpoints` table (plus rows to `writes`) **per
superstep** (every node completion), not per session. Measured directly:
a single hazard session that only reached partway through `act` (router →
ask → interrupted → act) had already produced 7 checkpoint rows and 19
write rows, split across the parent thread's own namespace and a separate
namespace for the `hazard` subgraph's internal steps.

This granularity is *why* pause/resume is durable: the checkpoint written
at the exact moment `interrupt()` is called captures full state, so a
second process can look it up by `thread_id` alone and continue — no
shared memory required (verified: paused in one Python process, killed
it, resumed successfully from a separate process reading the same SQLite
file). It's also what `POST /submit/{id}/switch` relies on —
`graph.update_state(config, {...}, as_node="router")` just writes a new
synthetic checkpoint and points execution at it.

**`api.py` is now deployed** (Cloud Run, `orchestrator-api`, project
`supervisor-orchestrator`, `australia-southeast1` —
`https://orchestrator-api-r5t2pyegva-ts.a.run.app`), but its durability
story hasn't caught up with that yet. Everything verified above (durable
pause/resume across separate processes) was tested with `orchestrate.py`/
`api.py` running as local processes on one machine, both against the same
local file (see the `orchestrate.py` bullet above) — that part is solid.
Deployed to Cloud Run, though, the checkpoint file sits on that container
instance's local, ephemeral disk — `min-instances=0` (the pattern every
other service here uses, `orchestrator-api` included) means a paused
session **can** be lost if the instance scales down before the submitter
answers. That's the exact failure mode this checkpointer was originally
built to survive, just one layer up: single-process durability is solved,
multi-instance/Cloud-Run durability isn't. **Deliberately deferred, not
solved** (2026-08-16, reconfirmed after actually deploying) — options
considered: pin the service to exactly 1 instance so the local disk never
gets recycled, mount a GCS bucket for the SQLite file (still wants
max-instances=1, since concurrent instances can't safely share one SQLite
file), or move to a real multi-instance-safe checkpointer
(`langgraph-checkpoint-postgres` against Cloud SQL). None implemented —
staying on local SQLite with this known gap live, not just theoretical.

**Growth is unbounded by default** — nothing deletes anything, and growth
scales with `sessions × nodes-executed-per-session`. `checkpoint_cleanup.py`
addresses this, using `checkpointer.delete_thread()`/`prune()`:

- **Retention: 5 days. Sweep gate: runs at most once per 48h**, tracked via
  a `last_cleanup_at` timestamp in a small `cleanup_meta` table in the same
  SQLite file — no separate process, since Cloud Run's `min-instances=0`
  means there's no long-lived process to host a real scheduler.
- **Trigger: piggybacked on every state-mutating request** (`/submit`,
  `/answer`, `/switch`) — deliberately not `GET /submit/{id}`, which stays
  a pure read per the refresh-safety contract.
- Deliberately **not** tied to a session reaching `"complete"` — a
  submitter can still refresh a finished result page afterward, so
  completed sessions need to survive a while, just not forever.
- Verified directly: a synthetic 6-day-old thread was deleted on the first
  sweep, a 1-hour-old thread survived, and an immediate second sweep
  correctly no-op'd (gated) even with a fresh 10-day-old thread present.

### Warmup

`GET /warmup` on `router_service/main.py` — called once by the frontend on
page load, before the submitter finishes filling in the form, to hide
cold-start latency behind that time rather than eliminate it. Pings the
other 2 of the 3 backing services (`wellington-poller`, `oia-server` —
`router-service` itself is already warm by definition once it's handling
this request) via `GET {base}/health`, fire-and-forget. Uses FastAPI's
`BackgroundTasks`, not a bare `asyncio.create_task` — Cloud Run's default
billing only guarantees CPU allocation for the lifetime of request
handling, and a detached asyncio task can get frozen mid-flight the
instant the response is sent; `BackgroundTasks` keeps the request
considered "in flight" until they finish. The client still gets the
response immediately (verified: ~1ms round-trip locally).

## Data flow

**Hazard path** (fixed, no branching):
```
raw_text → ask (interrupt, 1 question, always) → act (answer → actions)
   → poll_for_triage (poll GET /events until triaged, 3s/90s)
   → misroute_recheck (router call 2, advisory) → result + switch suggestion?
```

**OIA path** (loops on a parsed "ready" flag, checked on every call
including the first — enables 0, 1, or 2 clarify rounds):
```
raw_text ──▶ clarify ──▶ ready, or attempt == 2 (cap)? ──▶ yes ──▶ classify ──▶ misroute_recheck (router call 2, advisory) ──▶ result + switch suggestion?
                 ▲                    │
                 └── no, attempt < 2 ─┘
              (loop back to clarify with raw_text + prior Q&A)
```

Both paths converge on the same final shape: the subgraph's own result,
then an advisory router call 2 (misroute recheck), feeding a single
response with an optional switch suggestion attached.

- **Router call 2 runs sequentially, right after the subgraph's final
  step** — not in parallel as originally designed (see "Misroute recheck"
  above for why: true parallelism would require breaking subgraph
  encapsulation). Cost is still doubled (two router calls per submission);
  latency is added, not hidden, as a result of this implementation
  deviation.
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
