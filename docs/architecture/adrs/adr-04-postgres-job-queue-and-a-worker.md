---
type: Decision
title: ADR-04 Postgres job queue and a worker
description: Background work runs in a separate worker process that claims jobs from a PostgreSQL table, enqueued in the same transaction as the change that needs them.
status: draft
tags: [signal-pipeline, service-configuration, accounts-and-discovery, prospect-dashboard, evaluation-and-feedback]
---

# ADR-04 Postgres job queue and a worker

## Context

Refreshes, reclassification, rescoring, discovery and evaluation run in the background with retries, priorities and visible progress. The api must never lose the work a change requires, and the stack should have as few moving parts as possible.

## Decision

A [`job`](/architecture/sql-store.md#job) table claimed with `FOR UPDATE SKIP LOCKED` by a separate [worker](/architecture/services/worker.md) process built from the same package as the api. The api writes a change, its audit row, its [`pipeline_run`](/architecture/sql-store.md#pipeline_run) and the run's first jobs in one transaction. No Redis, Celery or message broker.

## Consequences

- A change and its follow-up work commit or fail together.
- One fewer service to run; throughput is bounded by PostgreSQL, which is ample at the target volume.
- More worker containers can share the queue; the scheduler takes an advisory lock so only one schedules.

## Alternatives considered

- **Celery or Arq on Redis.** Rejected: another service, and enqueueing cannot join the database transaction.
- **In-process background tasks in the api.** Rejected: work is lost on restart and competes with requests.
