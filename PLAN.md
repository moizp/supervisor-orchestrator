# Plan

Build checklist. See `README.md` for architecture.

## Phase 0 — Router model hosting investigation (done)

- [x] HF Inference Providers: free tier is $0.10/month (PRO: $2/month) —
      moot, `Phi-3.5-mini-instruct` isn't served by any Inference Provider
      on HF at all.
- [x] Azure AI Foundry: Phi-3.5-mini-instruct is in the catalog as
      pay-as-you-go serverless, but no standing free tier for it — only the
      general, time-limited new-account Azure credit.
- [x] GitHub Models: hosted Phi-3.5-mini-instruct free, ~50-150 req/day.
      **Chosen**, then **superseded (2026-08-13)**: fully retired
      2026-07-30, no exceptions for existing users.
- [x] AWS Bedrock: ruled out — Phi models are Microsoft-platform-exclusive,
      not in Bedrock's ~107-model catalog.
- [x] AWS Lightsail: technically viable, not financially. Free-trial-eligible
      tier (Small-2GB, $12/mo) is too tight for a ~2.4GB GGUF + overhead;
      the comfortable tier (Medium-4GB, 4GB RAM) is $24/mo with **no**
      free trial — a new ongoing cost on a second cloud vendor.
- [x] **Final decision (2026-08-14): self-host on Google Cloud Run**, same
      pattern as the other four models (skip fine-tune/fuse, straight
      `convert_hf_to_gguf.py` → quantize → `llama-cpp-python`). Beats every
      hosted option evaluated — no external free tier survives scrutiny at
      the needed RAM/availability, and Cloud Run's pooled Always Free tier
      is capacity already paid for at $0. Closes Phase 5's hosting item.

## Phase 1 — Router

- [x] Local serving for prompt validation:
      `mlx_lm.server --model microsoft/Phi-3.5-mini-instruct --port 8080`
      (base model, no adapter)
- [x] `test_router_model.py`: 3 prompts (clear hazard, clear OIA, 1
      ambiguous/unscored) against the local server. **2/2 scored cases
      passed.**
- [ ] `requirements.txt` (langgraph, httpx), `.env.example`
      (`MODEL_SERVER_URL`, `HAZARD_API_BASE`, `OIA_API_BASE`)
- [ ] Implement `router_node` in an actual graph (currently only a
      standalone script), pointed at `MODEL_SERVER_URL` so local `mlx_lm`
      and a future hosted endpoint are interchangeable

## Phase 2 — Hazard subgraph (reuse existing pipeline)

- [ ] **Audit finding (2026-08-14, critical):** the original 4-node plan
      below (`ask → act → aggregate → triage`, one HTTP call each) doesn't
      match `wellington-impact-lab`'s real API. Confirmed from `main.py`:
      only `POST /events/community-report/clarify` (ask) and
      `POST /events/{id}/clarification-answer` (act) exist. The answer call
      triggers `aggregate` + `triage` **internally**, fire-and-forget
      (`asyncio.create_task`, not awaited) — there is no `aggregate` or
      `triage` endpoint to call. There is also no `GET /events/{id}` —
      only `GET /events` with list filters. Completion can only be
      detected by **polling `GET /events` and filtering client-side by
      ID** until `status == "triaged"`.
- [ ] Rewrite hazard subgraph around the real shape: `ask` node (calls
      `/clarify`) → `act` node (calls `/clarification-answer`) →
      `poll_for_triage` node (polls `GET /events`, filters by ID, loops on
      a short interval until `status == "triaged"` or a timeout) → done.
      Not 4 clean node-per-endpoint calls.
- [ ] Confirm `wellington-impact-lab`'s endpoints are reachable (local,
      then Cloud Run)
- [ ] Decide and document the poll interval/timeout for `poll_for_triage`
      — affects both latency and how hard this hammers
      `wellington-impact-lab`'s `/events` endpoint
- [ ] Compile and expose as a single node the parent graph can call

## Phase 3 — OIA subgraph

- [ ] Confirm OIA project's Clarifier + Classifier interfaces — **check
      specifically for the same collapsed-endpoint/no-single-GET shape
      found in Phase 2's audit**, don't assume clean node-per-endpoint
      calls will work here either
- [ ] Add OIA Clarifier training rows where the target output is
      `Question: none — ready to classify` for well-formed requests,
      alongside existing ask-a-question rows
- [ ] Retrain / re-fuse / re-export (same pipeline as the hazard models)
- [ ] Validate output round-trips through a `parse_oia_ask_output()`-style
      parser
- [ ] Build `oia_supervisor`: `oia_clarify` → conditional edge (parsed
      "ready" flag, or cap of 2 attempts) → loop or advance to
      `oia_classify`
- [ ] Wire nodes to the OIA project's endpoints over HTTP

## Phase 4 — Supervisor graph assembly

- [ ] **OIA test cases here are transitively blocked on Phase 3's
      retrain** — `oia_supervisor`'s loop logic depends on the OIA
      Clarifier actually emitting `Question: none — ready to classify`,
      which doesn't exist until Phase 3's dataset/retrain work lands. Not
      just sequenced after Phase 3 — genuinely can't be tested before it.
- [ ] Parent graph: `router_node` → conditional edge →
      `{hazard_subgraph, oia_subgraph}` → `END`
- [ ] End-to-end test: 1 hazard submission, 1 well-formed OIA (skips
      straight to classify), 1 vague OIA (loops clarify at least once)
- [ ] **End-to-end test, loop cap hit:** an OIA request still vague after
      2 clarify attempts — confirm it's forced to classify anyway, not
      left hanging. Missing from the original test plan (audit finding,
      2026-08-14) — the cap's actual purpose was never covered.
- [ ] **Audit finding (2026-08-14, high):** `interrupt_before` +
      `MemorySaver` (as originally planned) won't survive the orchestrator
      running as a real Cloud Run service — min-instances=0, no
      guaranteed instance affinity across requests, so a paused graph's
      state can vanish before the submitter's answer arrives on a
      different instance. Needs a **durable** checkpointer
      (SQLite/Postgres-backed) before this phase ships, not `MemorySaver`.
- [ ] `interrupt_before` on every clarify-style node (`ask`, `oia_clarify`)
      wired to the durable checkpointer above, keyed by session — required
      by `FRONTEND_PLAN.md`'s API contract, not optional polish

## Phase 5 — Deployment

- [x] Router model hosting — **decided** (see Phase 0): self-host on Cloud
      Run like the other four
- [x] GCP project `supervisor-orchestrator` created, billing linked, APIs
      enabled (Cloud Run, Cloud Build, Artifact Registry)
- [x] Artifact Registry repo (`supervisor-orchestrator`, us-central1) +
      dedicated `cloudbuild-deployer` service account (4 roles: build,
      artifact writer, run admin, SA user) — same gotcha
      `wellington-impact-lab` hit: new projects don't get the legacy
      default Cloud Build SA
- [x] Router GGUF built: `convert_hf_to_gguf.py` → `llama-quantize`
      (Q4_K_M, 2.29GB, matches the other two models' size). Sanity-checked
      locally via `llama-completion` — correctly classified a hazard-report
      test prompt
- [x] Uploaded to private HF repo `moiz-hf/supervisor-router-q4km`
      (artifact storage only, same pattern as the other two models)
- [x] `router_service/` added: minimal FastAPI wrapper
      (`/v1/chat/completions`), `Dockerfile` (fetches the GGUF from HF at
      build time via `HF_TOKEN` build-arg), `cloudbuild.yaml` (8Gi/4CPU —
      matches the single-model memory `wellington-impact-lab` needed after
      4Gi OOM-killed one model)
- [x] First Cloud Build attempt (`5af48e11`) **failed** — `curl` SSL
      connection dropped mid-download of the 2.3GB GGUF inside the build.
      Fixed: added `--retry 5 --retry-all-errors` to the Dockerfile's fetch
- [x] Second attempt hung during source upload — the local
      `models/router-q4km.gguf` (2.3GB) wasn't excluded from the Cloud
      Build source tarball. Fixed: added `.gcloudignore` (+ `.gitignore`
      entry, `models/` — model weights don't belong in this repo per its
      own README, gap now closed)
- [ ] **Cloud Build deploy — resubmitted, in progress** (build ID
      `c22dc677`, project `supervisor-orchestrator`). Not yet confirmed
      working end-to-end — check status and hit `/health` once it lands.
- [ ] Confirm reachability to both source APIs (CORS/networking) once this
      service and Phases 2/3's subgraphs both exist
- [ ] **Audit finding (2026-08-14, medium):** router-service is planned as
      its own separate Cloud Run deployment, adding a network hop +
      independent cold-start surface on **every** submission (the router
      always runs). Unlike the hazard/OIA calls, this split isn't forced
      by a repo-ownership boundary — this repo is allowed to own the
      router model. Reconsider colocating it in-process with the
      orchestrator's own service, same reasoning `wellington-impact-lab`
      used to justify loading both its models in one process.
- [ ] **Known limitation to document, not fix (audit finding,
      2026-08-14, low):** worst-case latency stacks up to 3 sequential
      cold starts on one submission (router + orchestrator +
      hazard/OIA backend), all min-instances=0. Document as accepted,
      same as `wellington-impact-lab`'s own cold-start tradeoff, rather
      than solving it.

## Open design decisions (audit findings, 2026-08-14, not yet resolved)

- [ ] **No misroute recovery path.** Router is zero-shot, unvalidated at
      scale, and `FRONTEND_PLAN.md` makes the domain reveal non-editable
      by the submitter. A hazard report misrouted to the OIA path gets
      funneled into a bureaucratic question loop instead of triage —
      actively harmful, not just a UX gap. Decide: add a correction path,
      or explicitly document the accepted risk (same precedent as
      `wellington-impact-lab`'s "call 111 in an emergency" disclaimer).
- [ ] No session TTL/cleanup for abandoned mid-clarification sessions
      (submitter starts, never answers) — will accumulate indefinitely
      under any checkpointer until something expires them.
- [ ] `README.md`'s "no frontend yet" line is stale — `FRONTEND_PLAN.md`
      now exists (design done, build still blocked on Phase 4).

## Deferred

- [ ] Generic public-facing submission frontend — design done, see
      `FRONTEND_PLAN.md`. Build still holds until Phase 4 passes (needs the
      `interrupt_before` API contract that plan depends on).
