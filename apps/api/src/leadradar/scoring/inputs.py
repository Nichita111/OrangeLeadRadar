"""Store access for the inputs [Rescoring](/architecture/rules.md#rescoring) reads: an account's
attributes, its in-force findings, lead feedback and overrides, the question polarities of a
settings document and the current score row. Shared by the worker's SCORE step and the api's
scoring preview (`API-19`), so both score from the same inputs."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AccountStatus, DisqualifierOverrideStatus, FindingStatus
from leadradar.core.scoring.settings import ScoringSettings
from leadradar.db.models.accounts import Account
from leadradar.db.models.feedback import LeadFeedback
from leadradar.db.models.signals import AccountScore, DisqualifierOverride, Finding


async def load_question_polarity(
    session: AsyncSession,
    service_id: uuid.UUID,
    settings: ScoringSettings,
) -> list[dict[str, object]]:
    """Build the question_settings_with_polarity list from DB question polarities."""
    from leadradar.core.enums import SignalQuestionStatus
    from leadradar.db.models.configuration import SignalQuestion

    # Load all ACTIVE questions for the service
    stmt = select(SignalQuestion).where(
        SignalQuestion.service_id == service_id,
        SignalQuestion.status == SignalQuestionStatus.ACTIVE,
    )
    result = await session.execute(stmt)
    questions = result.scalars().all()
    polarity_by_key: dict[str, str] = {q.key: str(q.polarity) for q in questions}

    result_list: list[dict[str, object]] = []
    for qs in settings.questions:
        polarity = polarity_by_key.get(qs.question_key, "POSITIVE")
        result_list.append(
            {
                "question_key": qs.question_key,
                "weight": qs.weight,
                "half_life_days": qs.half_life_days,
                "polarity": polarity,
            }
        )
    return result_list


async def load_active_accounts(
    session: AsyncSession, account_id: uuid.UUID | None
) -> list[Account]:
    """The ACTIVE account of the run, or every ACTIVE account when the run names none."""
    stmt = select(Account).where(Account.status == AccountStatus.ACTIVE)
    if account_id is not None:
        stmt = stmt.where(Account.id == account_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def load_inforce_findings(
    session: AsyncSession,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
) -> list[dict[str, object]]:
    """Load ACTIVE findings for this account's questions of this service."""
    from leadradar.db.models.configuration import SignalQuestion
    from leadradar.db.models.ingestion import Chunk, Document

    # Join finding → chunk → document to reach document.source_type.
    # Finding.chunk_id references chunk.id; chunk.document_id references document.id.
    stmt = (
        select(
            Finding.id,
            Finding.question_id,
            Finding.strength,
            Finding.observed_at,
            SignalQuestion.key.label("question_key"),
            Document.source_type,
        )
        .join(SignalQuestion, Finding.question_id == SignalQuestion.id)
        .join(Chunk, Finding.chunk_id == Chunk.id)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Finding.account_id == account_id,
            Finding.status == FindingStatus.ACTIVE,
            SignalQuestion.service_id == service_id,
        )
    )
    rows = await session.execute(stmt)
    results: list[dict[str, object]] = []
    for row in rows:
        results.append(
            {
                "id": str(row.id),
                "question_key": row.question_key,
                "strength": str(row.strength),
                "observed_at": row.observed_at,
                "source_type": str(row.source_type),
            }
        )
    return results


async def load_lead_feedback(
    session: AsyncSession,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
) -> str | None:
    """Return the in-force lead feedback verdict, or None."""
    stmt = (
        select(LeadFeedback.verdict)
        .where(
            LeadFeedback.account_id == account_id,
            LeadFeedback.service_id == service_id,
        )
        .order_by(LeadFeedback.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return str(row) if row is not None else None


async def load_active_overrides(
    session: AsyncSession,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
) -> list[dict[str, object]]:
    """Load ACTIVE disqualifier_override rows."""
    stmt = select(DisqualifierOverride).where(
        DisqualifierOverride.account_id == account_id,
        DisqualifierOverride.service_id == service_id,
        DisqualifierOverride.status == DisqualifierOverrideStatus.ACTIVE,
    )
    result = await session.execute(stmt)
    return [{"id": str(row.id), "rule_key": row.rule_key} for row in result.scalars().all()]


def account_to_attributes(account: Account) -> dict[str, object]:
    """Convert Account model to flat attributes dict."""
    return {
        "industry": account.industry,
        "country_code": account.country_code,
        "employee_count": account.employee_count,
        "revenue_eur": account.revenue_eur,
        "operational_complexity": (
            str(account.operational_complexity)
            if account.operational_complexity is not None
            else None
        ),
    }


async def load_current_score(
    session: AsyncSession,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
) -> dict[str, object] | None:
    """Return the current `account_score` row as a dict, or None."""
    stmt = select(AccountScore).where(
        AccountScore.account_id == account_id,
        AccountScore.service_id == service_id,
        AccountScore.is_current.is_(True),
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return {
        "id": row.id,
        "scoring_config_id": str(row.scoring_config_id),
        "fit": row.fit,
        "intent": row.intent,
        "priority": row.priority,
        "standing": str(row.standing),
        "band": str(row.band) if row.band is not None else None,
        "breakdown": row.breakdown,
    }
