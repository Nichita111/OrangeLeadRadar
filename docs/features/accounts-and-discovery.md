---
type: Feature
title: Accounts and discovery
description: How Sales builds the target account list - CSV import with a dry run, manual entry, profile attributes, aliases, source addresses and minimal contacts - and how discovery suggests new accounts for a service that a person accepts or rejects.
status: draft
tags: [accounts-and-discovery]
---

# Accounts and discovery

## Purpose

An account is a company worth watching, identified by its web domain and shared by the whole team. Sales brings in the target list from a CSV export, such as one from LinkedIn Sales Navigator, or adds accounts one by one, and keeps their profile, the names they are reported under and the addresses where they publish. Decision-makers are recorded with the minimum personal data. Discovery widens the list: for a service it proposes companies that fit the ICP or appear in relevant news, and nothing happens to a suggestion until a person accepts it.

## Flows

### FL-04 Import accounts from a CSV file

```mermaid
sequenceDiagram
  actor Sales
  participant Web as Account import
  participant API as api
  participant DB as database
  participant S as worker scheduler
  Sales->>Web: choose CSV file
  Web->>API: import, dry_run = true (API-22)
  API-->>Web: per-row outcome: created, updated, possible duplicate, invalid
  Sales->>Web: Import
  Web->>API: import, dry_run = false (API-22)
  API->>DB: accounts, aliases, sources; audit ACCOUNTS_IMPORTED
  S->>DB: next tick enqueues a refresh for each new account, due while next_refresh_at is null
```

### FL-05 Maintain an account and its contacts

1. Sales adds an account on [Accounts](#accounts) with its domain and name (`API-21`), or opens an existing one's [Account profile](#account-profile).
2. Sales edits attributes, aliases, source addresses, parent and status (`API-24`). A changed attribute is stored as a manual value, which no source overwrites, and the account is rescored.
3. Sales adds a contact with name, job title and the public page that states them (`API-26`); the persona is suggested from the job title and can be changed.
4. On request, Sales erases a contact (`API-28`); it is deleted and the audit keeps no personal data.

### FL-06 Discover and accept suggested accounts

```mermaid
sequenceDiagram
  actor Sales
  participant Web as Suggested accounts
  participant API as api
  participant W as worker
  participant P as Crunchbase and news plug-ins
  Sales->>Web: Find new accounts (selected service)
  Web->>API: discovery run (API-29)
  W->>P: organisation search with the ICP; news search with hint terms
  W->>W: triage news, extract named companies, drop known ones, estimate fit
  W-->>API: candidates stored PENDING
  Web->>API: list candidates (API-30)
  Sales->>Web: Accept (domain if missing) or Reject (reason)
  Web->>API: accept (API-31) or reject (API-32)
  API-->>Web: new account; its refresh is queued
```

## Reading order

1. Terms in the [glossary](/requirements/glossary.md): Account, Account alias, Account source, Contact, Persona, Discovery candidate, Fit score, Free core.
2. Requirement rows: `S-ACC-01` to `S-ACC-05`, `S-DSC-01`, `S-DSC-02`, `S-ING-06` in [system requirements](/requirements/system.md); `B-07` to `B-10`, `B-37`, `RULE-01`, `RULE-07` in [business requirements](/requirements/business.md); `N-08`.
3. Stores: [`account`](/architecture/sql-store.md#account), [`account_alias`](/architecture/sql-store.md#account_alias), [`account_source`](/architecture/sql-store.md#account_source), [`contact`](/architecture/sql-store.md#contact), [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate).
4. Rules: [Account identity](/architecture/rules.md#account-identity), [Account attributes](/architecture/rules.md#account-attributes), [Persona mapping](/architecture/rules.md#persona-mapping), [Discovery](/architecture/rules.md#discovery), [Fit score](/architecture/rules.md#fit-score), [Retention and erasure](/architecture/rules.md#retention-and-erasure).
5. Interfaces: [Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts) (`API-20` to `API-28`, [`AccountImportRow`](/architecture/interfaces.md#accountimportrow)) and [Discovery](/architecture/interfaces.md#discovery) (`API-29` to `API-32`).
6. Services: the [api](/architecture/services/api.md) and its [runtime](/architecture/services/api.md#runtime) (`IMPORT_MAX_ROWS`, `CONTACT_RETENTION_DAYS`); the [worker](/architecture/services/worker.md) for discovery; the [frontend](/architecture/services/frontend.md) shell; the accounts of the [demo dataset](/architecture/overview.md#demo-dataset) and the account columns of [store ownership](/architecture/overview.md#store-ownership).
7. Decisions: [ADR-10](/architecture/adrs/adr-10-minimal-contact-data.md), [ADR-12](/architecture/adrs/adr-12-suggested-accounts-need-acceptance.md), [ADR-07](/architecture/adrs/adr-07-source-plug-ins-with-a-free-core.md).
8. Screens: [Accounts](#accounts), [Account import](#account-import), [Account profile](#account-profile), [Suggested accounts](#suggested-accounts).
9. Acceptance rows in [acceptance criteria](/requirements/acceptance.md): `AC-09` to `AC-15`, `AC-59`, `AC-63`, `AC-69`.

## Accounts

Route `/accounts`. Any signed-in user.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Accounts   [ search name, alias, domain ]  Country ▾  Industry ▾  Status ▾   │
│                                              [ Import CSV ]  [ New account ] │
├───────────────────┬────────────────────┬─────────┬──────────────┬────────────┤
│ Name              │ Domain             │ Country │ Industry     │ Refreshed  │
├───────────────────┼────────────────────┼─────────┼──────────────┼────────────┤
│ DHL Group         │ dhl.com            │ Germany │ Logistics    │ 2 hours ago│
│ Lufthansa Group   │ lufthansagroup.com │ Germany │ Aviation     │ refreshing…│
│ SWISS             │ swiss.com          │ Switzerland │ Aviation │ yesterday  │
└───────────────────┴────────────────────┴─────────┴──────────────┴────────────┘
```

WF-06 — Accounts

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-038` | The screen shall list accounts with name, domain, country, industry, origin, status and last refresh, marking an account whose refresh is running, and search name, alias or domain. |
| `FR-039` | New account shall open a dialog with domain or URL and name, required, and the optional profile fields; a domain already used shall show the existing account with a link to it. |
| `FR-040` | A row shall open the account's [Account detail](/features/prospect-dashboard.md#account-detail) for the selected service. |
| `FR-137` | The name cell shall show the parent account as Part of its name, an inactive account with an Inactive chip and an account whose refresh is running with a Refreshing chip. |
| `FR-138` | In the New account dialog the domain field shall show, under the field, that the domain is already an account, naming it, and the confirming button shall then read Open existing account. |

Obligations: `S-ACC-01`, `S-ACC-05`.

**Data**: `API-20`, `API-21`. **States**: [States](/architecture/services/frontend.md#states); the empty state offers Import CSV and New account.

## Account import

Route `/accounts/import`. Any signed-in user.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Import accounts          [ Choose CSV file ]   Template: download header row │
├──────────────────────────────────────────────────────────────────────────────┤
│ 24 rows · 19 new · 2 updated · 1 possible duplicate · 2 invalid              │
│ Line  Domain              Outcome              Details                       │
│ 3     lufthansagroup.com  Update               fills employee_count          │
│ 7     dhl.de              Possible duplicate   name matches DHL Group        │
│ 11    —                   Invalid              domain is required            │
│                                          [ Cancel ]  [ Import 21 accounts ]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

WF-07 — Account import

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-041` | Choosing a file shall run a dry run and show the counts and every row's line, domain, outcome and errors; nothing is written until Import is pressed. |
| `FR-042` | The screen shall offer the header row of [`AccountImportRow`](/architecture/interfaces.md#accountimportrow) as a downloadable template. |
| `FR-043` | Import shall write the valid rows, show the result counts, and link to [Accounts](#accounts) filtered to the imported rows' origin. |
| `FR-139` | Account import shall show its progress as three parts, Choose file, Review the check and Import, and after Import a callout shall state how many accounts were imported and that a refresh is queued for each new one. |
| `FR-140` | The check shall show the number of new, updated, possible duplicate and invalid rows each with its meaning, then only the rows that need attention, each with an outcome chip and a sentence saying what will happen to it. |

Obligations: `S-ACC-02`.

**Data**: `API-22`. **States**: [States](/architecture/services/frontend.md#states).

## Account profile

Route `/accounts/:id/profile`. Any signed-in user. It is the Profile tab of [Account detail](/features/prospect-dashboard.md#account-detail).

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ DHL Group · dhl.com        [Why] [Signals] [History] [Profile] [Outreach]    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Country   [ Germany ▾ ]   manual         Industry [ Logistics ▾ ]  Crunchbase │
│ Employees [ 594 000 ]     manual         Revenue  [ 81 000 000 000 ] manual  │
│ Complexity[ High ▾ ]      suggested      Parent   [ none ▾ ]                 │
│ Names     DHL Group · Deutsche Post DHL · DHL  [ + ]                          │
│ Sources   Website    https://dhl.com/                       manual           │
│           Newsroom   https://group.dhl.com/en/media-relations detected  [off]│
│           Careers    https://careers.dhl.com/               detected         │
│ LinkedIn  [ https://www.linkedin.com/company/… ]  opened by you, never read  │
│ Status    (•) Active ( ) Inactive                                  [ Save ]  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Contacts                                                     [ Add contact ] │
│ Name           Job title                    Persona          Source          │
│ J. Example     Chief Information Officer    CIO (suggested)  group.dhl.com/… │
└──────────────────────────────────────────────────────────────────────────────┘
```

WF-08 — Account profile

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-044` | Each attribute shall show where its value came from — manual, Crunchbase or suggested — and say that a value entered here is never overwritten. |
| `FR-045` | Names shall edit the aliases; Sources shall add, remove or switch off addresses by kind, showing detected ones with their origin. |
| `FR-046` | The LinkedIn field shall open the page in a new tab and state that LeadRadar never reads LinkedIn. |
| `FR-047` | Save shall say that the account's scores will be recomputed when an attribute changed. |
| `FR-048` | Contacts shall list name, job title, persona with its origin, and the source page; Add and Edit shall take name, job title, source page (required) and an optional persona, and offer no field for email address or phone number. |
| `FR-049` | Erase shall confirm that the contact is deleted permanently and that drafts addressed to them keep no name. |

Obligations: `S-ACC-03`, `S-ACC-04`, `S-ING-06`.

**Data**: `API-23`, `API-24`, `API-25`, `API-26`, `API-27`, `API-28`. **States**: [States](/architecture/services/frontend.md#states).

## Suggested accounts

Route `/suggested-accounts`. Any signed-in user; lists the selected service's candidates.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Suggested accounts · Intelligent Automation   Pending ▾   [ Find new accounts ] │
│ Finding… news searched 3/3 · 42 articles · 6 companies                        │
├──────────────────────┬─────────┬────────────┬──────┬───────────────────────────┤
│ Company              │ Country │ Industry   │ Fit  │ Why suggested             │
├──────────────────────┼─────────┼────────────┼──────┼───────────────────────────┤
│ Example Logistik AG  │ Germany │ Logistics  │ 88   │ News: "…launches an RPA…" │
│                      │         │            │      │  [ Accept ]  [ Reject ]   │
└──────────────────────┴─────────┴────────────┴──────┴───────────────────────────┘
```

WF-09 — Suggested accounts

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-050` | Find new accounts shall start a discovery run for the selected service and show its progress until it finishes; while one runs the button shows it instead of starting another. |
| `FR-051` | The list shall show pending candidates by default, ordered by fit estimate, with country, industry, employees when known, and why each was suggested: the Crunchbase match or the news quote with a link to the article. |
| `FR-052` | Accept shall ask for the website domain when the candidate has none, then open the new account; a domain that is already an account shall link to it instead. |
| `FR-053` | Reject shall take an optional reason and remove the candidate from the pending list for good. |
| `FR-141` | While a discovery run is active a callout shall show the news searched, the articles read and the companies found so far; the fit estimate of a candidate shall be shown as a score, and when no candidate is pending the empty state shall say how to find new ones. |
| `FR-142` | Accepting a candidate shall mark it in place as Accepted with its refresh queued, and a candidate without a website shall say that the domain will be asked for. |

Obligations: `S-DSC-01`, `S-DSC-02`.

**Data**: `API-29`, `API-30`, `API-31`, `API-32`, `API-35`. **States**: [States](/architecture/services/frontend.md#states); without Crunchbase the screen states that suggestions come from news only.

## Open questions

- Whether the import should also accept the native column names of a LinkedIn Sales Navigator account export, mapped onto [`AccountImportRow`](/architecture/interfaces.md#accountimportrow), instead of requiring the template header. Missing: a sample export. Decides: the sales manager who owns the target list.
