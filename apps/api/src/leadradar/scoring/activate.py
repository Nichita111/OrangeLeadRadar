"""Capability function for `API-18`: activate a DRAFT scoring config.

One transaction per call:
  - target config DRAFT → ACTIVE (set activated_at / activated_by)
  - previous ACTIVE → RETIRED
  - SCORING_ACTIVATED audit row
  - RESCORE pipeline_run (trigger SCORING_ACTIVATION, service_id set)
  - one SCORE job at priority 3
  - RUN_REQUESTED audit row

See [API-18](/architecture/interfaces.md#scoring) and
[Enqueueing](/architecture/services/api.md#design).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import write_run_requested, write_scoring_activated
from leadradar.core.enums import (
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
    ScoringConfigStatus,
)
from leadradar.db.models.configuration import ScoringConfig
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.scoring.errors import NotADraft, ScoringConfigNotFound

# Priority 3 for RESCORE from SCORING_ACTIVATION
# (see [Job queue](/architecture/services/worker.md#job-queue))
_RESCORE_ACTIVATION_PRIORITY = 3


@dataclass(frozen=True)
class ActivationResult:
    """The activated scoring config row, returned by the route."""

    id: uuid.UUID
    service_id: uuid.UUID
    version: int
    status: ScoringConfigStatus
    settings: dict[str, object]
    change_note: str | None
    activated_at: datetime | None
    activated_by: uuid.UUID | None
    run_id: uuid.UUID


async def activate_scoring_config(
    session: AsyncSession,
    *,
    config_id: uuid.UUID,
    actor_id: uuid.UUID,
    change_note: str,
    request_id: str | None,
    now: datetime | None = None,
) -> ActivationResult:
    """Activate a DRAFT scoring config in one transaction.

    Raises `NotADraft` when the target config is not DRAFT.
    Raises `ScoringConfigNotFound` when the config does not exist.
    """
    if now is None:
        now = datetime.now(tz=UTC)

    # Load the target config
    row = await session.get(ScoringConfig, config_id)
    if row is None:
        raise ScoringConfigNotFound(str(config_id))
    if row.status != ScoringConfigStatus.DRAFT:
        raise NotADraft(str(config_id), row.status.value)

    service_id = row.service_id

    # Find the current ACTIVE version (if any) to retire it and record previous_version
    stmt_active = select(ScoringConfig).where(
        ScoringConfig.service_id == service_id,
        ScoringConfig.status == ScoringConfigStatus.ACTIVE,
    )
    active_result = await session.execute(stmt_active)
    active_row: ScoringConfig | None = active_result.scalar_one_or_none()
    previous_version: int | None = active_row.version if active_row is not None else None

    # Retire the previous ACTIVE version
    if active_row is not None:
        await session.execute(
            update(ScoringConfig)
            .where(ScoringConfig.id == active_row.id)
            .values(status=ScoringConfigStatus.RETIRED)
        )

    # Activate the target
    await session.execute(
        update(ScoringConfig)
        .where(ScoringConfig.id == config_id)
        .values(
            status=ScoringConfigStatus.ACTIVE,
            change_note=change_note,
            activated_at=now,
            activated_by=actor_id,
        )
    )

    # Write SCORING_ACTIVATED audit
    await write_scoring_activated(
        session,
        actor_id=actor_id,
        scoring_config_id=config_id,
        version=row.version,
        previous_version=previous_version,
        change_note=change_note,
        request_id=request_id,
    )

    # Create RESCORE pipeline_run
    run_id = uuid.uuid4()
    session.add(
        PipelineRun(
            id=run_id,
            kind=PipelineRunKind.RESCORE,
            trigger=PipelineRunTrigger.SCORING_ACTIVATION,
            account_id=None,
            service_id=service_id,
            question_id=None,
            status=PipelineRunStatus.QUEUED,
            stage=None,
            progress={},
            errors=[],
            requested_by=actor_id,
            started_at=None,
            finished_at=None,
        )
    )
    # Flush so the run row gets its id before the job references it
    await session.flush()

    # Create one SCORE job
    session.add(
        Job(
            run_id=run_id,
            step=JobStep.SCORE,
            payload={"service_id": str(service_id)},
            status=JobStatus.READY,
            priority=_RESCORE_ACTIVATION_PRIORITY,
            attempts=0,
            not_before=now,
            locked_by=None,
            locked_at=None,
            last_error=None,
        )
    )

    # Write RUN_REQUESTED audit
    await write_run_requested(
        session,
        actor_id=actor_id,
        run_id=run_id,
        kind=PipelineRunKind.RESCORE.value,
        trigger=PipelineRunTrigger.SCORING_ACTIVATION.value,
        request_id=request_id,
    )

    # Reload to return the updated row
    await session.flush()
    updated = await session.get(ScoringConfig, config_id)
    assert updated is not None  # just wrote it

    return ActivationResult(
        id=updated.id,
        service_id=updated.service_id,
        version=updated.version,
        status=updated.status,
        settings=dict(updated.settings),
        change_note=updated.change_note,
        activated_at=updated.activated_at,
        activated_by=updated.activated_by,
        run_id=run_id,
    )
