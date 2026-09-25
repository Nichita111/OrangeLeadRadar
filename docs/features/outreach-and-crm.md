---
type: Feature
title: Outreach and CRM
description: How Sales drafts an email or LinkedIn InMail grounded in an account's quoted signals and the service's value proposition, edits and exports it without the product ever sending it, and pushes an account's score and top signals to HubSpot.
status: draft
tags: [outreach-and-crm]
---

# Outreach and CRM

## Purpose

Once a lead is worth contacting, the first message should reference what the company actually said. The Outreach composer drafts an email or InMail from the account's strongest in-force signals and the service's value proposition, cites the signals it uses, and leaves sending to the person: LeadRadar never contacts anyone. When the team works in HubSpot, one action pushes the account with its Priority, band and top signals.

## Flows

### FL-17 Draft outreach

```mermaid
sequenceDiagram
  actor Sales
  participant Web as Outreach composer
  participant API as api
  participant L as Anthropic LLM
  Sales->>Web: choose channel and, optionally, a contact
  Web->>API: generate (API-56)
  API->>API: budget guard; select top signals of the service
  API->>L: draft outreach with signals, value proposition, contact
  L-->>API: subject, body, cited signal ids
  API->>API: validate citations, length, no invented contact data
  API-->>Web: draft stored as DRAFT
  Sales->>Web: edit, then Copy or Download
  Web->>API: update (API-58): status EXPORTED
```

### FL-18 Push to HubSpot

1. Sales opens the [HubSpot push dialog](#hubspot-push-dialog) from [Account detail](/features/prospect-dashboard.md#account-detail).
2. The dialog shows what will be written: domain, name, service, Priority, band, standing, top signals and a link back.
3. Push (`API-59`) finds the company by domain in HubSpot, updates or creates it, and records the outcome; without a configured token the dialog says HubSpot is not connected.

## Reading order

1. Terms in the [glossary](/requirements/glossary.md): Outreach draft, Value proposition, Finding, Contact, Persona, Budget guard.
2. Requirement rows: `S-OUT-01`, `S-OUT-02` in [system requirements](/requirements/system.md); `B-25`, `B-26`, `RULE-06`, `RULE-07` in [business requirements](/requirements/business.md).
3. Stores: [`outreach_draft`](/architecture/sql-store.md#outreach_draft), [`crm_sync`](/architecture/sql-store.md#crm_sync), [`finding`](/architecture/sql-store.md#finding), [`contact`](/architecture/sql-store.md#contact), [`service`](/architecture/sql-store.md#service).
4. Rules: [Outreach grounding](/architecture/rules.md#outreach-grounding), [Budget guard](/architecture/rules.md#budget-guard).
5. Interfaces: [Outreach and CRM](/architecture/interfaces.md#outreach-and-crm) (`API-56` to `API-59`), [LLM](/architecture/interfaces.md#llm) (`API-66`), [CRM](/architecture/interfaces.md#crm) (`API-70`).
6. Services: the [api](/architecture/services/api.md) (`OUTREACH_MAX_FINDINGS`, `OUTREACH_EMAIL_MAX_CHARS`, `OUTREACH_INMAIL_MAX_CHARS`, `HUBSPOT_ACCESS_TOKEN`, `APP_BASE_URL` in its [runtime](/architecture/services/api.md#runtime)); the [AI gateway](/architecture/services/worker.md#ai-gateway).
7. Decisions: [ADR-03](/architecture/adrs/adr-03-models-answer-rules-score.md), [ADR-10](/architecture/adrs/adr-10-minimal-contact-data.md).
8. Screens: [Outreach composer](#outreach-composer), [HubSpot push dialog](#hubspot-push-dialog).
9. Acceptance rows in [acceptance criteria](/requirements/acceptance.md): `AC-50`, `AC-51`.

## Outreach composer

Route `/accounts/:id/outreach`, with the service from the selector. Any signed-in user. It is the Outreach tab of [Account detail](/features/prospect-dashboard.md#account-detail).

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ DHL Group · Intelligent Automation                                           │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ Signals the draft can use     │ Channel (•) Email ( ) LinkedIn InMail        │
│ 1 AI and automation projects  │ To      [ J. Example — CIO ▾ ]  (optional)   │
│   "DHL setzt in über 1.000 …" │                               [ Generate ]   │
│ 2 Cost programme              │ Subject [ Automating the next 1,000 processes ] │
│   "Fit for Growth senkt …"    │ Body    [ Dear J. Example, your announcement …] │
│                               │ Uses signals: 1, 2                           │
│ Earlier drafts                │ Nothing is sent from LeadRadar.              │
│ Email · 2 days ago · exported │          [ Copy ]  [ Download .txt ] [ Save ] │
└───────────────────────────────┴──────────────────────────────────────────────┘
```

WF-19 — Outreach composer

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-086` | The left panel shall list the signals a draft may use, in the order they will be given, and the account's earlier drafts for the service with channel, age and status. |
| `FR-087` | Generate shall take the channel and an optional contact of the account, and show the subject (email only), the body and which signals it cites. |
| `FR-088` | The subject and body shall be editable and saved with Save; the screen shall state that nothing is sent from LeadRadar. |
| `FR-089` | Copy and Download .txt shall export the draft and mark it exported. |
| `FR-090` | When the account has no in-force positive signal for the service, Generate shall be disabled with the reason. |

Obligations: `S-OUT-01`.

**Data**: `API-25`, `API-42`, `API-56`, `API-57`, `API-58`. **States**: [States](/architecture/services/frontend.md#states); `429` and `503` show the unavailable state and keep the edited text.

## HubSpot push dialog

Opened from the Push to HubSpot button of [Account detail](/features/prospect-dashboard.md#account-detail). Any signed-in user. No route of its own.

**Layout**

```text
┌ Push to HubSpot ─────────────────────────────────────────────────────────────┐
│ Company   DHL Group · dhl.com                                                │
│ Service   Intelligent Automation   Priority 78 · Hot · Ranked                │
│ Signals   AI and automation projects — "DHL setzt in über 1.000 …"           │
│ Link      https://leadradar.example/accounts/…                               │
│ Last push: 3 days ago · succeeded                    [ Cancel ]  [ Push ]    │
└──────────────────────────────────────────────────────────────────────────────┘
```

WF-20 — HubSpot push dialog

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-091` | The dialog shall show the values that will be written, the last push of the account for the service with its outcome, and push on confirmation. |
| `FR-092` | A `NOT_CONFIGURED` answer shall show that HubSpot is not connected and that an Admin must set it up; a failure shall show HubSpot's message. |

Obligations: `S-OUT-02`.

**Data**: `API-40`, `API-59`. **States**: [States](/architecture/services/frontend.md#states).

## Open questions

- The HubSpot custom properties `leadradar_*` must exist in the target portal; whether the setup creates them or an Admin does. Missing: access to the portal. Decides: the HubSpot administrator.
