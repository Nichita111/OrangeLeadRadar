---
type: Decision
title: ADR-29 Contact suggestions added by a person
description: On request, the LLM names the people an account's stored documents state with a job title, each with a verbatim quote; the suggestions are shown and never stored, and a person adds the ones they choose as ordinary minimal contacts.
status: draft
tags: [accounts-and-discovery, outreach-and-crm]
---

# ADR-29 Contact suggestions added by a person

## Context

[ADR-10](/architecture/adrs/adr-10-minimal-contact-data.md) makes a person type every contact, and rejects importing key people because it holds personal data no person chose. The product owner asked for an account's contacts to be found without typing them. The account's stored documents — press releases, reports, board pages — already name its leaders with their job titles, next to press contacts' email addresses and phone numbers and to people of other companies.

## Decision

- A new AI role, `CONTACT_EXTRACTION`, reads the account's stored passages that [Contact suggestion](/architecture/rules.md#contact-suggestion) selects and names the people they state work at the account, each with a job title and a quote that is checked as verbatim.
- Suggestions are computed on a user's request and never stored; only the `AI_CALL` audit row of the call remains.
- A user adds a suggestion they choose as a [`contact`](/architecture/sql-store.md#contact) through the same contract as a typed one, with its name, job title and the document's address as its source; its persona and retention follow as for any contact.
- A suggestion carries no email address or phone number, even when its passage states one ([RULE-07](/requirements/business.md#business-rules)).

## Consequences

- ADR-10 still holds: no personal data is stored until a person chooses it, and a contact holds the same four fields.
- An account never refreshed, or whose documents name no one, gets no suggestion; finding people beyond the stored documents stays a human step.
- Each request costs one LLM call on `LLM_EVIDENCE_MODEL`, under the [Budget guard](/architecture/rules.md#budget-guard).

## Alternatives considered

- **Storing every person a refresh finds as a contact.** Rejected: personal data held for people no one chose, against ADR-10 and data minimisation.
- **A people-data provider or LinkedIn.** Rejected: cost, terms and the brief's bar on depending on LinkedIn ([ADR-19](/architecture/adrs/adr-19-source-provider-terms-and-limits.md)).
