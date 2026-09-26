---
type: Decision
title: ADR-18 Industries and markets as configuration
description: Industries and markets are lists an Admin maintains without code; a market is a shortcut stored as its countries, so scores stay reproducible.
status: draft
tags: [service-configuration]
---

# ADR-18 Industries and markets as configuration

## Context

The brief asks that Orange Systems users configure the ideal customer profile "by market, industry, company size, geography", and judges the ability to scale to new markets, industries and verticals. `N-11` requires that adding a market or an industry needs configuration only. Industry was a fixed enumeration of the store, so a new vertical needed a migration, and the markets of the ICP editor were fixed shortcuts in a screen.

## Decision

[`industry`](/architecture/sql-store.md#industry) and [`market`](/architecture/sql-store.md#market) are tables an Admin maintains through `API-71` to `API-76`: add, rename, retire and restore, never delete. An account's industry and an `INDUSTRY` criterion name an industry code, and only an active industry can be newly set or named by a saved draft. A market is a named group of countries used as a shortcut: choosing it in a `GEOGRAPHY` criterion stores its countries in the scoring settings, so the scoring rules keep matching on country codes. The first rows are seeded from the [demo dataset](/architecture/overview.md#demo-dataset).

## Consequences

- A new vertical or market is a few clicks, with no migration and no restart ([RULE-04](/requirements/business.md#business-rules)).
- Scores stay reproducible ([RULE-05](/requirements/business.md#business-rules)): a scoring version holds industry codes and country codes, and a later change to a market never changes a saved version; a retired industry keeps matching in the versions that name it.
- The Crunchbase category mapping targets the seeded codes, and yields no industry when its target is retired.

## Alternatives considered

- **Keep the enumeration and migrate for each new industry.** Rejected: contradicts `N-11` and the brief's configurability.
- **Markets as a criterion kind scored at run time.** Rejected: editing a market would silently change every score that uses it without a new scoring version.
