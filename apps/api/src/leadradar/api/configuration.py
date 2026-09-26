"""Router of the [Services and questions](/architecture/interfaces.md#services-and-questions)
(`API-07` to `API-13`), [Scoring](/architecture/interfaces.md#scoring) (`API-15` to `API-17`) and
[Industries and markets](/architecture/interfaces.md#industries-and-markets) (`API-71` to
`API-76`) families. `API-14` (try a question), `API-18` (activate) and `API-19` (preview impact)
are other tasks'."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import CurrentUser, require_admin
from leadradar.configuration import commands, queries
from leadradar.configuration.queries import (
    IndustryData,
    MarketData,
    QuestionSummary,
    ScoringConfigData,
    ScoringConfigSummary,
    ServiceSummary,
)
from leadradar.core.countries import ISO_3166_1_ALPHA_2
from leadradar.core.enums import (
    DocumentSourceType,
    FindingStrength,
    IndustryStatus,
    MarketStatus,
    ScoringConfigStatus,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
)
from leadradar.core.scoring_settings import ScoringSettingsDocument
from leadradar.db.models.identity import AppUser
from leadradar.db.session import get_session

router = APIRouter(tags=["configuration"])

_UPPER_SNAKE = r"^[A-Z][A-Z0-9_]*$"


# --- Services and questions shapes --------------------------------------------------------------


class Service(BaseModel):
    """[`Service`](/architecture/interfaces.md#service)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    code: str
    name: str
    description: str
    value_proposition: str
    status: ServiceStatus
    active_version: int | None
    draft_version: int | None
    question_count: int


class ServiceCreate(BaseModel):
    """[`ServiceCreate`](/architecture/interfaces.md#servicecreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=_UPPER_SNAKE)
    name: str
    description: str
    value_proposition: str


class ServiceUpdate(BaseModel):
    """[`ServiceUpdate`](/architecture/interfaces.md#serviceupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = None
    description: str | None = None
    value_proposition: str | None = None
    status: ServiceStatus | None = None


class QuestionOption(BaseModel):
    """One entry of [`SignalQuestion`](/architecture/interfaces.md#signalquestion) `options`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=_UPPER_SNAKE)
    label: str
    strength: FindingStrength


class SignalQuestion(BaseModel):
    """[`SignalQuestion`](/architecture/interfaces.md#signalquestion)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    service_id: uuid.UUID
    key: str
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[QuestionOption] | None
    polarity: SignalQuestionPolarity
    source_types: list[DocumentSourceType]
    hint_terms: list[str]
    revision: int
    status: SignalQuestionStatus
    finding_count: int


class SignalQuestionCreate(BaseModel):
    """[`SignalQuestionCreate`](/architecture/interfaces.md#signalquestioncreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=_UPPER_SNAKE)
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[QuestionOption] | None = None
    polarity: SignalQuestionPolarity
    source_types: list[DocumentSourceType] = Field(min_length=1)
    hint_terms: list[str] = []


class SignalQuestionUpdate(BaseModel):
    """[`SignalQuestionUpdate`](/architecture/interfaces.md#signalquestionupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str | None = None
    answer_type: SignalQuestionAnswerType | None = None
    options: list[QuestionOption] | None = None
    source_types: list[DocumentSourceType] | None = None
    hint_terms: list[str] | None = None
    status: SignalQuestionStatus | None = None


def _to_service(summary: ServiceSummary) -> Service:
    return Service(
        id=summary.id,
        code=summary.code,
        name=summary.name,
        description=summary.description,
        value_proposition=summary.value_proposition,
        status=summary.status,
        active_version=summary.active_version,
        draft_version=summary.draft_version,
        question_count=summary.question_count,
    )


def _to_signal_question(summary: QuestionSummary) -> SignalQuestion:
    return SignalQuestion(
        id=summary.id,
        service_id=summary.service_id,
        key=summary.key,
        text=summary.text,
        answer_type=summary.answer_type,
        options=(
            [QuestionOption(**option) for option in summary.options]
            if summary.options is not None
            else None
        ),
        polarity=summary.polarity,
        source_types=[DocumentSourceType(value) for value in summary.source_types],
        hint_terms=summary.hint_terms,
        revision=summary.revision,
        status=summary.status,
        finding_count=summary.finding_count,
    )


def _options_payload(options: list[QuestionOption] | None) -> list[dict[str, object]] | None:
    return [option.model_dump(mode="json") for option in options] if options is not None else None


@router.get("/services")
async def list_services(
    user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[Service]:
    """`API-07`."""
    summaries = await queries.list_services(session)
    return [_to_service(summary) for summary in summaries]


@router.post("/services")
async def create_service_route(
    body: ServiceCreate,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Service:
    """`API-08`."""
    now: datetime = request.app.state.clock()
    summary = await commands.create_service(
        session,
        code=body.code,
        name=body.name,
        description=body.description,
        value_proposition=body.value_proposition,
        actor_id=admin.id,
        now=now,
    )
    return _to_service(summary)


@router.get("/services/{id}")
async def get_service_route(
    id: uuid.UUID, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
) -> Service:
    """`API-09`."""
    summary = await queries.get_service(session, id)
    return _to_service(summary)


@router.patch("/services/{id}")
async def update_service_route(
    id: uuid.UUID,
    body: ServiceUpdate,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Service:
    """`API-10`."""
    now: datetime = request.app.state.clock()
    summary = await commands.update_service(
        session,
        service_id=id,
        name=body.name,
        description=body.description,
        value_proposition=body.value_proposition,
        status=body.status,
        actor_id=admin.id,
        now=now,
    )
    return _to_service(summary)


@router.get("/services/{id}/questions")
async def list_questions_route(
    id: uuid.UUID, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[SignalQuestion]:
    """`API-11`."""
    summaries = await queries.list_questions(session, id)
    return [_to_signal_question(summary) for summary in summaries]


@router.post("/services/{id}/questions")
async def create_question_route(
    id: uuid.UUID,
    body: SignalQuestionCreate,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SignalQuestion:
    """`API-12`."""
    now: datetime = request.app.state.clock()
    summary = await commands.create_question(
        session,
        service_id=id,
        key=body.key,
        text=body.text,
        answer_type=body.answer_type,
        options=_options_payload(body.options),
        polarity=body.polarity,
        source_types=body.source_types,
        hint_terms=body.hint_terms,
        actor_id=admin.id,
        now=now,
    )
    return _to_signal_question(summary)


@router.patch("/questions/{id}")
async def update_question_route(
    id: uuid.UUID,
    body: SignalQuestionUpdate,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SignalQuestion:
    """`API-13`."""
    now: datetime = request.app.state.clock()
    summary = await commands.update_question(
        session,
        question_id=id,
        text=body.text,
        answer_type=body.answer_type,
        options=_options_payload(body.options),
        source_types=body.source_types,
        hint_terms=body.hint_terms,
        status=body.status,
        actor_id=admin.id,
        now=now,
    )
    return _to_signal_question(summary)


# --- Scoring shapes ------------------------------------------------------------------------------


class ScoringConfigSummaryModel(BaseModel):
    """[`ScoringConfigSummary`](/architecture/interfaces.md#scoringconfigsummary)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    service_id: uuid.UUID
    version: int
    status: ScoringConfigStatus
    change_note: str | None
    activated_at: datetime | None
    activated_by_name: str | None


class ScoringConfigModel(ScoringConfigSummaryModel):
    """[`ScoringConfig`](/architecture/interfaces.md#scoringconfig)."""

    settings: dict[str, object]


class ScoringDraftUpdate(BaseModel):
    """[`ScoringDraftUpdate`](/architecture/interfaces.md#scoringdraftupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    settings: ScoringSettingsDocument
    change_note: str | None = None


def _to_scoring_config_summary(summary: ScoringConfigSummary) -> ScoringConfigSummaryModel:
    return ScoringConfigSummaryModel(
        id=summary.id,
        service_id=summary.service_id,
        version=summary.version,
        status=summary.status,
        change_note=summary.change_note,
        activated_at=summary.activated_at,
        activated_by_name=summary.activated_by_name,
    )


def _to_scoring_config(data: ScoringConfigData) -> ScoringConfigModel:
    summary = _to_scoring_config_summary(data.summary)
    return ScoringConfigModel(**summary.model_dump(), settings=data.settings)


@router.get("/services/{id}/scoring-configs")
async def list_scoring_configs_route(
    id: uuid.UUID, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[ScoringConfigSummaryModel]:
    """`API-15`."""
    summaries = await queries.list_scoring_configs(session, id)
    return [_to_scoring_config_summary(summary) for summary in summaries]


@router.get("/scoring-configs/{id}")
async def get_scoring_config_route(
    id: uuid.UUID, user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]
) -> ScoringConfigModel:
    """`API-16`."""
    data = await queries.get_scoring_config(session, id)
    return _to_scoring_config(data)


@router.put("/services/{id}/scoring-configs/draft")
async def save_scoring_draft_route(
    id: uuid.UUID,
    body: ScoringDraftUpdate,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScoringConfigModel:
    """`API-17`."""
    now: datetime = request.app.state.clock()
    data = await commands.save_scoring_draft(
        session,
        service_id=id,
        settings=body.settings,
        change_note=body.change_note,
        actor_id=admin.id,
        now=now,
    )
    return _to_scoring_config(data)


# --- Industries and markets shapes ---------------------------------------------------------------


class Industry(BaseModel):
    """[`Industry`](/architecture/interfaces.md#industry)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    label: str
    status: IndustryStatus
    account_count: int


class IndustryCreate(BaseModel):
    """[`IndustryCreate`](/architecture/interfaces.md#industrycreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=_UPPER_SNAKE)
    label: str


class IndustryUpdate(BaseModel):
    """[`IndustryUpdate`](/architecture/interfaces.md#industryupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str | None = None
    status: IndustryStatus | None = None


class Market(BaseModel):
    """[`Market`](/architecture/interfaces.md#market)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    name: str
    country_codes: list[str]
    status: MarketStatus


class MarketCreate(BaseModel):
    """[`MarketCreate`](/architecture/interfaces.md#marketcreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=_UPPER_SNAKE)
    name: str
    country_codes: list[str] = Field(min_length=1)

    @field_validator("country_codes")
    @classmethod
    def _valid_countries(cls, value: list[str]) -> list[str]:
        invalid = [code for code in value if code not in ISO_3166_1_ALPHA_2]
        if invalid:
            raise ValueError(f"not a valid ISO 3166-1 alpha-2 country code: {', '.join(invalid)}")
        return value


class MarketUpdate(BaseModel):
    """[`MarketUpdate`](/architecture/interfaces.md#marketupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = None
    country_codes: list[str] | None = Field(default=None, min_length=1)
    status: MarketStatus | None = None

    @field_validator("country_codes")
    @classmethod
    def _valid_countries(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        invalid = [code for code in value if code not in ISO_3166_1_ALPHA_2]
        if invalid:
            raise ValueError(f"not a valid ISO 3166-1 alpha-2 country code: {', '.join(invalid)}")
        return value


def _to_industry(data: IndustryData) -> Industry:
    return Industry(
        code=data.code, label=data.label, status=data.status, account_count=data.account_count
    )


def _to_market(data: MarketData) -> Market:
    return Market(
        code=data.code, name=data.name, country_codes=data.country_codes, status=data.status
    )


@router.get("/industries")
async def list_industries_route(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    status: Annotated[IndustryStatus | None, Query()] = None,
) -> list[Industry]:
    """`API-71`."""
    data = await queries.list_industries(session, status)
    return [_to_industry(item) for item in data]


@router.post("/industries")
async def create_industry_route(
    body: IndustryCreate,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Industry:
    """`API-72`."""
    now: datetime = request.app.state.clock()
    data = await commands.create_industry(
        session, code=body.code, label=body.label, actor_id=admin.id, now=now
    )
    return _to_industry(data)


@router.patch("/industries/{code}")
async def update_industry_route(
    code: str,
    body: IndustryUpdate,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Industry:
    """`API-73`."""
    now: datetime = request.app.state.clock()
    data = await commands.update_industry(
        session, code=code, label=body.label, status=body.status, actor_id=admin.id, now=now
    )
    return _to_industry(data)


@router.get("/markets")
async def list_markets_route(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    status: Annotated[MarketStatus | None, Query()] = None,
) -> list[Market]:
    """`API-74`."""
    data = await queries.list_markets(session, status)
    return [_to_market(item) for item in data]


@router.post("/markets")
async def create_market_route(
    body: MarketCreate,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Market:
    """`API-75`."""
    now: datetime = request.app.state.clock()
    data = await commands.create_market(
        session,
        code=body.code,
        name=body.name,
        country_codes=body.country_codes,
        actor_id=admin.id,
        now=now,
    )
    return _to_market(data)


@router.patch("/markets/{code}")
async def update_market_route(
    code: str,
    body: MarketUpdate,
    request: Request,
    admin: Annotated[AppUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Market:
    """`API-76`."""
    now: datetime = request.app.state.clock()
    data = await commands.update_market(
        session,
        code=code,
        name=body.name,
        country_codes=body.country_codes,
        status=body.status,
        actor_id=admin.id,
        now=now,
    )
    return _to_market(data)
