---
type: Service
title: Frontend
description: The React web client - stack, routes and roles, navigation and page anatomy, visual language, score presentation, screen states, messages and dialogs, motion, screen labels, formatting, polling, tables and accessibility - with the shell-level FR rows every screen obeys and its configuration keys.
status: draft
tags: [accounts-and-discovery, audit-trail, evaluation-and-feedback, identity-and-access, outreach-and-crm, prospect-dashboard, service-configuration, signal-pipeline]
---

# Frontend

## Responsibilities

The frontend is the only user interface: a single-page React app for Sales and Admin users on desktop browsers. It renders what the api returns and composes no score, band, standing or finding of its own; every number it shows comes from a contract. It is built for users without AI expertise: it speaks in the [screen labels](#screen-labels), never in model terms, and it makes every change of state visible, on the screen and in words.

It never calls a provider, never stores data outside the browser session except the conveniences [Navigation](#navigation) names, never loads a font, script or image from a third party, and never holds a secret.

## Owns

No table and no rule. It owns the routes, the shell and the screens of the [features](/features/index.md), and the design values of [Visual language](#visual-language) and [Motion](#motion).

## Provides and consumes

Consumes every REST family of [interfaces](/architecture/interfaces.md) through a client generated from the api's OpenAPI document. Provides the routes below.

## Design

React with TypeScript in strict mode, built by Vite; React Router for routes; TanStack Query for server state, caching and polling; a typed client generated with `openapi-typescript`; Tailwind CSS with Radix-based components for accessible primitives. Icons come from one family, Phosphor (`@phosphor-icons/react`), at one stroke weight. Type is Geist and Geist Mono, self-hosted by the `web` container. Animation uses `motion`, and the animated components of [Motion](#motion) are copied from React Bits ([ADR-17](/architecture/adrs/adr-17-animated-components-from-react-bits.md)). The build is static files served by the `web` container, which proxies `/api/v1` to `API_UPSTREAM`. The other keys of [Runtime](#runtime) reach the client at run time: the `web` container writes them to `/config.json` when it starts, and the client reads that file before its first render, so changing one needs a restart, not a rebuild.

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
| `/settings/industries-markets` | [Industries and markets](/features/service-configuration.md#industries-and-markets) | Admin | service-configuration |
| `/quality` | [Quality report](/features/evaluation-and-feedback.md#quality-report) | Admin | evaluation-and-feedback |
| `/settings/source-plugins` | [Source plug-ins](/features/signal-pipeline.md#source-plug-ins) | Admin | signal-pipeline |
| `/users` | [Users](/features/identity-and-access.md#users) | Admin | identity-and-access |
| `/audit` | [Audit log](/features/audit-trail.md#audit-log) | Admin | audit-trail |

`/` redirects to `/prospects`.

## Navigation

```text
┌───────────────┬──────────────────────────────────────────────────────────────┐
│ LeadRadar     │  Prospects                Service: [ Intelligent Automation ▾ ] │
│               ├──────────────────────────────────────────────────────────────┤
│ Work          │                                                              │
│ Prospects     │                                                              │
│ Alerts    (3) │                     screen content                           │
│ Accounts      │                                                              │
│ Suggested     │                                                              │
│ Runs          │                                                              │
│ Labelling     │                                                              │
│ Admin only    │                                                              │
│ Services      │                                                              │
│ Industries    │                                                              │
│ Quality       │                                                              │
│ Source plug-ins│                                                             │
│ Users         │                                                              │
│ Audit log     │                                                              │
│ ┌───────────┐ │                                                              │
│ │ Ana Sales │ │                                                              │
│ │ Sales   ⎋ │ │                                                              │
│ └───────────┘ │                                                              │
└───────────────┴──────────────────────────────────────────────────────────────┘
```

WF-01 — application shell

| ID | Requirement |
|---|---|
| `FR-001` | The shell shall show a left navigation with Prospects, Alerts, Accounts, Suggested accounts, Runs and Labelling for every user, and an Admin section with Services, Industries and markets, Quality, Source plug-ins, Users and Audit log shown only to Admins. |
| `FR-002` | The Alerts entry shall show the number of unread alerts of the selected service when it is greater than zero. |
| `FR-003` | The header shall carry a service selector listing the active services; the selected service applies to Prospects, Alerts, Suggested accounts and Account detail, and is remembered in the browser's local storage per user, falling back to the first active service. |
| `FR-004` | The user card at the foot of the navigation shall show the user's display name and role and offer Sign out. |
| `FR-101` | The navigation shall group its entries under the headings Work and Admin only, every entry carrying an icon and its label; the entry of the current screen shall be marked with a tint and the accessible current-page state, never by colour alone. |
| `FR-102` | The header shall show the current screen as a breadcrumb, with the parent screen as a link on a nested screen such as Account detail, and every Admin screen shall carry an Admin only chip. |

## Page anatomy

Every screen is built from the same parts in the same order, so a user who has learnt one screen has learnt the shell.

| ID | Requirement |
|---|---|
| `FR-103` | A screen shall start with a page header: its title, and one sentence saying what the screen is for and what a user does on it, in the [screen labels](#screen-labels). |
| `FR-104` | The primary action of a screen shall be one filled button at the right of the page header; every other action on the screen is a secondary or ghost button, and a screen has at most one primary button outside a dialog. |
| `FR-105` | Below the page header a screen shall place its filters and view controls in one toolbar, then its content, then no footer chrome; a legend explaining the marks used on the screen sits directly under the content it explains. |

## Visual language

The values below are literal design values. The client defines each as a token, a CSS variable with a light and a dark value, and no screen names a colour, size or radius directly.

| Token | Light | Dark | Use |
|---|---|---|---|
| Page | `#F4F4F5` | `#0E0E10` | Screen background |
| Surface | `#FFFFFF` | `#17171A` | Cards, dialogs, navigation |
| Border | `#E4E4E7` | `#2A2A30` | Card edges and dividers |
| Text | `#18181B` | `#ECECEE` | Body and headings |
| Text secondary | `#52525B` | `#A1A1AA` | Lead sentences and descriptions |
| Text tertiary | `#6B6B74` | `#8A8A93` | Hints, ages and column headings |
| Accent | `#C2410C` | `#F0803F` | The one brand colour: primary buttons, Hot, current page |
| On accent | `#FFFFFF` | `#1A0B03` | Text on the accent |
| Accent soft, ink | `#FFF1E7`, `#9A3412` | `#2A1B12`, `#FDBA8C` | Warm chips, the current navigation entry, key callouts |
| Positive, soft | `#14703A`, `#E8F5EC` | `#4ADE80`, `#12261A` | Adds to Intent, success, matched |
| Negative, soft | `#B42318`, `#FCEBE9` | `#F87171`, `#2C1416` | Takes from Intent, errors |
| Caution, soft | `#946200`, `#FBF3DC` | `#FACC15`, `#2A2410` | Partial results, unknown, warnings |
| Cool, soft | `#475569`, `#EEF1F5` | `#A8B5C7`, `#1D232C` | Cold |
| Highlight | `#FDF0B8` | `#4A3F12` | The quote inside a passage |

| Element | Design value |
|---|---|
| Body type | Geist 14 px, line height 1.5 |
| Page title | Geist 24 px, weight 600 |
| Section title | Geist 15 px, weight 600 |
| Hint | Geist 12.5 px in Text tertiary |
| Numbers and identifiers | Geist Mono with tabular figures: scores, points, counts, keys and codes |
| Corner radius | One scale: 14 px for cards and dialogs, 10 px for buttons and inputs, full for chips, avatars and switches |
| Elevation | Borders, not shadows; only dialogs and toasts cast a shadow, tinted to the page |
| Icons | Phosphor, regular weight, 16, 20 or 24 px |
| Control height | 36 px for buttons, 38 px for inputs, 30 px for small buttons and segmented items |

| ID | Requirement |
|---|---|
| `FR-106` | The client shall define colour, type, radius and spacing as tokens with a light and a dark value, follow the system colour scheme, and offer no per-section inversion; a screen never uses a literal colour. |
| `FR-107` | The client shall use one accent colour; the positive, negative, caution and cool colours express state only, and no state is carried by colour alone ([FR-016](#accessibility)). |
| `FR-108` | Every text and control colour pair of the tokens shall meet WCAG 2.2 AA contrast in both themes; a new token is added only with its measured contrast. |
| `FR-109` | The client shall serve its fonts and icons itself and make no request to a third party. |
| `FR-110` | An icon shall never stand alone for meaning: it sits beside its label, or an icon-only button carries an accessible name and a tooltip. |

## Score presentation

A score is read at a glance on Prospects and explained on Account detail. The parts below look the same wherever they appear.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ [DG] DHL Group  dhl.com ↗  Germany, Logistics                [flame] Hot  78 │
│ [check] 88 Fit, how well it matches   [bolt] 72 Intent, recent signals       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Criterion   [check] Sector   Logistics   High    +37.5                       │
│             [dash]  Size     unknown     Medium  +12.5                       │
│ Signal      [plus]  AI and automation projects   Strong   +53.0              │
│             | "DHL setzt in über 1.000 Prozessen KI-Agenten ein…"            │
│             | English: "DHL uses AI agents in more than 1,000 processes…"    │
│             group.dhl.com, press release, 3 weeks ago        [Evidence]       │
└──────────────────────────────────────────────────────────────────────────────┘
```

WF-24 — score anatomy

| ID | Requirement |
|---|---|
| `FR-111` | A band shall be a chip with an icon and its label: Hot a filled accent chip with a flame, Warm a soft accent chip with a sun, Cold a cool chip with a snowflake; a standing other than Ranked is a neutral chip with its label and no band. |
| `FR-112` | Priority shall be shown as a number in the mono face, larger than Fit and Intent; Fit and Intent each carry a one-line meaning in words where they first appear on a screen, and a bar beside a number is drawn without a background track. |
| `FR-113` | A signal shall carry a polarity mark: a filled plus circle for a positive signal and a filled minus circle for a negative one, beside the question's label and the signed points. |
| `FR-114` | A Fit criterion shall carry a match mark: a check for matched, a dashed circle for unknown and a cross for not matched, beside the criterion's icon, its value, its weight level and its points; an unknown criterion says which fact to add to sharpen the score. |
| `FR-115` | A strength shall be a chip with the label Weak, Clear or Strong and a confidence shall follow [FR-009](#screen-labels); the deciding check is shown as Quick check or Detailed check. |
| `FR-116` | A quote shall be shown verbatim with a rule at its left, its English translation on the next line when the passage is not English, then its source domain, source type and age; in the evidence view the quoted sentence is highlighted inside its passage. |
| `FR-117` | Wherever a band is explained, the legend shall read the Warm and Hot thresholds from the service's active [scoring settings](/architecture/sql-store.md#scoring-settings-document), never from literals in the client. |

## States

| ID | Requirement |
|---|---|
| `FR-005` | Every data view shall render four states: loading (skeleton rows, no spinner longer than the content), empty (a sentence saying what would appear and the action that creates it), error (the error's message and a Retry button), and unavailable (for `503` and `429`: which dependency is unavailable and what still works, per [Degradation](/architecture/overview.md#degradation)). |
| `FR-006` | A `401` from any call shall send the user to Sign in with the current route as return path; a `403` shall show a "Not allowed" page naming the role required. |
| `FR-007` | A form shall keep the user's input when a save fails and show each `VALIDATION` field error next to its field. |
| `FR-118` | A loading state shall draw skeleton shapes the size of the rows or cards it stands in for, so the layout does not move when the data arrives; an empty state shall name the action that fills it and offer that action as a button; an unavailable state shall list what still works with a check for each item. |
| `FR-119` | A form field shall place its label above the input, its hint below the label or the input, and its error below the input in words; a placeholder is never the label. |

## Messages and feedback

| ID | Requirement |
|---|---|
| `FR-120` | Feedback shall take one of three forms: a toast for a completed action, a callout for a state that stays true while the screen is open, and a field error for input. A toast is announced as a status, can be dismissed, leaves by itself after the confirmation time of [Motion](#motion), and an error is never a toast. |
| `FR-121` | A callout shall carry an icon and one to two sentences, the first in bold when it names the state; its kind is neutral, accent, caution or error, each with its own icon. |
| `FR-122` | A user action that changes a score shall say so where it was taken: a verdict on a signal shows its result on the signal and a callout saying the account is being rescored, and the screen updates when the rescore run ends. |

## Confirmation

| ID | Requirement |
|---|---|
| `FR-015` | Erasing a contact, disabling a user, revoking an exception, activating scoring and deactivating a service or question shall ask for confirmation in a dialog that says what will happen; every other change applies on Save and confirms with a short toast. |
| `FR-123` | A dialog shall title itself with the action, say in one sentence what changes and what is kept, offer the cancel button first and the confirming button last, and name the confirming button after its verb, such as Disable user, never OK; Escape closes it and focus returns to the control that opened it. |

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
| Finding status `ACTIVE`, `REJECTED`, `SUPERSEDED` | Counting, Marked wrong, Outdated question |
| `decided_by` `CLASSIFIER`, `LLM` | Quick check, Detailed check |
| Scoring settings | Scoring |

| ID | Requirement |
|---|---|
| `FR-008` | Screens shall use the labels above and shall never show internal names such as `p_positive`, escalation, triage or token counts, except on the Admin screens Quality report and Audit log and in the Admin-only details of Runs. |
| `FR-009` | A confidence shall be shown as a word: High at `CONFIDENCE_HIGH_MIN` or above, Medium at `CONFIDENCE_MEDIUM_MIN` or above, Low below; the number is shown only in a tooltip. |

## Formatting

| ID | Requirement |
|---|---|
| `FR-010` | Dates shall be shown relative ("3 days ago") with the absolute date and time in the user's time zone in a tooltip; exports use ISO-8601. |
| `FR-011` | Country codes shall be shown with the country's English name; enum values with their label or a title-cased form of the value. |

## Motion

Motion tells a user that something changed. It never carries meaning alone, never delays a task, and every pattern below collapses to an instant change under `prefers-reduced-motion`. Only transform and opacity are animated. The animated components come from [React Bits](https://reactbits.dev), installed through its shadcn registry in the TypeScript and Tailwind variant and copied into `apps/web/src/components/motion/` ([ADR-17](/architecture/adrs/adr-17-animated-components-from-react-bits.md)); the Motion library supplies the rest.

| Pattern | React Bits family | Where | What it communicates |
|---|---|---|---|
| Count-up number | Text animations | Priority, Fit and Intent in the Account detail header when a rescore changes them | The value changed, and from what to what |
| Staggered entry | Animations | New alerts on Alerts and new candidates on Suggested accounts when a poll brings them | New items arrived |
| Rank reorder | Motion layout animation | Prospects after a rescore | Which accounts moved, and in which direction |
| Shimmer label | Text animations | The Refreshing label and the running status of a run | Work is in progress |
| Stepper | Components | The stages of a run and the three parts of Account import | Position in a process |
| Spotlight hover | Components | A card that is a link, on pointer devices | The card is clickable |
| Success pulse | Micro interactions | Copy, Push to HubSpot and Accept | The action completed |
| Blur-in text | Text animations | The headline of an empty state and of Sign in, once on arrival | A screen or state has arrived |
| Aurora background | Backgrounds | The brand panel of Sign in only | Ambience; the only WebGL, loaded lazily |

| Design value | Setting |
|---|---|
| Enter | 200 ms |
| Exit | 150 ms |
| Count-up | 600 ms |
| Stagger between items | 40 ms |
| Easing | `cubic-bezier(0.16, 1, 0.3, 1)` |
| Spring | stiffness 100, damping 20 |
| Toast visible | 6 s |

| ID | Requirement |
|---|---|
| `FR-124` | Every animation shall be one row of the patterns above; a pattern that is not listed is not used. |
| `FR-125` | Under `prefers-reduced-motion` every pattern shall show its end state at once, the running indicator shall show a static mark with its label, and the Aurora background shall show a still gradient of the same colours. |
| `FR-126` | A screen shall show at most one perpetual animation at a time, the running indicator; no pattern loops, parallax, scroll-driven motion or custom cursors are used on any screen. |
| `FR-127` | A button shall respond to a press within its own bounds, and a pattern shall never move content the user is reading or about to click. |
| `FR-128` | The Sign in background shall load lazily and its failure to load shall leave the still gradient; no other screen imports a WebGL library. |

## Polling

| ID | Requirement |
|---|---|
| `FR-012` | A screen showing a run in `QUEUED` or `RUNNING` shall poll `API-35` every `RUN_POLL_INTERVAL_MS` and stop when the run is final ([ADR-13](/architecture/adrs/adr-13-run-progress-by-polling.md)). |
| `FR-013` | The unread-alert count shall be refreshed every `ALERT_POLL_INTERVAL_MS` and when the window regains focus. |

## Tables and filters

| ID | Requirement |
|---|---|
| `FR-014` | A list shall page with `PAGE_SIZE_DEFAULT` rows, and its filters, sort and page shall be kept in the URL query so a view can be shared by link. |

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
| `CONFIDENCE_HIGH_MIN` | `0.85` | Lowest confidence shown as High |
| `CONFIDENCE_MEDIUM_MIN` | `0.65` | Lowest confidence shown as Medium |

## Examples

**A rescore lands on Account detail.** DHL Group was Warm with Priority 61. A refresh finds a strong signal and its run ends. The header counts Priority from 61 to 78 over the count-up time and the band chip changes from a soft sun chip to a filled flame chip; the History tab gains a row naming the refresh and the signal added ([FR-111](#score-presentation), [FR-124](#motion)). With `prefers-reduced-motion` the header shows 78 and Hot at once.

**A user marks a signal wrong.** The signal shows a chip saying it is marked wrong and no longer counts, and a callout saying the account is being rescored ([FR-122](#messages-and-feedback)). No toast is used, because the state stays true until the run ends. When the run ends the header numbers update as in the example above.
