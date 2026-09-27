---
type: Decision
title: ADR-27 Outreach personalization and tone check
description: Outreach preferences are immutable generation inputs stored with a draft, while advisory tone checks run through the shared AI gateway and are audited but not stored.
status: draft
tags: [outreach-and-crm]
---

# ADR-27 Outreach personalization and tone check

## Context

Sales needs to choose how a draft is personalised and written, and to review the current editor text before sending it themselves. These operations use an LLM, so they must retain the product's single budgeted, recorded and audited path to OpenRouter. The choices that produced a draft must remain explainable after the draft is reopened, while tone advice does not change the draft.

## Decision

- [Outreach preferences](/architecture/sql-store.md#outreachpreferences) are optional immutable inputs of one generated [`outreach_draft`](/architecture/sql-store.md#outreach_draft), selected and enforced by [Outreach grounding](/architecture/rules.md#outreach-grounding). Null preserves generation from before this decision.
- The api, never the browser, invokes the [AI gateway](/architecture/services/worker.md#ai-gateway) for outreach generation and [tone checks](/architecture/interfaces.md#tonecheck). Both use `LLM_OUTREACH_MODEL`, the [Budget guard](/architecture/rules.md#budget-guard), recorded fixtures and the shared OpenRouter adapter.
- A tone check is advisory and ephemeral. It reads the current editor text and the saved generation context, writes the call's `AI_CALL` audit row, and neither changes the draft nor stores the review.

## Consequences

- Reopening a draft shows the choices that produced it; changing choices generates a new draft rather than rewriting that fact.
- Replay needs recordings for the revised outreach input and the `TONE_CHECK` role.
- Tone advice can be requested repeatedly without creating a second history beside the editable draft and the audit trail.

## Alternatives considered

- **Call OpenRouter from the browser.** Rejected: it would expose credentials and bypass the budget, fixtures, validation and audit path.
- **Give tone checking its own configurable model.** Rejected: it is an interactive outreach operation and `LLM_OUTREACH_MODEL` already owns that role family.
- **Save tone reports.** Rejected: no requirement needs review history, and a report over unsaved editor text is not a fact of the stored draft.
