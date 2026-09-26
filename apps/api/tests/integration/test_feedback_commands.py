"""Integration tests of `feedback.commands.give_lead_feedback` and `give_finding_feedback`
(`S-EVL-01`, `S-EVL-02`, `API-46`, `API-47`) against a real database
([Feedback effects](/architecture/rules.md#feedback-effects) with D1, D2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import Connection, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from leadradar.core.enums import (
    AppUserRole,
    EvaluationItemOrigin,
    EvaluationItemStatus,
    FindingFeedbackVerdict,
    FindingStatus,
    FindingStrength,
    JobStatus,
    LeadFeedbackVerdict,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
    ScoringConfigStatus,
    SignalQuestionAnswerType,
)
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.feedback import EvaluationItem, FindingFeedback, LeadFeedback
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Job, PipelineRun
from leadradar.db.models.signals import AccountScore, Finding
from leadradar.feedback.commands import give_finding_feedback, give_lead_feedback
from leadradar.feedback.errors import FindingNotFound, ScoreNotFound
from leadradar.logs import request_id_var
from tests.integration import factories as f

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 15, tzinfo=UTC)


def _principal(user_id: uuid.UUID, display_name: str = "Ada Lovelace") -> AppUser:
    return AppUser(id=user_id, display_name=display_name, role=AppUserRole.SALES)


async def _count(session_conn: AsyncConnection, model: type) -> int:
    result = await session_conn.execute(select(func.count()).select_from(model))
    return result.scalar_one()


async def _make_scored_account(connection: AsyncConnection) -> tuple[uuid.UUID, uuid.UUID]:
    def _insert(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        account_id = f.make_account(conn)
        service_id = f.make_service(conn)
        scoring_config_id = f.make_scoring_config(
            conn, service_id, status=ScoringConfigStatus.ACTIVE
        )
        run_id = f.make_pipeline_run(conn)
        f.make_account_score(
            conn, account_id, service_id, scoring_config_id, run_id, is_current=True
        )
        return account_id, service_id

    return await connection.run_sync(_insert)


async def _make_user(connection: AsyncConnection, display_name: str = "Ada Lovelace") -> uuid.UUID:
    return await connection.run_sync(lambda conn: f.make_app_user(conn, display_name=display_name))


# --- give_lead_feedback ----------------------------------------------------------------------


async def test_inserts_one_lead_feedback_row_and_changes_no_account_score(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    account_id, service_id = await _make_scored_account(async_connection)
    user_id = await _make_user(async_connection)

    result = await give_lead_feedback(
        async_session,
        account_id=account_id,
        service_id=service_id,
        verdict=LeadFeedbackVerdict.RELEVANT,
        note="looks good",
        principal=_principal(user_id),
        now=NOW,
    )

    row = (
        await async_session.execute(select(LeadFeedback).where(LeadFeedback.id == result.id))
    ).scalar_one()
    assert row.user_id == user_id
    assert row.verdict == LeadFeedbackVerdict.RELEVANT
    assert row.note == "looks good"
    assert result.user_name == "Ada Lovelace"

    score_count = await _count(async_connection, AccountScore)
    assert score_count == 1  # unchanged: still only the one seeded current score


async def test_two_lead_verdicts_on_the_same_account_and_service_are_both_kept(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    account_id, service_id = await _make_scored_account(async_connection)
    user_id = await _make_user(async_connection)

    await give_lead_feedback(
        async_session,
        account_id=account_id,
        service_id=service_id,
        verdict=LeadFeedbackVerdict.RELEVANT,
        note=None,
        principal=_principal(user_id),
        now=NOW,
    )
    await give_lead_feedback(
        async_session,
        account_id=account_id,
        service_id=service_id,
        verdict=LeadFeedbackVerdict.NOT_RELEVANT,
        note=None,
        principal=_principal(user_id),
        now=NOW,
    )

    rows = (
        await async_session.execute(
            select(LeadFeedback).where(
                LeadFeedback.account_id == account_id, LeadFeedback.service_id == service_id
            )
        )
    ).all()
    assert len(rows) == 2


@pytest.mark.parametrize("case", ["unknown_account", "unknown_service", "non_current_only"])
async def test_lead_feedback_without_a_current_score_raises_score_not_found_and_writes_nothing(
    async_connection: AsyncConnection, async_session: AsyncSession, case: str
) -> None:
    user_id = await _make_user(async_connection)
    if case == "unknown_account":
        account_id, service_id = uuid.uuid4(), uuid.uuid4()
    elif case == "unknown_service":
        account_id, _ = await _make_scored_account(async_connection)
        service_id = uuid.uuid4()
    else:

        def _insert(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
            account_id = f.make_account(conn)
            service_id = f.make_service(conn)
            scoring_config_id = f.make_scoring_config(conn, service_id)
            run_id = f.make_pipeline_run(conn)
            f.make_account_score(
                conn, account_id, service_id, scoring_config_id, run_id, is_current=False
            )
            return account_id, service_id

        account_id, service_id = await async_connection.run_sync(_insert)

    audit_before = await _count(async_connection, AuditEvent)
    runs_before = await _count(async_connection, PipelineRun)

    with pytest.raises(ScoreNotFound):
        await give_lead_feedback(
            async_session,
            account_id=account_id,
            service_id=service_id,
            verdict=LeadFeedbackVerdict.RELEVANT,
            note=None,
            principal=_principal(user_id),
            now=NOW,
        )

    feedback_count = await _count(async_connection, LeadFeedback)
    assert feedback_count == 0
    assert await _count(async_connection, AuditEvent) == audit_before
    assert await _count(async_connection, PipelineRun) == runs_before


async def test_lead_feedback_writes_the_audit_row_and_no_run_requested_row(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    account_id, service_id = await _make_scored_account(async_connection)
    user_id = await _make_user(async_connection)

    token = request_id_var.set("the-request-id")
    try:
        result = await give_lead_feedback(
            async_session,
            account_id=account_id,
            service_id=service_id,
            verdict=LeadFeedbackVerdict.RELEVANT,
            note=None,
            principal=_principal(user_id),
            now=NOW,
        )
    finally:
        request_id_var.reset(token)

    audit_rows = (
        (await async_session.execute(select(AuditEvent).where(AuditEvent.entity_id == result.id)))
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    row = audit_rows[0]
    assert row.action == "LEAD_FEEDBACK_GIVEN"
    assert row.kind == "FEEDBACK"
    assert row.entity_type == "lead_feedback"
    assert row.actor_id == user_id
    assert row.payload == {"verdict": "RELEVANT"}
    assert row.request_id == "the-request-id"

    run_requested_rows = (
        (
            await async_session.execute(
                select(AuditEvent).where(AuditEvent.action == "RUN_REQUESTED")
            )
        )
        .scalars()
        .all()
    )
    assert run_requested_rows == []


async def test_lead_feedback_enqueues_one_rescore_run_with_one_score_job(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    account_id, service_id = await _make_scored_account(async_connection)
    user_id = await _make_user(async_connection)

    await give_lead_feedback(
        async_session,
        account_id=account_id,
        service_id=service_id,
        verdict=LeadFeedbackVerdict.RELEVANT,
        note=None,
        principal=_principal(user_id),
        now=NOW,
    )

    runs = (
        (
            await async_session.execute(
                select(PipelineRun).where(
                    PipelineRun.kind == PipelineRunKind.RESCORE,
                    PipelineRun.account_id == account_id,
                    PipelineRun.service_id == service_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(runs) == 1
    run = runs[0]
    assert run.trigger == PipelineRunTrigger.FEEDBACK
    assert run.requested_by == user_id
    assert run.status == PipelineRunStatus.QUEUED

    jobs = (await async_session.execute(select(Job).where(Job.run_id == run.id))).scalars().all()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.priority == 0
    assert job.status == JobStatus.READY
    assert job.attempts == 0
    assert job.not_before == NOW
    assert job.payload == {}


async def test_two_verdicts_in_a_row_create_two_rescore_runs(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    account_id, service_id = await _make_scored_account(async_connection)
    user_id = await _make_user(async_connection)

    for _ in range(2):
        await give_lead_feedback(
            async_session,
            account_id=account_id,
            service_id=service_id,
            verdict=LeadFeedbackVerdict.RELEVANT,
            note=None,
            principal=_principal(user_id),
            now=NOW,
        )

    runs = (
        (
            await async_session.execute(
                select(PipelineRun).where(
                    PipelineRun.kind == PipelineRunKind.RESCORE,
                    PipelineRun.account_id == account_id,
                    PipelineRun.service_id == service_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(runs) == 2


# --- give_finding_feedback --------------------------------------------------------------------


async def _make_finding(
    connection: AsyncConnection,
    *,
    status: FindingStatus = FindingStatus.ACTIVE,
    strength: FindingStrength = FindingStrength.MEDIUM,
    question_revision: int = 1,
    finding_revision: int | None = None,
    answer_type: SignalQuestionAnswerType = SignalQuestionAnswerType.YES_NO,
    options: list[dict[str, str]] | None = None,
    option_key: str | None = None,
) -> dict[str, uuid.UUID]:
    def _insert(conn: Connection) -> dict[str, uuid.UUID]:
        service_id = f.make_service(conn)
        question_id = f.make_signal_question(
            conn,
            service_id,
            revision=question_revision,
            answer_type=answer_type,
            options=options,
        )
        account_id = f.make_account(conn)
        run_id = f.make_pipeline_run(conn)
        document_id = f.make_document(conn, run_id)
        chunk_id = f.make_chunk(conn, document_id)
        classification_id = f.make_classification(conn, chunk_id, question_id, run_id)
        finding_id = f.make_finding(
            conn,
            account_id,
            question_id,
            classification_id,
            chunk_id,
            status=status,
            strength=strength,
            question_revision=(
                finding_revision if finding_revision is not None else question_revision
            ),
            option_key=option_key,
        )
        return {
            "service_id": service_id,
            "question_id": question_id,
            "account_id": account_id,
            "chunk_id": chunk_id,
            "finding_id": finding_id,
        }

    return await connection.run_sync(_insert)


async def test_wrong_on_an_active_finding_of_the_current_revision(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    ids = await _make_finding(async_connection, strength=FindingStrength.STRONG)
    user_id = await _make_user(async_connection)

    view = await give_finding_feedback(
        async_session,
        finding_id=ids["finding_id"],
        verdict=FindingFeedbackVerdict.WRONG,
        note=None,
        principal=_principal(user_id),
        now=NOW,
    )

    finding = (
        await async_session.execute(select(Finding).where(Finding.id == ids["finding_id"]))
    ).scalar_one()
    assert finding.status == FindingStatus.REJECTED
    assert view.status == FindingStatus.REJECTED

    items = (
        (
            await async_session.execute(
                select(EvaluationItem).where(
                    EvaluationItem.chunk_id == ids["chunk_id"],
                    EvaluationItem.question_id == ids["question_id"],
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(items) == 1
    item = items[0]
    assert item.expected_strength == FindingStrength.NONE
    assert item.status == EvaluationItemStatus.ACTIVE
    assert item.labelled_by == user_id
    assert item.origin == EvaluationItemOrigin.FINDING_FEEDBACK

    audit_rows = (
        (
            await async_session.execute(
                select(AuditEvent).where(AuditEvent.action == "FINDING_FEEDBACK_GIVEN")
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1

    runs = (
        (
            await async_session.execute(
                select(PipelineRun).where(
                    PipelineRun.kind == PipelineRunKind.RESCORE,
                    PipelineRun.account_id == ids["account_id"],
                    PipelineRun.service_id == ids["service_id"],
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(runs) == 1


async def test_correct_afterwards_reactivates_the_finding_and_updates_the_same_item(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    ids = await _make_finding(
        async_connection, status=FindingStatus.REJECTED, strength=FindingStrength.WEAK
    )
    first_user = await _make_user(async_connection, "First User")
    second_user = await _make_user(async_connection, "Second User")

    await give_finding_feedback(
        async_session,
        finding_id=ids["finding_id"],
        verdict=FindingFeedbackVerdict.WRONG,
        note=None,
        principal=_principal(first_user, "First User"),
        now=NOW,
    )
    view = await give_finding_feedback(
        async_session,
        finding_id=ids["finding_id"],
        verdict=FindingFeedbackVerdict.CORRECT,
        note=None,
        principal=_principal(second_user, "Second User"),
        now=NOW,
    )

    finding = (
        await async_session.execute(select(Finding).where(Finding.id == ids["finding_id"]))
    ).scalar_one()
    assert finding.status == FindingStatus.ACTIVE
    assert view.status == FindingStatus.ACTIVE

    items = (
        (
            await async_session.execute(
                select(EvaluationItem).where(
                    EvaluationItem.chunk_id == ids["chunk_id"],
                    EvaluationItem.question_id == ids["question_id"],
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(items) == 1
    item = items[0]
    assert item.expected_strength == FindingStrength.WEAK
    assert item.labelled_by == second_user


@pytest.mark.parametrize("manual_status", [EvaluationItemStatus.ACTIVE, EvaluationItemStatus.STALE])
async def test_a_manual_label_is_left_untouched_but_the_status_and_run_still_happen(
    async_connection: AsyncConnection,
    async_session: AsyncSession,
    manual_status: EvaluationItemStatus,
) -> None:
    ids = await _make_finding(async_connection, strength=FindingStrength.STRONG)
    user_id = await _make_user(async_connection)

    def _insert_manual(conn: Connection) -> None:
        f.make_evaluation_item(
            conn,
            ids["chunk_id"],
            ids["question_id"],
            user_id,
            origin=EvaluationItemOrigin.MANUAL,
            status=manual_status,
            expected_strength=FindingStrength.WEAK,
        )

    await async_connection.run_sync(_insert_manual)

    await give_finding_feedback(
        async_session,
        finding_id=ids["finding_id"],
        verdict=FindingFeedbackVerdict.WRONG,
        note=None,
        principal=_principal(user_id),
        now=NOW,
    )

    finding = (
        await async_session.execute(select(Finding).where(Finding.id == ids["finding_id"]))
    ).scalar_one()
    assert finding.status == FindingStatus.REJECTED

    items = (
        (
            await async_session.execute(
                select(EvaluationItem).where(
                    EvaluationItem.chunk_id == ids["chunk_id"],
                    EvaluationItem.question_id == ids["question_id"],
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(items) == 1
    assert items[0].origin == EvaluationItemOrigin.MANUAL
    assert items[0].expected_strength == FindingStrength.WEAK

    audit_rows = (
        (
            await async_session.execute(
                select(AuditEvent).where(AuditEvent.action == "FINDING_FEEDBACK_GIVEN")
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    runs = (
        (
            await async_session.execute(
                select(PipelineRun).where(PipelineRun.kind == PipelineRunKind.RESCORE)
            )
        )
        .scalars()
        .all()
    )
    assert len(runs) == 1


async def test_feedback_on_an_older_revision_writes_a_stale_item_and_a_second_verdict_updates_it(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    ids = await _make_finding(
        async_connection,
        strength=FindingStrength.STRONG,
        question_revision=2,
        finding_revision=1,
    )
    user_id = await _make_user(async_connection)

    await give_finding_feedback(
        async_session,
        finding_id=ids["finding_id"],
        verdict=FindingFeedbackVerdict.CORRECT,
        note=None,
        principal=_principal(user_id),
        now=NOW,
    )
    await give_finding_feedback(
        async_session,
        finding_id=ids["finding_id"],
        verdict=FindingFeedbackVerdict.WRONG,
        note=None,
        principal=_principal(user_id),
        now=NOW,
    )

    items = (
        (
            await async_session.execute(
                select(EvaluationItem).where(
                    EvaluationItem.chunk_id == ids["chunk_id"],
                    EvaluationItem.question_id == ids["question_id"],
                    EvaluationItem.question_revision == 1,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(items) == 1
    assert items[0].status == EvaluationItemStatus.STALE
    assert items[0].expected_strength == FindingStrength.NONE

    current_revision_items = (
        (
            await async_session.execute(
                select(EvaluationItem).where(
                    EvaluationItem.chunk_id == ids["chunk_id"],
                    EvaluationItem.question_id == ids["question_id"],
                    EvaluationItem.question_revision == 2,
                )
            )
        )
        .scalars()
        .all()
    )
    assert current_revision_items == []


async def test_the_returned_view_carries_the_question_document_feedback_and_points(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    ids = await _make_finding(
        async_connection,
        answer_type=SignalQuestionAnswerType.CHOICE,
        options=[{"key": "A", "label": "Option A", "strength": "WEAK"}],
        option_key="A",
    )
    user_id = await _make_user(async_connection, "Ada Lovelace")

    def _insert_score(conn: Connection) -> None:
        scoring_config_id = f.make_scoring_config(conn, ids["service_id"])
        run_id = f.make_pipeline_run(conn)
        f.make_account_score(
            conn,
            ids["account_id"],
            ids["service_id"],
            scoring_config_id,
            run_id,
            is_current=True,
            breakdown={
                "intent": {"questions": [{"finding_id": str(ids["finding_id"]), "points": 5.5}]}
            },
        )

    await async_connection.run_sync(_insert_score)

    view = await give_finding_feedback(
        async_session,
        finding_id=ids["finding_id"],
        verdict=FindingFeedbackVerdict.CORRECT,
        note=None,
        principal=_principal(user_id, "Ada Lovelace"),
        now=NOW,
    )

    assert view.question.id == ids["question_id"]
    assert view.option is not None
    assert view.option.key == "A"
    assert view.option.label == "Option A"
    assert view.document.id is not None
    assert view.feedback is not None
    assert view.feedback.user_name == "Ada Lovelace"
    assert view.points == 5.5


async def test_points_is_null_without_a_current_score(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    ids = await _make_finding(async_connection)
    user_id = await _make_user(async_connection)

    view = await give_finding_feedback(
        async_session,
        finding_id=ids["finding_id"],
        verdict=FindingFeedbackVerdict.CORRECT,
        note=None,
        principal=_principal(user_id),
        now=NOW,
    )

    assert view.points is None


async def test_a_failure_inside_the_transaction_persists_nothing(
    async_connection: AsyncConnection,
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = await _make_finding(async_connection, strength=FindingStrength.STRONG)
    user_id = await _make_user(async_connection)
    # `_make_finding` itself inserts one `pipeline_run` for the document's classification, so the
    # runs and jobs the write under test would add are counted as a delta, not an absolute zero.
    # Audit rows too: `audit_event` is append-only and other tests of the session (the AI
    # gateway's `AI_CALL` rows) commit rows that cannot be deleted.
    runs_before = await _count(async_connection, PipelineRun)
    jobs_before = await _count(async_connection, Job)
    audit_before = await _count(async_connection, AuditEvent)

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("leadradar.feedback.commands.enqueue_account_rescore", boom)

    with pytest.raises(RuntimeError):
        await give_finding_feedback(
            async_session,
            finding_id=ids["finding_id"],
            verdict=FindingFeedbackVerdict.WRONG,
            note=None,
            principal=_principal(user_id),
            now=NOW,
        )

    finding = (
        await async_session.execute(select(Finding).where(Finding.id == ids["finding_id"]))
    ).scalar_one()
    assert finding.status == FindingStatus.ACTIVE
    assert await _count(async_connection, FindingFeedback) == 0
    assert await _count(async_connection, EvaluationItem) == 0
    assert await _count(async_connection, AuditEvent) == audit_before
    assert await _count(async_connection, PipelineRun) == runs_before
    assert await _count(async_connection, Job) == jobs_before


async def test_feedback_on_an_unknown_finding_raises_finding_not_found_and_writes_nothing(
    async_connection: AsyncConnection, async_session: AsyncSession
) -> None:
    user_id = await _make_user(async_connection)

    with pytest.raises(FindingNotFound):
        await give_finding_feedback(
            async_session,
            finding_id=uuid.uuid4(),
            verdict=FindingFeedbackVerdict.WRONG,
            note=None,
            principal=_principal(user_id),
            now=NOW,
        )

    assert await _count(async_connection, FindingFeedback) == 0
