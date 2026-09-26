"""Typed errors for the scoring capability.

Mapped to HTTP codes at the api edge (`api/scoring.py`).
"""

from __future__ import annotations


class ScoringError(Exception):
    """Base class for scoring capability errors."""


class NotADraft(ScoringError):
    """Raised when the target scoring config is not in DRAFT status."""

    def __init__(self, config_id: str, status: str) -> None:
        self.config_id = config_id
        self.status = status
        super().__init__(
            f"Scoring config {config_id!r} has status {status!r}; only DRAFT can be activated."
        )


class ScoringConfigNotFound(ScoringError):
    """Raised when the target scoring config does not exist."""

    def __init__(self, config_id: str) -> None:
        self.config_id = config_id
        super().__init__(f"Scoring config {config_id!r} not found.")
