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
- [x] `requirements.txt` (langgraph==1.2.11, httpx==0.28.1 — pinned;
      langgraph wasn't actually installed in `.venv` despite being listed,
      installed now), `.env.example` (`MODEL_SERVER_URL`, `HAZARD_API_BASE`,
      `OIA_API_BASE`) — `HAZARD_API_BASE` confirmed via `gcloud run services
      list --project=oia-llm-server`: `wellington-poller` is live at
      `https://wellington-poller-735121956125.australia-southeast1.run.app`
      (same project/region as `oia-server`, per Phase 5's cross-project
      entanglement finding)
- [x] Implemented `router_node` in `orchestrate.py`: a real `StateGraph`
      (`router -> END`, nothing branches on the decision yet — hazard/oia
      subgraphs don't exist). Reuses `test_router_model.py`'s prompt/parsing
      rather than duplicating it. Verified end-to-end against the **live**
      `router-service` (not local `mlx_lm`): correctly classified a hazard
      test string.

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

- [x] **Confirmed the deployed backend and its deploy pipeline
      (2026-08-14)** — the actual serving code lives on a *third* branch,
      `demo/oia-back-end`, at `oia-server/app.py`: GGUF/`llama-cpp-python`
      based (`oia-clarification-q4km.gguf` / `oia-classification-q4km.gguf`
      loaded via `Llama(model_path=...)`), and **completely prompt-agnostic**
      — it just formats whatever `messages` array the caller sends, no
      hardcoded system prompt anywhere. Same deploy pattern as this
      project's other 3 models: private HF repos
      (`moiz-hf/oia-clarification-gguf`, `moiz-hf/oia-classification-gguf`)
      as artifact storage, `oia-server/cloudbuild.yaml` fetches at Cloud
      Build time, deploys to Cloud Run service `oia-server` in project
      **`oia-llm-server`** (already have `gcloud` access to it). Updating
      the clarification model is: upload new GGUF to the same HF path,
      resubmit that cloudbuild.yaml unchanged — no `app.py` edits needed.
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
- [x] **Training rows added, in `sayyah`** — 3 CSVs now feed the retrain:
      `oia_clarification_dataset.csv` (432, unchanged), a 50-row addition
      to `oia_clarification_long_dataset.csv` (179 → 229, grounded in real
      fyi.org.nz topic areas/phrasing, synthesized not copied), and new
      `oia_clarification_ready_dataset.csv` (45 rows: 16 first-call-ready,
      14 follow-up-ready, 15 follow-up-still-asks — the three new
      scenarios the ready signal needs). Ready sentinel, exact string used
      everywhere: `"This request is clear enough to process — no further
      clarification needed."`
- [x] **Consistent-prompting decision (2026-08-15):** rather than leave
      the old frontend sending a stale system prompt to a retrained model
      (a real risk — the server has zero prompt logic of its own, see the
      `oia-server/app.py` finding above), updated
      `OiaFlowViewModel.svelte.ts`'s `SYSTEM_CLARIFICATION` to match
      exactly, added `READY_SIGNAL` exact-match parsing + `isReady` state,
      and updated `OiaApp.svelte`'s step2 template to show a friendly
      "no further information needed" message instead of an empty
      "Potentially missing information" section when ready — still the
      same fixed two-step flow, no new step added. Autofixer + Prettier
      clean (also fixed a pre-existing missing `{#each ... (key)}` on the
      question list while touching that block).
- [x] **Abandoned trying to reuse/edit `fine_tune_oia_mlx.ipynb`** — it
      turned out to be a legacy, MLX-native-serving pipeline with no
      working GGUF export path at all (its own "Legacy" section claims
      `convert_hf_to_gguf.py` silently produces a base-model-identical
      GGUF for MLX-fused Phi-3.5 weights — **empirically confirmed false
      for the current deployment**: `curl`'d the live `oia-server` and got
      back the exact trained preamble+numbered-list format, proving the
      deployed GGUF is genuinely fine-tuned). Searched every branch for
      whatever pipeline actually produced the deployed GGUFs — not found,
      untracked in git. **Decision: stopped chasing it, followed
      `wellington-impact-lab`'s own proven pattern directly instead**
      (plain `mlx_lm lora` → fuse → `convert_hf_to_gguf.py` → quantize —
      already validated 3× this project).
- [x] `prepare_oia_clarification_data.py` written (`sayyah` root) —
      mirrors `wellington-impact-lab`'s `generate_clarifier_dataset.py`
      discipline: canonical `build_user_message()` (assembles the
      follow-up round's prior-Q&A context), round-trip validation via
      `parse_clarification_output()` before writing. All 3 CSVs merged:
      **706 rows total, 706/706 round-trip validated, 0 failures.**
      564 train / 142 valid.
- [x] **Fine-tune run — done, with two real gotchas hit and fixed:**
      - First attempt (batch-size 4, no memory flags): crashed with a
        Metal `Insufficient Memory` OOM right as real training started
        (validation pass alone succeeded). Root cause initially suspected
        to be `wellington-impact-lab`'s own dev `uvicorn` server (PID
        94502) holding a 2.4GB GGUF memory-mapped in the background —
        confirmed via `lsof`, killed it, but the **exact same OOM
        recurred** on retry, so it wasn't the sole cause.
      - Real fix: our merged dataset has genuinely longer sequences than
        `wellington-impact-lab`'s own datasets (the "long" dataset's
        multi-sentence requests + follow-up rows appending prior Q&A),
        pushing activation memory over the edge during backprop (vs.
        validation, which is forward-only and survived fine). Fixed with
        `--grad-checkpoint` + `--batch-size 2 --grad-accumulation-steps 2`
        (same effective batch size of 4, lower peak memory per step).
        Peak memory dropped to a stable ~9.15GB, no further crashes.
      - **Overfitting caught and handled the same way
        `wellington-impact-lab` documented for its own retrain:** val loss
        bottomed at iter 300 (0.329), climbed for two checkpoints after
        (iter 400: 0.356, iter 500: 0.366) while train loss kept dropping
        (0.216 → 0.202 → 0.169) — genuine overfitting, not noise. **Killed
        training at iter ~510, using the iter 300 checkpoint**
        (`0000300_adapters.safetensors`), not the final one.
- [x] Copy/select the iter-300 adapter checkpoint as the one to fuse
- [x] Fuse (`mlx_lm.fuse`) → `convert_hf_to_gguf.py` → `llama-quantize`
      (Q4_K_M, 2.29GB) — clean run, no errors
- [x] **Local sanity test — FAILED, not deployed.** Tested 4 first-call-ready
      requests via `llama-completion`, all straight from the training data
      (not held-out — the easiest possible case). **All 4 asked clarifying
      questions instead of emitting the ready signal.** Not a one-off —
      consistent across every test. **Root cause: severe class imbalance.**
      Only 16 first-call-ready rows out of 706 total (~2.3%) — drowned out
      by ~650+ "always ask" rows. The model essentially never learned this
      behavior; it learned the dominant "always ask" shortcut instead. This
      is the exact risk `wellington-impact-lab`'s own dataset guidance
      warns about (roughly even category coverage, or the model shortcuts
      to the majority pattern) — we didn't hit that target: 45 ready-signal
      rows total (first-call + follow-up combined) is ~6.4% of the dataset.
      **Not uploaded. Not deployed.** `moiz-hf/oia-clarification-gguf` and
      the live `oia-server` are both untouched, still the pre-retrain model.
- [x] **Fix round 1: added 129 more ready-signal rows** (91 first-call-ready
      + 68 follow-up-ready + 15 follow-up-ask; `oia_ready_batch2.py`,
      genuinely varied register this time — terse, casual, formal/legalistic,
      rambling-but-complete, news-triggered, not the earlier over-templated
      style). Ready-signal dataset: 45 → 174 rows. Combined dataset: 706 →
      835 rows, ready proportion 6.4% → ~19%. Regenerated JSONL
      (835/835 round-trip validated), retrained from scratch.
- [x] **Retrain #2 — hit the same overfitting pattern, handled the same
      way:** val loss bottomed at iter 400 (0.309), climbed for two
      checkpoints after (500: 0.344, 600: 0.353) while train loss stayed
      low. Killed training, selected iter 400 (val-loss-optimal).
- [x] **Local sanity test — FAILED AGAIN, even with the corrected balance.**
      Same 4 first-call-ready prompts, all straight from training data —
      all 4 still asked questions instead of the ready signal. Confirmed
      via MD5 checksum that the correct iter-400 checkpoint was actually
      fused (not a mixup).
- [x] **Real root cause, found by testing later checkpoints directly (no
      retraining needed):** aggregate val loss is dominated by the
      majority "ask" class (~80% of rows) — the checkpoint it picks as
      "best" doesn't necessarily mean the **minority** ready-signal
      pattern is well-learned yet, even if the majority class is already
      starting to overfit by that point. Tested the iter 500 and iter 600
      checkpoints (already saved on disk, no retraining) directly via
      `mlx_lm generate` against a temp adapter dir — **iter 600 correctly
      produced the ready signal on all 4 previously-failing tests**, despite
      iter 600 being *past* the aggregate-loss overfitting onset. Confirmed
      genuine generalization, not memorization: also tested 2 typo'd
      examples from the reserve batch (see below, never trained on) and 1
      entirely novel example in no dataset at all (dog-attack-incidents,
      new agency/topic) — all correct, plus the normal ask-case still
      correctly asks. **Lesson for future retrains on skewed datasets:
      don't pick the checkpoint by aggregate val loss alone — test the
      minority-class behavior directly at a few checkpoints past the
      aggregate optimum before assuming more data (rather than more
      training) is the fix.**
- [x] Re-fused using iter 600 (MD5-verified) → `convert_hf_to_gguf.py` →
      `llama-quantize` (Q4_K_M, 2.29GB) → local `llama-completion` sanity
      test on the actual final GGUF file (not just the MLX checkpoint) —
      matches, both the ready case and the ask case correct.
- [x] **Uploaded to `moiz-hf/oia-clarification-gguf`** (same filename,
      overwrites the pre-retrain model). `oia-server`/Cloud Run **not yet
      redeployed** — next step.
- [x] **100 more ready-signal rows drafted and appended to the CSV as a
      reserve batch** (`oia_ready_batch3.py`), deliberately with realistic
      typos/grammar slips in the user-authored text (model output stays
      clean) — **not yet merged into a training run** (added to the CSV
      after this run's JSONL was already generated, so these rows are
      genuinely held-out and were used above to confirm real
      generalization, not just future training material). Ready dataset
      now 274 rows total if merged (~28% of a ~935-row combined set).
- [x] **Redeploy — hit two gotchas, both fixed:** first submit assumed
      `wellington-impact-lab`'s own convention (`_AR_REGION=us-central1`,
      `_AR_REPO=oia-server`) without checking — failed, that repo doesn't
      exist in this project. `gcloud artifacts repositories list
      --project=oia-llm-server` showed the real one:
      **`oia-images`, region `australia-southeast1`** (matches the live
      service's own region — this project is NZ-hosted, not US). Also:
      `SHORT_SHA` doesn't auto-populate on a manual `gcloud builds submit`
      (only on trigger-based builds tied to a real commit) — pass it
      explicitly (`SHORT_SHA=$(git rev-parse --short HEAD)`) via
      `--substitutions`.
      **Standing rule going forward: default to `australia-southeast1`
      for any NZ-context deployment.** `router-service` was itself
      originally deployed to `us-central1` — not "the right call," just an
      unchecked assumption copied from `wellington-impact-lab`'s example
      config. **Migrated `router-service` to `australia-southeast1` too**
      (new Artifact Registry repo, rebuild, redeploy, verified working,
      old `us-central1` service + repo deleted) — see Phase 5.
- [x] Resubmitted `oia-server/cloudbuild.yaml` (on `demo/oia-back-end`,
      project `oia-llm-server`, `australia-southeast1`/`oia-images`) —
      rebuilds with the new GGUF, redeploys the same `oia-server` Cloud
      Run service
- [x] **End-to-end test — passed.** Redeployed backend, real HTTP calls:
      ready case → ready signal; ask case → 2 well-formed questions;
      classification (unchanged model, sanity check the whole service
      still works) → valid agency name. All via the consistent (matching)
      system prompt now used on both the frontend and the training data.
- [x] Update `OiaFlowViewModel.svelte.ts`'s `parseClarification()` — done
      earlier as part of the consistent-prompting change
- [x] **Regression found (2026-08-16), contradicts the two entries directly
      above — verify-don't-trust applies to this repo's own docs, not just
      external claims.** Building `llm-supervisor`'s live-interface test
      (`test_live_interfaces.py`, all 3 deployed services) turned up that
      `oia-server`'s Clarifier no longer reliably emits the ready signal.
      Confirmed real, not a test artifact, four independent ways: (1) live
      `oia-server` endpoint, (2) local GGUF
      (`sayyah/gguf/oia-clarification-q4km.gguf`, dated 15 Aug 19:43 —
      matches the redeploy timestamp) via `llama-cpp-python`'s auto
      chat-template, (3) same local GGUF via the *exact* manual prompt
      format `oia-server/app.py` actually uses in production
      (`<|role|>\ncontent<|end|>\n...<|assistant|>\n` — ruled out a
      chat-template mismatch as the cause), (4) greedy decoding
      (`temperature=0`, `top_k=1` — ruled out sampling noise). All 4 ways,
      on 3 examples taken verbatim from
      `oia_clarification_ready_dataset.csv`'s first-call-ready rows (not
      held-out, the easiest possible case) — every one asks a clarifying
      question instead of emitting the ready signal. Live endpoint and
      local GGUF file fail identically, which argues against a
      deploy-time mismatch (stale image, wrong file) as the explanation —
      points at the model/weights themselves. **Root cause not
      investigated further yet** — unknown whether the two "passed" entries
      above were tested on different (luckier) examples, tested wrong, or
      something changed since. Retrain tracked as a fresh open item below,
      not resumed inline — this session's actual task was interface
      reachability, not accuracy.
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
- [x] **Migrated `us-central1` → `australia-southeast1` (2026-08-15)** —
      the original region was an unchecked assumption copied from
      `wellington-impact-lab`'s example config, not a deliberate choice;
      NZ-context projects should default to `australia-southeast1` (see
      Phase 3's finding for the OIA project hitting the same thing).
      New Artifact Registry repo created, image rebuilt/redeployed, same
      IAM-binding gotcha hit again (`--allow-unauthenticated` didn't
      create the `allUsers` binding, added manually), verified working
      (`/health` + a real classification call). Old `us-central1` Cloud
      Run service and Artifact Registry repo **deleted** after
      verification — live at
      `https://router-service-716627644300.australia-southeast1.run.app`
      now.
- [x] **Artifact Registry audit across all 3 projects, unrelated stray
      artifacts found and cleaned up:**
      - A 2.2GB stale Cloud Build source tarball from the very first
        (pre-`.gcloudignore`) attempt, sitting unbilled-for-nothing in
        `gs://supervisor-orchestrator_cloudbuild` — deleted; added a
        7-day lifecycle rule to both projects' `_cloudbuild` buckets so
        this can't recur silently.
      - 2 untagged stray `oia-server` images in `oia-llm-server` — deleted.
      - **Found `wellington-impact-lab`'s own live production service**
        (`wellington-poller`, both its fine-tuned models bundled in one
        image, same pattern as `oia-server`) **deployed under the
        `oia-llm-server` project**, not its own — real cross-project
        entanglement, not just clutter. 3 of its 4 images weren't the
        live one (only `:latest` is) — those 3 deleted; the live image
        and service left untouched. Whether to properly migrate
        `wellington-poller` to its own project is a separate, bigger
        decision, not resolved here.
      - Confirmed the expected total size given 5 quantized models
        (~2.29GB each × 5 ≈ 11.45GB raw weight) packaged into 3 images
        (2+2+1 models, ~0.3-0.5GB overhead each): ~12.3GB total across
        both projects post-cleanup — matches observed.
- [x] **Raw interface reachability confirmed (2026-08-16), ahead of the
      subgraphs existing** — `test_live_interfaces.py` added, exercises all
      3 deployed services' actual HTTP contracts directly (not through this
      repo's own code, which doesn't call them yet): `router-service`
      `/health` + classify, `oia-server` `/health` + clarification +
      classification, `wellington-poller` `/health` + full
      `clarify → clarification-answer → poll GET /events` flow. All 3
      services reachable and shaped as documented; the hazard poll flow
      completed end-to-end (`severity=low`, `hazard_type=flooding`).
      Scope was reachability only, not accuracy — see the Phase 3 finding
      immediately above (and the fresh open item below) for the one
      accuracy regression this run surfaced incidentally.
- [ ] Confirm reachability to both source APIs (CORS/networking) once this
      service and Phases 2/3's subgraphs both exist — the item above covers
      raw HTTP reachability; this one is still open for when this repo's
      own code (not a standalone test script) is what's making the calls
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
- [ ] **OIA Clarifier retrain needed (2026-08-16) — the deployed "ready"
      signal doesn't fire.** See the regression finding in Phase 3 above for
      the full verification (4 independent ways, all failing, on verbatim
      training examples). Not started — root cause of *why* it regressed
      past the previously-claimed passing tests is also unconfirmed and
      should be figured out before just re-running the same recipe (was it
      a fluke checkpoint choice sensitive to exact eval examples, a
      mislabeled/overwritten GGUF, or something else?). Blocks `oia_subgraph`
      actually looping/skipping correctly (Phase 3's last 3 unchecked
      items) — those can still be built against the documented contract in
      the meantime, but won't behave correctly against the live model until
      this lands.

## Deferred

- [ ] Generic public-facing submission frontend — design done, see
      `FRONTEND_PLAN.md`. Build still holds until Phase 4 passes (needs the
      `interrupt_before` API contract that plan depends on).
