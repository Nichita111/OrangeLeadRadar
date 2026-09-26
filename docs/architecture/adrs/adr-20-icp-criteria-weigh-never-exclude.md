---
type: Decision
title: ADR-20 ICP criteria weigh, never exclude
description: An ICP criterion only lowers Fit; the ICP_MISMATCH disqualifier, the minimum fit and the Below fit standing are removed, so an account outside the profile ranks lower and stays in the ranking.
status: draft
tags: [accounts-and-discovery, prospect-dashboard, service-configuration]
---

# ADR-20 ICP criteria weigh, never exclude

## Context

Three mechanisms let the ideal customer profile take an account out of the ranking: a disqualifier of kind `ICP_MISMATCH`, which excluded an account whose attribute did not match a criterion; the `min_fit` setting, below which an account had standing `BELOW_FIT`; and discovery, which dropped a company that such a disqualifier would exclude. The product owner asked that the ICP act as a score and not as a filter: a company in another region should rank lower, not leave the list, because a strong buying signal can outweigh a region or a size that the profile did not foresee ([RULE-11](/requirements/business.md#business-rules)).

## Decision

- An ICP criterion contributes to [Fit score](/architecture/rules.md#fit-score) only. The `ICP_MISMATCH` disqualifier kind, the `min_fit` key and the `BELOW_FIT` standing are removed; a disqualifier is always an in-force finding of a question at or above a strength ([scoring settings document](/architecture/sql-store.md#scoring-settings-document)).
- The standing is `CUSTOMER`, `REJECTED`, `DISQUALIFIED` or `RANKED` ([Priority, standing and band](/architecture/rules.md#priority-standing-and-band)); every other account is ranked by Priority, however low its Fit.
- [Discovery](/architecture/rules.md#discovery) keeps a company that misses a criterion, with a lower fit estimate.

## Consequences

- An account outside the target region or industry is visible in the ranking, below the accounts that match, with the missed criterion shown in its breakdown.
- A service that truly cannot sell to a group of companies expresses it through the weight of a criterion; exclusion is kept for facts a document states, such as insolvency.
- A draft carrying `min_fit` or a criterion-based disqualifier is refused by [Scoring settings validation](/architecture/rules.md#scoring-settings-validation).

## Alternatives considered

- **Keeping `min_fit` but dropping `ICP_MISMATCH`.** Rejected: a very poor fit would still vanish from the default view, which is the filtering the owner asked to remove.
- **Keeping the mechanisms and changing only the demo configuration.** Rejected: an Admin could reintroduce the filter the owner rejected.
