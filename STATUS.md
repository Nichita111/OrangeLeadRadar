# LeadRadar task status

Snapshot of `origin/main` at `cae7e7d` (2026-09-27), checked against the code rather than the checkboxes in `implementation-plan.md`, which are out of date. GitHub issue and pull-request states were checked on 2026-09-27. A closed issue does not by itself mean every part of its task is on `main`; work on a branch does not count as done on `main`.

**Legend:** ✅ Done · 🟡 Partial (some parts on `main`, some missing) · 🔵 In progress (on a branch, not on `main`) · ⬜ To do

## Summary

| Status | Tasks |
|---|---|
| ✅ Done (8) | T01, T02, T03, T08, T09, T13, T20, T24 |
| 🟡 Partial (12) | T04, T05, T06, T07, T10, T11, T15, T17, T18, T19, T22, T23 |
| 🔵 In progress (1) | T12 |
| ⬜ To do (3) | T14, T16, T21 |
| People / decisions / gate | H1 partial; H2–H6, G7, OpenRouter key endpoint, feature-file questions and the P0 release gate to do |

Across **all 34 linked issues** (#7–#40), including the people tasks, decisions and release gate: **8 done, 13 partial, 1 in progress, 12 to do**. GitHub currently marks 17 closed and 17 open; tracker state is separate from implementation progress.

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
| T09 | AI gateway: classifiers, OpenRouter, budget, record/replay | #18 closed | ✅ | `leadradar/ai/` provides the shared gateway, classifier, OpenRouter, embedder, fixtures and budget guard. The duplicate `worker/ai/` gateway was removed in PR #49. |
| T10 | Free-core plug-ins, passages, embeddings, Source plug-ins screen | #19 open | 🟡 | **On `main`:** careers, GDELT, RSS and website adapters, crawl pacing, normalisation, chunking, embedder client, source-plugins API. **Missing:** FETCH and PROCESS worker steps, question-scoped passage selection (S-ING-04), the Source plug-ins screen. |
| T11 | Triage, classification, escalation, evidence | #20 open | 🟡 | The SIGNAL step is on `main`, registered in the queue and uses the shared AI gateway. It classifies stored passages without T10's question-scoped selection. AC-20–AC-26 acceptance tests are on `main` but cannot run through a complete refresh until FETCH and PROCESS exist; PR #48 remains open. |
| T12 | Reclassify after a question change | #21 open | 🔵 | On `feat/reclassify`, not merged. Adds `queue_reclassify`, the reclassify SIGNAL job and the hand-off to SCORE. On `main`, a question change still queues no `RECLASSIFY` run. |
| H4 | Record the demo recording | #22 open | ⬜ | Needs H2 and a working refresh (T10–T12). |

## Phase 3 — Product surface and release gate

| # | Task | Issue | Status | Notes |
|---|---|---|---|---|
| T13 | Prospects and Account detail screens | #23 closed | ✅ | Prospects ranking, drawer, account detail with Why and Signals tabs, evidence, exception dialog. |
| T14 | Labelling and Quality report | #24 open | ⬜ | No label queue, quality check, `make seed-labels` or screens. |
| H5 | Label and decide | #25 open | ⬜ | Needs T14. |
| T15 | Refresh target, degradation, retention, accessibility | #26 open | 🟡 | Dependency error envelopes and some screen degradation and keyboard behaviour are implemented. No complete replay refresh to measure N-02, no document-retention housekeeping for N-08, and no full accessibility scan of every screen for N-10. |
| Gate | P0 release gate | #40 open | ⬜ | Blocked on T10–T12, T14, T15, H4, H5 and the lost screens (T04–T06). |

## Phase 4 — P1

| # | Task | Issue | Status | Notes |
|---|---|---|---|---|
| T16 | Try it and Preview impact | #27 open | ⬜ | No preview routes or UI. |
| T17 | Impact panel | #28 closed | 🟡 | `GET /impact` is on `main`; no Impact panel in the web app. |
| T18 | Lead and signal feedback | #29 closed | 🟡 | Feedback API on `main`; no feedback controls in the web app. |
| T19 | History tab and alerts | #30 closed | 🟡 | Score history and alerts/acknowledge API on `main` (merged as partial #30); no History tab or Alerts screen. |
| T20 | Scheduled refresh | #31 closed | ✅ | `worker/scheduler.py` enqueues due refreshes. |
| T21 | Contacts and outreach composer | #32 open | ⬜ | The SQL store has contact and outreach tables, but there are no contacts routes or outreach composer UI on `main`. |
| T22 | Source detection, enrichment, discovery | #33 closed | 🟡 | Rules and discovery core on `main` (merged as partial #33). No DISCOVER step, discovery routes or Suggested accounts screen. |
| T23 | Audit log screen, escalation target, scale-out | #34 closed | 🟡 | Audit log screen and API done; the queue uses `SKIP LOCKED`, so scale-out works in principle. The escalation-rate target (N-03) exists only as a stored column. |
| H6 | Usability walkthrough | #35 open | ⬜ | |

## Phase 5 — P2

| # | Task | Issue | Status | Notes |
|---|---|---|---|---|
| T24 | HubSpot push | #36 closed | ✅ | API-59 and the HubSpot search/update/create adapter, CRM sync and audit rows, settings, contract and integration tests are on `main` via PR #50. The docs assign creation of `leadradar_*` properties to the target portal's HubSpot administrator. |

## People tasks and decisions

| Item | Issue | Status | Notes |
|---|---|---|---|
| H1 Demo account file | #7 open | 🟡 | `fixtures/demo_accounts.csv` has 20 accounts, but several required employee counts, operational-complexity values and source URLs are blank. Complete and verify them before closing the issue. |
| H2 OpenRouter setup | #8 open | ⬜ | Blocks live AI calls and H4. |
| H3 EU cloud machine | #9 open | ⬜ | Blocked on G7. |
| G7 HTTPS on the demo machine | #37 open | ⬜ | |
| OpenRouter key endpoint | #38 open | ⬜ | |
| Open questions in feature files | #39 open | ⬜ | |

## Open pull requests

- [Nichita111/OrangeLeadRadar#48](https://github.com/Nichita111/OrangeLeadRadar/pull/48): acceptance tests for triage, classification and evidence (`feat/signal-triage`).
- [Nichita111/OrangeLeadRadar#44](https://github.com/Nichita111/OrangeLeadRadar/pull/44): frontend foundation, contract stubs, landing and demo sign-in spec.

PR #50 (HubSpot push) merged into `main` at `cae7e7d`.

## Biggest blockers on the path to P0

1. **FETCH and PROCESS worker steps and passage selection (T10).** Without them no refresh produces findings, so every pipeline acceptance test (AC-20–AC-26, AC-73) and the demo recording are blocked.
2. **The configuration, accounts and runs screens lost in merge `5a74ba9`.** Restore them from commits `1b89bfc` and `4254734`, adapted to the current shell.
3. **T12 (reclassify)** has implementation on `feat/reclassify`, but it is not on `main`; the question API must call `queue_reclassify` so AC-03 can pass.
4. **T14 and T15**, plus completing H1, H2, H4 and H5, before the release gate.
