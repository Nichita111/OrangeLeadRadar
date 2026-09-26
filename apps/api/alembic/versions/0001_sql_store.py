"""The whole SQL store ([sql-store.md](/architecture/sql-store.md)), as one migration.

This is the first migration: it creates every table, enum, constraint and index of the store
in one pass, and provides no `downgrade()`: a schema change goes forward, in a new migration.
Enum values are spelled literally here rather than imported from `leadradar.core.enums`,
because a migration is a frozen snapshot that must not change when the code does; the
integration test "models match the migrated schema" catches any drift between the two.

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

# Read from the `ApiSettings` the entry point passed to `alembic/env.py`; frozen into the
# database at the dimension in force when this migration runs (see Risks, design).
EMBEDDING_DIM: int = context.config.attributes["embedding_dim"]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "app_user",
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Enum("SALES", "ADMIN", name="app_user_role"), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "DISABLED", name="app_user_status"), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("failed_logins", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("email", name=op.f("uq_app_user_email")),
    )
    op.create_table(
        "industry",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "INACTIVE", name="industry_status"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_industry")),
        sa.UniqueConstraint("code", name=op.f("uq_industry_code")),
        sa.UniqueConstraint("label", name=op.f("uq_industry_label")),
    )
    op.create_table(
        "market",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("country_codes", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "INACTIVE", name="market_status"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market")),
        sa.UniqueConstraint("code", name=op.f("uq_market_code")),
        sa.UniqueConstraint("name", name=op.f("uq_market_name")),
    )
    op.create_table(
        "plugin_usage",
        sa.Column(
            "plugin_code",
            sa.Enum(
                "GDELT",
                "RSS",
                "WEBSITE",
                "CAREERS",
                "CRUNCHBASE",
                "NEWSAPI",
                "SERPAPI",
                name="source_plugin_code",
            ),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plugin_usage")),
        sa.UniqueConstraint("plugin_code", "day", name=op.f("uq_plugin_usage_plugin_code_day")),
    )
    op.create_table(
        "service",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("value_proposition", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "INACTIVE", name="service_status"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service")),
        sa.UniqueConstraint("code", name=op.f("uq_service_code")),
        sa.UniqueConstraint("name", name=op.f("uq_service_name")),
    )
    op.create_table(
        "source_plugin",
        sa.Column(
            "code",
            sa.Enum(
                "GDELT",
                "RSS",
                "WEBSITE",
                "CAREERS",
                "CRUNCHBASE",
                "NEWSAPI",
                "SERPAPI",
                name="source_plugin_code",
            ),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False),
        sa.Column("daily_quota", sa.Integer(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_plugin")),
        sa.UniqueConstraint("code", name=op.f("uq_source_plugin_code")),
    )
    op.create_table(
        "account",
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("country_code", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("revenue_eur", sa.BigInteger(), nullable=True),
        sa.Column(
            "operational_complexity",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="account_operational_complexity"),
            nullable=True,
        ),
        sa.Column("attribute_origin", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("parent_account_id", sa.UUID(), nullable=True),
        sa.Column(
            "origin",
            sa.Enum("IMPORTED", "MANUAL", "DISCOVERED", name="account_origin"),
            nullable=False,
        ),
        sa.Column("status", sa.Enum("ACTIVE", "INACTIVE", name="account_status"), nullable=False),
        sa.Column("crunchbase_id", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["industry"],
            ["industry.code"],
            name=op.f("fk_account_industry_industry"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_account_id"],
            ["account.id"],
            name=op.f("fk_account_parent_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
        sa.UniqueConstraint("domain", name=op.f("uq_account_domain")),
    )
    op.create_table(
        "auth_session",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_auth_session_user_id_app_user"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_session")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_session_token_hash")),
    )
    op.create_table(
        "scoring_config",
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "ACTIVE", "RETIRED", name="scoring_config_status"),
            nullable=False,
        ),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["activated_by"],
            ["app_user.id"],
            name=op.f("fk_scoring_config_activated_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_scoring_config_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scoring_config")),
        sa.UniqueConstraint(
            "service_id", "version", name=op.f("uq_scoring_config_service_id_version")
        ),
    )
    op.create_index(
        "uq_scoring_config_active_per_service",
        "scoring_config",
        ["service_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "uq_scoring_config_draft_per_service",
        "scoring_config",
        ["service_id"],
        unique=True,
        postgresql_where=sa.text("status = 'DRAFT'"),
    )
    op.create_table(
        "signal_question",
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "answer_type",
            sa.Enum("YES_NO", "SCALE", "CHOICE", name="signal_question_answer_type"),
            nullable=False,
        ),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "polarity",
            sa.Enum("POSITIVE", "NEGATIVE", name="signal_question_polarity"),
            nullable=False,
        ),
        sa.Column("source_types", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("hint_terms", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.Enum("ACTIVE", "INACTIVE", name="signal_question_status"), nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(options IS NOT NULL) = (answer_type = 'CHOICE')",
            name=op.f("ck_signal_question_options_only_for_choice"),
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_signal_question_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signal_question")),
        sa.UniqueConstraint("service_id", "key", name=op.f("uq_signal_question_service_id_key")),
    )
    op.create_table(
        "account_alias",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("normalised", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_account_alias_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_alias")),
        sa.UniqueConstraint(
            "account_id", "normalised", name=op.f("uq_account_alias_account_id_normalised")
        ),
    )
    op.create_table(
        "account_source",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "WEBSITE",
                "NEWSROOM",
                "INVESTOR_RELATIONS",
                "CAREERS",
                "RSS_FEED",
                name="account_source_kind",
            ),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "origin", sa.Enum("MANUAL", "DETECTED", name="account_source_origin"), nullable=False
        ),
        sa.Column(
            "status", sa.Enum("ACTIVE", "INACTIVE", name="account_source_status"), nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_account_source_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_source")),
        sa.UniqueConstraint("account_id", "url", name=op.f("uq_account_source_account_id_url")),
    )
    op.create_table(
        "contact",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("job_title", sa.Text(), nullable=False),
        sa.Column(
            "persona",
            sa.Enum(
                "CIO",
                "CTO",
                "COO",
                "CFO",
                "CISO",
                "HEAD_OF_DIGITAL_TRANSFORMATION",
                "HEAD_OF_AUTOMATION",
                "HEAD_OF_PROCESS_EXCELLENCE",
                "HEAD_OF_SHARED_SERVICES",
                "OTHER",
                name="contact_persona",
            ),
            nullable=False,
        ),
        sa.Column(
            "persona_origin",
            sa.Enum("MANUAL", "CLASSIFIER", name="contact_persona_origin"),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("retain_until", sa.Date(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_contact_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact")),
    )
    op.create_table(
        "disqualifier_override",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("rule_key", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "REVOKED", name="disqualifier_override_status"),
            nullable=False,
        ),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_disqualifier_override_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["app_user.id"],
            name=op.f("fk_disqualifier_override_created_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"],
            ["app_user.id"],
            name=op.f("fk_disqualifier_override_revoked_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_disqualifier_override_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_disqualifier_override")),
    )
    op.create_index(
        "uq_disqualifier_override_active",
        "disqualifier_override",
        ["account_id", "service_id", "rule_key"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "pipeline_run",
        sa.Column(
            "kind",
            sa.Enum(
                "ACCOUNT_REFRESH",
                "RECLASSIFY",
                "RESCORE",
                "DISCOVERY",
                "EVALUATION",
                name="pipeline_run_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "trigger",
            sa.Enum(
                "SCHEDULE",
                "USER",
                "QUESTION_CHANGE",
                "SCORING_ACTIVATION",
                "ACCOUNT_CHANGE",
                "FEEDBACK",
                "OVERRIDE",
                name="pipeline_run_trigger",
            ),
            nullable=False,
        ),
        sa.Column("account_id", sa.UUID(), nullable=True),
        sa.Column("service_id", sa.UUID(), nullable=True),
        sa.Column("question_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "RUNNING",
                "SUCCEEDED",
                "PARTIAL",
                "FAILED",
                "CANCELLED",
                name="pipeline_run_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "stage",
            sa.Enum(
                "FETCH",
                "PROCESS",
                "TRIAGE",
                "CLASSIFY",
                "EVIDENCE",
                "SCORE",
                name="pipeline_run_stage",
            ),
            nullable=True,
        ),
        sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_pipeline_run_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["signal_question.id"],
            name=op.f("fk_pipeline_run_question_id_signal_question"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["app_user.id"],
            name=op.f("fk_pipeline_run_requested_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_pipeline_run_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_run")),
    )
    op.create_index(
        "uq_pipeline_run_account_refresh_active",
        "pipeline_run",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'ACCOUNT_REFRESH' AND status IN ('QUEUED', 'RUNNING')"),
    )
    op.create_index(
        "uq_pipeline_run_discovery_active",
        "pipeline_run",
        ["service_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'DISCOVERY' AND status IN ('QUEUED', 'RUNNING')"),
    )
    op.create_table(
        "account_score",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("scoring_config_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fit", sa.Integer(), nullable=False),
        sa.Column("intent", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "standing",
            sa.Enum(
                "RANKED", "BELOW_FIT", "DISQUALIFIED", "CUSTOMER", name="account_score_standing"
            ),
            nullable=False,
        ),
        sa.Column("band", sa.Enum("HOT", "WARM", "COLD", name="account_score_band"), nullable=True),
        sa.Column("breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(band IS NULL) OR (standing = 'RANKED')",
            name=op.f("ck_account_score_band_only_when_ranked"),
        ),
        sa.CheckConstraint("fit BETWEEN 0 AND 100", name=op.f("ck_account_score_fit_range")),
        sa.CheckConstraint("intent BETWEEN 0 AND 100", name=op.f("ck_account_score_intent_range")),
        sa.CheckConstraint(
            "priority BETWEEN 0 AND 100", name=op.f("ck_account_score_priority_range")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_account_score_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_account_score_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["scoring_config_id"],
            ["scoring_config.id"],
            name=op.f("fk_account_score_scoring_config_id_scoring_config"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_account_score_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_score")),
    )
    op.create_index(
        "ix_account_score_prospects",
        "account_score",
        ["service_id", "is_current", "standing", "priority"],
        unique=False,
    )
    op.create_index(
        "uq_account_score_current",
        "account_score",
        ["account_id", "service_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_table(
        "audit_event",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "AUTH",
                "USER",
                "CONFIG",
                "ACCOUNT",
                "CONTACT",
                "RUN",
                "OVERRIDE",
                "FEEDBACK",
                "OUTREACH",
                "CRM",
                "AI_CALL",
                name="audit_event_kind",
            ),
            nullable=False,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["app_user.id"],
            name=op.f("fk_audit_event_actor_id_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_audit_event_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_event")),
    )
    op.create_index(
        "ix_audit_event_kind_occurred_at", "audit_event", ["kind", "occurred_at"], unique=False
    )
    op.create_index("ix_audit_event_run_id", "audit_event", ["run_id"], unique=False)
    op.create_table(
        "document",
        sa.Column("account_id", sa.UUID(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column(
            "plugin_code",
            sa.Enum(
                "GDELT",
                "RSS",
                "WEBSITE",
                "CAREERS",
                "CRUNCHBASE",
                "NEWSAPI",
                "SERPAPI",
                name="source_plugin_code",
            ),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.Enum(
                "NEWS",
                "COMPANY_PUBLICATION",
                "JOB_POSTING",
                "COMPANY_PROFILE",
                name="document_source_type",
            ),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("duplicate_of_id", sa.UUID(), nullable=True),
        sa.Column("purge_after", sa.Date(), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_document_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"],
            ["document.id"],
            name=op.f("fk_document_duplicate_of_id_document"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_document_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document")),
        sa.UniqueConstraint(
            "account_id",
            "content_hash",
            name=op.f("uq_document_account_id_content_hash"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_table(
        "evaluation_result",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column(
            "classifier", sa.Enum("JEV", "LLM", name="document_triage_classifier"), nullable=False
        ),
        sa.Column("escalation_lower", sa.Numeric(), nullable=False),
        sa.Column("escalation_upper", sa.Numeric(), nullable=False),
        sa.Column("min_precision", sa.Numeric(), nullable=False),
        sa.Column("min_items", sa.Integer(), nullable=False),
        sa.Column("escalation_rate_target", sa.Numeric(), nullable=False),
        sa.Column("items", sa.Integer(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "escalation_lower BETWEEN 0 AND 1",
            name=op.f("ck_evaluation_result_escalation_lower_range"),
        ),
        sa.CheckConstraint(
            "escalation_rate_target BETWEEN 0 AND 1",
            name=op.f("ck_evaluation_result_escalation_rate_target_range"),
        ),
        sa.CheckConstraint(
            "escalation_upper BETWEEN 0 AND 1",
            name=op.f("ck_evaluation_result_escalation_upper_range"),
        ),
        sa.CheckConstraint(
            "min_precision BETWEEN 0 AND 1", name=op.f("ck_evaluation_result_min_precision_range")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_evaluation_result_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_result")),
        sa.UniqueConstraint("run_id", name=op.f("uq_evaluation_result_run_id")),
    )
    op.create_table(
        "job",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column(
            "step",
            sa.Enum("FETCH", "PROCESS", "SIGNAL", "SCORE", "DISCOVER", "EVALUATE", name="job_step"),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum("READY", "RUNNING", "DONE", "FAILED", "CANCELLED", name="job_status"),
            nullable=False,
        ),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_job_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job")),
    )
    op.create_index("ix_job_claiming", "job", ["status", "priority", "not_before"], unique=False)
    op.create_table(
        "outreach_draft",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum("EMAIL", "LINKEDIN_INMAIL", name="outreach_draft_channel"),
            nullable=False,
        ),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("finding_ids", sa.ARRAY(sa.UUID()), nullable=False),
        sa.Column("edited", sa.Boolean(), nullable=False),
        sa.Column(
            "status", sa.Enum("DRAFT", "EXPORTED", name="outreach_draft_status"), nullable=False
        ),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_outreach_draft_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contact.id"],
            name=op.f("fk_outreach_draft_contact_id_contact"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["app_user.id"],
            name=op.f("fk_outreach_draft_created_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_outreach_draft_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outreach_draft")),
    )
    op.create_table(
        "chunk",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "lexemes",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', text)", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_chunk_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunk")),
        sa.UniqueConstraint("document_id", "ordinal", name=op.f("uq_chunk_document_id_ordinal")),
    )
    op.create_index(
        "ix_chunk_embedding_hnsw",
        "chunk",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_chunk_lexemes_gin", "chunk", ["lexemes"], unique=False, postgresql_using="gin"
    )
    op.create_table(
        "crm_sync",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("score_id", sa.UUID(), nullable=False),
        sa.Column("target", sa.Enum("HUBSPOT", name="crm_sync_target"), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("SUCCEEDED", "FAILED", name="crm_sync_status"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_crm_sync_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["app_user.id"],
            name=op.f("fk_crm_sync_requested_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["score_id"],
            ["account_score.id"],
            name=op.f("fk_crm_sync_score_id_account_score"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_crm_sync_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_sync")),
    )
    op.create_table(
        "discovery_candidate",
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalised_name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("country_code", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column(
            "origin",
            sa.Enum("CRUNCHBASE_SEARCH", "NEWS_MENTION", name="discovery_candidate_origin"),
            nullable=False,
        ),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("fit_estimate", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACCEPTED", "REJECTED", name="discovery_candidate_status"),
            nullable=False,
        ),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("account_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fit_estimate BETWEEN 0 AND 100", name=op.f("ck_discovery_candidate_fit_estimate_range")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_discovery_candidate_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["app_user.id"],
            name=op.f("fk_discovery_candidate_decided_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_discovery_candidate_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["industry"],
            ["industry.code"],
            name=op.f("fk_discovery_candidate_industry_industry"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_discovery_candidate_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_discovery_candidate_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discovery_candidate")),
    )
    op.create_table(
        "document_triage",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column(
            "classifier", sa.Enum("JEV", "LLM", name="document_triage_classifier"), nullable=False
        ),
        sa.Column("about_account_p", sa.Numeric(), nullable=True),
        sa.Column("service_relevance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum("KEPT", "NOT_ABOUT_ACCOUNT", "IRRELEVANT", name="document_triage_outcome"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "about_account_p IS NULL OR about_account_p BETWEEN 0 AND 1",
            name=op.f("ck_document_triage_about_account_p_range"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_document_triage_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_triage")),
        sa.UniqueConstraint("document_id", name=op.f("uq_document_triage_document_id")),
    )
    op.create_table(
        "lead_feedback",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("score_id", sa.UUID(), nullable=False),
        sa.Column(
            "verdict",
            sa.Enum("RELEVANT", "NOT_RELEVANT", "ALREADY_CUSTOMER", name="lead_feedback_verdict"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_lead_feedback_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["score_id"],
            ["account_score.id"],
            name=op.f("fk_lead_feedback_score_id_account_score"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_lead_feedback_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_lead_feedback_user_id_app_user"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_feedback")),
    )
    op.create_table(
        "classification",
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("question_revision", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column(
            "classifier", sa.Enum("JEV", "LLM", name="document_triage_classifier"), nullable=False
        ),
        sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("p_positive", sa.Numeric(), nullable=False),
        sa.Column("escalated", sa.Boolean(), nullable=False),
        sa.Column(
            "strength",
            sa.Enum("NONE", "WEAK", "MEDIUM", "STRONG", name="finding_strength"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "NEGATIVE",
                "POSITIVE",
                "PENDING_LLM",
                "EVIDENCE_FAILED",
                name="classification_status",
            ),
            nullable=False,
        ),
        sa.Column("evidence_retried", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "p_positive BETWEEN 0 AND 1", name=op.f("ck_classification_p_positive_range")
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["chunk.id"],
            name=op.f("fk_classification_chunk_id_chunk"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["signal_question.id"],
            name=op.f("fk_classification_question_id_signal_question"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_classification_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classification")),
        sa.UniqueConstraint(
            "chunk_id",
            "question_id",
            "question_revision",
            name=op.f("uq_classification_chunk_id_question_id_question_revision"),
        ),
    )
    op.create_table(
        "evaluation_item",
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("question_revision", sa.Integer(), nullable=False),
        sa.Column(
            "expected_strength",
            sa.Enum("NONE", "WEAK", "MEDIUM", "STRONG", name="finding_strength"),
            nullable=False,
        ),
        sa.Column(
            "origin",
            sa.Enum("MANUAL", "FINDING_FEEDBACK", name="evaluation_item_origin"),
            nullable=False,
        ),
        sa.Column("labelled_by", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.Enum("ACTIVE", "STALE", name="evaluation_item_status"), nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["chunk.id"],
            name=op.f("fk_evaluation_item_chunk_id_chunk"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["labelled_by"],
            ["app_user.id"],
            name=op.f("fk_evaluation_item_labelled_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["signal_question.id"],
            name=op.f("fk_evaluation_item_question_id_signal_question"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_item")),
    )
    op.create_index(
        "uq_evaluation_item_active",
        "evaluation_item",
        ["chunk_id", "question_id", "question_revision"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "finding",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("question_revision", sa.Integer(), nullable=False),
        sa.Column("classification_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column(
            "strength",
            sa.Enum("NONE", "WEAK", "MEDIUM", "STRONG", name="finding_strength"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column(
            "decided_by", sa.Enum("CLASSIFIER", "LLM", name="finding_decided_by"), nullable=False
        ),
        sa.Column("option_key", sa.Text(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("quote_en", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "SUPERSEDED", "REJECTED", name="finding_status"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_finding_confidence_range")),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_finding_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["chunk.id"], name=op.f("fk_finding_chunk_id_chunk"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["classification_id"],
            ["classification.id"],
            name=op.f("fk_finding_classification_id_classification"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["signal_question.id"],
            name=op.f("fk_finding_question_id_signal_question"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finding")),
        sa.UniqueConstraint("classification_id", name=op.f("uq_finding_classification_id")),
    )
    op.create_index("ix_finding_account_status", "finding", ["account_id", "status"], unique=False)
    op.create_table(
        "alert",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Enum("STRONG_SIGNAL", "BAND_UP", name="alert_kind"), nullable=False),
        sa.Column("finding_id", sa.UUID(), nullable=True),
        sa.Column("score_id", sa.UUID(), nullable=True),
        sa.Column("acknowledged_by", sa.UUID(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_alert_account_id_account"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by"],
            ["app_user.id"],
            name=op.f("fk_alert_acknowledged_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["finding.id"],
            name=op.f("fk_alert_finding_id_finding"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["score_id"],
            ["account_score.id"],
            name=op.f("fk_alert_score_id_account_score"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name=op.f("fk_alert_service_id_service"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert")),
        sa.UniqueConstraint("finding_id", name=op.f("uq_alert_finding_id")),
        sa.UniqueConstraint("score_id", name=op.f("uq_alert_score_id")),
    )
    op.create_table(
        "finding_feedback",
        sa.Column("finding_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "verdict", sa.Enum("CORRECT", "WRONG", name="finding_feedback_verdict"), nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["finding.id"],
            name=op.f("fk_finding_feedback_finding_id_finding"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_finding_feedback_user_id_app_user"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finding_feedback")),
    )


def downgrade() -> None:
    raise NotImplementedError(
        "0001_sql_store is the first migration and provides no downgrade: "
        "a schema change goes forward, in a new migration."
    )
