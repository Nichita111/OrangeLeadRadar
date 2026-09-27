"""SCORE worker step: recompute account scores.

[Rescoring](/architecture/rules.md#rescoring),
[Run lifecycle](/architecture/services/worker.md#run-lifecycle).

For each account and service in the run's scope: loads in-force findings, feedback and overrides,
calls `score_account`, applies `rescore_decision`, inserts the new row and fires alerts on change.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AccountScoreBand,
    AccountStatus,
    AlertKind,
    DisqualifierOverrideStatus,
    FindingStatus,
    ScoringConfigStatus,
    ServiceStatus,
)
from leadradar.core.scoring.alerts import alerts
from leadradar.core.scoring.breakdown import ScoreInputs, ScoreResult, score_account
from leadradar.core.scoring.rescore import WriteNewRow, rescore_decision
from leadradar.core.scoring.settings import ScoringSettings
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import ScoringConfig, Service
from leadradar.db.models.feedback import LeadFeedback
from leadradar.db.models.ingestion import PipelineRun
from leadradar.db.models.signals import AccountScore, Alert, DisqualifierOverride, Finding


async def run_score_step(
    session: AsyncSession,
    *,
    run: PipelineRun,
    alert_max_age_days: int,
    now: datetime,
) -> None:
    """Execute the SCORE step for `run`.

    Its scope is its run's `account_id` and `service_id` ([Run lifecycle]
    (/architecture/services/worker.md#run-lifecycle)): the run's account, else every active
    account, for the run's service, else every active service. Each pair whose service has an
    `ACTIVE` scoring config is scored with `score_account`, `rescore_decision` is applied, and on
    a change the new row is inserted and alerts are created. The run's status is settled by the
    job loop, not here.
    """
    as_of: datetime = run.started_at or now
    accounts = await _load_active_accounts(session, run.account_id)
    service_ids = (
        [run.service_id] if run.service_id is not None else await _load_active_service_ids(session)
    )
    for service_id in service_ids:
        config = await _load_active_config(session, service_id)
        if config is None:
            continue
        await _score_service(
            session,
            run_id=run.id,
            service_id=service_id,
            config=config,
            accounts=accounts,
            as_of=as_of,
            alert_max_age_days=alert_max_age_days,
        )


async def _score_service(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    service_id: uuid.UUID,
    config: ScoringConfig,
    accounts: list[Account],
    as_of: datetime,
    alert_max_age_days: int,
) -> None:
    settings = ScoringSettings.model_validate(config.settings)
    scoring_config_id = str(config.id)
    settings_version = config.version
    settings_dict = dict(config.settings)

    # Load question polarity from the question_settings_with_polarity form
    q_polarity_map = await _load_question_polarity(session, service_id, settings)

    for account in accounts:
        account_id = account.id
        attributes = _account_to_attributes(account)

        # Load in-force findings for this account + service
        findings_list = await _load_inforce_findings(session, account_id, service_id)

        # Load in-force lead feedback
        feedback_verdict = await _load_lead_feedback(session, account_id, service_id)

        # Load ACTIVE overrides
        overrides_list = await _load_active_overrides(session, account_id, service_id)

        inputs = ScoreInputs(
            account_id=str(account_id),
            service_id=str(service_id),
            scoring_config_id=scoring_config_id,
            settings_version=settings_version,
            attributes=attributes,
            findings=findings_list,
            lead_feedback_verdict=feedback_verdict,
            active_overrides=overrides_list,
            question_settings_with_polarity=q_polarity_map,
        )

        result = score_account(inputs, as_of=as_of, settings=settings)

        # Load current score row for comparison
        current_row = await _load_current_score(session, account_id, service_id)

        decision = rescore_decision(result, current_row)

        if isinstance(decision, WriteNewRow):
            previous_band = _get_band(current_row)
            new_score_id = await _write_new_score(
                session,
                account_id=account_id,
                service_id=service_id,
                run_id=run_id,
                as_of=as_of,
                result=decision.result,
                current_row=current_row,
            )
            # RESCORE runs have no new findings; new findings come from refresh SCORE stage
            alert_list = alerts(
                new_score_id=str(new_score_id),
                new_standing=result.standing,
                new_band=result.band,
                previous_band=previous_band,
                new_findings=[],  # empty for RESCORE; refresh pipeline fills this
                active_settings=settings_dict,
                alert_max_age_days=alert_max_age_days,
                as_of=as_of,
                account_id=str(account_id),
                service_id=str(service_id),
            )
            for alert in alert_list:
                session.add(
                    Alert(
                        account_id=uuid.UUID(alert.account_id),
                        service_id=uuid.UUID(alert.service_id),
                        kind=alert.kind,
                        finding_id=uuid.UUID(alert.finding_id) if alert.finding_id else None,
                        score_id=new_score_id if alert.kind == AlertKind.BAND_UP else None,
                        acknowledged_by=None,
                        acknowledged_at=None,
                    )
                )


async def _load_active_config(session: AsyncSession, service_id: uuid.UUID) -> ScoringConfig | None:
    stmt = select(ScoringConfig).where(
        ScoringConfig.service_id == service_id,
        ScoringConfig.status == ScoringConfigStatus.ACTIVE,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_question_polarity(
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


async def _load_active_accounts(
    session: AsyncSession, account_id: uuid.UUID | None
) -> list[Account]:
    """The ACTIVE account of the run, or every ACTIVE account when the run names none."""
    stmt = select(Account).where(Account.status == AccountStatus.ACTIVE)
    if account_id is not None:
        stmt = stmt.where(Account.id == account_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _load_active_service_ids(session: AsyncSession) -> list[uuid.UUID]:
    stmt = select(Service.id).where(Service.status == ServiceStatus.ACTIVE)
    return list((await session.execute(stmt)).scalars())


async def _load_inforce_findings(
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


async def _load_lead_feedback(
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


async def _load_active_overrides(
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


def _account_to_attributes(account: Account) -> dict[str, object]:
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


async def _load_current_score(
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


async def _write_new_score(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    run_id: uuid.UUID,
    as_of: datetime,
    result: ScoreResult,
    current_row: dict[str, object] | None,
) -> uuid.UUID:
    """Insert new score row as current, clearing the previous one."""
    # Clear previous is_current
    await session.execute(
        update(AccountScore)
        .where(
            AccountScore.account_id == account_id,
            AccountScore.service_id == service_id,
            AccountScore.is_current.is_(True),
        )
        .values(is_current=False)
    )
    new_id = uuid.uuid4()
    session.add(
        AccountScore(
            id=new_id,
            account_id=account_id,
            service_id=service_id,
            scoring_config_id=uuid.UUID(result.scoring_config_id),
            run_id=run_id,
            as_of=as_of,
            fit=result.fit,
            intent=result.intent,
            priority=result.priority,
            standing=result.standing,
            band=result.band,
            breakdown=result.breakdown,
            is_current=True,
        )
    )
    await session.flush()
    return new_id


def _get_band(current_row: dict[str, object] | None) -> AccountScoreBand | None:
    """Extract the band from a stored row dict."""
    if current_row is None:
        return None
    band_str = current_row.get("band")
    if band_str is None:
        return None
    try:
        return AccountScoreBand(str(band_str))
    except ValueError:
        return None
