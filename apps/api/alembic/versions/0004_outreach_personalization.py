"""Outreach preferences, provider facts, and engagement status.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    provider_status = postgresql.ENUM("ACTIVE", "INACTIVE", name="provider_fact_status")
    engagement_status = postgresql.ENUM(
        "NOT_CONTACTED",
        "CONTACTED",
        "ANSWERED",
        "MEETING_BOOKED",
        "REJECTED",
        name="engagement_status_status",
    )
    engagement_origin = postgresql.ENUM("MANUAL", "HUBSPOT", name="engagement_status_origin")
    provider_status.create(op.get_bind(), checkfirst=True)
    engagement_status.create(op.get_bind(), checkfirst=True)
    engagement_origin.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TYPE audit_event_kind ADD VALUE IF NOT EXISTS 'ENGAGEMENT'")

    op.create_table(
        "provider_fact",
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("service_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("status", provider_status, nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_fact")),
    )
    op.add_column(
        "outreach_draft",
        sa.Column(
            "provider_fact_ids",
            postgresql.ARRAY(sa.UUID()),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "outreach_draft",
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "engagement_status",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("status", engagement_status, nullable=False),
        sa.Column("origin", engagement_origin, nullable=False),
        sa.Column("set_by", sa.UUID(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
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
            ["account_id"], ["account.id"], name=op.f("fk_engagement_status_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["service.id"], name=op.f("fk_engagement_status_service_id_service")
        ),
        sa.ForeignKeyConstraint(
            ["set_by"], ["app_user.id"], name=op.f("fk_engagement_status_set_by_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_engagement_status")),
    )
    op.create_index(
        "ix_engagement_status_in_force",
        "engagement_status",
        ["account_id", "service_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_engagement_status_in_force", table_name="engagement_status")
    op.drop_table("engagement_status")
    op.drop_column("outreach_draft", "preferences")
    op.drop_column("outreach_draft", "provider_fact_ids")
    op.drop_table("provider_fact")
    postgresql.ENUM(name="engagement_status_origin").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="engagement_status_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="provider_fact_status").drop(op.get_bind(), checkfirst=True)
