---
type: Decision
title: ADR-05 LangGraph only for the signal graph
description: The branching triage, classify, escalate and evidence step is a LangGraph state graph; every other step is plain code.
status: draft
tags: [signal-pipeline]
---

# ADR-05 LangGraph only for the signal graph

## Context

The brief expects LangChain or LangGraph. The pipeline has one genuinely branching, per-item flow — triage, passage selection, classification, routing by confidence to escalation or evidence, validation, persistence — and several simple steps: fetching, processing, scoring. The job queue already provides durability and retries.

## Decision

The `SIGNAL` job step is a LangGraph `StateGraph`, as drawn in the [signal graph](/architecture/services/worker.md#signal-graph). It uses no LangGraph checkpointer: each node writes its results to the database before the next runs, and the job is the unit of retry. Model calls go through the AI gateway's own adapters rather than LangChain wrappers.

## Consequences

- The cascade's branching is explicit and matches its diagram.
- The LangGraph dependency is confined to one module.
- Fetching, processing and scoring stay plain, testable functions.

## Alternatives considered

- **LangGraph for the whole pipeline.** Rejected: it would duplicate the job queue's state and retries.
- **No LangGraph.** Viable, but the graph form documents and structures the cascade well at little cost.
