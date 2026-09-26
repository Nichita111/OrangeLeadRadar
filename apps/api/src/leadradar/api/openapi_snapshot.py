"""Exports `create_app().openapi()` to the committed snapshot `apps/api/openapi.json`
([api Design](/architecture/services/api.md#design)): `uv run poe openapi-snapshot`.
The frontend's typed client is generated from this file, never written by hand."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import SecretStr

from leadradar.api.app import create_app
from leadradar.settings import ApiSettings

SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "openapi.json"


def main() -> None:
    # The schema depends only on the routes, never on a live database or secret, so a
    # placeholder `DATABASE_URL` is enough to build the app for introspection.
    settings = ApiSettings(database_url=SecretStr("postgresql://placeholder@localhost/placeholder"))
    app = create_app(settings)
    schema = app.openapi()
    SNAPSHOT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
