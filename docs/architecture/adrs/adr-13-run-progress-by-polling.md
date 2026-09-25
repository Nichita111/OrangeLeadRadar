---
type: Decision
title: ADR-13 Run progress by polling
description: The frontend follows a run by polling it every few seconds instead of a push channel.
status: draft
tags: [signal-pipeline, prospect-dashboard, service-configuration, evaluation-and-feedback]
---

# ADR-13 Run progress by polling

## Context

Users follow refreshes and other runs live. Runs last seconds to minutes and change stage a handful of times.

## Decision

The frontend polls `API-35` every `RUN_POLL_INTERVAL_MS` while a run is queued or running and stops when it is final ([Polling](/architecture/services/frontend.md#polling)).

## Consequences

- No streaming through the proxy, no connection state in the api.
- Progress lags by up to one interval; the load is one small read per open screen.

## Alternatives considered

- **Server-sent events or WebSockets.** Rejected: more infrastructure for no visible benefit at this cadence.
