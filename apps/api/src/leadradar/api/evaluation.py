"""Router of the [Evaluation](/architecture/interfaces.md#evaluation-contracts) family: `API-50`
to `API-55`, and `API-77`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import CurrentUser, require_admin
from leadradar.api.pagination import Page, PageRequest, page_request
from leadradar.api.runs_and_source_plugins import Run, to_run
from leadradar.core.enums import (
    DocumentTriageClassifier,
    EvaluationItemOrigin,
    EvaluationItemStatus,
    FindingStrength,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
)
from leadradar.db.models.identity import AppUser
from leadradar.db.session import get_session
from leadradar.evaluation.impact import read_impact
from leadradar.evaluation.labels import (
    EvaluationItemFilters,
    EvaluationItemView,
    LabelQueueView,
    label_pair,
    list_items,
    read_label_queue,
)
from leadradar.evaluation.labels import LabelTask as LabelTaskData
from leadradar.evaluation.runs import (
    EvaluationResultDetailView,
    EvaluationResultSummaryView,
    read_result,
    read_results,
    request_quality_check,
)

router = APIRouter(tags=["evaluation"])


# --- Shapes --------------------------------------------------------------------------------


class LabelTaskAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    name: str


class LabelTaskDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str | None
    url: str
    language: str
    published_at: datetime | None


class LabelTaskQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    key: str
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[dict[str, object]] | None
    polarity: SignalQuestionPolarity


class LabelTask(BaseModel):
    """[`LabelTask`](/architecture/interfaces.md#labeltask)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: uuid.UUID
    passage_text: str
    question: LabelTaskQuestion
    question_revision: int
    account: LabelTaskAccount
    document: LabelTaskDocument


class LabelQueue(BaseModel):
    """[`LabelQueue`](/architecture/interfaces.md#labelqueue), the response of `API-50`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tasks: list[LabelTask]
    active_items: int
    min_items: int


class LabelCreate(BaseModel):
    """[`LabelCreate`](/architecture/interfaces.md#labelcreate), the request of `API-51`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: uuid.UUID
    question_id: uuid.UUID
    question_revision: int
    expected_strength: FindingStrength


class EvaluationItem(BaseModel):
    """[`EvaluationItem`](/architecture/interfaces.md#evaluationitem)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    chunk_id: uuid.UUID
    question_id: uuid.UUID
    question_revision: int
    created_at: datetime
    question_key: str
    expected_strength: FindingStrength
    origin: EvaluationItemOrigin
    status: EvaluationItemStatus
    labelled_by_name: str


class EvaluationResultSummary(BaseModel):
    """[`EvaluationResultSummary`](/architecture/interfaces.md#evaluationresultsummary)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: uuid.UUID
    created_at: datetime
    classifier: DocumentTriageClassifier
    items: int
    passed: bool
    precision: float | None
    recall: float | None
    escalation_rate: float | None


class EvaluationResult(BaseModel):
    """[`EvaluationResult`](/architecture/interfaces.md#evaluationresult)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: uuid.UUID
    created_at: datetime
    classifier: DocumentTriageClassifier
    items: int
    passed: bool
    precision: float | None
    recall: float | None
    escalation_rate: float | None
    escalation_lower: float
    escalation_upper: float
    min_precision: float
    min_items: int
    escalation_rate_target: float
    metrics: dict[str, Any]


class Impact(BaseModel):
    """[`Impact`](/architecture/interfaces.md#impact), the response of `API-77`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_days: int
    accounts_refreshed: int
    refreshes: int
    cost_per_refresh_eur: float | None
    minutes_per_refresh: float | None
    findings_created: int
    precision: float | None
    labelled_items: int | None
    manual_minutes_per_account: int
    manual_hours_replaced: float


# --- Converters -----------------------------------------------------------------------------


def _label_task(task: LabelTaskData) -> LabelTask:
    return LabelTask(
        chunk_id=task.chunk_id,
        passage_text=task.passage_text,
        question=LabelTaskQuestion(
            id=task.question.id,
            key=task.question.key,
            text=task.question.text,
            answer_type=task.question.answer_type,
            options=task.question.options,
            polarity=task.question.polarity,
        ),
        question_revision=task.question_revision,
        account=LabelTaskAccount(id=task.account.id, name=task.account.name),
        document=LabelTaskDocument(
            title=task.document.title,
            url=task.document.url,
            language=task.document.language,
            published_at=task.document.published_at,
        ),
    )


def _label_queue(view: LabelQueueView) -> LabelQueue:
    return LabelQueue(
        tasks=[_label_task(task) for task in view.tasks],
        active_items=view.active_items,
        min_items=view.min_items,
    )


def _evaluation_item(view: EvaluationItemView) -> EvaluationItem:
    return EvaluationItem(
        id=view.id,
        chunk_id=view.chunk_id,
        question_id=view.question_id,
        question_revision=view.question_revision,
        created_at=view.created_at,
        question_key=view.question_key,
        expected_strength=view.expected_strength,
        origin=view.origin,
        status=view.status,
        labelled_by_name=view.labelled_by_name,
    )


def _result_summary(view: EvaluationResultSummaryView) -> EvaluationResultSummary:
    return EvaluationResultSummary(
        run_id=view.run_id,
        created_at=view.created_at,
        classifier=view.classifier,
        items=view.items,
        passed=view.passed,
        precision=view.precision,
        recall=view.recall,
        escalation_rate=view.escalation_rate,
    )


def _result_detail(view: EvaluationResultDetailView) -> EvaluationResult:
    summary = view.summary
    return EvaluationResult(
        run_id=summary.run_id,
        created_at=summary.created_at,
        classifier=summary.classifier,
        items=summary.items,
        passed=summary.passed,
        precision=summary.precision,
        recall=summary.recall,
        escalation_rate=summary.escalation_rate,
        escalation_lower=view.escalation_lower,
        escalation_upper=view.escalation_upper,
        min_precision=view.min_precision,
        min_items=view.min_items,
        escalation_rate_target=view.escalation_rate_target,
        metrics=view.metrics,
    )


# --- Routes ----------------------------------------------------------------------------------


@router.get("/evaluation/label-queue")
async def get_label_queue(
    service_id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> LabelQueue:
    """`API-50`: the label queue of [Evaluation metrics]
    (/architecture/rules.md#evaluation-metrics). A task never shows the classifier's answer."""
    view = await read_label_queue(session, request.app.state.settings, service_id)
    return _label_queue(view)


@router.post("/evaluation/items")
async def post_evaluation_item(
    body: LabelCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> EvaluationItem:
    """`API-51`: writes the `MANUAL` item for the passage, question and revision, updating the
    pair's active item in place, whatever its origin, or writing one when none exists (D9)."""
    view = await label_pair(
        session,
        principal=principal,
        chunk_id=body.chunk_id,
        question_id=body.question_id,
        question_revision=body.question_revision,
        expected_strength=body.expected_strength,
        now=request.app.state.clock(),
    )
    return _evaluation_item(view)


@router.get("/evaluation/items")
async def get_evaluation_items(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[AppUser, Depends(require_admin)],
    paging: Annotated[PageRequest, Depends(page_request)],
    question_id: uuid.UUID | None = None,
    origin: EvaluationItemOrigin | None = None,
    status: EvaluationItemStatus | None = None,
) -> Page[EvaluationItem]:
    """`API-52`, Admin only."""
    filters = EvaluationItemFilters(question_id=question_id, origin=origin, status=status)
    views, total = await list_items(session, filters, page=paging.page, page_size=paging.page_size)
    return Page[EvaluationItem](
        items=[_evaluation_item(view) for view in views],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


@router.post(
    "/evaluation/runs",
    status_code=http_status.HTTP_202_ACCEPTED,
    responses={
        http_status.HTTP_200_OK: {"model": Run, "description": "The evaluation already queued"}
    },
)
async def post_evaluation_run(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[AppUser, Depends(require_admin)],
) -> Run:
    """`API-53`: one queued or running evaluation at a time (D2): `202` with a new run, or `200`
    with the one already queued or running."""
    result = await request_quality_check(session, principal=admin, now=request.app.state.clock())
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return to_run(result.run)


@router.get("/evaluation/results")
async def get_evaluation_results(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[AppUser, Depends(require_admin)],
) -> list[EvaluationResultSummary]:
    """`API-54`: every quality check, newest first (D8)."""
    views = await read_results(session)
    return [_result_summary(view) for view in views]


@router.get("/evaluation/results/{run_id}")
async def get_evaluation_result(
    run_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[AppUser, Depends(require_admin)],
) -> EvaluationResult:
    """`API-55`."""
    view = await read_result(session, run_id)
    return _result_detail(view)


@router.get("/impact")
async def get_impact(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[AppUser, Depends(require_admin)],
) -> Impact:
    """`API-77`: computed on read by [Impact](/architecture/rules.md#impact); writes nothing."""
    settings = request.app.state.settings
    current_time = request.app.state.clock()
    report = await read_impact(session, settings, current_time)
    return Impact(
        period_days=report.period_days,
        accounts_refreshed=report.accounts_refreshed,
        refreshes=report.refreshes,
        cost_per_refresh_eur=report.cost_per_refresh_eur,
        minutes_per_refresh=report.minutes_per_refresh,
        findings_created=report.findings_created,
        precision=report.precision,
        labelled_items=report.labelled_items,
        manual_minutes_per_account=report.manual_minutes_per_account,
        manual_hours_replaced=report.manual_hours_replaced,
    )
