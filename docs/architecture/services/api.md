---
type: Service
title: API service
description: The FastAPI process - its responsibilities and boundary, the tables and rules it owns, request handling, transactions, enqueueing, the interactive AI calls it makes, and its configuration keys.
status: draft
tags: [accounts-and-discovery, audit-trail, evaluation-and-feedback, identity-and-access, outreach-and-crm, prospect-dashboard, service-configuration, signal-pipeline]
---

# API service

## Responsibilities

The api answers every REST contract of [interfaces](/architecture/interfaces.md): sign-in and users, configuration, accounts and contacts, run requests, prospects, evidence, overrides, feedback, labels, outreach drafts, the HubSpot push, the audit and health. It validates input, writes what a user changed, enqueues the background work the change requires, and makes the two interactive AI calls: question preview and outreach drafting. It owns the schema and applies migrations at start.

It never fetches from a source, never classifies in batch, never writes a score, and never sends a message to anyone outside the product.

## Owns

- **Tables and columns**: those of the api column of [store ownership](/architecture/overview.md#store-ownership); the Alembic migrations of the whole [SQL store](/architecture/sql-store.md).
- **Rules implemented**: [Account identity](/architecture/rules.md#account-identity), [Scoring settings validation](/architecture/rules.md#scoring-settings-validation), [Feedback effects](/architecture/rules.md#feedback-effects) (the status and label writes; the rescore is the worker's), the label queue of [Evaluation metrics](/architecture/rules.md#evaluation-metrics), [Outreach grounding](/architecture/rules.md#outreach-grounding), [Persona mapping](/architecture/rules.md#persona-mapping) on contact creation and edit, and erasure on request of [Retention and erasure](/architecture/rules.md#retention-and-erasure).
- **Rules invoked**, implemented by the [worker](/architecture/services/worker.md): [Chunking and passage selection](/architecture/rules.md#chunking-and-passage-selection), [Signal classification](/architecture/rules.md#signal-classification), [Escalation](/architecture/rules.md#escalation) and [Evidence extraction](/architecture/rules.md#evidence-extraction) for question preview, without writing; [Fit score](/architecture/rules.md#fit-score) through [Priority, standing and band](/architecture/rules.md#priority-standing-and-band) for scoring preview, without writing.

## Provides and consumes

- Provides every REST family of [interfaces](/architecture/interfaces.md), `API-01` to `API-61`.
- Consumes the [Classifier](/architecture/interfaces.md#classifier) and [LLM](/architecture/interfaces.md#llm) ports through the worker's [AI gateway](/architecture/services/worker.md#ai-gateway) module, the [Embedder](/architecture/interfaces.md#embedder) and the [CRM](/architecture/interfaces.md#crm) port.

## Design

**Layering.** A route validates its input into a Pydantic model, calls one function of the capability it belongs to, and shapes the response; that function owns the transaction and is the only code that touches the database for the request. Capabilities follow the interface families: auth and users, services and questions, scoring, accounts and contacts, discovery, runs and plug-ins, prospects and evidence, feedback and alerts, evaluation, outreach and CRM, audit. Errors are typed per capability and mapped once, at the edge, onto the envelope of [Conventions](/architecture/interfaces.md#conventions).

**Transactions.** One transaction per request. A change and the work it triggers commit together: the row the user changed, its audit row, and any `pipeline_run` with its first `job` rows are written in the same transaction, so a crash never leaves a change without its reclassification or rescore, or the reverse. The partial unique indexes of [constraints](/architecture/sql-store.md#constraints-and-indexes) make a concurrent duplicate refresh or discovery answer with the existing run.

**Enqueueing.** The api creates a run in status `QUEUED` with the jobs of its first stage, at the priority the [job queue](/architecture/services/worker.md#job-queue) assigns to its trigger. It never waits for a job.

**Interactive AI calls.** Question preview (`API-14`) and outreach drafting (`API-56`) call the AI gateway in the request, bounded by `AI_CALL_TIMEOUT_S`. Both pass the [Budget guard](/architecture/rules.md#budget-guard) and write `AI_CALL` audit rows. Preview writes nothing else.

**Sessions and passwords.** Passwords are hashed with argon2id. The session token is 32 random bytes, sent only in the cookie; the database holds its SHA-256.

**Request identity.** Every request gets a request id, returned in the `X-Request-Id` header, written to every log line and audit row of the request.

**Import.** `API-22` streams the CSV, validates every row with the [`AccountImportRow`](/architecture/interfaces.md#accountimportrow) rules, and in a non-dry run writes all valid rows in one transaction with one `ACCOUNTS_IMPORTED` audit row plus one `ACCOUNT_CREATED` or `ACCOUNT_UPDATED` row per account.

**OpenAPI.** The served OpenAPI document is generated from the routes; the frontend's client is generated from a committed snapshot of it, regenerated whenever a contract changes.

## Runtime

| Key | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | — (required) | PostgreSQL connection string |
| `APP_BASE_URL` | `http://localhost:8080` | Public base URL of the frontend, used in HubSpot links and the crawler's user agent |
| `SESSION_TTL_HOURS` | `12` | Session lifetime |
| `LOGIN_MAX_FAILURES` | `5` | Consecutive failed sign-ins before a lock |
| `LOGIN_LOCK_MINUTES` | `15` | Lock duration |
| `PASSWORD_MIN_LENGTH` | `12` | Minimum password length |
| `PAGE_SIZE_DEFAULT` | `50` | Default page size |
| `PAGE_SIZE_MAX` | `200` | Maximum page size |
| `IMPORT_MAX_ROWS` | `2000` | Maximum rows per CSV import |
| `PREVIEW_MAX_PASSAGES` | `5` | Passages returned by question preview |
| `EVIDENCE_CONTEXT_CHARS` | `600` | Document text shown on each side of an evidence passage |
| `LABEL_QUEUE_SIZE` | `20` | Tasks per label-queue request |
| `OUTREACH_MAX_FINDINGS` | `5` | Findings given to an outreach draft |
| `PROSPECT_TOP_SIGNALS` | `2` | Top signals shown on a Prospects row |
| `HUBSPOT_TOP_SIGNALS` | `3` | Top signals written to HubSpot |
| `IMPACT_PERIOD_DAYS` | `30` | Period the impact report covers |
| `MANUAL_RESEARCH_MINUTES_PER_ACCOUNT` | `120` | Minutes a sales manager spends researching one account by hand; an assumption until the sales team states it |
| `OUTREACH_EMAIL_MAX_CHARS` | `1200` | Maximum email body length |
| `OUTREACH_INMAIL_MAX_CHARS` | `1900` | Maximum InMail body length |
| `CONTACT_RETENTION_DAYS` | `730` | Sets a contact's `retain_until` at creation |
| `AUDIT_DEFAULT_RANGE_DAYS` | `30` | Default audit range |
| `HEALTH_TIMEOUT_MS` | `2000` | Timeout of each health check |
| `INTERACTIVE_P95_TARGET_MS` | `800` | Target p95 latency of interactive reads ([N-01](/requirements/system.md)) |
| `HUBSPOT_ACCESS_TOKEN` | unset | HubSpot private-app token; unset disables the push |
| `SEED_ADMIN_PASSWORD`, `SEED_SALES_PASSWORD` | — (required by `make seed-demo`) | Passwords of the demo users |
| `LOG_LEVEL` | `INFO` | Log level; logs are JSON lines |

The api also reads the AI gateway, embedder, fixture and `CLOCK_FILE` keys of the [worker runtime](/architecture/services/worker.md#runtime).

## Examples

A Sales user edits Lufthansa Group's employee count: `API-24` writes the value with origin `MANUAL`, an `ACCOUNT_UPDATED` audit row, and a `RESCORE` run with trigger `ACCOUNT_CHANGE` and its one `SCORE` job, which scores every active service, all in one transaction, and answers the updated [`Account`](/architecture/interfaces.md#account). The Fit change appears once the worker finishes the run.
