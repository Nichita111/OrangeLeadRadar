"""[Source detection](/architecture/rules.md#source-detection) (`S-ING-05`): called from
`run_fetch_step` when the job's plug-in is `WEBSITE`, once its crawl and its documents are
stored. Home-page detection is pure and needs no network; the `SERPAPI` half of the algorithm
makes its own request, outside the `WEBSITE` job's transaction, exactly as `run_fetch_step` does
for its own plug-in — its usage and outcome are recorded with the same `_record_outcome`, and a
failed search adds a run error without failing the `WEBSITE` job (G6)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from leadradar.accounts.sources import write_detected_sources
from leadradar.core.enums import AccountSourceKind, SourcePluginCode
from leadradar.core.source_detection import (
    DetectedSource,
    detect_home_page_sources,
    first_result_on_domain,
    search_query,
)
from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.http import build_crawl_client
from leadradar.plugins.serpapi import SerpapiWebSearch
from leadradar.plugins.shapes import FetchAccount
from leadradar.plugins.website import home_page_candidates
from leadradar.runs.queries import SourcePluginView
from leadradar.worker.queue import add_run_error
from leadradar.worker.steps import StepContext
from leadradar.worker.steps.fetch import _MS_PER_MINUTE, _Inputs, _record_outcome

#: [Source detection](/architecture/rules.md#source-detection) Algorithm: the only kinds a
#: `SERPAPI` search may fill.
_SEARCHABLE_KINDS = (AccountSourceKind.CAREERS, AccountSourceKind.INVESTOR_RELATIONS)


async def _search_missing(
    context: StepContext,
    *,
    account: FetchAccount,
    domain: str,
    missing: list[AccountSourceKind],
    serpapi: SourcePluginView,
) -> list[DetectedSource]:
    """One `SERPAPI` web search per kind of `missing`, through a client built like the `WEBSITE`
    job's own, keeping the first result on the account's domain; a failed search adds a run
    error and detection keeps what it already has (G6)."""
    sessions = context.sessions
    if sessions is None:
        raise RuntimeError("Source detection's SERPAPI search requires a session factory")
    settings = context.settings
    quota = serpapi.daily_quota
    client = build_crawl_client(
        adapter=SourcePluginCode.SERPAPI.value,
        user_agent=settings.crawler_user_agent_or_default(),
        host_delay_ms=settings.crawl_host_delay_ms,
        min_interval_ms=_MS_PER_MINUTE // serpapi.rate_limit_per_minute,
        requests_allowed=None if quota is None else max(0, quota - serpapi.requests_today),
        timeout_s=settings.http_timeout_s,
        clock=lambda: datetime.now(tz=UTC),
        fixture_mode=settings.fixture_mode,
        fixture_dir=settings.fixture_dir,
    )
    assert settings.serpapi_key is not None  # SERPAPI is available only when its key is set
    search = SerpapiWebSearch(api_key=settings.serpapi_key.get_secret_value())
    detected: list[DetectedSource] = []
    try:
        for kind in missing:
            try:
                results = await search.search(search_query(kind, account.name), client)
            except PluginFetchFailed as failure:
                await _record_search_error(context, str(failure))
                continue
            url = first_result_on_domain(results, domain)
            if url is not None:
                detected.append(DetectedSource(kind=kind, url=url))
    finally:
        try:
            async with sessions() as session, session.begin():
                await _record_outcome(
                    session,
                    code=SourcePluginCode.SERPAPI,
                    context=context,
                    client=client,
                    error=None,
                )
        finally:
            await client.aclose()
    return detected


async def _record_search_error(context: StepContext, message: str) -> None:
    sessions = context.sessions
    assert sessions is not None
    async with sessions() as session, session.begin():
        await add_run_error(
            session,
            job_id=context.job.id,
            run_id=context.job.run_id,
            error={
                "stage": "FETCH",
                "plugin_code": SourcePluginCode.SERPAPI.value,
                "code": "UPSTREAM_UNAVAILABLE",
                "message": message,
            },
        )


async def run_website_detection(
    context: StepContext, *, inputs: _Inputs, home_page: tuple[str, str] | None
) -> None:
    """The `WEBSITE` job's [Source detection](/architecture/rules.md#source-detection): the
    home page's links and feed, then a `SERPAPI` search for whichever of `CAREERS` and
    `INVESTOR_RELATIONS` is still missing, then the write, in the step's own transaction."""
    domain = inputs.account.domain
    home_detected: list[DetectedSource] = []
    if home_page is not None:
        final_url, body = home_page
        links, feed_urls = home_page_candidates(body, final_url)
        home_detected = detect_home_page_sources(
            links=links, feed_urls=feed_urls, domain=domain, existing_kinds=inputs.existing_kinds
        )

    searched_detected: list[DetectedSource] = []
    if inputs.serpapi.available:
        already = inputs.existing_kinds | {source.kind for source in home_detected}
        missing = [kind for kind in _SEARCHABLE_KINDS if kind not in already]
        if missing:
            searched_detected = await _search_missing(
                context,
                account=inputs.account,
                domain=domain,
                missing=missing,
                serpapi=inputs.serpapi,
            )

    detected = home_detected + searched_detected
    if detected:
        await write_detected_sources(
            context.session,
            uuid.UUID(inputs.account.id),
            detected,
            run_id=context.job.run_id,
            occurred_at=context.now,
        )
