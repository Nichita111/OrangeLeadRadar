"""SCORE worker step: recompute account scores for a service.

[Rescoring](/architecture/rules.md#rescoring),
[Run lifecycle](/architecture/services/worker.md#run-lifecycle).

For each active account of the run's service: loads in-force findings, feedback and overrides,
calls `score_account`, applies `rescore_decision`, inserts the new row and fires alerts on change.
Updates `pipeline_run` stage/progress and writes `RUN_FINISHED` at the end.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import write_run_finished
from leadradar.core.enums import (
    AccountScoreBand,
    AccountStatus,
    AlertKind,
    DisqualifierOverrideStatus,
    FindingStatus,
    PipelineRunStage,
    PipelineRunStatus,
    ScoringConfigStatus,
)
from leadradar.core.scoring.alerts import alerts
from leadradar.core.scoring.breakdown import ScoreInputs, ScoreResult, score_account
from leadradar.core.scoring.rescore import WriteNewRow, rescore_decision
from leadradar.core.scoring.settings import ScoringSettings
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import ScoringConfig
from leadradar.db.models.feedback import LeadFeedback
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.db.models.signals import AccountScore, Alert, DisqualifierOverride, Finding


async def run_score_step(
    session: AsyncSession,
    *,
    job: Job,
    run: PipelineRun,
    worker_instance_id: str,
    alert_max_age_days: int,
) -> None:
    """Execute the SCORE step for `run`.

    Loads the ACTIVE scoring config for the run's service; for each active account
    calls `score_account`, applies `rescore_decision`, and on a change inserts the new
    score row and creates alerts.
    """
    raw_service_id = run.service_id
    if raw_service_id is None:
        raise ValueError(f"SCORE step: run {run.id} has no service_id")
    service_id: uuid.UUID = raw_service_id
    as_of: datetime = run.started_at or datetime.now(tz=UTC)

    # Load ACTIVE scoring config
    config = await _load_active_config(session, service_id)
    if config is None:
        # No active scoring config — nothing to score
        await _finish_run(session, run_id=run.id, status=PipelineRunStatus.SUCCEEDED, progress={})
        return

    settings = ScoringSettings.model_validate(config.settings)
    scoring_config_id = str(config.id)
    settings_version = config.version
    settings_dict = dict(config.settings)

    # Load question polarity from the question_settings_with_polarity form
    q_polarity_map = await _load_question_polarity(session, service_id, settings)

    # Update run stage
    await session.execute(
        update(PipelineRun)
        .where(PipelineRun.id == run.id)
        .values(stage=PipelineRunStage.SCORE)
    )

    accounts = await _load_active_accounts(session, service_id)
    scored = 0
    changed = 0

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
                run_id=run.id,
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
            changed += 1

        scored += 1

    progress: dict[str, object] = {"scored": scored, "changed": changed}
    await _finish_run(
        session,
        run_id=run.id,
        status=PipelineRunStatus.SUCCEEDED,
        progress=progress,
    )


async def _load_active_config(
    session: AsyncSession, service_id: uuid.UUID
) -> ScoringConfig | None:
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
    session: AsyncSession, service_id: uuid.UUID
) -> list[Account]:
    """Load all ACTIVE accounts. (For RESCORE, service_id scoping is via the scoring config.)"""
    stmt = select(Account).where(Account.status == AccountStatus.ACTIVE)
    result = await session.execute(stmt)
    return list(result.scalars().all())


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
    return [
        {"id": str(row.id), "rule_key": row.rule_key}
        for row in result.scalars().all()
    ]


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


async def _finish_run(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    status: PipelineRunStatus,
    progress: dict[str, object],
) -> None:
    """Set the pipeline_run finished status and write RUN_FINISHED audit."""
    now = datetime.now(tz=UTC)
    await session.execute(
        update(PipelineRun)
        .where(PipelineRun.id == run_id)
        .values(
            status=status,
            finished_at=now,
            progress=progress,
        )
    )
    await write_run_finished(
        session,
        run_id=run_id,
        status=status.value,
        progress=progress,
    )
    await session.flush()
