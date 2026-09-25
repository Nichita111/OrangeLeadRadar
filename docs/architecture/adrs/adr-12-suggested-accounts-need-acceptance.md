---
type: Decision
title: ADR-12 Suggested accounts need acceptance
description: Discovery stores candidates apart from accounts; nothing is fetched or scored for a candidate until a person accepts it with a domain.
status: draft
tags: [accounts-and-discovery]
---

# ADR-12 Suggested accounts need acceptance

## Context

Discovery from news and searches is noisy; a false positive in the ranking costs a sales manager's time and the product's credibility, and refreshing every candidate costs fetches and AI calls.

## Decision

[`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) rows are separate from accounts. A person accepts one, supplying a domain when missing, which creates the account and queues its refresh, or rejects it, which keeps the company from being proposed again for the service.

## Consequences

- The ranking contains only accounts someone chose.
- Discovery stays cheap: triage and one extraction call per relevant news item.

## Alternatives considered

- **Adding discovered companies automatically.** Rejected: pollutes the ranking and spends budget on noise.
