---
type: Decision
title: ADR-06 Rule-based scoring with versioned settings
description: Scores come from explainable weighted rules whose settings are immutable versions activated by an Admin; feedback never changes weights.
status: draft
tags: [evaluation-and-feedback, prospect-dashboard, service-configuration, signal-pipeline]
---

# ADR-06 Rule-based scoring with versioned settings

## Context

There is no history of won and lost deals to learn from, configurability is a judging criterion, and every score must be reproducible. Admins need to tune weights and thresholds without code and see the effect before it applies.

## Decision

Fit, Intent with recency decay and negative signals, disqualifiers, Priority and bands are computed by the [scoring rules](/architecture/rules.md#fit-score) from a [scoring settings document](/architecture/sql-store.md#scoring-settings-document). Settings are edited as one draft per service, validated, previewed and activated as an immutable version; activation rescores from stored findings. Feedback corrects findings and standings but never changes a weight. Weights learned from outcomes (`B-29`) would be proposed as a draft for an Admin to activate.

## Consequences

- Each score names the version that computed it; history shows what a version changed.
- Tuning is immediate and cheap; defaults matter and are stated once.
- A learned model can later be introduced as a draft generator without changing the scoring path.

## Alternatives considered

- **A trained model on outcomes.** Rejected for the MVP: no data.
- **Mutable settings without versions.** Rejected: scores would not be reproducible.
