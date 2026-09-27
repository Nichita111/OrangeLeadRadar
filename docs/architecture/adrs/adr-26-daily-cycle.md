---
type: Decision
title: ADR-26 Daily cycle
description: Every day the scheduler refreshes every account, runs discovery for every active service and syncs engagement from HubSpot; new candidates and replies raise alerts, and Alerts opens with a summary of the day, while suggested companies still wait for a person's acceptance.
status: draft
tags: [accounts-and-discovery, outreach-and-crm, prospect-dashboard, signal-pipeline]
---

# ADR-26 Daily cycle

## Context

The product owner asked that the workspace evolve on its own: once a day the system should look for new signals, new companies and new alerts. Accounts were already refreshed every `REFRESH_INTERVAL_HOURS`, 24 by default, but discovery ran only when a user started it, and nothing told Sales what the day had changed.

## Decision

- [Scheduling](/architecture/rules.md#scheduling) starts a `DISCOVERY` run per active service every `DISCOVERY_INTERVAL_HOURS` and an `ENGAGEMENT_SYNC` run every `ENGAGEMENT_SYNC_INTERVAL_HOURS`, beside the refreshes it already queued.
- [Alerts](/architecture/rules.md#alerts) gains `NEW_CANDIDATES`, one per discovery run that proposes a company, and `REPLY_RECEIVED`, one per reply the sync records.
- The Alerts screen opens with the [Daily summary](/architecture/rules.md#daily-summary) of the service, counted from stored rows.
- Discovered companies still wait for a person's acceptance before anything is fetched or scored for them ([ADR-12](/architecture/adrs/adr-12-suggested-accounts-need-acceptance.md)).

## Consequences

- A scheduled discovery spends its searches and extraction calls every day for every active service, within the plug-in quotas and the budget guard.
- The demo, which replays one recording at a fixed clock, shows the daily cycle only with a second recording made a day later.

## Alternatives considered

- **Adding discovered companies above a fit bar automatically.** Rejected: keeps ADR-12's reason — unvetted companies in the ranking and budget spent on noise.
- **Email or chat delivery of the summary.** Rejected: alerts stay in the product ([business assumptions](/requirements/business.md#assumptions-and-constraints)).
