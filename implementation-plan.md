# LeadRadar implementation plan

Build order for LeadRadar, following the data flow: configuration → accounts → pipeline → scores → screens. The P0 release gate is reached at the end of Phase 3, before any P1 work.

**Status marks:** `[x]` done · `[~]` in progress · `[ ]` not started. Last updated 2026-09-26.

## How to run it

- **One task per line.** Each numbered line is one `/implement` run. It stops twice for your approval (the design, then the docs diff) and commits on its own branch. Merge that branch to `main` before starting the next task.
- **One task at a time per checkout.** The approval gate is a single `.work/gate.json`. To run a backend lane and a frontend lane in parallel, give each its own worktree.
- **People tasks.** Lines marked **H** are for people, not the chain.

## Done before implementation

- [x] Specification in `docs/`, checker clean: 58 files, 0 findings.
- [x] Agent chain in `.claude/` (Architect → Coder → QA → Critic), with the guard hook and `/implement`.
- [x] PRs #1 to #6 reviewed, fixed and merged.
- [x] README with the architecture and per-flow diagrams, plus the drift check (`python3 diagrams/flows.py --check`).
- [x] Pre-implementation review: 22 gaps and contradictions fixed (merge `b418a1d`).

## Start now (people)

- [ ] **H1 Demo account file.** For each of the 20 demo accounts, collect the careers, newsroom, investor-relations and RSS addresses, the employee count and the operational complexity. They go in `fixtures/demo_accounts.csv`.
- [ ] **H2 OpenRouter setup.** An API key, the three model ids (`LLM_CLASSIFIER_MODEL`, `LLM_EVIDENCE_MODEL`, `LLM_OUTREACH_MODEL`) and the daily budget.
- [ ] **H3 An EU cloud machine** for the demo and for AC-57. Decide first how it serves HTTPS (gap G7).

## Phase 0: Foundation

- [~] **1. `/implement S-RUN-01 N-12`, with the whole SQL store as the first migration**, on branch `feat/runtime-stack-foundation`. It builds:
  - the Docker Compose stack (web, api, worker, db, embedder);
  - the `leadradar` package skeleton, JSON logs and `/health`;
  - the whole SQL store as one migration, with models for all 31 tables;
  - the web proxy.

  Progress:
  - [x] Design approved (gaps G1–G8 decided)
  - [x] Docs approved
  - [x] Built: `poe validate` with 97 tests, and `npm run validate`
  - [ ] Free Docker memory: 12 GB or more, or stop other projects' containers. The embedder was killed for lack of memory.
  - [ ] QA runs AC-57 and AC-67
  - [ ] Critic review
  - [ ] Committed and merged
- [ ] **2. `/implement S-SEC-01 S-SEC-02 S-SEC-03 N-07 S-AUD-01`.** Sign-in, sessions, roles, CSRF, the users API, and the audit writer every later task uses. After 1.
- [ ] **3. `/implement the application shell, Sign in and Users`.** Design tokens, shared components, loading/empty/error states, motion, polling, the generated API client, and those two screens. After 2.

## Phase 1: Configuration and accounts

- [ ] **4. `/implement S-CFG-01 S-CFG-02 S-CFG-03 S-CFG-07 and their screens`.** Services, questions, scoring drafts, industries and markets, with their four screens. Try it and Preview impact come later. After 3.
- [ ] **5. `/implement S-ACC-01 S-ACC-02 S-ACC-03 S-ACC-05 and their screens`.** Accounts, CSV import, the account profile. Contacts come later. After 3.
- [ ] **6. `/implement S-PIP-01 S-PIP-03 S-PIP-04 N-05 and the Runs screen`.** Job queue, run lifecycle, retries, cancellation, Refresh now. After 1.
- [ ] **7. `/implement S-RUN-03`.** `make seed-demo` and `make refresh-demo`. Loading labels (`make seed-labels`) is finished in task 14. After 4, 5 and 6.

## Phase 2: The pipeline

- [ ] **8. `/implement S-SCO-01 S-SCO-02 S-SCO-03 S-SCO-04 S-SCO-05 S-SCO-06 S-SCO-07 S-SCO-08 S-CFG-04 N-04`.** Pure scoring rules with the worked examples as unit tests, the scoring stage, rescoring, activating a scoring version. After 6.
- [ ] **9. `/implement S-RUN-02 S-SIG-04 S-SIG-08`.** The AI gateway:
  - Jev and LLM classifier adapters;
  - the OpenRouter adapter with versioned prompts;
  - budget guard, record/replay, `CLOCK_FILE`, AI-call audit rows.

  Expect the design to add the fixture file format to the docs. After 6 and H2.
- [ ] **10. `/implement S-ING-01 S-ING-02 S-ING-03 S-ING-04 S-PIP-05 N-09 and the Source plug-ins screen`.** Free-core plug-ins, crawl etiquette, deduplication, passages, embeddings, passage selection. This task also settles gap G6: the seeded `source_plugin` values. After 9.
- [ ] **11. `/implement S-SIG-01 S-SIG-02 S-SIG-03 S-SIG-05 S-SIG-06 S-SIG-09`.** Triage, classification, escalation, evidence: the first full refresh, with findings. After 8 and 10.
- [ ] **12. `/implement S-SIG-07`.** Reclassification after a question change. After 11.
- [ ] **H4 Record the demo recording.** Run `make seed-demo` and `make refresh-demo` with `FIXTURE_MODE=record`. Needs H1, H2 and task 12.
  - Criteria that need findings from real documents can go green only after this recording exists.
  - That includes AC-34, AC-35 and AC-37 from task 8.

## Phase 3: The product surface and the release gate

- [ ] **13. `/implement S-PRO-01 S-PRO-02 S-PRO-03 S-PRO-05 N-01 and the Prospects and Account detail screens`.** The ranking, the account drawer, the explanation, evidence, exceptions. After 11.
- [ ] **14. `/implement S-EVL-03 S-EVL-04 and the Labelling and Quality report screens`.** Label queue, quality check, `make seed-labels`, and the label export. After 11.
- [ ] **H5 Label and decide.** Label at least 200 passages, export them, record a quality check under each classifier adapter, and choose `CLASSIFIER_PROVIDER` from the results.
- [ ] **15. `/implement N-02 N-06 N-08 N-10`.** Refresh-time target, degradation, retention housekeeping, accessibility. After 13 and 14.
- [ ] **Release gate.** Every P0 criterion plus scenarios SC-A to SC-D, in replay mode, then AC-57 on the EU machine. **P0 is done here.**

## Phase 4: P1, in order of demo value

- [ ] **16. `/implement S-CFG-05 S-CFG-06`.** Try it and Preview impact: demo steps 5–6.
- [ ] **17. `/implement S-EVL-05`.** The Impact panel: the demo's closing sentence (step 9).
- [ ] **18. `/implement S-EVL-01 S-EVL-02`.** Lead and signal feedback.
- [ ] **19. `/implement S-PRO-04 S-PRO-06 and the Alerts screen`.** The History tab and alerts.
- [ ] **20. `/implement S-PIP-02`.** Scheduled refresh.
- [ ] **21. `/implement S-ACC-04 S-OUT-01`.** Contacts and the outreach composer.
- [ ] **22. `/implement S-ING-05 S-ING-06 S-DSC-01 S-DSC-02 and the Suggested accounts screen`.** Source detection, profile enrichment, discovery. Afterwards, record the discovery recording that AC-14 uses.
- [ ] **23. `/implement S-AUD-02 N-03 N-11`.** The audit log screen, the escalation-rate target, scaling to several workers.
- [ ] **H6 Usability walkthrough** with two sales managers: AC-68 (N-13).

## Phase 5: P2

- [ ] **24. `/implement S-OUT-02`.** HubSpot push. Before starting, settle the open question of who creates the `leadradar_*` properties in HubSpot.

## Open decisions to watch

- **G7:** how HTTPS is served on the demo cloud machine. Decide before AC-57 runs there.
- **OpenRouter key endpoint:** `GET /api/v1/key`, used by the health check, is unverified. Confirm it before running against live OpenRouter.
- **Open questions in the feature files:**
  - the Sales Navigator import columns;
  - Jev's language coverage;
  - the careers-page hosts;
  - who does the labelling;
  - the HubSpot properties.
