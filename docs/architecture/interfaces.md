---
type: Interface
title: Interfaces
description: Every contract that crosses a boundary - the REST API the frontend calls, the in-process classifier, LLM, embedder, source plug-in and CRM ports - with every shape each carries and its source of truth.
status: draft
tags: [accounts-and-discovery, audit-trail, evaluation-and-feedback, identity-and-access, outreach-and-crm, prospect-dashboard, service-configuration, signal-pipeline]
---

# Interfaces

## Conventions

**Transport and base path.** REST over HTTPS under `/api/v1`, JSON bodies in UTF-8, except the CSV upload of `API-22`. Identifiers are UUID strings; timestamps are ISO-8601 UTC. This file is the source of every contract; the OpenAPI document the api serves is generated from the same routes, and the frontend's typed client is generated from it, never written by hand.

**Naming.** JSON field names are snake_case and carry the column name of their source of truth. Enum values are UPPER_SNAKE exactly as the [SQL store](/architecture/sql-store.md) defines them; a shape names an enum by linking its owning column and never lists its values.

**Roles.** The roles column of every contracts table uses:

| Symbol | Meaning |
|---|---|
| `*` | any signed-in user, Sales or Admin |
| `A` | Admin only |
| `-` | anonymous |

Authorisation is enforced by the api on every route ([S-SEC-02](/requirements/system.md)); a signed-in user without the role gets `403 FORBIDDEN`.

**Authentication.** `API-01` sets an HTTP-only, `Secure`, `SameSite=Lax` session cookie whose token is recorded as a hash in [`auth_session`](/architecture/sql-store.md#auth_session) and expires after `SESSION_TTL_HOURS`. Every other route except `API-61` requires it and accepts no other credential. `API-02` revokes it.

**CSRF.** A `POST`, `PUT`, `PATCH` or `DELETE` without an `X-Requested-With` header is refused `403 FORBIDDEN`. The browser reaches the api only through the frontend's proxy on the same origin.

**Pagination.** A list marked `Page<T>` takes `page` (from 1) and `page_size` (default `PAGE_SIZE_DEFAULT`, at most `PAGE_SIZE_MAX`) and returns `{items: T[], page, page_size, total}`.

**Runs.** A request that starts background work answers `202` with the [`Run`](#run). A refresh requested while one is queued or running for the same account answers `200` with the existing run.

**Envelope.** Success returns the resource. An error returns `{"error": {"code", "message", "details"?}}`:

| Code | HTTP | Raised when |
|---|---|---|
| `UNAUTHENTICATED` | 401 | No valid session, or wrong credentials |
| `FORBIDDEN` | 403 | The role does not allow the contract, the account is disabled, or the CSRF header is missing |
| `NOT_FOUND` | 404 | The resource does not exist |
| `CONFLICT` | 409 | A uniqueness or state rule refuses the change; `details.entity_id` names the conflicting row when there is one |
| `NOT_CONFIGURED` | 409 | The contract needs an integration or plug-in key that is not configured |
| `VALIDATION` | 422 | The input is invalid; `details.fields[]` lists `{field, message}`, where `field` is a body field name or a JSON pointer into it |
| `LOCKED` | 423 | Too many failed sign-ins; `details.retry_after_min` |
| `BUDGET_EXHAUSTED` | 429 | The [Budget guard](/architecture/rules.md#budget-guard) stops an LLM call; `details.resets_at` |
| `UPSTREAM_UNAVAILABLE` | 503 | The classifier, the LLM, the embedder or a provider is unavailable or returned invalid output; `details.dependency`, `details.reason` |
| `INTERNAL` | 500 | Anything else |

Degraded behaviour is an explicit error, never a placeholder result ([Degradation](/architecture/overview.md#degradation)).

## Authentication and users

### Authentication and users contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-01` | POST | `/auth/login` | `-` | [`LoginRequest`](#loginrequest) → [`AuthenticatedUser`](#authenticateduser) |
| `API-02` | POST | `/auth/logout` | `*` | — → `204` |
| `API-03` | GET | `/auth/me` | `*` | — → [`AuthenticatedUser`](#authenticateduser) |
| `API-04` | GET | `/users` | `A` | — → [`User`](#user)`[]` |
| `API-05` | POST | `/users` | `A` | [`UserCreate`](#usercreate) → [`User`](#user) |
| `API-06` | PATCH | `/users/{id}` | `A` | [`UserUpdate`](#userupdate) → [`User`](#user) |

- `API-01` — wrong email or password answers `401` with one message that does not reveal which was wrong. The failure that reaches `LOGIN_MAX_FAILURES` locks the account for `LOGIN_LOCK_MINUTES`; while locked every attempt answers `423 LOCKED`. A disabled account answers `403 FORBIDDEN` only when the password is correct.
- `API-06` — an Admin cannot change their own role or disable themselves (`409 CONFLICT`). Disabling a user revokes their sessions.

### Authentication and users shapes

#### LoginRequest

| Field | Type | Source of truth |
|---|---|---|
| `email` | string | [`app_user`](/architecture/sql-store.md#app_user) `email` |
| `password` | string | checked against `password_hash`; never stored or logged |

#### AuthenticatedUser

| Field | Type | Source of truth |
|---|---|---|
| `id` | string | [`app_user`](/architecture/sql-store.md#app_user) |
| `email` | string | [`app_user`](/architecture/sql-store.md#app_user) |
| `display_name` | string | [`app_user`](/architecture/sql-store.md#app_user) |
| `role` | enum | [`app_user`](/architecture/sql-store.md#app_user) `role` |

#### User

| Field | Type | Source of truth |
|---|---|---|
| `id`, `email`, `display_name` | string | [`app_user`](/architecture/sql-store.md#app_user) |
| `role` | enum | [`app_user`](/architecture/sql-store.md#app_user) `role` |
| `status` | enum | [`app_user`](/architecture/sql-store.md#app_user) `status` |
| `last_login_at` | string, null | [`app_user`](/architecture/sql-store.md#app_user) |

#### UserCreate

| Field | Type | Source of truth |
|---|---|---|
| `email`, `display_name` | string | [`app_user`](/architecture/sql-store.md#app_user) |
| `role` | enum | [`app_user`](/architecture/sql-store.md#app_user) `role` |
| `password` | string, at least `PASSWORD_MIN_LENGTH` characters | hashed into `password_hash` |

#### UserUpdate

| Field | Type | Source of truth |
|---|---|---|
| `display_name` | string, optional | [`app_user`](/architecture/sql-store.md#app_user) |
| `role` | enum, optional | [`app_user`](/architecture/sql-store.md#app_user) `role` |
| `status` | enum, optional | [`app_user`](/architecture/sql-store.md#app_user) `status` |
| `password` | string, optional | a reset; hashed into `password_hash` |

## Services and questions

### Services and questions contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-07` | GET | `/services` | `*` | — → [`Service`](#service)`[]` |
| `API-08` | POST | `/services` | `A` | [`ServiceCreate`](#servicecreate) → [`Service`](#service) |
| `API-09` | GET | `/services/{id}` | `*` | — → [`Service`](#service) |
| `API-10` | PATCH | `/services/{id}` | `A` | [`ServiceUpdate`](#serviceupdate) → [`Service`](#service) |
| `API-11` | GET | `/services/{id}/questions` | `*` | — → [`SignalQuestion`](#signalquestion)`[]` |
| `API-12` | POST | `/services/{id}/questions` | `A` | [`SignalQuestionCreate`](#signalquestioncreate) → [`SignalQuestion`](#signalquestion) |
| `API-13` | PATCH | `/questions/{id}` | `A` | [`SignalQuestionUpdate`](#signalquestionupdate) → [`SignalQuestion`](#signalquestion) |
| `API-14` | POST | `/questions/preview` | `A` | [`QuestionPreviewRequest`](#questionpreviewrequest) → [`QuestionPreview`](#questionpreview) |

- `API-08` — creates the service and its first scoring draft with the defaults of the [scoring settings document](/architecture/sql-store.md#scoring-settings-document). A code or name already used answers `409 CONFLICT`.
- `API-10` — `code` is not accepted. Setting `status` to `ACTIVE` from `INACTIVE` enqueues one `RECLASSIFY` run per active question.
- `API-12` — enqueues a `RECLASSIFY` run for the new question and adds it at weight `MEDIUM` to the service's draft, creating the draft from the active version if none exists.
- `API-13` — a change to `text`, `answer_type`, `options` or `source_types` increments `revision` and enqueues a `RECLASSIFY` run ([Reclassification](/architecture/rules.md#reclassification)); deactivating removes the question from the draft; reactivating enqueues a `RECLASSIFY` run and adds it to the draft.
- `API-14` — asks an unsaved or saved question against pasted text or against the account's stored passages, through the same classification, escalation and evidence rules as the pipeline, and stores nothing except `AI_CALL` audit rows.

### Services and questions shapes

#### Service

| Field | Type | Source of truth |
|---|---|---|
| `id`, `code`, `name`, `description`, `value_proposition` | string | [`service`](/architecture/sql-store.md#service) |
| `status` | enum | [`service`](/architecture/sql-store.md#service) `status` |
| `active_version` | integer, null | `version` of the service's `ACTIVE` [`scoring_config`](/architecture/sql-store.md#scoring_config) |
| `draft_version` | integer, null | `version` of its `DRAFT` |
| `question_count` | integer | its `ACTIVE` [`signal_question`](/architecture/sql-store.md#signal_question) rows |

#### ServiceCreate

| Field | Type | Source of truth |
|---|---|---|
| `code`, `name`, `description`, `value_proposition` | string | [`service`](/architecture/sql-store.md#service) |

#### ServiceUpdate

| Field | Type | Source of truth |
|---|---|---|
| `name`, `description`, `value_proposition` | string, optional | [`service`](/architecture/sql-store.md#service) |
| `status` | enum, optional | [`service`](/architecture/sql-store.md#service) `status` |

#### SignalQuestion

| Field | Type | Source of truth |
|---|---|---|
| `id`, `service_id`, `key`, `text` | string | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `answer_type` | enum | [`signal_question`](/architecture/sql-store.md#signal_question) `answer_type` |
| `options` | array of `{key, label, strength}`, null | [`signal_question`](/architecture/sql-store.md#signal_question) `options` |
| `polarity` | enum | [`signal_question`](/architecture/sql-store.md#signal_question) `polarity` |
| `source_types` | enum[] | [`signal_question`](/architecture/sql-store.md#signal_question) `source_types` |
| `hint_terms` | string[] | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `revision` | integer | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `status` | enum | [`signal_question`](/architecture/sql-store.md#signal_question) `status` |
| `finding_count` | integer | in-force [`finding`](/architecture/sql-store.md#finding) rows of the question |

#### SignalQuestionCreate

| Field | Type | Source of truth |
|---|---|---|
| `key`, `text` | string | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `answer_type` | enum | [`signal_question`](/architecture/sql-store.md#signal_question) `answer_type` |
| `options` | array, required exactly for `CHOICE` | [`signal_question`](/architecture/sql-store.md#signal_question) `options` |
| `polarity` | enum | [`signal_question`](/architecture/sql-store.md#signal_question) `polarity` |
| `source_types` | enum[], at least one | [`signal_question`](/architecture/sql-store.md#signal_question) `source_types` |
| `hint_terms` | string[], optional | [`signal_question`](/architecture/sql-store.md#signal_question) |

#### SignalQuestionUpdate

| Field | Type | Source of truth |
|---|---|---|
| `text` | string, optional | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `answer_type` | enum, optional | [`signal_question`](/architecture/sql-store.md#signal_question) `answer_type` |
| `options` | array, optional | [`signal_question`](/architecture/sql-store.md#signal_question) `options` |
| `source_types` | enum[], optional | [`signal_question`](/architecture/sql-store.md#signal_question) `source_types` |
| `hint_terms` | string[], optional | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `status` | enum, optional | [`signal_question`](/architecture/sql-store.md#signal_question) `status` |

#### QuestionPreviewRequest

| Field | Type | Source of truth |
|---|---|---|
| `service_id` | string | [`service`](/architecture/sql-store.md#service) |
| `question_id` | string, optional | a saved [`signal_question`](/architecture/sql-store.md#signal_question); or the three fields below for an unsaved one |
| `text`, `answer_type`, `options` | as [`SignalQuestionCreate`](#signalquestioncreate), optional | the unsaved question |
| `sample_text` | string, optional | pasted text, chunked like a document |
| `account_id` | string, optional | an [`account`](/architecture/sql-store.md#account) whose stored passages are searched instead; exactly one of `sample_text` and `account_id` |

#### QuestionPreview

| Field | Type | Source of truth |
|---|---|---|
| `classifier` | enum | [`document_triage`](/architecture/sql-store.md#document_triage) `classifier`: the configured adapter |
| `results` | array of preview results, at most `PREVIEW_MAX_PASSAGES` | the passages most similar to the question, as [Chunking and passage selection](/architecture/rules.md#chunking-and-passage-selection) ranks them |
| `results[].passage` | string | the passage text |
| `results[].document` | `{title, url, published_at}`, null | the passage's [`document`](/architecture/sql-store.md#document); null for pasted text |
| `results[].p_positive`, `results[].escalated` | number, boolean | as [`classification`](/architecture/sql-store.md#classification) would store them |
| `results[].strength` | enum | [`finding`](/architecture/sql-store.md#finding) `strength` |
| `results[].quote`, `results[].quote_en`, `results[].rationale` | string, null | as [Evidence extraction](/architecture/rules.md#evidence-extraction) would produce them, when positive |

## Scoring

### Scoring contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-15` | GET | `/services/{id}/scoring-configs` | `*` | — → [`ScoringConfigSummary`](#scoringconfigsummary)`[]` |
| `API-16` | GET | `/scoring-configs/{id}` | `*` | — → [`ScoringConfig`](#scoringconfig) |
| `API-17` | PUT | `/services/{id}/scoring-configs/draft` | `A` | [`ScoringDraftUpdate`](#scoringdraftupdate) → [`ScoringConfig`](#scoringconfig) |
| `API-18` | POST | `/scoring-configs/{id}/activate` | `A` | [`ActivationRequest`](#activationrequest) → [`ScoringConfig`](#scoringconfig) |
| `API-19` | POST | `/scoring-configs/{id}/preview` | `A` | — → [`ScoringPreview`](#scoringpreview) |

- `API-17` — creates the draft from the active version when none exists, then replaces its settings. The settings must pass [Scoring settings validation](/architecture/rules.md#scoring-settings-validation), else `422 VALIDATION`.
- `API-18` — only a `DRAFT` can be activated (`409 CONFLICT` otherwise). It re-validates, makes the draft `ACTIVE`, the previous active `RETIRED`, and enqueues a `RESCORE` run of the service with trigger `SCORING_ACTIVATION`. A `PUT` to an `ACTIVE` or `RETIRED` version does not exist: only the draft path is writable.
- `API-19` — computes, without writing, what every current score of the service would be under the draft, from the same inputs [Rescoring](/architecture/rules.md#rescoring) reads.

### Scoring shapes

#### ScoringConfigSummary

| Field | Type | Source of truth |
|---|---|---|
| `id`, `service_id` | string | [`scoring_config`](/architecture/sql-store.md#scoring_config) |
| `version` | integer | [`scoring_config`](/architecture/sql-store.md#scoring_config) |
| `status` | enum | [`scoring_config`](/architecture/sql-store.md#scoring_config) `status` |
| `change_note` | string, null | [`scoring_config`](/architecture/sql-store.md#scoring_config) |
| `activated_at` | string, null | [`scoring_config`](/architecture/sql-store.md#scoring_config) |
| `activated_by_name` | string, null | `display_name` of `activated_by` |

#### ScoringConfig

| Field | Type | Source of truth |
|---|---|---|
| every field of [`ScoringConfigSummary`](#scoringconfigsummary) | | |
| `settings` | object | the [scoring settings document](/architecture/sql-store.md#scoring-settings-document) |

#### ScoringDraftUpdate

| Field | Type | Source of truth |
|---|---|---|
| `settings` | object | the [scoring settings document](/architecture/sql-store.md#scoring-settings-document) |
| `change_note` | string, optional | [`scoring_config`](/architecture/sql-store.md#scoring_config) |

#### ActivationRequest

| Field | Type | Source of truth |
|---|---|---|
| `change_note` | string, required | [`scoring_config`](/architecture/sql-store.md#scoring_config) |

#### ScoringPreview

| Field | Type | Source of truth |
|---|---|---|
| `draft_version`, `active_version` | integer | [`scoring_config`](/architecture/sql-store.md#scoring_config) |
| `changes` | array | one entry per account whose priority, standing, band or rank would change |
| `changes[].account` | `{id, name}` | [`account`](/architecture/sql-store.md#account) |
| `changes[].current`, `changes[].proposed` | `{priority, standing, band, rank}` | [`account_score`](/architecture/sql-store.md#account_score) fields; `rank` from [Priority, standing and band](/architecture/rules.md#priority-standing-and-band) |
| `unchanged_count` | integer | accounts with no change |

## Accounts and contacts

### Accounts and contacts contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-20` | GET | `/accounts` | `*` | query `q`, `status`, `country_code`, `industry`, `origin` → `Page<`[`AccountRow`](#accountrow)`>` |
| `API-21` | POST | `/accounts` | `*` | [`AccountCreate`](#accountcreate) → [`Account`](#account) |
| `API-22` | POST | `/accounts/import` | `*` | multipart: `file` ([`AccountImportRow`](#accountimportrow) CSV), `dry_run` → [`ImportResult`](#importresult) |
| `API-23` | GET | `/accounts/{id}` | `*` | — → [`Account`](#account) |
| `API-24` | PATCH | `/accounts/{id}` | `*` | [`AccountUpdate`](#accountupdate) → [`Account`](#account) |
| `API-25` | GET | `/accounts/{id}/contacts` | `*` | — → [`Contact`](#contact)`[]` |
| `API-26` | POST | `/accounts/{id}/contacts` | `*` | [`ContactCreate`](#contactcreate) → [`Contact`](#contact) |
| `API-27` | PATCH | `/contacts/{id}` | `*` | [`ContactUpdate`](#contactupdate) → [`Contact`](#contact) |
| `API-28` | DELETE | `/contacts/{id}` | `*` | — → `204` |

- `API-20` — `q` matches the name, any alias or the domain.
- `API-21` — the domain is normalised by [Account identity](/architecture/rules.md#account-identity); an existing domain answers `409 CONFLICT` with `details.entity_id`. Creates the name alias, the `WEBSITE` source and any sources given, with `next_refresh_at` = now.
- `API-22` — at most `IMPORT_MAX_ROWS` rows, else `422`. Each row is matched by [Account identity](/architecture/rules.md#account-identity): a new domain is created; an existing domain is updated with the columns the row fills, as `MANUAL` values, and an update that changes an attribute enqueues a `RESCORE` with trigger `ACCOUNT_CHANGE` for that account, as `API-24` does; a new domain whose name matches another account is reported `POSSIBLE_DUPLICATE` and skipped; an invalid row is reported with its errors. With `dry_run` true nothing is written.
- `API-24` — `aliases` replaces the aliases (the name alias is kept); `sources` replaces the `MANUAL` sources and may set a `DETECTED` source's status. Any attribute change enqueues a `RESCORE` with trigger `ACCOUNT_CHANGE`.
- `API-26`, `API-27` — a contact without `source_url` answers `422`; a body field not in the shape, such as an email address, answers `422`. The persona is mapped by [Persona mapping](/architecture/rules.md#persona-mapping) unless one is given.
- `API-28` — erases the contact as [Retention and erasure](/architecture/rules.md#retention-and-erasure) states, with reason `REQUEST`.

### Accounts and contacts shapes

#### AccountRow

| Field | Type | Source of truth |
|---|---|---|
| `id`, `name`, `domain`, `country_code` | string | [`account`](/architecture/sql-store.md#account) |
| `industry` | enum, null | [`account`](/architecture/sql-store.md#account) `industry` |
| `status` | enum | [`account`](/architecture/sql-store.md#account) `status` |
| `origin` | enum | [`account`](/architecture/sql-store.md#account) `origin` |
| `last_refreshed_at` | string, null | [`account`](/architecture/sql-store.md#account) |
| `active_run_id` | string, null | its `QUEUED` or `RUNNING` `ACCOUNT_REFRESH` [`pipeline_run`](/architecture/sql-store.md#pipeline_run) |

#### Account

| Field | Type | Source of truth |
|---|---|---|
| every field of [`AccountRow`](#accountrow) | | |
| `employee_count`, `revenue_eur` | integer, null | [`account`](/architecture/sql-store.md#account) |
| `operational_complexity` | enum, null | [`account`](/architecture/sql-store.md#account) `operational_complexity` |
| `attribute_origin` | object | [`account`](/architecture/sql-store.md#account) `attribute_origin` |
| `parent` | `{id, name}`, null | the [`account`](/architecture/sql-store.md#account) of `parent_account_id` |
| `crunchbase_id`, `linkedin_url`, `notes` | string, null | [`account`](/architecture/sql-store.md#account) |
| `aliases` | string[] | [`account_alias`](/architecture/sql-store.md#account_alias) `alias` |
| `sources` | array of `{url, kind, origin, status}` | [`account_source`](/architecture/sql-store.md#account_source) |
| `next_refresh_at` | string, null | [`account`](/architecture/sql-store.md#account) |

#### AccountCreate

| Field | Type | Source of truth |
|---|---|---|
| `domain` | string: a domain or URL | normalised into [`account`](/architecture/sql-store.md#account) `domain` |
| `name` | string | [`account`](/architecture/sql-store.md#account) |
| `country_code`, `industry`, `employee_count`, `revenue_eur`, `operational_complexity` | optional | [`account`](/architecture/sql-store.md#account), written as `MANUAL` |
| `parent_account_id`, `linkedin_url`, `notes` | string, optional | [`account`](/architecture/sql-store.md#account) |
| `aliases` | string[], optional | [`account_alias`](/architecture/sql-store.md#account_alias) |
| `sources` | array of `{kind, url}`, optional | [`account_source`](/architecture/sql-store.md#account_source), origin `MANUAL` |

#### AccountUpdate

| Field | Type | Source of truth |
|---|---|---|
| every field of [`AccountCreate`](#accountcreate) except `domain`, optional | | |
| `sources` | array of `{kind, url, status}`, optional | [`account_source`](/architecture/sql-store.md#account_source) |
| `status` | enum, optional | [`account`](/architecture/sql-store.md#account) `status` |

#### AccountImportRow

One CSV row. The file is UTF-8, comma-separated, with this header row; the column names are literal.

| Column | Type | Source of truth |
|---|---|---|
| `domain` | required | [`account`](/architecture/sql-store.md#account) `domain` |
| `name` | required | [`account`](/architecture/sql-store.md#account) `name` |
| `country_code` | optional | [`account`](/architecture/sql-store.md#account) |
| `industry` | optional | [`account`](/architecture/sql-store.md#account) `industry` |
| `employee_count` | optional | [`account`](/architecture/sql-store.md#account) |
| `revenue_eur` | optional | [`account`](/architecture/sql-store.md#account) |
| `aliases` | optional, separated by `;` | [`account_alias`](/architecture/sql-store.md#account_alias) |
| `newsroom_url` | optional | [`account_source`](/architecture/sql-store.md#account_source) of kind `NEWSROOM` |
| `careers_url` | optional | [`account_source`](/architecture/sql-store.md#account_source) of kind `CAREERS` |
| `investor_relations_url` | optional | [`account_source`](/architecture/sql-store.md#account_source) of kind `INVESTOR_RELATIONS` |
| `rss_url` | optional | [`account_source`](/architecture/sql-store.md#account_source) of kind `RSS_FEED` |
| `operational_complexity` | optional | [`account`](/architecture/sql-store.md#account) `operational_complexity` |
| `linkedin_url` | optional | [`account`](/architecture/sql-store.md#account) |
| `notes` | optional | [`account`](/architecture/sql-store.md#account) |

#### ImportResult

| Field | Type | Source of truth |
|---|---|---|
| `dry_run` | boolean | the request |
| `rows` | array of `{line, domain, outcome, account_id, errors}` | `outcome` is `CREATED`, `UPDATED`, `POSSIBLE_DUPLICATE` or `INVALID`; `errors` as `details.fields[]` |
| `created`, `updated`, `duplicates`, `invalid` | integer | counts of `rows` |

#### Contact

| Field | Type | Source of truth |
|---|---|---|
| `id`, `account_id`, `full_name`, `job_title`, `source_url` | string | [`contact`](/architecture/sql-store.md#contact) |
| `persona` | enum | [`contact`](/architecture/sql-store.md#contact) `persona` |
| `persona_origin` | enum | [`contact`](/architecture/sql-store.md#contact) |
| `retain_until` | string (date) | [`contact`](/architecture/sql-store.md#contact) |

#### ContactCreate

| Field | Type | Source of truth |
|---|---|---|
| `full_name`, `job_title`, `source_url` | string | [`contact`](/architecture/sql-store.md#contact) |
| `persona` | enum, optional | [`contact`](/architecture/sql-store.md#contact) `persona`, written as `MANUAL` |

#### ContactUpdate

| Field | Type | Source of truth |
|---|---|---|
| every field of [`ContactCreate`](#contactcreate), optional | | |

## Discovery

### Discovery contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-29` | POST | `/services/{id}/discovery-runs` | `*` | — → [`Run`](#run) |
| `API-30` | GET | `/discovery-candidates` | `*` | query `service_id`, `status` → `Page<`[`DiscoveryCandidate`](#discoverycandidate)`>` |
| `API-31` | POST | `/discovery-candidates/{id}/accept` | `*` | [`CandidateDecision`](#candidatedecision) → [`Account`](#account) |
| `API-32` | POST | `/discovery-candidates/{id}/reject` | `*` | [`CandidateDecision`](#candidatedecision) → [`DiscoveryCandidate`](#discoverycandidate) |

- `API-29` — one queued or running discovery per service; a second request returns it.
- `API-30` — ordered by `fit_estimate` descending.
- `API-31`, `API-32` — only a `PENDING` candidate can be decided (`409` otherwise). Acceptance follows [Discovery](/architecture/rules.md#discovery): no domain answers `422`; an existing domain answers `409` with `details.entity_id`.

### Discovery shapes

#### DiscoveryCandidate

| Field | Type | Source of truth |
|---|---|---|
| `id`, `service_id`, `name` | string | [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) |
| `domain`, `country_code` | string, null | [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) |
| `industry` | enum, null | [`account`](/architecture/sql-store.md#account) `industry` |
| `employee_count` | integer, null | [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) |
| `origin`, `status` | enum | [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) |
| `fit_estimate` | integer | [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) |
| `evidence` | `{document_id, title, url, published_at, quote}`, null | the candidate's [`document`](/architecture/sql-store.md#document) and `quote`; `NEWS_MENTION` only |
| `reject_reason`, `account_id` | string, null | [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) |

#### CandidateDecision

| Field | Type | Source of truth |
|---|---|---|
| `domain` | string, optional | acceptance: the domain when the candidate has none |
| `reason` | string, optional | rejection: [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) `reject_reason` |

## Runs and source plug-ins

### Runs and source plug-ins contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-33` | POST | `/accounts/{id}/refresh` | `*` | — → [`Run`](#run) |
| `API-34` | GET | `/runs` | `*` | query `kind`, `status`, `account_id`, `service_id` → `Page<`[`Run`](#run)`>` |
| `API-35` | GET | `/runs/{id}` | `*` | — → [`Run`](#run) |
| `API-36` | POST | `/runs/{id}/cancel` | `*` | — → [`Run`](#run) |
| `API-37` | GET | `/source-plugins` | `A` | — → [`SourcePlugin`](#sourceplugin)`[]` |
| `API-38` | PATCH | `/source-plugins/{code}` | `A` | [`SourcePluginUpdate`](#sourcepluginupdate) → [`SourcePlugin`](#sourceplugin) |

- `API-33` — an inactive account answers `409`. The frontend polls `API-35` for progress ([ADR-13](/architecture/adrs/adr-13-run-progress-by-polling.md)).
- `API-34` — newest first.
- `API-36` — a `RECLASSIFY`, `RESCORE` or `EVALUATION` run can be cancelled by an Admin only (`403 FORBIDDEN` for Sales), so a user cannot leave a question's stored passages or a scoring version half applied. It cancels the run's `READY` jobs; running jobs finish their current step; the run ends `CANCELLED`. A finished run answers `409`.

### Runs and source plug-ins shapes

#### Run

| Field | Type | Source of truth |
|---|---|---|
| `id` | string | [`pipeline_run`](/architecture/sql-store.md#pipeline_run) |
| `kind`, `trigger`, `status`, `stage` | enum | [`pipeline_run`](/architecture/sql-store.md#pipeline_run) |
| `progress`, `errors` | object, array | [`pipeline_run`](/architecture/sql-store.md#pipeline_run) |
| `account`, `service` | `{id, name}`, null | [`account`](/architecture/sql-store.md#account), [`service`](/architecture/sql-store.md#service) |
| `question` | `{id, key}`, null | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `requested_by_name` | string, null | `display_name` of `requested_by` |
| `created_at`, `started_at`, `finished_at` | string, null | [`pipeline_run`](/architecture/sql-store.md#pipeline_run) |
| `ai_cost_eur` | number | sum of `cost_eur` of the run's `AI_CALL` rows in [`audit_event`](/architecture/sql-store.md#audit_event) |

#### SourcePlugin

| Field | Type | Source of truth |
|---|---|---|
| `code` | enum | [`source_plugin`](/architecture/sql-store.md#source_plugin) `code` |
| `enabled`, `rate_limit_per_minute`, `daily_quota` | | [`source_plugin`](/architecture/sql-store.md#source_plugin) |
| `needs_key` | boolean | the plug-in values table of [`source_plugin`](/architecture/sql-store.md#source_plugin) |
| `key_configured` | boolean | whether the plug-in's key is set in the [worker runtime](/architecture/services/worker.md#runtime); the key itself is never returned |
| `available` | boolean | [Plug-in availability](/architecture/rules.md#plug-in-availability) |
| `requests_today` | integer | [`plugin_usage`](/architecture/sql-store.md#plugin_usage) |
| `last_success_at`, `last_error`, `last_error_at` | string, null | [`source_plugin`](/architecture/sql-store.md#source_plugin) |

#### SourcePluginUpdate

| Field | Type | Source of truth |
|---|---|---|
| `enabled`, `rate_limit_per_minute`, `daily_quota` | optional | [`source_plugin`](/architecture/sql-store.md#source_plugin) |

## Prospects and evidence

### Prospects and evidence contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-39` | GET | `/services/{id}/prospects` | `*` | query `standing` (default `RANKED`), `band[]`, `country_code[]`, `industry[]`, `q`, `sort` → `Page<`[`ProspectRow`](#prospectrow)`>` |
| `API-40` | GET | `/accounts/{id}/scores/{service_id}` | `*` | — → [`ScoreView`](#scoreview) |
| `API-41` | GET | `/accounts/{id}/scores/{service_id}/history` | `*` | — → [`ScoreChange`](#scorechange)`[]` |
| `API-42` | GET | `/accounts/{id}/findings` | `*` | query `service_id`, `question_id`, `status` → [`FindingView`](#findingview)`[]` |
| `API-43` | GET | `/findings/{id}/evidence` | `*` | — → [`EvidenceView`](#evidenceview) |
| `API-44` | POST | `/accounts/{id}/scores/{service_id}/overrides` | `A` | [`OverrideCreate`](#overridecreate) → [`Override`](#override) |
| `API-45` | POST | `/overrides/{id}/revoke` | `A` | — → [`Override`](#override) |

- `API-39` — the current score rows of the service's active accounts; `sort` is `priority` (the ranking order of [Priority, standing and band](/architecture/rules.md#priority-standing-and-band), the default), `intent`, `fit`, `name` or `last_refreshed`.
- `API-40` — `404` when the account has no score for the service yet.
- `API-41` — newest first; each entry compares a score row with the one before it.
- `API-42` — default `status` is `ACTIVE`; ordered by contribution, then `observed_at` descending.
- `API-44` — the rule key must name a rule of the service's active settings that currently matches for the account (`422` otherwise); an active override for the same rule answers `409`. Enqueues a `RESCORE` with trigger `OVERRIDE`. `API-45` does the same on revocation.

### Prospects and evidence shapes

#### ProspectRow

| Field | Type | Source of truth |
|---|---|---|
| `rank` | integer, null | position in the ranking; null unless `RANKED` |
| `account` | `{id, name, domain, country_code, industry}` | [`account`](/architecture/sql-store.md#account) |
| `fit`, `intent`, `priority` | integer | current [`account_score`](/architecture/sql-store.md#account_score) |
| `standing`, `band` | enum | current [`account_score`](/architecture/sql-store.md#account_score) |
| `top_signals` | array of `{question_key, question_text, strength, observed_at}`, at most 2 | the positive findings with the most `points` in the breakdown |
| `finding_count` | integer | in-force [`finding`](/architecture/sql-store.md#finding) rows of the service |
| `unread_alerts` | integer | unacknowledged [`alert`](/architecture/sql-store.md#alert) rows |
| `as_of` | string | current [`account_score`](/architecture/sql-store.md#account_score) |
| `last_refreshed_at` | string, null | [`account`](/architecture/sql-store.md#account) |

#### ScoreView

| Field | Type | Source of truth |
|---|---|---|
| `score_id`, `account_id`, `service_id` | string | current [`account_score`](/architecture/sql-store.md#account_score) |
| `scoring_version` | integer | its [`scoring_config`](/architecture/sql-store.md#scoring_config) `version` |
| `as_of`, `fit`, `intent`, `priority` | | [`account_score`](/architecture/sql-store.md#account_score) |
| `standing`, `band` | enum | [`account_score`](/architecture/sql-store.md#account_score) |
| `rank` | integer, null | as [`ProspectRow`](#prospectrow) |
| `breakdown` | object | the [Score breakdown](/architecture/rules.md#score-breakdown), with each question entry's `question_text` added |
| `overrides` | [`Override`](#override)`[]` | the account's overrides for the service, active and revoked |
| `lead_feedback` | [`LeadFeedback`](#leadfeedback), null | the in-force [`lead_feedback`](/architecture/sql-store.md#lead_feedback) |

#### ScoreChange

| Field | Type | Source of truth |
|---|---|---|
| `score_id`, `as_of`, `fit`, `intent`, `priority`, `standing`, `band` | | the [`account_score`](/architecture/sql-store.md#account_score) row |
| `scoring_version` | integer | its [`scoring_config`](/architecture/sql-store.md#scoring_config) `version` |
| `trigger`, `run_id` | | the row's [`pipeline_run`](/architecture/sql-store.md#pipeline_run) |
| `change_note` | string, null | its [`scoring_config`](/architecture/sql-store.md#scoring_config) `change_note`, when the version changed |
| `findings_added`, `findings_removed` | array of `{finding_id, question_key}` | finding ids in this breakdown and not the previous one, and the reverse |
| `overrides_changed` | array of `{rule_key, overridden}` | disqualifiers whose `overridden` flag differs from the previous breakdown |

#### FindingView

| Field | Type | Source of truth |
|---|---|---|
| `id`, `account_id` | string | [`finding`](/architecture/sql-store.md#finding) |
| `service_id` | string | the question's [`service`](/architecture/sql-store.md#service) |
| `question` | `{id, key, text, polarity}` | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `question_revision`, `confidence`, `quote`, `quote_en`, `rationale`, `observed_at` | | [`finding`](/architecture/sql-store.md#finding) |
| `strength`, `decided_by`, `status` | enum | [`finding`](/architecture/sql-store.md#finding) |
| `option` | `{key, label}`, null | the question's option named by [`finding`](/architecture/sql-store.md#finding) `option_key`; `CHOICE` only |
| `document` | `{id, title, url, source_type, plugin_code, language, published_at}` | [`document`](/architecture/sql-store.md#document) |
| `points` | number, null | the finding's `points` in the current breakdown; null when it is not the counted finding of its question |
| `feedback` | `{verdict, user_name, created_at}`, null | the in-force [`finding_feedback`](/architecture/sql-store.md#finding_feedback) |

#### EvidenceView

| Field | Type | Source of truth |
|---|---|---|
| `finding_id` | string | [`finding`](/architecture/sql-store.md#finding) |
| `document` | as in [`FindingView`](#findingview) | [`document`](/architecture/sql-store.md#document) |
| `purged` | boolean | whether the document's `purged_at` is set |
| `excerpt` | string, null | the passage with up to `EVIDENCE_CONTEXT_CHARS` of document text on each side; null when purged |
| `quote_start`, `quote_end` | integer, null | offsets of the quote in `excerpt` |

#### Override

| Field | Type | Source of truth |
|---|---|---|
| `id`, `account_id`, `service_id`, `rule_key`, `note` | string | [`disqualifier_override`](/architecture/sql-store.md#disqualifier_override) |
| `rule_label` | string | the rule's `label` in the active settings |
| `status` | enum | [`disqualifier_override`](/architecture/sql-store.md#disqualifier_override) `status` |
| `created_by_name`, `created_at`, `revoked_by_name`, `revoked_at` | string, null | [`disqualifier_override`](/architecture/sql-store.md#disqualifier_override) |

#### OverrideCreate

| Field | Type | Source of truth |
|---|---|---|
| `rule_key` | string | [`disqualifier_override`](/architecture/sql-store.md#disqualifier_override) |
| `note` | string, required | [`disqualifier_override`](/architecture/sql-store.md#disqualifier_override) |

## Feedback and alerts

### Feedback and alerts contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-46` | POST | `/accounts/{id}/scores/{service_id}/feedback` | `*` | [`FeedbackCreate`](#feedbackcreate) → [`LeadFeedback`](#leadfeedback) |
| `API-47` | POST | `/findings/{id}/feedback` | `*` | [`FeedbackCreate`](#feedbackcreate) → [`FindingView`](#findingview) |
| `API-48` | GET | `/alerts` | `*` | query `service_id`, `unread` → `Page<`[`AlertView`](#alertview)`>` |
| `API-49` | POST | `/alerts/{id}/acknowledge` | `*` | — → [`AlertView`](#alertview) |

- `API-46`, `API-47` — apply [Feedback effects](/architecture/rules.md#feedback-effects). The verdict must be a [`lead_feedback`](/architecture/sql-store.md#lead_feedback) or [`finding_feedback`](/architecture/sql-store.md#finding_feedback) `verdict` value respectively.
- `API-48` — newest first; `unread` true lists unacknowledged alerts only.
- `API-49` — acknowledging an acknowledged alert returns it unchanged.

### Feedback and alerts shapes

#### FeedbackCreate

| Field | Type | Source of truth |
|---|---|---|
| `verdict` | enum | [`lead_feedback`](/architecture/sql-store.md#lead_feedback) or [`finding_feedback`](/architecture/sql-store.md#finding_feedback) `verdict` |
| `note` | string, optional | the same table's `note` |

#### LeadFeedback

| Field | Type | Source of truth |
|---|---|---|
| `id`, `note`, `created_at` | | [`lead_feedback`](/architecture/sql-store.md#lead_feedback) |
| `verdict` | enum | [`lead_feedback`](/architecture/sql-store.md#lead_feedback) `verdict` |
| `user_name` | string | `display_name` of `user_id` |

#### AlertView

| Field | Type | Source of truth |
|---|---|---|
| `id`, `created_at`, `acknowledged_at` | | [`alert`](/architecture/sql-store.md#alert) |
| `kind` | enum | [`alert`](/architecture/sql-store.md#alert) `kind` |
| `account`, `service` | `{id, name}` | [`account`](/architecture/sql-store.md#account), [`service`](/architecture/sql-store.md#service) |
| `finding` | `{id, question_text, strength, quote}`, null | [`finding`](/architecture/sql-store.md#finding); `STRONG_SIGNAL` only |
| `band_change` | `{from, to}`, null | bands of the previous and the alert's [`account_score`](/architecture/sql-store.md#account_score); `BAND_UP` only |
| `acknowledged_by_name` | string, null | `display_name` of `acknowledged_by` |

## Evaluation

### Evaluation contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-50` | GET | `/evaluation/label-queue` | `*` | query `service_id` → [`LabelTask`](#labeltask)`[]` |
| `API-51` | POST | `/evaluation/items` | `*` | [`LabelCreate`](#labelcreate) → [`EvaluationItem`](#evaluationitem) |
| `API-52` | GET | `/evaluation/items` | `A` | query `question_id`, `origin`, `status` → `Page<`[`EvaluationItem`](#evaluationitem)`>` |
| `API-53` | POST | `/evaluation/runs` | `A` | — → [`Run`](#run) |
| `API-54` | GET | `/evaluation/results` | `A` | — → [`EvaluationResultSummary`](#evaluationresultsummary)`[]` |
| `API-55` | GET | `/evaluation/results/{run_id}` | `A` | — → [`EvaluationResult`](#evaluationresult) |

- `API-50` — the label queue of [Evaluation metrics](/architecture/rules.md#evaluation-metrics). A task never shows the classifier's answer, so that labels are not biased by it.
- `API-51` — writes or replaces the `MANUAL` item for the passage, question and revision; a revision that is not current answers `409`.
- `API-53` — one queued or running evaluation at a time.

### Evaluation shapes

#### LabelTask

| Field | Type | Source of truth |
|---|---|---|
| `chunk_id`, `passage_text` | string | [`chunk`](/architecture/sql-store.md#chunk) |
| `question` | `{id, key, text, answer_type, options, polarity}` | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `question_revision` | integer | [`signal_question`](/architecture/sql-store.md#signal_question) `revision` |
| `account` | `{id, name}` | [`account`](/architecture/sql-store.md#account) |
| `document` | `{title, url, language, published_at}` | [`document`](/architecture/sql-store.md#document) |

#### LabelCreate

| Field | Type | Source of truth |
|---|---|---|
| `chunk_id`, `question_id` | string | [`evaluation_item`](/architecture/sql-store.md#evaluation_item) |
| `question_revision` | integer | [`evaluation_item`](/architecture/sql-store.md#evaluation_item) |
| `expected_strength` | enum | [`finding`](/architecture/sql-store.md#finding) `strength` |

#### EvaluationItem

| Field | Type | Source of truth |
|---|---|---|
| `id`, `chunk_id`, `question_id`, `question_revision`, `created_at` | | [`evaluation_item`](/architecture/sql-store.md#evaluation_item) |
| `question_key` | string | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `expected_strength`, `origin`, `status` | enum | [`evaluation_item`](/architecture/sql-store.md#evaluation_item) |
| `labelled_by_name` | string | `display_name` of `labelled_by` |

#### EvaluationResultSummary

| Field | Type | Source of truth |
|---|---|---|
| `run_id`, `created_at` | string | [`evaluation_result`](/architecture/sql-store.md#evaluation_result) |
| `classifier` | enum | [`evaluation_result`](/architecture/sql-store.md#evaluation_result) |
| `items`, `passed` | | [`evaluation_result`](/architecture/sql-store.md#evaluation_result) |
| `precision`, `recall`, `escalation_rate` | number, null | its `metrics` |

#### EvaluationResult

| Field | Type | Source of truth |
|---|---|---|
| every field of [`EvaluationResultSummary`](#evaluationresultsummary) | | |
| `escalation_lower`, `escalation_upper` | number | [`evaluation_result`](/architecture/sql-store.md#evaluation_result) |
| `metrics` | object | [Evaluation metrics](/architecture/rules.md#evaluation-metrics) |

## Outreach and CRM

### Outreach and CRM contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-56` | POST | `/accounts/{id}/scores/{service_id}/outreach-drafts` | `*` | [`OutreachRequest`](#outreachrequest) → [`OutreachDraft`](#outreachdraft) |
| `API-57` | GET | `/accounts/{id}/outreach-drafts` | `*` | query `service_id` → [`OutreachDraft`](#outreachdraft)`[]` |
| `API-58` | PATCH | `/outreach-drafts/{id}` | `*` | [`OutreachDraftUpdate`](#outreachdraftupdate) → [`OutreachDraft`](#outreachdraft) |
| `API-59` | POST | `/accounts/{id}/scores/{service_id}/crm-push` | `*` | — → [`CrmSyncView`](#crmsyncview) |

- `API-56` — follows [Outreach grounding](/architecture/rules.md#outreach-grounding); an account without an in-force positive finding for the service answers `422`. There is no contract that sends a message.
- `API-58` — changing `subject` or `body` sets `edited`; `status` may only move to `EXPORTED`.
- `API-59` — without `HUBSPOT_ACCESS_TOKEN` answers `409 NOT_CONFIGURED`; otherwise calls `API-70` and records the outcome in [`crm_sync`](/architecture/sql-store.md#crm_sync).

### Outreach and CRM shapes

#### OutreachRequest

| Field | Type | Source of truth |
|---|---|---|
| `channel` | enum | [`outreach_draft`](/architecture/sql-store.md#outreach_draft) `channel` |
| `contact_id` | string, optional | a [`contact`](/architecture/sql-store.md#contact) of the account |

#### OutreachDraft

| Field | Type | Source of truth |
|---|---|---|
| `id`, `account_id`, `service_id`, `subject`, `body`, `edited`, `created_at` | | [`outreach_draft`](/architecture/sql-store.md#outreach_draft) |
| `channel`, `status` | enum | [`outreach_draft`](/architecture/sql-store.md#outreach_draft) |
| `contact` | `{id, full_name, job_title}`, null | [`contact`](/architecture/sql-store.md#contact) |
| `findings` | array of `{id, question_text, quote}` | the [`finding`](/architecture/sql-store.md#finding) rows of `finding_ids` |
| `created_by_name` | string | `display_name` of `created_by` |

#### OutreachDraftUpdate

| Field | Type | Source of truth |
|---|---|---|
| `subject`, `body` | string, optional | [`outreach_draft`](/architecture/sql-store.md#outreach_draft) |
| `status` | enum, optional | [`outreach_draft`](/architecture/sql-store.md#outreach_draft) `status` |

#### CrmSyncView

| Field | Type | Source of truth |
|---|---|---|
| `id`, `external_id`, `error`, `created_at` | | [`crm_sync`](/architecture/sql-store.md#crm_sync) |
| `target`, `status` | enum | [`crm_sync`](/architecture/sql-store.md#crm_sync) |

## Audit and health

### Audit and health contracts

| ID | Method | Path | Roles | Request → response |
|---|---|---|---|---|
| `API-60` | GET | `/audit` | `A` | query `kind[]`, `action`, `actor_id`, `entity_id`, `run_id`, `from`, `to` → `Page<`[`AuditEntry`](#auditentry)`>` |
| `API-61` | GET | `/health` | `-` | — → [`Health`](#health) |

- `API-60` — newest first; without `from` the range is the last `AUDIT_DEFAULT_RANGE_DAYS` days.
- `API-61` — answers `200` when the database is reachable, else `503`; the other checks report without changing the status code.

### Audit and health shapes

#### AuditEntry

| Field | Type | Source of truth |
|---|---|---|
| `id`, `occurred_at`, `entity_type`, `entity_id`, `run_id`, `request_id`, `payload` | | [`audit_event`](/architecture/sql-store.md#audit_event) |
| `kind`, `action` | enum, string | [`audit_event`](/architecture/sql-store.md#audit_event); `action` from [Audit actions](/architecture/sql-store.md#audit-actions) |
| `actor_name` | string, null | `display_name` of `actor_id`; null for the system |

#### Health

| Field | Type | Source of truth |
|---|---|---|
| `status` | `OK`, `DEGRADED`, `DOWN` | `DOWN` when the database check fails; `DEGRADED` when another check fails |
| `checks` | object: `database`, `embedder`, `classifier`, `llm` → `OK`, `DOWN` or `NOT_CONFIGURED` | a lightweight call to each dependency, bounded by `HEALTH_TIMEOUT_MS` |

## Classifier

The in-process port every classification goes through ([ADR-02](/architecture/adrs/adr-02-classification-cascade.md)). Two adapters implement it, selected by `CLASSIFIER_PROVIDER`: `JEV` calls TypeSafe's Jev through OpenRouter's Decisions API; `LLM` asks `LLM_CLASSIFIER_MODEL` for the same probabilities through structured output. Both are behind the [AI gateway](/architecture/services/worker.md#ai-gateway).

### Classifier contracts

| ID | Operation | Module | Transaction | Returns |
|---|---|---|---|---|
| `API-62` | `classify(request)` | AI gateway, classifier port | none | [`ClassifierAnswer`](#classifieranswer)`[]`, one per question, or `UPSTREAM_UNAVAILABLE` |

- Every question of a request is answered over the same state in one call. Each call writes one `AI_CALL` audit row with role `CLASSIFIER`.
- The answer's probabilities for a question sum to 1 within 0.001; any other output is `INVALID_OUTPUT` and the call fails.

### Classifier shapes

#### ClassifierRequest

| Field | Type | Source of truth |
|---|---|---|
| `state` | string | the text judged: a passage, or a document's title and opening |
| `context` | string, optional | one line naming the account, e.g. "Company: Lufthansa Group (lufthansagroup.com, DE)" |
| `questions` | array of `{id, kind, text, options}` | `kind` is `YES_NO`, `SCALE` or `CHOICE`; `options` is `[{key, label}]` for `SCALE` and `CHOICE`; built by [Signal classification](/architecture/rules.md#signal-classification) and [Triage](/architecture/rules.md#triage) |

#### ClassifierAnswer

| Field | Type | Source of truth |
|---|---|---|
| `question_id` | string | the request's question `id` |
| `probabilities` | object: answer key → number 0–1 | `YES` and `NO` for `YES_NO`; the option keys otherwise |

## LLM

The in-process port for the four generation roles, all calling OpenRouter's chat completions API with a versioned prompt and structured output ([AI roles and boundaries](/architecture/overview.md#ai-roles-and-boundaries)).

### LLM contracts

| ID | Operation | Module | Transaction | Returns |
|---|---|---|---|---|
| `API-63` | `escalate(input)` | AI gateway, `LLM_EVIDENCE_MODEL` | none | [`EscalationOutput`](#escalationoutput) |
| `API-64` | `extract_evidence(input)` | AI gateway, `LLM_EVIDENCE_MODEL` | none | [`EvidenceOutput`](#evidenceoutput) |
| `API-65` | `extract_organisations(input)` | AI gateway, `LLM_EVIDENCE_MODEL` | none | [`Organisation`](#organisation)`[]` |
| `API-66` | `draft_outreach(input)` | AI gateway, `LLM_OUTREACH_MODEL` | none | [`OutreachOutput`](#outreachoutput) |

- Every call passes the [Budget guard](/architecture/rules.md#budget-guard) first, times out after `AI_CALL_TIMEOUT_S`, writes one `AI_CALL` audit row and returns output that its rule has validated, or fails with `UPSTREAM_UNAVAILABLE` or `BUDGET_EXHAUSTED`.

### LLM shapes

#### EscalationInput

| Field | Type | Source of truth |
|---|---|---|
| `account_name` | string | [`account`](/architecture/sql-store.md#account) |
| `question` | `{text, answer_type, options}` | [`signal_question`](/architecture/sql-store.md#signal_question) |
| `passage`, `language` | string | [`chunk`](/architecture/sql-store.md#chunk), [`document`](/architecture/sql-store.md#document) |

#### EscalationOutput

| Field | Type | Source of truth |
|---|---|---|
| `strength` | enum | [`finding`](/architecture/sql-store.md#finding) `strength`, `NONE` included; for a `CHOICE` question, the strength of `option_key` |
| `option_key` | string, null | `CHOICE` only: the key of the chosen option; becomes [`finding`](/architecture/sql-store.md#finding) `option_key` |
| `confidence` | number 0–1 | becomes [`finding`](/architecture/sql-store.md#finding) `confidence` |
| `quote`, `quote_en`, `rationale` | string, null | as [`EvidenceOutput`](#evidenceoutput); null when `strength` is `NONE` |

#### EvidenceInput

| Field | Type | Source of truth |
|---|---|---|
| every field of [`EscalationInput`](#escalationinput) | | |
| `strength` | enum | the classifier's candidate strength |

#### EvidenceOutput

| Field | Type | Source of truth |
|---|---|---|
| `quote`, `quote_en`, `rationale` | string, `quote_en` null for English | validated by [Evidence extraction](/architecture/rules.md#evidence-extraction) |

#### DiscoveryInput

| Field | Type | Source of truth |
|---|---|---|
| `service_description` | string | [`service`](/architecture/sql-store.md#service) `description` |
| `text`, `language` | string | the news [`document`](/architecture/sql-store.md#document) |

#### Organisation

| Field | Type | Source of truth |
|---|---|---|
| `name` | string | becomes [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) `name` |
| `country_code`, `website` | string, null | only when the text states them |
| `quote` | string | verbatim sentence naming the company and its signal; checked as a substring of `text` |

#### OutreachInput

| Field | Type | Source of truth |
|---|---|---|
| `account_name` | string | [`account`](/architecture/sql-store.md#account) |
| `service` | `{name, value_proposition}` | [`service`](/architecture/sql-store.md#service) |
| `findings` | array of `{id, question_text, quote, quote_en, observed_at, url}` | selected by [Outreach grounding](/architecture/rules.md#outreach-grounding) |
| `contact` | `{full_name, job_title, persona}`, null | [`contact`](/architecture/sql-store.md#contact) |
| `channel` | enum | [`outreach_draft`](/architecture/sql-store.md#outreach_draft) `channel` |
| `sender_name` | string | the user's `display_name` |

#### OutreachOutput

| Field | Type | Source of truth |
|---|---|---|
| `subject` | string, null | `EMAIL` only |
| `body` | string | validated by [Outreach grounding](/architecture/rules.md#outreach-grounding) |
| `cited_finding_ids` | string[] | becomes [`outreach_draft`](/architecture/sql-store.md#outreach_draft) `finding_ids` |

## Embedder

The HTTP port to the embedder container, Hugging Face Text Embeddings Inference serving `bge-m3` ([ADR-08](/architecture/adrs/adr-08-multilingual-embeddings.md)).

### Embedder contracts

| ID | Operation | Module | Transaction | Returns |
|---|---|---|---|---|
| `API-67` | `embed(texts)`: `POST {EMBEDDER_URL}/embed` | embedder client | none | one vector per text, or `UPSTREAM_UNAVAILABLE` |

- At most `EMBED_BATCH_SIZE` texts per call. The response must contain exactly one vector of `EMBEDDING_DIM` finite numbers per text, else the call fails. Embedding calls are logged, not audited: they are local, free and make no judgement.

### Embedder shapes

#### EmbedRequest

| Field | Type | Source of truth |
|---|---|---|
| `inputs` | string[] | passage texts, or a question's text followed by its hint terms |

## Source plug-ins

The in-process port each [source plug-in](/architecture/services/worker.md#source-plug-ins) implements.

### Source plug-ins contracts

| ID | Operation | Module | Transaction | Returns |
|---|---|---|---|---|
| `API-68` | `fetch(context)` | the plug-in's adapter | none | [`RawItem`](#rawitem)`[]` |
| `API-69` | `search(query)` | `CRUNCHBASE`, `GDELT`, `NEWSAPI`, `SERPAPI` adapters | none | [`RawItem`](#rawitem)`[]` for news, organisation records for `CRUNCHBASE` |

- An adapter makes no request when its plug-in is unavailable, counts every request in [`plugin_usage`](/architecture/sql-store.md#plugin_usage) and raises a typed error on failure; it never returns a partial list as if it were complete.

### Source plug-ins shapes

#### FetchContext

| Field | Type | Source of truth |
|---|---|---|
| `account` | `{id, name, domain, aliases, country_code, crunchbase_id}` | [`account`](/architecture/sql-store.md#account), [`account_alias`](/architecture/sql-store.md#account_alias) |
| `sources` | array of `{kind, url}` | the account's `ACTIVE` [`account_source`](/architecture/sql-store.md#account_source) rows |
| `since`, `until` | string | [Fetch window](/architecture/rules.md#fetch-window) |
| `queries` | string[] | news queries from [Fetch window](/architecture/rules.md#fetch-window) |
| `max_items` | integer | the plug-in's share of `MAX_DOCUMENTS_PER_REFRESH` |

#### RawItem

| Field | Type | Source of truth |
|---|---|---|
| `url`, `title`, `published_at` | string, null | become [`document`](/architecture/sql-store.md#document) columns |
| `content_type` | `HTML`, `PDF`, `JSON` | how [Document normalisation](/architecture/rules.md#document-normalisation) extracts the text |
| `body` | bytes | the fetched content |
| `source_type` | enum | [`document`](/architecture/sql-store.md#document) `source_type` |
| `plugin_code` | enum | [`source_plugin`](/architecture/sql-store.md#source_plugin) `code` |

## CRM

### CRM contracts

| ID | Operation | Module | Transaction | Returns |
|---|---|---|---|---|
| `API-70` | `upsert_company(push)` | HubSpot adapter: CRM v3 companies API, search by `domain`, then update or create | none | the HubSpot company id, or `UPSTREAM_UNAVAILABLE` |

### CRM shapes

#### CompanyPush

| Field | Type | Source of truth |
|---|---|---|
| `domain`, `name` | string | [`account`](/architecture/sql-store.md#account) |
| `leadradar_service` | string | [`service`](/architecture/sql-store.md#service) `name` |
| `leadradar_priority`, `leadradar_band`, `leadradar_standing` | | the current [`account_score`](/architecture/sql-store.md#account_score) |
| `leadradar_top_signals` | string | the question texts and quotes of up to three top findings, one per line |
| `leadradar_url` | string | `APP_BASE_URL` + the account detail route |
