---
type: Decision
title: ADR-22 Relationship status beside lead feedback
description: A team-wide account.relationship_status, set by a user and read by no rule, sits beside the per-service lead feedback ALREADY_CUSTOMER without replacing it, changes no score or standing, and does not disable drafting outreach.
status: draft
tags: [accounts-and-discovery, prospect-dashboard]
---

# ADR-22 Relationship status beside lead feedback

## Context

The team records where it stands with a company. The lead feedback `ALREADY_CUSTOMER` is per service and takes the account out of that service's ranking.

## Decision

- A team-wide `account.relationship_status`, set by a user, which no rule reads.
- It never sets or clears standing `CUSTOMER`, and it never changes a score.
- `CLIENT` does not imply `ALREADY_CUSTOMER`.
- `DO_NOT_CONTACT` does not disable drafting.

## Consequences

- A user may set both.
- Scores stay reproducible from the inputs of RULE-05.
- A later outreach change may read the status in drafting, but not in scoring.

## Alternatives considered

- **Deriving standing from `CLIENT`.** Rejected: it would change RULE-05's inputs and act on every service at once.
- **Blocking Generate for `DO_NOT_CONTACT`.** Rejected by the product owner.
