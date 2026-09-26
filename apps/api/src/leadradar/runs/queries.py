"""Reads that shape a [`Run`](/architecture/interfaces.md#run) (`API-33` to `API-36`) out of the
store. Plain dataclasses; the Pydantic response model lives at the api boundary
(`api/runs_and_source_plugins.py`)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Numeric, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AuditAction,
    PipelineRunKind,
    PipelineRunStage,
    PipelineRunStatus,
    PipelineRunTrigger,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.configuration import Service, SignalQuestion
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import PipelineRun
from leadradar.runs.errors import RunNotFound


@dataclass(frozen=True)
class NamedRef:
    """`Run.account` and `Run.service`: `{id, name}`."""

    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class QuestionRef:
    """`Run.question`: `{id, key}`."""

    id: uuid.UUID
    key: str


@dataclass(frozen=True)
class RunView:
    """[`Run`](/architecture/interfaces.md#run)."""

    id: uuid.UUID
    kind: PipelineRunKind
    trigger: PipelineRunTrigger
    status: PipelineRunStatus
    stage: PipelineRunStage | None
    progress: dict[str, object]
    errors: list[object]
    account: NamedRef | None
    service: NamedRef | None
    question: QuestionRef | None
    requested_by_name: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    ai_cost_eur: float


@dataclass(frozen=True)
class RunFilters:
    """The query of `API-34`; `None` does not filter."""

    kind: PipelineRunKind | None
    status: PipelineRunStatus | None
    account_id: uuid.UUID | None
    service_id: uuid.UUID | None


def _run_view_select() -> Select[Any]:
    # `ai_cost_eur`: the sum of `cost_eur` of the run's `AI_CALL` audit rows, served by the
    # `audit_event (run_id)` index.
    ai_cost_eur = (
        select(func.coalesce(func.sum(AuditEvent.payload["cost_eur"].astext.cast(Numeric)), 0))
        .where(AuditEvent.run_id == PipelineRun.id, AuditEvent.action == AuditAction.AI_CALL)
        .scalar_subquery()
    )
    return (
        select(
            PipelineRun,
            Account.name,
            Service.name,
            SignalQuestion.key,
            AppUser.display_name,
            ai_cost_eur,
        )
        .outerjoin(Account, Account.id == PipelineRun.account_id)
        .outerjoin(Service, Service.id == PipelineRun.service_id)
        .outerjoin(SignalQuestion, SignalQuestion.id == PipelineRun.question_id)
        .outerjoin(AppUser, AppUser.id == PipelineRun.requested_by)
    )


def _to_view(row: Sequence[Any]) -> RunView:
    run: PipelineRun = row[0]
    account_name, service_name, question_key, requester_name, ai_cost_eur = row[1:]
    return RunView(
        id=run.id,
        kind=run.kind,
        trigger=run.trigger,
        status=run.status,
        stage=run.stage,
        progress=run.progress,
        errors=run.errors,
        account=NamedRef(run.account_id, account_name) if run.account_id is not None else None,
        service=NamedRef(run.service_id, service_name) if run.service_id is not None else None,
        question=(
            QuestionRef(run.question_id, question_key) if run.question_id is not None else None
        ),
        requested_by_name=requester_name,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        ai_cost_eur=float(ai_cost_eur),
    )


async def read_run(session: AsyncSession, run_id: uuid.UUID) -> RunView | None:
    """The run, or `None` when no run has this id."""
    row = (await session.execute(_run_view_select().where(PipelineRun.id == run_id))).first()
    return _to_view(row) if row is not None else None


async def list_runs(
    session: AsyncSession, filters: RunFilters, *, page: int, page_size: int
) -> tuple[list[RunView], int]:
    """One page of the runs matching `filters`, newest first, and how many match in all."""
    conditions = [
        column == value
        for column, value in (
            (PipelineRun.kind, filters.kind),
            (PipelineRun.status, filters.status),
            (PipelineRun.account_id, filters.account_id),
            (PipelineRun.service_id, filters.service_id),
        )
        if value is not None
    ]
    total = (
        await session.execute(select(func.count()).select_from(PipelineRun).where(*conditions))
    ).scalar_one()
    rows = await session.execute(
        _run_view_select()
        .where(*conditions)
        .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return [_to_view(row) for row in rows], total


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> RunView:
    """`API-35`. Raises `RunNotFound`."""
    view = await read_run(session, run_id)
    if view is None:
        raise RunNotFound(f"No run {run_id}.")
    return view


async def get_runs_page(
    session: AsyncSession, filters: RunFilters, *, page: int, page_size: int
) -> tuple[list[RunView], int]:
    """`API-34`."""
    return await list_runs(session, filters, page=page, page_size=page_size)
