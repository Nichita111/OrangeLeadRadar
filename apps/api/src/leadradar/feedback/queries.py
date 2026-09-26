"""Reads that shape [`LeadFeedback`](/architecture/interfaces.md#leadfeedback),
[`FindingView`](/architecture/interfaces.md#findingview) (`API-46`, `API-47`) and
[`ScoreChange`](/architecture/interfaces.md#scorechange) (`API-41`) out of the store. Plain
dataclasses, not Pydantic models: those live at the api boundary
(`api/feedback_and_alerts.py`), which shapes its response from these."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AccountScoreBand,
    AccountScoreStanding,
    DocumentSourceType,
    FindingDecidedBy,
    FindingFeedbackVerdict,
    FindingStatus,
    FindingStrength,
    LeadFeedbackVerdict,
    PipelineRunTrigger,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SourcePluginCode,
)
from leadradar.core.score_breakdown import counted_points
from leadradar.db.models.configuration import ScoringConfig, SignalQuestion
from leadradar.db.models.ingestion import Chunk, Document, PipelineRun
from leadradar.db.models.signals import AccountScore, Finding


@dataclass(frozen=True)
class LeadFeedbackResult:
    """[`LeadFeedback`](/architecture/interfaces.md#leadfeedback), the response of `API-46`."""

    id: uuid.UUID
    verdict: LeadFeedbackVerdict
    note: str | None
    created_at: datetime
    user_name: str


@dataclass(frozen=True)
class QuestionSummary:
    """`FindingView.question`."""

    id: uuid.UUID
    key: str
    text: str
    polarity: SignalQuestionPolarity


@dataclass(frozen=True)
class OptionSummary:
    """`FindingView.option`; `CHOICE` questions only."""

    key: str
    label: str


@dataclass(frozen=True)
class DocumentSummary:
    """`FindingView.document`."""

    id: uuid.UUID
    title: str | None
    url: str
    source_type: DocumentSourceType
    plugin_code: SourcePluginCode
    language: str
    published_at: datetime | None


@dataclass(frozen=True)
class FeedbackSummary:
    """`FindingView.feedback`: the in-force
    [`finding_feedback`](/architecture/sql-store.md#finding_feedback)."""

    verdict: FindingFeedbackVerdict
    user_name: str
    created_at: datetime


@dataclass(frozen=True)
class FindingViewData:
    """[`FindingView`](/architecture/interfaces.md#findingview), the response of `API-47`."""

    id: uuid.UUID
    account_id: uuid.UUID
    service_id: uuid.UUID
    question: QuestionSummary
    question_revision: int
    confidence: float
    quote: str
    quote_en: str | None
    rationale: str
    observed_at: datetime
    strength: FindingStrength
    decided_by: FindingDecidedBy
    status: FindingStatus
    option: OptionSummary | None
    document: DocumentSummary
    points: float | None
    feedback: FeedbackSummary | None


def _option_summary(question: SignalQuestion, option_key: str | None) -> OptionSummary | None:
    if option_key is None or question.answer_type != SignalQuestionAnswerType.CHOICE:
        return None
    options = question.options if isinstance(question.options, list) else []
    for option in options:
        if isinstance(option, dict) and option.get("key") == option_key:
            return OptionSummary(key=option_key, label=str(option.get("label")))
    return None


async def _document_summary(session: AsyncSession, chunk_id: uuid.UUID) -> DocumentSummary:
    document = (
        await session.execute(
            select(Document)
            .join(Chunk, Chunk.document_id == Document.id)
            .where(Chunk.id == chunk_id)
        )
    ).scalar_one()
    return DocumentSummary(
        id=document.id,
        title=document.title,
        url=document.url,
        source_type=document.source_type,
        plugin_code=document.plugin_code,
        language=document.language,
        published_at=document.published_at,
    )


async def _current_breakdown(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID
) -> dict[str, object] | None:
    return (
        await session.execute(
            select(AccountScore.breakdown).where(
                AccountScore.account_id == account_id,
                AccountScore.service_id == service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()


async def read_finding_view(
    session: AsyncSession,
    *,
    finding: Finding,
    question: SignalQuestion,
    feedback: FeedbackSummary,
) -> FindingViewData:
    """Assembles [`FindingView`](/architecture/interfaces.md#findingview) for one finding, given
    the finding, its question, and the feedback row to show — the one `give_finding_feedback`
    just wrote, which is in force by definition."""
    document = await _document_summary(session, finding.chunk_id)
    breakdown = await _current_breakdown(session, finding.account_id, question.service_id)
    points = counted_points(breakdown, finding.id) if breakdown is not None else None
    return FindingViewData(
        id=finding.id,
        account_id=finding.account_id,
        service_id=question.service_id,
        question=QuestionSummary(
            id=question.id, key=question.key, text=question.text, polarity=question.polarity
        ),
        question_revision=finding.question_revision,
        confidence=finding.confidence,
        quote=finding.quote,
        quote_en=finding.quote_en,
        rationale=finding.rationale,
        observed_at=finding.observed_at,
        strength=finding.strength,
        decided_by=finding.decided_by,
        status=finding.status,
        option=_option_summary(question, finding.option_key),
        document=document,
        points=points,
        feedback=feedback,
    )


async def current_score_id(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID
) -> uuid.UUID | None:
    """The id of the account and service's current
    [`account_score`](/architecture/sql-store.md#account_score), or `None` when the account, the
    service, or a current score for the pair does not exist."""
    return (
        await session.execute(
            select(AccountScore.id).where(
                AccountScore.account_id == account_id,
                AccountScore.service_id == service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()


@dataclass(frozen=True)
class ScoreChangeFindingRef:
    """One entry of `ScoreChange.findings_added` or `findings_removed`."""

    finding_id: uuid.UUID
    question_key: str


@dataclass(frozen=True)
class ScoreChangeOverrideRef:
    """One entry of `ScoreChange.overrides_changed`."""

    rule_key: str
    overridden: bool


@dataclass(frozen=True)
class ScoreChangeData:
    """[`ScoreChange`](/architecture/interfaces.md#scorechange), one item of `API-41`."""

    score_id: uuid.UUID
    as_of: datetime
    fit: int
    intent: int
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand | None
    scoring_version: int
    trigger: PipelineRunTrigger
    run_id: uuid.UUID
    change_note: str | None
    findings_added: list[ScoreChangeFindingRef]
    findings_removed: list[ScoreChangeFindingRef]
    overrides_changed: list[ScoreChangeOverrideRef]


def _breakdown_findings(breakdown: dict[str, object]) -> dict[uuid.UUID, str]:
    """`{finding_id: question_key}` of every counted finding in `breakdown.intent.questions`
    ([Score breakdown](/architecture/rules.md#score-breakdown))."""
    intent = breakdown.get("intent")
    questions = intent.get("questions") if isinstance(intent, dict) else None
    findings: dict[uuid.UUID, str] = {}
    if isinstance(questions, list):
        for entry in questions:
            finding_id = entry.get("finding_id") if isinstance(entry, dict) else None
            if finding_id is not None:
                findings[uuid.UUID(str(finding_id))] = str(entry.get("question_key"))
    return findings


def _breakdown_overrides(breakdown: dict[str, object]) -> dict[str, bool]:
    """`{rule_key: overridden}` of every disqualifier in `breakdown.disqualifiers`."""
    disqualifiers = breakdown.get("disqualifiers")
    overrides: dict[str, bool] = {}
    if isinstance(disqualifiers, list):
        for entry in disqualifiers:
            key = entry.get("key") if isinstance(entry, dict) else None
            if key is not None:
                overrides[str(key)] = bool(entry.get("overridden", False))
    return overrides


async def read_score_history(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID
) -> list[ScoreChangeData]:
    """`API-41`: every [`account_score`](/architecture/sql-store.md#account_score) row of the
    account and service, newest first, each compared with the row before it: the finding ids its
    breakdown counts that the previous one did not, and the reverse, and the disqualifiers whose
    `overridden` flag differs. `change_note` is set only when the version changed from the row
    before."""
    rows = (
        await session.execute(
            select(
                AccountScore, ScoringConfig.version, ScoringConfig.change_note, PipelineRun.trigger
            )
            .join(ScoringConfig, ScoringConfig.id == AccountScore.scoring_config_id)
            .join(PipelineRun, PipelineRun.id == AccountScore.run_id)
            .where(AccountScore.account_id == account_id, AccountScore.service_id == service_id)
            .order_by(AccountScore.as_of.asc())
        )
    ).all()

    changes: list[ScoreChangeData] = []
    previous_findings: dict[uuid.UUID, str] = {}
    previous_overrides: dict[str, bool] = {}
    previous_scoring_config_id: uuid.UUID | None = None
    for score, version, change_note, trigger in rows:
        findings = _breakdown_findings(score.breakdown)
        overrides = _breakdown_overrides(score.breakdown)
        version_changed = (
            previous_scoring_config_id is not None
            and previous_scoring_config_id != score.scoring_config_id
        )
        changes.append(
            ScoreChangeData(
                score_id=score.id,
                as_of=score.as_of,
                fit=score.fit,
                intent=score.intent,
                priority=score.priority,
                standing=score.standing,
                band=score.band,
                scoring_version=version,
                trigger=trigger,
                run_id=score.run_id,
                change_note=change_note if version_changed else None,
                findings_added=[
                    ScoreChangeFindingRef(finding_id=fid, question_key=key)
                    for fid, key in findings.items()
                    if fid not in previous_findings
                ],
                findings_removed=[
                    ScoreChangeFindingRef(finding_id=fid, question_key=key)
                    for fid, key in previous_findings.items()
                    if fid not in findings
                ],
                overrides_changed=[
                    ScoreChangeOverrideRef(rule_key=key, overridden=value)
                    for key, value in overrides.items()
                    if previous_overrides.get(key, False) != value
                ],
            )
        )
        previous_findings = findings
        previous_overrides = overrides
        previous_scoring_config_id = score.scoring_config_id

    changes.reverse()
    return changes
