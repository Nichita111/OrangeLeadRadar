---
type: Decision
title: ADR-23 Engagement status synced from HubSpot
description: Each account has an engagement status per service that Sales and Admins set and that a daily sync advances from HubSpot's sales-email reply, meeting and lead-status data, storing nothing about the people; a rejection takes the account out of that service's ranking.
status: draft
tags: [outreach-and-crm, prospect-dashboard]
---

# ADR-23 Engagement status synced from HubSpot

## Context

The product owner asked that sales and admins track whether a company was contacted, answered or rejected, that the status change on its own when the company replies by email, and that the team see statistics. LeadRadar never sends a message ([RULE-06](/requirements/business.md#business-rules)) and stores no email address ([RULE-07](/requirements/business.md#business-rules)), so it cannot see a reply itself. HubSpot, where the team sends and tracks sales emails and books meetings, already records replies and meetings on its contacts.

## Decision

- [`engagement_status`](/architecture/sql-store.md#engagement_status) is an append-only history per account and service, `NOT_CONTACTED`, `CONTACTED`, `ANSWERED`, `MEETING_BOOKED` or `REJECTED`, the latest in force. Sales and Admins set it.
- `REJECTED` gives the account standing `REJECTED` for that service, which keeps it out of the ranking with its reason, as a customer is ([RULE-10](/requirements/business.md#business-rules)); the other statuses do not change a score.
- A daily `ENGAGEMENT_SYNC` run reads, for each contacted company, three standard HubSpot contact properties — `hs_sales_email_last_replied`, `hs_last_booked_meeting_date` and `hs_lead_status` — aggregated over the company's contacts, and advances the status to `ANSWERED`, `MEETING_BOOKED` or `REJECTED` ([Engagement sync](/architecture/rules.md#engagement-sync)). A lead status of `UNQUALIFIED`, HubSpot's default for a lead that will not buy, means rejected; `HUBSPOT_REJECTED_LEAD_STATUSES` holds the list.
- The sync never writes to HubSpot, never overrides a status a person set after HubSpot's event, and stores nothing about a contact.

## Consequences

- Standard properties need no set-up in HubSpot beyond using its sales-email tracking and meetings tool; a team that uses custom lead statuses sets `HUBSPOT_REJECTED_LEAD_STATUSES`.
- A reply to any of a company's contacts advances every service the company was contacted for; the team corrects a wrong one by hand.
- Without `HUBSPOT_ACCESS_TOKEN` no sync runs and the status is manual only.
- The HubSpot adapter now serves the worker too, and HubSpot exchanges are recorded and replayed like every other provider ([ADR-11](/architecture/adrs/adr-11-recorded-fixtures.md)).

## Alternatives considered

- **Reading a shared sales mailbox.** Rejected: a new integration holding personal email content, against [ADR-10](/architecture/adrs/adr-10-minimal-contact-data.md).
- **A custom LeadRadar property per service in HubSpot.** Rejected: it asks the team to maintain a second status by hand in HubSpot, which is what the sync is meant to avoid.
