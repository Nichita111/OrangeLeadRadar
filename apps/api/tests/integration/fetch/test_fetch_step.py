"""Integration tests of the `FETCH` step against a real database
([Source plug-ins](/architecture/services/worker.md#source-plug-ins), [Fetch window]
(/architecture/rules.md#fetch-window), [Plug-in availability]
(/architecture/rules.md#plug-in-availability); `S-ING-01`, `S-ING-02`, `S-PIP-03`, `N-05`).

The provider's side is an `httpx.MockTransport` behind the real crawl client, so a test sees
every request the step sends. Every test runs in one outer transaction rolled back at the end;
the step's own transactions are savepoints inside it."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from leadradar.core.enums import (
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    DocumentSourceType,
    JobStatus,
    JobStep,
    PipelineRunStatus,
    ServiceStatus,
    SignalQuestionStatus,
    SourcePluginCode,
)
from leadradar.db.models.accounts import AccountAlias, AccountSource
from leadradar.db.models.ingestion import (
    Chunk,
    Document,
    Job,
    PipelineRun,
    PluginUsage,
    SourcePlugin,
)
from leadradar.worker.loop import process_next_job
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import STEP_HANDLERS, StepContext, StepHandler
from tests.integration import factories as f
from tests.integration.pipeline_doubles import (
    GDELT_SEARCH,
    T0,
    Clock,
    Web,
    feed,
    gdelt_articles,
    html,
    install_web,
    session_factory,
)

pytestmark = pytest.mark.integration

FREE_PLUGINS = (
    SourcePluginCode.GDELT,
    SourcePluginCode.RSS,
    SourcePluginCode.WEBSITE,
    SourcePluginCode.CAREERS,
)


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> Web:
    return install_web(monkeypatch)


def settings(**overrides: Any) -> WorkerSettings:
    values: dict[str, Any] = {
        "database_url": SecretStr("postgresql://unused"),
        "crawler_user_agent": "LeadRadar-test/1.0",
        "job_max_attempts": 1,
        "job_retry_backoff_s": 1,
    }
    values.update(overrides)
    return WorkerSettings(**values)


@pytest.fixture
async def connection(async_connection: AsyncConnection) -> AsyncIterator[AsyncConnection]:
    await async_connection.execute(
        update(Job)
        .where(Job.status.in_((JobStatus.READY, JobStatus.RUNNING)))
        .values(status=JobStatus.CANCELLED)
    )
    await async_connection.execute(delete(SourcePlugin))
    yield async_connection


async def _succeed(context: StepContext) -> None:
    return None


async def drain(
    connection: AsyncConnection, worker_settings: WorkerSettings, clock: Clock | None = None
) -> None:
    """Runs every job that becomes due; `PROCESS` and `SCORE` are stubs (T10 PR 2, T11 PR 3)."""
    handlers: dict[JobStep, StepHandler] = {
        JobStep.FETCH: STEP_HANDLERS[JobStep.FETCH],
        JobStep.PROCESS: _succeed,
        JobStep.SCORE: _succeed,
    }
    clock = clock or Clock()
    for _ in range(6):
        while await process_next_job(
            session_factory(connection),
            handlers=handlers,
            settings=worker_settings,
            clock=clock,
            worker_id="worker-1",
        ):
            pass
        clock.now += timedelta(hours=1)


class Scene:
    def __init__(self, account_id: uuid.UUID, run_id: uuid.UUID) -> None:
        self.account_id = account_id
        self.run_id = run_id


async def scene(
    connection: AsyncConnection,
    *,
    fetch: Sequence[SourcePluginCode] = FREE_PLUGINS,
    plugins: dict[SourcePluginCode, dict[str, Any]] | None = None,
    sources: Sequence[tuple[AccountSourceKind, str]] = (),
    aliases: Sequence[str] = ("Acme Corp", "Acme"),
) -> Scene:
    """An account `Acme Corp`, its run, one `FETCH` job per `fetch` code, and a `source_plugin`
    row for every code (`plugins` overrides its columns)."""

    def build(conn: Connection) -> Scene:
        for code in SourcePluginCode:
            f.make_source_plugin(conn, code=code, **((plugins or {}).get(code) or {}))
        account_id = f.make_account(conn, name="Acme Corp", domain="acme-test.com")
        conn.execute(
            insert(AccountAlias),
            [{"account_id": account_id, "alias": a, "normalised": a.lower()} for a in aliases],
        )
        for kind, url in sources:
            conn.execute(
                insert(AccountSource).values(
                    account_id=account_id,
                    kind=kind,
                    url=url,
                    origin=AccountSourceOrigin.MANUAL,
                    status=AccountSourceStatus.ACTIVE,
                )
            )
        run_id = f.make_pipeline_run(conn, account_id=account_id)
        for code in fetch:
            f.make_job(
                conn,
                run_id,
                step=JobStep.FETCH,
                payload={"plugin_code": code.value},
                not_before=T0,
            )
        return Scene(account_id, run_id)

    return await connection.run_sync(build)


async def documents(connection: AsyncConnection, scene_: Scene) -> list[Any]:
    rows = await connection.execute(
        select(Document).where(Document.account_id == scene_.account_id).order_by(Document.url)
    )
    return list(rows.all())


async def usage(connection: AsyncConnection, code: SourcePluginCode) -> int:
    requests = (
        await connection.execute(
            select(PluginUsage.requests).where(
                PluginUsage.plugin_code == code, PluginUsage.day == T0.date()
            )
        )
    ).scalar_one_or_none()
    return int(requests or 0)


async def run_row(connection: AsyncConnection, run_id: uuid.UUID) -> Any:
    return (await connection.execute(select(PipelineRun).where(PipelineRun.id == run_id))).one()


async def plugin_row(connection: AsyncConnection, code: SourcePluginCode) -> Any:
    return (await connection.execute(select(SourcePlugin).where(SourcePlugin.code == code))).one()


async def chunks_of(connection: AsyncConnection, document_id: uuid.UUID) -> list[Any]:
    rows = await connection.execute(
        select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal)
    )
    return list(rows.all())


# --- one plug-in each: documents, passages, counters, usage ----------------------------------


async def test_gdelt_stores_its_articles_as_documents_with_passages_and_counts_its_requests(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(
        GDELT_SEARCH,
        gdelt_articles(["https://news.example.org/a1", "https://news.example.org/a2"]),
        kind="json",
    )
    web.add("https://news.example.org/a1", html("First story"))
    web.add("https://news.example.org/a2", html("Second story"))
    scene_ = await scene(connection, fetch=[SourcePluginCode.GDELT])

    await drain(connection, settings())

    stored = await documents(connection, scene_)
    assert [(d.plugin_code, d.source_type, d.title) for d in stored] == [
        (SourcePluginCode.GDELT, DocumentSourceType.NEWS, "Article 0"),
        (SourcePluginCode.GDELT, DocumentSourceType.NEWS, "Article 1"),
    ]
    assert {d.run_id for d in stored} == {scene_.run_id}
    assert {d.purge_after for d in stored} == {(T0 + timedelta(days=730)).date()}
    assert {d.language for d in stored} == {"en"}
    for document in stored:
        passages = await chunks_of(connection, document.id)
        assert len(passages) == 1
        assert passages[0].embedding is None
    run = await run_row(connection, scene_.run_id)
    assert run.progress["documents_fetched"] == 2
    assert run.progress["documents_new"] == 2
    assert run.progress["passages"] == 2
    assert (
        await usage(connection, SourcePluginCode.GDELT) == len(web.requests) == 5
    )  # two robots.txt, the search, two articles
    assert (await plugin_row(connection, SourcePluginCode.GDELT)).last_success_at == T0


async def test_rss_stores_its_feed_entries(connection: AsyncConnection, web: Web) -> None:
    web.add(
        "https://acme-test.com/feed.xml",
        feed([("https://acme-test.com/news/one", html("Own news one"))]),
        kind="xml",
    )
    scene_ = await scene(
        connection,
        fetch=[SourcePluginCode.RSS],
        sources=[(AccountSourceKind.RSS_FEED, "https://acme-test.com/feed.xml")],
    )

    await drain(connection, settings())

    [document] = await documents(connection, scene_)
    assert (document.plugin_code, document.source_type) == (
        SourcePluginCode.RSS,
        DocumentSourceType.COMPANY_PUBLICATION,
    )
    assert len(await chunks_of(connection, document.id)) == 1
    assert await usage(connection, SourcePluginCode.RSS) == 2  # robots.txt and the feed


async def test_website_stores_the_pages_it_crawls(connection: AsyncConnection, web: Web) -> None:
    web.add("https://acme-test.com/news/one", html("Newsroom item"))
    web.add("https://acme-test.com/news", html("Newsroom", ["/news/one"]))
    scene_ = await scene(
        connection,
        fetch=[SourcePluginCode.WEBSITE],
        sources=[(AccountSourceKind.NEWSROOM, "https://acme-test.com/news")],
    )

    await drain(connection, settings())

    stored = await documents(connection, scene_)
    assert len(stored) == 2
    assert {d.plugin_code for d in stored} == {SourcePluginCode.WEBSITE}
    assert {d.source_type for d in stored} == {DocumentSourceType.COMPANY_PUBLICATION}
    assert await usage(connection, SourcePluginCode.WEBSITE) == 3  # robots.txt and two pages


async def test_careers_stores_its_postings(connection: AsyncConnection, web: Web) -> None:
    posting = " ".join(["Runs the hub, its shifts and the yard team."] * 8)
    web.add(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
        {
            "jobs": [
                {
                    "title": "Hub manager",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    "updated_at": "2026-09-20T10:00:00Z",
                    "location": {"name": "Berlin"},
                    "content": f"<p>{posting}</p>",
                }
            ]
        },
        kind="json",
    )
    scene_ = await scene(
        connection,
        fetch=[SourcePluginCode.CAREERS],
        sources=[(AccountSourceKind.CAREERS, "https://boards.greenhouse.io/acme")],
    )

    await drain(connection, settings())

    [document] = await documents(connection, scene_)
    assert (document.plugin_code, document.source_type, document.title) == (
        SourcePluginCode.CAREERS,
        DocumentSourceType.JOB_POSTING,
        "Hub manager",
    )


#: A PNG's first bytes: NUL bytes that PostgreSQL text refuses, so storing one as text fails.
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01" * 20


async def test_website_skips_a_linked_page_that_is_not_html(
    connection: AsyncConnection, web: Web
) -> None:
    web.add("https://acme-test.com/news/logo", PNG, kind="png")
    web.add("https://acme-test.com/news/one", html("Newsroom item"))
    web.add("https://acme-test.com/news", html("Newsroom", ["/news/logo", "/news/one"]))
    scene_ = await scene(
        connection,
        fetch=[SourcePluginCode.WEBSITE],
        sources=[(AccountSourceKind.NEWSROOM, "https://acme-test.com/news")],
    )

    await drain(connection, settings())

    stored = await documents(connection, scene_)
    assert sorted(d.url for d in stored) == [
        "https://acme-test.com/news",
        "https://acme-test.com/news/one",
    ]


async def test_careers_skips_a_crawled_posting_that_is_not_html(
    connection: AsyncConnection, web: Web
) -> None:
    web.add("https://jobs.acme-test.com/share", PNG, kind="png")
    web.add("https://jobs.acme-test.com/job/1", html("Hub manager"))
    web.add("https://jobs.acme-test.com/", html("Careers", ["/share", "/job/1"]))
    scene_ = await scene(
        connection,
        fetch=[SourcePluginCode.CAREERS],
        sources=[(AccountSourceKind.CAREERS, "https://jobs.acme-test.com/")],
    )

    await drain(connection, settings())

    [document] = await documents(connection, scene_)
    assert (document.url, document.source_type) == (
        "https://jobs.acme-test.com/job/1",
        DocumentSourceType.JOB_POSTING,
    )


async def test_gdelt_skips_an_article_that_is_not_html(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(
        GDELT_SEARCH,
        gdelt_articles(["https://news.example.org/photo", "https://news.example.org/a1"]),
        kind="json",
    )
    web.add("https://news.example.org/photo", PNG, kind="png")
    web.add("https://news.example.org/a1", html("First story"))
    scene_ = await scene(connection, fetch=[SourcePluginCode.GDELT])

    await drain(connection, settings())

    [document] = await documents(connection, scene_)
    assert document.url == "https://news.example.org/a1"


# --- idempotency and deduplication ------------------------------------------------------------


async def test_running_the_fetch_again_stores_nothing_new_and_counts_its_requests_again(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(GDELT_SEARCH, gdelt_articles(["https://news.example.org/a1"]), kind="json")
    web.add("https://news.example.org/a1", html("First story"))
    scene_ = await scene(connection, fetch=[SourcePluginCode.GDELT])
    await drain(connection, settings())
    [first] = await documents(connection, scene_)
    await connection.execute(
        update(PipelineRun)
        .where(PipelineRun.id == scene_.run_id)
        .values(status=PipelineRunStatus.SUCCEEDED)
    )

    def again(conn: Connection) -> uuid.UUID:
        run_id = f.make_pipeline_run(conn, account_id=scene_.account_id)
        f.make_job(
            conn, run_id, step=JobStep.FETCH, payload={"plugin_code": "GDELT"}, not_before=T0
        )
        return run_id

    second_run = await connection.run_sync(again)
    await drain(connection, settings())

    [only] = await documents(connection, scene_)
    assert only.id == first.id
    assert len(await chunks_of(connection, only.id)) == 1
    progress = (await run_row(connection, second_run)).progress
    assert (progress["documents_fetched"], progress["documents_new"], progress["passages"]) == (
        1,
        0,
        0,
    )
    assert await usage(connection, SourcePluginCode.GDELT) == 8


async def test_the_same_article_from_rss_and_gdelt_in_one_run_is_stored_once(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(GDELT_SEARCH, gdelt_articles(["https://news.example.org/story"]), kind="json")
    web.add("https://news.example.org/story", html("Shared story"))
    web.add(
        "https://news.example.org/feed.xml",
        feed([("https://news.example.org/story", None)]),
        kind="xml",
    )
    scene_ = await scene(
        connection,
        fetch=[SourcePluginCode.GDELT, SourcePluginCode.RSS],
        sources=[(AccountSourceKind.RSS_FEED, "https://news.example.org/feed.xml")],
    )

    await drain(connection, settings())

    assert len(await documents(connection, scene_)) == 1


# --- the fetch window, queries and shares -----------------------------------------------------


def _since(web: Web) -> datetime:
    [search] = web.searches()
    return datetime.strptime(search["startdatetime"][0], "%Y%m%d%H%M%S").replace(tzinfo=UTC)


async def test_the_gdelt_window_starts_one_day_before_the_newest_gdelt_document(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(GDELT_SEARCH, {"articles": []}, kind="json")
    scene_ = await scene(connection, fetch=[SourcePluginCode.GDELT])
    newest = T0 - timedelta(days=10)
    await connection.run_sync(
        lambda conn: f.make_document(
            conn,
            scene_.run_id,
            account_id=scene_.account_id,
            plugin_code=SourcePluginCode.GDELT,
            published_at=newest,
        )
    )

    await drain(connection, settings())

    assert _since(web) == newest - timedelta(days=1)


async def test_the_gdelt_window_defaults_to_the_lookback_period(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(GDELT_SEARCH, {"articles": []}, kind="json")
    await scene(connection, fetch=[SourcePluginCode.GDELT])

    await drain(connection, settings(fetch_lookback_days=30))

    assert _since(web) == T0 - timedelta(days=30)


async def test_gdelt_sends_one_query_per_active_service_with_its_news_hint_terms(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(GDELT_SEARCH, {"articles": []}, kind="json")
    await scene(connection, fetch=[SourcePluginCode.GDELT])

    def services(conn: Connection) -> None:
        with_terms = f.make_service(conn)
        f.make_signal_question(conn, with_terms, hint_terms=["strike"])
        without_terms = f.make_service(conn)
        f.make_signal_question(
            conn, without_terms, source_types=["COMPANY_PUBLICATION"], hint_terms=["ignored"]
        )
        inactive = f.make_service(conn, status=ServiceStatus.INACTIVE)
        f.make_signal_question(conn, inactive, hint_terms=["inactive"])
        f.make_signal_question(
            conn, with_terms, status=SignalQuestionStatus.INACTIVE, hint_terms=["inactive question"]
        )

    await connection.run_sync(services)

    await drain(connection, settings())

    queries = {search["query"][0] for search in web.searches()}
    assert queries == {'("Acme Corp" OR "Acme") ("strike")', '"Acme Corp" OR "Acme"'}


async def test_with_four_fetch_jobs_no_plugin_stores_more_than_its_share(
    connection: AsyncConnection, web: Web
) -> None:
    urls = [f"https://news.example.org/n{index}" for index in range(5)]
    web.add(GDELT_SEARCH, gdelt_articles(urls), kind="json")
    for index, url in enumerate(urls):
        web.add(url, html(f"News {index}"))
    web.add(
        "https://acme-test.com/feed.xml",
        feed([(f"https://acme-test.com/r{index}", html(f"Feed {index}")) for index in range(5)]),
        kind="xml",
    )
    web.add("https://acme-test.com/site", html("Site", [f"/s{index}" for index in range(5)]))
    for index in range(5):
        web.add(f"https://acme-test.com/s{index}", html(f"Site page {index}"))
    web.add(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
        {
            "jobs": [
                {
                    "title": f"Job {index}",
                    "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{index}",
                    "updated_at": "2026-09-20T10:00:00Z",
                    "content": f"<p>{html(f'Posting {index}')}</p>",
                }
                for index in range(5)
            ]
        },
        kind="json",
    )
    scene_ = await scene(
        connection,
        sources=[
            (AccountSourceKind.RSS_FEED, "https://acme-test.com/feed.xml"),
            (AccountSourceKind.WEBSITE, "https://acme-test.com/site"),
            (AccountSourceKind.CAREERS, "https://boards.greenhouse.io/acme"),
        ],
    )

    await drain(connection, settings(max_documents_per_refresh=8))

    stored = await documents(connection, scene_)
    per_plugin = {code: sum(d.plugin_code == code for d in stored) for code in FREE_PLUGINS}
    assert per_plugin == dict.fromkeys(FREE_PLUGINS, 2)


# --- failure, availability and quota ----------------------------------------------------------


async def test_a_failing_plugin_keeps_its_usage_and_error_and_the_others_documents(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(GDELT_SEARCH, "unavailable", status=503, kind="json")
    web.add(
        "https://acme-test.com/feed.xml",
        feed([("https://acme-test.com/news/one", html("Own news one"))]),
        kind="xml",
    )
    scene_ = await scene(
        connection,
        fetch=[SourcePluginCode.GDELT, SourcePluginCode.RSS],
        sources=[(AccountSourceKind.RSS_FEED, "https://acme-test.com/feed.xml")],
    )

    await drain(connection, settings(job_max_attempts=2))

    run = await run_row(connection, scene_.run_id)
    [error] = run.errors
    assert {key: error[key] for key in ("stage", "plugin_code", "code")} == {
        "stage": "FETCH",
        "plugin_code": "GDELT",
        "code": "UPSTREAM_UNAVAILABLE",
    }
    assert "503" in error["message"]
    assert run.status is PipelineRunStatus.PARTIAL
    gdelt = await plugin_row(connection, SourcePluginCode.GDELT)
    assert gdelt.last_error is not None and "503" in gdelt.last_error
    assert gdelt.last_error_at is not None
    assert gdelt.last_success_at is None
    # Two attempts, each robots.txt, the search and its one retry: counted although the step
    # rolled back.
    assert await usage(connection, SourcePluginCode.GDELT) == 6
    assert [d.plugin_code for d in await documents(connection, scene_)] == [SourcePluginCode.RSS]
    steps = [
        step
        for (step,) in (
            await connection.execute(select(Job.step).where(Job.run_id == scene_.run_id))
        ).all()
    ]
    assert steps.count(JobStep.PROCESS) == 1


async def test_in_replay_an_unrecorded_request_fails_the_job_with_fixture_missing(
    connection: AsyncConnection, tmp_path: Path
) -> None:
    scene_ = await scene(connection, fetch=[SourcePluginCode.GDELT])

    await drain(connection, settings(fixture_mode="replay", fixture_dir=tmp_path))

    [error] = (await run_row(connection, scene_.run_id)).errors
    assert (error["code"], error["plugin_code"]) == ("FIXTURE_MISSING", "GDELT")
    assert await documents(connection, scene_) == []
    assert list(tmp_path.iterdir()) == []


async def test_a_plugin_disabled_after_the_run_was_enqueued_makes_no_request_and_no_error(
    connection: AsyncConnection, web: Web
) -> None:
    scene_ = await scene(
        connection,
        fetch=[SourcePluginCode.GDELT],
        plugins={SourcePluginCode.GDELT: {"enabled": False}},
    )

    await drain(connection, settings())

    assert web.requests == []
    assert await usage(connection, SourcePluginCode.GDELT) == 0
    run = await run_row(connection, scene_.run_id)
    assert run.errors == []
    assert run.status is PipelineRunStatus.SUCCEEDED
    [fetch_job] = (
        await connection.execute(
            select(Job.status).where(Job.run_id == scene_.run_id, Job.step == JobStep.FETCH)
        )
    ).all()
    assert fetch_job.status is JobStatus.DONE


async def test_a_plugin_that_reaches_its_daily_quota_mid_job_sends_no_further_request(
    connection: AsyncConnection, web: Web
) -> None:
    urls = [f"https://news.example.org/q{index}" for index in range(3)]
    web.add(GDELT_SEARCH, gdelt_articles(urls), kind="json")
    for index, url in enumerate(urls):
        web.add(url, html(f"Quota story {index}"))
    scene_ = await scene(
        connection,
        fetch=[SourcePluginCode.GDELT],
        plugins={SourcePluginCode.GDELT: {"daily_quota": 4}},
    )

    await drain(connection, settings())

    assert len(web.pages) == 2
    assert await usage(connection, SourcePluginCode.GDELT) == 4  # two robots.txt, search, one
    assert len(await documents(connection, scene_)) == 1
    assert (await run_row(connection, scene_.run_id)).errors == []


async def test_a_keyed_plugin_without_an_adapter_fails_internal_naming_the_plugin(
    connection: AsyncConnection, web: Web
) -> None:
    scene_ = await scene(connection, fetch=[SourcePluginCode.NEWSAPI])

    await drain(connection, settings(newsapi_key=SecretStr("key")))

    [error] = (await run_row(connection, scene_.run_id)).errors
    assert error["code"] == "INTERNAL"
    assert error["plugin_code"] == "NEWSAPI"
    assert "NEWSAPI" in error["message"]
    assert web.requests == []
