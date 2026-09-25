---
type: Decision
title: ADR-14 Labelled set and precision gate
description: Signal accuracy is measured on a labelled set built blind in the product, and a release requires the configured precision.
status: draft
tags: [evaluation-and-feedback]
---

# ADR-14 Labelled set and precision gate

## Context

Signal relevance and accuracy weigh most in judging and matter most to users. Choosing between Jev and the LLM classifier and setting the escalation band need numbers, not impressions.

## Decision

The team labels passage and question pairs in the product without seeing the classifier's answer, drawn across confidence strata; finding feedback adds labels unless a manual one exists. A quality check replays classification and escalation over the active labels and computes the [evaluation metrics](/architecture/rules.md#evaluation-metrics). The release gate requires precision of at least `EVAL_MIN_PRECISION` over at least `EVAL_MIN_ITEMS` labels.

## Consequences

- Quality claims are backed by a reproducible number.
- Labelling about 200 pairs is team work before release.
- A quality check spends classifier and LLM calls, recorded like any other.

## Alternatives considered

- **Judging quality by inspection.** Rejected: not repeatable.
- **Labelling with an LLM.** Rejected: circular.
