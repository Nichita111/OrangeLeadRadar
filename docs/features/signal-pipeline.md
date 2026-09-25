---
type: Feature
title: Signal pipeline
description: How an account refresh turns public sources into findings and scores - fetch, normalise, triage, classify with the fast classifier, escalate the uncertain, quote the evidence, score - on demand, on schedule, after a question change and after a scoring change, with the Runs and Source plug-ins screens.
status: draft
tags: [signal-pipeline]
---

# Signal pipeline

## Purpose

The pipeline is where public information becomes evidence. For each account it gathers what the enabled sources published recently, keeps each item once, checks which items are really about the account and relevant to a service, asks each relevant passage every applicable signal question through the fast classifier, sends only the uncertain answers to the LLM, and keeps every positive answer as a finding with a verbatim quote. It then recomputes the account's scores. It runs on a schedule, on a user's request with live progress, after a question changes and after scoring or data changes, and it reports exactly what failed without faking what it could not obtain.

## Flows

### FL-07 Refresh one account

```mermaid
sequenceDiagram
  actor Sales
  participant Web as Account detail
  participant API as api
  participant DB as database
  participant W as worker
  participant P as source plug-ins
  participant E as embedder
  participant C as classifier (Jev or LLM)
  participant L as OpenRouter LLM
  Sales->>Web: Refresh now
  Web->>API: refresh (API-33)
  API->>DB: run QUEUED with one FETCH job per available plug-in
  loop per plug-in
    W->>P: fetch within the window and caps
  end
  W->>W: normalise, drop duplicates, chunk
  W->>E: embed passages
  W->>C: triage each new document
  W->>C: classify selected passages, all applicable questions per call
  alt p_positive in the escalation band
    W->>L: escalate: verdict, quote, rationale
  else confident positive
    W->>L: extract evidence: quote, translation, rationale
  end
  W->>DB: findings; then scores for every active service; alerts
  loop every RUN_POLL_INTERVAL_MS
    Web->>API: run progress (API-35)
  end
```

1. A refresh starts from Refresh now on [Account detail](/features/prospect-dashboard.md#account-detail) or from the scheduler; a second request while one is queued or running returns the same run.
2. Each available plug-in fetches within the [Fetch window](/architecture/rules.md#fetch-window); a failing plug-in is recorded and the others continue.
3. [Document normalisation](/architecture/rules.md#document-normalisation) stores each new item once; [Chunking and passage selection](/architecture/rules.md#chunking-and-passage-selection) keeps a short item whole, splits a long one at its sections, and embeds every passage; each question then retrieves its own passages of a long document by keyword and by meaning.
4. The [signal graph](/architecture/services/worker.md#signal-graph) triages, classifies, escalates and extracts evidence, resuming the account's pairs left waiting by an earlier run.
5. The `SCORE` stage rescores every active service of the account and raises alerts.
6. The run ends `SUCCEEDED`, `PARTIAL` with its reasons, or `FAILED`.

### FL-08 Scheduled refresh cycle

1. Every `SCHEDULER_TICK_S` the scheduler enqueues refreshes of active accounts that are due, oldest first, at most `SCHEDULER_MAX_ENQUEUE` per tick, never a second one for an account ([Refresh scheduling](/architecture/rules.md#refresh-scheduling)).
2. Each runs as [FL-07](#fl-07-refresh-one-account) with trigger `SCHEDULE` and a lower priority than a user's request.
3. When it finishes, the account's next refresh is set `REFRESH_INTERVAL_HOURS` later.
4. Once a day the housekeeping applies [Retention and erasure](/architecture/rules.md#retention-and-erasure).

### FL-09 Reclassify after a question change

1. A question is created, reactivated or gets a new revision ([FL-01](/features/service-configuration.md#fl-01-define-a-service-and-its-signal-questions)).
2. A `RECLASSIFY` run supersedes the question's older findings, completes triage for the service where missing, and classifies the stored passages of the service's accounts for this question only ([Reclassification](/architecture/rules.md#reclassification)).
3. It ends by rescoring the service. Nothing is fetched.

### FL-10 Rescore after a scoring or data change

1. A scoring version is activated ([FL-02](/features/service-configuration.md#fl-02-edit-and-activate-scoring-settings)), an account attribute changes ([FL-05](/features/accounts-and-discovery.md#fl-05-maintain-an-account-and-its-contacts)), feedback is given ([FL-15](/features/evaluation-and-feedback.md#fl-15-give-feedback-on-a-lead-or-a-signal)) or an exception is added or revoked ([FL-13](/features/prospect-dashboard.md#fl-13-override-a-disqualifier)).
2. A `RESCORE` run recomputes the affected scores from stored findings ([Rescoring](/architecture/rules.md#rescoring)); a changed result becomes the new current score, the old one stays as history, and alerts are raised.

## Reading order

1. Terms in the [glossary](/requirements/glossary.md): Run, Account refresh, Source plug-in, Free core, Document, Passage, Source type, Triage, Classifier, Classification, Escalation, Escalation band, Finding, Strength, Evidence quote, Question revision, Budget guard, Rescore, Alert.
2. Requirement rows: `S-ING-01` to `S-ING-06`, `S-SIG-01` to `S-SIG-09`, `S-PIP-01` to `S-PIP-05`, `S-SCO-01` to `S-SCO-08`, `S-RUN-02` in [system requirements](/requirements/system.md); `N-02`, `N-03`, `N-04`, `N-05`, `N-06`, `N-09`, `N-11`; `B-05`, `B-11` to `B-20`, `B-33`, `B-36`, `B-37`, `RULE-01` to `RULE-03`, `RULE-05`, `RULE-08` in [business requirements](/requirements/business.md).
3. Stores: [`source_plugin`](/architecture/sql-store.md#source_plugin), [`plugin_usage`](/architecture/sql-store.md#plugin_usage), [`pipeline_run`](/architecture/sql-store.md#pipeline_run), [`job`](/architecture/sql-store.md#job), [`document`](/architecture/sql-store.md#document), [`chunk`](/architecture/sql-store.md#chunk), [`document_triage`](/architecture/sql-store.md#document_triage), [`classification`](/architecture/sql-store.md#classification), [`finding`](/architecture/sql-store.md#finding), [`account_score`](/architecture/sql-store.md#account_score), [`alert`](/architecture/sql-store.md#alert), [`account_source`](/architecture/sql-store.md#account_source), the `AI_CALL` payload of [Audit actions](/architecture/sql-store.md#audit-actions).
4. Rules: in pipeline order, [Refresh scheduling](/architecture/rules.md#refresh-scheduling), [Plug-in availability](/architecture/rules.md#plug-in-availability), [Fetch window](/architecture/rules.md#fetch-window), [Source detection](/architecture/rules.md#source-detection), [Account attributes](/architecture/rules.md#account-attributes), [Document normalisation](/architecture/rules.md#document-normalisation), [Chunking and passage selection](/architecture/rules.md#chunking-and-passage-selection), [Triage](/architecture/rules.md#triage), [Signal classification](/architecture/rules.md#signal-classification), [Escalation](/architecture/rules.md#escalation), [Evidence extraction](/architecture/rules.md#evidence-extraction), [Budget guard](/architecture/rules.md#budget-guard), [Reclassification](/architecture/rules.md#reclassification), then scoring: [Recency decay](/architecture/rules.md#recency-decay), [Fit score](/architecture/rules.md#fit-score), [Intent score](/architecture/rules.md#intent-score), [Disqualification](/architecture/rules.md#disqualification), [Priority, standing and band](/architecture/rules.md#priority-standing-and-band), [Score breakdown](/architecture/rules.md#score-breakdown), [Rescoring](/architecture/rules.md#rescoring), [Alerts](/architecture/rules.md#alerts), [Retention and erasure](/architecture/rules.md#retention-and-erasure) and the [Examples](/architecture/rules.md#examples).
5. Interfaces: [Runs and source plug-ins](/architecture/interfaces.md#runs-and-source-plug-ins) (`API-33` to `API-38`), [Classifier](/architecture/interfaces.md#classifier) (`API-62`), [LLM](/architecture/interfaces.md#llm) (`API-63`, `API-64`), [Embedder](/architecture/interfaces.md#embedder) (`API-67`), [Source plug-ins](/architecture/interfaces.md#source-plug-ins) (`API-68`).
6. Services: the [worker](/architecture/services/worker.md) — job queue, run lifecycle, signal graph, AI gateway, source plug-ins, scheduler, runtime keys; the [api](/architecture/services/api.md) for enqueueing; the frontend's [Polling](/architecture/services/frontend.md#polling); in the [architecture overview](/architecture/overview.md), [AI roles and boundaries](/architecture/overview.md#ai-roles-and-boundaries), [Degradation](/architecture/overview.md#degradation), fixture mode under [Runtime](/architecture/overview.md#runtime) and the [demo dataset](/architecture/overview.md#demo-dataset).
7. Decisions: [ADR-01](/architecture/adrs/adr-01-one-postgresql-store.md), [ADR-02](/architecture/adrs/adr-02-classification-cascade.md), [ADR-03](/architecture/adrs/adr-03-models-answer-rules-score.md), [ADR-04](/architecture/adrs/adr-04-postgres-job-queue-and-a-worker.md), [ADR-05](/architecture/adrs/adr-05-langgraph-only-for-the-signal-graph.md), [ADR-06](/architecture/adrs/adr-06-rule-based-scoring-with-versioned-settings.md), [ADR-07](/architecture/adrs/adr-07-source-plug-ins-with-a-free-core.md), [ADR-08](/architecture/adrs/adr-08-multilingual-embeddings.md), [ADR-09](/architecture/adrs/adr-09-findings-per-passage-and-question-revision.md), [ADR-11](/architecture/adrs/adr-11-recorded-fixtures.md), [ADR-13](/architecture/adrs/adr-13-run-progress-by-polling.md), [ADR-15](/architecture/adrs/adr-15-openrouter-as-the-llm-provider.md), [ADR-16](/architecture/adrs/adr-16-question-scoped-hybrid-passage-selection.md), [ADR-19](/architecture/adrs/adr-19-source-provider-terms-and-limits.md).
8. Screens: [Runs](#runs), [Source plug-ins](#source-plug-ins); Refresh now on [Account detail](/features/prospect-dashboard.md#account-detail).
9. Acceptance rows in [acceptance criteria](/requirements/acceptance.md): `AC-03`, `AC-04`, `AC-06`, `AC-11`, `AC-16` to `AC-40`, `AC-49`, `AC-58`, `AC-61` to `AC-64`, `AC-66`, `AC-69` to `AC-73`.

## Runs

Route `/runs`. Any signed-in user; cost and technical counters are shown to Admins only.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Runs    Kind ▾   Status ▾   Account [ … ]                                    │
├──────────────────┬────────────────────┬──────────┬───────────┬───────────────┤
│ Kind             │ Subject            │ Started  │ Status    │ Progress      │
├──────────────────┼────────────────────┼──────────┼───────────┼───────────────┤
│ Account refresh  │ DHL Group          │ 1 min ago│ Running   │ Checking passages 40/60 │
│ Account refresh  │ Lufthansa Group    │ 1 h ago  │ Partial   │ GDELT failed · 3 waiting │
│ Rescore          │ Intelligent Autom. │ 2 h ago  │ Succeeded │ 20 accounts   │
└──────────────────┴────────────────────┴──────────┴───────────┴───────────────┘
┌ DHL Group · Account refresh · by Ana Sales ─────────────────────────────────┐
│ Fetch ✓  Process ✓  Triage ✓  Classify ●  Evidence ○  Score ○                │
│ 25 fetched · 21 new · 9 kept · 60 passages · 7 detailed checks · 5 signals   │
│ Errors: none                            AI cost €0.41 (Admin)   [ Cancel ]   │
└──────────────────────────────────────────────────────────────────────────────┘
```

WF-10 — Runs

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-054` | The screen shall list runs newest first with kind, subject (account, service or question), trigger, requester, start time, duration, status and a one-line progress summary, filtered by kind, status and account. |
| `FR-055` | Selecting a run shall show its stages in order with done, current and pending marks, its counters in plain words, and each error with its stage and plug-in; an Admin also sees the run's AI cost. |
| `FR-056` | A `PARTIAL` run shall say why in one line: which plug-ins failed and how many signals are waiting for the next refresh. |
| `FR-057` | Cancel shall be offered on a queued or running run — to Admins only for reclassification, rescore and quality-check runs — and confirm that running steps finish first. |
| `FR-058` | A live run shall update by polling as the frontend's [Polling](/architecture/services/frontend.md#polling) states. |

Obligations: `S-PIP-01`, `S-PIP-03`, `S-SIG-08`.

**Data**: `API-34`, `API-35`, `API-36`. **States**: [States](/architecture/services/frontend.md#states).

## Source plug-ins

Route `/settings/source-plugins`. Admin only.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Source plug-ins                                                              │
├────────────┬───────────┬─────────┬─────────┬─────────────┬──────────┬────────┤
│ Plug-in    │ Needs key │ Key     │ Enabled │ Today/quota │ Per min  │ Last error │
├────────────┼───────────┼─────────┼─────────┼─────────────┼──────────┼────────┤
│ GDELT      │ no        │ —       │ [on]    │ 120 / —     │ 30       │ —      │
│ Crunchbase │ yes       │ missing │ [on]    │ 0 / 200     │ 20       │ —      │
│ NewsAPI    │ yes       │ set     │ [off]   │ 0 / 100     │ 10       │ —      │
└────────────┴───────────┴─────────┴─────────┴─────────────┴──────────┴────────┘
```

WF-11 — Source plug-ins

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-059` | The screen shall list every plug-in with whether it needs a key, whether the key is configured, the enabled switch, whether it is available now, requests today against the daily quota, the per-minute limit, the last success and the last error. |
| `FR-060` | A plug-in whose key is missing shall say that it stays unavailable until the key is set in the deployment's configuration, whatever the switch says. |
| `FR-061` | The switch and the limits shall save immediately and apply from the next fetch. |
| `FR-143` | Each plug-in row shall say in words what it reads, and its availability shall be one of Available, Switched off, or Unavailable with the reason, such as the key being missing. |

Obligations: `S-PIP-05`, `S-ING-01`.

**Data**: `API-37`, `API-38`. **States**: [States](/architecture/services/frontend.md#states).

## Open questions

- Jev's language coverage is not published; the quality check on the labelled set, which includes German passages, decides whether `CLASSIFIER_PROVIDER` becomes `JEV`. Decides: the team.
- Whether each demo account's careers source is one of the supported applicant-tracking hosts or needs crawling. Missing: the recording. Decides: the team while recording fixtures.
