---
type: Decision
title: ADR-08 Multilingual embeddings
description: Passages are embedded with bge-m3 served locally by Text Embeddings Inference, for passage selection, near-duplicate detection and preview search.
status: draft
tags: [signal-pipeline]
---

# ADR-08 Multilingual embeddings

## Context

Target accounts publish in German, French, Italian and other languages; the same story appears in several languages; annual reports run to hundreds of pages; and an Admin trying a question on an account needs its most relevant passages.

## Decision

Dense embeddings of `BAAI/bge-m3`, dimension `EMBEDDING_DIM`, computed by a local Hugging Face Text Embeddings Inference container and stored in `pgvector`. They select passages of long documents, detect near duplicates across languages and rank passages for question preview. They never decide an answer.

## Consequences

- No second AI vendor and no document text leaving the deployment for embedding.
- Cross-lingual similarity works out of the box; CPU inference is sufficient at the demo volume.
- A change of embedding model requires re-embedding stored passages.

## Alternatives considered

- **A hosted embedding API.** Rejected: another vendor and data transfer.
- **No embeddings.** Rejected: every passage of every long report would need classifying.
