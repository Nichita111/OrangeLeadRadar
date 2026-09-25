---
type: Guideline
title: Testing guidelines
description: The test pyramid and which agent writes what, independence of acceptance tests from the implementation, determinism and fixtures, what makes a good assertion, and traceability from each test to its acceptance criterion.
status: draft
tags: []
---

# Testing guidelines

How we test, in any language. What the system must do is specification; this file never restates it. The order — test first, seen to fail — is in [how to approach a change](/guidelines/coding.md#how-to-approach-a-change).

## The pyramid and who writes what

The level of a test decides what its author may look at.

| Level | Written by | May look at | Lives in |
|---|---|---|---|
| **Unit** | Coder | the implementation | `apps/api/tests/unit/`; in `apps/web`, beside the source |
| **Integration** | Coder | the implementation, a real PostgreSQL with `pgvector` | `apps/api/tests/integration/` |
| **Contract** | Coder | [interfaces](/architecture/interfaces.md) and the generated schemas | `apps/api/tests/contract/` |
| **Acceptance** | QA | **the specification only** | `tests/acceptance/`, pytest against the composed stack |
| **End-to-end** | QA | **the specification only** | `tests/e2e/`, Playwright against the composed stack |

**Acceptance and end-to-end tests are written from the acceptance criteria, by the QA agent, without reading the implementation.** A test that mirrors the code only detects that the code changed. When an acceptance test fails, QA reads the failure and the specification, not the source. If the specification cannot say what is right, that is a finding for a human, never resolved by matching the implementation.

## Unit tests

- Cover the pure core exhaustively: every rule of [rules](/architecture/rules.md), including its examples and boundaries (thresholds at, just below and just above).
- Table-driven where inputs are enumerable. No database, network or model.

## Integration tests

- Store access against a real PostgreSQL: unique constraints, idempotent writes, job claiming under concurrency, migrations from empty.

## Contract tests

- Every route against its contracts row: method, path, roles, request and response shapes, error codes.
- Every adapter's output against recorded fixtures of its provider.
- The frontend's generated client compiles against the current OpenAPI document.

## Acceptance tests

- One test per `AC-` row, tagged with its identifier: `@pytest.mark.ac("AC-24")`. A test verifying several criteria carries each tag.
- Driven through the REST contracts of the composed stack, in `FIXTURE_MODE` `replay`, seeded with the [demo dataset](/architecture/overview.md#demo-dataset). The clock is injected through `CLOCK_FILE` of the [worker runtime](/architecture/services/worker.md#runtime); nothing else is substituted.
- Named after the behaviour the criterion states, not the endpoint.

## End-to-end tests

- Playwright against the composed stack, following the journeys of the business scenarios `SC-A` to `SC-D` and the criteria that need a screen; each test's title starts with the `AC-` or `SC-` identifier.

## Determinism tests

- The same inputs and `as_of` produce a byte-identical score breakdown; run it twice in one test and compare ([N-04](/requirements/system.md)).
- A repeated refresh with unchanged recordings creates no new rows ([N-05](/requirements/system.md)).
- No value shown as a score, band or standing comes from a model.

## Models and providers in tests

- No test calls a live provider. Classifier, LLM and source exchanges come from fixtures recorded with `FIXTURE_MODE` `record` ([ADR-11](/architecture/adrs/adr-11-recorded-fixtures.md)); a missing fixture fails the test.
- A fixture that simulates a failure — a timeout, an invalid output, a plug-in error — is a recorded exchange like any other, named for the failure it plays.
- Re-record a fixture when its prompt version or request shape changes; the prompt version is part of the key.

## Test independence

- Tests run in any order and in parallel; each arranges its own data and leaves nothing behind. Acceptance tests use a fresh database per test module.
- No sleeps: wait for the condition — a run's final status — with a timeout.
- A flaky test is a defect: fix it or delete it, never retry it into green.

## What makes a good assertion

- Assert the observable outcome the criterion names, with its exact value where it has one: `Fit == 94`, not `Fit > 0`.
- Assert what must not happen as well: no `AI_CALL` row during a rescore, no request to `linkedin.com`.

## Traceability

- Every `AC-` row has at least one test carrying its tag; the QA agent reports criteria without a test as a finding.
- Every `FR-` row is exercised by a component test or an end-to-end test that names it.
- The [traceability matrix](/requirements/traceability.md) tells QA which criteria a task's requirements need.

## No skipped tests

A skipped or disabled test is not allowed in a passing suite. A test for a P1 or P2 criterion that is not yet built does not exist yet; it is not written and skipped.
