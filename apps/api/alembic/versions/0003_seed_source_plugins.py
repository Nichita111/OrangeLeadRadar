"""Seeds the seven [`source_plugin`](/architecture/sql-store.md#source_plugin) rows (G6,
`S-ING-01`): one row per plug-in value, with its Admin switch defaulting on and its rate limit
and daily quota from the Seeded values table `source_plugin` now documents. A plug-in that needs
a key stays unavailable until the key is configured, whatever `enabled` says
([Plug-in availability](/architecture/rules.md#plug-in-availability)), so seeding every switch on
is harmless and needs no per-plugin exception. No column change.

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

# `(code, rate_limit_per_minute, daily_quota)`, the Seeded values table of
# [`source_plugin`](/architecture/sql-store.md#source_plugin); every plug-in starts `enabled`.
_SEEDED_PLUGINS: tuple[tuple[str, int, int | None], ...] = (
    ("GDELT", 10, None),
    ("RSS", 30, None),
    ("WEBSITE", 30, None),
    ("CAREERS", 30, None),
    ("CRUNCHBASE", 20, 200),
    ("NEWSAPI", 10, 100),
    ("SERPAPI", 10, 100),
)

_source_plugin = sa.table(
    "source_plugin",
    sa.column("code", sa.Text()),
    sa.column("enabled", sa.Boolean()),
    sa.column("rate_limit_per_minute", sa.Integer()),
    sa.column("daily_quota", sa.Integer()),
)


def upgrade() -> None:
    op.bulk_insert(
        _source_plugin,
        [
            {
                "code": code,
                "enabled": True,
                "rate_limit_per_minute": rate_limit_per_minute,
                "daily_quota": daily_quota,
            }
            for code, rate_limit_per_minute, daily_quota in _SEEDED_PLUGINS
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.delete(_source_plugin).where(
            _source_plugin.c.code.in_([code for code, _, _ in _SEEDED_PLUGINS])
        )
    )
