# LeadRadar task status

Snapshot of `origin/main` at `fbae926` (2026-09-26), checked against the code rather than the checkboxes in `implementation-plan.md`, which are out of date. Merge conflicts between branches are ignored here.

**Legend:** ✅ Done · 🟡 Partial (some parts on `main`, some missing) · 🔵 In progress (on a branch, not on `main`) · ⬜ To do

## Summary

| Status | Tasks |
|---|---|
| ✅ Done | T01, T02, T03, T08, T09, T13, T20 |
| 🟡 Partial | T04, T05, T06, T07, T10, T11, T17, T18, T19, T22, T23 |
| 🔵 In progress | T12 |
| ⬜ To do | T14, T15, T16, T21, T24 |
| People / decisions | H1 mostly done; H2–H6, G7, OpenRouter key endpoint, feature-file questions and the P0 release gate all open |

## Phase 0 — Foundation

| # | Task | Issue | Status | Notes |
|---|---|---|---|---|
| T01 | Runtime stack and the whole SQL store | #10 closed | ✅ | Compose stack, package skeleton, JSON logs, `/health`, full migration. AC-57 and AC-67 acceptance tests present. |
| T02 | Sign-in, sessions, roles, CSRF, users API, audit writer | #11 closed | ✅ | Auth and users routes; acceptance tests AC-52 to AC-55. |
| T03 | Application shell, Sign in and Users screens | #12 closed | ✅ | Shell, shared components, Sign in, Users. |

## Phase 1 — Configuration and accounts

| # | Task | Issue | Status | Notes |
|---|---|---|---|---|
| T04 | Services, questions, scoring drafts, industries, markets | #13 closed | 🟡 | **API done.** The Services and Service editor screens were merged, then lost when `main` was merged into `claude/dazzling-planck-exnsmx` (`5a74ba9`); they are not on `main`. |
| T05 | Accounts, CSV import, account profile | #14 closed | 🟡 | **API done** (list, get, create, update, import). The Accounts, Import and Account profile screens were lost in the same merge. |
| T06 | Job queue, run lifecycle, Runs screen | #15 closed | 🟡 | **Queue, run lifecycle, runs/cancel/refresh API done.** The Runs screen was lost in the same merge. |
| T07 | Seed the demo dataset | #16 closed | 🟡 | `make seed-demo`, `make refresh-demo` and `fixtures/demo_accounts.csv` exist. A refresh can't produce findings until the FETCH and PROCESS steps exist (T10). |

## Phase 2 — The pipeline

| # | Task | Issue | Status | Notes |
|---|---|---|---|---|
| T08 | Scoring rules, rescoring, scoring activation | #17 closed | ✅ | Pure scoring rules, the SCORE step, the activate API. |
| T09 | AI gateway: classifiers, OpenRouter, budget, record/replay | #18 closed | ✅ | `leadradar/ai/` (classifier, OpenRouter, embedder, fixtures, budget guard). T11 added a second, replay-only gateway under `worker/ai/`; the two should be merged into one. |
| T10 | Free-core plug-ins, passages, embeddings, Source plug-ins screen | #19 open | 🟡 | **On `main`:** careers, GDELT, RSS and website adapters, crawl pacing, normalisation, chunking, embedder client, source-plugins API. **Missing:** FETCH and PROCESS worker steps, question-scoped passage selection (S-ING-04), the Source plug-ins screen. |
| T11 | Triage, classification, escalation, evidence | #20 open | 🟡 | **SIGNAL step merged** (PR #47) and registered in the queue, with integration tests. It classifies every stored passage until T10's selection lands, and its gateway is replay only. The AC-20–AC-26 acceptance tests are in open PR #48 and skip until a full refresh works. |
| T12 | Reclassify after a question change | #21 open | 🔵 | On `feat/reclassify`, not merged. Adds `queue_reclassify`, the reclassify SIGNAL job and the hand-off to SCORE. On `main`, a question change still queues no `RECLASSIFY` run. |
| H4 | Record the demo recording | #22 open | ⬜ | Needs H2 and a working refresh (T10–T12). |

## Phase 3 — Product surface and release gate

| # | Task | Issue | Status | Notes |
|---|---|---|---|---|
| T13 | Prospects and Account detail screens | #23 closed | ✅ | Prospects ranking, drawer, account detail with Why and Signals tabs, evidence, exception dialog. |
| T14 | Labelling and Quality report | #24 open | ⬜ | No label queue, quality check, `make seed-labels` or screens. |
| H5 | Label and decide | #25 open | ⬜ | Needs T14. |
| T15 | Refresh target, degradation, retention, accessibility | #26 open | ⬜ | Not started. |
| Gate | P0 release gate | #40 open | ⬜ | Blocked on T10–T12, T14, T15, H4, H5 and the lost screens (T04–T06). |

## Phase 4 — P1

| # | Task | Issue | Status | Notes |
|---|---|---|---|---|
| T16 | Try it and Preview impact | #27 open | ⬜ | No preview routes or UI. |
| T17 | Impact panel | #28 closed | 🟡 | `GET /impact` is on `main`; no Impact panel in the web app. |
| T18 | Lead and signal feedback | #29 closed | 🟡 | Feedback API on `main`; no feedback controls in the web app. |
| T19 | History tab and alerts | #30 closed | 🟡 | Score history and alerts/acknowledge API on `main` (merged as partial #30); no History tab or Alerts screen. |
| T20 | Scheduled refresh | #31 closed | ✅ | `worker/scheduler.py` enqueues due refreshes. |
| T21 | Contacts and outreach composer | #32 open | ⬜ | Nothing on `main`. |
| T22 | Source detection, enrichment, discovery | #33 closed | 🟡 | Rules and discovery core on `main` (merged as partial #33). No DISCOVER step, discovery routes or Suggested accounts screen. |
| T23 | Audit log screen, escalation target, scale-out | #34 closed | 🟡 | Audit log screen and API done; the queue uses `SKIP LOCKED`, so scale-out works in principle. The escalation-rate target (N-03) exists only as a stored column. |
| H6 | Usability walkthrough | #35 open | ⬜ | |

## Phase 5 — P2

| # | Task | Issue | Status | Notes |
|---|---|---|---|---|
| T24 | HubSpot push | #36 open | ⬜ | Blocked on the open HubSpot properties question. |

## People tasks and decisions

| Item | Issue | Status | Notes |
|---|---|---|---|
| H1 Demo account file | #7 open | 🟡 | `fixtures/demo_accounts.csv` has 20 accounts on `main`; the issue is still open, so check it's complete and close it. |
| H2 OpenRouter setup | #8 open | ⬜ | Blocks live AI calls and H4. |
| H3 EU cloud machine | #9 open | ⬜ | Blocked on G7. |
| G7 HTTPS on the demo machine | #37 open | ⬜ | |
| OpenRouter key endpoint | #38 open | ⬜ | |
| Open questions in feature files | #39 open | ⬜ | |

## Open pull requests

- [Nichita111/OrangeLeadRadar#48](https://github.com/Nichita111/OrangeLeadRadar/pull/48): acceptance tests for triage, classification and evidence (`feat/signal-triage`).
- [Nichita111/OrangeLeadRadar#44](https://github.com/Nichita111/OrangeLeadRadar/pull/44): frontend foundation, contract stubs, landing and demo sign-in spec.

## Biggest blockers on the path to P0

1. **FETCH and PROCESS worker steps and passage selection (T10).** Without them no refresh produces findings, so every pipeline acceptance test (AC-20–AC-26, AC-73) and the demo recording are blocked.
2. **The configuration, accounts and runs screens lost in merge `5a74ba9`.** Restore them from commits `1b89bfc` and `4254734`, adapted to the current shell.
3. **T12 (reclassify)** is ready on `feat/reclassify` and needs merging; then the question API must call `queue_reclassify` so AC-03 can pass.
4. **T14 and T15**, then H2, H4 and H5, before the release gate.
