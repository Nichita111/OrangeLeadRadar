"""The `FETCH` step ([Source plug-ins](/architecture/services/worker.md#source-plug-ins)): one
free-core plug-in fetches for its run's account, and each new item it returns is stored as a
normalised [`document`](/architecture/sql-store.md#document) with its un-embedded passages;
`PROCESS` embeds them. The network is used outside any transaction: the step reads its inputs
in one short transaction, fetches, then commits the plug-in's usage and errors whatever the
outcome, and only then writes its documents in the step's own transaction."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import any_, func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.sources import existing_source_kinds
from leadradar.ai.fixtures import FixtureMissing
from leadradar.core.chunking import split_into_passages
from leadradar.core.document_normalisation import normalise_item
from leadradar.core.enums import (
    AccountSourceKind,
    AccountSourceStatus,
    DocumentSourceType,
    JobStep,
    ServiceStatus,
    SignalQuestionStatus,
    SourcePluginCode,
)
from leadradar.core.fetch_window import fetch_window, news_queries_by_service, plugin_share
from leadradar.db.models.accounts import Account, AccountAlias, AccountSource
from leadradar.db.models.configuration import Service, SignalQuestion
from leadradar.db.models.ingestion import (
    Chunk,
    Document,
    Job,
    PipelineRun,
    PluginUsage,
    SourcePlugin,
)
from leadradar.plugins.base import SourcePluginAdapter
from leadradar.plugins.careers import CareersPlugin
from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.gdelt import GdeltPlugin
from leadradar.plugins.http import CrawlHttpClient, build_crawl_client
from leadradar.plugins.rss import RssPlugin
from leadradar.plugins.shapes import FetchAccount, FetchContext, FetchSource, RawItem
from leadradar.plugins.website import WebsitePlugin
from leadradar.runs.queries import SourcePluginView, get_source_plugin
from leadradar.worker.queue import add_run_progress
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import StepContext, StepFailed

_MS_PER_MINUTE = 60_000


@dataclass(frozen=True)
class _Inputs:
    plugin: SourcePluginView
    account: FetchAccount
    sources: list[FetchSource]
    hint_terms_by_service: dict[str, list[str]]
    newest_published_at: datetime | None
    fetch_job_count: int
    #: Every kind the account already has a source of ([Source detection]
    #: (/architecture/rules.md#source-detection) Invariants), and `SERPAPI`'s plug-in row and
    #: availability — the `WEBSITE` job's detection needs both; read here so detection makes no
    #: further query once the network has been used.
    existing_kinds: frozenset[AccountSourceKind]
    serpapi: SourcePluginView


async def _read_inputs(
    session: AsyncSession, context: StepContext, code: SourcePluginCode
) -> _Inputs | None:
    """The plug-in and the account's data the fetch needs; `None` when the plug-in is no
    longer available, so it makes no request ([Plug-in availability]
    (/architecture/rules.md#plug-in-availability))."""
    plugin = await get_source_plugin(
        session,
        code,
        keys_configured=context.settings.plugin_keys_configured(),
        now=context.now,
    )
    if not plugin.available:
        return None
    account_id = context.job.account_id
    account = await session.get(Account, account_id) if account_id is not None else None
    if account is None:
        raise StepFailed("INTERNAL", f"The run of job {context.job.id} has no account to fetch.")

    aliases = (
        await session.execute(
            select(AccountAlias.alias).where(AccountAlias.account_id == account.id)
        )
    ).scalars()
    run_created_at = (
        await session.execute(
            select(PipelineRun.created_at).where(PipelineRun.id == context.job.run_id)
        )
    ).scalar_one()
    sources = (
        await session.execute(
            select(AccountSource.kind, AccountSource.url).where(
                AccountSource.account_id == account.id,
                AccountSource.status == AccountSourceStatus.ACTIVE,
                # A source detected during a refresh is first read by the next one ([Source
                # detection](/architecture/rules.md#source-detection) Invariants, D1).
                AccountSource.created_at <= run_created_at,
            )
        )
    ).all()
    existing_kinds = await existing_source_kinds(session, account.id)
    serpapi = await get_source_plugin(
        session,
        SourcePluginCode.SERPAPI,
        keys_configured=context.settings.plugin_keys_configured(),
        now=context.now,
    )

    hint_terms_by_service: dict[str, list[str]] = {
        str(service_id): []
        for service_id in (
            await session.execute(select(Service.id).where(Service.status == ServiceStatus.ACTIVE))
        ).scalars()
    }
    questions = await session.execute(
        select(SignalQuestion.service_id, SignalQuestion.hint_terms).where(
            SignalQuestion.status == SignalQuestionStatus.ACTIVE,
            literal(DocumentSourceType.NEWS.value) == any_(SignalQuestion.source_types),
            SignalQuestion.service_id.in_(
                select(Service.id).where(Service.status == ServiceStatus.ACTIVE)
            ),
        )
    )
    for service_id, hint_terms in questions:
        terms = hint_terms_by_service[str(service_id)]
        terms.extend(term for term in hint_terms if term not in terms)

    newest_published_at = (
        await session.execute(
            select(func.max(Document.published_at)).where(
                Document.account_id == account.id, Document.plugin_code == code
            )
        )
    ).scalar_one()
    fetch_job_count = (
        await session.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.run_id == context.job.run_id, Job.step == JobStep.FETCH)
        )
    ).scalar_one()
    return _Inputs(
        plugin=plugin,
        account=FetchAccount(
            id=str(account.id),
            name=account.name,
            domain=account.domain,
            aliases=[alias for alias in aliases if alias != account.name],
            country_code=account.country_code,
            crunchbase_id=account.crunchbase_id,
        ),
        sources=[FetchSource(kind=kind, url=url) for kind, url in sources],
        hint_terms_by_service=hint_terms_by_service,
        newest_published_at=newest_published_at,
        fetch_job_count=fetch_job_count,
        existing_kinds=existing_kinds,
        serpapi=serpapi,
    )


def _adapter(code: SourcePluginCode, settings: WorkerSettings) -> SourcePluginAdapter:
    match code:
        case SourcePluginCode.GDELT:
            return GdeltPlugin(
                max_records=settings.gdelt_max_records,
                min_interval_s=settings.gdelt_min_interval_s,
                backoff_s=settings.gdelt_backoff_s,
            )
        case SourcePluginCode.RSS:
            return RssPlugin()
        case SourcePluginCode.WEBSITE:
            return WebsitePlugin(
                max_pages_per_site=settings.crawl_max_pages_per_site,
                max_pdfs=settings.crawl_max_pdfs,
            )
        case SourcePluginCode.CAREERS:
            return CareersPlugin(max_pages_per_site=settings.crawl_max_pages_per_site)
        case _:
            raise StepFailed("INTERNAL", f"No adapter for plug-in {code.value}")


def _fetch_context(context: StepContext, inputs: _Inputs) -> FetchContext:
    settings = context.settings
    window = fetch_window(
        now=context.now,
        lookback_days=settings.fetch_lookback_days,
        newest_published_at=inputs.newest_published_at,
    )
    queries = news_queries_by_service(
        name=inputs.account.name,
        aliases=inputs.account.aliases,
        hint_terms_by_service=inputs.hint_terms_by_service,
    )
    return FetchContext(
        account=inputs.account,
        sources=inputs.sources,
        since=window.since,
        until=window.until,
        queries=list(dict.fromkeys(queries.values())),
        max_items=plugin_share(settings.max_documents_per_refresh, inputs.fetch_job_count),
    )


async def _record_outcome(
    session: AsyncSession,
    *,
    code: SourcePluginCode,
    context: StepContext,
    client: CrawlHttpClient,
    error: str | None,
) -> None:
    """Counts every request the job made in today's `plugin_usage`, and sets the plug-in's
    `last_success_at` or `last_error`, in a transaction of its own that commits whether or not
    the step fails."""
    today = context.now.astimezone(UTC).date()
    if client.requests_made:
        upsert = insert(PluginUsage).values(
            plugin_code=code, day=today, requests=client.requests_made
        )
        await session.execute(
            upsert.on_conflict_do_update(
                index_elements=[PluginUsage.plugin_code, PluginUsage.day],
                set_={"requests": PluginUsage.requests + upsert.excluded.requests},
            )
        )
    plugin = (
        await session.execute(
            select(SourcePlugin).where(SourcePlugin.code == code).with_for_update()
        )
    ).scalar_one()
    if client.succeeded:
        plugin.last_success_at = context.now
    failure = error or client.last_failure
    if failure is not None:
        plugin.last_error = failure
        plugin.last_error_at = context.now


async def _store_items(context: StepContext, items: list[RawItem]) -> None:
    """Stores each new item as a `document` with its passages, and adds the run's counters.
    An item already stored for the account (same `content_hash`) adds nothing."""
    settings = context.settings
    session = context.session
    purge_after: date = (context.now + timedelta(days=settings.document_retention_days)).date()
    new_documents = 0
    passages = 0
    for item in items:
        normalised = await asyncio.to_thread(
            normalise_item,
            url=item.url,
            content_type=item.content_type,
            body=item.body,
            title=item.title,
            min_document_chars=settings.min_document_chars,
        )
        if normalised is None:
            continue
        document_id: uuid.UUID | None = (
            await session.execute(
                insert(Document)
                .values(
                    account_id=context.job.account_id,
                    run_id=context.job.run_id,
                    plugin_code=item.plugin_code,
                    source_type=item.source_type,
                    url=item.url,
                    canonical_url=normalised.canonical_url,
                    title=item.title,
                    language=normalised.language,
                    published_at=item.published_at,
                    fetched_at=context.now,
                    content_hash=normalised.content_hash,
                    text=normalised.text,
                    purge_after=purge_after,
                )
                .on_conflict_do_nothing()
                .returning(Document.id)
            )
        ).scalar_one_or_none()
        if document_id is None:
            continue
        new_documents += 1
        drafts = split_into_passages(
            normalised.text,
            normalised.sections,
            whole_document_max_chars=settings.whole_document_max_chars,
            chunk_target_chars=settings.chunk_target_chars,
            chunk_overlap_chars=settings.chunk_overlap_chars,
        )
        session.add_all(
            Chunk(
                document_id=document_id,
                ordinal=draft.ordinal,
                char_start=draft.char_start,
                char_end=draft.char_end,
                section=draft.section,
                text=draft.text,
                embedding=None,
            )
            for draft in drafts
        )
        passages += len(drafts)
    await session.flush()
    await add_run_progress(
        session,
        job_id=context.job.id,
        run_id=context.job.run_id,
        counts={
            "documents_fetched": len(items),
            "documents_new": new_documents,
            "passages": passages,
        },
    )


async def run_fetch_step(context: StepContext) -> None:
    """Runs the job's plug-in for its run's account; raises `StepFailed` when the plug-in's
    fetch fails, after its usage and error are committed."""
    sessions = context.sessions
    if sessions is None:
        raise RuntimeError("The FETCH step requires a session factory")
    code = SourcePluginCode(str(context.job.payload["plugin_code"]))

    async with sessions() as session, session.begin():
        inputs = await _read_inputs(session, context, code)
    if inputs is None:
        return

    adapter = _adapter(code, context.settings)
    settings = context.settings
    quota = inputs.plugin.daily_quota
    client = build_crawl_client(
        adapter=code.value,
        user_agent=settings.crawler_user_agent_or_default(),
        host_delay_ms=settings.crawl_host_delay_ms,
        min_interval_ms=_MS_PER_MINUTE // inputs.plugin.rate_limit_per_minute,
        requests_allowed=None if quota is None else max(0, quota - inputs.plugin.requests_today),
        timeout_s=settings.http_timeout_s,
        # Pacing measures real elapsed time, whatever the application clock says.
        clock=lambda: datetime.now(tz=UTC),
        fixture_mode=settings.fixture_mode,
        fixture_dir=settings.fixture_dir,
    )
    error: str | None = None
    items: list[RawItem] = []
    home_page: tuple[str, str] | None = None
    try:
        if isinstance(adapter, WebsitePlugin):
            crawl = await adapter.crawl(_fetch_context(context, inputs), client)
            items = crawl.items
            home_page = crawl.home_page
        else:
            items = await adapter.fetch(_fetch_context(context, inputs), client)
    except PluginFetchFailed as failure:
        error = str(failure)
        raise StepFailed("UPSTREAM_UNAVAILABLE", error) from failure
    except FixtureMissing as failure:
        error = str(failure)
        raise StepFailed("FIXTURE_MISSING", error) from failure
    finally:
        try:
            async with sessions() as session, session.begin():
                await _record_outcome(
                    session, code=code, context=context, client=client, error=error
                )
        finally:
            await client.aclose()

    await _store_items(context, items)

    if code is SourcePluginCode.WEBSITE:
        # Deferred import: `detection` reuses this module's `_record_outcome`, which would
        # otherwise be a circular import at module load time.
        from leadradar.worker.steps.detection import run_website_detection

        await run_website_detection(context, inputs=inputs, home_page=home_page)
