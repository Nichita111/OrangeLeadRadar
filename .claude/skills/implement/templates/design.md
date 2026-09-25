# Design: <task title>

## Summary

Three to five sentences: what the task adds to the system and how, in glossary terms.

## Specification read

Every heading the design rests on, as links: requirement rows, flows, tables, rules, contracts, configuration keys, screens, decisions.

## Existing state

What already exists that this task builds on, and what is missing.

## Prerequisites

Public surfaces the acceptance criteria need; whether each exists, is added by this task (smallest piece only), or makes a criterion deferred.

## Changes, outside in

| Order | Module or file | Change | Specified by |
|---|---|---|---|
| 1 | contract / route | … | `API-nn` |
| 2 | rule in `core` | … | `docs/architecture/rules.md#…` |
| 3 | table / migration | … | `docs/architecture/sql-store.md#…` |
| 4 | capability, worker step, screen | … | `FR-nnn` |

## Configuration keys

Keys read, each already defined in a service's `Runtime` section. A new key is a document change below.

## Tests for the coder

| Level | Test (behaviour it checks) | Covers |
|---|---|---|
| unit | … | rule, example, boundary |
| integration | … | table, constraint, idempotency |
| contract | … | `API-nn` |

## Acceptance coverage

| Criterion | In scope now or deferred | Surface it needs |
|---|---|---|

## Document changes

For each: the owning heading, the exact new text, whether it touches a requirements register (separate commit, human review), whether an ADR is required. "None" when there are none.

## Not building

What a reader might expect but this task deliberately leaves out, and why no row in scope needs it.

## Specification gaps

For each: the question, the options, the recommended option, and the heading that would change. "None" when there are none.

## Risks

What could make the task larger than designed.
