"""Minimal valid rows for the integration tests, inserted with SQLAlchemy Core so a test can
build only the fixture chain its constraint needs."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, insert

from leadradar.core.enums import (
    AccountOrigin,
    AccountScoreBand,
    AccountScoreStanding,
    AccountStatus,
    AlertKind,
    AppUserRole,
    AppUserStatus,
    AuditEventKind,
    ClassificationStatus,
    DisqualifierOverrideStatus,
    DocumentSourceType,
    DocumentTriageClassifier,
    DocumentTriageOutcome,
    EvaluationItemOrigin,
    EvaluationItemStatus,
    FindingDecidedBy,
    FindingStatus,
    FindingStrength,
    IndustryStatus,
    MarketStatus,
    PipelineRunKind,
    PipelineRunStatus,
    PipelineRunTrigger,
    ScoringConfigStatus,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
    SourcePluginCode,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.audit import AuditEvent
from leadradar.db.models.configuration import (
    Industry,
    Market,
    ScoringConfig,
    Service,
    SignalQuestion,
)
from leadradar.db.models.feedback import EvaluationItem, EvaluationResult
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Chunk, Document, PipelineRun, SourcePlugin
from leadradar.db.models.signals import (
    AccountScore,
    Alert,
    Classification,
    DisqualifierOverride,
    DocumentTriage,
    Finding,
)

NOW = datetime.now(tz=UTC)


def _insert(connection: Connection, table: Any, **values: Any) -> uuid.UUID:
    row_id: uuid.UUID = connection.execute(
        insert(table).values(**values).returning(table.c.id)
    ).scalar_one()
    return row_id


def make_app_user(connection: Connection, **overrides: Any) -> uuid.UUID:
    values = {
        "email": f"user-{uuid.uuid4()}@example.com",
        "display_name": "Test User",
        "role": AppUserRole.SALES,
        "status": AppUserStatus.ACTIVE,
        "password_hash": "hash",
        "failed_logins": 0,
        "locked_until": None,
        "last_login_at": None,
    }
    values.update(overrides)
    return _insert(connection, AppUser.__table__, **values)


def make_industry(connection: Connection, **overrides: Any) -> str:
    code: str = overrides.pop("code", f"IND_{uuid.uuid4().hex[:8].upper()}")
    values = {
        "code": code,
        "label": overrides.pop("label", f"Label {code}"),
        "status": IndustryStatus.ACTIVE,
    }
    values.update(overrides)
    _insert(connection, Industry.__table__, **values)
    return code


def make_service(connection: Connection, **overrides: Any) -> uuid.UUID:
    unique = uuid.uuid4().hex[:8].upper()
    values = {
        "code": f"SERVICE_{unique}",
        "name": f"Service {unique}",
        "description": "A service.",
        "value_proposition": "A value proposition.",
        "status": ServiceStatus.ACTIVE,
    }
    values.update(overrides)
    return _insert(connection, Service.__table__, **values)


def make_signal_question(
    connection: Connection, service_id: uuid.UUID, **overrides: Any
) -> uuid.UUID:
    unique = uuid.uuid4().hex[:8].upper()
    values = {
        "service_id": service_id,
        "key": f"QUESTION_{unique}",
        "text": "Does the company do the thing?",
        "answer_type": SignalQuestionAnswerType.YES_NO,
        "options": None,
        "polarity": SignalQuestionPolarity.POSITIVE,
        "source_types": [DocumentSourceType.NEWS.value],
        "hint_terms": [],
        "revision": 1,
        "status": SignalQuestionStatus.ACTIVE,
    }
    values.update(overrides)
    return _insert(connection, SignalQuestion.__table__, **values)


def make_scoring_config(
    connection: Connection, service_id: uuid.UUID, **overrides: Any
) -> uuid.UUID:
    values = {
        "service_id": service_id,
        "version": 1,
        "status": ScoringConfigStatus.DRAFT,
        "settings": {},
        "change_note": None,
        "activated_at": None,
        "activated_by": None,
    }
    values.update(overrides)
    return _insert(connection, ScoringConfig.__table__, **values)


def make_account(connection: Connection, **overrides: Any) -> uuid.UUID:
    values: dict[str, Any] = {
        "domain": f"{uuid.uuid4().hex[:12]}.example.com",
        "name": "Example Corp",
        "country_code": "DE",
        "industry": None,
        "employee_count": None,
        "revenue_eur": None,
        "operational_complexity": None,
        "attribute_origin": {},
        "parent_account_id": None,
        "origin": AccountOrigin.MANUAL,
        "status": AccountStatus.ACTIVE,
        "crunchbase_id": None,
        "linkedin_url": None,
        "notes": None,
        "last_refreshed_at": None,
        "next_refresh_at": None,
    }
    values.update(overrides)
    return _insert(connection, Account.__table__, **values)


def make_pipeline_run(connection: Connection, **overrides: Any) -> uuid.UUID:
    values: dict[str, Any] = {
        "kind": PipelineRunKind.ACCOUNT_REFRESH,
        "trigger": PipelineRunTrigger.USER,
        "account_id": None,
        "service_id": None,
        "question_id": None,
        "status": PipelineRunStatus.QUEUED,
        "stage": None,
        "progress": {},
        "errors": [],
        "requested_by": None,
        "started_at": None,
        "finished_at": None,
    }
    values.update(overrides)
    return _insert(connection, PipelineRun.__table__, **values)


def make_document(connection: Connection, run_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    values = {
        "account_id": None,
        "run_id": run_id,
        "plugin_code": SourcePluginCode.GDELT,
        "source_type": DocumentSourceType.NEWS,
        "url": f"https://example.com/{uuid.uuid4().hex}",
        "canonical_url": f"https://example.com/{uuid.uuid4().hex}",
        "title": "A title",
        "language": "en",
        "published_at": None,
        "fetched_at": NOW,
        "content_hash": uuid.uuid4().hex,
        "text": "Some normalised text.",
        "duplicate_of_id": None,
        "purge_after": date.today() + timedelta(days=730),
        "purged_at": None,
    }
    values.update(overrides)
    return _insert(connection, Document.__table__, **values)


def make_chunk(connection: Connection, document_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    values = {
        "document_id": document_id,
        "ordinal": 0,
        "char_start": 0,
        "char_end": 10,
        "section": None,
        "text": "Some text",
        "embedding": None,
    }
    values.update(overrides)
    return _insert(connection, Chunk.__table__, **values)


def make_document_triage(
    connection: Connection, document_id: uuid.UUID, **overrides: Any
) -> uuid.UUID:
    values = {
        "document_id": document_id,
        "classifier": DocumentTriageClassifier.LLM,
        "about_account_p": 0.9,
        "service_relevance": {},
        "outcome": DocumentTriageOutcome.KEPT,
    }
    values.update(overrides)
    return _insert(connection, DocumentTriage.__table__, **values)


def make_classification(
    connection: Connection,
    chunk_id: uuid.UUID,
    question_id: uuid.UUID,
    run_id: uuid.UUID,
    **overrides: Any,
) -> uuid.UUID:
    values = {
        "chunk_id": chunk_id,
        "question_id": question_id,
        "question_revision": 1,
        "run_id": run_id,
        "classifier": DocumentTriageClassifier.LLM,
        "answer": {},
        "p_positive": 0.5,
        "escalated": False,
        "strength": FindingStrength.WEAK,
        "status": ClassificationStatus.POSITIVE,
        "evidence_retried": False,
    }
    values.update(overrides)
    return _insert(connection, Classification.__table__, **values)


def make_evaluation_item(
    connection: Connection,
    chunk_id: uuid.UUID,
    question_id: uuid.UUID,
    labelled_by: uuid.UUID,
    **overrides: Any,
) -> uuid.UUID:
    values = {
        "chunk_id": chunk_id,
        "question_id": question_id,
        "question_revision": 1,
        "expected_strength": FindingStrength.WEAK,
        "origin": EvaluationItemOrigin.MANUAL,
        "labelled_by": labelled_by,
        "status": EvaluationItemStatus.ACTIVE,
    }
    values.update(overrides)
    return _insert(connection, EvaluationItem.__table__, **values)


def make_market(connection: Connection, **overrides: Any) -> uuid.UUID:
    unique = uuid.uuid4().hex[:8].upper()
    values = {
        "code": f"MARKET_{unique}",
        "name": f"Market {unique}",
        "country_codes": ["DE"],
        "status": MarketStatus.ACTIVE,
    }
    values.update(overrides)
    return _insert(connection, Market.__table__, **values)


def make_source_plugin(connection: Connection, **overrides: Any) -> uuid.UUID:
    values = {
        "code": SourcePluginCode.GDELT,
        "enabled": True,
        "rate_limit_per_minute": 60,
        "daily_quota": None,
        "last_success_at": None,
        "last_error": None,
        "last_error_at": None,
    }
    values.update(overrides)
    return _insert(connection, SourcePlugin.__table__, **values)


def make_finding(
    connection: Connection,
    account_id: uuid.UUID,
    question_id: uuid.UUID,
    classification_id: uuid.UUID,
    chunk_id: uuid.UUID,
    **overrides: Any,
) -> uuid.UUID:
    values = {
        "account_id": account_id,
        "question_id": question_id,
        "question_revision": 1,
        "classification_id": classification_id,
        "chunk_id": chunk_id,
        "strength": FindingStrength.WEAK,
        "confidence": 0.5,
        "decided_by": FindingDecidedBy.CLASSIFIER,
        "option_key": None,
        "quote": "a quote",
        "quote_en": None,
        "rationale": "a rationale",
        "observed_at": NOW,
        "status": FindingStatus.ACTIVE,
    }
    values.update(overrides)
    return _insert(connection, Finding.__table__, **values)


def make_account_score(
    connection: Connection,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    scoring_config_id: uuid.UUID,
    run_id: uuid.UUID,
    **overrides: Any,
) -> uuid.UUID:
    values = {
        "account_id": account_id,
        "service_id": service_id,
        "scoring_config_id": scoring_config_id,
        "run_id": run_id,
        "as_of": NOW,
        "fit": 50,
        "intent": 50,
        "priority": 50,
        "standing": AccountScoreStanding.RANKED,
        "band": AccountScoreBand.WARM,
        "breakdown": {},
        "is_current": False,
    }
    values.update(overrides)
    return _insert(connection, AccountScore.__table__, **values)


def make_alert(
    connection: Connection, account_id: uuid.UUID, service_id: uuid.UUID, **overrides: Any
) -> uuid.UUID:
    values = {
        "account_id": account_id,
        "service_id": service_id,
        "kind": AlertKind.STRONG_SIGNAL,
        "finding_id": None,
        "score_id": None,
        "acknowledged_by": None,
        "acknowledged_at": None,
    }
    values.update(overrides)
    return _insert(connection, Alert.__table__, **values)


def make_evaluation_result(
    connection: Connection, run_id: uuid.UUID, **overrides: Any
) -> uuid.UUID:
    values = {
        "run_id": run_id,
        "classifier": DocumentTriageClassifier.LLM,
        "escalation_lower": 0.35,
        "escalation_upper": 0.65,
        "min_precision": 0.8,
        "min_items": 200,
        "escalation_rate_target": 0.15,
        "items": 0,
        "metrics": {},
        "passed": False,
    }
    values.update(overrides)
    return _insert(connection, EvaluationResult.__table__, **values)


def make_audit_event(connection: Connection, **overrides: Any) -> uuid.UUID:
    values: dict[str, Any] = {
        "occurred_at": NOW,
        "actor_id": None,
        "kind": AuditEventKind.AI_CALL,
        "action": "AI_CALL",
        "entity_type": None,
        "entity_id": None,
        "run_id": None,
        "request_id": None,
        "payload": {},
    }
    values.update(overrides)
    return _insert(connection, AuditEvent.__table__, **values)


def make_disqualifier_override(
    connection: Connection,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    created_by: uuid.UUID,
    **overrides: Any,
) -> uuid.UUID:
    values = {
        "account_id": account_id,
        "service_id": service_id,
        "rule_key": "SOME_RULE",
        "note": "A reason.",
        "created_by": created_by,
        "status": DisqualifierOverrideStatus.ACTIVE,
        "revoked_by": None,
        "revoked_at": None,
    }
    values.update(overrides)
    return _insert(connection, DisqualifierOverride.__table__, **values)
