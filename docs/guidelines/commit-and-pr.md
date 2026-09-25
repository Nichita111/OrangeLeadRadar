---
type: Guideline
title: Commits and pull requests
description: Commit format, branch naming, what a pull request must state, how specification changes travel, and the review order of the agent chain.
status: draft
tags: []
---

# Commits and pull requests

## Commits

Conventional Commits. The scope is the feature slug the change serves — the slug in the `tags` of the documents it touches — or a non-feature area such as `tooling` or `docs`:

```text
feat(signal-pipeline): escalate answers inside the escalation band
fix(prospect-dashboard): keep disqualified accounts out of the ranking
docs(service-configuration): state the validation of disqualifier operands
test(evaluation-and-feedback): cover AC-48 label queue strata
chore(tooling): check flows named by no requirement
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`. The subject says what changed in the system. The body says why and names the identifiers the change serves (`S-SIG-03`, `AC-22`). A change to a table, rule, contract or screen carries its document change in the same commit; a change to a requirements register is a commit of its own. Don't add the ai agent as co-author.

## Branches

```text
<type>/<feature-slug>-<short-slug>
feat/signal-pipeline-escalation
```

## Pull requests

A pull request states:

- the requirement rows it implements and the `AC-` rows that verify them, taken from the [traceability matrix](/requirements/traceability.md);
- the Architect's design, or a link to it;
- the document changes and the `log.md` line;
- the test levels added and how to run them;
- anything left for a later task, as a tracker item, never as a comment in code or documents.

## Review order

The chain of `AGENTS.md` reviews in this order: the QA agent's acceptance and end-to-end results, then the Critic's review, then a human. A red gate or an unresolved Critic finding blocks the merge.

## Spec changes in a pull request

A document change is **approved** before the code that depends on it and **committed** with that code, as [R7](/guidelines/documents/common.md#the-eight-rules) states. When implementation shows the specification is wrong or incomplete, the owning heading is changed following R7 and a human approves the change before any code relies on it — the docs phase of `/implement`. Only a change to a requirements register (`business.md`, `system.md`, `acceptance.md`, `glossary.md`) is committed on its own, before the rest of the change.
