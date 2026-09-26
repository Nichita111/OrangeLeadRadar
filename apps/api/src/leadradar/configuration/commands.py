"""Writes of the configuration capability ([Services and questions]
(/architecture/interfaces.md#services-and-questions), [Scoring]
(/architecture/interfaces.md#scoring), [Industries and markets]
(/architecture/interfaces.md#industries-and-markets); `S-CFG-01`, `S-CFG-02`, `S-CFG-03`,
`S-CFG-07`) - each in one transaction it owns, with its audit row
([api Design](/architecture/services/api.md#design) Transactions).

Reclassification (a question's `RECLASSIFY` run) and scoring activation (`API-18`) are other
tasks' (`S-CFG-04`, reclassify-after-change); this module creates and edits questions and drafts
but never enqueues either.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.configuration import queries
from leadradar.configuration.errors import (
    DraftInvalid,
    IndustryConflict,
    IndustryNotFound,
    MarketConflict,
    MarketNotFound,
    QuestionInvalid,
    QuestionKeyConflict,
    QuestionNotFound,
    ServiceConflict,
)
from leadradar.configuration.queries import (
    IndustryData,
    MarketData,
    QuestionSummary,
    ScoringConfigData,
    ServiceSummary,
    industry_data,
    require_service,
)
from leadradar.core.enums import (
    AuditAction,
    DocumentSourceType,
    IndustryStatus,
    MarketStatus,
    ScoringConfigStatus,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
)
from leadradar.core.questions import validate_question_shape
from leadradar.core.scoring_settings import (
    ScoringSettingsDocument,
    add_question,
    default_scoring_settings,
    drop_retired_industries,
    remove_question,
    validate_scoring_settings,
)
from leadradar.core.sign_in import changed_fields
from leadradar.db.models.configuration import (
    Industry,
    Market,
    ScoringConfig,
    Service,
    SignalQuestion,
)


async def _ensure_draft(session: AsyncSession, service: Service) -> ScoringConfig:
    """The service's `DRAFT` [`scoring_config`](/architecture/sql-store.md#scoring_config), or a
    fresh one copied from the `ACTIVE` version with any retired industry dropped from its `INDUSTRY`
    criteria ([FL-22](/features/service-configuration.md#fl-22-maintain-industries-and-markets)
    step 3, `API-12`'s and `API-17`'s note). A service always has one or the other."""
    draft = (
        await session.execute(
            select(ScoringConfig)
            .where(
                ScoringConfig.service_id == service.id,
                ScoringConfig.status == ScoringConfigStatus.DRAFT,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if draft is not None:
        return draft

    active = (
        await session.execute(
            select(ScoringConfig).where(
                ScoringConfig.service_id == service.id,
                ScoringConfig.status == ScoringConfigStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    assert active is not None, "a service always has a draft or an active scoring config"

    active_codes = await queries.active_industry_codes(session)
    document = drop_retired_industries(
        ScoringSettingsDocument.model_validate(active.settings), active_codes
    )

    draft = ScoringConfig(
        service_id=service.id,
        version=active.version + 1,
        status=ScoringConfigStatus.DRAFT,
        settings=document.model_dump(mode="json"),
        change_note=None,
        activated_at=None,
        activated_by=None,
    )
    session.add(draft)
    await session.flush()
    return draft


# --- Services ---------------------------------------------------------------------------------


async def create_service(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    description: str,
    value_proposition: str,
    actor_id: uuid.UUID,
    now: datetime,
) -> ServiceSummary:
    """`API-08`: creates the service and its first scoring draft with the [scoring settings
    document](/architecture/sql-store.md#scoring-settings-document) defaults (`S-CFG-01`). Raises
    `ServiceConflict` on a `code` or `name` already used."""
    service = Service(
        code=code,
        name=name,
        description=description,
        value_proposition=value_proposition,
        status=ServiceStatus.ACTIVE,
    )
    session.add(service)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing_id = (
            await session.execute(
                select(Service.id).where(or_(Service.code == code, Service.name == name))
            )
        ).scalar_one()
        raise ServiceConflict(
            "A service with that code or name already exists.", entity_id=str(existing_id)
        ) from None

    session.add(
        ScoringConfig(
            service_id=service.id,
            version=1,
            status=ScoringConfigStatus.DRAFT,
            settings=default_scoring_settings().model_dump(mode="json"),
            change_note=None,
            activated_at=None,
            activated_by=None,
        )
    )

    await append_audit_event(
        session,
        action=AuditAction.SERVICE_CREATED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="service",
        entity_id=service.id,
        payload={"code": code},
    )
    await session.commit()
    return await queries.get_service(session, service.id)


async def update_service(
    session: AsyncSession,
    *,
    service_id: uuid.UUID,
    name: str | None,
    description: str | None,
    value_proposition: str | None,
    status: ServiceStatus | None,
    actor_id: uuid.UUID,
    now: datetime,
) -> ServiceSummary:
    """`API-10`. `code` is not settable. Raises `ServiceNotFound`, `ServiceConflict` on a `name`
    already used.

    Reactivating a service (`INACTIVE` to `ACTIVE`) reclassifies every active question
    ([Services and questions](/architecture/interfaces.md#services-and-questions) `API-10`'s
    note); that reclassification is issue #21's, so this function only records the status
    change."""
    service = await require_service(session, service_id)

    sent: dict[str, object] = {}
    if name is not None:
        sent["name"] = name
    if description is not None:
        sent["description"] = description
    if value_proposition is not None:
        sent["value_proposition"] = value_proposition
    if status is not None:
        sent["status"] = status
    current = {
        "name": service.name,
        "description": service.description,
        "value_proposition": service.value_proposition,
        "status": service.status,
    }
    changes = changed_fields(current, sent)

    if name is not None and "name" in changes:
        service.name = name
    if description is not None and "description" in changes:
        service.description = description
    if value_proposition is not None and "value_proposition" in changes:
        service.value_proposition = value_proposition
    if status is not None and "status" in changes:
        service.status = status

    if changes:
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            existing_id = (
                await session.execute(select(Service.id).where(Service.name == name))
            ).scalar_one()
            raise ServiceConflict(
                "A service with that name already exists.", entity_id=str(existing_id)
            ) from None

        await append_audit_event(
            session,
            action=AuditAction.SERVICE_UPDATED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type="service",
            entity_id=service.id,
            payload=changes,
        )
    await session.commit()
    return await queries.get_service(session, service.id)


# --- Signal questions --------------------------------------------------------------------------


async def create_question(
    session: AsyncSession,
    *,
    service_id: uuid.UUID,
    key: str,
    text: str,
    answer_type: SignalQuestionAnswerType,
    options: list[dict[str, object]] | None,
    polarity: SignalQuestionPolarity,
    source_types: list[DocumentSourceType],
    hint_terms: list[str],
    actor_id: uuid.UUID,
    now: datetime,
) -> QuestionSummary:
    """`API-12`: joins the draft at weight `MEDIUM`, creating it from the active version if none
    exists (`S-CFG-02`). Raises `ServiceNotFound`, `QuestionInvalid` on a bad `options` shape,
    `QuestionKeyConflict` on a `key` already used within the service."""
    service = await require_service(session, service_id)

    shape_errors = validate_question_shape(answer_type, options)
    if shape_errors:
        raise QuestionInvalid(shape_errors)

    question = SignalQuestion(
        service_id=service_id,
        key=key,
        text=text,
        answer_type=answer_type,
        options=options,
        polarity=polarity,
        source_types=[source.value for source in source_types],
        hint_terms=list(hint_terms),
        revision=1,
        status=SignalQuestionStatus.ACTIVE,
    )
    session.add(question)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing_id = (
            await session.execute(
                select(SignalQuestion.id).where(
                    SignalQuestion.service_id == service_id, SignalQuestion.key == key
                )
            )
        ).scalar_one()
        raise QuestionKeyConflict(
            "A question with that key already exists for this service.", entity_id=str(existing_id)
        ) from None

    draft = await _ensure_draft(session, service)
    document = ScoringSettingsDocument.model_validate(draft.settings)
    draft.settings = add_question(document, key).model_dump(mode="json")

    await append_audit_event(
        session,
        action=AuditAction.QUESTION_CREATED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="signal_question",
        entity_id=question.id,
        payload={"key": key, "revision": 1},
    )
    await session.commit()
    return await queries.question_summary(session, question)


_SHAPE_FIELDS = frozenset({"text", "answer_type", "options", "source_types"})


async def update_question(
    session: AsyncSession,
    *,
    question_id: uuid.UUID,
    text: str | None,
    answer_type: SignalQuestionAnswerType | None,
    options: list[dict[str, object]] | None,
    source_types: list[DocumentSourceType] | None,
    hint_terms: list[str] | None,
    status: SignalQuestionStatus | None,
    actor_id: uuid.UUID,
    now: datetime,
) -> QuestionSummary:
    """`API-13` (`S-CFG-02`): a change to `text`, `answer_type`, `options` or `source_types`
    increments `revision`; deactivating removes the question from the draft, reactivating adds it
    back at weight `MEDIUM`. Raises `QuestionNotFound`, `QuestionInvalid` on a bad `options`
    shape.

    Reclassification is issue #21's: this function increments `revision` and updates the draft's
    `questions` but enqueues no `RECLASSIFY` run."""
    question = (
        await session.execute(
            select(SignalQuestion).where(SignalQuestion.id == question_id).with_for_update()
        )
    ).scalar_one_or_none()
    if question is None:
        raise QuestionNotFound(f"No question {question_id}.")

    sent: dict[str, object] = {}
    if text is not None:
        sent["text"] = text
    if answer_type is not None:
        sent["answer_type"] = answer_type
    if options is not None:
        sent["options"] = options
    if source_types is not None:
        sent["source_types"] = [source.value for source in source_types]
    if hint_terms is not None:
        sent["hint_terms"] = list(hint_terms)
    if status is not None:
        sent["status"] = status

    current = {
        "text": question.text,
        "answer_type": question.answer_type,
        "options": question.options,
        "source_types": question.source_types,
        "hint_terms": question.hint_terms,
        "status": question.status,
    }
    changes = changed_fields(current, sent)

    if _SHAPE_FIELDS & changes.keys():
        effective_answer_type = answer_type if answer_type is not None else question.answer_type
        effective_options = (
            options if options is not None else queries.question_options(question.options)
        )
        shape_errors = validate_question_shape(effective_answer_type, effective_options)
        if shape_errors:
            raise QuestionInvalid(shape_errors)

    activating = changes.get("status") == SignalQuestionStatus.ACTIVE
    deactivating = changes.get("status") == SignalQuestionStatus.INACTIVE
    revision_bumped = bool(_SHAPE_FIELDS & changes.keys())

    if text is not None and "text" in changes:
        question.text = text
    if answer_type is not None and "answer_type" in changes:
        question.answer_type = answer_type
    if options is not None and "options" in changes:
        question.options = cast("list[object]", options)
    if source_types is not None and "source_types" in changes:
        question.source_types = [source.value for source in source_types]
    if hint_terms is not None and "hint_terms" in changes:
        question.hint_terms = list(hint_terms)
    if status is not None and "status" in changes:
        question.status = status
    if revision_bumped:
        question.revision += 1

    if activating or deactivating:
        service = await require_service(session, question.service_id)
        draft = await _ensure_draft(session, service)
        document = ScoringSettingsDocument.model_validate(draft.settings)
        document = (
            add_question(document, question.key)
            if activating
            else remove_question(document, question.key)
        )
        draft.settings = document.model_dump(mode="json")

    if changes:
        await append_audit_event(
            session,
            action=AuditAction.QUESTION_UPDATED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type="signal_question",
            entity_id=question.id,
            payload={**changes, "revision": question.revision},
        )
    await session.commit()
    return await queries.question_summary(session, question)


# --- Scoring drafts ----------------------------------------------------------------------------


async def save_scoring_draft(
    session: AsyncSession,
    *,
    service_id: uuid.UUID,
    settings: ScoringSettingsDocument,
    change_note: str | None,
    actor_id: uuid.UUID,
    now: datetime,
) -> ScoringConfigData:
    """`API-17` (`S-CFG-03`): creates the draft from the active version when none exists, then
    replaces its settings once they pass [Scoring settings validation]
    (/architecture/rules.md#scoring-settings-validation). Raises `ServiceNotFound`, `DraftInvalid`
    with every violation."""
    service = await require_service(session, service_id)
    draft = await _ensure_draft(session, service)

    question_keys = await queries.active_question_keys(session, service_id)
    industry_codes = await queries.active_industry_codes(session)
    violations = validate_scoring_settings(
        settings, active_question_keys=question_keys, active_industry_codes=industry_codes
    )
    if violations:
        raise DraftInvalid(violations)

    draft.settings = settings.model_dump(mode="json")
    if change_note is not None:
        draft.change_note = change_note

    await append_audit_event(
        session,
        action=AuditAction.SCORING_DRAFT_SAVED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="scoring_config",
        entity_id=draft.id,
        payload={"version": draft.version},
    )
    await session.commit()
    return await queries.get_scoring_config(session, draft.id)


# --- Industries and markets ---------------------------------------------------------------------


async def create_industry(
    session: AsyncSession, *, code: str, label: str, actor_id: uuid.UUID, now: datetime
) -> IndustryData:
    """`API-72` (`S-CFG-07`). Raises `IndustryConflict` on a `code` or `label` already used."""
    industry = Industry(code=code, label=label, status=IndustryStatus.ACTIVE)
    session.add(industry)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing_id = (
            await session.execute(
                select(Industry.id).where(or_(Industry.code == code, Industry.label == label))
            )
        ).scalar_one()
        raise IndustryConflict(
            "An industry with that code or label already exists.", entity_id=str(existing_id)
        ) from None

    await append_audit_event(
        session,
        action=AuditAction.INDUSTRY_CREATED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="industry",
        entity_id=industry.id,
        payload={"code": code},
    )
    await session.commit()
    return await industry_data(session, industry)


async def update_industry(
    session: AsyncSession,
    *,
    code: str,
    label: str | None,
    status: IndustryStatus | None,
    actor_id: uuid.UUID,
    now: datetime,
) -> IndustryData:
    """`API-73` (`S-CFG-07`): `code` is not settable; setting `status` `INACTIVE` retires the
    industry - it leaves pickers and validation, but every account and saved scoring version that
    names it keeps it. Raises `IndustryNotFound`, `IndustryConflict` on a `label` already used."""
    industry = (
        await session.execute(select(Industry).where(Industry.code == code).with_for_update())
    ).scalar_one_or_none()
    if industry is None:
        raise IndustryNotFound(f"No industry {code}.")

    sent: dict[str, object] = {}
    if label is not None:
        sent["label"] = label
    if status is not None:
        sent["status"] = status
    changes = changed_fields({"label": industry.label, "status": industry.status}, sent)

    if label is not None and "label" in changes:
        industry.label = label
    if status is not None and "status" in changes:
        industry.status = status

    if changes:
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            existing_id = (
                await session.execute(select(Industry.id).where(Industry.label == label))
            ).scalar_one()
            raise IndustryConflict(
                "An industry with that label already exists.", entity_id=str(existing_id)
            ) from None

        await append_audit_event(
            session,
            action=AuditAction.INDUSTRY_UPDATED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type="industry",
            entity_id=industry.id,
            payload=changes,
        )
    await session.commit()
    return await industry_data(session, industry)


async def create_market(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    country_codes: list[str],
    actor_id: uuid.UUID,
    now: datetime,
) -> MarketData:
    """`API-75` (`S-CFG-07`). Raises `MarketConflict` on a `code` or `name` already used."""
    market = Market(
        code=code, name=name, country_codes=list(country_codes), status=MarketStatus.ACTIVE
    )
    session.add(market)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing_id = (
            await session.execute(
                select(Market.id).where(or_(Market.code == code, Market.name == name))
            )
        ).scalar_one()
        raise MarketConflict(
            "A market with that code or name already exists.", entity_id=str(existing_id)
        ) from None

    await append_audit_event(
        session,
        action=AuditAction.MARKET_CREATED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="market",
        entity_id=market.id,
        payload={"code": code, "country_codes": list(country_codes)},
    )
    await session.commit()
    return MarketData(
        code=market.code,
        name=market.name,
        country_codes=list(market.country_codes),
        status=market.status,
    )


async def update_market(
    session: AsyncSession,
    *,
    code: str,
    name: str | None,
    country_codes: list[str] | None,
    status: MarketStatus | None,
    actor_id: uuid.UUID,
    now: datetime,
) -> MarketData:
    """`API-76` (`S-CFG-07`): `code` is not settable; setting `status` `INACTIVE` retires the
    market - it is not offered in the ICP editor, but a scoring version whose criterion already
    stored its countries is unchanged. Raises `MarketNotFound`, `MarketConflict` on a `name`
    already used."""
    market = (
        await session.execute(select(Market).where(Market.code == code).with_for_update())
    ).scalar_one_or_none()
    if market is None:
        raise MarketNotFound(f"No market {code}.")

    sent: dict[str, object] = {}
    if name is not None:
        sent["name"] = name
    if country_codes is not None:
        sent["country_codes"] = list(country_codes)
    if status is not None:
        sent["status"] = status
    changes = changed_fields(
        {"name": market.name, "country_codes": market.country_codes, "status": market.status}, sent
    )

    if name is not None and "name" in changes:
        market.name = name
    if country_codes is not None and "country_codes" in changes:
        market.country_codes = list(country_codes)
    if status is not None and "status" in changes:
        market.status = status

    if changes:
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            existing_id = (
                await session.execute(select(Market.id).where(Market.name == name))
            ).scalar_one()
            raise MarketConflict(
                "A market with that name already exists.", entity_id=str(existing_id)
            ) from None

        await append_audit_event(
            session,
            action=AuditAction.MARKET_UPDATED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type="market",
            entity_id=market.id,
            payload=changes,
        )
    await session.commit()
    return MarketData(
        code=market.code,
        name=market.name,
        country_codes=list(market.country_codes),
        status=market.status,
    )


__all__ = [
    "create_service",
    "update_service",
    "create_question",
    "update_question",
    "save_scoring_draft",
    "create_industry",
    "update_industry",
    "create_market",
    "update_market",
]
