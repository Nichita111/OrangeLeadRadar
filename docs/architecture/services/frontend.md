---
type: Service
title: Frontend
description: The React web client - stack, routes and roles, navigation and service selector, screen states, screen labels, formatting, polling, tables and accessibility - with the shell-level FR rows every screen obeys and its configuration keys.
status: draft
tags: [service-configuration, accounts-and-discovery, signal-pipeline, prospect-dashboard, evaluation-and-feedback, outreach-and-crm, identity-and-access, audit-trail]
---

# Frontend

## Responsibilities

The frontend is the only user interface: a single-page React app for Sales and Admin users on desktop browsers. It renders what the api returns and composes no score, band, standing or finding of its own; every number it shows comes from a contract. It is built for users without AI expertise: it speaks in the [screen labels](#screen-labels), never in model terms.

It never calls a provider, never stores data outside the browser session except the conveniences [Navigation](#navigation) names, and never holds a secret.

## Owns

No table and no rule. It owns the routes, the shell and the screens of the [features](/features/index.md).

## Provides and consumes

Consumes every REST family of [interfaces](/architecture/interfaces.md) through a client generated from the api's OpenAPI document. Provides the routes below.

## Design

React with TypeScript in strict mode, built by Vite; React Router for routes; TanStack Query for server state, caching and polling; a typed client generated with `openapi-typescript`; Tailwind CSS with Radix-based components for accessible primitives. The build is static files served by the `web` container, which proxies `/api/v1` to `API_UPSTREAM`.

## Routes

| Route | Screen | Roles | Feature |
|---|---|---|---|
| `/login` | [Sign in](/features/identity-and-access.md#sign-in) | anonymous | identity-and-access |
| `/prospects` | [Prospects](/features/prospect-dashboard.md#prospects) | any | prospect-dashboard |
| `/accounts/:id` | [Account detail](/features/prospect-dashboard.md#account-detail) | any | prospect-dashboard |
| `/alerts` | [Alerts](/features/prospect-dashboard.md#alerts) | any | prospect-dashboard |
| `/accounts` | [Accounts](/features/accounts-and-discovery.md#accounts) | any | accounts-and-discovery |
| `/accounts/:id/profile` | [Account profile](/features/accounts-and-discovery.md#account-profile) | any | accounts-and-discovery |
| `/accounts/import` | [Account import](/features/accounts-and-discovery.md#account-import) | any | accounts-and-discovery |
| `/suggested-accounts` | [Suggested accounts](/features/accounts-and-discovery.md#suggested-accounts) | any | accounts-and-discovery |
| `/runs` | [Runs](/features/signal-pipeline.md#runs) | any | signal-pipeline |
| `/labelling` | [Labelling](/features/evaluation-and-feedback.md#labelling) | any | evaluation-and-feedback |
| `/accounts/:id/outreach` | [Outreach composer](/features/outreach-and-crm.md#outreach-composer) | any | outreach-and-crm |
| `/services` | [Services](/features/service-configuration.md#services) | Admin | service-configuration |
| `/services/:id` | [Service editor](/features/service-configuration.md#service-editor) | Admin | service-configuration |
| `/services/:id/scoring` | [Scoring settings](/features/service-configuration.md#scoring-settings) | Admin | service-configuration |
| `/quality` | [Quality report](/features/evaluation-and-feedback.md#quality-report) | Admin | evaluation-and-feedback |
| `/settings/source-plugins` | [Source plug-ins](/features/signal-pipeline.md#source-plug-ins) | Admin | signal-pipeline |
| `/users` | [Users](/features/identity-and-access.md#users) | Admin | identity-and-access |
| `/audit` | [Audit log](/features/audit-trail.md#audit-log) | Admin | audit-trail |

`/` redirects to `/prospects`.

## Navigation

```text
┌───────────────┬──────────────────────────────────────────────────────────────┐
│ LeadRadar     │  Service: [ Intelligent Automation ▾ ]         Ana Sales ▾  │
│               ├──────────────────────────────────────────────────────────────┤
│ Prospects     │                                                              │
│ Alerts    (3) │                     screen content                           │
│ Accounts      │                                                              │
│ Suggested     │                                                              │
│ Runs          │                                                              │
│ Labelling     │                                                              │
│ ─ Admin ─     │                                                              │
│ Services      │                                                              │
│ Quality       │                                                              │
│ Source plug-ins│                                                             │
│ Users         │                                                              │
│ Audit log     │                                                              │
└───────────────┴──────────────────────────────────────────────────────────────┘
```

WF-01 — application shell

| ID | Requirement |
|---|---|
| `FR-001` | The shell shall show a left navigation with Prospects, Alerts, Accounts, Suggested accounts, Runs and Labelling for every user, and an Admin section with Services, Quality, Source plug-ins, Users and Audit log shown only to Admins. |
| `FR-002` | The Alerts entry shall show the number of unread alerts of the selected service when it is greater than zero. |
| `FR-003` | The header shall carry a service selector listing the active services; the selected service applies to Prospects, Alerts, Suggested accounts and Account detail, and is remembered in the browser's local storage per user, falling back to the first active service. |
| `FR-004` | The user menu shall show the user's display name and role and offer Sign out. |

## States

| ID | Requirement |
|---|---|
| `FR-005` | Every data view shall render four states: loading (skeleton rows, no spinner longer than the content), empty (a sentence saying what would appear and the action that creates it), error (the error's message and a Retry button), and unavailable (for `503` and `429`: which dependency is unavailable and what still works, per [Degradation](/architecture/overview.md#degradation)). |
| `FR-006` | A `401` from any call shall send the user to Sign in with the current route as return path; a `403` shall show a "Not allowed" page naming the role required. |
| `FR-007` | A form shall keep the user's input when a save fails and show each `VALIDATION` field error next to its field. |

## Screen labels

The words the screens show for glossary terms. A label is a presentation of the term, never a second name for the concept.

| Term | Label |
|---|---|
| Finding | Signal |
| Fit score, Intent score, Priority score | Fit, Intent, Priority |
| Band `HOT`, `WARM`, `COLD` | Hot, Warm, Cold |
| Standing `RANKED`, `BELOW_FIT`, `DISQUALIFIED`, `CUSTOMER` | Ranked, Below fit, Excluded, Customer |
| Disqualifier | Exclusion rule |
| Disqualifier override | Exception |
| Discovery candidate | Suggested account |
| Evaluation item | Label |
| Evaluation run | Quality check |
| Strength `WEAK`, `MEDIUM`, `STRONG` | Weak, Clear, Strong |
| `decided_by` `CLASSIFIER`, `LLM` | Quick check, Detailed check |
| Scoring settings | Scoring |

| ID | Requirement |
|---|---|
| `FR-008` | Screens shall use the labels above and shall never show internal names such as `p_positive`, escalation, triage or token counts, except on the Admin screens Quality report, Runs details and Audit log. |
| `FR-009` | A confidence shall be shown as a word: High at 0.85 or above, Medium at 0.65 or above, Low below; the number is shown only in a tooltip. |

## Formatting

| ID | Requirement |
|---|---|
| `FR-010` | Dates shall be shown relative ("3 days ago") with the absolute date and time in the user's time zone in a tooltip; exports use ISO-8601. |
| `FR-011` | Country codes shall be shown with the country's English name; enum values with their label or a title-cased form of the value. |

## Polling

| ID | Requirement |
|---|---|
| `FR-012` | A screen showing a run in `QUEUED` or `RUNNING` shall poll `API-35` every `RUN_POLL_INTERVAL_MS` and stop when the run is final ([ADR-13](/architecture/adrs/adr-13-run-progress-by-polling.md)). |
| `FR-013` | The unread-alert count shall be refreshed every `ALERT_POLL_INTERVAL_MS` and when the window regains focus. |

## Tables and filters

| ID | Requirement |
|---|---|
| `FR-014` | A list shall page with `PAGE_SIZE_DEFAULT` rows, and its filters, sort and page shall be kept in the URL query so a view can be shared by link. |

## Confirmation

| ID | Requirement |
|---|---|
| `FR-015` | Erasing a contact, disabling a user, revoking an exception, activating scoring and deactivating a service or question shall ask for confirmation in a dialog that says what will happen; every other change applies on Save and confirms with a short toast. |

## Accessibility

| ID | Requirement |
|---|---|
| `FR-016` | Every action shall be reachable and operable by keyboard with a visible focus ring; text and controls shall meet WCAG 2.2 AA contrast; band and standing shall never be conveyed by colour alone ([N-10](/requirements/system.md)). |
| `FR-017` | Screens shall be laid out for widths of 1280 px and above and stay usable without horizontal page scroll down to 1024 px. |

## Runtime

| Key | Default | Meaning |
|---|---|---|
| `API_UPSTREAM` | `http://api:8000` | Where the `web` container proxies `/api/v1` |
| `RUN_POLL_INTERVAL_MS` | `2000` | Poll interval of a live run |
| `ALERT_POLL_INTERVAL_MS` | `60000` | Poll interval of the unread-alert count |
