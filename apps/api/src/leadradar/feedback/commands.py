"""[Feedback effects](/architecture/rules.md#feedback-effects) (`S-EVL-01`, `S-EVL-02`), the
api's half: writes `lead_feedback` or `finding_feedback`, the status and label side effects, the
audit row, and enqueues the worker's rescore — all in one transaction
([api Design](/architecture/services/api.md#design) Transactions). `API-46` and `API-47` call
these; neither writes a score nor `RUN_REQUESTED` (G4: only `LEAD_FEEDBACK_GIVEN` or
`FINDING_FEEDBACK_GIVEN`)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.core.enums import (
    AuditAction,
    EvaluationItemOrigin,
    FindingFeedbackVerdict,
    LeadFeedbackVerdict,
    PipelineRunTrigger,
)
from leadradar.core.feedback import derived_label, finding_status_after
from leadradar.db.models.configuration import SignalQuestion
from leadradar.db.models.feedback import EvaluationItem, FindingFeedback, LeadFeedback
from leadradar.db.models.identity import AppUser
from leadradar.db.models.signals import Finding
from leadradar.feedback.errors import FindingNotFound, ScoreNotFound
from leadradar.feedback.queries import (
    FeedbackSummary,
    FindingViewData,
    LeadFeedbackResult,
    current_score_id,
    read_finding_view,
)
from leadradar.runs.enqueue import enqueue_account_rescore


async def give_lead_feedback(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    verdict: LeadFeedbackVerdict,
    note: str | None,
    principal: AppUser,
    now: datetime,
) -> LeadFeedbackResult:
    """`API-46`. Raises `ScoreNotFound` when the account has no current score for the service
    (D2 of [Feedback and alerts](/architecture/interfaces.md#feedback-and-alerts))."""
    async with session.begin():
        score_id = await current_score_id(session, account_id, service_id)
        if score_id is None:
            raise ScoreNotFound(f"No current score for account {account_id}, service {service_id}.")

        feedback = LeadFeedback(
            account_id=account_id,
            service_id=service_id,
            user_id=principal.id,
            score_id=score_id,
            verdict=verdict,
            note=note,
        )
        session.add(feedback)
        await session.flush()

        await append_audit_event(
            session,
            occurred_at=now,
            actor_id=principal.id,
            action=AuditAction.LEAD_FEEDBACK_GIVEN,
            entity_type="lead_feedback",
            entity_id=feedback.id,
            payload={"verdict": verdict.value},
        )

        await enqueue_account_rescore(
            session,
            account_id=account_id,
            service_id=service_id,
            trigger=PipelineRunTrigger.FEEDBACK,
            requested_by=principal.id,
            now=now,
        )

        result = LeadFeedbackResult(
            id=feedback.id,
            verdict=verdict,
            note=note,
            created_at=feedback.created_at,
            user_name=principal.display_name,
        )
    return result


async def give_finding_feedback(
    session: AsyncSession,
    *,
    finding_id: uuid.UUID,
    verdict: FindingFeedbackVerdict,
    note: str | None,
    principal: AppUser,
    now: datetime,
) -> FindingViewData:
    """`API-47`. Raises `FindingNotFound` when `finding_id` names no finding."""
    async with session.begin():
        finding = (
            await session.execute(select(Finding).where(Finding.id == finding_id).with_for_update())
        ).scalar_one_or_none()
        if finding is None:
            raise FindingNotFound(f"No finding {finding_id}.")

        question = (
            await session.execute(
                select(SignalQuestion).where(SignalQuestion.id == finding.question_id)
            )
        ).scalar_one()
        revision_is_current = finding.question_revision == question.revision

        feedback = FindingFeedback(
            finding_id=finding_id, user_id=principal.id, verdict=verdict, note=note
        )
        session.add(feedback)
        await session.flush()

        finding.status = finding_status_after(
            finding.status, verdict, revision_is_current=revision_is_current
        )

        manual_label_exists = (
            await session.execute(
                select(EvaluationItem.id).where(
                    EvaluationItem.chunk_id == finding.chunk_id,
                    EvaluationItem.question_id == finding.question_id,
                    EvaluationItem.question_revision == finding.question_revision,
                    EvaluationItem.origin == EvaluationItemOrigin.MANUAL,
                )
            )
        ).first() is not None

        label = derived_label(
            verdict,
            finding.strength,
            revision_is_current=revision_is_current,
            manual_label_exists=manual_label_exists,
        )
        if label is not None:
            existing_item = (
                await session.execute(
                    select(EvaluationItem).where(
                        EvaluationItem.chunk_id == finding.chunk_id,
                        EvaluationItem.question_id == finding.question_id,
                        EvaluationItem.question_revision == finding.question_revision,
                        EvaluationItem.origin == EvaluationItemOrigin.FINDING_FEEDBACK,
                    )
                )
            ).scalar_one_or_none()
            if existing_item is None:
                session.add(
                    EvaluationItem(
                        chunk_id=finding.chunk_id,
                        question_id=finding.question_id,
                        question_revision=finding.question_revision,
                        expected_strength=label.expected_strength,
                        origin=EvaluationItemOrigin.FINDING_FEEDBACK,
                        labelled_by=principal.id,
                        status=label.status,
                    )
                )
            else:
                existing_item.expected_strength = label.expected_strength
                existing_item.status = label.status
                existing_item.labelled_by = principal.id

        await append_audit_event(
            session,
            occurred_at=now,
            actor_id=principal.id,
            action=AuditAction.FINDING_FEEDBACK_GIVEN,
            entity_type="finding_feedback",
            entity_id=feedback.id,
            payload={"verdict": verdict.value},
        )

        await enqueue_account_rescore(
            session,
            account_id=finding.account_id,
            service_id=question.service_id,
            trigger=PipelineRunTrigger.FEEDBACK,
            requested_by=principal.id,
            now=now,
        )

        view = await read_finding_view(
            session,
            finding=finding,
            question=question,
            feedback=FeedbackSummary(
                verdict=verdict, user_name=principal.display_name, created_at=feedback.created_at
            ),
        )
    return view
