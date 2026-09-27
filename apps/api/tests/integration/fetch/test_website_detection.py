"""Integration tests of [Source detection](/architecture/rules.md#source-detection) (`S-ING-05`,
`AC-19`) wired into the `WEBSITE` `FETCH` job: home-page link detection, the `SERPAPI`
web-search half, and the crawler's redirect following ([Fetch window]
(/architecture/rules.md#fetch-window) step 3; ADR-21, `source-detection-timing-and-redirects`).

The provider's side is an `httpx.MockTransport` behind the real crawl client, as in
`test_fetch_step.py`. Every test runs in one outer transaction rolled back at the end."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import Connection, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from leadradar.core.enums import (
    AccountSourceKind,
    AccountSourceOrigin,
    AccountSourceStatus,
    AuditAction,
    JobStatus,
    JobStep,
    PipelineRunStatus,
    SourcePluginCode,
)
from leadradar.db.models.accounts import AccountSource
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.ingestion import Document, Job, PipelineRun, SourcePlugin
from leadradar.worker.loop import process_next_job
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import STEP_HANDLERS, StepContext, StepHandler
from tests.integration import factories as f
from tests.integration.pipeline_doubles import T0, Clock, Web, html, install_web, session_factory

pytestmark = pytest.mark.integration

DOMAIN = "acme-test.com"
HOME_URL = f"https://{DOMAIN}/"


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
    fetch: Sequence[SourcePluginCode] = (SourcePluginCode.WEBSITE,),
    extra_sources: Sequence[
        tuple[AccountSourceKind, str, AccountSourceOrigin, AccountSourceStatus]
    ] = (),
    plugins: dict[SourcePluginCode, dict[str, Any]] | None = None,
) -> Scene:
    """An account whose only source is `WEBSITE` at `HOME_URL` (as created for a real account),
    plus `extra_sources`; one `FETCH` job per code of `fetch`."""

    def build(conn: Connection) -> Scene:
        for code in SourcePluginCode:
            f.make_source_plugin(conn, code=code, **((plugins or {}).get(code) or {}))
        account_id = f.make_account(conn, name="Acme Corp", domain=DOMAIN)
        conn.execute(
            insert(AccountSource).values(
                account_id=account_id,
                kind=AccountSourceKind.WEBSITE,
                url=HOME_URL,
                origin=AccountSourceOrigin.MANUAL,
                status=AccountSourceStatus.ACTIVE,
            )
        )
        for kind, url, origin, status in extra_sources:
            conn.execute(
                insert(AccountSource).values(
                    account_id=account_id, kind=kind, url=url, origin=origin, status=status
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


async def sources_of(connection: AsyncConnection, account_id: uuid.UUID) -> list[Any]:
    rows = await connection.execute(
        select(AccountSource)
        .where(AccountSource.account_id == account_id)
        .order_by(AccountSource.kind, AccountSource.url)
    )
    return list(rows.all())


async def account_updated_rows(connection: AsyncConnection, run_id: uuid.UUID) -> list[Any]:
    rows = await connection.execute(
        select(AuditEvent).where(
            AuditEvent.run_id == run_id, AuditEvent.action == AuditAction.ACCOUNT_UPDATED
        )
    )
    return list(rows.all())


async def documents_of(connection: AsyncConnection, account_id: uuid.UUID) -> list[Any]:
    rows = await connection.execute(
        select(Document).where(Document.account_id == account_id).order_by(Document.url)
    )
    return list(rows.all())


async def usage(connection: AsyncConnection, code: SourcePluginCode) -> int:
    from leadradar.db.models.ingestion import PluginUsage

    requests = (
        await connection.execute(
            select(PluginUsage.requests).where(
                PluginUsage.plugin_code == code, PluginUsage.day == T0.date()
            )
        )
    ).scalar_one_or_none()
    return int(requests or 0)


def home_page_with_links(links: Sequence[str] = ()) -> str:
    return html("Acme Corp home", links)


# --- home-page link detection ------------------------------------------------------------------


async def test_home_page_links_add_detected_sources_with_one_audit_row(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(HOME_URL, home_page_with_links(["/press", "/careers"]))
    scene_ = await scene(connection)

    await drain(connection, settings())

    sources = await sources_of(connection, scene_.account_id)
    detected = {
        (row.kind, row.url): row for row in sources if row.origin is AccountSourceOrigin.DETECTED
    }
    assert set(detected) == {
        (AccountSourceKind.NEWSROOM, f"https://{DOMAIN}/press"),
        (AccountSourceKind.CAREERS, f"https://{DOMAIN}/careers"),
    }
    assert all(row.status is AccountSourceStatus.ACTIVE for row in detected.values())
    [audit_row] = await account_updated_rows(connection, scene_.run_id)
    assert audit_row.actor_id is None
    assert audit_row.run_id == scene_.run_id
    payload_urls = {entry["url"] for entry in audit_row.payload["sources"]}
    assert payload_urls == {f"https://{DOMAIN}/press", f"https://{DOMAIN}/careers"}


async def test_a_manual_source_of_a_kind_blocks_its_detection(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(HOME_URL, home_page_with_links(["/careers"]))
    scene_ = await scene(
        connection,
        extra_sources=[
            (
                AccountSourceKind.CAREERS,
                "https://boards.greenhouse.io/acme",
                AccountSourceOrigin.MANUAL,
                AccountSourceStatus.ACTIVE,
            )
        ],
    )

    await drain(connection, settings())

    sources = await sources_of(connection, scene_.account_id)
    careers = [row for row in sources if row.kind == AccountSourceKind.CAREERS]
    assert [c.url for c in careers] == ["https://boards.greenhouse.io/acme"]
    assert careers[0].origin is AccountSourceOrigin.MANUAL


async def test_an_inactive_detected_source_of_a_kind_also_blocks_its_detection(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(HOME_URL, home_page_with_links(["/careers"]))
    scene_ = await scene(
        connection,
        extra_sources=[
            (
                AccountSourceKind.CAREERS,
                f"https://{DOMAIN}/old-careers",
                AccountSourceOrigin.DETECTED,
                AccountSourceStatus.INACTIVE,
            )
        ],
    )

    await drain(connection, settings())

    sources = await sources_of(connection, scene_.account_id)
    careers = [row for row in sources if row.kind == AccountSourceKind.CAREERS]
    assert [c.url for c in careers] == [f"https://{DOMAIN}/old-careers"]


async def test_a_detected_url_already_a_source_of_another_kind_adds_no_row(
    connection: AsyncConnection, web: Web
) -> None:
    shared_url = f"https://{DOMAIN}/careers"
    web.add(HOME_URL, home_page_with_links(["/careers"]))
    scene_ = await scene(
        connection,
        extra_sources=[
            (
                AccountSourceKind.INVESTOR_RELATIONS,
                shared_url,
                AccountSourceOrigin.MANUAL,
                AccountSourceStatus.ACTIVE,
            )
        ],
    )

    await drain(connection, settings())

    sources = await sources_of(connection, scene_.account_id)
    matching = [row for row in sources if row.url == shared_url]
    assert len(matching) == 1
    assert matching[0].kind == AccountSourceKind.INVESTOR_RELATIONS
    assert await account_updated_rows(connection, scene_.run_id) == []


async def test_running_the_fetch_again_adds_no_source_or_audit_row(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(HOME_URL, home_page_with_links(["/press"]))
    scene_ = await scene(connection)
    await drain(connection, settings())
    first_sources = await sources_of(connection, scene_.account_id)
    await connection.execute(
        update(PipelineRun)
        .where(PipelineRun.id == scene_.run_id)
        .values(status=PipelineRunStatus.SUCCEEDED)
    )

    def again(conn: Connection) -> uuid.UUID:
        run_id = f.make_pipeline_run(conn, account_id=scene_.account_id)
        f.make_job(
            conn, run_id, step=JobStep.FETCH, payload={"plugin_code": "WEBSITE"}, not_before=T0
        )
        return run_id

    second_run = await connection.run_sync(again)
    await drain(connection, settings())

    assert await sources_of(connection, scene_.account_id) == first_sources
    assert await account_updated_rows(connection, second_run) == []


async def test_a_source_detected_this_run_is_not_read_by_the_same_runs_careers_job(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(HOME_URL, home_page_with_links(["/careers"]))
    scene_ = await scene(connection, fetch=[SourcePluginCode.WEBSITE, SourcePluginCode.CAREERS])

    await drain(connection, settings())

    sources = await sources_of(connection, scene_.account_id)
    assert any(
        row.kind == AccountSourceKind.CAREERS and row.origin is AccountSourceOrigin.DETECTED
        for row in sources
    )
    # The CAREERS job of this same run read no CAREERS source: no request went to the ATS API,
    # and no job posting was stored.
    documents = await documents_of(connection, scene_.account_id)
    assert not any(d.plugin_code == SourcePluginCode.CAREERS for d in documents)

    def next_refresh(conn: Connection) -> uuid.UUID:
        run_id = f.make_pipeline_run(conn, account_id=scene_.account_id)
        f.make_job(
            conn, run_id, step=JobStep.FETCH, payload={"plugin_code": "CAREERS"}, not_before=T0
        )
        return run_id

    await connection.execute(
        update(PipelineRun)
        .where(PipelineRun.id == scene_.run_id)
        .values(status=PipelineRunStatus.SUCCEEDED)
    )
    web.add(f"https://{DOMAIN}/careers", home_page_with_links())
    await connection.run_sync(next_refresh)
    await drain(connection, settings())

    careers_requests = [r for r in web.pages if str(r.url) == f"https://{DOMAIN}/careers"]
    assert careers_requests  # the next refresh does read the detected source


async def test_with_max_items_one_the_home_page_is_still_the_one_item(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(HOME_URL, home_page_with_links(["/press"]))
    scene_ = await scene(connection)

    await drain(connection, settings(max_documents_per_refresh=1))

    documents = await documents_of(connection, scene_.account_id)
    assert [d.url for d in documents] == [HOME_URL]
    sources = await sources_of(connection, scene_.account_id)
    assert any(row.kind == AccountSourceKind.NEWSROOM for row in sources)


# --- redirects ------------------------------------------------------------------------------


async def test_a_redirected_home_page_is_read_and_detection_resolves_against_the_final_url(
    connection: AsyncConnection, web: Web
) -> None:
    final_url = f"https://www.{DOMAIN}/"
    web.add(HOME_URL, "", status=301, headers={"location": final_url})
    web.add(final_url, home_page_with_links(["/careers"]))
    scene_ = await scene(connection)

    await drain(connection, settings())

    documents = await documents_of(connection, scene_.account_id)
    assert [d.url for d in documents] == [HOME_URL]  # G9: the address requested, not the target
    sources = await sources_of(connection, scene_.account_id)
    assert any(
        row.kind == AccountSourceKind.CAREERS and row.url == f"https://www.{DOMAIN}/careers"
        for row in sources
    )


async def test_a_redirect_to_another_registrable_domain_is_not_followed(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(HOME_URL, "", status=301, headers={"location": "https://evil-example.com/"})
    scene_ = await scene(connection)

    await drain(connection, settings())

    assert not any("evil-example.com" in str(r.url) for r in web.requests)
    assert await documents_of(connection, scene_.account_id) == []


async def test_a_redirect_loop_stops_at_the_first_repeated_url(
    connection: AsyncConnection, web: Web
) -> None:
    other = f"https://{DOMAIN}/b"
    web.add(HOME_URL, "", status=301, headers={"location": other})
    web.add(other, "", status=301, headers={"location": HOME_URL})
    scene_ = await scene(connection)

    await drain(connection, settings())

    assert len(web.pages) == 2  # the home page, then /b; the repeat of the home page is not sent
    assert await documents_of(connection, scene_.account_id) == []


async def test_a_hop_disallowed_by_robots_is_not_requested(
    connection: AsyncConnection, web: Web
) -> None:
    web.robots[DOMAIN] = "User-agent: *\nDisallow: /secret"
    web.add(HOME_URL, "", status=301, headers={"location": f"https://{DOMAIN}/secret"})
    scene_ = await scene(connection)

    await drain(connection, settings())

    assert not any(r.url.path == "/secret" for r in web.requests)
    assert await documents_of(connection, scene_.account_id) == []


async def test_each_redirect_hop_counts_against_the_page_budget(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(HOME_URL, "", status=301, headers={"location": f"https://www.{DOMAIN}/"})
    web.add(f"https://www.{DOMAIN}/", home_page_with_links())
    scene_ = await scene(connection)

    await drain(connection, settings(crawl_max_pages_per_site=1))

    assert await documents_of(connection, scene_.account_id) == []
    assert await usage(connection, SourcePluginCode.WEBSITE) == 2  # one robots.txt, one page
    assert len(web.pages) == 1


# --- SERPAPI --------------------------------------------------------------------------------


async def test_serpapi_unavailable_makes_no_request(connection: AsyncConnection, web: Web) -> None:
    web.add(HOME_URL, home_page_with_links())
    await scene(connection)

    await drain(connection, settings())  # no serpapi_key configured

    assert not any("serpapi.com" in str(r.url) for r in web.requests)
    assert await usage(connection, SourcePluginCode.SERPAPI) == 0


async def test_serpapi_available_and_careers_missing_detects_the_first_on_domain_result(
    connection: AsyncConnection, web: Web
) -> None:
    web.add(HOME_URL, home_page_with_links())  # no matching links: CAREERS and IR stay missing
    web.add(
        "https://serpapi.com/search.json",
        {
            "organic_results": [
                {"link": "https://other.example/careers"},
                {"link": f"https://{DOMAIN}/careers"},
            ]
        },
        kind="json",
    )
    scene_ = await scene(connection)

    await drain(connection, settings(serpapi_key=SecretStr("key")))

    sources = await sources_of(connection, scene_.account_id)
    careers = [row for row in sources if row.kind == AccountSourceKind.CAREERS]
    assert [c.url for c in careers] == [f"https://{DOMAIN}/careers"]
    # One robots.txt request, plus one search per missing kind (CAREERS, INVESTOR_RELATIONS).
    assert await usage(connection, SourcePluginCode.SERPAPI) == 3


async def test_a_failed_serpapi_search_records_a_run_error_and_keeps_home_page_detections(
    connection: AsyncConnection, web: Web
) -> None:
    # The home page's own link fills INVESTOR_RELATIONS, so only one SERPAPI search (CAREERS)
    # is made, and only one error results.
    web.add(HOME_URL, home_page_with_links(["/press", "/investors"]))
    web.add("https://serpapi.com/search.json", "unavailable", status=503, kind="json")
    scene_ = await scene(connection)

    await drain(connection, settings(serpapi_key=SecretStr("key"), job_max_attempts=2))

    sources = await sources_of(connection, scene_.account_id)
    assert any(row.kind == AccountSourceKind.NEWSROOM for row in sources)
    run = (
        await connection.execute(select(PipelineRun).where(PipelineRun.id == scene_.run_id))
    ).one()
    errors = cast(list[dict[str, Any]], run.errors)
    [error] = [e for e in errors if e.get("plugin_code") == "SERPAPI"]
    assert error["stage"] == "FETCH"
    assert error["code"] == "UPSTREAM_UNAVAILABLE"
    assert run.status is PipelineRunStatus.PARTIAL


async def test_in_record_mode_the_serpapi_fixture_holds_no_api_key(
    connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unlike the other tests here, this one does not use the `web` fixture: it needs requests to
    go through the real record/replay transport, not the raw mock `install_web` substitutes for
    it, so that a fixture file is actually written (G5)."""
    server = Web()
    server.add(HOME_URL, home_page_with_links())
    server.add(
        "https://serpapi.com/search.json",
        {"organic_results": [{"link": f"https://{DOMAIN}/careers"}]},
        kind="json",
    )
    monkeypatch.setattr(
        "leadradar.ai.fixtures.httpx.AsyncHTTPTransport", lambda: httpx.MockTransport(server)
    )
    await scene(connection)

    await drain(
        connection,
        settings(
            serpapi_key=SecretStr("super-secret"), fixture_mode="record", fixture_dir=tmp_path
        ),
    )

    files = list((tmp_path / "SERPAPI").glob("*.json"))
    assert files
    for path in files:
        assert "super-secret" not in path.read_text()
