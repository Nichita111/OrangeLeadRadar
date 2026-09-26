"""Configuration of the worker process: [worker Runtime](/architecture/services/worker.md#runtime).
Only the keys the worker's code reads today are here; `DATABASE_URL` is added with the job loop
that first reads it ([S-PIP-01])."""

from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from leadradar.ai.settings import AiGatewaySettings


class WorkerSettings(AiGatewaySettings):
    """The worker process's configuration; fixture mode, `CLOCK_FILE` and the AI gateway's keys
    come from `AiGatewaySettings`."""

    model_config = SettingsConfigDict(extra="ignore")

    log_level: str = "INFO"
