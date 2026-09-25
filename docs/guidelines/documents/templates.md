---
type: Guideline
title: Document templates
description: The heading skeleton each of the eleven document types follows; read when creating a document or adding a concept heading to one.
status: draft
tags: []
---

# Document templates

Frontmatter plus the headings below. A section that would be empty is omitted, never stubbed. Every concept heading is unique in its file. The type in frontmatter fixes which template applies ([R1](/guidelines/documents/common.md#the-eight-rules)).

## Register

For `requirements/business.md`, `system.md` and `acceptance.md`.

```
# <register name>
## <opening>                  ← optional: what the register is for and how its rows are read
## <family or area>           ← one per identifier family, or one per area for S-XXX-nn; the table
### <area>                    ← optional: one per area within a family, each with its own table
## <closing>                  ← optional: gates, scenario pass criteria
```

One table per heading. The identifier is the first column and the only address. A row states one obligation in "shall" form and links to the heading that specifies it; it never restates the specification or lists enum values. The columns are fixed per family:

| Family | Columns |
|---|---|
| `B-nn` | ID · Requirement · Priority |
| `RULE-nn` | Rule · Statement · Specified by |
| `S-XXX-nn` | Id · Requirement · Priority · Realises · Flows · Entities · Specified in |
| `N-nn` | Id · Requirement · Priority · Realises · Flows · Entities · Measure · Specified in |
| `AC-nn` | ID · Criterion (Given / When / Then) · Verifies |

## Glossary

```
## Terms                      ← table: term · meaning · identifier · defined in (link)
## Do not translate           ← protected values
## Retired terms              ← only when a term has been retired: retired · use instead · since
## Retired identifiers        ← only when an identifier has been retired: identifier · reason · replaced by
```

## Architecture

For `architecture/overview.md`.

```
# <title>
## Purpose · ## Principles · ## Topology · ## Runtime · ## Store ownership
## AI roles and boundaries · ## Degradation · ## Production path · ## Demo dataset
```

## Store

```
# <store name>
One paragraph: what it holds and who owns it.
## <domain>                   ← grouping, opening with an ER diagram in mermaid
### <table>                   ← one per table; columns table; enums defined here with every value and meaning
## <cross-table document>     ← e.g. a JSON document stored in a column, a shared vocabulary
## Hard-delete allow-list
## Constraints and indexes
```

Only `###` headings name tables: the checker treats every `###` of the store as a table that some requirement must name.

## Rule

```
# <engine name>
## <rule subject>             ← one per rule: Inputs · Algorithm · Invariants (or After)
## Examples                   ← worked cases the acceptance criteria verify
```

## Interface

```
# Interfaces
## Conventions                ← transport, roles, authentication, pagination, envelope, error codes
## <family>                   ← one per family
### <family> contracts        ← REST: ID · Method · Path · Roles · Request → response
                                in-process: ID · Operation · Module · Transaction · Returns
### <family> shapes           ← one #### per shape; Field · Type · Source of truth
```

A contracts heading and a shape heading each carry exactly one table. Behaviour beyond the table is a list under it, one item per contract.

## Service

```
# <service name>
## Responsibilities           ← what it does and the boundary: what it never does
## Owns                       ← tables written, rules implemented; rules it only runs say "invokes"
## Provides and consumes      ← interface families
## Design                     ← internal structure; frontend: one ## per shell concern with its FR rows
## Runtime                    ← configuration keys: Key · Default · Meaning
## Examples
```

## Decision

```
# ADR-nn <title>              ← file architecture/adrs/adr-nn-<slug of the title>.md
## Context · ## Decision · ## Consequences · ## Alternatives considered · ## Supersedes (when true)
```

Context states the problem. Alternatives considered is the only place a rejected option is named. Supersedes is the only place a previous state is named.

## Feature

```
# <feature name>
## Purpose                    ← one paragraph
## Flows
### FL-nn <title>             ← one per end-to-end flow; numbered steps, mermaid sequence where useful
## Reading order              ← numbered absolute links in dependency order:
                                glossary terms → requirement rows → store → rules → interfaces → services
                                → decisions → screens → acceptance rows
## <screen label>             ← one per screen: route and roles · Layout (wireframe with its WF-nn) ·
                                Behaviour (FR table, then one "Obligations:" line naming the register rows
                                the screen satisfies) · Data (contract ids) · States (link)
## Open questions             ← specification gaps only: what is missing and who decides
```

## Guideline

Free structure. States craft rules only, never a requirement. Uses glossary vocabulary. Names tooling only if it exists in the repository; tooling that does not exist yet is marked *planned*.

## Reference

External material as received, converted to Markdown with the source's own headings; frontmatter plus the content. Never edited to match the specification.
