# Plan

Build checklist for the supervisor-orchestrator prototype. See `README.md`
for the architecture this implements.

## Phase 0 — Router model hosting investigation (done)

- [x] Evaluate Hugging Face Inference Providers' free tier for hosting a
      zero-shot base-model router call. Found: free accounts get $0.10/month
      in credits (PRO: $2/month) — but moot regardless, since
      `Phi-3.5-mini-instruct` is not currently deployed by any Inference
      Provider on HF at all (confirmed directly on the model page: "This
      model isn't deployed by any Inference Provider").
- [x] Evaluate Azure AI Foundry. Found: Phi-3.5-mini-instruct is in the
      model catalog, deployable as a pay-as-you-go serverless endpoint, but
      there is no standing free tier for it specifically — only the
      general, time-limited new-account Azure credit.
- [x] Evaluate GitHub Models. Found: hosts Phi-3.5-mini-instruct directly,
      genuinely free, no credit card, rate-limited to ~50-150 requests/day
      depending on tier. **Chosen** as the router's model host.

## Phase 1 — Router

- [ ] Set up repo scaffolding: `requirements.txt` (langgraph, httpx),
      `.env.example` (`GITHUB_MODELS_TOKEN`, `HAZARD_API_BASE`,
      `OIA_API_BASE`)
- [ ] Implement `router_node`: zero-shot prompt to GitHub-Models-hosted
      Phi-3.5-mini-instruct, classifying `raw_text` as `hazard` or `oia`
- [ ] Write a small set of sample hazard/OIA submissions and sanity-check
      the router's accuracy against them before wiring it into the graph

## Phase 2 — Hazard subgraph (reuse existing pipeline)

- [ ] Confirm `wellington-impact-lab`'s
      `POST /events/community-report/clarify` and
      `POST /events/{id}/clarification-answer` endpoints are reachable
      (local dev first, then the deployed Cloud Run URL)
- [ ] Rebuild the hazard graph (`ask → act → aggregate → triage`) as its own
      LangGraph subgraph, calling the endpoints above over HTTP instead of
      importing `app.*` modules directly (keeps this repo from needing
      `wellington-impact-lab`'s source at all)
- [ ] Compile the hazard subgraph and expose it as a single node the parent
      graph can call

## Phase 3 — OIA subgraph

- [ ] Locate and confirm the OIA project's Clarifier + Classifier
      interfaces (endpoints or module signatures, output formats)
- [ ] **Improve the OIA Clarifier's training data** so its `ask` output can
      signal readiness instead of always asking a question — add rows where
      the target output is `Question: none — ready to classify` for
      already-well-formed requests, alongside the existing "ask a real
      question" rows for vague ones
- [ ] Retrain / re-fuse / re-export the OIA Clarifier on the updated dataset
      (same fine-tune → fuse → GGUF → quantize pipeline as the hazard
      project's models)
- [ ] Validate the retrained Clarifier's output round-trips cleanly through
      a `parse_oia_ask_output()`-style parser before wiring it in
- [ ] Build the `oia_supervisor` mini-graph: `oia_clarify` → conditional
      edge (parsed "ready" flag, or a hard cap of 2 clarify attempts) →
      loop back to `oia_clarify` or advance to `oia_classify`
- [ ] Wire the OIA subgraph's nodes to call the OIA project's endpoints
      over HTTP

## Phase 4 — Supervisor graph assembly

- [ ] Parent graph: `router_node` → conditional edge →
      `{hazard_subgraph, oia_subgraph}` → `END`
- [ ] End-to-end test: one sample hazard submission, one well-formed OIA
      submission (should skip straight to classify), one vague OIA
      submission (should loop clarify at least once)

## Phase 5 — Deployment

- [ ] Decide hosting for this orchestrator service — its own Cloud Run
      service, separate from both source projects' deployments
- [ ] Containerize, deploy, confirm it can reach both source APIs from
      wherever it's hosted (CORS/networking, same category of issue
      `wellington-impact-lab` hit early with its own deploy)

## Deferred / open questions

- [ ] **Generic public-facing submission frontend.** Not started —
      deliberately deferred until the orchestration logic itself is proven
      via a CLI/script test harness (Phase 4), the same way
      `wellington-impact-lab`'s hazard graph was first validated with a
      standalone script before any UI question came up. Revisit once
      Phase 4 passes.
