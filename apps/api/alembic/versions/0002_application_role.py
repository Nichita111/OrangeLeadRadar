"""Grants to `leadradar_app` ([Runtime](/architecture/overview.md#runtime), G1): the application
role created by [`db/init/01_application_role.sh`](/../../db/init/01_application_role.sh) may
read and write every table of the store except
[`audit_event`](/architecture/sql-store.md#audit_event), where it may only `SELECT` and `INSERT`
([Constraints and indexes](/architecture/sql-store.md#constraints-and-indexes)). `ALTER DEFAULT
PRIVILEGES` covers a table a later migration creates, run as the same owner; a later migration
that adds an append-only table revokes explicitly instead. No table or column change.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

_APPLICATION_ROLE = "leadradar_app"

# Every table of [sql-store.md](/architecture/sql-store.md), in the order migration 0001 creates
# them; `audit_event` is the one append-only exception.
_APPEND_ONLY_TABLES = frozenset({"audit_event"})

_ALL_TABLES = (
    "app_user",
    "industry",
    "market",
    "plugin_usage",
    "service",
    "source_plugin",
    "account",
    "auth_session",
    "scoring_config",
    "signal_question",
    "account_alias",
    "account_source",
    "contact",
    "disqualifier_override",
    "pipeline_run",
    "account_score",
    "audit_event",
    "document",
    "evaluation_result",
    "job",
    "outreach_draft",
    "chunk",
    "crm_sync",
    "discovery_candidate",
    "document_triage",
    "lead_feedback",
    "classification",
    "evaluation_item",
    "finding",
    "alert",
    "finding_feedback",
)


def upgrade() -> None:
    op.execute(f"GRANT USAGE ON SCHEMA public TO {_APPLICATION_ROLE}")
    for table in _ALL_TABLES:
        privileges = (
            "SELECT, INSERT" if table in _APPEND_ONLY_TABLES else "SELECT, INSERT, UPDATE, DELETE"
        )
        op.execute(f"GRANT {privileges} ON {table} TO {_APPLICATION_ROLE}")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {_APPLICATION_ROLE}"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {_APPLICATION_ROLE}"
    )
    for table in _ALL_TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM {_APPLICATION_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {_APPLICATION_ROLE}")
