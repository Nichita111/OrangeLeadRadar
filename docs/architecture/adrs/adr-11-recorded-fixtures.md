---
type: Decision
title: ADR-11 Recorded fixtures
description: Every source, classifier and LLM exchange can be recorded and replayed, so the demo and the acceptance tests run offline and repeatably.
status: draft
tags: [signal-pipeline, evaluation-and-feedback, outreach-and-crm]
---

# ADR-11 Recorded fixtures

## Context

The demo must not depend on live networks, quotas or model variability, and acceptance tests must be deterministic. Mocks written by hand drift from real providers.

## Decision

`FIXTURE_MODE` `record` stores each plug-in request and each AI gateway call under `FIXTURE_DIR`, keyed by a SHA-256 of the adapter and the normalised request; `replay` answers from those files and fails a missing one with `FIXTURE_MISSING`, never falling back to a live call. The local embedder runs live in every mode.

## Consequences

- The acceptance suite and the demo are repeatable offline.
- A change to a prompt or request shape requires re-recording the affected fixtures.
- Fixtures are committed data and must contain no secrets or personal data beyond public sources.

## Alternatives considered

- **Hand-written mocks.** Rejected: they test the mock.
- **Live calls in tests.** Rejected: flaky, slow and costly.
