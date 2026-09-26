---
type: Feature
title: Audit trail
description: The append-only record of who changed what and of every classifier and LLM call with its model, prompt version, cost and outcome, as the Admin's Audit log screen filters and reads it back.
status: draft
tags: [audit-trail]
---

# Audit trail

## Purpose

Every configuration change, exception, piece of feedback, run and AI call is recorded, so that any score can be traced back to the settings, signals and decisions behind it and any model call to its model, prompt version and cost. The record is append-only; nothing in the product edits or deletes it. It also feeds the daily LLM budget.

## Flows

### FL-21 Review the audit trail

1. An Admin opens the [Audit log](#audit-log).
2. The Admin filters by kind, action, user, entity, run and date range — for example all `AI_CALL` rows of one refresh, or every `CONFIG` change of the last week.
3. The Admin expands an entry to read its payload, and from a run's entries follows the link to [Runs](/features/signal-pipeline.md#runs).

## Reading order

1. Terms in the [glossary](/requirements/glossary.md): Audit event, AI call, AI role, Budget guard.
2. Requirement rows: `S-AUD-01`, `S-AUD-02` in [system requirements](/requirements/system.md); `B-31`, `B-32`, `RULE-09` in [business requirements](/requirements/business.md).
3. Stores: [`audit_event`](/architecture/sql-store.md#audit_event) and [Audit actions](/architecture/sql-store.md#audit-actions).
4. Rules: [Budget guard](/architecture/rules.md#budget-guard), which reads the `AI_CALL` rows.
5. Interfaces: [Audit and health](/architecture/interfaces.md#audit-and-health) (`API-60`, [`AuditEntry`](/architecture/interfaces.md#auditentry)).
6. Services: the [api](/architecture/services/api.md) (`AUDIT_DEFAULT_RANGE_DAYS`); the [AI gateway](/architecture/services/worker.md#ai-gateway), which writes `AI_CALL` rows; [AI roles and boundaries](/architecture/overview.md#ai-roles-and-boundaries); the [frontend](/architecture/services/frontend.md) shell.
7. Decisions: [ADR-03](/architecture/adrs/adr-03-models-answer-rules-score.md).
8. Screens: [Audit log](#audit-log).
9. Acceptance rows in [acceptance criteria](/requirements/acceptance.md): `AC-55`, `AC-56`.

## Audit log

Route `/audit`. Admin only.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Audit log   Kind [AI call ▾]  Action ▾  User ▾  Run [ … ]  From [ ] To [ ]   │
├─────────────────────┬──────────────┬─────────────────┬───────────────────────┤
│ When                │ Who          │ Action          │ Subject               │
├─────────────────────┼──────────────┼─────────────────┼───────────────────────┤
│ 2026-09-25 09:14:02 │ system       │ AI_CALL         │ ESCALATION · google/gemini-2.5-flash · v2 · €0.012 · 1.8 s · OK │
│ 2026-09-25 09:13:57 │ system       │ AI_CALL         │ CLASSIFIER · JEV · 6 questions · 0.2 s · OK │
│ 2026-09-25 08:40:11 │ Olga Admin   │ SCORING_ACTIVATED │ Intelligent Automation v3 "Hiring counts less" │
└─────────────────────┴──────────────┴─────────────────┴───────────────────────┘
```

WF-23 — Audit log

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-098` | The screen shall list entries newest first with time, actor or "system", action and a one-line subject built from the entity and payload; an `AI_CALL` line shows role, provider or model, prompt version, cost, latency and outcome. |
| `FR-099` | Filters shall cover kind, action, user, entity, run and date range, defaulting to the last `AUDIT_DEFAULT_RANGE_DAYS` days. |
| `FR-100` | Expanding an entry shall show its full payload; an entry with a run shall link to it on [Runs](/features/signal-pipeline.md#runs). |
| `FR-153` | The kind filter shall be a segmented control with All, AI calls and Changes, and an entry shall expand in place to show its payload. |

Obligations: `S-AUD-02`.

**Data**: `API-04`, `API-60`. **States**: [States](/architecture/services/frontend.md#states).
