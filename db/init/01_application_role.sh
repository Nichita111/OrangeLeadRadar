#!/bin/bash
# Creates the application role of [Runtime](/architecture/overview.md#runtime): a non-superuser
# login used by the api and the worker through `DATABASE_URL`, granted its privileges by the
# Alembic migration `0002_application_role.py` (the owner alone may `GRANT`). Mounted at
# `/docker-entrypoint-initdb.d/` so Compose's `db` container runs it once, on an empty volume, as
# its own superuser; the integration and contract test fixture runs this exact file inside its
# test container too, so both environments share one statement (G1, `task.md`).
set -euo pipefail

psql -v ON_ERROR_STOP=1 -v app_password="$APP_DB_PASSWORD" \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE leadradar_app WITH LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
EOSQL
