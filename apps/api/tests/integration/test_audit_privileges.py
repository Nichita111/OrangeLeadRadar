"""Integration tests of the application role's database privileges ([Runtime](
/architecture/overview.md#runtime), G1): `leadradar_app` may read and write every table but only
read and append [`audit_event`](/architecture/sql-store.md#audit_event) (`AC-55`)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import ProgrammingError

from tests.integration import factories as f

pytestmark = pytest.mark.integration


def test_the_application_role_can_insert_and_select_audit_event_but_not_update_or_delete_it(
    sync_connection: Connection,
) -> None:
    user_id = f.make_app_user(sync_connection)
    row_id: uuid.UUID = sync_connection.execute(
        text(
            "INSERT INTO audit_event (occurred_at, actor_id, kind, action, payload) "
            "VALUES (now(), :actor_id, 'USER', 'USER_CREATED', '{}'::jsonb) RETURNING id"
        ),
        {"actor_id": user_id},
    ).scalar_one()

    read_back: uuid.UUID = sync_connection.execute(
        text("SELECT id FROM audit_event WHERE id = :id"), {"id": row_id}
    ).scalar_one()
    assert read_back == row_id

    with pytest.raises(ProgrammingError, match="permission denied"), sync_connection.begin_nested():
        sync_connection.execute(
            text("UPDATE audit_event SET action = 'LOGOUT' WHERE id = :id"), {"id": row_id}
        )

    with pytest.raises(ProgrammingError, match="permission denied"), sync_connection.begin_nested():
        sync_connection.execute(text("DELETE FROM audit_event WHERE id = :id"), {"id": row_id})


def test_the_application_role_can_write_every_other_table_and_is_not_a_superuser(
    sync_connection: Connection,
) -> None:
    industry_code = f.make_industry(sync_connection)
    sync_connection.execute(
        text("UPDATE industry SET label = 'Renamed' WHERE code = :code"), {"code": industry_code}
    )
    sync_connection.execute(
        text("DELETE FROM industry WHERE code = :code"), {"code": industry_code}
    )

    is_superuser: bool = sync_connection.execute(
        text("SELECT rolsuper FROM pg_roles WHERE rolname = 'leadradar_app'")
    ).scalar_one()
    assert is_superuser is False


def test_the_application_role_cannot_create_or_drop_a_table(sync_connection: Connection) -> None:
    table_name = f"throwaway_{uuid.uuid4().hex[:8]}"
    with pytest.raises(ProgrammingError, match="permission denied"), sync_connection.begin_nested():
        sync_connection.execute(text(f"CREATE TABLE {table_name} (id uuid)"))
