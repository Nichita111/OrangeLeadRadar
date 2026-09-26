"""Imports every model module so that `Base.metadata` is complete wherever it is imported."""

from __future__ import annotations

from leadradar.db.models import (  # noqa: F401
    accounts,
    audit,
    configuration,
    feedback,
    identity,
    ingestion,
    outreach,
    signals,
)

__all__ = [
    "accounts",
    "audit",
    "configuration",
    "feedback",
    "identity",
    "ingestion",
    "outreach",
    "signals",
]
