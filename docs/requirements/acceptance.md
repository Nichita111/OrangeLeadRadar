---
type: Requirements
title: Acceptance criteria
description: The AC-nn criteria in Given / When / Then form that QA turns into acceptance and end-to-end tests, the pass criteria of the four business scenarios and the release gate they are read against.
status: draft
tags: [accounts-and-discovery, audit-trail, evaluation-and-feedback, identity-and-access, outreach-and-crm, prospect-dashboard, service-configuration, signal-pipeline]
---

# Acceptance criteria and release gate

## Acceptance criteria

Each criterion is written as Given / When / Then against the Compose deployment of `S-RUN-01`, in `FIXTURE_MODE` `replay` unless it says otherwise, seeded with the [demo dataset](/architecture/overview.md#demo-dataset). "The demo recording" is the fixture set the demo dataset names. Values quoted in a criterion are owned by the heading linked next to them; a configuration key stands for its default unless the criterion sets it. The clock is injected where a criterion depends on time. **Verifies** names the `S-`, `N-`, `B-` and `RULE-` rows the criterion covers; a criterion takes the highest priority of the rows it verifies. A criterion is tested through the product's public surface — its REST contracts or its screens — never by reading the implementation.

### Configuration

| ID | Criterion | Verifies |
|---|---|---|
| `AC-01` | Given an Admin, when they create a service with code `TEST_SERVICE`, then it is listed `ACTIVE` with a draft version 1 whose settings are the defaults of the [scoring settings document](/architecture/sql-store.md#scoring-settings-document); a second service with code `TEST_SERVICE` is refused `409 CONFLICT`, and a `PATCH` that carries `code` is refused `422 VALIDATION`. | `S-CFG-01` |
| `AC-02` | Given `CYBERSECURITY` set `INACTIVE`, when DHL Group is refreshed, then no triage row records a relevance for it, no classification exists for its questions from that refresh, the service is absent from `API-07`'s active services in the selector and `API-39` for it returns no row; when it is reactivated, one `RECLASSIFY` run per active question is queued. | `S-CFG-01` |
| `AC-03` | Given `COST_PROGRAM` at revision 1, when an Admin changes its text, then its revision is 2 and a `RECLASSIFY` run with trigger `QUESTION_CHANGE` is queued; when the Admin then changes only its hint terms, the revision stays 2 and no run is queued; a newly created question has revision 1, a queued `RECLASSIFY` run, and appears in the service's draft at weight `MEDIUM`. | `S-CFG-02`, `S-SIG-07` |
| `AC-04` | Given an Admin, when they create a `CHOICE` question none of whose options has strength `NONE`, or a question with no source type, then each is refused `422 VALIDATION` naming the field; a `PATCH` that carries `polarity` is refused `422 VALIDATION`. | `S-CFG-02` |
| `AC-05` | Given the Intelligent Automation draft, when an Admin saves settings with `fit_weight` 0.5 and `intent_weight` 0.6, `warm_threshold` 80 with `hot_threshold` 70, and a disqualifier whose `question_key` is `UNKNOWN_KEY`, then the save is refused `422 VALIDATION` with a field error at each offending JSON pointer, and the stored draft is unchanged. | `S-CFG-03` |
| `AC-06` | Given all demo accounts refreshed from the demo recording and a draft that raises `AUTOMATION_HIRING` to `HIGH`, when an Admin activates it with a change note, then the draft is `ACTIVE`, the previous version `RETIRED`, and a `RESCORE` run with trigger `SCORING_ACTIVATION` finishes with every changed current score referencing the new version; during that run no document, classification or `AI_CALL` audit row is created. | `S-CFG-04`, `S-SCO-07`, `B-05` |
| `AC-07` | Given an unsaved `YES_NO` question "Does the company announce a cost-reduction programme?" and pasted German text announcing a Kostensenkungsprogramm, when an Admin runs the preview, then a positive result carries a strength, a confidence, a quote that is a substring of the pasted text and an English translation; afterwards no question, classification or finding was created, and the only new rows are `AI_CALL` audit rows. | `S-CFG-05` |
| `AC-08` | Given a draft that lowers `hot_threshold` from 70 to 55, when an Admin previews it, then exactly the ranked accounts whose current Priority is between 55 and 69 are listed with band `WARM` current and `HOT` proposed, the rest are counted unchanged, and no score row is written. | `S-CFG-06` |

### Accounts and discovery

| ID | Criterion | Verifies |
|---|---|---|
| `AC-09` | Given a Sales user, when they create an account from `https://www.Lufthansagroup.com/de/` named "Lufthansa Group", then its domain is `lufthansagroup.com`, it has the alias "Lufthansa Group" and a `WEBSITE` source; creating an account for `lufthansagroup.com` again is refused `409 CONFLICT` with `details.entity_id` naming the first. | `S-ACC-01` |
| `AC-10` | Given the seeded demo accounts and a CSV of the rows of the demo account file plus one row without a domain, one row with the new domain `dhl-example.de` named "DHL Group AG" and one row with the new domain `beispiel-logistik.de` named "Beispiel Logistik", when it is imported with `dry_run` true, then the result reports 20 updated, 1 created, 1 invalid and 1 possible duplicate, and nothing is written; imported with `dry_run` false, the account `beispiel-logistik.de` exists, the 20 demo accounts are unchanged, and one `ACCOUNTS_IMPORTED` audit row is written; a file of `IMPORT_MAX_ROWS` + 1 rows is refused `422`. | `S-ACC-02` |
| `AC-11` | Given DHL Group with `employee_count` entered by a user, when it is refreshed with the Crunchbase recording, then `employee_count` keeps the user's value with origin `MANUAL`; when the user changes `employee_count`, a `RESCORE` run with trigger `ACCOUNT_CHANGE` is queued and Fit reflects the new value. | `S-ACC-03` |
| `AC-12` | Given the demo accounts and the alias "Deutsche Lufthansa" added to Lufthansa Group, when a user searches "deutsche lufthansa", then Lufthansa Group is returned; filtering country `CH` and industry `BANKING` returns UBS only. | `S-ACC-05` |
| `AC-13` | Given DHL Group, when a user adds a contact without `source_url`, or with an `email` field, then each is refused `422`; a contact with job title "Leiter Prozessautomatisierung" and a source URL gets persona `HEAD_OF_AUTOMATION` with origin `CLASSIFIER`; when the user erases it, the row is gone, a draft addressed to it has no contact, and the `CONTACT_ERASED` audit row contains neither the name nor the job title. | `S-ACC-04`, `RULE-07` |
| `AC-14` | Given Crunchbase unavailable and the discovery recording for Intelligent Automation, when a user runs discovery, then every candidate has origin `NEWS_MENTION` and a quote found in its document, none matches an existing account's domain or alias or an earlier candidate, none has a known country outside the `REGION` criterion, and there are at most `DISCOVERY_MAX_CANDIDATES`, ordered by fit estimate. | `S-DSC-01` |
| `AC-15` | Given a pending candidate without a domain, when a user accepts it without one, then it is refused `422`; accepted with domain `example-logistik.de`, an account of origin `DISCOVERED` exists and an `ACCOUNT_REFRESH` run is queued; a rejected candidate is absent from the next discovery run's candidates; no document had been fetched for either as an account before the decision. | `S-DSC-02` |

### Ingestion and signal detection

| ID | Criterion | Verifies |
|---|---|---|
| `AC-16` | Given the demo recording and only the free core available, when DHL Group is refreshed, then its documents come only from `GDELT`, `RSS`, `WEBSITE` and `CAREERS`, none has a publication date older than `FETCH_LOOKBACK_DAYS`, at most `MAX_DOCUMENTS_PER_REFRESH` were kept, `plugin_usage` counts every request made, and no request was made for `CRUNCHBASE`, `NEWSAPI` or `SERPAPI`. | `S-ING-01`, `S-ING-02`, `RULE-08` |
| `AC-17` | Given recorded items with the same text at `https://example.com/a?utm_source=x` and `https://example.com/a/`, and a German translation of the same story one day later, when the account is refreshed, then one document holds the first two, the translation is stored with `duplicate_of_id` pointing to it, and the translation has no triage row or classification. | `S-ING-03` |
| `AC-18` | Given a recorded annual-report PDF that yields more than `MAX_PASSAGES_PER_DOCUMENT` passages, when it is kept for Intelligent Automation, then exactly `MAX_PASSAGES_PER_DOCUMENT` of its passages have classifications for that service, and they are the passages most similar to the service's questions. | `S-ING-04` |
| `AC-69` | Given DHL Group with empty `industry` and `operational_complexity`, when it is refreshed with the Crunchbase recording, then `industry` is filled with origin `CRUNCHBASE`, and `operational_complexity` is set with origin `CLASSIFIER` or stays empty as [Account attributes](/architecture/rules.md#account-attributes) states. | `S-ING-06` |
| `AC-19` | Given an account with only its `WEBSITE` source whose recorded home page links a press page and a careers page on its domain, when it is refreshed, then `NEWSROOM` and `CAREERS` sources with origin `DETECTED` exist; for an account with a `MANUAL` `CAREERS` source, no careers source is detected. | `S-ING-05` |
| `AC-20` | Given the demo recording, when DHL Group is refreshed, then every new non-duplicate document has one triage row; the recorded article that mentions DHL only in passing is `NOT_ABOUT_ACCOUNT` and has no classification; documents from DHL's own website have no `about_account_p`. | `S-SIG-01` |
| `AC-21` | Given a kept news document and the Intelligent Automation questions, when it is classified, then each selected passage has one classification per active question whose source types include `NEWS` and none for `AUTOMATION_HIRING`; each classification records the classifier `CLASSIFIER_PROVIDER` names; a second refresh adds no classification for the same passage, question and revision. | `S-SIG-02`, `S-SIG-04` |
| `AC-22` | Given recorded classifier answers with `p_positive` 0.9, 0.5 and 0.2 for three pairs, when they are routed, then the first is positive without an LLM call for its verdict, the second is escalated and carries the LLM's strength, and the third is `NEGATIVE` with no LLM call. | `S-SIG-03` |
| `AC-23` | Given a recording made under both classifier adapters, when a refresh and a quality check run with `CLASSIFIER_PROVIDER` `JEV` and again with `LLM`, then the classifications and evaluation results record `JEV` and `LLM` respectively, every stored shape is the same, and nothing but the configuration differs between the runs. | `S-SIG-04` |
| `AC-24` | Given all demo accounts refreshed, when their findings are read, then every quote, after collapsing whitespace, is a substring of its passage, every finding from a German document has a `quote_en` and every finding from an English one has none; given a recorded evidence answer whose quote is not in the passage on both attempts, then that pair has no finding and its classification is `EVIDENCE_FAILED`. | `S-SIG-05`, `S-SIG-09`, `RULE-02` |
| `AC-25` | Given a finding from a document with a publication date and one from a document without, when they are read, then each carries strength, confidence, `decided_by` and question revision, a finding of the `CHOICE` question `INCUMBENT_PROVIDER` carries the option it matched, and `observed_at` is the publication date for the first and the fetch time for the second. | `S-SIG-06` |
| `AC-26` | Given all demo accounts refreshed and findings for `COST_PROGRAM`, when an Admin revises its text, then the `RECLASSIFY` run fetches nothing, sets the question's revision-1 findings `SUPERSEDED`, creates classifications at revision 2 for that question only, leaves every other question's classifications unchanged, and ends by rescoring the service. | `S-SIG-07`, `S-SIG-06`, `B-05` |
| `AC-27` | Given `CLASSIFIER_PROVIDER` `LLM` and today's `AI_CALL` costs already at `LLM_DAILY_BUDGET_EUR`, when DHL Group is refreshed, then its documents are fetched and processed, no LLM call is made, its new passages have no classification, the run ends `PARTIAL` with `pending_budget` counting the stopped work, and a question preview answers `429 BUDGET_EXHAUSTED`; after the clock passes 00:00 UTC the next refresh classifies those passages. | `S-SIG-08` |
| `AC-70` | Given `CLASSIFIER_PROVIDER` `JEV` and today's `AI_CALL` costs already at `LLM_DAILY_BUDGET_EUR`, when DHL Group is refreshed, then Jev classifications are created, no LLM call is made, the pairs needing escalation or evidence are `PENDING_LLM` and counted in `pending_budget`, and the run ends `PARTIAL`; after the clock passes 00:00 UTC the next refresh resolves the pending pairs. | `S-SIG-08` |

### Runs

| ID | Criterion | Verifies |
|---|---|---|
| `AC-28` | Given a refresh of Lufthansa Group queued by one user, when another user requests a refresh of it, then they get the same run id with `200`; polling it shows the stage moving from `FETCH` to `SCORE` with growing counters, and the finished run's counters equal the documents, classifications and findings it created. | `S-PIP-01` |
| `AC-29` | Given three active accounts due and one inactive account due, when the scheduler ticks twice, then exactly three refreshes with trigger `SCHEDULE` are queued, none for the inactive account, and after they finish each account's `next_refresh_at` is its finish time plus `REFRESH_INTERVAL_HOURS`. | `S-PIP-02` |
| `AC-30` | Given a recording in which `GDELT` answers errors, when the account is refreshed, then the other plug-ins' documents are processed and scored and the run ends `PARTIAL` with an error naming `GDELT`; given a queued run, when it is cancelled, then its ready jobs never run and it ends `CANCELLED`; a Sales user cancelling a `RESCORE` or `RECLASSIFY` run is refused `403`. | `S-PIP-03` |
| `AC-31` | Given a `PROCESS` job made to fail once by a fixture fault, when the worker runs, then it is retried after its backoff and the run ends with the same documents and passages as without the fault; a job that fails `JOB_MAX_ATTEMPTS` times is `FAILED` and recorded in its run's errors; a job left `RUNNING` beyond `JOB_LOCK_TIMEOUT_S` is reclaimed and completes without duplicate rows. | `S-PIP-04`, `N-05` |
| `AC-32` | Given `NEWSAPI_KEY` unset, when an Admin lists the plug-ins, then `NEWSAPI` shows `needs_key` true, `key_configured` false and `available` false even while enabled; when the Admin disables `GDELT`, the next refresh makes no `GDELT` request; a Sales user listing them is refused `403`. | `S-PIP-05`, `S-ING-01` |

### Scoring

| ID | Criterion | Verifies |
|---|---|---|
| `AC-33` | Given the settings and account of Example 1 of the [rules examples](/architecture/rules.md#examples), when the account is scored, then Fit is 94 and the breakdown shows `SIZE` as `UNKNOWN` with credit `unknown_match`. | `S-SCO-01` |
| `AC-34` | Given the findings of Example 1 at their stated ages, when the account is scored, then Intent is 38, Priority 60, standing `RANKED` and band `WARM`, and the `IN_HOUSE_AUTOMATION` entry has negative points; without that finding Intent is higher. | `S-SCO-02`, `B-18` |
| `AC-35` | Given the Example 1 settings, when a `NEWS` finding of a question without its own half-life is 90 days old at `as_of`, then its decay is 0.5; the 400-day-old finding of Example 3 contributes 0. | `S-SCO-03` |
| `AC-36` | Given Example 2's account, when it is scored, then its standing is `DISQUALIFIED` with no band and the breakdown names `OUTSIDE_REGION`; it is absent from the default Prospects list and present under standing `DISQUALIFIED` with the rule's label; after an Admin adds an exception with a note it is `RANKED` and `WARM`; after revocation it is `DISQUALIFIED` again; a Sales user adding an exception is refused `403`. | `S-SCO-04`, `S-PRO-05`, `RULE-10` |
| `AC-37` | Given the default thresholds and accounts with Fit of at least 40, when they score Priority 70, 69, 40 and 39, then their bands are `HOT`, `WARM`, `WARM` and `COLD`; an account with Fit 39 is `BELOW_FIT` with no band and no rank; an account whose in-force lead feedback is `ALREADY_CUSTOMER` is `CUSTOMER` even when a disqualifier also matches. | `S-SCO-05` |
| `AC-38` | Given any score produced from the demo recording, when its breakdown is read, then the criteria points add up to Fit and the question points to Intent before rounding and clamping, and every question entry with non-zero points names an in-force finding. | `S-SCO-06`, `B-17` |
| `AC-39` | Given a scored account, when it is rescored with no input changed, then no score row is written; when the same inputs are scored twice at the same `as_of`, the two breakdowns are byte-identical; when a new finding changes Intent, a new current row exists and the previous one remains with `is_current` false. | `S-SCO-07`, `N-04` |
| `AC-40` | Given all demo accounts refreshed, when the test recomputes each score from the stored findings, feedback, exceptions, attributes and active settings with the formulas of the [rules](/architecture/rules.md#examples), then it equals the stored score; no classifier or LLM contract of [interfaces](/architecture/interfaces.md) returns a score, band, standing or exclusion. | `S-SCO-08`, `RULE-03` |

### Prospects and evidence

| ID | Criterion | Verifies |
|---|---|---|
| `AC-41` | Given all demo accounts refreshed, when a user opens Prospects for Intelligent Automation, then only `RANKED` accounts are listed, by descending Priority with ties by Intent, Fit and name, each with at most two top signals; filtering band `HOT` and country `DE` returns only such accounts; standing `DISQUALIFIED` lists excluded accounts with their disqualifier's label and no rank. | `S-PRO-01` |
| `AC-42` | Given DHL Group scored, when a user opens its Account detail for Intelligent Automation, then the Why tab shows every ICP criterion with its match and points, every counted question with its finding's strength label, confidence word, age, source, quote, English translation and points, and an "In short" paragraph whose every statement is backed by an entry of the breakdown. | `S-PRO-02` |
| `AC-43` | Given a finding, when a user opens its evidence, then the excerpt contains the quote at the returned offsets and the original URL is shown; after the document's `purge_after` has passed and housekeeping ran, the evidence shows `purged` true, no excerpt, and still the quote and URL. | `S-PRO-03` |
| `AC-44` | Given an account rescored by a refresh, a scoring activation and an exception, when a user opens its history, then three entries give the causes refresh, the new scoring version with its change note, and exception, each with Priority and band before and after and the findings or exceptions that changed. | `S-PRO-04` |
| `AC-45` | Given a refresh that creates a `STRONG` finding for a `HIGH`-weight positive question observed within `ALERT_MAX_AGE_DAYS` and moves a ranked account from `WARM` to `HOT`, when it finishes, then one `STRONG_SIGNAL` and one `BAND_UP` alert exist; repeating the refresh creates no further alert; after one user acknowledges one, every user's unread count is one lower. | `S-PRO-06` |

### Feedback and evaluation

| ID | Criterion | Verifies |
|---|---|---|
| `AC-46` | Given a ranked account, when a user gives the lead verdict `ALREADY_CUSTOMER`, then after the rescore its standing is `CUSTOMER`, it is absent from the ranking and listed under standing `CUSTOMER` with who marked it; a later `RELEVANT` verdict returns it to `RANKED`. | `S-EVL-01` |
| `AC-47` | Given the counted finding of a question, when a user marks it `WRONG`, then it is `REJECTED`, the rescored Intent no longer counts it, and an evaluation item with origin `FINDING_FEEDBACK` and expected strength `NONE` exists unless a manual label exists for the pair; marking it `CORRECT` again makes it `ACTIVE` and counted. | `S-EVL-02` |
| `AC-48` | Given classified pairs in all three confidence strata, when a user fetches the label queue, then it returns up to `LABEL_QUEUE_SIZE` unlabelled pairs drawn from every stratum that has pairs, with no classifier output; a submitted label is stored with origin `MANUAL`; after the question's revision changes, that label is `STALE`. | `S-EVL-03` |
| `AC-49` | Given the demo refresh and the labels loaded by `make seed-labels`, when an Admin runs a quality check, then its result has every metric of [Evaluation metrics](/architecture/rules.md#evaluation-metrics), no classification or finding was written, `passed` is true exactly when precision ≥ `EVAL_MIN_PRECISION` and items ≥ `EVAL_MIN_ITEMS`, and `escalation_rate` is at most `ESCALATION_RATE_TARGET`; for the release candidate `passed` is true. | `S-EVL-04`, `N-03`, `B-27` |

### Outreach and CRM

| ID | Criterion | Verifies |
|---|---|---|
| `AC-50` | Given DHL Group with in-force positive findings and a contact, when a user generates an email draft, then it has a subject and a body of at most `OUTREACH_EMAIL_MAX_CHARS`, cites only ids of the findings it was given, contains no email address or phone number, and is `DRAFT`; after an edit it is `edited`; after export it is `EXPORTED`; no contract sends a message. | `S-OUT-01`, `RULE-06` |
| `AC-51` | Given `HUBSPOT_ACCESS_TOKEN` unset, when a user pushes DHL Group, then the answer is `409 NOT_CONFIGURED`; given a token and a recorded HubSpot exchange, the company is found by domain and updated with the `leadradar_*` properties, and a `SUCCEEDED` `crm_sync` row holds its HubSpot id. | `S-OUT-02` |

### Security, audit and runtime

| ID | Criterion | Verifies |
|---|---|---|
| `AC-52` | Given the seeded Sales user, when they sign in with the right password, then the response sets an HTTP-only, `Secure`, `SameSite=Lax` cookie and `API-03` returns role `SALES`; a wrong password answers `401`; the `LOGIN_MAX_FAILURES`-th consecutive failure and every attempt during the lock answer `423`; after sign-out the cookie no longer authenticates; the database holds no plain password or token. | `S-SEC-01`, `N-07` |
| `AC-53` | Given every contract of [interfaces](/architecture/interfaces.md) with a path, when it is called anonymously, as Sales and as Admin, then it answers `401`, `403` or success exactly as its roles column states, and any `POST` without `X-Requested-With` answers `403`. | `S-SEC-02` |
| `AC-54` | Given an Admin, when they create a Sales user, disable them, and try to disable or demote themselves, then the user exists, the disabled user's sessions stop authenticating, and each self-change is refused `409`. | `S-SEC-03` |
| `AC-55` | Given a refresh, a question change, a scoring activation, an exception, feedback and an outreach draft, when the audit is read, then each produced its action with the entity and payload of [Audit actions](/architecture/sql-store.md#audit-actions), every classifier and LLM call has one `AI_CALL` row with role, provider, model, prompt version, tokens, cost, latency and outcome, and the application's database role has no `UPDATE` or `DELETE` privilege on `audit_event`. | `S-AUD-01`, `RULE-09` |
| `AC-56` | Given audit rows of several kinds, when an Admin filters by kind `AI_CALL` and a run id, then only that run's AI calls are returned, newest first; a Sales user is refused `403`. | `S-AUD-02` |
| `AC-57` | Given a machine with Docker and no database, when `docker compose up` runs, then `web`, `api`, `worker`, `db` and `embedder` start, the migrations are applied, `/health` answers `OK` with every check reported, and with the embedder stopped it answers `DEGRADED` naming `embedder`. | `S-RUN-01`, `N-12` |
| `AC-58` | Given `FIXTURE_MODE` `replay`, the demo recording, the same `CLOCK_FILE` time and no outbound network, when a clean database is seeded and all 20 accounts are refreshed, twice from scratch, then both runs succeed with identical findings and scores; a request with no recording fails its step with `FIXTURE_MISSING` and no live request is attempted. | `S-RUN-02`, `N-05` |
| `AC-59` | Given an empty database, when `make seed-demo` runs, then the two users, the services `INTELLIGENT_AUTOMATION` and `CYBERSECURITY` with the questions, ICP criteria and disqualifiers of the [demo dataset](/architecture/overview.md#demo-dataset) as active version 1, and the 20 accounts with the parent links and the sources and attributes of the demo account file exist, and no document was fetched; after the demo refresh, `make seed-labels` attaches every exported label to its passage. | `S-RUN-03` |

### Non-functional

| ID | Criterion | Verifies |
|---|---|---|
| `AC-60` | Given 200 accounts with findings and scores, when `API-39`, `API-40`, `API-42` and `API-20` are each called 100 times, then each one's p95 is within `INTERACTIVE_P95_TARGET_MS`. | `N-01` |
| `AC-61` | Given replay mode, when each demo account is refreshed alone, then the longest refresh finishes within `REFRESH_TARGET_MINUTES`. | `N-02` |
| `AC-62` | Given the demo recording, when in turn a plug-in, the classifier, OpenRouter, the embedder and HubSpot are made unavailable, then each affected refresh, preview, draft or push reports an error naming the dependency with the behaviour of the [Degradation](/architecture/overview.md#degradation) table, Prospects and Account detail keep answering, and no placeholder finding, score, quote or draft is stored. | `N-06` |
| `AC-63` | Given the clock past a document's `purge_after` and a contact's `retain_until`, when housekeeping runs, then the document's text and its passages' text and embeddings are null except a passage referenced by an active label, its findings keep their quotes, and the contact is erased with a `CONTACT_ERASED` row of reason `RETENTION`; no log line or audit payload of the acceptance run contains a contact's name; the demo cloud machine runs in an EU region. | `N-08` |
| `AC-64` | Given a fixture web server whose `robots.txt` disallows `/private`, when an account on it is refreshed, then no request goes under `/private`, every request carries `CRAWLER_USER_AGENT`, consecutive requests to the host are at least `CRAWL_HOST_DELAY_MS` apart, and an account with a `linkedin_url` causes no request to `linkedin.com`. | `N-09`, `RULE-01` |
| `AC-65` | Given every screen, when an automated accessibility scan runs as a Sales user and as an Admin, then it reports no serious or critical violation, every action is reachable by keyboard, and no screen available to Sales shows a raw probability or the words "escalation" or "triage". | `N-10` |
| `AC-66` | Given a third service configured through the API only, and two worker containers, when all accounts are refreshed, then the new service's questions are classified and scored with no code change, and no job is run by both workers. | `N-11` |
| `AC-67` | Given the logs of the acceptance run, when they are scanned, then every line is JSON carrying a `request_id` or a `run_id`, and none contains a password, a session token or an API key. | `N-12`, `N-07` |
| `AC-68` | Given two sales managers who have not used LeadRadar, when they perform the tasks of `SC-A` without help, then both complete them. | `N-13` |

## Scenario pass criteria

| Scenario | Passes when |
|---|---|
| `SC-A` | `AC-10`, `AC-16`, `AC-20`, `AC-24`, `AC-28`, `AC-41`, `AC-42` and `AC-43` pass in one continuous run on the demo recording, walked with Lufthansa Group and DHL Group. |
| `SC-B` | `AC-06`, `AC-26` and `AC-39` pass in one run that follows `SC-A`. |
| `SC-C` | `AC-34` and `AC-36` pass on the accounts of the [rules examples](/architecture/rules.md#examples). |
| `SC-D` | `AC-48` and `AC-49` pass with at least `EVAL_MIN_ITEMS` labels. |

## Release gate

The release gate is every criterion in this file except those listed below, plus the four scenarios; it passes when each is green on the Compose deployment in replay mode; `AC-57` is also run on the demo cloud machine.

Outside the gate: P1 `AC-07`, `AC-08`, `AC-13`, `AC-14`, `AC-15`, `AC-19`, `AC-29`, `AC-44`, `AC-45`, `AC-46`, `AC-47`, `AC-50`, `AC-56`, `AC-66`, `AC-68`, `AC-69`; P2 `AC-51`. A scenario names only criteria inside the gate.
