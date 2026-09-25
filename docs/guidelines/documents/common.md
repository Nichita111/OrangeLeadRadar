---
type: Guideline
title: Document conventions
description: The layout, the eight rules, identifier families, traceability, frontmatter, addressing and the placement guide every document in this bundle obeys; read before writing or moving any document.
status: draft
tags: []
---

# Document conventions

This bundle is the single source of truth for building LeadRadar. It follows the [Open Knowledge Format](https://okf.md/spec/) v0.2: every non-reserved `.md` file carries frontmatter with a `type`; `index.md` and `log.md` are reserved. Everything is readable with `cat`. The scripts in `scripts/` generate the indexes and the traceability matrix and check the rules; they run in the scripts project's own environment.

The heading skeleton of each type is in [templates](/guidelines/documents/templates.md).

## Layout

```
AGENTS.md                         the agent chain: Architect, Coder, QA, Critic
scripts/build_indexes.py          generates every index.md from frontmatter
scripts/build_traceability.py     generates requirements/traceability.md from the registers
scripts/check_docs.py             checks the rules below; exit code 1 on any finding
docs/
├── index.md                      generated: one line per document, grouped by folder
├── log.md                        change history, newest first
├── reference/  index.md          Reference   the external brief, as received
├── guidelines/ index.md          Guideline   how we write code and documents
│   └── documents/ index.md       Guideline   these conventions and the templates
├── requirements/ index.md        Requirements · Glossary   why and what
│   ├── business.md               objective, roles, RULE-nn, B-nn, SC-x, assumptions
│   ├── system.md                 S-XXX-nn and N-nn with Realises, Flows, Entities, Specified in
│   ├── acceptance.md             AC-nn, scenario pass criteria, release gate
│   ├── traceability.md           generated: requirement → flow → entity → acceptance
│   └── glossary.md               terms, identifiers, do-not-translate list
├── architecture/ index.md        how it is built
│   ├── overview.md               Architecture   principles, topology, runtime, ownership, AI roles, degradation, demo dataset
│   ├── sql-store.md              Store          every table, column, enum and constraint
│   ├── rules.md                  Rule           every deterministic computation
│   ├── interfaces.md             Interface      every contract that crosses a boundary, and its shapes
│   ├── adrs/ index.md            Decision       ADR-nn, one file per decision
│   └── services/ index.md        Service        api, worker, frontend
└── features/   index.md          Feature        one file per feature: flows, reading order, screens, open questions
```

Eleven types: `Reference`, `Guideline`, `Requirements`, `Glossary`, `Architecture`, `Store`, `Rule`, `Interface`, `Decision`, `Service`, `Feature`. The `architecture/` files other than `adrs/` and `services/` are the **kernel**: what every service must agree on.

## The eight rules

**R1 — Folder = question, type = template.** Five folders answer five questions: what we were asked (`reference/`), why and what (`requirements/`), how it is built (`architecture/`), how one feature runs end to end (`features/`), how we write (`guidelines/`). Every document declares one type, allowed in its folder; the type fixes its template. No document in the bundle root. Every folder has a generated `index.md`. `reference/` holds external material as received: it is cited, never edited to match the specification, and exempt from R4.

**R2 — Concept = anchored heading; file = what is read together.** A table, a rule, an interface family, an ADR, a flow, a screen, a requirement row is a concept with a stable identifier or a unique heading, linked by anchor. A new file appears only for a new group not read with an existing one: a new service, a new feature. A new concept is a new heading.

**R3 — One owner per fact; definitions do not know their users.** Grep before writing; if the fact exists, link to it. Links point from consumer to definition: `features → services → kernel → requirements`, and inside the kernel `interfaces → rules → store`. Anything may link to an ADR, the glossary or `reference/`. `requirements/system.md` links to whatever specifies a row. A feature may link to a screen or flow of another feature when a flow crosses it. Never copy a table, a shape, an enum or a rule: an enum is defined once, under the column that owns it, and every consumer names it by link. A rule is implemented by exactly one service; another that runs it says "invokes".

**R4 — Nothing ephemeral, nothing legacy.** No implementation status marks other than the `*planned*` tooling marker of the Guideline template, no code line citations, gap registers, to-dos or revision tables. No legacy aliases or "formerly known as": a rename replaces every occurrence. Work status lives in the tracker and in git. Document status is a property of the file (frontmatter).

**R5 — Stable addresses, one name per concept.** Headings are unnumbered, unique within a file, plain ASCII. Identifiers are never reused or renumbered; a retired one is listed once in the glossary under Retired identifiers. Every concept has one term, recorded in the glossary with the implementation identifier it maps to. A screen's heading and its route use the screen's label, as the frontend's [Routes](/architecture/services/frontend.md#routes) lists them; API paths and tables use the identifier. `FR-` and `WF-` rows live on the screen that carries them, or in the frontend service for shell-level rows.

| Family | Owner | Numbering |
|---|---|---|
| `ADR-nn` | `architecture/adrs/` | next integer, one file per decision |
| `B-nn`, `RULE-nn`, `SC-x` | `requirements/business.md` | next integer / next letter |
| `S-XXX-nn`, `N-nn` | `requirements/system.md` | `XXX` is the area code of its `##`; next integer within the area |
| `AC-nn` | `requirements/acceptance.md` | next integer |
| `FL-nn` | the feature that owns the flow, as a `### FL-nn Title` heading under `## Flows` | next integer across the bundle |
| `API-nn` | `architecture/interfaces.md` | next integer, one per contract |
| `FR-nnn` | the screen or shell section that carries it | next integer across the bundle |
| `WF-nn` | the screen that carries it | next integer across the bundle |
| `P-nn` | `architecture/overview.md` | next integer |

ADRs are append-only; only the human owner may consolidate, trim or move one, recording the previous state in one `Supersedes` sentence.

**R6 — Frontmatter is five fields.** `type`, `title`, `description`, `status`, `tags`. `title` and `description` are the document's index line; the description is one sentence saying what the reader finds inside. `tags` are the feature slugs whose reading orders link the file. Optional, only when true: `sources: [https://…]` for genuinely external material.

**R7 — One change flow.** Edit the owning heading → grep the bundle for inbound links, for the identifiers involved and for words the change invalidates → fix every consumer → regenerate the indexes and the traceability matrix → run the checker → add one line to `log.md` → append an ADR when the change reverses a decision, adds or removes a store, service, interface family or an enum value a rule branches on, or changes an invariant. A code change to a table, rule, contract or screen carries its document change in the same commit. A change to a requirements register is its own commit, reviewed by a human before code depends on it. `draft → stable` requires human review.

**R8 — Readable with `cat`, checked by scripts.** No rule depends on tooling beyond `scripts/`. The checker verifies what can be verified mechanically; meaning (R3 duplication, R7 consumer updates, R5 naming) remains grep and review.

## Traceability

The coding chain in `AGENTS.md` needs every requirement to lead to the flows it is exercised in, the data it touches and the criteria that verify it. The registers carry these links; nothing else restates them.

- Every `S-` and `N-` row of [system requirements](/requirements/system.md) names the `B-` or `RULE-` rows it **Realises**, the `FL-` **Flows** it is exercised in (or `all`), the store **Entities** it reads or writes (or `none`) and the headings it is **Specified in**.
- Every `AC-` row of [acceptance criteria](/requirements/acceptance.md) names the rows it **Verifies**.
- The [traceability matrix](/requirements/traceability.md) is generated from those columns by `scripts/build_traceability.py`; it is never edited by hand.
- The checker fails when an `S-` or `N-` row has no realised row, flow, entity or specifying link, or no verifying `AC-` row; when an `AC-` row verifies an unknown identifier; when a `P0` or `P1` `B-` row is realised by no `S-` row; when a flow is named by no requirement; or when a table of the SQL store is named by no requirement.

## Tooling

| Command | When | What it does |
|---|---|---|
| `uv run --project scripts python scripts/build_indexes.py` | after adding, renaming, moving or re-describing a document | Rewrites every `index.md` from the documents' `title` and `description` |
| `uv run --project scripts python scripts/build_traceability.py` | after changing a register row or a flow heading | Rewrites `requirements/traceability.md` |
| `uv run --project scripts python scripts/check_docs.py` | before every commit that touches `docs/` | Exit 1 on any finding: types and folders, frontmatter, headings, ADR file names, duplicate identifiers, `FR-` rows outside features and the frontend service, broken links and anchors, ephemeral marks, log format, the traceability rules above, identifiers cited but declared nowhere, gaps in an identifier family's numbering that the glossary does not retire, an `S-` row whose priority differs from the highest it realises, a release gate that does not exclude exactly the non-P0 criteria, a scenario naming a criterion outside the gate, `tags` that differ from the features whose reading order links the file, and any stale generated file |

Generated files are never edited by hand. A finding is a defect, not a warning.

## Frontmatter

```yaml
---
type: Rule                       # one of the eleven types
title: Rules
description: One sentence; this is the index line and the retrieval key.
status: draft                    # draft | stable | deprecated
tags: [signal-pipeline]          # feature slugs whose reading order links this file; [] when none
---
```

`index.md` and `log.md` carry no frontmatter, except `okf_version: "0.2"` on the root index.

## Addressing and links

- Links are bundle-absolute: `/architecture/sql-store.md#finding`. Generated index files use relative links.
- Anchors are GitHub heading slugs: lowercase, spaces to hyphens, punctuation removed. `### account_score` → `#account_score`; `### FL-07 Refresh one account` → `#fl-07-refresh-one-account`.
- A register row is cited by identifier and linked to its file: `[S-SIG-05](/requirements/system.md)`.
- Runtime numbers — thresholds, limits, timeouts, defaults — are configuration keys, defined once with their default in the owning service's `Runtime` section, or keys of the scoring settings document; a requirement, rule or screen names the key. Design values — layout widths, colours — are literal on the screen or in the frontend service.
- Naming follows the glossary. When a file and the glossary disagree, the glossary wins and the file is fixed.

## Literal cells and illustrative ones

A table cell is either **literal** — a value a mechanism consumes: an identifier, a configuration key, an enum value, a CSV column name, a route, a default — or **illustrative** — a meaning, a rule, a note. A literal cell is written exactly as the thing it names: in full, with its case and punctuation, never abbreviated or paraphrased; it is the one owner of that spelling. An ellipsis is allowed only in a wireframe, truncating a value whose full spelling is owned elsewhere. A cell whose ellipsis stands for text the bundle carries nowhere is a missing fact.

## Placement guide

Ask the first question that gets a yes.

| Does it state… | Goes to | Type |
|---|---|---|
| a term, its meaning and its identifier; a retired term or identifier | `requirements/glossary.md` | Glossary |
| an obligation with a register identifier (`B-`, `RULE-`, `SC-`, `S-`, `N-`, `AC-`) | a row of the matching register in `requirements/` | Requirements |
| a persisted table, column, enum, index or constraint | `architecture/sql-store.md`, under the table's heading | Store |
| a deterministic computation, invariant or transition over stored data | `architecture/rules.md`, one `##` per subject | Rule |
| a contract that crosses a service or system boundary, or a shape or error code that exists only on the wire | `architecture/interfaces.md` | Interface |
| a choice that must outlive the conversation that made it | `architecture/adrs/`, appended | Decision |
| how one service is built internally, and its configuration keys | `architecture/services/<service>.md` | Service |
| a UI concern that applies to every screen | `architecture/services/frontend.md` | Service |
| how the system as a whole is built, when no store, rule, interface or service owns it | `architecture/overview.md` | Architecture |
| what a user sees on one screen (`FR-`, `WF-`), or how a feature runs end to end (`FL-`) | `features/<feature>.md` | Feature |
| how we write code or documents | `guidelines/` | Guideline |
| the brief or other material received from outside | `reference/` | Reference |
| implementation status, a to-do, a code line | not documentation: the tracker or git | — |

Store = what is persisted. Rule = how it is computed. Interface = what crosses a boundary. Service = who runs it. Feature = what a user does with it.
