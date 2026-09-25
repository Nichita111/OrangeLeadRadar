---
type: Decision
title: ADR-10 Minimal contact data
description: Contacts hold only name, job title, public source address and persona; no email or phone; retention and erasure are built in.
status: draft
tags: [accounts-and-discovery, outreach-and-crm]
---

# ADR-10 Minimal contact data

## Context

Decision-makers are personal data under the GDPR. Outreach needs to know who to address, not how to reach them automatically, and the brief allows LinkedIn only for manual validation.

## Decision

A [`contact`](/architecture/sql-store.md#contact) is entered by a user and holds full name, job title, persona and the public page stating them; the schema has no column for an email address or phone number and the api refuses such fields. Contacts are erased on request and after `CONTACT_RETENTION_DAYS`, with an audit row carrying no personal data.

## Consequences

- The legitimate-interest basis is easier to argue; there is less to protect.
- Drafts can address a person by name and title; finding an address stays a human step.

## Alternatives considered

- **Contact enrichment with emails and phones.** Rejected: privacy risk, cost and no need for the MVP.
- **Importing Crunchbase key people as contacts.** Rejected: more personal data held without a person choosing it; key people still reach the pipeline as text of the account's `COMPANY_PROFILE` document.
