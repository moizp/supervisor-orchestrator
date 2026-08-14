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

- [x] **Confirmed OIA project's real interfaces (2026-08-14)** — checked
      `/Users/moiz/Repos/sayyah`, branch `demo/oia-front-end`,
      `docs/OIA_API.md` + the live deployment directly (not assumed):
      - Single synchronous endpoint: `POST /v1/chat/completions`, `model`
        field selects `"clarification"` or `"classification"`, full
        result returned directly in the response. **No collapsed-endpoint
        gap** — actually simpler than `wellington-impact-lab`'s API, no
        polling needed for either call.
      - **Already deployed and live:**
        `https://oia-server-735121956125.australia-southeast1.run.app`
        (Cloud Run, australia-southeast1) — verified via direct `curl`,
        `{"status":"ok","models":["clarification","classification"]}`. An
        undocumented (but live) `/health` endpoint exists too.
      - No CORS headers (confirmed via `OPTIONS` check — 405, no
        `Access-Control-Allow-Origin`) — **not a blocker**, our calls are
        server-to-server (orchestrator backend → OIA server), not
        browser-to-OIA-server, so CORS doesn't apply here. Flagged as a
        concern in an earlier pass of this plan, resolved on inspection.
- [x] **Confirmed the current (pre-retrain) baseline, not evidence against
      retraining.** Via `oia_clarification_dataset.csv` (every row has a
      non-empty clarification output — no "already clear" examples exist
      *yet*) and the real frontend (`OiaFlowViewModel.svelte.ts`): today,
      the Clarifier is called exactly once, never loops, has no "ready"
      signal. **Correction (2026-08-14): an earlier pass of this plan
      wrongly concluded from this that the planned retrain was
      unnecessary** — backwards reasoning, conflating "doesn't exist yet"
      with "not needed." The retrain's entire purpose is to add a
      capability absent today. Confirming it's absent today is the
      expected starting point, not a reason to cancel it. Retrain is back
      on.
- [x] Real output formats confirmed (different from what was originally
      assumed, still true and still useful): **clarification** =
      multi-line preamble + numbered list
      (`"To process your OIA request, please clarify:\n1. ...\n2. ..."`),
      not a single-line `Question:` template. **classification** =
      `Agency: [name]` (single line, matches what was assumed). **The
      retrain's "ready" output should extend this real style** (stay
      consistent with the existing preamble/list convention the model
      already produces correctly on hundreds of rows) rather than bolting
      on an unrelated single-line format — lower risk to the model's
      existing well-tuned behavior on everything else.
- [x] **Caller-compatibility — reopened, real.** `OiaFlowViewModel.svelte.ts`'s
      `parseClarification()` assumes the output always contains at least
      one question. Once the retrain adds a "ready, no further questions"
      output, this parser needs updating to handle it — genuine rework in
      the OIA project (`sayyah`), not just a training-data change. Decide
      whether that branch is still actively used/maintained (name suggests
      a demo branch) before prioritizing the fix there.
- [ ] Add training rows to `sayyah`'s `oia_clarification_dataset.csv`
      where the target output signals readiness — **on both a first call
      (enables 0 rounds — request already well-scoped) and after a prior
      round of Q&A (enables 1 round)** — styled consistently with the
      real preamble/numbered-list format above, not invented from scratch
- [ ] Retrain / re-fuse / re-export the OIA Clarifier (in `sayyah`, its
      own `fine_tune_oia_mlx.ipynb` pipeline)
- [ ] Update `OiaFlowViewModel.svelte.ts`'s `parseClarification()` (or
      decide it's out of scope if that branch is inactive) to handle the
      new "ready" output
- [ ] Write our own parser (in `llm-supervisor`) matching the retrained
      format's "ready" signal + the existing multi-line question format
- [ ] Build `oia_subgraph`: `clarify` → conditional edge (parsed "ready"
      flag **on the first call too**, or cap of 2 attempts) → advance to
      `classify` (0 or 1 rounds), or loop back to `clarify` with
      accumulated context (raw_text + prior Q&A) for a 2nd round, then
      force `classify` regardless if still not ready
- [ ] Wire nodes to the OIA project's live endpoint over HTTP

## Phase 4 — Supervisor graph assembly

- [ ] **OIA test cases here are transitively blocked on Phase 3's
      retrain landing in `sayyah`** — `oia_subgraph`'s loop/skip logic
      depends on the retrained Clarifier actually emitting a "ready"
      signal, which doesn't exist until Phase 3's dataset+retrain work
      lands there. (Corrected 2026-08-14 — a prior pass of this plan
      wrongly dropped the retrain and this note along with it; both are
      back.)
- [ ] Parent graph: `router_node` → conditional edge →
      `{hazard_subgraph, oia_subgraph}` → `END`
- [ ] End-to-end test: 1 hazard submission, 1 OIA submission that's
      well-scoped (0 rounds, straight to classify), 1 OIA submission
      that's vague (loops at least once)
- [ ] **End-to-end test, loop cap hit:** an OIA request still vague after
      2 clarify attempts — confirm it's forced to classify anyway, not
      left hanging.
- [ ] **Audit finding (2026-08-14, high):** `interrupt_before` +
      `MemorySaver` (as originally planned) won't survive the orchestrator
      running as a real Cloud Run service — min-instances=0, no
      guaranteed instance affinity across requests, so a paused graph's
      state can vanish before the submitter's answer arrives on a
      different instance. Needs a **durable** checkpointer
      (SQLite/Postgres-backed) before this phase ships, not `MemorySaver`.
- [ ] `interrupt_before` on every clarify-style node (`ask`, `clarify`)
      wired to the durable checkpointer above, keyed by session — required
      by `FRONTEND_PLAN.md`'s API contract, not optional polish
- [ ] Add the misroute-recheck node to both subgraphs, run in parallel
      (fan-out/fan-in) with `triage` / `classify`, writing
      `misroute_suggestion` into graph state (see "Resolved design
      decisions" above)
- [ ] `POST /submit/{session_id}/switch` — restarts the other subgraph at
      its first clarification node using the graph's existing `raw_text`
- [ ] End-to-end test: a submission where router call 2 disagrees with
      call 1 — confirm `misroute_suggestion` is set and the original
      result is still returned alongside it
- [ ] **Audit finding (2026-08-14, medium):** original API contract had no
      safe way to recover state on refresh — `/answer`/`/switch` are real
      mutations, unsafe to replay. Added `GET /submit/{session_id}`
      (idempotent, no mutation) — also closes a REST-completeness gap, not
      just the refresh problem. Implement alongside the other 3 endpoints.

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
- [x] **Cloud Build deploy — succeeded** (build `c22dc677`). Live at
      `https://router-service-r5t2pyegva-uc.a.run.app`
- [x] **Gotcha found:** `--allow-unauthenticated` in `cloudbuild.yaml`
      didn't actually apply an `allUsers` invoker binding — service
      returned 403 until added manually:
      `gcloud run services add-iam-policy-binding router-service --member=allUsers --role=roles/run.invoker`.
      Not an org policy block — the binding just wasn't created. Worth
      double-checking after any future redeploy, don't assume the flag
      alone is sufficient.
- [x] `test_router_model.py` re-run against the **live deployed service**
      (not local `mlx_lm`) — same 2/2 pass, same ambiguous-case answer as
      the local run
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
- [x] **Known limitation, documented (audit finding, 2026-08-14, low):**
      worst-case latency stacks up to 3 sequential cold starts on one
      submission (router + orchestrator + hazard/OIA backend), all
      min-instances=0. Now recorded in `README.md`'s Architecture section
      with the verified figure — Cloud Run's own docs confirm **15
      minutes** idle before scale-to-zero (not a hard guarantee, "up to"),
      recurring after every idle gap that long, not just first-ever use.

## Resolved design decisions (2026-08-14)

- [x] **Misroute recovery — resolved.** Add a second, advisory-only router
      call ("misroute recheck") per subgraph, run **in parallel** with the
      final step (`triage` / `classify`) using the extra information
      gathered by then, not sequentially before it — hides its latency
      behind the final step's own latency. **Suggest, never auto-switch**:
      if it disagrees with the original domain, surface *"this looks like
      it might fit better as [other domain]"* with a switch button; the
      already-computed result is shown regardless. Rejected the
      auto-switch alternative — a disagreeing second zero-shot call isn't
      necessarily *right*, and silently overriding call 1 risks replacing
      a correct classification with a wrong one (same "never present
      inferred output as confirmed fact" rule `wellington-impact-lab`
      already follows). Bonus: suggestion-only needs no flip cap or cycle
      back to the router's dispatch — no ping-pong risk, since nothing
      auto-reroutes. Full design: `README.md` Data flow,
      `FRONTEND_PLAN.md`.
- [x] **Switch behavior — resolved.** Clicking "Submit as hazard report" /
      "Submit as OIA request" always restarts at the *other* pipeline's
      first clarification step (`ask` / `clarify`), never skips to its
      final result — uniform regardless of how far the original path got.
- [x] `README.md`'s stale "no frontend yet" line — fixed, now points at
      `FRONTEND_PLAN.md`.

## Open design decisions (not yet resolved)

- [ ] No session TTL/cleanup for abandoned mid-clarification sessions
      (submitter starts, never answers) — will accumulate indefinitely
      under any checkpointer until something expires them.

## Deferred

- [ ] Generic public-facing submission frontend — design done, see
      `FRONTEND_PLAN.md`. Build still holds until Phase 4 passes (needs the
      `interrupt_before` API contract that plan depends on).
