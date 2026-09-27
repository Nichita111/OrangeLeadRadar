"""Adds [`account`](/architecture/sql-store.md#account) `relationship_status` (`S-ACC-06`,
`B-41`): the team's relationship with the company, set by a user and shared by every service. Not
null, defaulting to `PROSPECT`, which backfills existing rows. No rule reads it, so it enqueues no
run and needs no grant change (`account` is already granted by migration `0002`).

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

_ENUM_NAME = "account_relationship_status"
_ENUM_VALUES = ("PROSPECT", "IN_TALKS", "CLIENT", "PAST_CLIENT", "DO_NOT_CONTACT")


def upgrade() -> None:
    relationship_status = postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME)
    relationship_status.create(op.get_bind())
    op.add_column(
        "account",
        sa.Column(
            "relationship_status",
            relationship_status,
            server_default="PROSPECT",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("account", "relationship_status")
    postgresql.ENUM(name=_ENUM_NAME).drop(op.get_bind())
