"""EVALUATE worker step (`S-EVL-04`, `AC-49`): replays [Signal classification]
(/architecture/rules.md#signal-classification) and [Escalation]
(/architecture/rules.md#escalation) over every `ACTIVE` item of an `ACTIVE` question, without
evidence extraction, and writes one [`evaluation_result`]
(/architecture/sql-store.md#evaluation_result) ([Run lifecycle]
(/architecture/services/worker.md#run-lifecycle) after D1)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.ai.audit import AiCallContext
from leadradar.ai.errors import BudgetExhausted, UpstreamUnavailable
from leadradar.ai.fixtures import FixtureMissing
from leadradar.ai.gateway import AiGateway
from leadradar.ai.shapes import (
    ClassifierOption,
    ClassifierQuestion,
    ClassifierRequest,
    EscalationInput,
    EscalationQuestion,
    QuestionOption,
)
from leadradar.configuration.queries import question_options
from leadradar.core.chunking import passage_header
from leadradar.core.enums import (
    AccountScoreBand,
    EvaluationItemStatus,
    FindingStrength,
    LeadFeedbackVerdict,
    PipelineRunStage,
    SignalQuestionAnswerType,
    SignalQuestionStatus,
)
from leadradar.core.evaluation import EvaluationSettings, ItemPrediction, evaluation_metrics, passed
from leadradar.core.signal.classification import (
    SCALE_SUFFIX,
    ClassifierQuestionSpec,
    classifier_questions_for,
    map_answer,
    merge_yes_no_probabilities,
)
from leadradar.core.signal.escalation import Route, route
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import SignalQuestion
from leadradar.db.models.feedback import EvaluationItem, EvaluationResult, LeadFeedback
from leadradar.db.models.ingestion import Chunk, Document, Job, PipelineRun
from leadradar.db.models.signals import AccountScore, Classification
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import StepFailed


@dataclass(frozen=True)
class _Row:
    """One `ACTIVE` item of an `ACTIVE` question, with everything [Evaluation metrics]
    (/architecture/rules.md#evaluation-metrics) needs to replay it, ordered by the item's
    `created_at` then `id` (the order `errors` is listed in)."""

    item_id: uuid.UUID
    chunk_id: uuid.UUID
    passage_text: str
    section: str | None
    question_id: uuid.UUID
    question_key: str
    service_id: uuid.UUID
    question_text: str
    answer_type: SignalQuestionAnswerType
    options: list[dict[str, object]] | None
    question_revision: int
    expected_strength: FindingStrength
    account_name: str
    document_title: str | None
    document_source_type: str
    document_language: str
    document_published_at: datetime | None
    document_fetched_at: datetime
    selected: bool


async def _load_rows(session: AsyncSession) -> list[_Row]:
    selected_exists = (
        select(Classification.id)
        .where(
            Classification.chunk_id == EvaluationItem.chunk_id,
            Classification.question_id == EvaluationItem.question_id,
            Classification.question_revision == SignalQuestion.revision,
        )
        .exists()
    )
    stmt = (
        select(EvaluationItem, SignalQuestion, Chunk, Document, Account, selected_exists)
        .join(SignalQuestion, SignalQuestion.id == EvaluationItem.question_id)
        .join(Chunk, Chunk.id == EvaluationItem.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .join(Account, Account.id == Document.account_id)
        .where(
            EvaluationItem.status == EvaluationItemStatus.ACTIVE,
            SignalQuestion.status == SignalQuestionStatus.ACTIVE,
        )
        .order_by(EvaluationItem.created_at, EvaluationItem.id)
    )
    rows = (await session.execute(stmt)).all()
    result: list[_Row] = []
    for item, question, chunk, document, account, selected in rows:
        assert chunk.text is not None, "an ACTIVE item's passage is never purged"
        result.append(
            _Row(
                item_id=item.id,
                chunk_id=chunk.id,
                passage_text=chunk.text,
                section=chunk.section,
                question_id=question.id,
                question_key=question.key,
                service_id=question.service_id,
                question_text=question.text,
                answer_type=question.answer_type,
                options=question_options(question.options),
                question_revision=question.revision,
                expected_strength=item.expected_strength,
                account_name=account.name,
                document_title=document.title,
                document_source_type=document.source_type.value,
                document_language=document.language,
                document_published_at=document.published_at,
                document_fetched_at=document.fetched_at,
                selected=bool(selected),
            )
        )
    return result


async def _lead_verdicts(
    session: AsyncSession,
) -> list[tuple[AccountScoreBand, LeadFeedbackVerdict]]:
    """The in-force lead feedback and current bands [Evaluation metrics]
    (/architecture/rules.md#evaluation-metrics) needs for `lead_verdicts`: for every account and
    service with a current, banded score (`RANKED` standing), the latest `lead_feedback` row of
    that pair, when it is `RELEVANT` or `NOT_RELEVANT`."""
    scored = (
        await session.execute(
            select(AccountScore.account_id, AccountScore.service_id, AccountScore.band).where(
                AccountScore.is_current.is_(True), AccountScore.band.isnot(None)
            )
        )
    ).all()
    result: list[tuple[AccountScoreBand, LeadFeedbackVerdict]] = []
    for account_id, service_id, band in scored:
        if band is None:
            continue
        verdict = (
            await session.execute(
                select(LeadFeedback.verdict)
                .where(LeadFeedback.account_id == account_id, LeadFeedback.service_id == service_id)
                .order_by(LeadFeedback.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if verdict in (LeadFeedbackVerdict.RELEVANT, LeadFeedbackVerdict.NOT_RELEVANT):
            result.append((band, verdict))
    return result


def _classifier_question(spec: ClassifierQuestionSpec) -> ClassifierQuestion:
    return ClassifierQuestion(
        id=spec.id,
        kind=spec.answer_type,
        text=spec.text,
        options=(
            None
            if spec.options is None
            else [ClassifierOption(key=option.key, label=option.label) for option in spec.options]
        ),
    )


async def run_evaluate_step(
    session: AsyncSession, *, run: PipelineRun, settings: WorkerSettings, gateway: AiGateway
) -> None:
    """Executes the one `EVALUATE` job an `EVALUATION` run owns: classifies every passage of its
    active items once (G3), escalates the pairs the band sends to the LLM, computes the metrics
    and writes the result. Raises `StepFailed` on any AI failure; nothing is written on that
    path, so the run ends `FAILED` with no result."""
    await session.execute(
        update(PipelineRun).where(PipelineRun.id == run.id).values(stage=PipelineRunStage.CLASSIFY)
    )

    rows = await _load_rows(session)

    by_passage: dict[uuid.UUID, list[_Row]] = defaultdict(list)
    for row in rows:
        by_passage[row.chunk_id].append(row)

    final_strengths: dict[uuid.UUID, FindingStrength] = {}
    escalated_by_item: dict[uuid.UUID, bool] = {}
    p_positive_by_item: dict[uuid.UUID, float] = {}

    try:
        for chunk_id, passage_rows in by_passage.items():
            passage_text = passage_rows[0].passage_text
            first = passage_rows[0]
            date = (first.document_published_at or first.document_fetched_at).strftime("%Y-%m-%d")
            header = passage_header(
                account_name=first.account_name,
                document_title=first.document_title,
                section=first.section,
                date=date,
            )
            specs_by_row = {
                row.item_id: classifier_questions_for(
                    question_id=str(row.question_id),
                    account_name=row.account_name,
                    question_text=row.question_text,
                    answer_type=row.answer_type,
                    options=row.options,
                )
                for row in passage_rows
            }
            questions: list[ClassifierQuestion] = [
                _classifier_question(spec) for specs in specs_by_row.values() for spec in specs
            ]
            answers = await gateway.classify(
                ClassifierRequest(state=passage_text, context=header, questions=questions),
                AiCallContext(entity_type="chunk", entity_id=chunk_id, run_id=run.id),
            )
            answers_by_qid = {answer.question_id: answer.probabilities for answer in answers}

            for row in passage_rows:
                main_probs = answers_by_qid.get(str(row.question_id), {})
                if row.answer_type is SignalQuestionAnswerType.YES_NO:
                    scale_probs = answers_by_qid.get(f"{row.question_id}{SCALE_SUFFIX}", {})
                    merged = merge_yes_no_probabilities(main_probs, scale_probs)
                else:
                    merged = main_probs
                mapping = map_answer(
                    answer_type=row.answer_type, probabilities=merged, options=row.options
                )
                p_positive_by_item[row.item_id] = mapping.p_positive
                initial_route = route(
                    mapping.p_positive,
                    escalation_lower=settings.escalation_lower,
                    escalation_upper=settings.escalation_upper,
                )
                if initial_route is Route.NEGATIVE:
                    final_strengths[row.item_id] = FindingStrength.NONE
                    escalated_by_item[row.item_id] = False
                elif initial_route is Route.POSITIVE:
                    final_strengths[row.item_id] = mapping.candidate_strength
                    escalated_by_item[row.item_id] = False
                else:
                    escalation_options = (
                        None
                        if row.options is None
                        else [
                            QuestionOption(
                                key=str(option["key"]),
                                label=str(option["label"]),
                                strength=FindingStrength(str(option["strength"])),
                            )
                            for option in row.options
                        ]
                    )
                    escalation_output = await gateway.escalate(
                        EscalationInput(
                            account_name=row.account_name,
                            question=EscalationQuestion(
                                text=row.question_text,
                                answer_type=row.answer_type,
                                options=escalation_options,
                            ),
                            passage=passage_text,
                            language=row.document_language,
                            header=header,
                        ),
                        AiCallContext(entity_type="chunk", entity_id=chunk_id, run_id=run.id),
                    )
                    final_strengths[row.item_id] = escalation_output.strength
                    escalated_by_item[row.item_id] = True
    except (UpstreamUnavailable, BudgetExhausted, FixtureMissing) as error:
        if isinstance(error, BudgetExhausted):
            raise StepFailed("BUDGET_EXHAUSTED", str(error)) from error
        if isinstance(error, FixtureMissing):
            raise StepFailed("FIXTURE_MISSING", str(error)) from error
        if error.reason == "NOT_CONFIGURED":
            raise StepFailed("NOT_CONFIGURED", str(error)) from error
        raise StepFailed("UPSTREAM_UNAVAILABLE", str(error)) from error

    predictions = [
        ItemPrediction(
            item_id=row.item_id,
            question_id=row.question_id,
            question_key=row.question_key,
            service_id=row.service_id,
            source_type=row.document_source_type,
            expected_strength=row.expected_strength,
            p_positive=p_positive_by_item[row.item_id],
            escalated=escalated_by_item[row.item_id],
            final_strength=final_strengths[row.item_id],
            selected=row.selected,
        )
        for row in rows
    ]
    lead_verdicts = await _lead_verdicts(session)
    metrics = evaluation_metrics(
        predictions,
        lead_verdicts,
        EvaluationSettings(
            eval_min_precision=settings.eval_min_precision,
            eval_min_items=settings.eval_min_items,
            eval_classifier_only_p=settings.eval_classifier_only_p,
            eval_calibration_bins=settings.eval_calibration_bins,
            eval_max_errors=settings.eval_max_errors,
        ),
    )
    precision = metrics.get("precision")
    assert precision is None or isinstance(precision, float)
    result_passed = passed(
        precision,
        len(predictions),
        min_precision=settings.eval_min_precision,
        min_items=settings.eval_min_items,
    )

    session.add(
        EvaluationResult(
            run_id=run.id,
            classifier=gateway.classifier,
            escalation_lower=settings.escalation_lower,
            escalation_upper=settings.escalation_upper,
            min_precision=settings.eval_min_precision,
            min_items=settings.eval_min_items,
            escalation_rate_target=settings.escalation_rate_target,
            items=len(predictions),
            metrics=metrics,
            passed=result_passed,
        )
    )
    progress = {
        "items_evaluated": len(predictions),
        "pairs_escalated": sum(1 for value in escalated_by_item.values() if value),
    }
    await session.execute(
        update(PipelineRun).where(PipelineRun.id == run.id).values(progress=progress)
    )
    await session.flush()


async def run_evaluate_job(
    session: AsyncSession,
    *,
    job: Job,
    run: PipelineRun,
    settings: WorkerSettings,
    gateway: AiGateway,
) -> None:
    """Adapter that wires an `EVALUATE` `Job` into the generic job-loop handler protocol."""
    await run_evaluate_step(session, run=run, settings=settings, gateway=gateway)
