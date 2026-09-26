"""Typed errors of the runs capability, mapped once onto the envelope by `api/errors.py`
([Runs and source plug-ins contracts]
(/architecture/interfaces.md#runs-and-source-plug-ins-contracts))."""

from __future__ import annotations


class RunsError(Exception):
    """Base of the runs capability's errors."""


class RunNotFound(RunsError):
    """`API-35`, `API-36`: no run has this id (`404 NOT_FOUND`)."""


class RefreshAccountNotFound(RunsError):
    """`API-33`: no account has this id (`404 NOT_FOUND`)."""


class AccountInactive(RunsError):
    """`API-33`: the account is `INACTIVE` (`409 CONFLICT`)."""


class RunFinished(RunsError):
    """`API-36`: the run is already final (`409 CONFLICT`)."""


class SourcePluginNotFound(RunsError):
    """`API-38`: no `source_plugin` row has this code (`404 NOT_FOUND`)."""
