"""Reads that shape the [Services and questions]
(/architecture/interfaces.md#services-and-questions), [Scoring]
(/architecture/interfaces.md#scoring) and [Industries and markets]
(/architecture/interfaces.md#industries-and-markets) responses out of the store. Plain
dataclasses, not Pydantic models: those live at the api boundary (`api/configuration.py`), which
shapes its response from these."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.configuration.errors import (
    IndustryNotFound,
    MarketNotFound,
    QuestionNotFound,
    ScoringConfigNotFound,
    ServiceNotFound,
)
from leadradar.core.enums import (
    FindingStatus,
    IndustryStatus,
    MarketStatus,
    ScoringConfigStatus,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import (
    Industry,
    Market,
    ScoringConfig,
    Service,
    SignalQuestion,
)
from leadradar.db.models.identity import AppUser
from leadradar.db.models.signals import Finding


@dataclass(frozen=True)
class ServiceSummary:
    """[`Service`](/architecture/interfaces.md#service)."""

    id: uuid.UUID
    code: str
    name: str
    description: str
    value_proposition: str
    status: ServiceStatus
    active_version: int | None
    draft_version: int | None
    question_count: int


@dataclass(frozen=True)
class QuestionSummary:
    """[`SignalQuestion`](/architecture/interfaces.md#signalquestion)."""

    id: uuid.UUID
    service_id: uuid.UUID
    key: str
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[dict[str, object]] | None
    polarity: SignalQuestionPolarity
    source_types: list[str]
    hint_terms: list[str]
    revision: int
    status: SignalQuestionStatus
    finding_count: int


@dataclass(frozen=True)
class ScoringConfigSummary:
    """[`ScoringConfigSummary`](/architecture/interfaces.md#scoringconfigsummary)."""

    id: uuid.UUID
    service_id: uuid.UUID
    version: int
    status: ScoringConfigStatus
    change_note: str | None
    activated_at: datetime | None
    activated_by_name: str | None


@dataclass(frozen=True)
class ScoringConfigData:
    """[`ScoringConfig`](/architecture/interfaces.md#scoringconfig): `summary`'s fields plus
    `settings`."""

    summary: ScoringConfigSummary
    settings: dict[str, object]


@dataclass(frozen=True)
class IndustryData:
    """[`Industry`](/architecture/interfaces.md#industry)."""

    code: str
    label: str
    status: IndustryStatus
    account_count: int


@dataclass(frozen=True)
class MarketData:
    """[`Market`](/architecture/interfaces.md#market)."""

    code: str
    name: str
    country_codes: list[str]
    status: MarketStatus


async def _question_count(session: AsyncSession, service_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(SignalQuestion)
            .where(
                SignalQuestion.service_id == service_id,
                SignalQuestion.status == SignalQuestionStatus.ACTIVE,
            )
        )
    ).scalar_one()


async def _versions(session: AsyncSession, service_id: uuid.UUID) -> tuple[int | None, int | None]:
    """`(active_version, draft_version)`, either `None` when that version does not exist."""
    rows = (
        await session.execute(
            select(ScoringConfig.status, ScoringConfig.version).where(
                ScoringConfig.service_id == service_id,
                ScoringConfig.status.in_([ScoringConfigStatus.ACTIVE, ScoringConfigStatus.DRAFT]),
            )
        )
    ).all()
    active_version = next((v for s, v in rows if s == ScoringConfigStatus.ACTIVE), None)
    draft_version = next((v for s, v in rows if s == ScoringConfigStatus.DRAFT), None)
    return active_version, draft_version


async def _service_summary(session: AsyncSession, service: Service) -> ServiceSummary:
    active_version, draft_version = await _versions(session, service.id)
    question_count = await _question_count(session, service.id)
    return ServiceSummary(
        id=service.id,
        code=service.code,
        name=service.name,
        description=service.description,
        value_proposition=service.value_proposition,
        status=service.status,
        active_version=active_version,
        draft_version=draft_version,
        question_count=question_count,
    )


async def list_services(session: AsyncSession) -> list[ServiceSummary]:
    """`API-07`, ordered by `name` (G8)."""
    services = (await session.execute(select(Service).order_by(Service.name))).scalars().all()
    return [await _service_summary(session, service) for service in services]


async def get_service(session: AsyncSession, service_id: uuid.UUID) -> ServiceSummary:
    """`API-09`. Raises `ServiceNotFound`."""
    service = (
        await session.execute(select(Service).where(Service.id == service_id))
    ).scalar_one_or_none()
    if service is None:
        raise ServiceNotFound(f"No service {service_id}.")
    return await _service_summary(session, service)


async def require_service(session: AsyncSession, service_id: uuid.UUID) -> Service:
    """The [`service`](/architecture/sql-store.md#service) row, or `ServiceNotFound`; the
    smallest read a write needs before it locks and changes the row."""
    service = (
        await session.execute(select(Service).where(Service.id == service_id))
    ).scalar_one_or_none()
    if service is None:
        raise ServiceNotFound(f"No service {service_id}.")
    return service


async def _finding_count(session: AsyncSession, question_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Finding)
            .where(Finding.question_id == question_id, Finding.status == FindingStatus.ACTIVE)
        )
    ).scalar_one()


def question_options(value: object) -> list[dict[str, object]] | None:
    """`question.options` narrowed to the shape [`signal_question`]
    (/architecture/sql-store.md#signal_question) `options` actually holds: a list of `{key,
    label, strength}` objects, or `None`. The column itself is loosely typed (plain JSONB) since
    it is `None` for every non-`CHOICE` answer type."""
    return cast("list[dict[str, object]] | None", value if isinstance(value, list) else None)


async def question_summary(session: AsyncSession, question: SignalQuestion) -> QuestionSummary:
    """[`SignalQuestion`](/architecture/interfaces.md#signalquestion) shaped from an already
    loaded row, its `finding_count` computed on read."""
    count = await _finding_count(session, question.id)
    options = question_options(question.options)
    return QuestionSummary(
        id=question.id,
        service_id=question.service_id,
        key=question.key,
        text=question.text,
        answer_type=question.answer_type,
        options=options,
        polarity=question.polarity,
        source_types=list(question.source_types),
        hint_terms=list(question.hint_terms),
        revision=question.revision,
        status=question.status,
        finding_count=count,
    )


async def list_questions(session: AsyncSession, service_id: uuid.UUID) -> list[QuestionSummary]:
    """`API-11`, active first, then `key` (`FR-150`). Raises `ServiceNotFound`."""
    await require_service(session, service_id)
    questions = (
        (
            await session.execute(
                select(SignalQuestion)
                .where(SignalQuestion.service_id == service_id)
                .order_by(SignalQuestion.status, SignalQuestion.key)
            )
        )
        .scalars()
        .all()
    )
    return [await question_summary(session, question) for question in questions]


async def require_question(session: AsyncSession, question_id: uuid.UUID) -> SignalQuestion:
    """The [`signal_question`](/architecture/sql-store.md#signal_question) row, or
    `QuestionNotFound`."""
    question = (
        await session.execute(select(SignalQuestion).where(SignalQuestion.id == question_id))
    ).scalar_one_or_none()
    if question is None:
        raise QuestionNotFound(f"No question {question_id}.")
    return question


async def active_question_keys(session: AsyncSession, service_id: uuid.UUID) -> frozenset[str]:
    """Every `ACTIVE` [`signal_question`](/architecture/sql-store.md#signal_question) `key` of
    the service ([Scoring settings validation](/architecture/rules.md#scoring-settings-validation)
    bullet 6)."""
    keys = (
        (
            await session.execute(
                select(SignalQuestion.key).where(
                    SignalQuestion.service_id == service_id,
                    SignalQuestion.status == SignalQuestionStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .all()
    )
    return frozenset(keys)


async def active_industry_codes(session: AsyncSession) -> frozenset[str]:
    """Every `ACTIVE` [`industry`](/architecture/sql-store.md#industry) `code` ([Scoring settings
    validation](/architecture/rules.md#scoring-settings-validation) bullet 5)."""
    codes = (
        (
            await session.execute(
                select(Industry.code).where(Industry.status == IndustryStatus.ACTIVE)
            )
        )
        .scalars()
        .all()
    )
    return frozenset(codes)


def _scoring_config_summary(
    config: ScoringConfig, activated_by_name: str | None
) -> ScoringConfigSummary:
    return ScoringConfigSummary(
        id=config.id,
        service_id=config.service_id,
        version=config.version,
        status=config.status,
        change_note=config.change_note,
        activated_at=config.activated_at,
        activated_by_name=activated_by_name,
    )


async def list_scoring_configs(
    session: AsyncSession, service_id: uuid.UUID
) -> list[ScoringConfigSummary]:
    """`API-15`, newest version first. Raises `ServiceNotFound`."""
    await require_service(session, service_id)
    rows = (
        await session.execute(
            select(ScoringConfig, AppUser.display_name)
            .outerjoin(AppUser, AppUser.id == ScoringConfig.activated_by)
            .where(ScoringConfig.service_id == service_id)
            .order_by(ScoringConfig.version.desc())
        )
    ).all()
    return [_scoring_config_summary(config, name) for config, name in rows]


async def get_scoring_config(
    session: AsyncSession, scoring_config_id: uuid.UUID
) -> ScoringConfigData:
    """`API-16`. Raises `ScoringConfigNotFound`."""
    row = (
        await session.execute(
            select(ScoringConfig, AppUser.display_name)
            .outerjoin(AppUser, AppUser.id == ScoringConfig.activated_by)
            .where(ScoringConfig.id == scoring_config_id)
        )
    ).first()
    if row is None:
        raise ScoringConfigNotFound(f"No scoring config {scoring_config_id}.")
    config, name = row
    return ScoringConfigData(
        summary=_scoring_config_summary(config, name), settings=config.settings
    )


async def list_industries(
    session: AsyncSession, status: IndustryStatus | None = None
) -> list[IndustryData]:
    """`API-71`, active first, then `label` (`FR-154`)."""
    counts = (
        select(Account.industry, func.count().label("account_count"))
        .group_by(Account.industry)
        .subquery()
    )
    stmt = (
        select(Industry, func.coalesce(counts.c.account_count, 0))
        .outerjoin(counts, counts.c.industry == Industry.code)
        .order_by(Industry.status, Industry.label)
    )
    if status is not None:
        stmt = stmt.where(Industry.status == status)
    rows = (await session.execute(stmt)).all()
    return [
        IndustryData(
            code=industry.code, label=industry.label, status=industry.status, account_count=count
        )
        for industry, count in rows
    ]


async def require_industry(session: AsyncSession, code: str) -> Industry:
    """The [`industry`](/architecture/sql-store.md#industry) row, or `IndustryNotFound`."""
    industry = (
        await session.execute(select(Industry).where(Industry.code == code))
    ).scalar_one_or_none()
    if industry is None:
        raise IndustryNotFound(f"No industry {code}.")
    return industry


async def industry_data(session: AsyncSession, industry: Industry) -> IndustryData:
    """[`Industry`](/architecture/interfaces.md#industry) shaped from an already loaded row, its
    `account_count` computed on read."""
    count = (
        await session.execute(
            select(func.count()).select_from(Account).where(Account.industry == industry.code)
        )
    ).scalar_one()
    return IndustryData(
        code=industry.code, label=industry.label, status=industry.status, account_count=count
    )


async def list_markets(
    session: AsyncSession, status: MarketStatus | None = None
) -> list[MarketData]:
    """`API-74`, active first, then `name` (`FR-154`)."""
    stmt = select(Market).order_by(Market.status, Market.name)
    if status is not None:
        stmt = stmt.where(Market.status == status)
    markets = (await session.execute(stmt)).scalars().all()
    return [
        MarketData(code=m.code, name=m.name, country_codes=list(m.country_codes), status=m.status)
        for m in markets
    ]


async def require_market(session: AsyncSession, code: str) -> Market:
    """The [`market`](/architecture/sql-store.md#market) row, or `MarketNotFound`."""
    market = (await session.execute(select(Market).where(Market.code == code))).scalar_one_or_none()
    if market is None:
        raise MarketNotFound(f"No market {code}.")
    return market
