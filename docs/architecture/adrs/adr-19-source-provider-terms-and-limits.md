---
type: Decision
title: ADR-19 Source provider terms and limits
description: What each news and company-data provider allows - GDELT free with credit and strict pacing, Google News only through SerpAPI, Crunchbase not expected, LinkedIn never - and how the plug-ins follow it.
status: draft
tags: [signal-pipeline]
---

# ADR-19 Source provider terms and limits

## Context

The team's provider analysis of September 2026 established what each source in the brief allows. GDELT's DOC 2.0 API is free with no key and allows commercial use when the GDELT Project is credited; it searches a rolling three months, returns at most 250 articles per request and metadata only, and enforces about one request every five seconds, blocking for about a minute after a `429`. Google News has had no official API since 2016; its RSS feeds are limited to personal, non-commercial use, and paid search APIs such as SerpAPI return its results under their own terms. Crunchbase's API needs a paid enterprise licence, estimated at USD 50,000 a year, and its free tier is no longer offered to new users. LinkedIn's official APIs need partner approval beyond sign-in and sharing, and third-party professional-network data such as CoreSignal is not LinkedIn's.

## Decision

- `GDELT` stays in the free core, paced by `GDELT_MIN_INTERVAL_S`, paused for `GDELT_BACKOFF_S` after a `429`, asking `GDELT_MAX_RECORDS` per request, with every document it found credited to the GDELT Project on Account detail. Article text is fetched from the article's own page.
- Google News is read only through the optional `SERPAPI` plug-in; no feed on `news.google.com` is read or accepted as a source.
- No Crunchbase key is expected. Account attributes come from users, the demo account file and the classifier; the `CRUNCHBASE` plug-in stays available for a key, and only P1 capabilities use it.
- LinkedIn is never read ([RULE-01](/requirements/business.md#business-rules)), and professional-network data from third parties is not used.

## Consequences

- Every P0 capability runs on the free core without a licence ([ADR-07](/architecture/adrs/adr-07-source-plug-ins-with-a-free-core.md)).
- News older than three months comes only from the companies' own publications.
- A GDELT refresh of many accounts is slow by design; the scheduler spreads accounts over the refresh interval.

## Alternatives considered

- **Google News RSS as a free news source.** Rejected: its terms forbid commercial use.
- **Buying Crunchbase for the hackathon.** Rejected: cost far beyond the product's budget for data the demo account file and the classifier provide.
- **A browser-like user agent to get past GDELT throttling.** Rejected: the crawler identifies itself ([N-09](/requirements/system.md)).
