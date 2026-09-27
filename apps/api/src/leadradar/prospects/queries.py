"""Reads of the [Prospects and evidence](/architecture/interfaces.md#prospects-and-evidence)
family: `API-39` (the prospect list), `API-40` (one score with its breakdown), `API-42` (an
account's findings) and `API-43` (a finding's evidence). Each returns plain data shaped as its
contract; the router validates it into the response model."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AccountScoreBand,
    AccountScoreStanding,
    AccountStatus,
    FindingStatus,
    LeadFeedbackVerdict,
    ScoringConfigStatus,
    SignalQuestionPolarity,
)
from leadradar.db.models.accounts import Account, AccountAlias
from leadradar.db.models.configuration import ScoringConfig, SignalQuestion
from leadradar.db.models.feedback import FindingFeedback, LeadFeedback
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Chunk, Document
from leadradar.db.models.outreach import CrmSync
from leadradar.db.models.signals import AccountScore, Alert, DisqualifierOverride, Finding
from leadradar.feedback.queries import FeedbackSummary, FindingViewData, read_finding_view
from leadradar.prospects.errors import ProspectNotFound


@dataclass(frozen=True)
class ProspectFilters:
    """`API-39`'s query: `standing`, `band[]`, `country_code[]`, `industry[]`, `q` and `sort`."""

    standing: AccountScoreStanding
    bands: Sequence[AccountScoreBand] | None
    country_codes: Sequence[str] | None
    industries: Sequence[str] | None
    q: str | None
    sort: str


def _ranking_key(score: AccountScore, account: Account) -> tuple[int, int, int, str]:
    """[Priority, standing and band](/architecture/rules.md#priority-standing-and-band): Priority,
    then Intent, then Fit descending, then account name ascending."""
    return (-score.priority, -score.intent, -score.fit, account.name.casefold())


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


async def _current_scores(
    session: AsyncSession, service_id: uuid.UUID
) -> list[tuple[AccountScore, Account]]:
    rows = await session.execute(
        select(AccountScore, Account)
        .join(Account, Account.id == AccountScore.account_id)
        .where(
            AccountScore.service_id == service_id,
            AccountScore.is_current.is_(True),
            Account.status == AccountStatus.ACTIVE,
        )
    )
    return [(score, account) for score, account in rows.all()]


def _ranks(scored: list[tuple[AccountScore, Account]]) -> dict[uuid.UUID, int]:
    ranked = sorted(
        (pair for pair in scored if pair[0].standing is AccountScoreStanding.RANKED),
        key=lambda pair: _ranking_key(*pair),
    )
    return {account.id: position for position, (_, account) in enumerate(ranked, start=1)}


async def _matching_account_ids(session: AsyncSession, q: str) -> set[uuid.UUID]:
    """`q` matches as in `API-20`: the account's name, domain or one of its aliases."""
    pattern = f"%{q}%"
    rows = await session.execute(
        select(Account.id).where(
            or_(
                Account.name.ilike(pattern),
                Account.domain.ilike(pattern),
                Account.id.in_(
                    select(AccountAlias.account_id).where(AccountAlias.alias.ilike(pattern))
                ),
            )
        )
    )
    return set(rows.scalars())


def _sort_key(sort: str, score: AccountScore, account: Account) -> tuple[object, ...]:
    if sort == "intent":
        return (-score.intent, *_ranking_key(score, account))
    if sort == "fit":
        return (-score.fit, *_ranking_key(score, account))
    if sort == "name":
        return (account.name.casefold(),)
    if sort == "last_refreshed":
        refreshed = account.last_refreshed_at
        return (refreshed is None, -(refreshed.timestamp() if refreshed else 0.0))
    return _ranking_key(score, account)


async def _in_force_lead_feedback(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID
) -> tuple[LeadFeedback, str] | None:
    row = (
        await session.execute(
            select(LeadFeedback, AppUser.display_name)
            .join(AppUser, AppUser.id == LeadFeedback.user_id)
            .where(LeadFeedback.account_id == account_id, LeadFeedback.service_id == service_id)
            .order_by(LeadFeedback.created_at.desc())
            .limit(1)
        )
    ).first()
    return (row[0], row[1]) if row is not None else None


async def _reason(
    session: AsyncSession, score: AccountScore, service_id: uuid.UUID
) -> dict[str, object] | None:
    """`ProspectRow.reason`: null when `RANKED`, else the member its standing names."""
    reason: dict[str, object] = {
        "min_fit": None,
        "disqualifier_labels": None,
        "customer_marked_by_name": None,
    }
    if score.standing is AccountScoreStanding.RANKED:
        return None
    if score.standing is AccountScoreStanding.BELOW_FIT:
        settings = (
            await session.execute(
                select(ScoringConfig.settings).where(ScoringConfig.id == score.scoring_config_id)
            )
        ).scalar_one()
        reason["min_fit"] = settings.get("min_fit")
    elif score.standing is AccountScoreStanding.DISQUALIFIED:
        disqualifiers = score.breakdown.get("disqualifiers")
        reason["disqualifier_labels"] = [
            str(entry.get("label"))
            for entry in (disqualifiers if isinstance(disqualifiers, list) else [])
            if isinstance(entry, dict) and entry.get("matched") and not entry.get("overridden")
        ]
    elif score.standing is AccountScoreStanding.CUSTOMER:
        feedback = await _in_force_lead_feedback(session, score.account_id, service_id)
        if feedback is not None and feedback[0].verdict is LeadFeedbackVerdict.ALREADY_CUSTOMER:
            reason["customer_marked_by_name"] = feedback[1]
    return reason


def _breakdown_questions(breakdown: dict[str, object]) -> list[dict[str, object]]:
    intent = breakdown.get("intent")
    questions = intent.get("questions") if isinstance(intent, dict) else None
    return [entry for entry in (questions or []) if isinstance(entry, dict)]


async def _top_signals(
    session: AsyncSession, score: AccountScore, limit: int
) -> list[dict[str, object]]:
    """The positive counted findings with the most `points` in the breakdown."""
    counted = sorted(
        (
            entry
            for entry in _breakdown_questions(score.breakdown)
            if entry.get("finding_id")
            and entry.get("polarity") == SignalQuestionPolarity.POSITIVE.value
            and float(str(entry.get("points") or 0)) > 0
        ),
        key=lambda entry: -float(str(entry.get("points") or 0)),
    )[:limit]
    if not counted:
        return []
    ids = [uuid.UUID(str(entry["finding_id"])) for entry in counted]
    rows = await session.execute(
        select(Finding, SignalQuestion)
        .join(SignalQuestion, SignalQuestion.id == Finding.question_id)
        .where(Finding.id.in_(ids))
    )
    by_id = {finding.id: (finding, question) for finding, question in rows.all()}
    signals: list[dict[str, object]] = []
    for finding_id in ids:
        if finding_id not in by_id:
            continue
        finding, question = by_id[finding_id]
        signals.append(
            {
                "question_key": question.key,
                "question_text": question.text,
                "strength": finding.strength,
                "observed_at": finding.observed_at.isoformat(),
            }
        )
    return signals


async def _counts_by_account(
    session: AsyncSession, service_id: uuid.UUID
) -> tuple[Counter[uuid.UUID], Counter[uuid.UUID]]:
    findings = await session.execute(
        select(Finding.account_id, func.count())
        .join(SignalQuestion, SignalQuestion.id == Finding.question_id)
        .where(SignalQuestion.service_id == service_id, Finding.status == FindingStatus.ACTIVE)
        .group_by(Finding.account_id)
    )
    alerts = await session.execute(
        select(Alert.account_id, func.count())
        .where(Alert.service_id == service_id, Alert.acknowledged_at.is_(None))
        .group_by(Alert.account_id)
    )
    return Counter(dict(findings.all())), Counter(dict(alerts.all()))


async def list_prospects(
    session: AsyncSession,
    *,
    service_id: uuid.UUID,
    filters: ProspectFilters,
    page: int,
    page_size: int,
    top_signals: int,
) -> dict[str, object]:
    """`API-39`: the current score rows of the service's active accounts, filtered, sorted and
    paged, with `band_counts` under every filter but `band[]`."""
    scored = await _current_scores(session, service_id)
    ranks = _ranks(scored)
    q_ids = await _matching_account_ids(session, filters.q) if filters.q else None

    def matches(score: AccountScore, account: Account) -> bool:
        return (
            score.standing is filters.standing
            and (not filters.country_codes or account.country_code in filters.country_codes)
            and (not filters.industries or account.industry in filters.industries)
            and (q_ids is None or account.id in q_ids)
        )

    unbanded = [pair for pair in scored if matches(*pair)]
    band_counts = Counter(
        score.band
        for score, _ in unbanded
        if score.standing is AccountScoreStanding.RANKED and score.band is not None
    )
    selected = [pair for pair in unbanded if not filters.bands or pair[0].band in filters.bands]
    selected.sort(key=lambda pair: _sort_key(filters.sort, *pair))
    page_rows = selected[(page - 1) * page_size : page * page_size]

    finding_counts, alert_counts = await _counts_by_account(session, service_id)
    items: list[dict[str, object]] = []
    for score, account in page_rows:
        items.append(
            {
                "rank": ranks.get(account.id),
                "account": {
                    "id": str(account.id),
                    "name": account.name,
                    "domain": account.domain,
                    "country_code": account.country_code,
                    "industry": account.industry,
                },
                "fit": score.fit,
                "intent": score.intent,
                "priority": score.priority,
                "standing": score.standing,
                "band": score.band,
                "reason": await _reason(session, score, service_id),
                "top_signals": await _top_signals(session, score, top_signals),
                "finding_count": finding_counts[account.id],
                "unread_alerts": alert_counts[account.id],
                "as_of": score.as_of.isoformat(),
                "last_refreshed_at": _iso(account.last_refreshed_at),
            }
        )
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": len(selected),
        "band_counts": {band: band_counts.get(band, 0) for band in AccountScoreBand},
    }


async def _current_score(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID
) -> AccountScore:
    score = (
        await session.execute(
            select(AccountScore).where(
                AccountScore.account_id == account_id,
                AccountScore.service_id == service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if score is None:
        raise ProspectNotFound("The account has no score for the service yet.")
    return score


async def active_disqualifier_labels(
    session: AsyncSession, service_id: uuid.UUID
) -> dict[str, str]:
    """Each disqualifier `key` → `label` of the service's `ACTIVE` scoring settings."""
    settings = (
        await session.execute(
            select(ScoringConfig.settings).where(
                ScoringConfig.service_id == service_id,
                ScoringConfig.status == ScoringConfigStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    rules = settings.get("disqualifiers") if isinstance(settings, dict) else None
    return {
        str(rule["key"]): str(rule.get("label", rule["key"]))
        for rule in (rules if isinstance(rules, list) else [])
        if isinstance(rule, dict) and "key" in rule
    }


async def override_views(
    session: AsyncSession,
    overrides: Sequence[DisqualifierOverride],
    *,
    run_id: uuid.UUID | None = None,
) -> list[dict[str, object]]:
    """[`Override`](/architecture/interfaces.md#override) for each row; `run_id` is set only by
    the command that enqueued a `RESCORE`."""
    if not overrides:
        return []
    labels = await active_disqualifier_labels(session, overrides[0].service_id)
    user_ids = {o.created_by for o in overrides} | {o.revoked_by for o in overrides if o.revoked_by}
    names = dict(
        (
            await session.execute(
                select(AppUser.id, AppUser.display_name).where(AppUser.id.in_(user_ids))
            )
        ).all()
    )
    return [
        {
            "id": str(o.id),
            "account_id": str(o.account_id),
            "service_id": str(o.service_id),
            "rule_key": o.rule_key,
            "note": o.note,
            "rule_label": labels.get(o.rule_key, o.rule_key),
            "status": o.status,
            "created_by_name": names.get(o.created_by, ""),
            "created_at": o.created_at.isoformat(),
            "revoked_by_name": names.get(o.revoked_by) if o.revoked_by else None,
            "revoked_at": _iso(o.revoked_at),
            "run_id": str(run_id) if run_id is not None else None,
        }
        for o in overrides
    ]


async def read_score_view(
    session: AsyncSession, *, account_id: uuid.UUID, service_id: uuid.UUID
) -> dict[str, object]:
    """`API-40`: the current score with its breakdown, overrides, lead feedback and CRM sync;
    raises `ProspectNotFound` when the account has no score for the service yet."""
    score = await _current_score(session, account_id, service_id)
    version = (
        await session.execute(
            select(ScoringConfig.version).where(ScoringConfig.id == score.scoring_config_id)
        )
    ).scalar_one()
    scored = await _current_scores(session, service_id)

    questions = _breakdown_questions(score.breakdown)
    texts = dict(
        (
            await session.execute(
                select(SignalQuestion.key, SignalQuestion.text).where(
                    SignalQuestion.service_id == service_id
                )
            )
        ).all()
    )
    finding_ids = [uuid.UUID(str(e["finding_id"])) for e in questions if e.get("finding_id")]
    observed = dict(
        (
            await session.execute(
                select(Finding.id, Finding.observed_at).where(Finding.id.in_(finding_ids))
            )
        ).all()
    )
    breakdown = dict(score.breakdown)
    stored_intent = breakdown.get("intent")
    intent: dict[str, object] = dict(stored_intent) if isinstance(stored_intent, dict) else {}
    intent["questions"] = [
        {
            **entry,
            "question_text": texts.get(str(entry.get("question_key")), ""),
            "observed_at": (
                observed.get(uuid.UUID(str(entry["finding_id"])))
                if entry.get("finding_id")
                else None
            ),
        }
        for entry in questions
    ]
    breakdown["intent"] = intent

    overrides = (
        (
            await session.execute(
                select(DisqualifierOverride)
                .where(
                    DisqualifierOverride.account_id == account_id,
                    DisqualifierOverride.service_id == service_id,
                )
                .order_by(DisqualifierOverride.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    feedback = await _in_force_lead_feedback(session, account_id, service_id)
    crm = (
        await session.execute(
            select(CrmSync)
            .where(CrmSync.account_id == account_id, CrmSync.service_id == service_id)
            .order_by(CrmSync.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return {
        "score_id": str(score.id),
        "account_id": str(account_id),
        "service_id": str(service_id),
        "scoring_version": version,
        "as_of": score.as_of.isoformat(),
        "fit": score.fit,
        "intent": score.intent,
        "priority": score.priority,
        "standing": score.standing,
        "band": score.band,
        "rank": _ranks(scored).get(account_id),
        "breakdown": breakdown,
        "overrides": await override_views(session, overrides),
        "lead_feedback": (
            {
                "id": feedback[0].id,
                "verdict": feedback[0].verdict,
                "note": feedback[0].note,
                "created_at": feedback[0].created_at,
                "user_name": feedback[1],
            }
            if feedback is not None
            else None
        ),
        "last_crm_sync": (
            {
                "id": crm.id,
                "external_id": crm.external_id,
                "error": crm.error,
                "created_at": crm.created_at,
                "target": crm.target,
                "status": crm.status,
            }
            if crm is not None
            else None
        ),
    }


async def list_findings(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    service_id: uuid.UUID | None,
    question_id: uuid.UUID | None,
    status: FindingStatus,
) -> list[FindingViewData]:
    """`API-42`: the account's findings of `status`, ordered by contribution to the current
    breakdown, then `observed_at` descending."""
    query = (
        select(Finding, SignalQuestion)
        .join(SignalQuestion, SignalQuestion.id == Finding.question_id)
        .where(Finding.account_id == account_id, Finding.status == status)
    )
    if service_id is not None:
        query = query.where(SignalQuestion.service_id == service_id)
    if question_id is not None:
        query = query.where(Finding.question_id == question_id)
    pairs = (await session.execute(query)).all()

    feedback_rows = await session.execute(
        select(FindingFeedback, AppUser.display_name)
        .join(AppUser, AppUser.id == FindingFeedback.user_id)
        .where(FindingFeedback.finding_id.in_([finding.id for finding, _ in pairs]))
        .order_by(FindingFeedback.created_at)
    )
    in_force: dict[uuid.UUID, FeedbackSummary] = {}
    for row, name in feedback_rows.all():
        in_force[row.finding_id] = FeedbackSummary(
            verdict=row.verdict, user_name=name, created_at=row.created_at
        )

    views = [
        await read_finding_view(
            session, finding=finding, question=question, feedback=in_force.get(finding.id)
        )
        for finding, question in pairs
    ]
    views.sort(
        key=lambda view: (
            view.points is None,
            -(view.points or 0.0),
            -view.observed_at.timestamp(),
        )
    )
    return views


async def read_evidence(
    session: AsyncSession, *, finding_id: uuid.UUID, context_chars: int
) -> dict[str, object]:
    """`API-43`: the finding's passage with up to `context_chars` of document text on each
    side, and the quote's offsets in it; no excerpt once the document is purged."""
    row = (
        await session.execute(
            select(Finding, Chunk, Document)
            .join(Chunk, Chunk.id == Finding.chunk_id)
            .join(Document, Document.id == Chunk.document_id)
            .where(Finding.id == finding_id)
        )
    ).first()
    if row is None:
        raise ProspectNotFound("The finding does not exist.")
    finding, chunk, document = row
    purged = document.purged_at is not None or document.text is None
    excerpt: str | None = None
    quote_start: int | None = None
    quote_end: int | None = None
    if not purged and document.text is not None:
        start = max(0, chunk.char_start - context_chars)
        excerpt = document.text[start : chunk.char_end + context_chars]
        found = excerpt.find(finding.quote)
        if found >= 0:
            quote_start, quote_end = found, found + len(finding.quote)
    return {
        "finding_id": str(finding.id),
        "document": {
            "id": str(document.id),
            "title": document.title,
            "url": document.url,
            "source_type": document.source_type,
            "plugin_code": document.plugin_code,
            "language": document.language,
            "published_at": _iso(document.published_at),
        },
        "section": chunk.section,
        "purged": purged,
        "excerpt": excerpt,
        "quote_start": quote_start,
        "quote_end": quote_end,
    }
