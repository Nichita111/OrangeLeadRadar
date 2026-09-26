"""AC-55 (docs/requirements/acceptance.md), the clause this task's `qa-report.md` carries in
scope: "the application's database role has no `UPDATE` or `DELETE` privilege on `audit_event`."

`.work/auth-and-audit/task.md` defers every other clause of AC-55 (the audit rows of a refresh,
a question change, a scoring activation, an exception and an AI call) to the tasks that build
those actions.

docs/architecture/overview.md#runtime names the two database roles: the owner `leadradar`
(only it applies migrations, through `MIGRATION_DATABASE_URL`) and the application role
`leadradar_app`, which "may read and write every table but only read and append
[`audit_event`]". docs/architecture/sql-store.md#audit_event: "The application role holds only
`SELECT` and `INSERT` on it." This is checked by querying the grants Postgres itself records for
`leadradar_app` on `audit_event` - the database's own account of its role's privileges, not the
implementation that requested them.
"""

from __future__ import annotations

import pytest

from conftest import psql


@pytest.mark.ac("AC-55")
def test_application_database_role_has_no_update_or_delete_privilege_on_audit_event(stack):
    env = stack["env"]
    project = stack["project"]

    result = psql(
        project, env, "leadradar", env["POSTGRES_PASSWORD"],
        "SELECT privilege_type FROM information_schema.role_table_grants "
        "WHERE grantee = 'leadradar_app' AND table_name = 'audit_event' "
        "ORDER BY privilege_type;",
    )
    assert result.returncode == 0, result.stderr
    granted = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    assert granted, "expected leadradar_app to hold some privilege on audit_event (SELECT, INSERT)"
    assert "UPDATE" not in granted, granted
    assert "DELETE" not in granted, granted
