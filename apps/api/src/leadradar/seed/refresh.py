"""Entry point `leadradar-refresh-demo` ([Seeding](/architecture/overview.md#runtime)): the demo
refresh that follows `make seed-demo`. Requests a refresh of every active account through
`API-33` (`runs.commands.request_account_refresh`, the same function the route calls) and waits
until every run it created is final, so the worker container does the actual fetching,
processing, classifying and scoring - this entry point only enqueues and watches.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.clock import build_clock
from leadradar.core.enums import AccountStatus, PipelineRunStatus, SourcePluginCode
from leadradar.db.models.accounts import Account
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import PipelineRun
from leadradar.db.session import build_engine
from leadradar.logs import configure_json_logging
from leadradar.runs.commands import request_account_refresh
from leadradar.seed.demo import DEMO_ADMIN_EMAIL
from leadradar.settings import ApiSettings

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = (PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING)


class RefreshSettings(ApiSettings):
    """Adds the two [worker runtime](/architecture/services/worker.md#runtime) keys this entry
    point's wait needs; the api already reads `EVAL_MIN_ITEMS` of the same section for the same
    reason ([api Runtime](/architecture/services/api.md#runtime))."""

    job_poll_interval_s: float = 1.0
    refresh_target_minutes: float = 10.0


def _plugins_with_a_key(settings: ApiSettings) -> frozenset[SourcePluginCode]:
    """The plug-ins whose key is set in the runtime, exactly as `api.post_account_refresh`
    (`API-33`) computes it, so a refresh queued here sees the same available plug-ins."""
    keys = {
        SourcePluginCode.CRUNCHBASE: settings.crunchbase_api_key,
        SourcePluginCode.NEWSAPI: settings.newsapi_key,
        SourcePluginCode.SERPAPI: settings.serpapi_key,
    }
    return frozenset(code for code, key in keys.items() if key is not None)


async def _require_admin(db: AsyncSession) -> AppUser:
    admin = (
        await db.execute(select(AppUser).where(AppUser.email == DEMO_ADMIN_EMAIL))
    ).scalar_one()
    return admin


async def _active_account_ids(db: AsyncSession) -> list[uuid.UUID]:
    return list(
        (await db.execute(select(Account.id).where(Account.status == AccountStatus.ACTIVE)))
        .scalars()
        .all()
    )


async def refresh_demo_accounts(db: AsyncSession, settings: RefreshSettings) -> list[uuid.UUID]:
    """Requests one `USER` refresh per active account through `request_account_refresh`
    (`API-33`), each in its own transaction, and returns the run ids to wait for."""
    admin = await _require_admin(db)
    keys_configured = _plugins_with_a_key(settings)
    clock = build_clock(settings)

    run_ids: list[uuid.UUID] = []
    for account_id in await _active_account_ids(db):
        result = await request_account_refresh(
            db,
            account_id=account_id,
            principal=admin,
            keys_configured=keys_configured,
            now=clock(),
        )
        run_ids.append(result.run.id)
    return run_ids


async def _run_statuses(
    db: AsyncSession, run_ids: list[uuid.UUID]
) -> dict[uuid.UUID, PipelineRunStatus]:
    rows = await db.execute(
        select(PipelineRun.id, PipelineRun.status).where(PipelineRun.id.in_(run_ids))
    )
    return dict(rows.all())


async def wait_for_runs_final(
    db: AsyncSession, run_ids: list[uuid.UUID], settings: RefreshSettings
) -> None:
    """Polls the runs `request_account_refresh` created until every one leaves `QUEUED` or
    `RUNNING`. The deadline is one `REFRESH_TARGET_MINUTES` per run - the target duration of one
    account refresh in replay mode - since the worker processes them concurrently, never one at
    a time."""
    if not run_ids:
        return
    deadline = time.monotonic() + len(run_ids) * settings.refresh_target_minutes * 60
    while True:
        statuses = await _run_statuses(db, run_ids)
        if all(status not in _ACTIVE_STATUSES for status in statuses.values()):
            return
        if time.monotonic() >= deadline:
            unfinished = [
                str(run_id) for run_id, status in statuses.items() if status in _ACTIVE_STATUSES
            ]
            raise TimeoutError(f"Runs still not final after the deadline: {', '.join(unfinished)}")
        await asyncio.sleep(settings.job_poll_interval_s)
        db.expire_all()


async def _run(settings: RefreshSettings) -> None:
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            run_ids = await refresh_demo_accounts(db, settings)
            await wait_for_runs_final(db, run_ids, settings)
    finally:
        await engine.dispose()


def run() -> None:
    """`leadradar-refresh-demo`: fails loudly (a non-zero exit, one JSON log line) rather than
    leaving the demo dataset partially refreshed."""
    settings = RefreshSettings()
    configure_json_logging(settings.log_level)
    try:
        asyncio.run(_run(settings))
    except Exception:
        logger.exception("Refreshing the demo dataset failed")
        sys.exit(1)
    logger.info("Refreshed the demo dataset")


if __name__ == "__main__":
    run()
