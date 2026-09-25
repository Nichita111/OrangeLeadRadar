---
type: Decision
title: ADR-02 Classification cascade
description: Every relevant passage is classified by a fast classifier behind one port, with Jev and LLM adapters, and only uncertain answers and confirmed positives reach the LLM.
status: draft
tags: [signal-pipeline, evaluation-and-feedback, service-configuration]
---

# ADR-02 Classification cascade

## Context

Most of the pipeline's work is classification over many passages: is this document about the account, is it relevant to a service, does this passage answer this question and how strongly. Asking an LLM for every pair is slow and costly. Jev, released by TypeSafe AI in limited early access on 15 September 2026, is a classification model that returns probabilities over answer values defined per request, with a reported latency of 70–500 ms and a cost far below a frontier LLM. It produces no text, so it cannot quote evidence, and its language coverage and API details are not yet public.

## Decision

A [Classifier](/architecture/interfaces.md#classifier) port with two adapters selected by `CLASSIFIER_PROVIDER`: Jev, and an LLM adapter that asks `LLM_CLASSIFIER_MODEL` for the same probabilities through structured output. Triage and signal classification go through the port for every relevant passage. [Escalation](/architecture/rules.md#escalation) sends answers whose `p_positive` falls between `ESCALATION_LOWER` and `ESCALATION_UPPER` to the LLM, whose verdict is final; confident positives go to the LLM only for [Evidence extraction](/architecture/rules.md#evidence-extraction). The LLM adapter is the default until a key is provisioned and a quality check shows Jev passes the release gate.

## Consequences

- Cost and latency scale with the classifier; LLM use is bounded by the escalation rate and the number of positives.
- The escalation band is tuned with the [labelled set](/architecture/adrs/adr-14-labelled-set-and-precision-gate.md); the quality report compares the classifier alone with the full cascade.
- The dependency on an early-access vendor is contained behind the port; switching is configuration.

## Alternatives considered

- **An LLM for every pair.** Rejected for cost and latency at thousands of pairs per refresh.
- **Keyword rules.** Rejected: poor precision across languages and phrasings.
- **Embeddings with a trained classifier per question.** Rejected: needs labels for every question and defeats configurable questions.
- **Zero-shot NLI models.** Rejected: weaker on multilingual business text and no calibrated multi-question pass.
