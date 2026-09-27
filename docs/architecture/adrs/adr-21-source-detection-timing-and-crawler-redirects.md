---
type: Decision
title: ADR-21 Source detection timing and crawler redirects
description: A source a refresh detects is read starting the next refresh, not its own, and the WEBSITE crawler follows same-registrable-domain redirects as paced, robots-checked, recorded requests, so a redirecting home page is read at all.
status: draft
tags: [signal-pipeline]
---

# ADR-21 Source detection timing and crawler redirects

## Context

[Source detection](/architecture/rules.md#source-detection) reads the account's home page during the `WEBSITE` `FETCH` job and writes `DETECTED` `account_source` rows for the kinds still missing. The `WEBSITE` source is created as `https://{domain}/`, and most sites answer that address with an HTTP redirect to a canonical host such as `https://www.{domain}/`. The crawler did not follow redirects, so a redirecting home page yielded no item and no detection, which `AC-19` cannot pass without. Following a redirect inside `httpx` would bypass robots checking, pacing, request counting and the `linkedin.com` block that `CrawlHttpClient` enforces on every other request, so a redirect has to be its own recorded hop through the same client. Separately, a source a refresh's own `FETCH` job detects could, without a rule, be read by that same run's `CAREERS` or `INVESTOR_RELATIONS` job later in the same `FETCH` stage, making the run's own document set depend on job ordering within the run.

## Decision

- **Detection timing (G1).** `FetchContext.sources` carries the account's `ACTIVE` `account_source` rows created before the run itself, not before the job. A source a refresh detects is first read by the next refresh.
- **Redirects (G8, G10).** The `WEBSITE` crawler follows a redirect (301, 302, 303, 307 or 308) whose target is on the account's registrable domain, as a new paced, robots-checked, recorded `client.get` of the target, unless that target has already been requested in the job. Each hop counts as one of the source's pages against `CRAWL_MAX_PAGES_PER_SITE`, or one of the job's `CRAWL_MAX_PDFS`; no new configuration key bounds the chain. A redirect to another registrable domain is never followed. A source whose own URL redirects crawls the same-host links of the host it leads to.
- **document.url (G9).** A redirected page's `document.url` stays the address requested, not the address it led to; the final address is kept only in the fixture's `location` field of that hop. The page's own canonical address still reaches `canonical_url` through its declared canonical link.

## Consequences

- A run's own detections never change what that same run itself fetches; the job order within `FETCH` no longer matters for source completeness.
- The `WEBSITE` `https://{domain}/` source is read even when the site's canonical host differs, closing the gap `AC-19` exposed.
- The fixture format gains the redirect's `Location` header as `location` on a `3xx` record, so a recorded redirect chain replays identically.
- Only the `WEBSITE` crawler follows redirects; `CAREERS`, `RSS` and `GDELT` still read exactly the address given them.

## Alternatives considered

- **Let `httpx` follow redirects for the `WEBSITE` client.** Rejected: it would bypass robots checking, pacing, per-request counting and the `linkedin.com` block that every other request goes through.
- **A source detected mid-refresh is read later in the same run.** Rejected: it makes the document set depend on the job queue's order within one `FETCH` stage rather than on the data.
- **A configuration key bounding the number of redirect hops.** Rejected: the existing page and PDF budgets already bound every hop; a second limit would duplicate them.
- **Store the redirect chain on `document`.** Rejected: no requirement reads it, and the fixture file already holds each hop for replay.
