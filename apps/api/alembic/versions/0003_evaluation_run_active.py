"""Partial unique index enforcing one queued or running `EVALUATION` run at a time (D2 of
`.work/labelling-and-quality/design.md`, `API-53`), matching the `ACCOUNT_REFRESH` and
`DISCOVERY` indexes of migration `0001`. No table, column or grant change: `pipeline_run` is
already granted to `leadradar_app` by migration `0002`.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

_INDEX_NAME = "uq_pipeline_run_evaluation_active"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        "pipeline_run",
        ["kind"],
        unique=True,
        postgresql_where=sa.text("kind = 'EVALUATION' AND status IN ('QUEUED', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="pipeline_run")
