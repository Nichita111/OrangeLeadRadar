"""Reads the account, service, current [`account_score`](/architecture/sql-store.md#account_score)
and the findings `top_finding_ids` selects, for `API-59`'s push. Plain dataclasses, not Pydantic
models: those live at the api boundary (`api/outreach_and_crm.py`)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AccountScoreBand,
    AccountScoreStanding,
    CrmSyncStatus,
    CrmSyncTarget,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import Service, SignalQuestion
from leadradar.db.models.signals import AccountScore, Finding
from leadradar.outreach.company_push import (
    TopSignalText,
    intent_question_entries,
    top_finding_ids,
)


@dataclass(frozen=True)
class PushInputs:
    """What `build_company_push` and the [`crm_sync`](/architecture/sql-store.md#crm_sync) write
    need, read once for the account and service."""

    account_domain: str
    account_name: str
    service_name: str
    score_id: uuid.UUID
    priority: int
    band: AccountScoreBand | None
    standing: AccountScoreStanding
    top_signals: list[TopSignalText]


@dataclass(frozen=True)
class CrmSyncResult:
    """[`CrmSyncView`](/architecture/interfaces.md#crmsyncview), the response of `API-59`."""

    id: uuid.UUID
    external_id: str | None
    error: str | None
    created_at: datetime
    target: CrmSyncTarget
    status: CrmSyncStatus


async def read_push_inputs(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID, top_signals_limit: int
) -> PushInputs | None:
    """`None` when the account has no current
    [`account_score`](/architecture/sql-store.md#account_score) for the service."""
    row = (
        await session.execute(
            select(
                AccountScore.id,
                AccountScore.priority,
                AccountScore.band,
                AccountScore.standing,
                AccountScore.breakdown,
                Account.domain,
                Account.name,
                Service.name,
            )
            .join(Account, Account.id == AccountScore.account_id)
            .join(Service, Service.id == AccountScore.service_id)
            .where(
                AccountScore.account_id == account_id,
                AccountScore.service_id == service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).first()
    if row is None:
        return None
    score_id, priority, band, standing, breakdown, domain, account_name, service_name = row

    finding_ids = {
        uuid.UUID(str(entry["finding_id"]))
        for entry in (intent_question_entries(breakdown) if isinstance(breakdown, dict) else [])
        if isinstance(entry, dict) and isinstance(entry.get("finding_id"), str)
    }

    observed_at_by_finding: dict[str, datetime] = {}
    signal_by_finding: dict[str, TopSignalText] = {}
    if finding_ids:
        finding_rows = (
            await session.execute(
                select(Finding.id, Finding.observed_at, Finding.quote, SignalQuestion.text)
                .join(SignalQuestion, SignalQuestion.id == Finding.question_id)
                .where(Finding.id.in_(finding_ids))
            )
        ).all()
        for finding_id, observed_at, quote, question_text in finding_rows:
            key = str(finding_id)
            observed_at_by_finding[key] = observed_at
            signal_by_finding[key] = TopSignalText(question_text=question_text, quote=quote)

    selected_ids = top_finding_ids(breakdown, observed_at_by_finding, top_signals_limit)

    return PushInputs(
        account_domain=domain,
        account_name=account_name,
        service_name=service_name,
        score_id=score_id,
        priority=priority,
        band=band,
        standing=standing,
        top_signals=[signal_by_finding[finding_id] for finding_id in selected_ids],
    )
