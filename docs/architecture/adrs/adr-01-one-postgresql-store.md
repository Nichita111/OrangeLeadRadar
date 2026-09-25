---
type: Decision
title: ADR-01 One PostgreSQL store
description: The single PostgreSQL store with pgvector that holds everything, and why there is no graph store or GraphRAG.
status: draft
tags: [signal-pipeline]
---

# ADR-01 One PostgreSQL store

## Context

LeadRadar stores configuration, accounts, fetched documents, passages with embeddings, classifier answers, findings, scores, a job queue and an audit. Its central question is narrow and per account: does company X show signal Q for service S, and where is the evidence? The questions are written by users and change. A GraphRAG design — extracting every entity and relation of every document into a knowledge graph up front and answering from the graph — was proposed.

## Decision

One PostgreSQL 16 database with the `pgvector` extension holds every table of the [SQL store](/architecture/sql-store.md), including passage embeddings and the job queue. There is no graph database and no GraphRAG. The relationships that matter — an account's parent, contacts, sources, a finding's passage and document — are ordinary foreign keys.

## Consequences

- One transaction boundary, one backup and one schema to migrate.
- Similarity search uses an HNSW index on passage embeddings; at the target volume it needs no separate vector store.
- A question across accounts, such as "which prospects work with provider X", is SQL over findings; if such questions become central, a graph store needs its own decision.

## Alternatives considered

- **GraphRAG over an extracted entity graph.** Rejected: questions are configurable, so a graph built for today's questions misses tomorrow's and must be re-extracted; extraction costs an LLM call per passage, mostly on irrelevant text; and the evidence chain gets longer — passage, extracted triple, graph, answer — which weakens the verbatim quote every finding must carry.
- **MongoDB.** Rejected: foreign keys, unique constraints and transactions carry the traceability and idempotency rules.
- **A dedicated vector database.** Rejected: unnecessary at this scale and a second store to keep consistent.
