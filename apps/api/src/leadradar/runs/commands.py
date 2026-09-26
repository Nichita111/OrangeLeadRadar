"""The api's run commands ([Runs and source plug-ins contracts]
(/architecture/interfaces.md#runs-and-source-plug-ins-contracts)): `API-33` requests an account
refresh, `API-36` cancels a run. Each commits the request's one transaction — the one its
authentication opened — writing the change and its audit row together
([api Design](/architecture/services/api.md#design) Transactions)."""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.auth.errors import Forbidden
from leadradar.core.enums import (
    AccountStatus,
    AppUserRole,
    AuditAction,
    JobStatus,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
    SourcePluginCode,
)
from leadradar.core.plugin_availability import is_plugin_available
from leadradar.db.models.accounts import Account
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Job, PipelineRun, PluginUsage, SourcePlugin
from leadradar.runs.enqueue import enqueue_account_refresh
from leadradar.runs.errors import AccountInactive, RefreshAccountNotFound, RunFinished, RunNotFound
from leadradar.runs.queries import RunView, read_run

# `API-36`: only an Admin cancels these kinds, so a user cannot leave a question's stored
# passages or a scoring version half applied.
_ADMIN_ONLY_CANCEL_KINDS = frozenset(
    {PipelineRunKind.RECLASSIFY, PipelineRunKind.RESCORE, PipelineRunKind.EVALUATION}
)
_ACTIVE_STATUSES = (PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING)


@dataclass(frozen=True)
class RefreshRequested:
    """`API-33`'s result: the run, and whether this request created it (`202`) or found it
    queued or running (`200`)."""

    run: RunView
    created: bool


async def _available_plugins(
    session: AsyncSession, *, keys_configured: Collection[SourcePluginCode], now: datetime
) -> set[SourcePluginCode]:
    """The plug-ins [Plug-in availability](/architecture/rules.md#plug-in-availability) allows
    now: their switch, key and today's usage."""
    rows = await session.execute(
        select(SourcePlugin, PluginUsage.requests).outerjoin(
            PluginUsage,
            (PluginUsage.plugin_code == SourcePlugin.code) & (PluginUsage.day == now.date()),
        )
    )
    return {
        plugin.code
        for plugin, requests_today in rows
        if is_plugin_available(
            code=plugin.code,
            enabled=plugin.enabled,
            key_configured=plugin.code in keys_configured,
            requests_today=requests_today or 0,
            daily_quota=plugin.daily_quota,
        )
    }


async def request_account_refresh(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    principal: AppUser,
    keys_configured: Collection[SourcePluginCode],
    now: datetime,
) -> RefreshRequested:
    """`API-33`: enqueues a `USER` refresh of the account with its `RUN_REQUESTED` audit row, or
    returns the refresh already queued or running. Raises `RefreshAccountNotFound` or
    `AccountInactive`."""
    account = await session.get(Account, account_id, populate_existing=True)
    if account is None:
        raise RefreshAccountNotFound(f"No account {account_id}.")
    if account.status is not AccountStatus.ACTIVE:
        raise AccountInactive(f"Account {account_id} is inactive.")

    run_id, created = await enqueue_account_refresh(
        session,
        account_id=account_id,
        trigger=PipelineRunTrigger.USER,
        requested_by=principal.id,
        available_plugins=await _available_plugins(
            session, keys_configured=keys_configured, now=now
        ),
        now=now,
    )
    if created:
        await append_audit_event(
            session,
            action=AuditAction.RUN_REQUESTED,
            occurred_at=now,
            actor_id=principal.id,
            entity_type="pipeline_run",
            entity_id=run_id,
            payload={
                "kind": PipelineRunKind.ACCOUNT_REFRESH.value,
                "trigger": PipelineRunTrigger.USER.value,
            },
            run_id=run_id,
        )
    view = await read_run(session, run_id)
    await session.commit()
    if view is None:
        raise RunNotFound(f"No run {run_id}.")
    return RefreshRequested(run=view, created=created)


async def cancel_run(
    session: AsyncSession, *, run_id: uuid.UUID, principal: AppUser, now: datetime
) -> RunView:
    """`API-36`: sets the run `CANCELLED` with `finished_at` and its `READY` jobs `CANCELLED`,
    with a `RUN_CANCELLED` audit row ([Run lifecycle]
    (/architecture/services/worker.md#run-lifecycle)). Raises `RunNotFound`, `Forbidden` for a
    Sales user cancelling an Admin-only kind, or `RunFinished`.

    Jobs are updated before the run, the order the worker's job loop locks them in, so the two
    never wait on each other in a cycle."""
    run = await session.get(PipelineRun, run_id, populate_existing=True)
    if run is None:
        raise RunNotFound(f"No run {run_id}.")
    if run.kind in _ADMIN_ONLY_CANCEL_KINDS and principal.role is not AppUserRole.ADMIN:
        raise Forbidden
    if run.status not in _ACTIVE_STATUSES:
        raise RunFinished(f"Run {run_id} is {run.status}.")

    await session.execute(
        update(Job)
        .where(Job.run_id == run_id, Job.status == JobStatus.READY)
        .values(status=JobStatus.CANCELLED)
    )
    cancelled = await session.execute(
        update(PipelineRun)
        .where(PipelineRun.id == run_id, PipelineRun.status.in_(_ACTIVE_STATUSES))
        .values(status=PipelineRunStatus.CANCELLED, stage=None, finished_at=now)
        .returning(PipelineRun.id)
    )
    if cancelled.scalar_one_or_none() is None:
        # The run's last job finished it while this request waited for its lock.
        raise RunFinished(f"Run {run_id} finished meanwhile.")
    await append_audit_event(
        session,
        action=AuditAction.RUN_CANCELLED,
        occurred_at=now,
        actor_id=principal.id,
        entity_type="pipeline_run",
        entity_id=run_id,
        payload={},
        run_id=run_id,
    )
    session.expire_all()
    view = await read_run(session, run_id)
    await session.commit()
    if view is None:
        raise RunNotFound(f"No run {run_id}.")
    return view
