"""Reads that shape [`AlertView`](/architecture/interfaces.md#alertview) (`API-48`, `API-49`) out
of the [`alert`](/architecture/sql-store.md#alert) store. Plain dataclasses, not Pydantic models:
those live at the api boundary (`api/feedback_and_alerts.py`), which shapes its response from
these."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from leadradar.alerts.errors import AlertNotFound
from leadradar.core.enums import AccountScoreBand, AlertKind, FindingStrength
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import Service, SignalQuestion
from leadradar.db.models.identity import AppUser
from leadradar.db.models.signals import AccountScore, Alert, Finding
from leadradar.runs.queries import NamedRef


@dataclass(frozen=True)
class AlertFindingRef:
    """`AlertView.finding`; `STRONG_SIGNAL` only."""

    id: uuid.UUID
    question_text: str
    strength: FindingStrength
    quote: str


@dataclass(frozen=True)
class AlertBandChangeRef:
    """`AlertView.band_change`; `BAND_UP` only."""

    from_band: AccountScoreBand | None
    to_band: AccountScoreBand | None


@dataclass(frozen=True)
class AlertRow:
    """[`AlertView`](/architecture/interfaces.md#alertview)."""

    id: uuid.UUID
    created_at: datetime
    acknowledged_at: datetime | None
    kind: AlertKind
    account: NamedRef
    service: NamedRef
    finding: AlertFindingRef | None
    band_change: AlertBandChangeRef | None
    acknowledged_by_name: str | None


@dataclass(frozen=True)
class AlertFilters:
    """The query of `API-48`; `None` does not filter. `unread` filters only when true, per
    `API-48`'s note that a falsy value lists every alert."""

    service_id: uuid.UUID | None
    unread: bool | None


def _alert_select() -> Select[Any]:
    previous_score = aliased(AccountScore)
    previous_band = (
        select(previous_score.band)
        .where(
            previous_score.account_id == AccountScore.account_id,
            previous_score.service_id == AccountScore.service_id,
            previous_score.as_of < AccountScore.as_of,
        )
        .order_by(previous_score.as_of.desc())
        .limit(1)
        .correlate(AccountScore)
        .scalar_subquery()
    )
    return (
        select(
            Alert,
            Account.name,
            Service.name,
            Finding.id,
            SignalQuestion.text,
            Finding.strength,
            Finding.quote,
            AccountScore.band,
            previous_band,
            AppUser.display_name,
        )
        .join(Account, Account.id == Alert.account_id)
        .join(Service, Service.id == Alert.service_id)
        .outerjoin(Finding, Finding.id == Alert.finding_id)
        .outerjoin(SignalQuestion, SignalQuestion.id == Finding.question_id)
        .outerjoin(AccountScore, AccountScore.id == Alert.score_id)
        .outerjoin(AppUser, AppUser.id == Alert.acknowledged_by)
    )


def _to_row(row: Any) -> AlertRow:
    (
        alert,
        account_name,
        service_name,
        finding_id,
        question_text,
        strength,
        quote,
        band,
        previous_band,
        acknowledged_by_name,
    ) = row
    finding = (
        AlertFindingRef(id=finding_id, question_text=question_text, strength=strength, quote=quote)
        if alert.kind == AlertKind.STRONG_SIGNAL and finding_id is not None
        else None
    )
    band_change = (
        AlertBandChangeRef(from_band=previous_band, to_band=band)
        if alert.kind == AlertKind.BAND_UP
        else None
    )
    return AlertRow(
        id=alert.id,
        created_at=alert.created_at,
        acknowledged_at=alert.acknowledged_at,
        kind=alert.kind,
        account=NamedRef(id=alert.account_id, name=account_name),
        service=NamedRef(id=alert.service_id, name=service_name),
        finding=finding,
        band_change=band_change,
        acknowledged_by_name=acknowledged_by_name,
    )


async def list_alerts(
    session: AsyncSession, filters: AlertFilters, *, page: int, page_size: int
) -> tuple[list[AlertRow], int]:
    """`API-48`: newest first, filtered by service and, when `unread` is true, to unacknowledged
    alerts only."""
    conditions = []
    if filters.service_id is not None:
        conditions.append(Alert.service_id == filters.service_id)
    if filters.unread:
        conditions.append(Alert.acknowledged_at.is_(None))
    total = (
        await session.execute(select(func.count()).select_from(Alert).where(*conditions))
    ).scalar_one()
    rows = (
        await session.execute(
            _alert_select()
            .where(*conditions)
            .order_by(Alert.created_at.desc(), Alert.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    return [_to_row(row) for row in rows], total


async def get_alert(session: AsyncSession, alert_id: uuid.UUID) -> AlertRow:
    """Raises `AlertNotFound` when `alert_id` names no alert."""
    row = (await session.execute(_alert_select().where(Alert.id == alert_id))).first()
    if row is None:
        raise AlertNotFound(f"No alert {alert_id}.")
    return _to_row(row)
