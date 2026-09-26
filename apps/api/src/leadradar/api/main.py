"""Entry point `leadradar-api` ([Runtime](/architecture/services/api.md#runtime)): builds
settings, configures JSON logging, applies the Alembic migrations synchronously (failing fast
and logging one JSON line if that fails), then serves the app."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from alembic.config import Config
from pydantic import ValidationError

from alembic import command
from leadradar.api.app import create_app
from leadradar.logs import configure_json_logging
from leadradar.settings import ApiSettings

logger = logging.getLogger(__name__)

# apps/api/alembic.ini and apps/api/alembic/, found relative to this module's own file so the
# entry point works regardless of the process's working directory.
_API_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI_PATH = _API_ROOT / "alembic.ini"
_ALEMBIC_SCRIPT_LOCATION = _API_ROOT / "alembic"


def apply_migrations(settings: ApiSettings) -> None:
    """Runs every pending Alembic migration up to head, over the given settings."""
    config = Config(str(_ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(_ALEMBIC_SCRIPT_LOCATION))
    config.attributes["settings"] = settings
    command.upgrade(config, "head")


def run() -> None:
    """`leadradar-api`: applies migrations, then serves `create_app(settings)` on port 8000."""
    configure_json_logging("INFO")
    try:
        settings = ApiSettings()
    except ValidationError:
        logger.exception("Invalid configuration; the api will not start")
        sys.exit(1)
    configure_json_logging(settings.log_level)

    try:
        apply_migrations(settings)
    except Exception:
        logger.exception("Migration failed; the api will not start")
        sys.exit(1)

    import uvicorn

    uvicorn.run(create_app(settings), host="0.0.0.0", port=8000, log_config=None)


if __name__ == "__main__":
    run()
