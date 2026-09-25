---
type: Decision
title: ADR-15 OpenRouter as the LLM provider
description: Every LLM call goes through OpenRouter's chat completions API, each AI role's model is an OpenRouter model id chosen by configuration, and a call's cost is the cost OpenRouter reports.
status: draft
tags: []
---

# ADR-15 OpenRouter as the LLM provider

## Context

The specification assumed Anthropic's Messages API for every generation role and for the LLM classifier adapter. The team will not use an Anthropic key: it needs cheaper models, and the best price for classification, escalation, evidence and outreach may come from different vendors. Keeping a price list per model by hand is also a fact that drifts.

## Decision

The [OpenRouter adapter](/architecture/services/worker.md#ai-gateway) of the AI gateway serves every LLM call through OpenRouter's OpenAI-compatible chat completions API, with one `OPENROUTER_API_KEY`. `LLM_CLASSIFIER_MODEL`, `LLM_EVIDENCE_MODEL` and `LLM_OUTREACH_MODEL` are OpenRouter model ids of the form `organisation/model`. Structured output is requested as a `json_schema` response format with `provider.require_parameters`, so only providers that honour the schema serve the call. A call's cost is the `usage.cost` OpenRouter returns, converted at `USD_EUR_RATE`, and the [Budget guard](/architecture/rules.md#budget-guard) caps the calls whose audit `provider` is `OPENROUTER`. The Jev classifier adapter is unchanged.

## Consequences

- Changing a role's model, or its vendor, is configuration; no price table is maintained.
- The recorded fixtures are keyed by the request, which includes the model id, so changing a model requires re-recording the affected fixtures ([ADR-11](/architecture/adrs/adr-11-recorded-fixtures.md)).
- A model that does not support structured output cannot be configured for a role; the quality check measures whether a cheaper model keeps the precision the release gate requires.
- Document text is sent to OpenRouter and to the upstream provider it routes to; the data-processing agreements of the [production path](/architecture/overview.md#production-path) include both.

## Alternatives considered

- **Anthropic's Messages API directly.** Rejected: one vendor's prices for every role, and no key will be provisioned.
- **Each vendor's own API.** Rejected: one adapter, key and structured-output dialect per vendor.
