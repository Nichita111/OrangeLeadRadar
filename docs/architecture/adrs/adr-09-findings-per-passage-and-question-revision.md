---
type: Decision
title: ADR-09 Findings per passage and question revision
description: Classifications and findings are keyed by passage, question and question revision, and scoring parameters live outside the question, so rescoring never reclassifies.
status: draft
tags: [signal-pipeline, service-configuration, prospect-dashboard]
---

# ADR-09 Findings per passage and question revision

## Context

Admins change questions and weights often. Recomputing everything on every change is slow and costly; recomputing nothing makes changes invisible.

## Decision

A [`classification`](/architecture/sql-store.md#classification) and its [`finding`](/architecture/sql-store.md#finding) belong to one passage, one question and one question revision. Only changes to a question's text, answer type, options or source types create a revision and trigger [Reclassification](/architecture/rules.md#reclassification) of that question alone. Weight and half-life are in the scoring settings, so changing them only rescores. Polarity is fixed at creation.

## Consequences

- A weight change re-ranks in seconds without an AI call.
- A wording change costs one question's worth of classification.
- Findings of older revisions are superseded, not deleted, so history stays explainable.

## Alternatives considered

- **Per-account aggregated signal scores.** Rejected: loses the evidence and forces full recomputation.
- **Weights on the question.** Rejected: would make a weight change indistinguishable from a content change and break versioned scoring.
