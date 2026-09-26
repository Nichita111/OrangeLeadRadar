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
from leadradar.core.sign_in import changed_fields
from leadradar.db.models.accounts import Account
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Job, PipelineRun, SourcePlugin
from leadradar.runs.enqueue import enqueue_account_refresh
from leadradar.runs.errors import (
    AccountInactive,
    RefreshAccountNotFound,
    RunFinished,
    RunNotFound,
    SourcePluginNotFound,
)
from leadradar.runs.queries import (
    RunView,
    SourcePluginView,
    available_refresh_plugins,
    get_source_plugin,
    read_run,
)

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
        available_plugins=await available_refresh_plugins(
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


async def update_source_plugin(
    session: AsyncSession,
    *,
    code: SourcePluginCode,
    enabled: bool | None,
    rate_limit_per_minute: int | None,
    daily_quota: int | None,
    daily_quota_set: bool,
    keys_configured: Collection[SourcePluginCode],
    principal: AppUser,
    now: datetime,
) -> SourcePluginView:
    """`API-38`: saves the Admin's switch and limits, in effect from the next fetch, with a
    `PLUGIN_UPDATED` audit row. Raises `SourcePluginNotFound`."""
    plugin = (
        await session.execute(
            select(SourcePlugin).where(SourcePlugin.code == code).with_for_update()
        )
    ).scalar_one_or_none()
    if plugin is None:
        raise SourcePluginNotFound(f"No source plugin {code}.")

    sent: dict[str, object] = {}
    if enabled is not None:
        sent["enabled"] = enabled
    if rate_limit_per_minute is not None:
        sent["rate_limit_per_minute"] = rate_limit_per_minute
    if daily_quota_set:
        sent["daily_quota"] = daily_quota
    changes = changed_fields(
        {
            "enabled": plugin.enabled,
            "rate_limit_per_minute": plugin.rate_limit_per_minute,
            "daily_quota": plugin.daily_quota,
        },
        sent,
    )
    for field, value in changes.items():
        setattr(plugin, field, value)

    if changes:
        await append_audit_event(
            session,
            action=AuditAction.PLUGIN_UPDATED,
            occurred_at=now,
            actor_id=principal.id,
            entity_type="source_plugin",
            entity_id=plugin.id,
            payload={"code": code.value, **changes},
        )
    await session.commit()
    return await get_source_plugin(session, code, keys_configured=keys_configured, now=now)
