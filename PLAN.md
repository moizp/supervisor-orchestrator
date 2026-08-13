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
      2026-07-30, no exceptions for existing users. Hosting decision is
      open again — see Phase 5.

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

- [ ] Confirm `wellington-impact-lab`'s
      `POST /events/community-report/clarify` and
      `POST /events/{id}/clarification-answer` are reachable (local, then
      Cloud Run)
- [ ] Rebuild `ask → act → aggregate → triage` as its own LangGraph
      subgraph, calling those endpoints over HTTP (no import of
      `wellington-impact-lab` source)
- [ ] Compile and expose as a single node the parent graph can call

## Phase 3 — OIA subgraph

- [ ] Confirm OIA project's Clarifier + Classifier interfaces
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

- [ ] Parent graph: `router_node` → conditional edge →
      `{hazard_subgraph, oia_subgraph}` → `END`
- [ ] End-to-end test: 1 hazard submission, 1 well-formed OIA (skips
      straight to classify), 1 vague OIA (loops clarify at least once)

## Phase 5 — Deployment

- [ ] Router model hosting, for real (open again). Leading candidate:
      self-host like the other four (skip fine-tune/fuse,
      `convert_hf_to_gguf.py` → quantize → `llama-cpp-python`)
- [ ] Hosting for this orchestrator service — its own Cloud Run service,
      separate from both source deployments
- [ ] Containerize, deploy, confirm reachability to both source APIs
      (CORS/networking)

## Deferred

- [ ] Generic public-facing submission frontend — hold until Phase 4
      passes.
