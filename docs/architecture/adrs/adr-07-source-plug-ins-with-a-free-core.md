---
type: Decision
title: ADR-07 Source plug-ins with a free core
description: Sources are seven plug-ins behind one port; four need no key and suffice alone, three are optional keyed ones, and LinkedIn is never read.
status: draft
tags: [accounts-and-discovery, signal-pipeline]
---

# ADR-07 Source plug-ins with a free core

## Context

The brief lists Crunchbase, company websites and reports, news APIs and GDELT, career pages and job boards, and LinkedIn only for manual validation: the solution must not depend on LinkedIn scraping or API access. Paid keys may or may not be obtained in time.

## Decision

Seven [source plug-ins](/architecture/services/worker.md#source-plug-ins) implement the [Source plug-ins](/architecture/interfaces.md#source-plug-ins) port: `GDELT`, `RSS`, `WEBSITE` and `CAREERS` form the free core; `CRUNCHBASE`, `NEWSAPI` and `SERPAPI` are available only with their keys. Every P0 capability works on the free core. LinkedIn addresses are stored for people to open and are never fetched. The crawler obeys `robots.txt`, identifies itself and paces requests.

## Consequences

- The demo and the tests never depend on a paid key; each key that arrives improves coverage.
- Each plug-in has its own switch, rate limit and quota, visible to Admins.
- Without Crunchbase, discovery relies on news mentions and attributes are entered or classified.

## Alternatives considered

- **LinkedIn scraping or API.** Rejected by the brief and the platform's terms.
- **A single paid search API for everything.** Rejected: a hard dependency on one key.
