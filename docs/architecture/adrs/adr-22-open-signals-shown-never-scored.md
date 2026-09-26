---
type: Decision
title: ADR-22 Open signals shown, never scored
description: The LLM notes buying signals that no configured question asks about, each with a verbatim quote; they are shown and fed to the interpretation but never counted in a score, and an Admin can turn one into a question.
status: draft
tags: [signal-pipeline, service-configuration, prospect-dashboard]
---

# ADR-22 Open signals shown, never scored

## Context

Signal detection answers only the questions an Admin configured. The product owner asked the model also to find signals outside the predefined ones. Counting such signals would let a model decide part of a score and make scores depend on free text no scoring version describes, against [ADR-03](/architecture/adrs/adr-03-models-answer-rules-score.md) and [ADR-06](/architecture/adrs/adr-06-rule-based-scoring-with-versioned-settings.md).

## Decision

- A new AI role, `OPEN_SIGNAL`, asks each kept document, once per service and at most `OPEN_SIGNAL_MAX_DOCUMENTS_PER_REFRESH` per refresh, for the buying signals none of the service's questions asks about ([Open signals](/architecture/rules.md#open-signals)).
- Each is stored as an [`open_signal`](/architecture/sql-store.md#open_signal) only with a quote validated as verbatim, as a finding's is ([RULE-02](/requirements/business.md#business-rules)).
- Open signals are shown on the account and given to its [Interpretation](/architecture/rules.md#interpretation), and never enter a score or a breakdown.
- An Admin promotes a useful one to a question — which then classifies stored passages and scores through the usual path — or dismisses it.

## Consequences

- The configured questions keep deciding every score; open signals widen what Sales reads and what an Admin learns to ask.
- A refresh costs at most `OPEN_SIGNAL_MAX_DOCUMENTS_PER_REFRESH` more LLM calls per service.

## Alternatives considered

- **Scoring open signals at a fixed weight.** Rejected: unversioned, uncalibrated and not reproducible from settings.
