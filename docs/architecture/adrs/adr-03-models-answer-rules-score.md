---
type: Decision
title: ADR-03 Models answer, rules score
description: Classifier and LLM output is limited to answers, quotes and text; deterministic rules compute every score, band, standing and exclusion.
status: draft
tags: [service-configuration, accounts-and-discovery, signal-pipeline, prospect-dashboard, evaluation-and-feedback, outreach-and-crm, identity-and-access, audit-trail]
---

# ADR-03 Models answer, rules score

## Context

Sales managers must be able to trust, check and challenge a ranking, the judges weigh signal accuracy and explainability, and scores must be reproducible after the fact. An LLM asked to rate an account directly gives an answer that cannot be decomposed, drifts with prompts and models, and cannot be recomputed.

## Decision

Models only answer fixed questions over passages, extract verbatim quotes, translate them, write one-sentence rationales, name companies in news, and draft outreach. [Rules](/architecture/rules.md) alone compute Fit, Intent, Priority, standing, band and disqualification from stored findings and versioned settings. No model output is read as a score. The allowed outputs per role are in [AI roles and boundaries](/architecture/overview.md#ai-roles-and-boundaries).

## Consequences

- Every point of a score is attributed to an ICP criterion or a quoted finding.
- A model change moves findings, never the formula; its effect is measured by the quality check.
- The explanation shown to users is composed from the stored breakdown, not generated.

## Alternatives considered

- **Holistic LLM scoring of each account.** Rejected: not reproducible, not decomposable, not testable.
- **A learned model over findings.** Deferred: no outcome labels yet ([ADR-06](/architecture/adrs/adr-06-rule-based-scoring-with-versioned-settings.md)).
