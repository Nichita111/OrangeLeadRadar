"""The [`user_invite`](/architecture/sql-store.md#user_invite) table of invite links
(`S-SEC-05`, [ADR-21](/architecture/adrs/adr-21-invite-links-and-the-invite-scene.md)).
`leadradar_app` gets its privileges from migration `0002`'s default privileges.

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
    op.create_table(
        "user_invite",
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("SALES", "ADMIN", name="app_user_role", create_type=False),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("invited_by", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
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
            ["invited_by"],
            ["app_user.id"],
            name=op.f("fk_user_invite_invited_by_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_user_invite_user_id_app_user"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_invite")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_invite_token_hash")),
    )


def downgrade() -> None:
    op.drop_table("user_invite")
