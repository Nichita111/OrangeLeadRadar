"""Typed errors of the Alerts capability (`API-49`), mapped once at the edge (`api/errors.py`)
onto `404 NOT_FOUND`."""

from __future__ import annotations


class AlertError(Exception):
    """Base of every typed error this capability raises."""


class AlertNotFound(AlertError):
    """No [`alert`](/architecture/sql-store.md#alert) row for the given id (`API-49`)."""
