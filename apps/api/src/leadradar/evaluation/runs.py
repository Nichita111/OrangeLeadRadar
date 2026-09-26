"""Requesting a quality check and reading its results (`API-53` to `API-55`): thin wrappers over
`runs.enqueue.enqueue_evaluation` and `runs.queries`, plus the `errors` enrichment `API-55`
adds on read."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.core.enums import (
    AuditAction,
    DocumentTriageClassifier,
    PipelineRunKind,
    PipelineRunTrigger,
)
from leadradar.db.models.configuration import SignalQuestion
from leadradar.db.models.feedback import EvaluationItem, EvaluationResult
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Chunk, Document
from leadradar.evaluation.errors import ResultNotFound
from leadradar.runs.enqueue import enqueue_evaluation
from leadradar.runs.queries import RunView, read_run

# --- Shapes --------------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationRunRequested:
    """`API-53`'s result: the run, and whether this request created it (`202`) or found one
    already queued or running (`200`, D2)."""

    run: RunView
    created: bool


@dataclass(frozen=True)
class EvaluationResultSummaryView:
    """[`EvaluationResultSummary`](/architecture/interfaces.md#evaluationresultsummary)."""

    run_id: uuid.UUID
    created_at: datetime
    classifier: DocumentTriageClassifier
    items: int
    passed: bool
    precision: float | None
    recall: float | None
    escalation_rate: float | None


@dataclass(frozen=True)
class EvaluationResultDetailView:
    """[`EvaluationResult`](/architecture/interfaces.md#evaluationresult): every field of
    `EvaluationResultSummary`, the gate in force, and `metrics` with each `errors` entry
    enriched with `question_key`, `passage_text` and `document {title, url}`."""

    summary: EvaluationResultSummaryView
    escalation_lower: float
    escalation_upper: float
    min_precision: float
    min_items: int
    escalation_rate_target: float
    metrics: dict[str, object]


def _to_summary(result: EvaluationResult) -> EvaluationResultSummaryView:
    metrics = cast(dict[str, Any], result.metrics)
    return EvaluationResultSummaryView(
        run_id=result.run_id,
        created_at=result.created_at,
        classifier=result.classifier,
        items=result.items,
        passed=result.passed,
        precision=metrics.get("precision"),
        recall=metrics.get("recall"),
        escalation_rate=metrics.get("escalation_rate"),
    )


async def _enrich_error(session: AsyncSession, error: dict[str, Any]) -> dict[str, Any]:
    """One `errors` entry of `metrics`, with `question_key`, `passage_text` and `document`
    `{title, url}` added on read (`API-55`)."""
    item = await session.get(EvaluationItem, uuid.UUID(str(error["item_id"])))
    if item is None:
        # The item was deleted since the run: the enrichment is skipped rather than invented.
        return error
    question = await session.get(SignalQuestion, item.question_id)
    chunk = await session.get(Chunk, item.chunk_id)
    document = await session.get(Document, chunk.document_id) if chunk is not None else None
    return {
        **error,
        "question_key": question.key if question is not None else None,
        "passage_text": chunk.text if chunk is not None else None,
        "document": (
            {"title": document.title, "url": document.url} if document is not None else None
        ),
    }


async def _enriched_metrics(session: AsyncSession, metrics: dict[str, Any]) -> dict[str, object]:
    errors = metrics.get("errors")
    if not isinstance(errors, list):
        return metrics
    enriched = [await _enrich_error(session, error) for error in errors]
    return {**metrics, "errors": enriched}


# --- Commands and reads ----------------------------------------------------------------------


async def request_quality_check(
    session: AsyncSession, *, principal: AppUser, now: datetime
) -> EvaluationRunRequested:
    """`API-53`: enqueues a `USER` `EVALUATION` run with its `RUN_REQUESTED` audit row, or
    returns the one already queued or running (D2)."""
    run_id, created = await enqueue_evaluation(session, requested_by=principal.id, now=now)
    if created:
        await append_audit_event(
            session,
            action=AuditAction.RUN_REQUESTED,
            occurred_at=now,
            actor_id=principal.id,
            entity_type="pipeline_run",
            entity_id=run_id,
            payload={
                "kind": PipelineRunKind.EVALUATION.value,
                "trigger": PipelineRunTrigger.USER.value,
            },
            run_id=run_id,
        )
    view = await read_run(session, run_id)
    await session.commit()
    assert view is not None, "the run was just inserted in this transaction"
    return EvaluationRunRequested(run=view, created=created)


async def read_results(session: AsyncSession) -> list[EvaluationResultSummaryView]:
    """`API-54`: every [`evaluation_result`](/architecture/sql-store.md#evaluation_result),
    newest first (D8)."""
    rows = (
        await session.execute(select(EvaluationResult).order_by(EvaluationResult.created_at.desc()))
    ).scalars()
    return [_to_summary(result) for result in rows]


async def read_result(session: AsyncSession, run_id: uuid.UUID) -> EvaluationResultDetailView:
    """`API-55`. Raises `ResultNotFound`."""
    result = (
        await session.execute(select(EvaluationResult).where(EvaluationResult.run_id == run_id))
    ).scalar_one_or_none()
    if result is None:
        raise ResultNotFound(f"No evaluation result for run {run_id}.")
    metrics = await _enriched_metrics(session, cast(dict[str, Any], result.metrics))
    return EvaluationResultDetailView(
        summary=_to_summary(result),
        escalation_lower=result.escalation_lower,
        escalation_upper=result.escalation_upper,
        min_precision=result.min_precision,
        min_items=result.min_items,
        escalation_rate_target=result.escalation_rate_target,
        metrics=metrics,
    )
