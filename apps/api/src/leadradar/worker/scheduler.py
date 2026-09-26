"""The scheduler of [Scheduler and housekeeping]
(/architecture/services/worker.md#scheduler-and-housekeeping): every `SCHEDULER_TICK_S`, applies
[Refresh scheduling](/architecture/rules.md#refresh-scheduling) — the due-account selection is
the pure `core.refresh_scheduling.due_refresh_account_ids`; this module is the store access and
the loop around it. One worker at a time runs a tick: a PostgreSQL advisory lock, held for the
tick's transaction only, makes every other loop skip it."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.core.enums import (
    AuditAction,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
    SourcePluginCode,
)
from leadradar.core.refresh_scheduling import RefreshCandidate, due_refresh_account_ids
from leadradar.db.models.accounts import Account
from leadradar.db.models.ingestion import PipelineRun
from leadradar.runs.enqueue import enqueue_account_refresh
from leadradar.runs.queries import available_refresh_plugins
from leadradar.worker.settings import WorkerSettings

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AsyncSession]
Clock = Callable[[], datetime]

_ACTIVE_STATUSES = (PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING)

#: This scheduler tick's own PostgreSQL advisory lock id: an arbitrary constant, unique among
#: the process's advisory locks (there are no others), never a business-configurable number.
_SCHEDULER_LOCK_KEY = 72710010


def _plugin_keys_configured(settings: WorkerSettings) -> frozenset[SourcePluginCode]:
    """The plug-ins whose key is set in the runtime, as `api.runs_and_source_plugins` reads
    them from `ApiSettings`; the keys themselves stay in `settings`."""
    keys = {
        SourcePluginCode.CRUNCHBASE: settings.crunchbase_api_key,
        SourcePluginCode.NEWSAPI: settings.newsapi_key,
        SourcePluginCode.SERPAPI: settings.serpapi_key,
    }
    return frozenset(code for code, key in keys.items() if key is not None)


async def _refresh_candidates(session: AsyncSession) -> list[RefreshCandidate]:
    active_refresh_ids = select(PipelineRun.account_id).where(
        PipelineRun.kind == PipelineRunKind.ACCOUNT_REFRESH,
        PipelineRun.status.in_(_ACTIVE_STATUSES),
    )
    rows = await session.execute(
        select(
            Account.id,
            Account.status,
            Account.next_refresh_at,
            Account.id.in_(active_refresh_ids),
        )
    )
    return [
        RefreshCandidate(
            account_id=account_id,
            status=status,
            next_refresh_at=next_refresh_at,
            has_active_refresh=has_active_refresh,
        )
        for account_id, status, next_refresh_at, has_active_refresh in rows
    ]


async def run_scheduler_tick(
    session_factory: SessionFactory,
    *,
    clock: Clock,
    max_enqueue: int,
    keys_configured: frozenset[SourcePluginCode],
) -> int:
    """One tick: skips when another worker holds the advisory lock, else enqueues an
    `ACCOUNT_REFRESH` with trigger `SCHEDULE` for every due account, oldest due first, up to
    `max_enqueue`. Returns how many were selected (0 when the lock was held or none was due).
    `requested_by` is `None`: the scheduler acts on its own ([`audit_event`]
    (/architecture/sql-store.md#audit_event) `actor_id`)."""
    now = clock()
    async with session_factory() as session, session.begin():
        acquired: bool = (
            await session.execute(select(func.pg_try_advisory_xact_lock(_SCHEDULER_LOCK_KEY)))
        ).scalar_one()
        if not acquired:
            return 0

        due_ids = due_refresh_account_ids(
            await _refresh_candidates(session), now=now, limit=max_enqueue
        )
        if not due_ids:
            return 0

        available_plugins = await available_refresh_plugins(
            session, keys_configured=keys_configured, now=now
        )
        for account_id in due_ids:
            run_id, created = await enqueue_account_refresh(
                session,
                account_id=account_id,
                trigger=PipelineRunTrigger.SCHEDULE,
                requested_by=None,
                available_plugins=available_plugins,
                now=now,
            )
            if created:
                await append_audit_event(
                    session,
                    action=AuditAction.RUN_REQUESTED,
                    occurred_at=now,
                    actor_id=None,
                    entity_type="pipeline_run",
                    entity_id=run_id,
                    payload={
                        "kind": PipelineRunKind.ACCOUNT_REFRESH.value,
                        "trigger": PipelineRunTrigger.SCHEDULE.value,
                    },
                    run_id=run_id,
                )
        return len(due_ids)


async def run_scheduler_loop(
    session_factory: SessionFactory,
    *,
    clock: Clock,
    settings: WorkerSettings,
    stop: asyncio.Event,
) -> None:
    """Ticks every `SCHEDULER_TICK_S` until `stop` is set."""
    keys_configured = _plugin_keys_configured(settings)
    while not stop.is_set():
        try:
            await run_scheduler_tick(
                session_factory,
                clock=clock,
                max_enqueue=settings.scheduler_max_enqueue,
                keys_configured=keys_configured,
            )
        except Exception:
            # The database is unreachable or refused the tick: logged, and tried again after
            # the next interval rather than ending the loop (the job loops do the same).
            logger.exception("Scheduler tick failed")
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.scheduler_tick_s)
