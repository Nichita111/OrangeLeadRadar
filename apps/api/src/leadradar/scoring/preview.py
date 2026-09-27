"""Capability function for `API-19`: what every current score of a service would be under its
draft scoring settings, computed from the same inputs [Rescoring](/architecture/rules.md#rescoring)
reads and with the same pure scoring functions, without writing anything
([`ScoringPreview`](/architecture/interfaces.md#scoringpreview))."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AccountScoreBand, AccountScoreStanding, ScoringConfigStatus
from leadradar.core.scoring.breakdown import ScoreInputs, score_account
from leadradar.core.scoring.settings import ScoringSettings
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import ScoringConfig
from leadradar.db.models.signals import AccountScore
from leadradar.scoring.errors import NoActiveVersion, NotADraft, ScoringConfigNotFound
from leadradar.scoring.inputs import (
    account_to_attributes,
    load_active_overrides,
    load_inforce_findings,
    load_lead_feedback,
    load_question_polarity,
)


@dataclass(frozen=True)
class PreviewScore:
    """`{priority, standing, band, rank}` of one account, current or proposed."""

    fit: int
    intent: int
    priority: int
    standing: AccountScoreStanding
    band: AccountScoreBand | None
    rank: int | None = None


@dataclass(frozen=True)
class PreviewChange:
    account_id: uuid.UUID
    account_name: str
    current: PreviewScore
    proposed: PreviewScore


@dataclass(frozen=True)
class ScoringPreviewResult:
    draft_version: int
    active_version: int
    changes: list[PreviewChange]
    unchanged_count: int


def _ranks(
    scores: dict[uuid.UUID, PreviewScore], names: dict[uuid.UUID, str]
) -> dict[uuid.UUID, int]:
    """The ranking of [Priority, standing and band]
    (/architecture/rules.md#priority-standing-and-band): `RANKED` accounts by Priority, Intent
    and Fit descending, then name ascending."""
    ranked = [aid for aid, s in scores.items() if s.standing == AccountScoreStanding.RANKED]
    ranked.sort(key=lambda a: (-scores[a].priority, -scores[a].intent, -scores[a].fit, names[a]))
    return {aid: index for index, aid in enumerate(ranked, start=1)}


def _with_rank(score: PreviewScore, rank: int | None) -> PreviewScore:
    return PreviewScore(score.fit, score.intent, score.priority, score.standing, score.band, rank)


async def preview_scoring_config(
    session: AsyncSession, *, config_id: uuid.UUID
) -> ScoringPreviewResult:
    """Scores every account with a current score of the draft's service under the draft, at
    the `as_of` of its current score so only the settings differ, and compares."""
    draft = await session.get(ScoringConfig, config_id)
    if draft is None:
        raise ScoringConfigNotFound(str(config_id))
    if draft.status != ScoringConfigStatus.DRAFT:
        raise NotADraft(str(config_id), str(draft.status))
    active_version = (
        await session.execute(
            select(ScoringConfig.version).where(
                ScoringConfig.service_id == draft.service_id,
                ScoringConfig.status == ScoringConfigStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if active_version is None:
        raise NoActiveVersion

    settings = ScoringSettings.model_validate(draft.settings)
    polarity = await load_question_polarity(session, draft.service_id, settings)

    rows = (
        await session.execute(
            select(AccountScore, Account)
            .join(Account, Account.id == AccountScore.account_id)
            .where(
                AccountScore.service_id == draft.service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).all()

    names: dict[uuid.UUID, str] = {}
    current: dict[uuid.UUID, PreviewScore] = {}
    proposed: dict[uuid.UUID, PreviewScore] = {}
    for score_row, account in rows:
        names[account.id] = account.name
        current[account.id] = PreviewScore(
            score_row.fit, score_row.intent, score_row.priority, score_row.standing, score_row.band
        )
        as_of: datetime = score_row.as_of
        result = score_account(
            ScoreInputs(
                account_id=str(account.id),
                service_id=str(draft.service_id),
                scoring_config_id=str(draft.id),
                settings_version=draft.version,
                attributes=account_to_attributes(account),
                findings=await load_inforce_findings(session, account.id, draft.service_id),
                lead_feedback_verdict=await load_lead_feedback(
                    session, account.id, draft.service_id
                ),
                active_overrides=await load_active_overrides(session, account.id, draft.service_id),
                question_settings_with_polarity=polarity,
            ),
            as_of=as_of,
            settings=settings,
        )
        proposed[account.id] = PreviewScore(
            result.fit, result.intent, result.priority, result.standing, result.band
        )

    current_ranks = _ranks(current, names)
    proposed_ranks = _ranks(proposed, names)
    changes: list[PreviewChange] = []
    for account_id, name in names.items():
        before = _with_rank(current[account_id], current_ranks.get(account_id))
        after = _with_rank(proposed[account_id], proposed_ranks.get(account_id))
        if (before.priority, before.standing, before.band, before.rank) != (
            after.priority,
            after.standing,
            after.band,
            after.rank,
        ):
            changes.append(PreviewChange(account_id, name, before, after))
    changes.sort(key=lambda c: (-c.proposed.priority, c.account_name))
    return ScoringPreviewResult(
        draft_version=draft.version,
        active_version=active_version,
        changes=changes,
        unchanged_count=len(names) - len(changes),
    )
