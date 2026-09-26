---
type: Decision
title: ADR-21 Written interpretation after scoring
description: After scoring, the worker has the LLM write for each ranked score why the company is worth approaching and why each counted signal matters, citing only its findings, open signals and provider facts; it explains the score and never sets one.
status: draft
tags: [prospect-dashboard, signal-pipeline]
---

# ADR-21 Written interpretation after scoring

## Context

The Why tab shows every point of a score and an "In short" paragraph composed from the breakdown alone. The product owner asked for more: an interpretation that says why a signal matters for the service and why the company is a good prospect for Orange Systems, the step the [manual process](/reference/annex-1-participant-reference-pack.md) calls interpretation. Only a language model can write that, yet models must never decide a score ([ADR-03](/architecture/adrs/adr-03-models-answer-rules-score.md)).

## Decision

- A new AI role, `INTERPRETATION`, writes one [`score_interpretation`](/architecture/sql-store.md#score_interpretation) per `RANKED` score row, in an `INTERPRET` stage the worker runs after `SCORE` ([Interpretation](/architecture/rules.md#interpretation)).
- Its inputs are the breakdown, the counted findings with their quotes, the account's open signals, the service's value proposition and the provider facts; its output cites only those, gives a reason for every counted positive finding, and states no number its inputs do not carry.
- It is generated in the worker rather than on demand, so it is ready when the list and alerts are read, and it is regenerated only when a new score row is written.
- Nothing reads a score, band, standing or exclusion from it; the deterministic "In short" stays beside it.

## Consequences

- Each changed ranked score costs one LLM call, capped by the [Budget guard](/architecture/rules.md#budget-guard); an interpretation the budget or an outage stops is written by the next refresh or rescore.
- A scoring activation that changes every score of a service causes one call per ranked account of the service.
- The demo recording holds the interpretation calls, so replay shows the same text every time.

## Alternatives considered

- **On demand when the Why tab opens, cached per score.** Rejected: the first reader waits, and nothing is ready for alerts or the drawer.
- **Richer rationales from the evidence call only.** Rejected: a finding's rationale explains one quote; it cannot weigh the account's signals together against the service and Orange Systems' strengths.
