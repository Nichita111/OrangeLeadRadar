---
type: Guideline
title: Coding guidelines
description: How we approach code in any language - how a change is made from the specification, functions before objects, purity and idempotency, types, structure and layering, errors without fallbacks, comments, dependencies, configuration and validation.
status: draft
tags: []
---

# Coding guidelines

How we write code, in any language. What the code must do is specification and lives in `/requirements/` and `/architecture/`; how a language spells these rules is in its own guideline. A sentence here that would be false in another repository is in the wrong file.

## How to approach a change

1. **Start from the requirement and follow its links.** A task names `S-`, `N-` or `FR-` rows. Open the feature's reading order and the [traceability matrix](/requirements/traceability.md): the flows, tables, rules and contracts they name are part of what you were asked to build. If a behaviour is specified nowhere, stop: that is a specification gap, fixed in the documents first ([R7](/guidelines/documents/common.md#the-eight-rules)), never invented in code.
2. **Write the test first and watch it fail.** Red, green, refactor. A test that never failed has not been shown to test anything. Which level and who writes it is [the pyramid](/guidelines/testing.md#the-pyramid-and-who-writes-what).
3. **Work outside in.** Contract, then rule, then table, then the code that satisfies them. A shape invented in the implementation and reconciled later is a shape nobody agreed to.
4. **Name every runtime number as a configuration key** with its default in the owning service's `Runtime` section. A literal threshold, limit or timeout is a defect.
5. **Carry the document change in the same commit** when a table, rule, contract or screen moved.
6. **Build the smallest thing the requirement asks for.** No speculative option, abstraction, plug-in point or configuration that no requirement reads ([P-06](/architecture/overview.md#principles)).

## Functions first

- Prefer pure functions over methods. A class with no state between calls is a namespace with ceremony; a class with one method and no state is a function.
- Objects earn their place where there is identity and an invariant to protect: domain values, models at a boundary, and the few honest polymorphic seams — the [classifier adapters](/architecture/services/worker.md#ai-gateway) and the [source plug-ins](/architecture/services/worker.md#source-plug-ins).
- Compose; do not inherit for reuse. Immutable by default: a transformation returns a new value.
- Small, total functions: handle every input of the type without special cases at the call site.

## Purity, idempotency and state

- **A pure core, with I/O at the edges.** Every rule of [rules](/architecture/rules.md) — scoring, decay, routing, validation, normalisation — is a pure function of its inputs: no database, network, clock or randomness inside. Adapters fetch and store; they do not decide.
- **Inject time, randomness and identity.** `as_of`, the scheduler's clock and id generation arrive as arguments.
- **Writes are idempotent.** A job may run twice; a user may double-click. Every write goes through a unique constraint or checks what is already recorded, so repetition converges ([N-05](/requirements/system.md)).
- **Stateless processes.** The api and the worker keep nothing between requests or jobs except bounded caches that are safe to lose, such as per-job question embeddings. State lives in the database, owned by one writer per the [store ownership](/architecture/overview.md#store-ownership) table.
- **Effects are visible at the signature.** A function that writes, fetches or calls a model says so in its name and type.

## Types

- Everything is typed, in the strictest mode the language offers, for the whole project.
- **No suppressions.** An inline ignore of the type checker or linter is itself a violation; a finding is fixed, not hidden.
- **Make illegal states unrepresentable.** A closed set is an enum or a literal union, never a bare string; parse into a type at the boundary and trust it afterwards.
- A shape that crosses a boundary has a name, the one [interfaces](/architecture/interfaces.md) gives it.

## Structure

**Layering.** Dependencies point one way: route or job handler → capability function → store access, with the pure rules beside them and depending on nothing. A handler validates input, calls one capability function and shapes the result; that function owns the transaction. A cycle between layers is a design defect.

**Modules by capability.** Group code by the capabilities of the interface families — services and questions, scoring, accounts, discovery, runs, prospects, feedback, evaluation, outreach, audit — plus the worker's pipeline stages and the AI gateway. Everything of one capability lives together.

**Naming.** The glossary term, or its identifier, is the name: `finding`, `account_score`, `p_positive`, never a synonym. A name not in the glossary goes into the glossary first.

**One writer per fact.** A column is written by the process the [store ownership](/architecture/overview.md#store-ownership) table names and by one function in it. Scores are written only by the worker's rescoring.

## Errors

- A typed error hierarchy per capability, mapped once at the edge onto the envelope and codes of [Conventions](/architecture/interfaces.md#conventions).
- **Never swallow.** A caught error is acted on, or logged with the reason it is safe to ignore.
- **No fallback results.** When a dependency fails, the failure is returned or recorded: no placeholder quote, no invented finding, no empty list pretending there was no data, no untranslated text claimed as translated. Degradation is what [Degradation](/architecture/overview.md#degradation) states, driven by the caller recognising the error.
- Distinguish the caller's fault (`VALIDATION`, `CONFLICT`) from ours (`UPSTREAM_UNAVAILABLE`, `INTERNAL`).

## Comments

Comment the non-obvious: why an invariant holds, why a query has that shape. Link the rule instead of restating it. Never narrate what the line says.

## Dependencies

A new dependency needs a reason in the pull request: what it replaces, what it costs, and why the standard library or an existing dependency does not do it.

## Validation

Each target validates itself with its own commands; the root composes them. *planned*: `make validate` at the root runs every target's checks and every test level, and `make validate-quick` checks the changed files. Both are blocking: the only passing state is zero findings, with no baseline and no advisory mode. The way out of a red gate is a correct implementation, never a quieter check.

| Property | Enforced by |
|---|---|
| Every signature typed in strict mode | the language's type checker |
| No suppression of any kind | the language's linter configuration |
| No runtime number as a literal | review, and a lint rule where the language allows |
| No declared dependency that is unused | the language's dependency checker |
| The pure core imports no I/O module | an import-boundary rule |
| Documents follow the conventions | `scripts/check_docs.py` |
