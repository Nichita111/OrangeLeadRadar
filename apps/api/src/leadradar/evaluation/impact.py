"""[Impact](/architecture/rules.md#impact) (`API-77`): gathers the aggregates of the rule's
Inputs from `pipeline_run`, `audit_event`, `finding` (through `classification`) and
`evaluation_result` in one transaction, then applies the pure rule of `core.impact`. Writes
nothing."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Float, Interval, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AuditEventKind, PipelineRunKind, PipelineRunStatus
from leadradar.core.impact import ImpactInputs, ImpactReport, compute_impact
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.feedback import EvaluationResult
from leadradar.db.models.ingestion import PipelineRun
from leadradar.db.models.signals import Classification, Finding
from leadradar.settings import ApiSettings

_COUNTED_STATUSES = (PipelineRunStatus.SUCCEEDED, PipelineRunStatus.PARTIAL)


async def read_impact(session: AsyncSession, settings: ApiSettings, now: datetime) -> ImpactReport:
    """`API-77`'s capability function: the aggregate queries of [Impact]
    (/architecture/rules.md#impact)'s Inputs, then the pure rule. Writes nothing."""
    period_start = now - timedelta(days=settings.impact_period_days)
    is_counted_run = (
        PipelineRun.kind == PipelineRunKind.ACCOUNT_REFRESH,
        PipelineRun.status.in_(_COUNTED_STATUSES),
        PipelineRun.finished_at >= period_start,
        PipelineRun.finished_at <= now,
    )
    counted_run_ids = select(PipelineRun.id).where(*is_counted_run).scalar_subquery()
    run_duration = cast(PipelineRun.finished_at - PipelineRun.started_at, Interval)

    refreshes, accounts_refreshed, total_duration = (
        await session.execute(
            select(
                func.count(PipelineRun.id),
                func.count(func.distinct(PipelineRun.account_id)),
                func.sum(run_duration),
            ).where(*is_counted_run)
        )
    ).one()

    total_cost = (
        await session.execute(
            select(func.sum(cast(AuditEvent.payload["cost_eur"].astext, Float))).where(
                AuditEvent.kind == AuditEventKind.AI_CALL,
                AuditEvent.run_id.in_(counted_run_ids),
            )
        )
    ).scalar_one()

    findings_created = (
        await session.execute(
            select(func.count(Finding.id))
            .select_from(Finding)
            .join(Classification, Finding.classification_id == Classification.id)
            .where(Classification.run_id.in_(counted_run_ids))
        )
    ).scalar_one()

    latest_passing = (
        await session.execute(
            select(
                EvaluationResult.items,
                cast(EvaluationResult.metrics["precision"].astext, Float),
            )
            .where(EvaluationResult.passed.is_(True))
            .order_by(EvaluationResult.created_at.desc())
            .limit(1)
        )
    ).first()
    latest_passing_labelled_items, latest_passing_precision = (
        latest_passing if latest_passing is not None else (None, None)
    )

    inputs = ImpactInputs(
        refreshes=refreshes,
        accounts_refreshed=accounts_refreshed,
        total_ai_call_cost_eur=total_cost if total_cost is not None else 0.0,
        total_run_duration=total_duration if total_duration is not None else timedelta(),
        findings_created=findings_created,
        latest_passing_precision=latest_passing_precision,
        latest_passing_labelled_items=latest_passing_labelled_items,
        period_days=settings.impact_period_days,
        manual_minutes_per_account=settings.manual_research_minutes_per_account,
    )
    return compute_impact(inputs)
