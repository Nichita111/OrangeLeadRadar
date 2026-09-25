---
type: Decision
title: ADR-16 Question-scoped hybrid passage selection
description: Short documents are read whole, long ones are split at their sections, every passage is read with a header, and each question retrieves its own passages of a long document by keyword and by meaning, fused by rank.
status: draft
tags: [signal-pipeline]
---

# ADR-16 Question-scoped hybrid passage selection

## Context

Every document was split into passages of one size, and a long document's passages were selected per service: the ones most similar, by embedding, to any of the service's questions. Three problems follow. A frequent topic crowds out rare ones: a 300-page report fills every slot with its cost programme, and the one sentence announcing a new Chief Digital Officer is never read. A new question is only asked of passages chosen for the old questions, so evidence for it in stored reports is never found. Embeddings blur the exact names that incumbent-provider and regulation signals hinge on — UiPath, Celonis, NIS2, DORA. Short documents gain nothing from splitting, and a passage cut from the middle of a posting or an article loses the title that gives it meaning.

## Decision

[Chunking and passage selection](/architecture/rules.md#chunking-and-passage-selection) reads a document of at most `WHOLE_DOCUMENT_MAX_CHARS` whole, as one passage, and splits a longer one at its sections — HTML headings, the PDF outline, or pages — recording each passage's section path. Every passage is read with a header naming the account, the document, the section and the date. For a long document, each applicable question retrieves its own first `PASSAGES_PER_QUESTION` passages by fusing, by reciprocal rank, a keyword ranking on its `hint_terms` (PostgreSQL full-text search in the `simple` configuration) with an embedding ranking; the document's selection is the union, capped at `MAX_PASSAGES_PER_DOCUMENT` so that every question keeps its best passage first. [Reclassification](/architecture/rules.md#reclassification) retrieves for the changed question over all stored passages. The label queue gains a stratum of passages the selection did not pick, and the quality check reports the share of them that hold a signal.

## Consequences

- A rare signal in a long report is read even when a frequent one dominates it, and a new question finds evidence in documents already stored.
- Names and acronyms in hint terms are found by keyword; hint terms decide which passages are read, still never an answer.
- Long documents cost up to `MAX_PASSAGES_PER_DOCUMENT` classifier calls instead of eight; short ones cost one.
- `chunk` gains `section` and a generated `lexemes` column with a GIN index; the store stays one PostgreSQL database ([ADR-01](/architecture/adrs/adr-01-one-postgresql-store.md)).
- Hint terms become quality-relevant: a vague term floods the keyword ranking, so the Admin checks them with question preview.
- The `missed_evidence` metric measures what selection still leaves unread, so the limits are tuned from labels, not guesses.

## Alternatives considered

- **One similarity ranking per service.** Replaced: it starves rare questions and hides evidence from new ones.
- **Classifying every passage of every document.** Rejected: a long report would cost hundreds of classifier calls per refresh.
- **A separate search engine for keyword retrieval.** Rejected: PostgreSQL full-text search covers it in the one store.
- **A generated summary of each document classified instead of its passages.** Rejected: a finding must quote its passage verbatim ([RULE-02](/requirements/business.md#business-rules)).
