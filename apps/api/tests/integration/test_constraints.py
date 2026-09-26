"""Integration tests of
[Constraints and indexes](/architecture/sql-store.md#constraints-and-indexes)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import Connection, insert, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from leadradar.core.enums import (
    AccountScoreBand,
    AccountScoreStanding,
    DocumentTriageClassifier,
    PipelineRunKind,
    PipelineRunStatus,
    ScoringConfigStatus,
)
from leadradar.db.models.accounts import DiscoveryCandidate
from leadradar.db.models.feedback import EvaluationResult
from leadradar.db.models.signals import AccountScore, Finding
from tests.integration import factories as f

pytestmark = pytest.mark.integration


def test_app_user_email_is_unique_regardless_of_case(sync_connection: Connection) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    f.make_app_user(sync_connection, email=email)
    with pytest.raises(IntegrityError):
        f.make_app_user(sync_connection, email=email.upper())


# --- unique constraints, one case per bullet item -------------------------------------------


def _duplicate_signal_question(connection: Connection) -> None:
    service_id = f.make_service(connection)
    f.make_signal_question(connection, service_id, key="SAME_KEY")
    f.make_signal_question(connection, service_id, key="SAME_KEY")


def _duplicate_scoring_config_version(connection: Connection) -> None:
    service_id = f.make_service(connection)
    f.make_scoring_config(connection, service_id, version=1)
    f.make_scoring_config(connection, service_id, version=1, status=ScoringConfigStatus.RETIRED)


def _duplicate_account_alias(connection: Connection) -> None:
    from leadradar.db.models.accounts import AccountAlias

    account_id = f.make_account(connection)
    connection.execute(
        insert(AccountAlias).values(account_id=account_id, alias="Acme", normalised="acme")
    )
    connection.execute(
        insert(AccountAlias).values(account_id=account_id, alias="ACME", normalised="acme")
    )


def _duplicate_account_source(connection: Connection) -> None:
    from leadradar.core.enums import AccountSourceKind, AccountSourceOrigin, AccountSourceStatus
    from leadradar.db.models.accounts import AccountSource

    account_id = f.make_account(connection)
    values = {
        "account_id": account_id,
        "kind": AccountSourceKind.WEBSITE,
        "url": "https://example.com",
        "origin": AccountSourceOrigin.MANUAL,
        "status": AccountSourceStatus.ACTIVE,
    }
    connection.execute(insert(AccountSource).values(**values))
    connection.execute(insert(AccountSource).values(**values))


def _duplicate_plugin_usage(connection: Connection) -> None:
    from datetime import date

    from leadradar.core.enums import SourcePluginCode
    from leadradar.db.models.ingestion import PluginUsage

    values = {"plugin_code": SourcePluginCode.GDELT, "day": date.today(), "requests": 1}
    connection.execute(insert(PluginUsage).values(**values))
    connection.execute(insert(PluginUsage).values(**values))


def _duplicate_chunk_ordinal(connection: Connection) -> None:
    run_id = f.make_pipeline_run(connection)
    document_id = f.make_document(connection, run_id)
    f.make_chunk(connection, document_id, ordinal=0)
    f.make_chunk(connection, document_id, ordinal=0)


def _duplicate_classification(connection: Connection) -> None:
    run_id = f.make_pipeline_run(connection)
    document_id = f.make_document(connection, run_id)
    chunk_id = f.make_chunk(connection, document_id)
    service_id = f.make_service(connection)
    question_id = f.make_signal_question(connection, service_id)
    f.make_classification(connection, chunk_id, question_id, run_id)
    f.make_classification(connection, chunk_id, question_id, run_id)


UNIQUE_CONSTRAINT_CASES: dict[str, Callable[[Connection], None]] = {
    "signal_question(service_id, key)": _duplicate_signal_question,
    "scoring_config(service_id, version)": _duplicate_scoring_config_version,
    "account_alias(account_id, normalised)": _duplicate_account_alias,
    "account_source(account_id, url)": _duplicate_account_source,
    "plugin_usage(plugin_code, day)": _duplicate_plugin_usage,
    "chunk(document_id, ordinal)": _duplicate_chunk_ordinal,
    "classification(chunk_id, question_id, question_revision)": _duplicate_classification,
}


@pytest.mark.parametrize("case", UNIQUE_CONSTRAINT_CASES, ids=list(UNIQUE_CONSTRAINT_CASES))
def test_unique_constraint_refuses_a_duplicate(case: str, sync_connection: Connection) -> None:
    with pytest.raises(IntegrityError):
        UNIQUE_CONSTRAINT_CASES[case](sync_connection)


def test_two_documents_with_no_account_and_the_same_content_hash_conflict(
    sync_connection: Connection,
) -> None:
    run_id = f.make_pipeline_run(sync_connection)
    same_hash = uuid.uuid4().hex
    f.make_document(sync_connection, run_id, account_id=None, content_hash=same_hash)
    with pytest.raises(IntegrityError):
        f.make_document(sync_connection, run_id, account_id=None, content_hash=same_hash)


# --- partial unique indexes -------------------------------------------------------------------


def test_a_second_draft_and_a_second_active_scoring_config_are_refused_but_not_retired(
    sync_connection: Connection,
) -> None:
    service_id = f.make_service(sync_connection)
    f.make_scoring_config(sync_connection, service_id, version=1, status=ScoringConfigStatus.DRAFT)
    with pytest.raises(IntegrityError):
        f.make_scoring_config(
            sync_connection, service_id, version=2, status=ScoringConfigStatus.DRAFT
        )


def test_a_second_active_scoring_config_is_refused(sync_connection: Connection) -> None:
    service_id = f.make_service(sync_connection)
    f.make_scoring_config(sync_connection, service_id, version=1, status=ScoringConfigStatus.ACTIVE)
    with pytest.raises(IntegrityError):
        f.make_scoring_config(
            sync_connection, service_id, version=2, status=ScoringConfigStatus.ACTIVE
        )


def test_a_second_retired_scoring_config_is_accepted(sync_connection: Connection) -> None:
    service_id = f.make_service(sync_connection)
    f.make_scoring_config(
        sync_connection, service_id, version=1, status=ScoringConfigStatus.RETIRED
    )
    f.make_scoring_config(
        sync_connection, service_id, version=2, status=ScoringConfigStatus.RETIRED
    )


def test_a_second_current_account_score_per_account_and_service_is_refused(
    sync_connection: Connection,
) -> None:
    account_id = f.make_account(sync_connection)
    service_id = f.make_service(sync_connection)
    scoring_config_id = f.make_scoring_config(sync_connection, service_id)
    run_id = f.make_pipeline_run(sync_connection)

    def score(is_current: bool) -> uuid.UUID:
        return sync_connection.execute(
            insert(AccountScore)
            .values(
                account_id=account_id,
                service_id=service_id,
                scoring_config_id=scoring_config_id,
                run_id=run_id,
                as_of=datetime.now(tz=UTC),
                fit=50,
                intent=50,
                priority=50,
                standing=AccountScoreStanding.RANKED,
                band=AccountScoreBand.WARM,
                breakdown={},
                is_current=is_current,
            )
            .returning(AccountScore.id)
        ).scalar_one()

    score(True)
    with pytest.raises(IntegrityError):
        score(True)


def test_a_second_queued_or_running_account_refresh_is_refused_then_accepted_after_success(
    sync_connection: Connection,
) -> None:
    account_id = f.make_account(sync_connection)
    first_run_id = f.make_pipeline_run(
        sync_connection,
        kind=PipelineRunKind.ACCOUNT_REFRESH,
        account_id=account_id,
        status=PipelineRunStatus.QUEUED,
    )
    with pytest.raises(IntegrityError), sync_connection.begin_nested():
        f.make_pipeline_run(
            sync_connection,
            kind=PipelineRunKind.ACCOUNT_REFRESH,
            account_id=account_id,
            status=PipelineRunStatus.RUNNING,
        )

    # a new one after the first SUCCEEDED is accepted
    sync_connection.execute(
        text("UPDATE pipeline_run SET status = 'SUCCEEDED' WHERE id = :id"),
        {"id": first_run_id},
    )
    f.make_pipeline_run(
        sync_connection,
        kind=PipelineRunKind.ACCOUNT_REFRESH,
        account_id=account_id,
        status=PipelineRunStatus.QUEUED,
    )


def test_a_second_queued_or_running_discovery_is_refused_a_different_service_is_accepted(
    sync_connection: Connection,
) -> None:
    service_id = f.make_service(sync_connection)
    other_service_id = f.make_service(sync_connection)
    first_run_id = f.make_pipeline_run(
        sync_connection,
        kind=PipelineRunKind.DISCOVERY,
        service_id=service_id,
        status=PipelineRunStatus.QUEUED,
    )
    with pytest.raises(IntegrityError), sync_connection.begin_nested():
        f.make_pipeline_run(
            sync_connection,
            kind=PipelineRunKind.DISCOVERY,
            service_id=service_id,
            status=PipelineRunStatus.RUNNING,
        )
    # a different service is accepted
    f.make_pipeline_run(
        sync_connection,
        kind=PipelineRunKind.DISCOVERY,
        service_id=other_service_id,
        status=PipelineRunStatus.QUEUED,
    )
    # a new one after the first SUCCEEDED is accepted
    sync_connection.execute(
        text("UPDATE pipeline_run SET status = 'SUCCEEDED' WHERE id = :id"),
        {"id": first_run_id},
    )
    f.make_pipeline_run(
        sync_connection,
        kind=PipelineRunKind.DISCOVERY,
        service_id=service_id,
        status=PipelineRunStatus.QUEUED,
    )


def test_a_second_active_disqualifier_override_per_key_is_refused(
    sync_connection: Connection,
) -> None:
    account_id = f.make_account(sync_connection)
    service_id = f.make_service(sync_connection)
    user_id = f.make_app_user(sync_connection)
    f.make_disqualifier_override(sync_connection, account_id, service_id, user_id)
    with pytest.raises(IntegrityError):
        f.make_disqualifier_override(sync_connection, account_id, service_id, user_id)


def test_a_second_active_evaluation_item_per_pair_is_refused(sync_connection: Connection) -> None:
    run_id = f.make_pipeline_run(sync_connection)
    document_id = f.make_document(sync_connection, run_id)
    chunk_id = f.make_chunk(sync_connection, document_id)
    service_id = f.make_service(sync_connection)
    question_id = f.make_signal_question(sync_connection, service_id)
    user_id = f.make_app_user(sync_connection)
    f.make_evaluation_item(sync_connection, chunk_id, question_id, user_id)
    with pytest.raises(IntegrityError):
        f.make_evaluation_item(sync_connection, chunk_id, question_id, user_id)


# --- range checks: 0-1 and 0-100, parametrised over the eleven columns ------------------------


def _discovery_candidate_row(connection: Connection, value: float) -> None:
    service_id = f.make_service(connection)
    run_id = f.make_pipeline_run(connection, kind=PipelineRunKind.DISCOVERY, service_id=service_id)
    connection.execute(
        insert(DiscoveryCandidate).values(
            service_id=service_id,
            run_id=run_id,
            name="Acme",
            normalised_name="acme",
            domain=None,
            country_code=None,
            industry=None,
            employee_count=None,
            origin="NEWS_MENTION",
            document_id=None,
            quote=None,
            fit_estimate=value,
            status="PENDING",
            decided_by=None,
            decided_at=None,
            reject_reason=None,
            account_id=None,
        )
    )


def _document_triage_row(connection: Connection, value: float) -> None:
    run_id = f.make_pipeline_run(connection)
    document_id = f.make_document(connection, run_id)
    f.make_document_triage(connection, document_id, about_account_p=value)


def _classification_row(connection: Connection, value: float) -> None:
    run_id = f.make_pipeline_run(connection)
    document_id = f.make_document(connection, run_id)
    chunk_id = f.make_chunk(connection, document_id)
    service_id = f.make_service(connection)
    question_id = f.make_signal_question(connection, service_id)
    f.make_classification(connection, chunk_id, question_id, run_id, p_positive=value)


def _finding_row(connection: Connection, value: float) -> None:
    run_id = f.make_pipeline_run(connection)
    document_id = f.make_document(connection, run_id)
    chunk_id = f.make_chunk(connection, document_id)
    service_id = f.make_service(connection)
    question_id = f.make_signal_question(connection, service_id)
    classification_id = f.make_classification(connection, chunk_id, question_id, run_id)
    account_id = f.make_account(connection)
    connection.execute(
        insert(Finding).values(
            account_id=account_id,
            question_id=question_id,
            question_revision=1,
            classification_id=classification_id,
            chunk_id=chunk_id,
            strength="WEAK",
            confidence=value,
            decided_by="CLASSIFIER",
            option_key=None,
            quote="a quote",
            quote_en=None,
            rationale="a rationale",
            observed_at=datetime.now(tz=UTC),
            status="ACTIVE",
        )
    )


def _account_score_row(column: str) -> Callable[[Connection, float], None]:
    def build(connection: Connection, value: float) -> None:
        account_id = f.make_account(connection)
        service_id = f.make_service(connection)
        scoring_config_id = f.make_scoring_config(connection, service_id)
        run_id = f.make_pipeline_run(connection)
        base = {"fit": 50, "intent": 50, "priority": 50}
        base[column] = value
        connection.execute(
            insert(AccountScore).values(
                account_id=account_id,
                service_id=service_id,
                scoring_config_id=scoring_config_id,
                run_id=run_id,
                as_of=datetime.now(tz=UTC),
                standing=AccountScoreStanding.RANKED,
                band=AccountScoreBand.WARM,
                breakdown={},
                is_current=False,
                **base,
            )
        )

    return build


def _evaluation_result_row(column: str) -> Callable[[Connection, float], None]:
    def build(connection: Connection, value: float) -> None:
        run_id = f.make_pipeline_run(connection)
        base = {
            "escalation_lower": 0.35,
            "escalation_upper": 0.65,
            "min_precision": 0.8,
            "escalation_rate_target": 0.15,
        }
        base[column] = value
        connection.execute(
            insert(EvaluationResult).values(
                run_id=run_id,
                classifier=DocumentTriageClassifier.LLM,
                min_items=200,
                items=0,
                metrics={},
                passed=False,
                **base,
            )
        )

    return build


RANGE_CHECK_CASES: dict[str, tuple[float, float, Callable[[Connection, float], None]]] = {
    "discovery_candidate.fit_estimate": (0, 100, _discovery_candidate_row),
    "document_triage.about_account_p": (0, 1, _document_triage_row),
    "classification.p_positive": (0, 1, _classification_row),
    "finding.confidence": (0, 1, _finding_row),
    "account_score.fit": (0, 100, _account_score_row("fit")),
    "account_score.intent": (0, 100, _account_score_row("intent")),
    "account_score.priority": (0, 100, _account_score_row("priority")),
    "evaluation_result.escalation_lower": (0, 1, _evaluation_result_row("escalation_lower")),
    "evaluation_result.escalation_upper": (0, 1, _evaluation_result_row("escalation_upper")),
    "evaluation_result.min_precision": (0, 1, _evaluation_result_row("min_precision")),
    "evaluation_result.escalation_rate_target": (
        0,
        1,
        _evaluation_result_row("escalation_rate_target"),
    ),
}


def _step(upper: float) -> float:
    # The 0-100 columns are integers; the 0-1 columns are numeric. A fractional step on an
    # integer column would be rounded back into range by the driver instead of refused.
    return 1 if upper == 100 else 0.001


@pytest.mark.parametrize("case", RANGE_CHECK_CASES, ids=list(RANGE_CHECK_CASES))
def test_range_check_refuses_just_below_the_lower_bound(
    case: str, sync_connection: Connection
) -> None:
    lower, upper, build = RANGE_CHECK_CASES[case]
    with pytest.raises(IntegrityError):
        build(sync_connection, lower - _step(upper))


@pytest.mark.parametrize("case", RANGE_CHECK_CASES, ids=list(RANGE_CHECK_CASES))
def test_range_check_refuses_just_above_the_upper_bound(
    case: str, sync_connection: Connection
) -> None:
    lower, upper, build = RANGE_CHECK_CASES[case]
    with pytest.raises(IntegrityError):
        build(sync_connection, upper + _step(upper))


@pytest.mark.parametrize("case", RANGE_CHECK_CASES, ids=list(RANGE_CHECK_CASES))
def test_range_check_accepts_both_bounds(case: str, sync_connection: Connection) -> None:
    lower, upper, build = RANGE_CHECK_CASES[case]
    build(sync_connection, lower)
    build(sync_connection, upper)


# --- other check constraints -------------------------------------------------------------------


def test_a_band_with_a_standing_other_than_ranked_is_refused(sync_connection: Connection) -> None:
    account_id = f.make_account(sync_connection)
    service_id = f.make_service(sync_connection)
    scoring_config_id = f.make_scoring_config(sync_connection, service_id)
    run_id = f.make_pipeline_run(sync_connection)
    with pytest.raises(IntegrityError):
        sync_connection.execute(
            insert(AccountScore).values(
                account_id=account_id,
                service_id=service_id,
                scoring_config_id=scoring_config_id,
                run_id=run_id,
                as_of=datetime.now(tz=UTC),
                fit=10,
                intent=10,
                priority=10,
                standing=AccountScoreStanding.BELOW_FIT,
                band=AccountScoreBand.WARM,
                breakdown={},
                is_current=False,
            )
        )


def test_options_is_refused_on_a_non_choice_question_and_required_on_a_choice_one(
    sync_connection: Connection,
) -> None:
    service_id = f.make_service(sync_connection)
    with pytest.raises(IntegrityError):
        f.make_signal_question(
            sync_connection,
            service_id,
            answer_type="YES_NO",
            options=[{"key": "A", "label": "A", "strength": "WEAK"}],
        )


def test_options_required_for_a_choice_question(sync_connection: Connection) -> None:
    service_id = f.make_service(sync_connection)
    with pytest.raises(IntegrityError):
        f.make_signal_question(sync_connection, service_id, answer_type="CHOICE", options=None)


def test_an_unknown_enum_value_is_refused(sync_connection: Connection) -> None:
    with pytest.raises(DBAPIError):
        sync_connection.execute(
            text(
                "INSERT INTO app_user (email, display_name, role, status, password_hash, "
                "failed_logins) VALUES (:email, 'x', 'NOT_A_ROLE', 'ACTIVE', 'h', 0)"
            ),
            {"email": f"{uuid.uuid4()}@example.com"},
        )


# --- foreign keys -------------------------------------------------------------------------------


def test_deleting_a_referenced_account_is_refused(sync_connection: Connection) -> None:
    from leadradar.db.models.accounts import AccountAlias

    account_id = f.make_account(sync_connection)
    sync_connection.execute(
        insert(AccountAlias).values(account_id=account_id, alias="Acme", normalised="acme")
    )
    with pytest.raises(IntegrityError):
        sync_connection.execute(text("DELETE FROM account WHERE id = :id"), {"id": account_id})


def test_deleting_a_contact_sets_a_drafts_contact_id_to_null(sync_connection: Connection) -> None:
    from datetime import date, timedelta

    from leadradar.core.enums import (
        ContactPersona,
        ContactPersonaOrigin,
        OutreachDraftChannel,
        OutreachDraftStatus,
    )
    from leadradar.db.models.accounts import Contact
    from leadradar.db.models.outreach import OutreachDraft

    account_id = f.make_account(sync_connection)
    service_id = f.make_service(sync_connection)
    user_id = f.make_app_user(sync_connection)
    contact_id = sync_connection.execute(
        insert(Contact)
        .values(
            account_id=account_id,
            full_name="Jane Doe",
            job_title="CIO",
            persona=ContactPersona.CIO,
            persona_origin=ContactPersonaOrigin.MANUAL,
            source_url="https://example.com/team",
            retain_until=date.today() + timedelta(days=730),
        )
        .returning(Contact.id)
    ).scalar_one()
    draft_id = sync_connection.execute(
        insert(OutreachDraft)
        .values(
            account_id=account_id,
            service_id=service_id,
            contact_id=contact_id,
            channel=OutreachDraftChannel.EMAIL,
            subject="Hello",
            body="Body",
            finding_ids=[],
            edited=False,
            status=OutreachDraftStatus.DRAFT,
            created_by=user_id,
        )
        .returning(OutreachDraft.id)
    ).scalar_one()

    sync_connection.execute(text("DELETE FROM contact WHERE id = :id"), {"id": contact_id})

    remaining_contact_id = sync_connection.execute(
        select(OutreachDraft.contact_id).where(OutreachDraft.id == draft_id)
    ).scalar_one()
    assert remaining_contact_id is None


# --- generated column and indexes ---------------------------------------------------------------


def test_chunk_lexemes_is_the_simple_tsvector_of_text_and_null_when_text_is_null(
    sync_connection: Connection,
) -> None:
    from leadradar.db.models.ingestion import Chunk

    run_id = f.make_pipeline_run(sync_connection)
    document_id = f.make_document(sync_connection, run_id)
    chunk_id = f.make_chunk(sync_connection, document_id, text="hello world")

    lexemes = sync_connection.execute(
        select(Chunk.lexemes).where(Chunk.id == chunk_id)
    ).scalar_one()
    assert lexemes == "'hello':1 'world':2"

    sync_connection.execute(text("UPDATE chunk SET text = NULL WHERE id = :id"), {"id": chunk_id})
    lexemes_after = sync_connection.execute(
        select(Chunk.lexemes).where(Chunk.id == chunk_id)
    ).scalar_one()
    assert lexemes_after is None


def test_the_special_indexes_exist(database_url: str) -> None:
    from sqlalchemy import create_engine

    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://"))
    try:
        with engine.connect() as connection:
            names = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT indexname FROM pg_indexes WHERE indexname IN "
                        "('ix_chunk_embedding_hnsw', 'ix_chunk_lexemes_gin', 'ix_job_claiming', "
                        "'ix_audit_event_kind_occurred_at', 'ix_audit_event_run_id', "
                        "'ix_finding_account_status', 'ix_account_score_prospects')"
                    )
                )
            }
        assert names == {
            "ix_chunk_embedding_hnsw",
            "ix_chunk_lexemes_gin",
            "ix_job_claiming",
            "ix_audit_event_kind_occurred_at",
            "ix_audit_event_run_id",
            "ix_finding_account_status",
            "ix_account_score_prospects",
        }
    finally:
        engine.dispose()
